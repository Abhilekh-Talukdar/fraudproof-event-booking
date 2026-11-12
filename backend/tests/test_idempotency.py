from datetime import timedelta

from app import db
from app.models import (
    IdempotencyRecord,
    Inventory,
    Order,
    PaymentIdempotencyRecord,
    Reservation,
    Ticket,
    utcnow,
)


def reserve(client, event_id, key, quantity=1):
    return client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": quantity},
        headers={"Idempotency-Key": key},
    )


def pay(client, reservation_id, key):
    return client.post(
        f"/api/reservations/{reservation_id}/mock-payment",
        json={"outcome": "APPROVED"},
        headers={"Idempotency-Key": key},
    )


def test_expired_reservation_key_can_be_reused(client, app, event_factory):
    event_id = event_factory(capacity=3)
    first = reserve(client, event_id, "reusable-reservation-key")
    assert first.status_code == 201

    with app.app_context():
        record = db.session.query(IdempotencyRecord).filter_by(
            key="reusable-reservation-key"
        ).one()
        record.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()

    second = reserve(client, event_id, "reusable-reservation-key")
    assert second.status_code == 201
    assert second.json["reservationId"] != first.json["reservationId"]

    with app.app_context():
        assert db.session.query(Reservation).count() == 2
        assert db.session.query(IdempotencyRecord).filter(
            IdempotencyRecord.key == "reusable-reservation-key",
            IdempotencyRecord.expires_at > utcnow(),
        ).count() == 1
        inventory = db.session.get(Inventory, event_id)
        assert (inventory.available_quantity, inventory.reserved_quantity) == (1, 2)


def test_expired_payment_key_replays_current_state_without_duplicate_sale(client, app, event_factory):
    event_id = event_factory(capacity=2)
    hold = reserve(client, event_id, "payment-expiry-hold")
    assert hold.status_code == 201
    reservation_id = hold.json["reservationId"]

    first = pay(client, reservation_id, "reusable-payment-key")
    assert first.status_code == 201
    assert len(first.json["tickets"]) == 1

    with app.app_context():
        record = db.session.query(PaymentIdempotencyRecord).filter_by(
            key="reusable-payment-key"
        ).one()
        record.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()

    second = pay(client, reservation_id, "reusable-payment-key")
    assert second.status_code == 200

    with app.app_context():
        assert db.session.query(Order).count() == 1
        assert db.session.query(Ticket).count() == 1
        assert db.session.query(PaymentIdempotencyRecord).filter(
            PaymentIdempotencyRecord.key == "reusable-payment-key",
            PaymentIdempotencyRecord.expires_at > utcnow(),
        ).count() == 1


def test_idempotency_purge_cli_is_bounded_and_preserves_unexpired_records(client, app, event_factory):
    event_id = event_factory(capacity=5)
    reservations = []
    for index in range(3):
        hold = reserve(client, event_id, f"retention-hold-{index}")
        assert hold.status_code == 201
        reservations.append(hold.json["reservationId"])
        if index < 2:
            payment = pay(client, reservations[-1], f"retention-payment-{index}")
            assert payment.status_code == 201

    with app.app_context():
        expired_at = utcnow() - timedelta(seconds=1)
        for key in ("retention-hold-0", "retention-hold-1"):
            db.session.query(IdempotencyRecord).filter_by(key=key).one().expires_at = expired_at
        for key in ("retention-payment-0", "retention-payment-1"):
            db.session.query(PaymentIdempotencyRecord).filter_by(key=key).one().expires_at = expired_at
        db.session.commit()

    runner = app.test_cli_runner()
    first = runner.invoke(args=["idempotency", "purge", "--batch-size", "1"])
    assert first.exit_code == 0
    assert first.output.strip() == (
        "Purged 2 expired idempotency record(s): 1 reservation and 1 payment."
    )

    with app.app_context():
        assert db.session.query(IdempotencyRecord).count() == 2
        assert db.session.query(PaymentIdempotencyRecord).count() == 1

    second = runner.invoke(args=["idempotency", "purge", "--batch-size", "1"])
    assert second.exit_code == 0
    assert second.output.strip() == (
        "Purged 2 expired idempotency record(s): 1 reservation and 1 payment."
    )

    with app.app_context():
        assert db.session.query(IdempotencyRecord).count() == 1
        assert db.session.query(PaymentIdempotencyRecord).count() == 0
