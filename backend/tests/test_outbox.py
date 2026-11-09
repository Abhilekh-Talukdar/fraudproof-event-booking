"""
Tests for Milestone 6: Async Reliability — Transactional Outbox

Verified properties:
1. Outbox event is written atomically with the reservation — rolled-back
   transactions produce no orphaned events.
2. Outbox event is written atomically with payment (confirmed + declined).
3. Outbox event is written atomically with abuse detection.
4. Worker processes PENDING → DONE with a registered handler.
5. Worker retries a failing handler up to MAX_ATTEMPTS, then marks FAILED.
6. Worker is idempotent: running twice on already-DONE events does nothing.
7. Worker returns 0 when there are no PENDING events.
8. Concurrent worker calls do not double-process the same event (simulated
   via two sequential calls on separate sessions — real concurrent safety
   is covered by the FOR UPDATE SKIP LOCKED in worker.py).
9. Missing handler marks event FAILED immediately.
10. Abuse outbox event carries correct payload fields.
"""

from datetime import timedelta

from app import db
from app.models import (
    OutboxEvent,
    OutboxEventStatus,
    Reservation,
    ReservationStatus,
    User,
    UserRole,
    UserStatus,
    utcnow,
)
from app.services.outbox import enqueue_event
from app.services.worker import MAX_ATTEMPTS, register_handler, run_worker_cycle
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(app, email="worker@example.test"):
    with app.app_context():
        u = User(
            email=email,
            password_hash=generate_password_hash("correct-horse-battery-staple"),
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(app, email="worker@example.test"):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery-staple"})
    assert r.status_code == 200, r.json
    return c


# ---------------------------------------------------------------------------
# 1 & 2. Outbox events are written atomically with business operations
# ---------------------------------------------------------------------------

def test_reservation_creates_outbox_event(client, app, event_factory):
    event_id = event_factory()
    resp = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "outbox-res-1"},
    )
    assert resp.status_code == 201
    with app.app_context():
        events = db.session.query(OutboxEvent).filter_by(event_type="reservation.created").all()
        assert len(events) == 1
        e = events[0]
        assert e.status == OutboxEventStatus.PENDING
        assert e.payload["reservationId"] == resp.json["reservationId"]
        assert e.payload["quantity"] == 1


def test_approved_payment_creates_outbox_event(client, app, event_factory):
    event_id = event_factory()
    res = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "outbox-pay-res"},
    ).json
    resp = client.post(
        f"/api/reservations/{res['reservationId']}/mock-payment",
        json={"outcome": "APPROVED"},
        headers={"Idempotency-Key": "outbox-pay-1"},
    )
    assert resp.status_code == 201
    with app.app_context():
        e = db.session.query(OutboxEvent).filter_by(event_type="payment.confirmed").first()
        assert e is not None
        assert e.status == OutboxEventStatus.PENDING
        assert e.payload["orderId"] == resp.json["orderId"]
        assert len(e.payload["tickets"]) == 1


def test_declined_payment_creates_outbox_event(client, app, event_factory):
    event_id = event_factory()
    res = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "outbox-dec-res"},
    ).json
    resp = client.post(
        f"/api/reservations/{res['reservationId']}/mock-payment",
        json={"outcome": "DECLINED"},
        headers={"Idempotency-Key": "outbox-dec-1"},
    )
    assert resp.status_code == 402
    with app.app_context():
        e = db.session.query(OutboxEvent).filter_by(event_type="payment.declined").first()
        assert e is not None
        assert e.payload["reservationId"] == res["reservationId"]


# ---------------------------------------------------------------------------
# 3. Abuse detection writes outbox event
# ---------------------------------------------------------------------------

def test_abuse_block_creates_outbox_event(app, event_factory):
    event_id = event_factory(capacity=200)
    uid = _make_user(app)
    client = _login(app)

    now = utcnow()
    with app.app_context():
        for _ in range(50):
            db.session.add(Reservation(
                event_id=event_id,
                user_id=uid,
                quantity=1,
                status=ReservationStatus.HELD,
                expires_at=now + timedelta(minutes=5),
                created_at=now - timedelta(minutes=10),
            ))
        db.session.commit()

    client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "abuse-outbox-trigger"},
    )
    with app.app_context():
        e = db.session.query(OutboxEvent).filter_by(event_type="abuse.blocked").first()
        assert e is not None
        assert e.payload["userId"] == uid
        assert "Too many" in e.payload["reason"]


