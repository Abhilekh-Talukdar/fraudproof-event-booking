"""
Transactional outbox — write side.

Call `enqueue_event(...)` from within an existing SQLAlchemy session (before
commit) to atomically record an outbox event alongside the business operation.
The session must still be committed by the caller; this function only adds the
ORM object to the session.
"""

from ..models import OutboxEvent


def enqueue_event(*, event_type: str, aggregate_id: str, payload: dict) -> OutboxEvent:
    """
    Add an OutboxEvent to the current session.

    Must be called before the session is committed. The event is durable only
    after the surrounding transaction commits. If the transaction rolls back the
    event is discarded — which is exactly what we want.

    Args:
        event_type:   Dot-namespaced event name, e.g. "reservation.created".
        aggregate_id: The ID of the primary entity involved (reservation, order, …).
        payload:      JSON-serialisable dict of event data. Keep it small; it
                      is stored in the database and forwarded to handlers.

    Returns:
        The OutboxEvent instance (not yet persisted — caller must commit).
    """
    from .. import db

    event = OutboxEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=payload,
    )
    db.session.add(event)
    return event
