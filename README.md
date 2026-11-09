# FraudProof — High-Concurrency, Fraud-Resistant Event Ticketing Platform

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Angular 21](https://img.shields.io/badge/Angular-19-red.svg)](https://angular.dev)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)
[![Redis 7](https://img.shields.io/badge/Redis-7-D82C20.svg)](https://redis.io)
[![CI](https://github.com/Abhilekh-Talukdar/fraudproof-event-booking/actions/workflows/ci.yml/badge.svg)](https://github.com/Abhilekh-Talukdar/fraudproof-event-booking/actions/workflows/ci.yml)

**FraudProof** is an event ticketing application built around a few backend problems that are easy to get wrong: allocating limited inventory under concurrency, handling request retries, issuing tickets that cannot be tampered with, and processing background events reliably.

---

## Architecture Overview

```mermaid
graph TD
    subgraph Client Layer
        A[Angular 21 SPA / SSR]
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
- **Temporary Holds**: A reservation holds inventory for five minutes by default. Expired holds are released when the booking/payment paths process them.
- **Concurrency Test**: A PostgreSQL-only test is included for 100 buyers competing for 10 tickets. It runs when `FRAUDPROOF_TEST_DATABASE_URL` points to a disposable PostgreSQL database.

### 2. End-to-End Persistent Idempotency
- **Durable `IdempotencyRecord`**: Every critical mutation (`/api/reservations`, `/api/reservations/:id/mock-payment`) requires an `Idempotency-Key` header.
- **Payload Fingerprinting**: SHA-256 fingerprinting ensures that replaying an identical key with a conflicting request payload is rejected with `409 Conflict`.
- **Safe Network Retries**: Retried client requests return the original exact response payload without consuming additional inventory or double-billing.

### 3. Cryptographically Signed Fraud-Proof Tickets
- **HMAC-SHA256 Token Generation**: Each ticket token signs its ticket ID, event ID, order ID, version, timestamps, and nonce.
- **Replay & Double-Spend Protection**: The verification API validates HMAC integrity before database lookup and atomically transitions tickets from `ISSUED` to `USED` in a single database transaction. Re-scans of the same QR code are immediately rejected.

### 4. Session Authentication & Role-Based Access Control (RBAC)
- **Roles**: `ADMIN`, `USER`, and `SCANNER` roles with fine-grained endpoint authorization.
- **Ownership Verification**: Users can only inspect and settle reservations and tickets that belong to their authenticated identity.
- **Secure Sessions**: Protected by HTTP-only, SameSite session cookies.

### 5. Multi-Layer Abuse & Fraud Detection
- **Rate Limiting**: Distributed rate-limiting via Flask-Limiter with Redis backend (protecting auth and booking endpoints).
- **Rule-Based Cutoffs**: Blocks automated ticket-hoarding bots creating ≥ 50 reservations in a 1-hour rolling window before reaching the database lock layer.
- **Security Audit Log**: Records actions such as `user_registered`, `login_success`, `login_failed`, and `abuse_blocked`, along with the available user, IP, and timestamp details.

### 6. Transactional Outbox Pattern & Background Reliability
- **Dual-Write Hazard Elimination**: Business mutations and event generation (`reservation.created`, `payment.confirmed`, `payment.declined`, `abuse.blocked`) are committed atomically within the same database transaction in the `outbox_events` table. If the business write rolls back, no orphaned event is emitted.
- **Worker Claims**: The worker claims `PENDING` events with PostgreSQL `FOR UPDATE SKIP LOCKED`, so concurrent workers do not claim the same pending row.
- **Retries**: Failed handlers are retried on later worker cycles, up to `MAX_ATTEMPTS`. Events that reach the limit are marked `FAILED`. The current handlers log events; email or message-broker delivery is not wired up yet.

---

## Tech Stack

| Domain | Technology |
|---|---|
| **Frontend** | Angular 21, TypeScript, RxJS, Server-Side Rendering (SSR) |
| **Backend** | Python 3.12, Flask, Flask-SQLAlchemy 3.x, Flask-Migrate, Flask-Limiter |
| **Database** | PostgreSQL 16 (via `psycopg3` binary driver), SQLAlchemy 2.0 |
| **Cache & Distributed State** | Redis 7 (rate limiting, locks) |
| **Testing** | Pytest, In-Memory SQLite (unit test suite), PostgreSQL (concurrency stress test) |
| **Containerization** | Docker, Docker Compose |

---

## Getting Started

### Prerequisites
- **Node.js**: v22+ and `npm`
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

**Scheduled job — Reservation expiry cleanup:**
```bash
cd backend
source venv/bin/activate
flask reservations expire --batch-size 1000
```
*Schedule this command with cron or a platform scheduler. Each invocation releases up to 1,000 expired holds; run it repeatedly to drain larger backlogs. Row-level locking allows concurrent cleanup jobs to share work safely.*

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

The current results are reported by CI. CI also runs the PostgreSQL concurrency tests and an Angular production build.

To run the live/ **100-concurrent-buyer PostgreSQL stress test**:
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
curl -i -X POST http://localhost:5001/api/tickets/verify \
  -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"token": "<SIGNED_TICKET_TOKEN>"}'
```
*Admit ticket exactly once; replaying this payload returns `409 Ticket already consumed`.*

---

## Project Documentation
- Detailed Design & Architecture Plan: [FRAUDPROOF_FAANG_PORTFOLIO_PLAN.md](FRAUDPROOF_FAANG_PORTFOLIO_PLAN.md)
- Concurrency & Inventory Specifications: [docs/booking-concurrency.md](docs/booking-concurrency.md)
- Design decisions: [docs/decisions/](docs/decisions/)
