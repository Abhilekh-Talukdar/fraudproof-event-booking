from sqlalchemy import delete, select

from .. import db
from ..models import IdempotencyRecord, PaymentIdempotencyRecord, utcnow


def get_active_idempotency_record(record_model, key: str, *, now=None):
    """Return an unexpired key record and remove an expired row for key reuse."""
    now = now or utcnow()
    active = db.session.execute(
        select(record_model).where(
            record_model.key == key,
            record_model.expires_at > now,
        )
    ).scalar_one_or_none()
    if active is not None:
        return active

    db.session.execute(
        delete(record_model).where(
            record_model.key == key,
            record_model.expires_at <= now,
        )
    )
    return None


def _purge_expired(model, *, now, batch_size: int) -> int:
    records = db.session.execute(
        select(model)
        .where(model.expires_at <= now)
        .order_by(model.expires_at.asc(), model.id.asc())
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    ).scalars().all()

    for record in records:
        db.session.delete(record)
    return len(records)


def purge_expired_idempotency_records(*, batch_size: int = 1000) -> dict[str, int]:
    """Delete at most batch_size expired rows from each idempotency table.

    The caller owns the transaction and must commit or roll it back. Row locks
    with SKIP LOCKED let multiple scheduled cleanup processes share the work.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    now = utcnow()
    return {
        "reservations": _purge_expired(IdempotencyRecord, now=now, batch_size=batch_size),
        "payments": _purge_expired(PaymentIdempotencyRecord, now=now, batch_size=batch_size),
    }
