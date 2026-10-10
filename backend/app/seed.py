from datetime import datetime, timezone
from decimal import Decimal

import click
from flask import Flask

from . import db
from .models import Event, Inventory, User, UserRole, UserStatus
from werkzeug.security import generate_password_hash


DEMO_EVENTS = (
    ("Tech Innovators Conference", "2027-06-15T09:00:00+00:00", "Bengaluru, Karnataka", "A conference on applied AI, security, and software systems.", "2999.00", 500),
    ("NH7 Weekender Music Festival", "2027-07-20T16:00:00+00:00", "Pune, Maharashtra", "An indie and international music festival.", "2500.00", 2500),
    ("Comic Con India", "2027-08-05T10:00:00+00:00", "Delhi", "A pop-culture convention for comics, games, and film.", "1500.00", 1200),
)


def register_seed_command(app: Flask) -> None:
    @app.cli.command("seed-demo-data")
    def seed_demo_data() -> None:
        """Seed only an empty local database with non-production demo events."""
        if db.session.query(Event.id).first():
            raise click.ClickException("The database already contains events; refusing to seed duplicates.")
        for name, starts_at, location, description, price, capacity in DEMO_EVENTS:
            event = Event(
                name=name,
                starts_at=datetime.fromisoformat(starts_at).astimezone(timezone.utc),
                location=location,
                description=description,
                price=Decimal(price),
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
        demo_password = "fraudproof-demo-password"
        db.session.add_all([
            User(email="attendee@fraudproof.local", password_hash=generate_password_hash(demo_password), role=UserRole.USER, status=UserStatus.ACTIVE),
            User(email="scanner@fraudproof.local", password_hash=generate_password_hash(demo_password), role=UserRole.SCANNER, status=UserStatus.ACTIVE),
        ])
        db.session.commit()
        click.echo(f"Seeded {len(DEMO_EVENTS)} demo events and two local demo accounts.")
