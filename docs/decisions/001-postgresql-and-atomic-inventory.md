# 001 — PostgreSQL and atomic inventory updates

## Context

The original application writes bookings to SQLite without any capacity model.
That cannot demonstrate safe allocation when requests race for scarce tickets.

## Decision

Use PostgreSQL as the source of truth for inventory and reserve tickets with one
conditional update inside the reservation transaction:

```sql
UPDATE inventory
SET available_quantity = available_quantity - :quantity,
    reserved_quantity = reserved_quantity + :quantity,
    version = version + 1
WHERE event_id = :event_id
  AND available_quantity >= :quantity;
```

The request succeeds only when this updates exactly one row. PostgreSQL's row
locking for conflicting writes provides the concurrency boundary; Redis is not
part of this correctness guarantee.

## Consequences

- The invariant `total = available + reserved + sold` is also enforced by a
  database check constraint.
- A real PostgreSQL integration test, not an in-memory simulation, is required
  for the concurrent-buyer proof.
- SQLite remains an old local artifact only; the application no longer reads it.
