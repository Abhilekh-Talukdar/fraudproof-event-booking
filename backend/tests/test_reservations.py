from app import db
from app.models import Inventory, Reservation, ReservationStatus


def reservation_request(client, event_id, quantity, key):
    return client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": quantity},
        headers={"Idempotency-Key": key},
    )


def test_reservation_decrements_available_inventory_and_preserves_invariant(client, app, event_factory):
    event_id = event_factory(capacity=3)
    response = reservation_request(client, event_id, 2, "reserve-1")

    assert response.status_code == 201
    assert response.json["status"] == "HELD"
    assert response.json["quantity"] == 2
    with app.app_context():
        inventory = db.session.get(Inventory, event_id)
        assert (inventory.total_quantity, inventory.available_quantity, inventory.reserved_quantity, inventory.sold_quantity) == (3, 1, 2, 0)
        assert inventory.total_quantity == inventory.available_quantity + inventory.reserved_quantity + inventory.sold_quantity


def test_idempotent_retry_returns_original_hold_without_consuming_more_inventory(client, app, event_factory):
    event_id = event_factory(capacity=3)
    first = reservation_request(client, event_id, 2, "retry-safe-key")
    second = reservation_request(client, event_id, 2, "retry-safe-key")

    assert first.status_code == second.status_code == 201
    assert first.json == second.json
    with app.app_context():
        assert db.session.query(Reservation).count() == 1
        inventory = db.session.get(Inventory, event_id)
        assert inventory.available_quantity == 1
        assert inventory.reserved_quantity == 2


def test_same_idempotency_key_with_changed_request_is_rejected(client, event_factory):
    event_id = event_factory(capacity=4)
    assert reservation_request(client, event_id, 1, "same-key").status_code == 201
    response = reservation_request(client, event_id, 2, "same-key")

    assert response.status_code == 422
    assert response.json["error"] == "idempotency_key_reused_with_different_request"


def test_insufficient_inventory_does_not_create_a_partial_reservation(client, app, event_factory):
    event_id = event_factory(capacity=1)
    assert reservation_request(client, event_id, 1, "winner").status_code == 201
    response = reservation_request(client, event_id, 1, "loser")

    assert response.status_code == 409
    with app.app_context():
        assert db.session.query(Reservation).filter_by(status=ReservationStatus.HELD).count() == 1
        inventory = db.session.get(Inventory, event_id)
        assert inventory.available_quantity == 0
        assert inventory.reserved_quantity == 1
