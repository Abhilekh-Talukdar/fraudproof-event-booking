from functools import wraps

from flask import g, jsonify, session

from . import db
from .models import User, UserRole, UserStatus


def serialize_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role.value, "status": user.status.value}


def current_user() -> User | None:
    if hasattr(g, "current_user"):
        return g.current_user
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if not user or user.status != UserStatus.ACTIVE:
        session.pop("user_id", None)
        user = None
    g.current_user = user
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "authentication_required", "message": "Please sign in."}), 401
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles: UserRole):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "authentication_required", "message": "Please sign in."}), 401
            if user.role not in roles:
                return jsonify({"error": "forbidden", "message": "You are not permitted to perform this action."}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator
