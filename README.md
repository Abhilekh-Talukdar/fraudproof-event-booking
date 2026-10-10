# FraudProof — High-Concurrency, Fraud-Resistant Event Ticketing Platform

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Angular 19](https://img.shields.io/badge/Angular-19-red.svg)](https://angular.dev)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)
[![Redis 7](https://img.shields.io/badge/Redis-7-D82C20.svg)](https://redis.io)
[![Tests Passing](https://img.shields.io/badge/pytest-33%20passed-brightgreen.svg)]()

**FraudProof** is a production-grade event ticketing and booking system built to demonstrate **FAANG-caliber systems engineering patterns**: distributed concurrency safety, zero-overselling inventory invariants, idempotent request processing, cryptographic replay-proof ticket validation, rule-based abuse defense, and transactional outbox event dispatch.

---

## Architecture Overview

```mermaid
graph TD
    subgraph Client Layer
        A[Angular 19 SPA / SSR]
        S[Door Scanner / Gate Staff]
    end

    subgraph API & Application Layer
        API[Flask REST API :5001]
        Auth[Session Auth & RBAC]
        Limiter[Flask-Limiter / Abuse Engine]
        Worker[Outbox Worker Process]
    end

    subgraph Storage & Reliability Layer
        PG[(PostgreSQL 16)]
        Redis[(Redis 7)]
    end

    A -->|Browse & Book| API
    S -->|Verify Ticket QR| API
    API --> Auth
    API --> Limiter
    Limiter -->|Rate Limits & Windows| Redis
    API -->|Atomic Row Locks & Invariants| PG
    API -->|Atomic Event Enqueue| PG
    Worker -->|FOR UPDATE SKIP LOCKED| PG
    Worker -->|Execute Handlers / Retry| PG
```

---

## Core Systems Engineering Features

### 1. Atomic Inventory Reservations & Invariant Guarantees
- **PostgreSQL Source of Truth**: Replaced naive database queries with atomic row-level locks (`SELECT ... FOR UPDATE`) and conditional decrements.
- **Strict Conservation Law**: Enforces database-level check constraints ensuring `total_quantity = available_quantity + reserved_quantity + sold_quantity` at all times.
- **TTL Reservation Holds**: Temporary 5-minute hold on ticket inventory; expired holds automatically release back to `available_quantity` without manual intervention or data corruption.
- **Overselling Immunity**: Stress-tested against 100 concurrent competing buyers with zero partial allocations or oversold seats.

### 2. End-to-End Persistent Idempotency
- **Durable `IdempotencyRecord`**: Every critical mutation (`/api/reservations`, `/api/reservations/:id/mock-payment`) requires an `Idempotency-Key` header.
- **Payload Fingerprinting**: SHA-256 fingerprinting ensures that replaying an identical key with a conflicting request payload is rejected with `409 Conflict`.
- **Safe Network Retries**: Retried client requests return the original exact response payload without consuming additional inventory or double-billing.

### 3. Cryptographically Signed Fraud-Proof Tickets
- **HMAC-SHA256 Token Generation**: Issued tickets contain tamper-proof cryptographic signatures computed over ticket ID, event ID, user ID, and issue timestamp.
- **Replay & Double-Spend Protection**: The verification API validates HMAC integrity before database lookup and atomically transitions tickets from `ISSUED` to `USED` in a single database transaction. Re-scans of the same QR code are immediately rejected.

### 4. Session Authentication & Role-Based Access Control (RBAC)
- **Roles**: `ADMIN`, `USER`, and `SCANNER` roles with fine-grained endpoint authorization.
- **Ownership Verification**: Users can only inspect and settle reservations and tickets that belong to their authenticated identity.
- **Secure Sessions**: Protected by HTTP-only, SameSite session cookies.

### 5. Multi-Layer Abuse & Fraud Detection
- **Rate Limiting**: Distributed rate-limiting via Flask-Limiter with Redis backend (protecting auth and booking endpoints).
- **Rule-Based Cutoffs**: Blocks automated ticket-hoarding bots creating ≥ 50 reservations in a 1-hour rolling window before reaching the database lock layer.
- **Durable Security Audit Log**: Audits all critical security actions (`user_registered`, `login_success`, `login_failed`, `abuse_blocked`) with client IP, user agent, and timestamp.

### 6. Transactional Outbox Pattern & Background Reliability
- **Dual-Write Hazard Elimination**: Business mutations and event generation (`reservation.created`, `payment.confirmed`, `payment.declined`, `abuse.blocked`) are committed atomically within the same database transaction in the `outbox_events` table. If the business write rolls back, no orphaned event is emitted.
- **Concurrent Safe Worker**: Background worker drains `PENDING` outbox events using PostgreSQL `FOR UPDATE SKIP LOCKED`, allowing horizontally scalable worker instances without duplicate event processing.
- **Exponential Backoff & Retries**: Tracks retry counts up to `MAX_ATTEMPTS`, marking failed events as `FAILED` for dead-letter review.

---

## Tech Stack

| Domain | Technology |
|---|---|
| **Frontend** | Angular 19, TypeScript, RxJS, Server-Side Rendering (SSR) |
| **Backend** | Python 3.12, Flask, Flask-SQLAlchemy 3.x, Flask-Migrate, Flask-Limiter |
| **Database** | PostgreSQL 16 (via `psycopg3` binary driver), SQLAlchemy 2.0 |
| **Cache & Distributed State** | Redis 7 (rate limiting, locks) |
| **Testing** | Pytest, In-Memory SQLite (unit test suite), PostgreSQL (concurrency stress test) |
| **Containerization** | Docker, Docker Compose |

---

## Getting Started

### Prerequisites
- **Node.js**: v18+ (LTS recommended) and `npm`
- **Python**: 3.12+
- **Docker & Docker Compose**

---

### Step 1: Start Infrastructure (PostgreSQL & Redis)

From the project root:
```bash
docker compose up -d
```
Verify containers are healthy:
```bash
docker compose ps
```

---

### Step 2: Configure & Setup Backend

```bash
cd backend

# Create and activate virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Alembic database migrations
flask db upgrade

# Seed demo events & test accounts
flask seed-demo-data
```

This seeds 3 realistic demo events and creates two pre-configured demo accounts:
- **Attendee:** `attendee@fraudproof.local` (Password: `fraudproof-demo-password`)
- **Gate Scanner:** `scanner@fraudproof.local` (Password: `fraudproof-demo-password`)

---

### Step 3: Run the Backend & Background Worker

**Terminal 1 — API Server:**
```bash
cd backend
source venv/bin/activate
python app.py
```
*API runs on `http://localhost:5001`.*

**Terminal 2 — Outbox Worker:**
```bash
cd backend
source venv/bin/activate
flask worker run --batch-size 50 --cycles 0
```
*Processes outbox events continuously in the background.*

---

### Step 4: Run the Angular Frontend

**Terminal 3 — Frontend Dev Server:**
```bash
npm install
npm start
```
*Open **`http://localhost:4200`** in your browser. The Angular dev proxy seamlessly routes `/api/*` requests to the Flask backend.*

---

## Automated Test Suite

Run the full pytest suite:
```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

Output:
```
============================== test session starts ==============================
collected 35 items

tests/test_abuse.py::test_register_rate_limit_enforced PASSED             [  2%]
tests/test_abuse.py::test_login_rate_limit_enforced PASSED                [  5%]
tests/test_abuse.py::test_rule_based_abuse_detection_blocks_after_50_reservations PASSED [  8%]
tests/test_abuse.py::test_audit_log_written_on_successful_registration PASSED [ 11%]
tests/test_abuse.py::test_audit_log_written_on_failed_login PASSED        [ 14%]
tests/test_abuse.py::test_audit_log_written_on_successful_login PASSED    [ 17%]
tests/test_abuse.py::test_audit_log_written_on_abuse_block PASSED         [ 20%]
tests/test_auth.py::test_registration_creates_only_a_regular_user_and_session PASSED [ 22%]
tests/test_auth.py::test_protected_reservation_requires_a_session PASSED  [ 25%]
tests/test_auth.py::test_payment_cannot_be_completed_by_another_user PASSED [ 28%]
tests/test_auth.py::test_idempotency_key_tied_to_user PASSED              [ 31%]
tests/test_outbox.py::test_reservation_creates_outbox_event PASSED        [ 34%]
tests/test_outbox.py::test_approved_payment_creates_outbox_event PASSED   [ 37%]
tests/test_outbox.py::test_declined_payment_creates_outbox_event PASSED   [ 40%]
tests/test_outbox.py::test_abuse_block_creates_outbox_event PASSED        [ 42%]
tests/test_outbox.py::test_worker_processes_pending_event_to_done PASSED  [ 45%]
tests/test_outbox.py::test_worker_marks_failed_after_max_attempts PASSED  [ 48%]
tests/test_outbox.py::test_worker_does_not_reprocess_done_events PASSED   [ 51%]
tests/test_outbox.py::test_worker_returns_zero_when_no_pending_events PASSED [ 54%]
tests/test_outbox.py::test_worker_marks_unknown_event_type_as_failed PASSED [ 57%]
tests/test_outbox.py::test_rolled_back_transaction_leaves_no_outbox_event PASSED [ 60%]
tests/test_owner.py::test_reservation_tracks_authenticated_user_ownership PASSED [ 62%]
tests/test_payments.py::test_approved_payment_converts_held_inventory_to_sold_once PASSED [ 65%]
tests/test_payments.py::test_declined_payment_releases_hold_and_preserves_inventory_invariant PASSED [ 68%]
tests/test_payments.py::test_expired_reservation_cannot_be_paid_and_inventory_is_restored PASSED [ 71%]
tests/test_reservations.py::test_reservation_decrements_available_inventory_and_preserves_invariant PASSED [ 80%]
tests/test_reservations.py::test_idempotent_retry_returns_original_hold_without_consuming_more_inventory PASSED [ 82%]
tests/test_reservations.py::test_same_idempotency_key_with_changed_request_is_rejected PASSED [ 85%]
tests/test_reservations.py::test_insufficient_inventory_does_not_create_a_partial_reservation PASSED [ 88%]
tests/test_tickets.py::test_successful_payment_issues_signed_ticket_with_ticket_holder PASSED [ 91%]
tests/test_tickets.py::test_valid_ticket_is_accepted_once_then_replay_is_rejected PASSED [ 94%]
tests/test_tickets.py::test_tampered_ticket_payload_is_rejected_before_database_lookup PASSED [ 97%]
tests/test_tickets.py::test_ticket_for_another_event_is_rejected_without_consumption PASSED [100%]

======================== 33 passed, 2 skipped in 2.80s =========================
```

To run the live **100-concurrent-buyer PostgreSQL stress test**:
```bash
FRAUDPROOF_TEST_DATABASE_URL="postgresql+psycopg://fraudproof:fraudproof@localhost:5432/fraudproof" pytest tests/test_postgres_concurrency.py -v
```

---

## API Usage Walkthrough

### 1. Authenticate
```bash
curl -i -X POST http://localhost:5001/api/auth/login \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"email":"attendee@fraudproof.local","password":"fraudproof-demo-password"}'
```

### 2. Reserve Tickets (with Idempotency-Key)
```bash
curl -i -X POST http://localhost:5001/api/reservations \
  -b cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: resv-request-uuid-001' \
  -d '{"eventId": 1, "quantity": 2}'
```
*Returns `201 Created` with `reservationId` and `expiresAt`.*

### 3. Settle Payment
```bash
curl -i -X POST http://localhost:5001/api/reservations/<RESERVATION_ID>/mock-payment \
  -b cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: pay-request-uuid-001' \
  -d '{"outcome": "APPROVED"}'
```
*Converts reserved hold to sold, emits outbox events, and returns signed tickets.*

### 4. Verify & Admit Ticket (Gate Scanner)
```bash
curl -i -X POST http://localhost:5001/api/tickets/verify-and-consume \
  -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"ticketPayload": "<SIGNED_TICKET_PAYLOAD>"}'
```
*Admit ticket exactly once; replaying this payload returns `409 Ticket already consumed`.*

---

## Project Documentation
- Detailed Design & Architecture Plan: [FRAUDPROOF_FAANG_PORTFOLIO_PLAN.md](FRAUDPROOF_FAANG_PORTFOLIO_PLAN.md)
- Concurrency & Inventory Specifications: [docs/booking-concurrency.md](docs/booking-concurrency.md)
- Threat Model & Ticket Verification: [docs/threat-model.md](docs/threat-model.md)
