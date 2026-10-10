# FraudProof Event Booking — FAANG-Level Portfolio Upgrade Plan

> **Project goal:** Evolve the existing event-booking application into a production-oriented, fraud-resistant, highly concurrent ticketing platform that demonstrates distributed systems, backend correctness, security, observability, testing, cloud infrastructure, and measurable performance.
>
> **Target positioning:** A small-scale Ticketmaster-style system where the hard engineering problem is not simply booking a ticket, but maintaining **correctness, security, and reliability under concurrency, retries, failures, and malicious traffic**.

---

## 0. How to use this document

This file is intentionally written so that an implementation agent can execute the project in stages.

### Status vocabulary

- `[ ] TODO` — not implemented yet.
- `[x] DONE` — implemented and verified.
- `[~] DESIGN` — architecture or implementation guidance is provided, but exact code depends on the repository after inspection.
- `[?] DECIDE` — an explicit trade-off still needs to be chosen.
- `[P] PROOF` — must be demonstrated with a test, benchmark, trace, screenshot, or other evidence rather than merely documented.

### Important implementation rule

Do not claim performance, security, availability, or correctness properties until they are verified experimentally.

Examples:

- Do not write `10,000 concurrent users supported` until a repeatable load test produces evidence.
- Do not write `zero overselling` until a concurrency test verifies inventory invariants.
- Do not write `fraud-proof` unless concrete attack cases are implemented and blocked.
- Do not write `highly available` unless the actual deployment architecture and failure behavior justify the claim.

### Agent execution principle

Implement the smallest correct version first. Add complexity only when a real engineering problem requires it. Do **not** split everything into microservices merely to make the architecture diagram larger.

---

# 1. Current Repository Snapshot

The repository is currently a relatively small event-booking system. The public repository contains `backend`, `public`, and `src`, has 8 commits, and uses Angular SSR with a Python/Flask backend and SQLite. citeturn942151view0turn942151view1

Current documented features:

- Browse upcoming events.
- View event details.
- Book 1–4 tickets.
- Collect name and date of birth for each ticket.
- Store booking information in the backend database.
- REST communication between Angular and Flask.
- Deployment documentation involving Gunicorn, Nginx, Systemd, Angular SSR, Linux, and GCP. citeturn942151view1

The frontend is Angular 19 with Angular SSR; the repository's `package.json` includes Angular 19 packages and `@angular/ssr` 19.0.6. citeturn493347view0

### Current architecture

```text
Browser
   |
   v
Angular SSR / Node
   |
   | REST
   v
Flask API
   |
   +---- Event data ----> SQLite
   |
   +---- Booking data --> SQLite
```

The current README explicitly describes the backend as event-data management plus booking handling, backed by SQLite. citeturn942151view1

### Main limitation

The name `FraudProof` currently promises substantially more than the documented implementation demonstrates. The upgraded system should make fraud prevention and booking correctness real, measurable system properties.

---

# 2. Target Product Definition

## Product name

**FraudProof**

## Product statement

> A fraud-resistant, highly concurrent event-ticketing platform designed to prevent ticket overselling, duplicate bookings, ticket tampering, QR replay, unauthorized access, and abusive booking traffic while remaining observable and resilient under failure.

## Core engineering problems

1. **Concurrent inventory reservation** — prevent overselling when many users race for the last tickets.
2. **Idempotent operations** — retries must not create duplicate bookings, orders, tickets, or payments.
3. **Temporary reservations** — tickets can be held while payment is pending, then released safely on timeout/failure.
4. **Cryptographically signed tickets** — a user cannot modify ticket data without invalidating the ticket.
5. **Single-use verification** — the same ticket cannot be admitted twice.
6. **Ticket transfer/revocation** — ownership changes invalidate the old ticket version.
7. **Fraud detection** — detect bots and abnormal purchasing behavior.
8. **API security** — prevent broken object/function authorization, abuse, and sensitive business-flow exploitation.
9. **Event-driven processing** — decouple notifications, analytics, and fraud processing from the critical booking path.
10. **Observability** — traces, metrics, logs, dashboards, and alerts must show what happened in production.
11. **Load testing** — prove behavior and performance under controlled concurrency.
12. **Failure/chaos testing** — prove the system recovers or degrades safely when dependencies fail.

---

# 3. Target Architecture

The target should remain understandable. Start with a modular monolith or a small number of services, not 10+ microservices.

```text
                                      +----------------------+
                                      |      Angular SSR     |
                                      |       Frontend       |
                                      +----------+-----------+
                                                 |
                                                 v
                                      +----------------------+
                                      | API / Auth Layer      |
                                      +----------+-----------+
                                                 |
                         +-----------------------+----------------------+
                         |                       |                      |
                         v                       v                      v
                +----------------+     +----------------+     +----------------+
                | Event Module   |     | Booking /      |     | Ticket /       |
                |                |     | Inventory      |     | Verification   |
                +----------------+     +-------+--------+     +----------------+
                                               |
                         +---------------------+--------------------+
                         |                     |                    |
                         v                     v                    v
                   +-----------+        +-----------+        +-----------+
                   |PostgreSQL |        |   Redis   |        | Message   |
                   |           |        | Locks /   |        | Broker    |
                   | Source of |        | Rate limit|        | Kafka /   |
                   | truth     |        | TTL/cache |        | Pub/Sub   |
                   +-----------+        +-----------+        +-----+-----+
                                                                |
                                     +--------------------------+------------------+
                                     |                          |                  |
                                     v                          v                  v
                              +-------------+            +-------------+    +-------------+
                              | Notification|            | Fraud       |    | Analytics   |
                              | Worker      |            | Worker      |    | Worker      |
                              +-------------+            +-------------+    +-------------+

                                      Observability across all layers
                                               |
                                      OpenTelemetry / Metrics /
                                      Logs / Traces / Dashboards
```

### Recommended logical components

Keep these boundaries initially:

1. **API/Auth**
2. **Event + Organizer management**
3. **Booking + Inventory + Reservation state machine**
4. **Ticket + Verification**
5. **Fraud/risk processing** as a worker/service once asynchronous events are introduced
6. **Notification/analytics workers** as asynchronous consumers

`Fraud` and `Ticket` may start as modules in the same Flask application. Split them into independently deployable services only when there is a demonstrated reason.

Google Cloud's event-driven architecture guidance emphasizes decoupling producers from consumers and allowing consumers to scale or deploy independently. citeturn172103search0turn172103search6

---

# 4. Technology Direction

## Required / strongly recommended

| Area | Target |
|---|---|
| Frontend | Angular 19+ / TypeScript / SSR |
| Backend | Python + Flask initially |
| Primary DB | PostgreSQL |
| Cache / rate limiting / short-lived state | Redis |
| Messaging | Kafka or Google Cloud Pub/Sub |
| API style | REST + OpenAPI |
| Authentication | OAuth/OIDC or a carefully implemented JWT/session model |
| Ticket security | HMAC or asymmetric digital signatures |
| Observability | OpenTelemetry |
| Metrics | Prometheus or managed metrics |
| Dashboards | Grafana or managed dashboards |
| Load testing | k6 or Locust |
| E2E | Playwright |
| Unit/integration | pytest + Angular tests |
| Containers | Docker |
| CI/CD | GitHub Actions |
| IaC | Terraform |
| Cloud | GCP is a natural fit because the current project already documents GCP deployment |

Cloud SQL for PostgreSQL is a managed PostgreSQL option on GCP and supports production-oriented capabilities such as backups and high availability. citeturn777193search0turn777193search6

## Explicit non-goal

Do **not** add AI/LLM functionality just for portfolio appeal. A deterministic fraud/risk engine, strong concurrency semantics, security testing, observability, and load testing are more important.

