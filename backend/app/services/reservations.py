import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Event, IdempotencyRecord, Inventory, Reservation, ReservationStatus, utcnow
from .outbox import enqueue_event


class ReservationError(Exception):
    status_code = 400
    code = "reservation_error"


class EventNotFound(ReservationError):
    status_code = 404
    code = "event_not_found"


class InsufficientInventory(ReservationError):
    status_code = 409
    code = "insufficient_inventory"


class IdempotencyConflict(ReservationError):
    status_code = 422
    code = "idempotency_key_reused_with_different_request"


def request_fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reservation_payload(reservation: Reservation) -> dict:
    return {
        "reservationId": reservation.id,
        "eventId": reservation.event_id,
        "quantity": reservation.quantity,
        "status": reservation.status.value,
        "expiresAt": reservation.expires_at.isoformat(),
    }


def release_expired_reservations() -> int:
    """Release stale holds atomically; a scheduled worker will use this later."""
    now = utcnow()
    expired = db.session.execute(
        select(Reservation).where(
            Reservation.status == ReservationStatus.HELD,
            Reservation.expires_at <= now,
        ).with_for_update()
    ).scalars().all()
    for reservation in expired:
        db.session.execute(
            update(Inventory)
            .where(Inventory.event_id == reservation.event_id)
            .values(
                available_quantity=Inventory.available_quantity + reservation.quantity,
                reserved_quantity=Inventory.reserved_quantity - reservation.quantity,
                version=Inventory.version + 1,
                updated_at=now,
            )
        )
        reservation.status = ReservationStatus.RELEASED
        reservation.updated_at = now
    return len(expired)


def _stored_response(record: IdempotencyRecord, fingerprint: str) -> tuple[dict, int]:
    if record.request_hash != fingerprint:
        raise IdempotencyConflict("This Idempotency-Key was used for a different request.")
    return json.loads(record.response_body), record.response_status


def create_reservation(*, event_id: int, quantity: int, idempotency_key: str, ttl_seconds: int, attendee_names: list[str] | None = None, user_id: str | None = None) -> tuple[dict, int]:
    fingerprint = request_fingerprint({"eventId": event_id, "quantity": quantity, "attendeeNames": attendee_names or [], "userId": user_id})
    existing = db.session.execute(select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)).scalar_one_or_none()
    if existing:
        return _stored_response(existing, fingerprint)

    now = utcnow()
    try:
        release_expired_reservations()
        event = db.session.get(Event, event_id)
        if not event or event.status != "PUBLISHED":
            raise EventNotFound("The requested event does not exist.")

        # PostgreSQL serializes competing writes here; only one request can take
        # the final available ticket(s).
        result = db.session.execute(
            update(Inventory)
            .where(Inventory.event_id == event_id, Inventory.available_quantity >= quantity)
            .values(
                available_quantity=Inventory.available_quantity - quantity,
                reserved_quantity=Inventory.reserved_quantity + quantity,
                version=Inventory.version + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise InsufficientInventory("Not enough tickets remain for this event.")

        reservation = Reservation(
            id=str(uuid4()),
            event_id=event_id,
            user_id=user_id,
            quantity=quantity,
            attendee_names=attendee_names,
            status=ReservationStatus.HELD,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        body = reservation_payload(reservation)
        db.session.add(reservation)
        db.session.add(IdempotencyRecord(
            key=idempotency_key,
            request_hash=fingerprint,
            response_status=201,
            response_body=json.dumps(body, separators=(",", ":")),
            expires_at=now + timedelta(hours=24),
        ))
        # Outbox event written atomically — durable only if commit succeeds.
        enqueue_event(
            event_type="reservation.created",
            aggregate_id=reservation.id,
            payload={
                "reservationId": reservation.id,
                "eventId": reservation.event_id,
                "userId": user_id,
                "quantity": quantity,
                "expiresAt": reservation.expires_at.isoformat(),
            },
        )
        db.session.commit()
        return body, 201
    except ReservationError:
        db.session.rollback()
        raise
    except IntegrityError:
        db.session.rollback()
        existing = db.session.execute(select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)).scalar_one_or_none()
        if existing:
            return _stored_response(existing, fingerprint)
        raise
    except Exception:
        db.session.rollback()
        raise
