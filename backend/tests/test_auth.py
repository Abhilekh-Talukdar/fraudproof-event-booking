from app import db
from app.models import User, UserRole


def test_registration_creates_only_a_regular_user_and_session(app):
    client = app.test_client()
    response = client.post(
        "/api/auth/register",
        json={"email": "person@example.test", "password": "a-strong-password", "role": "ADMIN"},
    )

    assert response.status_code == 201
    assert response.json["user"]["role"] == "USER"
    assert client.get("/api/me").status_code == 200
    with app.app_context():
        assert db.session.query(User).filter_by(email="person@example.test", role=UserRole.ADMIN).count() == 0


def test_protected_reservation_requires_a_session(app, event_factory):
    event_id = event_factory()
    client = app.test_client()
    response = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "unauthenticated"},
    )
    assert response.status_code == 401
    assert response.json["error"] == "authentication_required"


def test_payment_cannot_be_completed_by_another_user(client, app, event_factory):
    event_id = event_factory()
    reservation = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "owner-reservation"},
    ).json
    other = app.test_client()
    assert other.post(
        "/api/auth/register",
        json={"email": "other@example.test", "password": "another-strong-password"},
    ).status_code == 201

    response = other.post(
        f"/api/reservations/{reservation['reservationId']}/mock-payment",
        json={"outcome": "APPROVED"},
        headers={"Idempotency-Key": "other-payment"},
    )
    assert response.status_code == 409

def test_idempotency_key_tied_to_user(client, app, event_factory):
    event_id = event_factory()
    
    # User A creates a reservation
    first = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "shared-key"},
    )
    assert first.status_code == 201

    other = app.test_client()
    other.post(
        "/api/auth/register",
        json={"email": "thief@example.test", "password": "another-strong-password"},
    )
    
    # User B tries to reuse User A's Idempotency Key with the same payload
    second = other.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "shared-key"},
    )
    
    # Should be rejected because the fingerprint includes the user_id, 
    # making it a DIFFERENT request from the same idempotency key.
    assert second.status_code == 422
    assert second.json["error"] == "idempotency_key_reused_with_different_request"