An ML model may be added later as an optional risk-scoring layer after the deterministic system works.

---

# 5. Phase 1 — Repository Stabilization and Baseline

## Goal

Understand and stabilize the existing project before introducing architecture changes.

### Tasks

- [ ] Run the current frontend locally.
- [ ] Run the current backend locally.
- [ ] Document current API endpoints.
- [ ] Document current database schema.
- [ ] Confirm current event and booking workflows.
- [ ] Record current application screenshots.
- [ ] Record a baseline latency measurement for important endpoints.
- [ ] Add backend unit-test infrastructure if missing.
- [ ] Improve frontend test coverage where practical.
- [ ] Add linting and formatting.
- [ ] Create a root-level developer setup guide.
- [ ] Add a `docker-compose.yml` for local development.
- [ ] Add a `.env.example`.
- [ ] Ensure secrets are not committed.

### Baseline benchmark

Record at minimum:

```text
GET /events
GET /events/{id}
POST /bookings
```

Capture:

- p50 latency
- p95 latency
- p99 latency
- error rate
- throughput

Do not optimize yet. This is a baseline for comparison.

---

# 6. Phase 2 — Database Migration to PostgreSQL

## Goal

Replace SQLite with PostgreSQL because the upgraded system needs stronger transactional semantics, concurrent writes, constraints, indexes, and explicit locking behavior.

### Tasks

- [ ] Add PostgreSQL locally via Docker Compose.
- [ ] Introduce migrations (Alembic/Flask-Migrate or equivalent).
- [ ] Define schema explicitly.
- [ ] Create seed data.
- [ ] Move event data from SQLite.
- [ ] Move booking data from SQLite.
- [ ] Add database constraints.
- [ ] Add indexes based on actual query paths.
- [ ] Add transaction boundaries.
- [ ] Add integration tests against a real PostgreSQL instance.

### Recommended schema

```text
users
-----
id
email
role
status
created_at
updated_at

organizers
----------
id
user_id
name
created_at

events
------
id
organizer_id
name
venue
starts_at
ends_at
status
capacity
created_at
updated_at

inventory
---------
event_id PK/FK
total_quantity
available_quantity
reserved_quantity
sold_quantity
version
updated_at

reservations
------------
id
user_id
event_id
quantity
status
expires_at
idempotency_key
created_at
updated_at

orders
------
id
reservation_id
user_id
payment_id
status
amount
currency
created_at
updated_at

tickets
-------
id
order_id
event_id
owner_id
version
status
payload_hash
signature
issued_at
expires_at
used_at
created_at
updated_at

ticket_transfers
----------------
id
ticket_id
from_user_id
to_user_id
from_version
to_version
created_at

fraud_events
------------
id
user_id
event_id
ip_hash/device_hash or appropriate privacy-safe identifiers
action
risk_score
reason
created_at

audit_log
---------
id
actor_id
action
resource_type
resource_id
metadata
created_at
```

### Index examples

```sql
CREATE INDEX idx_reservations_event_status
ON reservations(event_id, status);

CREATE INDEX idx_tickets_owner
ON tickets(owner_id);

CREATE INDEX idx_tickets_event_status
ON tickets(event_id, status);

CREATE UNIQUE INDEX idx_reservations_idempotency
ON reservations(idempotency_key);
```

The exact SQL should be adapted after inspecting the actual ORM/query layer.

### Concurrency note

PostgreSQL supports row-level locking with `SELECT ... FOR UPDATE`; locked rows are protected from conflicting modifications until the transaction ends. The implementation agent should use explicit transactions/locking only where required and prove the chosen pattern with concurrent tests. citeturn777193search13

---

# 7. Phase 3 — Authentication and Authorization

## Goal

Introduce explicit identities and roles before building security-sensitive APIs.

### Roles

```text
USER
ORGANIZER
SCANNER
ADMIN
```

### User capabilities

#### USER

- Browse events.
- Create reservations.
- View own bookings.
- View own tickets.
- Transfer eligible tickets.
- Cancel eligible reservations.

#### ORGANIZER

- Create/update events.
- View event inventory.
- View sales.
- View fraud analytics for owned events.
- Manage scanners for owned events.

#### SCANNER

- Verify tickets for assigned events.
- Cannot modify bookings.
- Cannot view unrelated user data.

#### ADMIN

- User management.
- Security investigation.
- Fraud investigation.
- System operations.

### Security requirements

- [ ] Authentication required for all protected endpoints.
- [ ] Explicit authorization at the resource level.
- [ ] Explicit authorization at the function/role level.
- [ ] Server-side validation of all user-controlled fields.
- [ ] Avoid mass assignment.
- [ ] Avoid returning internal fields unnecessarily.
- [ ] Never trust IDs from a client without ownership/permission checks.

OWASP's API Security Top 10 includes Broken Object Level Authorization, Broken Authentication, Broken Object Property Level Authorization, Unrestricted Resource Consumption, Broken Function Level Authorization, and abuse of sensitive business flows. These categories should directly shape the security test plan. citeturn172103search2turn172103search3turn172103search4

---

# 8. Phase 4 — Inventory and Concurrency Correctness

## This is one of the most important parts of the entire project.

### Goal

Guarantee:

```text
successful_ticket_quantity <= event_capacity
```

under concurrent requests.

### Do not use naive logic

Avoid code equivalent to:

```python
available = get_available_tickets()

if available > requested:
    create_booking()
```

That creates a classic race condition.

### Preferred model

Use an atomic database transaction.

One approach is an atomic conditional update:

```sql
UPDATE inventory
SET available_quantity = available_quantity - :quantity,
    sold_quantity = sold_quantity + :quantity
WHERE event_id = :event_id
  AND available_quantity >= :quantity;
```

Then:

```text
rows_updated == 1 -> success
rows_updated == 0 -> sold out / insufficient inventory
```

Alternative: lock the inventory row using a transaction and `SELECT ... FOR UPDATE`, then update state inside the transaction. Choose one strategy and document why.

### Required reservation state machine

```text
AVAILABLE
    |
    v
HELD ----------------------+
 |                         |
 | payment success         | timeout / failure
 v                         v
CONFIRMED                RELEASED
```

The agent must define all legal transitions and reject invalid transitions.

### Reservation timeout

Recommended initial default:

```text
5 minutes
```

This value is a project parameter, not a universal production rule. Make it configurable.

### Required tests

- [ ] Two concurrent buyers compete for one ticket.
- [ ] 100 concurrent buyers compete for 10 tickets.
- [ ] 1,000 concurrent booking attempts against a low-inventory event.
- [ ] Multiple workers attempt the same reservation.
- [ ] Reservation expires while payment is being processed.
- [ ] Payment succeeds near reservation expiry.
- [ ] Database transaction is rolled back after an injected failure.

### Proof requirement

Create an automated invariant test:

```text
After every load test:

sold_quantity + available_quantity + reserved_quantity == total_quantity
```

and:

```text
sold_quantity <= total_quantity
```

The load test should fail if the invariant is violated.

---

# 9. Phase 5 — Idempotency

## Goal

Retries must not duplicate side effects.

Typical failure:

```text
Client -> POST /booking
            |
            v
       server creates booking
            |
       response is lost
            X
Client retries
            |
            v
       second booking created
```

### API design

Support:

```http
POST /api/reservations
Idempotency-Key: <high-entropy-unique-key>
```

Store:

```text
idempotency_key
request_hash
status
response_body
response_status
created_at
expires_at
```

### Required behavior

Same key + same request:

```text
return the original result
```

Same key + different request:

```text
reject with a deterministic client error
```

The exact status code can be chosen during implementation, but the behavior must be explicit and tested.

Stripe's API documentation describes the core pattern: idempotency keys let clients safely retry operations without accidentally creating the same object or applying an update twice, with the prior result associated with the key. citeturn777193search10turn777193search14

