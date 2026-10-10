"""
Transactional outbox — worker (read/process side).

Architecture
------------
* The worker claims a batch of PENDING events by marking them PROCESSING inside
  a FOR UPDATE SKIP LOCKED transaction. This prevents two worker instances from
  picking the same event, making it safe to run multiple workers concurrently.
* Each event is dispatched to a registered handler by event_type.
* On success the event is marked DONE.
* On failure the attempt counter is incremented and last_error is recorded.
  After MAX_ATTEMPTS the event is permanently marked FAILED.
* Handlers are registered via the module-level registry; adding a new handler
  is one line of code. The interface is thin so it can be replaced by a real
  message broker (e.g. GCP Pub/Sub) without changing the business services.

Usage (Flask CLI / APScheduler / Cloud Scheduler)
-------------------------------------------------
    with app.app_context():
        processed = run_worker_cycle(batch_size=50)
"""

import logging
import traceback
from typing import Callable

from sqlalchemy import select, update

from .. import db
from ..models import OutboxEvent, OutboxEventStatus, utcnow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

HandlerFn = Callable[[OutboxEvent], None]
_handlers: dict[str, list[HandlerFn]] = {}

MAX_ATTEMPTS = 5


def register_handler(event_type: str, fn: HandlerFn) -> None:
    """Register a handler function for an event type.

    Multiple handlers per event type are allowed; all are called in order.
    This function is idempotent — registering the same function twice is a
    no-op only if the caller avoids duplicates (module-level registration
    naturally prevents this).
    """
    _handlers.setdefault(event_type, []).append(fn)


# ---------------------------------------------------------------------------
# Worker cycle
# ---------------------------------------------------------------------------

def run_worker_cycle(batch_size: int = 50) -> int:
    """
    Claim and process up to *batch_size* PENDING outbox events.

    Returns the number of events successfully processed (marked DONE).
    This function is safe to call from multiple concurrent workers thanks to
    FOR UPDATE SKIP LOCKED.
    """
    now = utcnow()

    # Claim batch atomically
    pending_rows = db.session.execute(
        select(OutboxEvent)
        .where(OutboxEvent.status == OutboxEventStatus.PENDING)
        .order_by(OutboxEvent.created_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).scalars().all()

    if not pending_rows:
        return 0

    # Mark all as PROCESSING in one UPDATE
    ids = [e.id for e in pending_rows]
    db.session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id.in_(ids))
        .values(status=OutboxEventStatus.PROCESSING, attempts=OutboxEvent.attempts + 1)
    )
    db.session.commit()

    done_count = 0
    for event in pending_rows:
        # Re-fetch with current attempt count
        event = db.session.get(OutboxEvent, event.id)
        handlers = _handlers.get(event.event_type, [])

        if not handlers:
            logger.warning("outbox: no handler for event_type=%s id=%s", event.event_type, event.id)
            # Treat missing handler as permanent failure — no retry loop needed.
            event.status = OutboxEventStatus.FAILED
            event.last_error = f"No handler registered for event_type '{event.event_type}'"
            event.processed_at = utcnow()
            db.session.commit()
            continue

        success = True
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                success = False
                error_text = traceback.format_exc()
                logger.error(
                    "outbox: handler %s failed for event id=%s attempt=%d: %s",
                    handler.__name__, event.id, event.attempts, exc,
                )
                event.last_error = error_text[:4000]  # cap to column size
                break  # stop processing remaining handlers for this event

        now = utcnow()
        if success:
            event.status = OutboxEventStatus.DONE
            event.processed_at = now
            done_count += 1
            logger.info("outbox: DONE event_type=%s id=%s", event.event_type, event.id)
        elif event.attempts >= MAX_ATTEMPTS:
            event.status = OutboxEventStatus.FAILED
            event.processed_at = now
            logger.error(
                "outbox: FAILED permanently event_type=%s id=%s attempts=%d",
                event.event_type, event.id, event.attempts,
            )
        else:
            # Revert to PENDING so the next cycle retries
            event.status = OutboxEventStatus.PENDING
            logger.warning(
                "outbox: retry queued event_type=%s id=%s attempts=%d",
                event.event_type, event.id, event.attempts,
            )

        db.session.commit()

    return done_count
