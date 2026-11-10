import base64
import binascii
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from flask import current_app
from sqlalchemy import update

from .. import db
from ..models import Event, Order, Reservation, Ticket, TicketStatus, utcnow


class TicketError(Exception):
    status_code = 400
    code = "ticket_error"


class InvalidTicket(TicketError):
    status_code = 400
    code = "invalid_ticket"


class TicketRejected(TicketError):
    status_code = 409
    code = "ticket_rejected"


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload_bytes: bytes) -> str:
    secret = current_app.config["TICKET_SIGNING_SECRET"].encode("utf-8")
    return hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()


def _ticket_payload(ticket: Ticket) -> dict:
    return {
        "eventId": ticket.event_id,
        "expiresAt": int(ticket.expires_at.timestamp()),
        "issuedAt": int(ticket.issued_at.timestamp()),
        "nonce": ticket.nonce,
        "orderId": ticket.order_id,
        "ticketId": ticket.id,
        "version": ticket.version,
    }


def encode_ticket(ticket: Ticket) -> str:
    payload = _canonical_payload(_ticket_payload(ticket))
    return f"{_b64encode(payload)}.{_b64encode(bytes.fromhex(ticket.signature))}"


def issue_tickets(*, order: Order, reservation: Reservation, event: Event) -> list[Ticket]:
    """Create signed, QR-ready tickets inside the successful payment transaction."""
    issued_at = utcnow()
    expires_at = event.starts_at + timedelta(seconds=current_app.config["TICKET_VALIDITY_AFTER_EVENT_SECONDS"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    holders = reservation.attendee_names or []
    tickets = []
    for index in range(reservation.quantity):
        ticket = Ticket(
            id=str(uuid4()),
            order_id=order.id,
            event_id=event.id,
            holder_name=holders[index] if index < len(holders) else None,
            version=1,
            status=TicketStatus.ISSUED,
            nonce=secrets.token_urlsafe(32),
            issued_at=issued_at,
            expires_at=expires_at,
        )
        payload = _canonical_payload(_ticket_payload(ticket))
        ticket.payload_hash = hashlib.sha256(payload).hexdigest()
        ticket.signature = _sign(payload)
        db.session.add(ticket)
        tickets.append(ticket)
    return tickets


def ticket_payload(ticket: Ticket, *, include_token: bool = False) -> dict:
    result = {
        "ticketId": ticket.id,
        "orderId": ticket.order_id,
        "eventId": ticket.event_id,
        "holderName": ticket.holder_name,
        "version": ticket.version,
        "status": ticket.status.value,
        "expiresAt": ticket.expires_at.isoformat(),
    }
    if include_token:
        result["token"] = encode_ticket(ticket)
    return result


def _decode_and_authenticate(token: str) -> dict:
    try:
        encoded_payload, encoded_signature = token.split(".")
        payload_bytes = _b64decode(encoded_payload)
        supplied_signature = _b64decode(encoded_signature).hex()
        expected_signature = _sign(payload_bytes)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise InvalidTicket("Ticket signature is invalid.")
        payload = json.loads(payload_bytes)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as error:
        raise InvalidTicket("Ticket token is malformed.") from error
    required = {"ticketId", "eventId", "orderId", "version", "issuedAt", "expiresAt", "nonce"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise InvalidTicket("Ticket payload is invalid.")
    ticket_id = payload["ticketId"]
    event_id = payload["eventId"]
    order_id = payload["orderId"]
    version = payload["version"]
    issued_at = payload["issuedAt"]
    expires_at = payload["expiresAt"]
    nonce = payload["nonce"]

    # bool is a subclass of int in Python, but it is not a valid JSON integer
    # for an identifier, version, or Unix timestamp in this token schema.
    is_integer = lambda value: isinstance(value, int) and not isinstance(value, bool)
    valid_strings = (
        isinstance(ticket_id, str) and 0 < len(ticket_id) <= 36 and ticket_id.strip(),
        isinstance(order_id, str) and 0 < len(order_id) <= 36 and order_id.strip(),
        isinstance(nonce, str) and 0 < len(nonce) <= 64 and nonce.strip(),
    )
    valid_integers = (
        is_integer(event_id) and event_id > 0,
        is_integer(version) and version > 0,
        is_integer(issued_at) and issued_at > 0,
        is_integer(expires_at) and expires_at > 0,
    )
    if not all(valid_strings) or not all(valid_integers) or expires_at < issued_at:
        raise InvalidTicket("Ticket payload has invalid fields.")
    return payload


def verify_and_consume(*, token: str, expected_event_id: int | None = None) -> dict:
    payload = _decode_and_authenticate(token)
    now = utcnow()
    if payload["expiresAt"] < int(now.timestamp()):
        raise TicketRejected("Ticket has expired.")
    ticket = db.session.get(Ticket, payload["ticketId"])
    if not ticket:
        raise TicketRejected("Ticket was not found.")
    canonical = _canonical_payload(payload)
    if not hmac.compare_digest(ticket.payload_hash, hashlib.sha256(canonical).hexdigest()):
        raise TicketRejected("Ticket payload does not match the issued ticket.")
    if not hmac.compare_digest(ticket.signature, _sign(canonical)):
        raise TicketRejected("Ticket signature does not match the issued ticket.")
    if expected_event_id is not None and ticket.event_id != expected_event_id:
        raise TicketRejected("Ticket is for a different event.")
    ticket_expires_at = ticket.expires_at
    if ticket_expires_at.tzinfo is None:
        ticket_expires_at = ticket_expires_at.replace(tzinfo=timezone.utc)
    if ticket_expires_at < now:
        raise TicketRejected("Ticket has expired.")

    # This conditional update is the admission concurrency boundary: two
    # scanners may verify the signature, but only one can consume ISSUED.
    result = db.session.execute(
        update(Ticket)
        .where(
            Ticket.id == ticket.id,
            Ticket.status == TicketStatus.ISSUED,
            Ticket.version == payload["version"],
        )
        .values(status=TicketStatus.USED, used_at=now, updated_at=now)
    )
    if result.rowcount != 1:
        db.session.rollback()
        raise TicketRejected("Ticket has already been used or is no longer valid.")
    db.session.commit()
    return {
        "accepted": True,
        "ticketId": ticket.id,
        "eventId": ticket.event_id,
        "message": "Ticket accepted.",
    }