### Idempotency must cover

- [ ] Reservation creation.
- [ ] Payment initiation.
- [ ] Payment webhook processing.
- [ ] Ticket creation.
- [ ] Ticket transfer.
- [ ] Event creation where appropriate.

---

# 10. Phase 6 — Payment Workflow

## Goal

Model payment as a failure-prone external dependency even if real payments are not used.

Use Stripe test mode or a deterministic mock payment provider.

### State machine

```text
CREATED
   |
   v
PAYMENT_PENDING
   |
   +-----------> PAYMENT_FAILED ----> RELEASED
   |
   v
PAID
   |
   v
CONFIRMED
```

### Required failure cases

- [ ] Successful payment.
- [ ] Declined payment.
- [ ] Payment request timeout.
- [ ] Client retry after timeout.
- [ ] Duplicate webhook.
- [ ] Webhook arrives before normal request returns.
- [ ] Webhook arrives multiple times.
- [ ] Application crashes after payment succeeds but before ticket generation.

### Core principle

Payment success must eventually produce a valid confirmed order/ticket without creating duplicates.

Do not rely on a single in-memory function call to guarantee this.

---

# 11. Phase 7 — Cryptographically Signed Tickets

## This is the feature that makes the project truly deserving of the `FraudProof` name.

### Ticket payload

Example:

```json
{
  "ticket_id": "TKT_839201",
  "event_id": "EVT_102",
  "booking_id": "BK_9912",
  "owner_id": "USR_183",
  "version": 1,
  "issued_at": 1790921200,
  "expires_at": 1791007600,
  "nonce": "random-high-entropy-value"
}
```

### Signature

Possible initial implementation:

```text
signature = HMAC-SHA256(secret, canonical_payload)
```

Then encode something similar to:

```text
base64url(payload).base64url(signature)
```

### Important implementation requirements

- Canonical serialization must be deterministic.
- The signing secret must never be exposed to the frontend.
- Store only what is necessary.
- Prefer versioned ticket formats.
- Include a nonce.
- Never put sensitive personal information directly into the QR payload unless there is a strong reason.
- The verification service must validate the signature before trusting claims such as `event_id` or `owner_id`.

### Alternative

An asymmetric signature scheme can be considered later:

```text
private key -> ticket signing
public key  -> verification
```

This is particularly useful if verification needs to happen in separately deployed components that should not all possess the signing secret.

The exact cryptographic scheme should be documented in an ADR. Do not invent cryptography; use well-tested standard-library or established cryptographic libraries.

---

# 12. Phase 8 — QR Verification and Replay Protection

## Verification flow

```text
QR scanner
   |
   v
POST /api/tickets/verify
   |
   +--> decode payload
   |
   +--> verify signature
   |
   +--> verify ticket exists
   |
   +--> verify event matches checkpoint
   |
   +--> verify ticket status
   |
   +--> atomically transition ISSUED -> USED
   |
   +--> emit TicketScanned event
   |
   v
ACCEPT / REJECT
```

### Critical requirement: atomic consumption

Two scanners must not both admit the same ticket.

Example race:

```text
Scanner A -----> ticket T123 <----- Scanner B
                     |
              both see ISSUED
```

Only one should win the state transition.

Possible implementation patterns:

1. PostgreSQL transaction + row lock.
2. Conditional update:

```sql
UPDATE tickets
SET status = 'USED', used_at = NOW()
WHERE id = :ticket_id
  AND status = 'ISSUED';
```

Then:

```text
rows_updated == 1 -> ACCEPT
rows_updated == 0 -> REJECT
```

Use database state as the source of truth. Redis may accelerate lookups but must not become the sole authoritative ticket state unless the architecture explicitly proves durability and consistency requirements.

### Required attack tests

- [ ] Valid QR -> accepted once.
- [ ] Same QR -> rejected second time.
- [ ] Tampered event ID -> rejected.
- [ ] Tampered ticket ID -> rejected.
- [ ] Tampered timestamp -> rejected.
- [ ] Expired ticket -> rejected.
- [ ] Revoked ticket -> rejected.
- [ ] Ticket from another event -> rejected.
- [ ] Two concurrent scans -> exactly one acceptance.

---

# 13. Phase 9 — Ticket Transfer and Revocation

## Goal

Make ticket ownership changes auditable and invalidate the old ticket representation.

### Ownership history

```text
Ticket T123
   |
   +--> version 1: Alice
   |
   +--> version 2: Bob
   |
   +--> version 3: Charlie
```

### Transfer flow

```text
Alice
  |
  v
POST /tickets/T123/transfer
  |
  v
Create transfer record
  |
  v
Invalidate version 1
  |
  v
Create version 2 for Bob
  |
  v
Issue new signed token
```

### Requirements

- [ ] Old QR becomes invalid.
- [ ] New owner can verify the ticket.
- [ ] Transfer history is immutable.
- [ ] Used/revoked tickets cannot be transferred.
- [ ] Transfer actions are idempotent.
- [ ] Transfer permissions are checked server-side.
- [ ] Suspicious rapid transfer patterns are available to the fraud system.

---

# 14. Phase 10 — Fraud / Abuse Detection

## Goal

Start with deterministic risk rules. Do not start with an LLM.

### Initial risk features

Possible signals:

```text
+30  unusually high booking attempts per minute
+25  repeated payment failures
+20  many accounts attempting the same event from a shared source
+20  rapid ticket transfers
+15  abnormal request velocity
+15  repeated reservation expiry behavior
+30  behavior matching known bot patterns
```

These numbers are starting examples only. They must be treated as configuration and tuned using test data.

### Example decision

```text
risk < threshold_1
    -> ALLOW

threshold_1 <= risk < threshold_2
    -> CHALLENGE / manual review / stricter throttling

risk >= threshold_2
    -> BLOCK
```

Do not call this a real-world calibrated fraud model unless the system has a real evaluation dataset.

### Fraud event model

```text
fraud_events
------------
id
user_id
event_id
action
risk_score
rule_id
reason
timestamp
```

### Example fraud rules

- `HIGH_BOOKING_VELOCITY`
- `REPEATED_PAYMENT_FAILURE`
- `RAPID_TRANSFER_CHAIN`
- `EXCESSIVE_RESERVATION_EXPIRY`
- `BOT_LIKE_REQUEST_PATTERN`
- `MULTI_ACCOUNT_EVENT_ABUSE`

### Organizer fraud dashboard

Show:

```text
Suspicious attempts
Blocked requests
Challenged accounts
Top triggered rules
Booking velocity
Transfer velocity
Payment failure rate
Ticket verification anomalies
```

### Optional Phase 2 — ML

Once the rule engine produces structured features, an ML model can optionally consume them:

```text
raw events
   |
   v
feature extraction
   |
   v
rule engine + ML model
   |
   v
risk score
```

The ML addition should be a real evaluation problem, not an "AI" label added for appearance.

---

# 15. Phase 11 — Rate Limiting and Abuse Protection

OWASP identifies unrestricted resource consumption and abuse of sensitive business flows as major API security risks, and ticket purchasing is directly the kind of business flow that can be abused automatically. citeturn172103search4turn172103search7

### Rate-limit candidates

- `POST /reservations`
- `POST /payments`
- `POST /tickets/verify`
- `POST /tickets/transfer`
- login/auth endpoints
- event search endpoints if needed

### Redis-backed model

Possible structure:

```text
request
   |
   v
Redis token bucket / fixed window / sliding window
   |
   +--> allowed
   |
   +--> HTTP 429
```

### Make limits configurable

```text
RATE_LIMIT_BOOKING_PER_USER
RATE_LIMIT_BOOKING_PER_IP
RATE_LIMIT_LOGIN
RATE_LIMIT_TICKET_VERIFY
```

