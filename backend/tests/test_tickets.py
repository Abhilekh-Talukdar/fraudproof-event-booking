import base64
import json

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
