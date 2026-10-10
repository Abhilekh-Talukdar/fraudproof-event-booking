"""Reservation ownership regression tests."""
from app import db
from app.models import Reservation


def test_reservation_tracks_authenticated_user_ownership(client, app, event_factory):
    event_id = event_factory()
    reservation = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "owner-reservation"},
    ).json
    
    with app.app_context():
        res_db = db.session.get(Reservation, reservation['reservationId'])
        assert res_db.user_id is not None, "user_id should not be None"
    
    response = client.post(
        f"/api/reservations/{reservation['reservationId']}/mock-payment",
        json={"outcome": "APPROVED"},
        headers={"Idempotency-Key": "owner-payment"},
    )
    assert response.status_code == 201