Avoid over-aggressive hard-coded limits that make legitimate testing difficult.

### Abuse tests

- [ ] 1 user sends burst traffic.
- [ ] 1 IP sends burst traffic.
- [ ] Many accounts send traffic.
- [ ] High-rate ticket verification.
- [ ] High-rate reservation attempts for a sold-out event.
- [ ] Ensure normal traffic remains functional.

---

# 16. Phase 12 — Event-Driven Architecture

## Goal

Move non-critical side effects out of the synchronous booking request.

### Example

```text
Booking Service
     |
     v
BookingConfirmed event
     |
     v
Message Broker
     |
     +------------+--------------+---------------+
     |            |              |
     v            v              v
Notification   Fraud         Analytics
worker         worker        worker
```

Google Cloud's event-driven architecture guidance describes events as immutable facts that can fan out to multiple consumers; this supports loose coupling and independent scaling of consumers. citeturn172103search6turn172103search0

### Candidate events

```text
ReservationCreated
ReservationExpired
PaymentInitiated
PaymentSucceeded
PaymentFailed
BookingConfirmed
TicketIssued
TicketTransferred
TicketRevoked
TicketScanned
FraudDetected
```

### Required event envelope

Use a common format such as:

```json
{
  "event_id": "uuid",
  "event_type": "BookingConfirmed",
  "event_version": 1,
  "occurred_at": "ISO-8601 timestamp",
  "producer": "booking-service",
  "correlation_id": "uuid",
  "aggregate_id": "booking-id",
  "payload": {}
}
```

### Consumer requirements

Every consumer should be designed to tolerate duplicate delivery.

At minimum:

```text
at-least-once delivery
        |
        v
idempotent consumer
```

The project should explicitly document whether the chosen broker provides at-most-once, at-least-once, or another delivery model and how the application handles duplicates.

---

# 17. Phase 13 — Outbox Pattern

## Problem

This is unsafe:

```text
DB transaction commits
        |
        X
Message publish fails
```

The database says the booking is confirmed, but downstream services never receive the event.

### Preferred pattern

```text
DB transaction
   |
   +--> update booking
   |
   +--> insert outbox event
   |
   v
COMMIT
   |
   v
Outbox publisher
   |
   v
Message broker
```

### Outbox table

```text
outbox_events
-------------
id
aggregate_type
aggregate_id
event_type
payload
created_at
published_at
attempt_count
last_error
```

### Agent implementation guidance

- [ ] Write business state + outbox row in the same DB transaction.
- [ ] Create a publisher worker.
- [ ] Publish unpublished rows.
- [ ] Mark them published only after broker acknowledgement.
- [ ] Retry failed publishing.
- [ ] Make consumers idempotent.
- [ ] Add metrics for outbox backlog.

This gives a strong interview discussion around transactional consistency between a database and an asynchronous broker.

---

# 18. Phase 14 — Observability

OpenTelemetry is a vendor-neutral observability framework for generating, collecting, and exporting traces, metrics, and logs. citeturn172103search1turn172103search9

## Goal

A production request should be traceable from frontend/API through database/cache/broker/worker operations.

### Instrument

- [ ] Incoming HTTP request.
- [ ] Booking flow.
- [ ] Reservation transaction.
- [ ] PostgreSQL query boundaries.
- [ ] Redis operations where useful.
- [ ] Message publication.
- [ ] Message consumption.
- [ ] Payment provider interaction.
- [ ] Ticket verification.
- [ ] Fraud decision.

### Trace example

```text
POST /reservations
  |
  +-- booking.service
        |
        +-- postgres.transaction
        |
        +-- inventory.update
        |
        +-- outbox.insert
        |
        +-- response
```

### Metrics

Track at minimum:

```text
http_requests_total
http_request_duration
booking_attempts_total
booking_success_total
booking_failure_total
reservation_expiry_total
payment_success_total
payment_failure_total
ticket_verification_success_total
ticket_verification_failure_total
ticket_replay_total
fraud_block_total
fraud_challenge_total
rate_limit_rejection_total
outbox_backlog
consumer_lag
```

### Business invariants as metrics

Especially valuable:

```text
inventory_negative_total = 0
oversold_ticket_count = 0
```

### Dashboards

Create dashboards for:

1. System health.
2. Booking funnel.
3. Ticket verification.
4. Fraud/abuse.
5. Database/broker/cache health.
6. Load-test runs.

---

# 19. Phase 15 — Structured Logging

## Requirements

Use structured JSON logs rather than free-form text for backend services.

Example:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "service": "booking-service",
  "event": "reservation_created",
  "reservation_id": "RES_123",
  "event_id": "EVT_42",
  "user_id": "USR_7",
  "correlation_id": "...",
  "trace_id": "..."
}
```

Do not log:

- passwords
- auth tokens
- payment secrets
- signing keys
- unnecessary personal data
- full payment details

Make PII logging an explicit security decision.

---

# 20. Phase 16 — API Design

## Recommended endpoint surface

### Public/event

```http
GET    /api/events
GET    /api/events/{event_id}
```

### Auth/user

```http
GET    /api/me
GET    /api/me/bookings
GET    /api/me/tickets
```

### Reservations

```http
POST   /api/reservations
GET    /api/reservations/{reservation_id}
POST   /api/reservations/{reservation_id}/cancel
```

### Payments

```http
POST   /api/orders/{order_id}/payment
POST   /api/webhooks/payment
```

### Tickets

```http
GET    /api/tickets/{ticket_id}
POST   /api/tickets/{ticket_id}/transfer
POST   /api/tickets/{ticket_id}/revoke
POST   /api/tickets/verify
```

### Organizer

```http
POST   /api/organizer/events
PATCH  /api/organizer/events/{event_id}
GET    /api/organizer/events/{event_id}/stats
GET    /api/organizer/events/{event_id}/fraud
```

### Admin

```http
GET    /api/admin/fraud/events
GET    /api/admin/audit-log
```

The exact API should be aligned with the existing route structure after repository inspection.

---

# 21. Phase 17 — OpenAPI / API Documentation

- [ ] Add OpenAPI specification.
- [ ] Document request/response schemas.
- [ ] Document authentication.
- [ ] Document idempotency headers.
- [ ] Document possible error responses.
- [ ] Document rate limits.
- [ ] Document webhook behavior.
- [ ] Generate Swagger UI or equivalent.

Every important endpoint should have examples.

---

# 22. Phase 18 — Security Test Lab

Create a dedicated `security/` or `docs/security/` area.

## Attack 1 — Duplicate booking

```text
100 concurrent requests
for a scarce event
```

Expected:

```text
inventory never negative
successful quantity <= capacity
```

## Attack 2 — QR replay

```text
Scan same ticket twice
```

Expected:

```text
first -> accepted
second -> rejected
```

## Attack 3 — Ticket tampering

Change `event_id`, `ticket_id`, `owner_id`, or expiry.

Expected:

```text
signature invalid -> reject
```

## Attack 4 — IDOR / BOLA

User A accesses User B's ticket ID.

Expected:

```text
403 or 404 according to API policy
```

OWASP explicitly recommends object-level authorization checks for every endpoint that uses a client-provided object identifier. citeturn172103search5

## Attack 5 — Function-level authorization

A regular user calls organizer/admin endpoints.

Expected:

```text
403
```

OWASP identifies this as Broken Function Level Authorization. citeturn172103search11

## Attack 6 — Resource abuse

Burst booking requests.

Expected:

```text
429 after configured limit
```

## Attack 7 — Mass assignment

Attempt to modify fields such as:

```text
role
status
risk_score
owner_id
```

Expected:

```text
server ignores or rejects unauthorized fields
```

OWASP specifically covers object property authorization and warns against exposing or modifying internal properties through generic object binding. citeturn172103search10

## Attack 8 — Replay a payment webhook

Send the exact same webhook multiple times.

Expected:

```text
order state changes once
one ticket issuance
```

---

# 23. Phase 19 — Load Testing

## Goal

Replace claims with evidence.

### Tool

Use k6 or Locust. k6 supports thresholds that can turn latency/error requirements into pass/fail criteria. citeturn777193search7

### Primary scenario

Use a scarce event:

```text
capacity = 10,000

