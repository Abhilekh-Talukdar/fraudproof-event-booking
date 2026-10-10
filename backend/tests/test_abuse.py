"""
Tests for Milestone 5: Abuse Protection

- Rate limiting on auth endpoints (Flask-Limiter, in-memory storage for tests).
- Rule-based abuse detection: a user who creates ≥ 50 reservations within an
  hour is blocked at the API layer BEFORE the service is called.
- Audit log entries are written for key security events.
"""

from datetime import timedelta

from app import db
from app.models import AuditLog, Reservation, ReservationStatus, User, UserRole, UserStatus, utcnow
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(app, email="abuse@example.test", role=UserRole.USER):
    with app.app_context():
        u = User(
            email=email,
            password_hash=generate_password_hash("correct-horse-battery-staple"),
            role=role,
            status=UserStatus.ACTIVE,
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(app, email="abuse@example.test"):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery-staple"})
    assert r.status_code == 200, f"login failed: {r.json}"
    return c


# ---------------------------------------------------------------------------
# Rate limiting — register endpoint (limit: 10/minute)
# ---------------------------------------------------------------------------

def test_register_rate_limit_enforced(app):
    """After 10 registration attempts from the same IP, the 11th must be 429."""
    client = app.test_client()
    for i in range(10):
        resp = client.post(
            "/api/auth/register",
            json={"email": f"ratelimit{i}@example.test", "password": "a-strong-password"},
        )
        # Some will succeed (201) or conflict (409); all below 429 is fine.
        assert resp.status_code != 429, f"Rate limited too early on attempt {i + 1}"

    # 11th attempt — must be rate-limited
    resp = client.post(
        "/api/auth/register",
        json={"email": "ratelimit11@example.test", "password": "a-strong-password"},
    )
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Rate limiting — login endpoint (limit: 20/minute)
# ---------------------------------------------------------------------------

def test_login_rate_limit_enforced(app):
    """After 20 login attempts from the same IP, the 21st must be 429."""
    client = app.test_client()
    for i in range(20):
        client.post(
            "/api/auth/login",
            json={"email": "ghost@example.test", "password": "wrong-password"},
        )

    resp = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.test", "password": "wrong-password"},
    )
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Rule-based abuse detection — >50 reservations in 1 hour
# ---------------------------------------------------------------------------

def test_rule_based_abuse_detection_blocks_after_50_reservations(app, event_factory):
    """
    A user who already has 50+ reservations in the last hour must receive 429
    with code 'abuse_detected' on the next reservation attempt.

    We inject the reservation rows directly (bypassing limits) so the test is
    fast and does not depend on inventory capacity.
    """
    event_id = event_factory(capacity=200)
    uid = _make_user(app)
    client = _login(app)

    now = utcnow()
    with app.app_context():
        for _ in range(50):
            db.session.add(
                Reservation(
                    event_id=event_id,
                    user_id=uid,
                    quantity=1,
                    status=ReservationStatus.HELD,
                    expires_at=now + timedelta(minutes=5),
                    created_at=now - timedelta(minutes=10),
                )
            )
        db.session.commit()

    resp = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "abuse-trigger"},
    )
    assert resp.status_code == 429
    assert resp.json["error"] == "abuse_detected"


# ---------------------------------------------------------------------------
# Audit log — events are persisted on auth actions
# ---------------------------------------------------------------------------

def test_audit_log_written_on_successful_registration(app):
    client = app.test_client()
    client.post(
        "/api/auth/register",
        json={"email": "audited@example.test", "password": "a-strong-password"},
    )
    with app.app_context():
        log = db.session.query(AuditLog).filter_by(action="user_registered").first()
        assert log is not None
        assert log.details["email"] == "audited@example.test"


def test_audit_log_written_on_failed_login(app):
    client = app.test_client()
    client.post(
        "/api/auth/login",
        json={"email": "nobody@example.test", "password": "wrong-password"},
    )
    with app.app_context():
        log = db.session.query(AuditLog).filter_by(action="login_failed").first()
        assert log is not None
        assert log.details["email"] == "nobody@example.test"


def test_audit_log_written_on_successful_login(app):
    _make_user(app, email="loginaudit@example.test")
    client = app.test_client()
    client.post(
        "/api/auth/login",
        json={"email": "loginaudit@example.test", "password": "correct-horse-battery-staple"},
    )
    with app.app_context():
        log = db.session.query(AuditLog).filter_by(action="login_success").first()
        assert log is not None


def test_audit_log_written_on_abuse_block(app, event_factory):
    event_id = event_factory(capacity=200)
    uid = _make_user(app, email="abusedaudit@example.test")
    client = _login(app, email="abusedaudit@example.test")

    now = utcnow()
    with app.app_context():
        for _ in range(50):
            db.session.add(
                Reservation(
                    event_id=event_id,
                    user_id=uid,
                    quantity=1,
                    status=ReservationStatus.HELD,
                    expires_at=now + timedelta(minutes=5),
                    created_at=now - timedelta(minutes=10),
                )
            )
        db.session.commit()

    client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1},
        headers={"Idempotency-Key": "audit-abuse-trigger"},
    )

    with app.app_context():
        log = db.session.query(AuditLog).filter_by(action="abuse_blocked").first()
        assert log is not None
        assert "Too many reservations" in log.details["reason"]
