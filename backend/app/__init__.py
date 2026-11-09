from flask import Flask, jsonify, cli
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import click

from .config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401
    from .api import api
    from .seed import register_seed_command
    from .limiter import limiter
    from .services.handlers import register_all_handlers

    # RATELIMIT_STORAGE_URI can be pre-set by test configs (memory://).
    # Only default to Redis when not already configured.
    app.config.setdefault("RATELIMIT_STORAGE_URI", app.config.get("REDIS_URL", "redis://localhost:6379/0"))
    app.config.setdefault("RATELIMIT_STRATEGY", "fixed-window")
    limiter.init_app(app)

    # Register outbox handlers once at startup.
    register_all_handlers()

    app.register_blueprint(api, url_prefix="/api")
    register_seed_command(app)

    # ---------------------------------------------------------------------------
    # Flask CLI: flask worker run [--batch-size N]
    # ---------------------------------------------------------------------------
    @app.cli.group()
    def worker():
        """Outbox worker commands."""

    @worker.command("run")
    @click.option("--batch-size", default=50, show_default=True, help="Events per cycle.")
    @click.option("--cycles", default=1, show_default=True, help="Number of cycles to run (0 = infinite).")
    def worker_run(batch_size: int, cycles: int):
        """Process pending outbox events."""
        from .services.worker import run_worker_cycle
        import time

        cycle = 0
        while True:
            processed = run_worker_cycle(batch_size=batch_size)
            click.echo(f"Cycle {cycle + 1}: processed {processed} events.")
            cycle += 1
            if cycles > 0 and cycle >= cycles:
                break
            time.sleep(1)

    # ---------------------------------------------------------------------------
    # Flask CLI: flask reservations expire [--batch-size N]
    # ---------------------------------------------------------------------------
    @app.cli.group()
    def reservations():
        """Reservation maintenance commands."""

    @reservations.command("expire")
    @click.option(
        "--batch-size",
        default=1000,
        type=click.IntRange(min=1),
        show_default=True,
        help="Maximum expired holds to release in this invocation.",
    )
    def reservations_expire(batch_size: int):
        """Release one bounded batch of expired reservation holds."""
        from .services.reservations import release_expired_reservations

        try:
            released = release_expired_reservations(batch_size=batch_size)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        click.echo(f"Released {released} expired reservation(s).")

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    return app