concurrent users = configurable
booking attempts = configurable
```

### Measure

```text
requests/sec
p50
p95
p99
error rate
booking success rate
oversold quantity
reservation expiry rate
DB CPU
DB connections
Redis latency
broker lag
```

### Test progression

```text
100 users
500 users
1,000 users
5,000 users
10,000 users
```

Do not assume 10,000 users is achievable. The benchmark is the evidence.

### Example k6 threshold concept

```text
http_req_failed < 1%
p95 < chosen target
p99 < chosen target
oversold_count == 0
```

Actual thresholds must be chosen after baseline measurements.

### Golden result

The most valuable correctness result is not just low latency:

```text
10,000 concurrent attempts
10,000 available tickets

successful tickets <= 10,000
negative inventory = 0
oversold tickets = 0
```

Then document exact environment, workload, version, and results.

---

# 24. Phase 20 — Chaos / Failure Testing

## Goal

Test what happens when dependencies fail at inconvenient moments.

### Scenarios

#### Payment failure

```text
Reservation HELD
       |
       v
Payment service fails
       |
       v
Reservation RELEASED
```

#### Payment timeout

```text
PAYMENT_PENDING
       |
       v
Timeout
       |
 retry / reconciliation
```

#### Duplicate webhook

```text
same webhook x N
       |
       v
single effective state transition
```

#### Broker unavailable

The booking transaction should remain correct even if non-critical asynchronous publishing is temporarily unavailable, assuming the outbox pattern is implemented.

#### Notification service down

Booking should still succeed.

#### Fraud worker down

Define policy explicitly. For high-risk booking paths you may fail closed, challenge, or use a degraded rules-only mode; document the trade-off.

#### Redis down

Decide whether the system:

- temporarily disables non-critical rate limiting,
- falls back to DB-based protection,
- or fails closed for sensitive endpoints.

This is a design decision, not an implementation detail.

#### Application restart during booking

Booking state must remain recoverable from PostgreSQL and asynchronous events.

### Failure-injection tests

Use controlled local failure injection first. Do not introduce destructive chaos into an uncontrolled environment.

---

# 25. Phase 21 — CI/CD

## GitHub Actions pipeline

```text
Pull Request
    |
    +--> frontend lint
    +--> backend lint
    +--> type checks
    +--> unit tests
    +--> integration tests
    +--> security tests
    +--> Docker build
    +--> dependency/security scan
    |
    v
Merge
    |
    v
Deployment pipeline
```

### Recommended checks

- [ ] Python formatter/linter.
- [ ] TypeScript lint.
- [ ] TypeScript build.
- [ ] pytest.
- [ ] Angular unit tests.
- [ ] Playwright E2E tests.
- [ ] PostgreSQL integration tests.
- [ ] Migration tests.
- [ ] Docker image build.
- [ ] Container vulnerability scan.
- [ ] Secret scan.
- [ ] Dependency audit.

### Pull request policy

No merge if critical checks fail.

---

# 26. Phase 22 — Infrastructure as Code

Use Terraform.

## Suggested infrastructure

```text
GCP
 |
 +-- VPC / networking
 |
 +-- application runtime
 |
 +-- Cloud SQL PostgreSQL
 |
 +-- Redis / managed equivalent
 |
 +-- Pub/Sub or Kafka environment
 |
 +-- Secret Manager
 |
 +-- Load balancer / ingress
 |
 +-- monitoring / logging
 |
 +-- artifact/container registry
```

Cloud SQL provides managed PostgreSQL and supports production capabilities such as backups, high availability, and read replicas depending on edition/setup. citeturn777193search6turn777193search5

### Terraform requirements

- [ ] No hard-coded secrets.
- [ ] Variables for project/region/environment.
- [ ] Separate dev/staging/prod configuration where practical.
- [ ] Outputs for critical resources.
- [ ] State management documented.
- [ ] Least-privilege service accounts.

---

# 27. Phase 23 — Deployment Model

## Initial production model

A practical option:

```text
Internet
   |
   v
Load balancer / Nginx
   |
   +--> Angular SSR
   |
   +--> Flask API
           |
           +--> Cloud SQL PostgreSQL
           +--> Redis
           +--> Pub/Sub/Kafka
```

Alternatively, deploy frontend and backend to Cloud Run or another managed container runtime, depending on what is easiest to maintain and demonstrate.

The current README already documents Nginx, Gunicorn, Systemd, Angular SSR, Linux and GCP, so the production deployment can evolve from the existing approach rather than starting from zero. citeturn942151view1

### Production concerns

- [ ] HTTPS.
- [ ] Secret Manager.
- [ ] Health endpoints.
- [ ] Readiness/liveness strategy where the runtime supports it.
- [ ] Graceful shutdown.
- [ ] Database connection pooling.
- [ ] Migration strategy.
- [ ] Backups.
- [ ] Log retention.
- [ ] Alerting.
- [ ] Rate limits.
- [ ] CORS policy.
- [ ] Security headers.

---

# 28. Phase 24 — Frontend Upgrade

Do not neglect the UI. The backend is the differentiator, but the project should still look like a real product.

### User experience

- [ ] Event discovery page.
- [ ] Event detail page.
- [ ] Availability indicator.
- [ ] Reservation countdown.
- [ ] Payment state.
- [ ] Booking confirmation.
- [ ] Digital ticket/QR display.
- [ ] Ticket transfer UI.
- [ ] Ticket history.
- [ ] Verification result UI for scanner.

### Organizer dashboard

- [ ] Event creation.
- [ ] Inventory.
- [ ] Revenue/sales.
- [ ] Reservations.
- [ ] Ticket scans.
- [ ] Fraud signals.
- [ ] Suspicious activity timeline.

### Scanner interface

- [ ] QR scanner.
- [ ] Large ACCEPT/REJECT result.
- [ ] Reason for rejection.
- [ ] Event mismatch warning.
- [ ] Already-used warning.
- [ ] Invalid signature warning.

### UX proof

Include screenshots/GIFs in the final README.

---

# 29. Phase 25 — Audit Trail

Security-sensitive actions should be auditable.

### Log actions such as

```text
USER_LOGIN
RESERVATION_CREATED
RESERVATION_RELEASED
PAYMENT_SUCCEEDED
PAYMENT_FAILED
TICKET_ISSUED
TICKET_TRANSFERRED
TICKET_REVOKED
TICKET_SCANNED
TICKET_REPLAY_ATTEMPT
FRAUD_BLOCK
ADMIN_ACTION
```

Audit records should include:

```text
actor
action
resource
resource_id
timestamp
correlation_id
metadata
```

Make audit records append-only from normal application workflows.

---

# 30. Phase 26 — Architecture Decision Records (ADRs)

Create:

```text
docs/decisions/
  001-postgresql.md
  002-inventory-concurrency.md
  003-idempotency.md
  004-signed-tickets.md
  005-message-broker.md
  006-outbox-pattern.md
  007-redis.md
  008-observability.md
  009-cloud-deployment.md
```

Each ADR should contain:

```text
Context
Problem
Options considered
Decision
Why
Trade-offs
Consequences
```

### Example — broker ADR

```text
Options:
- synchronous HTTP
- Redis Streams
- RabbitMQ
- Kafka
- Google Pub/Sub

