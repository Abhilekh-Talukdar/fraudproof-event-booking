# 004 — Session authentication and role-based access

## Decision

Use Flask's signed, HTTP-only server session cookie for the modular-monolith
portfolio deployment. The cookie holds only a user ID; each protected request
loads the active user from PostgreSQL. Passwords are stored only as Werkzeug
password hashes.

Roles are `USER`, `ORGANIZER`, `SCANNER`, and `ADMIN`. Registration always
creates `USER`, regardless of client-supplied fields. Ticket consumption is
limited to scanner, organizer, or admin roles; checkout additionally verifies
reservation ownership.

## Consequences

This avoids putting authorization claims into a long-lived client token while
the application is one deployable service. A future OIDC provider can replace
the login adapter without weakening route-level authorization checks.
