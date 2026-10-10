import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app import create_app, db
from app.models import Event, Inventory, User, UserRole, UserStatus
from werkzeug.security import generate_password_hash


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = os.environ.get("FRAUDPROOF_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:4200"]
    RESERVATION_TTL_SECONDS = 300
    MAX_RESERVATION_QUANTITY = 4
    TICKET_SIGNING_SECRET = "test-ticket-signing-secret"
    TICKET_VALIDITY_AFTER_EVENT_SECONDS = 86400
    RATELIMIT_STORAGE_URI = "memory://"


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    with app.app_context():
        user = User(
            email="admin@example.test",
            password_hash=generate_password_hash("correct-horse-battery-staple"),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.session.add(user)
        db.session.commit()
    test_client = app.test_client()
    response = test_client.post("/api/auth/login", json={"email": "admin@example.test", "password": "correct-horse-battery-staple"})
    assert response.status_code == 200
    return test_client


@pytest.fixture()
def event_factory(app):
    def create(capacity=10):
        with app.app_context():
            event = Event(
                name="Scarce Tickets",
                starts_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
                location="Test Venue",
                description="Test event",
                price=Decimal("100.00"),
            )
            db.session.add(event)
            db.session.flush()
            db.session.add(Inventory(
                event_id=event.id,
                total_quantity=capacity,
                available_quantity=capacity,
                reserved_quantity=0,
                sold_quantity=0,
            ))
            db.session.commit()
            return event.id
    return create