Decision:
[fill after evaluating actual constraints]

Reasons:
- delivery model
- replay requirements
- operational complexity
- cloud fit
- expected workload
```

The agent should **not** blindly choose Kafka because it sounds impressive. If GCP Pub/Sub is simpler and better suited to the deployment, use Pub/Sub and document the trade-off.

---

# 31. Recommended Repository Structure

Adapt this to the existing repository rather than deleting working code unnecessarily.

```text
fraudproof-event-booking/
│
├── frontend/
│   └── Angular application or existing src/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── events/
│   │   ├── bookings/
│   │   ├── inventory/
│   │   ├── payments/
│   │   ├── tickets/
│   │   ├── fraud/
│   │   ├── outbox/
│   │   ├── db/
│   │   └── config/
│   ├── tests/
│   ├── migrations/
│   └── worker/
│
├── infra/
│   ├── terraform/
│   └── docker/
│
├── load-tests/
│   ├── k6/
│   └── scenarios/
│
├── security/
│   ├── concurrency/
│   ├── api-abuse/
│   ├── ticket-tampering/
│   └── replay/
│
├── docs/
│   ├── architecture.md
│   ├── booking-concurrency.md
│   ├── ticket-security.md
│   ├── fraud-detection.md
│   ├── observability.md
│   ├── load-testing.md
│   ├── failure-testing.md
│   ├── api.md
│   └── decisions/
│
├── .github/
│   └── workflows/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

Exact structure can change based on the existing codebase. Avoid a massive refactor unless required.

---

# 32. Testing Strategy

The test pyramid should be deliberate.

## Unit tests

Test:

- reservation state transitions
- fraud rules
- signature generation/verification
- ticket status transitions
- permission checks
- idempotency behavior
- input validation

## Integration tests

Test against real PostgreSQL/Redis/broker dependencies where the behavior matters.

Examples:

- reservation + inventory transaction
- outbox transaction
- webhook processing
- ticket verification transaction
- Redis rate limiting

## End-to-end tests

Use Playwright to cover:

```text
browse -> reserve -> pay -> ticket
```

and:

```text
scanner -> scan -> accept/reject
```

## Security tests

Automate the attack cases from the security lab.

## Load tests

Automate k6/Locust workloads and preserve result artifacts.

## Regression policy

Every major bug discovered should produce a regression test.

---

# 33. Definition of Done for Core Engineering Claims

## Claim: prevents overselling

Must have:

- [ ] Atomic inventory operation.
- [ ] Transaction semantics documented.
- [ ] Concurrent integration tests.
- [ ] Load test.
- [ ] Invariant check.
- [ ] Result artifact showing zero oversold tickets for tested scenario.

## Claim: idempotent booking

Must have:

- [ ] Idempotency key API.
- [ ] Persistent idempotency record.
- [ ] Same-key/same-request test.
- [ ] Same-key/different-request test.
- [ ] Retry/failure test.

## Claim: fraud-resistant ticket

Must have:

- [ ] Cryptographic signature.
- [ ] Server-side verification.
- [ ] Tampering tests.
- [ ] Expiry/revocation behavior.
- [ ] Replay test.
- [ ] Concurrent scan test.

## Claim: production observable

Must have:

- [ ] Tracing.
- [ ] Metrics.
- [ ] Structured logs.
- [ ] Dashboard.
- [ ] At least one actionable alert.

## Claim: scalable

Must have:

- [ ] Defined workload.
- [ ] Load-test script.
- [ ] Repeatable environment.
- [ ] p50/p95/p99 results.
- [ ] Error rate.
- [ ] Resource measurements.
- [ ] Bottleneck analysis.

---

# 34. Performance Benchmark Plan

Run controlled experiments.

## Experiment A — naive booking vs. atomic inventory

If the original implementation permits a meaningful comparison, create a test branch or test harness that demonstrates the failure mode of naive check-then-write logic, then compare with the corrected design.

Record:

```text
workload
concurrency
capacity
successful tickets
oversold tickets
errors
latency
```

## Experiment B — synchronous side effects vs. event-driven

Compare booking latency before and after moving email/analytics/fraud processing out of the critical path.

Do not claim a universal improvement; report measured values.

## Experiment C — rate limiting

Compare resource behavior under abusive request volume with and without rate limiting.

## Experiment D — database/index tuning

Show query/latency effects of relevant indexes if there is an actual measurable bottleneck.

---

# 35. Failure Matrix

Create a table in `docs/failure-testing.md` similar to:

| Failure | Expected state | Recovery | User-visible result |
|---|---|---|---|
| Payment timeout | Reservation remains recoverable | Retry/reconciliation | Pending/retry |
| Payment failure | Reservation released | Automatic release | Payment failed |
| Duplicate webhook | Single effective transition | Idempotent handler | No duplicate ticket |
| Broker down | DB/outbox remains correct | Publisher retry | Booking can remain correct |
| Notification down | Booking unaffected | Consumer retry | Delayed notification |
| Redis down | Defined degraded mode | Fallback/restart | Rate-limit behavior documented |
| App restart | State recoverable from DB/events | Restart worker | No duplicate booking |
| Concurrent scan | One state transition | DB atomicity | One ACCEPT |

The exact expected behavior for Redis/fraud degradation is a design choice and must be explicitly documented.

---

# 36. Security Checklist

- [ ] HTTPS in deployment.
- [ ] Secrets in secret manager/environment, never source-controlled.
- [ ] Passwords/tokens never logged.
- [ ] Object-level authorization.
- [ ] Function-level authorization.
- [ ] Property-level authorization.
- [ ] Input validation.
- [ ] Output schemas.
- [ ] Rate limiting.
- [ ] Request body size limits.
- [ ] Pagination limits.
- [ ] Security headers.
- [ ] Secure cookie/token strategy.
- [ ] CORS configured narrowly.
- [ ] Dependency scanning.
- [ ] Container scanning.
- [ ] Audit logs.
- [ ] Ticket signature verification.
- [ ] Ticket replay protection.
- [ ] Webhook authenticity validation.
- [ ] Idempotent webhooks.

OWASP's 2023 API Security Top 10 should be the baseline reference for the API threat model. citeturn172103search2turn172103search4

---

# 37. What NOT to Build

Avoid these traps:

### Do not create many microservices without a reason

`UserService`, `EventService`, `TicketService`, `BookingService`, `PaymentService`, `QRService`, `AnalyticsService`, etc. can become architecture theater if the boundaries have no operational reason.

### Do not add AI just for branding

A serious deterministic fraud engine is the first milestone.

### Do not implement custom cryptography

Use established cryptographic primitives/libraries.

### Do not claim real fraud prevention

This is a portfolio project unless real-world fraud data and operations exist. Describe it as a **fraud-resistant design** and show the concrete attacks it prevents.

### Do not claim zero downtime/high availability without evidence

Deployments, health checks, retries, backups, and HA configuration are not the same as measured availability.

### Do not optimize without measurement

Create a baseline, measure, change one thing, measure again.

---

# 38. Recommended Implementation Order

This is the canonical order for an implementation agent.

## Stage 1 — Understand and stabilize

- [ ] Inspect the full existing repository.
- [ ] Run frontend/backend.
- [ ] Map current routes and data flow.
- [ ] Add baseline tests.
- [ ] Add Docker local setup.
- [ ] Record baseline metrics.

## Stage 2 — Data foundation

- [ ] PostgreSQL.
- [ ] Migrations.
- [ ] Schema.
- [ ] Seed data.
- [ ] Transactions.

## Stage 3 — Identity/security

- [ ] Auth.
- [ ] Roles.
- [ ] Resource authorization.
- [ ] Validation.
- [ ] Security tests.

## Stage 4 — Booking correctness

