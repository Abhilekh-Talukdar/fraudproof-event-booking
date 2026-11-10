import base64
import hashlib
import hmac
import json

import pytest

from app import db
from app.models import Ticket, TicketStatus


def reserve_and_pay(client, event_id, names):
    reservation = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": len(names), "attendeeNames": names},
        headers={"Idempotency-Key": "ticket-reservation"},
    )
    assert reservation.status_code == 201
    payment = client.post(
        f"/api/reservations/{reservation.json['reservationId']}/mock-payment",
        json={"outcome": "APPROVED"},
        headers={"Idempotency-Key": "ticket-payment"},
    )
    assert payment.status_code == 201
    return payment.json


def verify(client, token, expected_event_id=None):
    body = {"token": token}
    if expected_event_id is not None:
        body["expectedEventId"] = expected_event_id
    return client.post("/api/tickets/verify", json=body)


def test_successful_payment_issues_signed_ticket_with_ticket_holder(client, app, event_factory):
    event_id = event_factory()
    paid = reserve_and_pay(client, event_id, ["Ada Lovelace"])

    assert paid["status"] == "PAID"
    assert len(paid["tickets"]) == 1
    ticket = paid["tickets"][0]
    assert ticket["holderName"] == "Ada Lovelace"
    assert ticket["token"].count(".") == 1
    with app.app_context():
        stored = db.session.get(Ticket, ticket["ticketId"])
        assert stored.status == TicketStatus.ISSUED
        assert stored.payload_hash
        assert stored.signature


def test_valid_ticket_is_accepted_once_then_replay_is_rejected(client, event_factory):
    event_id = event_factory()
    token = reserve_and_pay(client, event_id, ["Ada"])["tickets"][0]["token"]

    first = verify(client, token, event_id)
    replay = verify(client, token, event_id)

    assert first.status_code == 200
    assert first.json["accepted"] is True
    assert replay.status_code == 409
    assert replay.json["accepted"] is False
    assert replay.json["error"] == "ticket_rejected"


def test_tampered_ticket_payload_is_rejected_before_database_lookup(client, event_factory):
    event_id = event_factory()
    token = reserve_and_pay(client, event_id, ["Ada"])["tickets"][0]["token"]
    payload, signature = token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    decoded["eventId"] = event_id + 1
    altered = base64.urlsafe_b64encode(json.dumps(decoded, separators=(",", ":")).encode()).rstrip(b"=").decode()

    response = verify(client, f"{altered}.{signature}")

    assert response.status_code == 400
    assert response.json["accepted"] is False
    assert response.json["error"] == "invalid_ticket"


def test_ticket_for_another_event_is_rejected_without_consumption(client, app, event_factory):
    event_id = event_factory()
    other_event_id = event_factory()
    token = reserve_and_pay(client, event_id, ["Ada"])["tickets"][0]["token"]

    response = verify(client, token, other_event_id)

    assert response.status_code == 409
    with app.app_context():
        ticket = db.session.query(Ticket).one()
        assert ticket.status == TicketStatus.ISSUED



def sign_payload_for_test(app, payload):
    """Create a correctly signed token so tests reach payload-schema validation."""
    from flask import current_app

    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    with app.app_context():
        secret = current_app.config["TICKET_SIGNING_SECRET"].encode("utf-8")
    signature = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode("ascii")
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded_payload}.{encoded_signature}"


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("ticketId", 123),
        ("eventId", True),
        ("orderId", None),
        ("version", True),
        ("issuedAt", "not-a-timestamp"),
        ("expiresAt", "not-a-timestamp"),
        ("nonce", []),
    ],
)
def test_correctly_signed_ticket_with_invalid_field_types_is_rejected(
    client, app, field, invalid_value
):
    payload = {
        "ticketId": "ticket-placeholder",
        "eventId": 1,
        "orderId": "order-placeholder",
        "version": 1,
        "issuedAt": 1,
        "expiresAt": 2,
        "nonce": "nonce-placeholder",
    }
    payload[field] = invalid_value
    token = sign_payload_for_test(app, payload)

    response = verify(client, token)

    assert response.status_code == 400
    assert response.json["accepted"] is False
    assert response.json["error"] == "invalid_ticket"


def test_correctly_signed_ticket_with_expiry_before_issue_time_is_rejected(client, app):
    payload = {
        "ticketId": "ticket-placeholder",
        "eventId": 1,
        "orderId": "order-placeholder",
        "version": 1,
        "issuedAt": 200,
        "expiresAt": 100,
        "nonce": "nonce-placeholder",
    }
    token = sign_payload_for_test(app, payload)

    response = verify(client, token)

    assert response.status_code == 400
    assert response.json["error"] == "invalid_ticket"


def test_expected_event_id_rejects_boolean_values(client):
    response = client.post(
        "/api/tickets/verify",
        json={"token": "not-a-token", "expectedEventId": True},
    )

    assert response.status_code == 400
    assert response.json["error"] == "expectedEventId must be a positive integer."
