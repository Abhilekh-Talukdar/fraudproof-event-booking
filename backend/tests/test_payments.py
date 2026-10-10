from datetime import timedelta

from app import db
from app.models import Inventory, Order, OrderStatus, Reservation, ReservationStatus, utcnow


def create_hold(client, event_id, quantity=1, key="reservation-key"):
    response = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": quantity},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json["reservationId"]


def pay(client, reservation_id, outcome, key):
    return client.post(
        f"/api/reservations/{reservation_id}/mock-payment",
        json={"outcome": outcome},
        headers={"Idempotency-Key": key},
    )


def test_approved_payment_converts_held_inventory_to_sold_once(client, app, event_factory):
    event_id = event_factory(capacity=3)
    reservation_id = create_hold(client, event_id, quantity=2)

    first = pay(client, reservation_id, "APPROVED", "payment-retry-key")
    second = pay(client, reservation_id, "APPROVED", "payment-retry-key")

    assert first.status_code == second.status_code == 201
    assert first.json == second.json
    assert first.json["status"] == "PAID"
    with app.app_context():
        inventory = db.session.get(Inventory, event_id)
        reservation = db.session.get(Reservation, reservation_id)
        assert (inventory.available_quantity, inventory.reserved_quantity, inventory.sold_quantity) == (1, 0, 2)
        assert reservation.status == ReservationStatus.CONFIRMED
        assert db.session.query(Order).count() == 1


def test_declined_payment_releases_hold_and_preserves_inventory_invariant(client, app, event_factory):
    event_id = event_factory(capacity=2)
    reservation_id = create_hold(client, event_id, quantity=2)

    first = pay(client, reservation_id, "DECLINED", "decline-key")
    second = pay(client, reservation_id, "DECLINED", "decline-key")

    assert first.status_code == second.status_code == 402
    assert first.json == second.json
    assert first.json["status"] == "PAYMENT_FAILED"
    with app.app_context():
        inventory = db.session.get(Inventory, event_id)
        reservation = db.session.get(Reservation, reservation_id)
        order = db.session.query(Order).one()
        assert (inventory.available_quantity, inventory.reserved_quantity, inventory.sold_quantity) == (2, 0, 0)
        assert inventory.total_quantity == inventory.available_quantity + inventory.reserved_quantity + inventory.sold_quantity
        assert reservation.status == ReservationStatus.RELEASED
        assert order.status == OrderStatus.PAYMENT_FAILED


def test_expired_reservation_cannot_be_paid_and_inventory_is_restored(client, app, event_factory):
    event_id = event_factory(capacity=1)
    reservation_id = create_hold(client, event_id)
    with app.app_context():
        reservation = db.session.get(Reservation, reservation_id)
        reservation.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()

    response = pay(client, reservation_id, "APPROVED", "expired-payment")

    assert response.status_code == 409
    with app.app_context():
        inventory = db.session.get(Inventory, event_id)
        reservation = db.session.get(Reservation, reservation_id)
        assert (inventory.available_quantity, inventory.reserved_quantity, inventory.sold_quantity) == (1, 0, 0)
        assert reservation.status == ReservationStatus.RELEASED