- [ ] Inventory.
- [ ] Reservation state machine.
- [ ] Atomic reservation.
- [ ] Timeouts.
- [ ] Idempotency.
- [ ] Concurrent tests.

## Stage 5 — Payment

- [ ] Payment adapter.
- [ ] Payment state machine.
- [ ] Webhooks.
- [ ] Idempotent webhook processing.

## Stage 6 — FraudProof ticketing

- [ ] Ticket issuance.
- [ ] Signature.
- [ ] QR.
- [ ] Verification.
- [ ] Atomic single-use.
- [ ] Replay prevention.
- [ ] Transfer/revocation.

## Stage 7 — Abuse/fraud

- [ ] Redis.
- [ ] Rate limiting.
- [ ] Fraud rules.
- [ ] Fraud events.
- [ ] Fraud dashboard.

## Stage 8 — Async architecture

- [ ] Broker.
- [ ] Events.
- [ ] Outbox.
- [ ] Idempotent consumers.
- [ ] Notification worker.
- [ ] Fraud worker.
- [ ] Analytics worker.

## Stage 9 — Observability

- [ ] OpenTelemetry.
- [ ] Metrics.
- [ ] Logs.
- [ ] Traces.
- [ ] Dashboards.
- [ ] Alerts.

## Stage 10 — Cloud and DevOps

- [ ] Docker.
- [ ] Terraform.
- [ ] GCP deployment.
- [ ] Secret manager.
- [ ] CI/CD.

## Stage 11 — Proof

- [ ] Security lab.
- [ ] Load tests.
- [ ] Failure tests.
- [ ] Performance report.
- [ ] Screenshots/GIFs.
- [ ] Architecture diagrams.
- [ ] ADRs.

## Stage 12 — Portfolio polish

- [ ] Rewrite README around engineering problems.
- [ ] Add live/demo environment where practical.
- [ ] Add architecture diagram.
- [ ] Add benchmark graphs.
- [ ] Add threat model.
- [ ] Add failure matrix.
- [ ] Add API docs.
- [ ] Add a 60–90 second demo video.
- [ ] Add resume-ready metrics from measured experiments only.

---

# 39. Suggested Milestone Structure

## Milestone 1 — Correct Booking

**Deliverable:** PostgreSQL-backed booking system with atomic inventory and idempotency.

Success criteria:

```text
concurrent tests pass
inventory invariant passes
retries do not duplicate bookings
```

## Milestone 2 — FraudProof Tickets

**Deliverable:** signed QR tickets with atomic single-use verification.

Success criteria:

```text
valid ticket -> accepted once
tampered ticket -> rejected
replayed ticket -> rejected
concurrent double scan -> one acceptance
```

## Milestone 3 — Fraud and Abuse

**Deliverable:** rate limiting + deterministic fraud engine + dashboard.

## Milestone 4 — Event-Driven Backend

**Deliverable:** broker + outbox + idempotent workers.

## Milestone 5 — Production Observability

**Deliverable:** OpenTelemetry + metrics + dashboards + structured logs.

## Milestone 6 — Scalability and Resilience

**Deliverable:** load tests + failure tests + performance report.

## Milestone 7 — Cloud + Portfolio

**Deliverable:** reproducible Terraform deployment + polished README + system design documentation.

---

# 40. Final Portfolio Architecture Story

The project should ultimately tell this story:

```text
A user wants to buy a scarce ticket.

        |
        v
Authentication / authorization
        |
        v
Idempotent reservation request
        |
        v
Atomic inventory reservation
        |
        v
Temporary hold
        |
        v
Payment workflow
        |
        +---- retry-safe webhook
        |
        v
Confirmed booking
        |
        +---- outbox event
                 |
                 v
              broker
           /      |      \
          v       v       v
      ticket    fraud   notification
       worker   worker     worker
          |
          v
   signed QR ticket
          |
          v
     event scanner
          |
          v
 signature + state verification
          |
          v
    atomic single-use
          |
          v
        ADMIT
```

Across all of this:

```text
OpenTelemetry
    |
    +--> traces
    +--> metrics
    +--> logs

Security testing
    |
    +--> IDOR/BOLA
    +--> replay
    +--> tampering
    +--> rate abuse

Load testing
    |
    +--> concurrency
    +--> latency
    +--> errors
    +--> overselling invariant

Failure testing
    |
    +--> retries
    +--> duplicate messages
    +--> service failure
    +--> restart recovery
```

---

# 41. README / Portfolio Requirements

The final README should not be a generic framework list.

Use this structure:

```text
# FraudProof

One-line problem statement.

[Live Demo] [Architecture] [API Docs] [Load Test Results]

## Why this project exists

## Threats / failure modes

## Architecture

## Booking correctness

## Fraud-resistant ticket design

## Ticket verification

## Fraud detection

## Event-driven architecture

## Observability

## Load-testing results

## Failure testing

## Security testing

## Infrastructure

## Design decisions

## Local development

## API documentation

## Screenshots / demo

## Engineering writeups
```

### Benchmark section

Include a table populated from real tests:

| Metric | Result | Environment | Workload |
|---|---:|---|---|
| Throughput | TODO | TODO | TODO |
| p50 latency | TODO | TODO | TODO |
| p95 latency | TODO | TODO | TODO |
| p99 latency | TODO | TODO | TODO |
| Error rate | TODO | TODO | TODO |
| Oversold tickets | TODO | TODO | TODO |
| Duplicate bookings | TODO | TODO | TODO |

---

# 42. Resume Positioning

Do not use final numbers until measured.

Potential final structure:

> **FraudProof — Distributed Event Ticketing Platform**  
> Built a fraud-resistant event booking platform using Angular, Python, PostgreSQL, Redis and a message broker, implementing atomic inventory reservation and idempotent payment workflows to prevent overselling and duplicate side effects under concurrent requests. Designed cryptographically signed, single-use QR tickets with replay protection and auditable ownership transfer; added rate limiting, deterministic fraud detection, OpenTelemetry tracing and automated load/failure testing.

After benchmarking, replace generic language with actual measurements:

```text
- X concurrent users
- Y booking attempts
- Z req/s
- p95 = N ms
- 0 oversold tickets
- 0 duplicate ticket issuance under retry tests
```

Only use results that were actually measured.

---

# 43. Interview Preparation Generated by the Project

The finished project should allow strong discussion around:

### Backend / concurrency

- How do you prevent overselling?
- Why PostgreSQL instead of SQLite?
- Row locking vs atomic conditional updates?
- What isolation level did you use?
- What happens when a transaction fails?
- How do you handle reservation expiry?

### Distributed systems

- Why idempotency?
- What happens when the client retries?
- What if Kafka/PubSub is unavailable?
- Why the outbox pattern?
- At-least-once delivery vs exactly-once expectations?
- How do consumers handle duplicates?

### Security

- How is a ticket authenticated?
- Why HMAC vs asymmetric signatures?
- How do you prevent QR replay?
- How do you prevent BOLA/IDOR?
- How do rate limits work?
- How do you avoid leaking sensitive ticket information?

### Observability

- How can you debug a slow booking?
- What does a distributed trace look like?
- Which metrics matter for the business?
- What alerts would page an engineer?

### Scalability

- Where is the bottleneck?
- What happens if booking traffic increases 10x?
- Can the ticket verifier scale independently?
- Can fraud processing be asynchronous?

### Reliability

- What happens when Redis fails?
- What happens when payment succeeds but the process crashes?
- What happens if an event is consumed twice?
- How do you recover from a stuck reservation?

---

# 44. Exact Implementation vs. Agent Design Guidance

## The following are exact enough to implement directly

