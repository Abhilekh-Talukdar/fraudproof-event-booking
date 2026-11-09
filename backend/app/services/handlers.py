"""
Outbox event handlers.

Each handler receives a fully-loaded OutboxEvent and does the side-effectful
work (email, Pub/Sub publish, fraud-signal recording, etc.).

In this iteration handlers are in-process stubs that log structured messages.
The interface is intentionally thin so any handler can be replaced with a real
external call (GCP Pub/Sub, SendGrid, etc.) without touching the business
services or the worker.

Registration is done at app startup via worker.register_handler().
The registry ignores repeat registration of the same callable, so app-factory
reinitialization cannot add duplicate handler executions.
"""

import logging

from .worker import register_handler
from ..models import OutboxEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# reservation.created
# ---------------------------------------------------------------------------

def _handle_reservation_created(event: OutboxEvent) -> None:
    p = event.payload
    logger.info(
        "[outbox] reservation.created reservation_id=%s event_id=%s user_id=%s quantity=%s",
        p.get("reservationId"), p.get("eventId"), p.get("userId"), p.get("quantity"),
    )
    # TODO(milestone-6): send "your reservation is confirmed — complete payment" email.
    # TODO(milestone-6): publish to GCP Pub/Sub topic "reservation-events".


# ---------------------------------------------------------------------------
# payment.confirmed
# ---------------------------------------------------------------------------

def _handle_payment_confirmed(event: OutboxEvent) -> None:
    p = event.payload
    logger.info(
        "[outbox] payment.confirmed order_id=%s reservation_id=%s amount=%s currency=%s tickets=%s",
        p.get("orderId"), p.get("reservationId"),
        p.get("amount"), p.get("currency"),
        len(p.get("tickets", [])),
    )
    # TODO(milestone-6): send ticket PDF / confirmation email.
    # TODO(milestone-6): publish to "payment-events" topic.


# ---------------------------------------------------------------------------
# payment.declined
# ---------------------------------------------------------------------------

def _handle_payment_declined(event: OutboxEvent) -> None:
    p = event.payload
    logger.info(
        "[outbox] payment.declined order_id=%s reservation_id=%s",
        p.get("orderId"), p.get("reservationId"),
    )
    # TODO(milestone-6): send "payment declined" notification email.
    # TODO(milestone-6): publish to "payment-events" topic.


# ---------------------------------------------------------------------------
# abuse.blocked
# ---------------------------------------------------------------------------

def _handle_abuse_blocked(event: OutboxEvent) -> None:
    p = event.payload
    logger.warning(
        "[outbox] abuse.blocked user_id=%s ip=%s reason=%s",
        p.get("userId"), p.get("ipAddress"), p.get("reason"),
    )
    # TODO(milestone-9): feed into fraud scoring service.
    # TODO(milestone-6): publish to "abuse-events" topic for downstream alerting.


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def register_all_handlers() -> None:
    """Register all handlers. Call once during create_app()."""
    register_handler("reservation.created", _handle_reservation_created)
    register_handler("payment.confirmed", _handle_payment_confirmed)
    register_handler("payment.declined", _handle_payment_declined)
    register_handler("abuse.blocked", _handle_abuse_blocked)
    logger.debug("[outbox] all handlers registered")