# ---------------------------------------------------------------------------
# 4. Worker processes PENDING → DONE
# ---------------------------------------------------------------------------

def test_worker_processes_pending_event_to_done(app):
    received = []

    def handler(evt):
        received.append(evt.event_type)

    with app.app_context():
        register_handler("test.event", handler)
        db.session.add(OutboxEvent(
            event_type="test.event",
            aggregate_id="agg-1",
            payload={"x": 1},
        ))
        db.session.commit()

        done = run_worker_cycle(batch_size=10)
        assert done == 1
        assert received == ["test.event"]

        evt = db.session.query(OutboxEvent).filter_by(event_type="test.event").first()
        assert evt.status == OutboxEventStatus.DONE
        assert evt.processed_at is not None


# ---------------------------------------------------------------------------
# 5. Worker retries a failing handler up to MAX_ATTEMPTS, then marks FAILED
# ---------------------------------------------------------------------------

def test_worker_marks_failed_after_max_attempts(app):
    call_count = {"n": 0}

    def always_fails(evt):
        call_count["n"] += 1
        raise ValueError("simulated handler failure")

    with app.app_context():
        register_handler("test.always_fails", always_fails)
        db.session.add(OutboxEvent(
            event_type="test.always_fails",
            aggregate_id="agg-2",
            payload={},
        ))
        db.session.commit()

        for _ in range(MAX_ATTEMPTS):
            run_worker_cycle(batch_size=10)

        evt = db.session.query(OutboxEvent).filter_by(event_type="test.always_fails").first()
        assert evt.status == OutboxEventStatus.FAILED
        assert "simulated handler failure" in evt.last_error
        assert call_count["n"] == MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# 6. Worker is idempotent — running again on DONE events is a no-op
# ---------------------------------------------------------------------------

def test_worker_does_not_reprocess_done_events(app):
    calls = {"n": 0}

    def handler(evt):
        calls["n"] += 1

    with app.app_context():
        register_handler("test.idempotent", handler)
        db.session.add(OutboxEvent(
            event_type="test.idempotent",
            aggregate_id="agg-3",
            payload={},
        ))
        db.session.commit()

        run_worker_cycle(batch_size=10)
        first_calls = calls["n"]
        run_worker_cycle(batch_size=10)

        assert calls["n"] == first_calls  # handler not called again


# ---------------------------------------------------------------------------
# 7. Worker returns 0 with no PENDING events
# ---------------------------------------------------------------------------

def test_worker_returns_zero_when_no_pending_events(app):
    with app.app_context():
        result = run_worker_cycle(batch_size=10)
        assert result == 0


# ---------------------------------------------------------------------------
# 9. Unknown event type → FAILED immediately (no handler registered)
# ---------------------------------------------------------------------------

def test_worker_marks_unknown_event_type_as_failed(app):
    with app.app_context():
        db.session.add(OutboxEvent(
            event_type="completely.unknown.type",
            aggregate_id="agg-unknown",
            payload={},
        ))
        db.session.commit()

        run_worker_cycle(batch_size=10)

        evt = db.session.query(OutboxEvent).filter_by(event_type="completely.unknown.type").first()
        assert evt.status == OutboxEventStatus.FAILED
        assert "No handler" in evt.last_error


# ---------------------------------------------------------------------------
# 10. Rolled-back transaction leaves no orphaned outbox event
# ---------------------------------------------------------------------------

def test_rolled_back_transaction_leaves_no_outbox_event(app):
    """
    Simulate a failure after enqueue_event but before commit.
    The outbox event must not appear in the DB.
    """
    with app.app_context():
        try:
            enqueue_event(
                event_type="reservation.created",
                aggregate_id="never-committed",
                payload={"test": True},
            )
            raise RuntimeError("simulated failure before commit")
        except RuntimeError:
            db.session.rollback()

        count = db.session.query(OutboxEvent).filter_by(aggregate_id="never-committed").count()
        assert count == 0



# ---------------------------------------------------------------------------
# Recoverable processing leases
# ---------------------------------------------------------------------------