- PostgreSQL migration direction.
- Inventory invariant.
- Idempotency-key concept.
- Reservation state machine.
- Ticket state transitions.
- Conditional-update pattern.
- Outbox data model.
- Event envelope.
- Suggested endpoint categories.
- Security attack cases.
- Test categories.
- Load-test metrics.
- Repository/documentation structure.

## The following require repository-specific implementation choices

- Existing Flask application layout.
- Existing database access layer/ORM.
- Existing API route names.
- Exact Angular component structure.
- Existing auth assumptions.
- Exact payment integration.
- Kafka vs Pub/Sub.
- Exact Redis deployment.
- Cloud Run vs GKE vs VM.
- Exact Terraform resources.
- Exact OpenTelemetry exporters.
- Exact rate-limit algorithm.
- Exact fraud-score thresholds.
- Exact cryptographic library/API.

The implementation agent should inspect the current code before modifying those areas.

## The following must be empirically measured

- Maximum throughput.
- p50/p95/p99 latency.
- Database bottlenecks.
- Redis bottlenecks.
- Broker latency/lag.
- Number of concurrent users supported.
- Effectiveness of fraud rules.
- Effect of indexes.
- Effect of caching.
- Effect of horizontal scaling.

---

# 45. Agent Working Rules

When another coding agent uses this plan:

1. **Inspect before refactoring.** Understand existing routes, models, components, and deployment before deleting or rewriting them.
2. **Keep the app runnable after every milestone.** Avoid long periods where the repo is completely broken.
3. **Make small commits.** Prefer one coherent architectural change per commit.
4. **Add tests with every correctness feature.** Especially concurrency, idempotency, ticket verification, and authorization.
5. **Do not hard-code secrets.** Use environment variables locally and Secret Manager in production.
6. **Do not silently weaken security to make tests pass.** If a security rule is inconvenient, fix the design rather than bypassing it.
7. **Do not invent benchmark results.** Create scripts and report actual measurements.
8. **Do not introduce infrastructure that cannot be reproduced.** Prefer Docker Compose locally and Terraform for cloud resources.
9. **Document important decisions.** Add an ADR whenever an architectural choice creates a meaningful trade-off.
10. **Prefer boring, proven primitives.** PostgreSQL transactions, Redis, standard crypto, OpenTelemetry, and a well-supported message broker are preferable to custom mechanisms.
11. **Keep PII minimal.** Collect/store only what the product needs.
12. **Do not expose internal fields by default.** Use explicit response schemas.
13. **Make workers idempotent.** Duplicate events should not duplicate business side effects.
14. **Use feature flags/configuration for risky migrations.** Especially during payment, reservation, and deployment changes.
15. **Preserve backwards compatibility where practical.** Migrate endpoints/data incrementally rather than breaking everything at once.

---

# 46. Minimum “FAANG-Level Portfolio” Cut

If time becomes limited, prioritize these seven pieces:

1. **Atomic concurrent inventory reservation**
2. **Idempotent booking/payment workflow**
3. **Cryptographically signed + single-use QR tickets**
4. **Rate limiting + deterministic fraud engine**
5. **Event-driven processing with an outbox**
6. **OpenTelemetry observability**
7. **10K-scale or highest-achievable controlled load test with measured results**

These seven features create the core engineering narrative.

Everything else supports them.

---

# 47. Optional Advanced Extensions

Only consider these after the core system is correct:

- [ ] Read replicas for read-heavy event pages.
- [ ] Partitioning for large audit/event tables.
- [ ] Dead-letter queue for poison events.
- [ ] Event replay tooling.
- [ ] Reservation reconciliation job.
- [ ] Scheduled cleanup worker.
- [ ] Distributed rate limiting across multiple API instances.
- [ ] Asymmetric ticket signatures.
- [ ] Offline scanner mode with carefully designed cryptographic/security constraints.
- [ ] Multi-region architecture analysis.
- [ ] Canary deployment.
- [ ] Blue/green deployment.
- [ ] Feature flags.
- [ ] ML-based fraud scoring.
- [ ] Synthetic traffic generation.
- [ ] SLO/error-budget tracking.

Do not implement these merely to increase the technology count.

---

# 48. Final Success Criteria

The project is ready to be presented as a serious portfolio system when all of these are true:

### Product

- [ ] User can discover and book events.
- [ ] Organizer can manage events.
- [ ] User receives a verifiable ticket.
- [ ] Scanner can verify tickets.
- [ ] Ticket transfers work.

### Correctness

- [ ] Overselling is prevented under tested concurrency.
- [ ] Idempotent retries work.
- [ ] Duplicate webhooks are safe.
- [ ] Ticket verification is atomic.

### Security

- [ ] BOLA tests pass.
- [ ] Function-level authorization tests pass.
- [ ] Property-level authorization tests pass.
- [ ] Ticket tampering is rejected.
- [ ] QR replay is rejected.
- [ ] Rate limits work.

### Distributed systems

- [ ] Async events are implemented.
- [ ] Outbox is implemented.
- [ ] Consumers are idempotent.
- [ ] Failure handling is documented/tested.

### Operations

- [ ] OpenTelemetry is integrated.
- [ ] Dashboards exist.
- [ ] Structured logs exist.
- [ ] Alerts exist.
- [ ] CI/CD exists.
- [ ] Infrastructure is reproducible.

### Evidence

- [ ] Load-test scripts are committed.
- [ ] Load-test results are documented.
- [ ] Security attack results are documented.
- [ ] Failure/chaos results are documented.
- [ ] Architecture diagram is committed.
- [ ] ADRs are committed.
- [ ] README clearly explains engineering problems and measured outcomes.

---

# 49. Research References

These are the primary references used to shape this plan. They should be consulted again during implementation because exact product APIs and cloud capabilities can change.

1. **Current FraudProof repository** — architecture, current features, stack, and deployment notes.  
   https://github.com/Abhilekh-Talukdar/fraudproof-event-booking

2. **FraudProof README** — current system description and technologies.  
   https://github.com/Abhilekh-Talukdar/fraudproof-event-booking/blob/main/README.md

3. **FraudProof package.json** — Angular 19 / SSR dependency versions.  
   https://github.com/Abhilekh-Talukdar/fraudproof-event-booking/blob/main/package.json

4. **OWASP API Security Project / API Security Top 10 2023** — API authorization, authentication, resource consumption, and sensitive business-flow risks.  
   https://owasp.org/projects/api-security-project

5. **OWASP API1: Broken Object Level Authorization** — object-level authorization requirements.  
   https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/

6. **OWASP API4: Unrestricted Resource Consumption** — API resource-abuse risks.  
   https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/

7. **Google Cloud — Event-driven architectures** — event/consumer decoupling and architecture patterns.  
   https://cloud.google.com/eventarc/standard/docs/event-driven-architectures

8. **Google Cloud — Event-driven architecture with Pub/Sub** — event streams, consumers, delivery semantics, and trade-offs.  
   https://docs.cloud.google.com/solutions/event-driven-architecture-pubsub

9. **OpenTelemetry documentation** — vendor-neutral traces, metrics, logs, and collectors.  
   https://opentelemetry.io/docs/

10. **Stripe — Idempotent requests** — industry example of retry-safe API semantics.  
    https://docs.stripe.com/api/idempotent_requests

11. **PostgreSQL documentation** — row locking / `FOR UPDATE` behavior.  
    https://www.postgresql.org/docs/current/sql-select.html

12. **Google Cloud SQL for PostgreSQL** — managed PostgreSQL deployment and production features.  
    https://docs.cloud.google.com/sql/docs/postgres

13. **Grafana k6 — thresholds** — pass/fail performance criteria for load tests.  
    https://grafana.com/docs/k6/latest/using-k6/thresholds/

---

# 50. End State in One Sentence

> **FraudProof should become a measurable, failure-tested, fraud-resistant distributed ticketing system—not simply a larger event-booking CRUD application.**

