"""Transactional outbox worker with recoverable processing claims.

A worker commits its claim before invoking a handler. Claims have a lease so
another worker can pick up an event if the original process disappears. Delivery
is therefore at-least-once: handlers that perform external side effects must be
idempotent.

The claim token acts as a fencing value. A worker whose lease has been replaced
cannot update the event's final status when its handler eventually returns.
"""

import logging
import traceback
from datetime import timedelta
from typing import Callable
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from .. import db
from ..models import OutboxEvent, OutboxEventStatus, utcnow

logger = logging.getLogger(__name__)

HandlerFn = Callable[[OutboxEvent], None]
_handlers: dict[str, list[HandlerFn]] = {}

MAX_ATTEMPTS = 5
LEASE_TIMEOUT_SECONDS = 300


def register_handler(event_type: str, fn: HandlerFn) -> None:
    """Register a handler for an outbox event type."""
    _handlers.setdefault(event_type, []).append(fn)


def run_worker_cycle(
    batch_size: int = 50,
    lease_timeout_seconds: int = LEASE_TIMEOUT_SECONDS,
) -> int:
    """Claim and process a batch of pending or abandoned outbox events.

    Returns the number of events successfully marked DONE. A PROCESSING row
    with no claim timestamp is treated as a legacy abandoned claim, which lets
    rows created before lease support recover on the first run after migration.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    if lease_timeout_seconds < 1:
        raise ValueError("lease_timeout_seconds must be greater than zero")

    now = utcnow()
    lease_cutoff = now - timedelta(seconds=lease_timeout_seconds)
    stale_claim = or_(
        OutboxEvent.claimed_at.is_(None),
        OutboxEvent.claimed_at <= lease_cutoff,
    )

    # A crashed worker may have consumed the final attempt without recording
    # a handler result. Do not dispatch it again after its lease expires.
    try:
        db.session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxEventStatus.PROCESSING,
                OutboxEvent.attempts >= MAX_ATTEMPTS,
                stale_claim,
            )
            .values(
                status=OutboxEventStatus.FAILED,
                last_error="Processing lease expired after maximum attempts",
                processed_at=now,
                claimed_at=None,
                claim_token=None,
            )
            .execution_options(synchronize_session=False)
        )

        candidates = db.session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.attempts < MAX_ATTEMPTS,
                or_(
                    OutboxEvent.status == OutboxEventStatus.PENDING,
                    and_(
                        OutboxEvent.status == OutboxEventStatus.PROCESSING,
                        stale_claim,
                    ),
                ),
            )
            .order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).scalars().all()

        claims: list[tuple[str, str, int]] = []
        for event in candidates:
            token = str(uuid4())
            event.status = OutboxEventStatus.PROCESSING
            event.attempts += 1
            event.claimed_at = now
            event.claim_token = token
            claims.append((event.id, token, event.attempts))

        # Persist the claim before calling handlers. A crash from this point on
        # is recoverable after the lease expires.
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    done_count = 0
    for event_id, claim_token, attempt_number in claims:
        # Re-read only while this worker still owns the claim. The token is
        # captured locally so a later claim cannot be mistaken for ours.
        event = db.session.execute(
            select(OutboxEvent).where(
                OutboxEvent.id == event_id,
                OutboxEvent.status == OutboxEventStatus.PROCESSING,
                OutboxEvent.claim_token == claim_token,
            )
        ).scalar_one_or_none()
        if event is None:
            continue

        handlers = _handlers.get(event.event_type, [])
        if not handlers:
            result = db.session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == OutboxEventStatus.PROCESSING,
                    OutboxEvent.claim_token == claim_token,
                )
                .values(
                    status=OutboxEventStatus.FAILED,
                    last_error=f"No handler registered for event_type '{event.event_type}'",
                    processed_at=utcnow(),
                    claimed_at=None,
                    claim_token=None,
                )
            )
            db.session.commit()
            if result.rowcount != 1:
                logger.info("outbox: claim was replaced before event id=%s could be failed", event_id)
            continue

        succeeded = True
        error_text = None
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                succeeded = False
                error_text = traceback.format_exc()[:4000]
                logger.error(
                    "outbox: handler %s failed for event id=%s attempt=%d: %s",
                    handler.__name__, event_id, attempt_number, exc,
                )
                # A failed handler may have left the SQLAlchemy session in an
                # error state. The claim was committed earlier, so it survives.
                db.session.rollback()
                break

        finished_at = utcnow()
        if succeeded:
            final_status = OutboxEventStatus.DONE
            processed_at = finished_at
            last_error = None
        elif attempt_number >= MAX_ATTEMPTS:
            final_status = OutboxEventStatus.FAILED
            processed_at = finished_at
            last_error = error_text
        else:
            final_status = OutboxEventStatus.PENDING
            processed_at = None
            last_error = error_text

        result = db.session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == event_id,
                OutboxEvent.status == OutboxEventStatus.PROCESSING,
                OutboxEvent.claim_token == claim_token,
            )
            .values(
                status=final_status,
                last_error=last_error,
                processed_at=processed_at,
                claimed_at=None,
                claim_token=None,
            )
        )
        db.session.commit()

        if result.rowcount != 1:
            logger.warning(
                "outbox: claim lost before finalizing event id=%s; leaving the newer claim untouched",
                event_id,
            )
            continue
        if succeeded:
            done_count += 1
            logger.info("outbox: DONE event_type=%s id=%s", event.event_type, event_id)
        elif final_status == OutboxEventStatus.FAILED:
            logger.error("outbox: FAILED permanently event_type=%s id=%s attempts=%d", event.event_type, event_id, attempt_number)
        else:
            logger.warning("outbox: retry queued event_type=%s id=%s attempts=%d", event.event_type, event_id, attempt_number)

    return done_count