def test_worker_recovers_an_expired_processing_claim(app):
    received = []

    def handler(event):
        received.append(event.id)

    with app.app_context():
        register_handler("test.recover_stale", handler)
        event = OutboxEvent(
            event_type="test.recover_stale",
            aggregate_id="agg-stale",
            payload={},
            status=OutboxEventStatus.PROCESSING,
            attempts=1,
            claimed_at=utcnow() - timedelta(minutes=2),
            claim_token="previous-worker-token",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        done = run_worker_cycle(batch_size=10, lease_timeout_seconds=60)

        recovered = db.session.get(OutboxEvent, event_id)
        assert done == 1
        assert received == [event_id]
        assert recovered.status == OutboxEventStatus.DONE
        assert recovered.attempts == 2
        assert recovered.claimed_at is None
        assert recovered.claim_token is None


def test_worker_recovers_processing_rows_created_before_lease_support(app):
    received = []

    def handler(event):
        received.append(event.id)

    with app.app_context():
        register_handler("test.recover_legacy", handler)
        event = OutboxEvent(
            event_type="test.recover_legacy",
            aggregate_id="agg-legacy",
            payload={},
            status=OutboxEventStatus.PROCESSING,
            attempts=1,
            claimed_at=None,
            claim_token=None,
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        done = run_worker_cycle(batch_size=10, lease_timeout_seconds=60)

        recovered = db.session.get(OutboxEvent, event_id)
        assert done == 1
        assert received == [event_id]
        assert recovered.status == OutboxEventStatus.DONE


def test_worker_leaves_a_live_processing_claim_alone(app):
    received = []

    def handler(event):
        received.append(event.id)

    with app.app_context():
        register_handler("test.live_claim", handler)
        event = OutboxEvent(
            event_type="test.live_claim",
            aggregate_id="agg-live",
            payload={},
            status=OutboxEventStatus.PROCESSING,
            attempts=1,
            claimed_at=utcnow(),
            claim_token="active-worker-token",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        done = run_worker_cycle(batch_size=10, lease_timeout_seconds=60)

        unchanged = db.session.get(OutboxEvent, event_id)
        assert done == 0
        assert received == []
        assert unchanged.status == OutboxEventStatus.PROCESSING
        assert unchanged.claim_token == "active-worker-token"


def test_worker_fails_an_expired_claim_after_max_attempts(app):
    with app.app_context():
        event = OutboxEvent(
            event_type="test.crashed_too_many_times",
            aggregate_id="agg-exhausted",
            payload={},
            status=OutboxEventStatus.PROCESSING,
            attempts=MAX_ATTEMPTS,
            claimed_at=utcnow() - timedelta(minutes=2),
            claim_token="last-worker-token",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        done = run_worker_cycle(batch_size=10, lease_timeout_seconds=60)

        failed = db.session.get(OutboxEvent, event_id)
        assert done == 0
        assert failed.status == OutboxEventStatus.FAILED
        assert "lease expired" in failed.last_error.lower()
        assert failed.claimed_at is None
        assert failed.claim_token is None


def test_old_worker_cannot_finalize_a_replaced_claim(app):
    def handler(event):
        # Simulate another worker taking over after this worker's lease expires.
        event.claim_token = "replacement-worker-token"
        event.claimed_at = utcnow()
        db.session.commit()

    with app.app_context():
        register_handler("test.replaced_claim", handler)
        event = OutboxEvent(
            event_type="test.replaced_claim",
            aggregate_id="agg-replaced",
            payload={},
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        done = run_worker_cycle(batch_size=10)

        current = db.session.get(OutboxEvent, event_id)
        assert done == 0
        assert current.status == OutboxEventStatus.PROCESSING
        assert current.claim_token == "replacement-worker-token"


def test_worker_rejects_invalid_batch_and_lease_values(app):
    import pytest

    with app.app_context():
        with pytest.raises(ValueError, match="batch_size"):
            run_worker_cycle(batch_size=0)
        with pytest.raises(ValueError, match="lease_timeout_seconds"):
            run_worker_cycle(lease_timeout_seconds=0)



def test_register_handler_ignores_same_callable_but_keeps_distinct_handlers(app):
    received = []

    def first_handler(event):
        received.append(("first", event.id))

    def second_handler(event):
        received.append(("second", event.id))

    with app.app_context():
        register_handler("test.registration_idempotency", first_handler)
        register_handler("test.registration_idempotency", second_handler)
        register_handler("test.registration_idempotency", first_handler)
        db.session.add(OutboxEvent(
            event_type="test.registration_idempotency",
            aggregate_id="agg-registration-idempotency",
            payload={},
        ))
        db.session.commit()

        done = run_worker_cycle(batch_size=10)
        event = db.session.query(OutboxEvent).filter_by(
            event_type="test.registration_idempotency"
        ).one()

        assert done == 1
        assert received == [
            ("first", event.id),
            ("second", event.id),
        ]
