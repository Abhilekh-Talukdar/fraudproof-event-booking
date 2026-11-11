from datetime import timedelta
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .auth import current_user, login_required, roles_required, serialize_user
from .limiter import limiter
from .models import AuditLog, Event, Inventory, User, UserRole, UserStatus, Reservation, utcnow
from .services.payments import PaymentError, confirm_mock_payment
from .services.reservations import ReservationError, create_reservation
from .services.tickets import TicketError, verify_and_consume
from .services.outbox import enqueue_event

api = Blueprint("api", __name__)


def _json_object() -> dict:
    """Return a JSON object body, treating malformed or non-object JSON as empty."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@api.post("/auth/register")
@limiter.limit("10 per minute")
def register():
    payload = _json_object()
    email = payload.get("email", "").strip().lower() if isinstance(payload.get("email"), str) else ""
    password = payload.get("password")
    if not email or "@" not in email or len(email) > 254:
        return jsonify({"error": "A valid email is required."}), 400
    if not isinstance(password, str) or len(password) < 12:
        return jsonify({"error": "Password must be at least 12 characters."}), 400
    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists."}), 409
    user = User(id=str(uuid4()), email=email, password_hash=generate_password_hash(password), role=UserRole.USER, status=UserStatus.ACTIVE)
    db.session.add(user)
    
    # Audit log
    db.session.add(AuditLog(action="user_registered", user_id=user.id, ip_address=request.remote_addr, details={"email": email}))
    
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    g.pop("current_user", None)
    return jsonify({"user": serialize_user(user)}), 201


@api.post("/auth/login")
@limiter.limit("20 per minute")
def login():
    payload = _json_object()
    email = payload.get("email", "").strip().lower() if isinstance(payload.get("email"), str) else ""
    password = payload.get("password")
    user = db.session.query(User).filter_by(email=email).one_or_none() if email else None
    if not user or not isinstance(password, str) or not check_password_hash(user.password_hash, password) or user.status != UserStatus.ACTIVE:
        db.session.add(AuditLog(action="login_failed", ip_address=request.remote_addr, details={"email": email}))
        db.session.commit()
        return jsonify({"error": "invalid_credentials", "message": "Invalid email or password."}), 401
    
    db.session.add(AuditLog(action="login_success", user_id=user.id, ip_address=request.remote_addr))
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    g.pop("current_user", None)
    return jsonify({"user": serialize_user(user)})


@api.post("/auth/logout")
def logout():
    session.clear()
    g.pop("current_user", None)
    return "", 204


@api.get("/me")
@login_required
def me():
    return jsonify({"user": serialize_user(current_user())})


def serialize_event(event: Event) -> dict:
    inventory = db.session.get(Inventory, event.id)
    return {
        "id": event.id,
        "name": event.name,
        "date": event.starts_at.date().isoformat(),
        "startsAt": event.starts_at.isoformat(),
        "location": event.location,
        "description": event.description,
        "price": float(event.price),
        "availability": inventory.available_quantity if inventory else 0,
    }


@api.get("/events")
def get_events():
    events = db.session.query(Event).filter_by(status="PUBLISHED").order_by(Event.starts_at.asc()).all()
    return jsonify([serialize_event(event) for event in events])


@api.get("/events/<int:event_id>")
def get_event(event_id: int):
    event = db.session.get(Event, event_id)
    if not event or event.status != "PUBLISHED":
        return jsonify({"error": "Event not found"}), 404
    return jsonify(serialize_event(event))


@api.post("/reservations")
@login_required
@limiter.limit("20 per minute")
def reserve_tickets():
    payload = _json_object()
    event_id = payload.get("eventId")
    quantity = payload.get("quantity")
    key = request.headers.get("Idempotency-Key")
    if not isinstance(event_id, int) or not isinstance(quantity, int):
        return jsonify({"error": "eventId and quantity must be integers."}), 400
    if not 1 <= quantity <= current_app.config["MAX_RESERVATION_QUANTITY"]:
        return jsonify({"error": "quantity is outside the allowed range."}), 400
    attendee_names = payload.get("attendeeNames")
    if attendee_names is not None and (
        not isinstance(attendee_names, list)
        or len(attendee_names) != quantity
        or any(not isinstance(name, str) or not name.strip() for name in attendee_names)
    ):
        return jsonify({"error": "attendeeNames must contain one non-empty name per ticket."}), 400
    if not key or len(key) > 255:
        return jsonify({"error": "A valid Idempotency-Key header is required."}), 400

    # Rule-based abuse detection
    user = current_user()
    recent_reservations = db.session.query(Reservation).filter(
        Reservation.user_id == user.id,
        Reservation.created_at >= utcnow() - timedelta(hours=1)
    ).count()

    if recent_reservations >= 50:
        db.session.add(AuditLog(
            action="abuse_blocked",
            user_id=user.id,
            ip_address=request.remote_addr,
            details={"reason": "Too many reservations in 1 hour"}
        ))
        enqueue_event(
            event_type="abuse.blocked",
            aggregate_id=user.id,
            payload={
                "userId": user.id,
                "ipAddress": request.remote_addr,
                "reason": "Too many reservations in 1 hour",
                "recentCount": recent_reservations,
            },
        )
        db.session.commit()
        return jsonify({"error": "abuse_detected", "message": "Too many reservations recently. Please try again later."}), 429

    try:
        body, status = create_reservation(
            event_id=event_id,
            quantity=quantity,
            idempotency_key=key,
            ttl_seconds=current_app.config["RESERVATION_TTL_SECONDS"],
            attendee_names=[name.strip() for name in attendee_names] if attendee_names else None,
            user_id=current_user().id,
        )
        return jsonify(body), status
    except ReservationError as error:
        return jsonify({"error": error.code, "message": str(error)}), error.status_code


@api.post("/reservations/<string:reservation_id>/mock-payment")
@login_required
def complete_mock_payment(reservation_id: str):
    payload = _json_object()
    outcome = payload.get("outcome", "APPROVED")
    key = request.headers.get("Idempotency-Key")
    if outcome not in {"APPROVED", "DECLINED"}:
        return jsonify({"error": "outcome must be APPROVED or DECLINED."}), 400
    if not key or len(key) > 255:
        return jsonify({"error": "A valid Idempotency-Key header is required."}), 400
    try:
        body, status = confirm_mock_payment(
            reservation_id=reservation_id,
            outcome=outcome,
            idempotency_key=key,
            user_id=current_user().id,
        )
        return jsonify(body), status
    except (PaymentError, ReservationError) as error:
        return jsonify({"error": error.code, "message": str(error)}), error.status_code


@api.post("/tickets/verify")
@roles_required(UserRole.SCANNER, UserRole.ORGANIZER, UserRole.ADMIN)
def verify_ticket():
    payload = _json_object()
    token = payload.get("token")
    expected_event_id = payload.get("expectedEventId")
    if not isinstance(token, str) or not token:
        return jsonify({"accepted": False, "error": "A ticket token is required."}), 400
    if expected_event_id is not None and not isinstance(expected_event_id, int):
        return jsonify({"accepted": False, "error": "expectedEventId must be an integer."}), 400
    try:
        return jsonify(verify_and_consume(token=token, expected_event_id=expected_event_id))
    except TicketError as error:
        return jsonify({"accepted": False, "error": error.code, "message": str(error)}), error.status_code


@api.post("/bookings")
@login_required
def compatibility_booking():
    """Temporary bridge for the existing form; mock payment follows next."""
    payload = _json_object()
    tickets = payload.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        return jsonify({"success": False, "message": "A non-empty tickets array is required."}), 400
    event_id = payload.get("eventId")
    if not isinstance(event_id, int):
        return jsonify({"success": False, "message": "eventId must be an integer."}), 400
    if len(tickets) > current_app.config["MAX_RESERVATION_QUANTITY"]:
        return jsonify({"success": False, "message": "Too many tickets requested."}), 400
    if any(not isinstance(ticket, dict) or not isinstance(ticket.get("name"), str) or not ticket["name"].strip() for ticket in tickets):
        return jsonify({"success": False, "message": "Every ticket requires a holder name."}), 400
    key = request.headers.get("Idempotency-Key") or str(uuid4())
    try:
        reservation, status = create_reservation(
            event_id=event_id,
            quantity=len(tickets),
            idempotency_key=key,
            ttl_seconds=current_app.config["RESERVATION_TTL_SECONDS"],
            attendee_names=[ticket["name"].strip() for ticket in tickets],
            user_id=current_user().id,
        )
        return jsonify({
            "success": True,
            "message": "Tickets are reserved. Complete mock payment before the hold expires.",
            "reservation": reservation,
        }), status
    except ReservationError as error:
        return jsonify({"success": False, "message": str(error), "error": error.code}), error.status_code
