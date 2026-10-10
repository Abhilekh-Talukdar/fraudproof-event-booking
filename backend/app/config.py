import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://fraudproof:fraudproof@localhost:5432/fraudproof"
    )
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:4200").split(",")
    RESERVATION_TTL_SECONDS = int(os.environ.get("RESERVATION_TTL_SECONDS", "300"))
    MAX_RESERVATION_QUANTITY = int(os.environ.get("MAX_RESERVATION_QUANTITY", "4"))
    # Development default only. Production must inject this through Secret Manager.
    TICKET_SIGNING_SECRET = os.environ.get("TICKET_SIGNING_SECRET", "development-ticket-signing-secret-change-me")
    TICKET_VALIDITY_AFTER_EVENT_SECONDS = int(os.environ.get("TICKET_VALIDITY_AFTER_EVENT_SECONDS", "86400"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
