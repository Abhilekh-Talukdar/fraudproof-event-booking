# Booking correctness

`POST /api/reservations` creates a five-minute `HELD` reservation (configurable
with `RESERVATION_TTL_SECONDS`). It requires an `Idempotency-Key` header.

The reservation transaction does three things together:

1. Releases any expired holds and restores their inventory.
2. Performs a conditional inventory update that fails if insufficient tickets
   remain.
3. Persists both the reservation and the original idempotent response.

A retry with the same key and request returns the original `201` response. The
same key for another request returns `422`; it cannot consume more inventory.

Mock payment then moves a valid hold atomically from `reserved` to `sold`. A
decline or expired hold moves it from `reserved` back to `available`. Payment
responses are independently idempotent, so a lost success response cannot sell
the same hold twice.

The committed test suite covers state/invariant and idempotency behavior. The
100 competing-buyer test activates only when `FRAUDPROOF_TEST_DATABASE_URL`
points at a disposable PostgreSQL database, because SQLite cannot prove the
PostgreSQL concurrency semantics used in production.

The same PostgreSQL-only suite includes two simultaneous scans of one signed
ticket and requires exactly one acceptance.
