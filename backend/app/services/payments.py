import json
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import (
    Event,
    Inventory,
    Order,
    OrderStatus,
    PaymentIdempotencyRecord,
    Reservation,
    ReservationStatus,
    utcnow,
)
from .reservations import IdempotencyConflict, request_fingerprint, release_expired_reservations
from .tickets import issue_tickets, ticket_payload
from .outbox import enqueue_event


class PaymentError(Exception):
    status_code = 400
    code = "payment_error"


class ReservationUnavailable(PaymentError):
    status_code = 409
    code = "reservation_unavailable"


class MockPaymentDeclined(PaymentError):
    status_code = 402
    code = "mock_payment_declined"


class PaymentInvariantError(PaymentError):
    status_code = 500
    code = "payment_inventory_invariant_failure"


def order_payload(order: Order, *, tickets: list | None = None) -> dict:
    result = {
        "orderId": order.id,
        "reservationId": order.reservation_id,
        "status": order.status.value,
        "amount": float(order.amount),
        "currency": order.currency,
        "paymentReference": order.payment_reference,
    }
    if tickets is not None:
        result["tickets"] = [ticket_payload(ticket, include_token=True) for ticket in tickets]
    return result


def _stored_response(record: PaymentIdempotencyRecord, fingerprint: str) -> tuple[dict, int]:
    if record.request_hash != fingerprint:
        raise IdempotencyConflict("This Idempotency-Key was used for a different payment request.")
    return json.loads(record.response_body), record.response_status


def _release_reservation(reservation: Reservation, now) -> None:
    result = db.session.execute(
        update(Inventory)
        .where(Inventory.event_id == reservation.event_id, Inventory.reserved_quantity >= reservation.quantity)
        .values(
            available_quantity=Inventory.available_quantity + reservation.quantity,
            reserved_quantity=Inventory.reserved_quantity - reservation.quantity,
            version=Inventory.version + 1,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        raise PaymentInvariantError("Reservation inventory could not be released safely.")
    reservation.status = ReservationStatus.RELEASED
    reservation.updated_at = now


def confirm_mock_payment(*, reservation_id: str, outcome: str, idempotency_key: str, user_id: str | None = None) -> tuple[dict, int]:
    fingerprint = request_fingerprint({"reservationId": reservation_id, "outcome": outcome, "userId": user_id})
    existing = db.session.execute(
        select(PaymentIdempotencyRecord).where(PaymentIdempotencyRecord.key == idempotency_key)
    ).scalar_one_or_none()
    if existing:
        return _stored_response(existing, fingerprint)

    try:
        # Expiry is a completed state transition, even when this checkout is
        # rejected. Commit it before entering the payment transaction so the
        # rejection rollback cannot put inventory back into HELD.
        release_expired_reservations()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    now = utcnow()
    try:
        reservation = db.session.execute(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if not reservation or reservation.status == ReservationStatus.RELEASED:
            raise ReservationUnavailable("This reservation has expired or is no longer payable.")
        if user_id is not None and reservation.user_id != user_id:
            raise ReservationUnavailable("This reservation is not owned by the current user.")

        order = db.session.execute(
            select(Order).where(Order.reservation_id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if reservation.status == ReservationStatus.CONFIRMED:
            if not order:
                raise PaymentInvariantError("Confirmed reservation is missing its order.")
            body, status = order_payload(order), 200
        else:
            event = db.session.get(Event, reservation.event_id)
            if not event:
                raise PaymentInvariantError("Reservation event is missing.")
            if not order:
                order = Order(
                    id=str(uuid4()),
                    reservation_id=reservation.id,
                    status=OrderStatus.PAYMENT_PENDING,
                    amount=Decimal(event.price) * reservation.quantity,
                    currency="INR",
                )
                db.session.add(order)

            if outcome == "DECLINED":
                order.status = OrderStatus.PAYMENT_FAILED
                order.payment_reference = f"mock_declined_{uuid4().hex}"
                _release_reservation(reservation, now)
                # Outbox event — written atomically with the order/inventory update.
                enqueue_event(
                    event_type="payment.declined",
                    aggregate_id=order.id,
                    payload={
                        "orderId": order.id,
                        "reservationId": reservation.id,
                        "userId": reservation.user_id,
                        "amount": float(order.amount),
                        "currency": order.currency,
                    },
                )
                body, status = order_payload(order), 402
            else:
                result = db.session.execute(
                    update(Inventory)
                    .where(Inventory.event_id == reservation.event_id, Inventory.reserved_quantity >= reservation.quantity)
                    .values(
                        reserved_quantity=Inventory.reserved_quantity - reservation.quantity,
                        sold_quantity=Inventory.sold_quantity + reservation.quantity,
                        version=Inventory.version + 1,
                        updated_at=now,
                    )
                )
                if result.rowcount != 1:
                    raise PaymentInvariantError("Reserved inventory could not be confirmed safely.")
                reservation.status = ReservationStatus.CONFIRMED
                reservation.updated_at = now
                order.status = OrderStatus.PAID
                order.payment_reference = f"mock_paid_{uuid4().hex}"
                tickets = issue_tickets(order=order, reservation=reservation, event=event)
                # Outbox event — written atomically with the inventory move and ticket issuance.
                enqueue_event(
                    event_type="payment.confirmed",
                    aggregate_id=order.id,
                    payload={
                        "orderId": order.id,
                        "reservationId": reservation.id,
                        "userId": reservation.user_id,
                        "amount": float(Decimal(event.price) * reservation.quantity),
                        "currency": "INR",
                        "tickets": [t.id for t in tickets],
                    },
                )
                body, status = order_payload(order, tickets=tickets), 201

        db.session.add(PaymentIdempotencyRecord(
            key=idempotency_key,
            request_hash=fingerprint,
            response_status=status,
            response_body=json.dumps(body, separators=(",", ":")),
            expires_at=now + timedelta(hours=24),
        ))
        db.session.commit()
        return body, status
    except (PaymentError, IdempotencyConflict):
        db.session.rollback()
        raise
    except IntegrityError:
        db.session.rollback()
        existing = db.session.execute(
            select(PaymentIdempotencyRecord).where(PaymentIdempotencyRecord.key == idempotency_key)
        ).scalar_one_or_none()
        if existing:
            return _stored_response(existing, fingerprint)
        raise
    except Exception:
        db.session.rollback()
        raise
