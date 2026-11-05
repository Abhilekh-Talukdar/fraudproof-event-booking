# Outbox delivery and recovery

Outbox rows are committed in the same database transaction as the business change that created them. A worker claims a batch, records the claim, commits it, and only then invokes handlers.

## Claim lifecycle

- New events start as `PENDING`.
- A worker moves a row to `PROCESSING`, increments its attempt count, and records `claimed_at` plus a unique `claim_token`.
- A claim is considered abandoned after five minutes without renewal. A later worker can reclaim it.
- Rows left in `PROCESSING` without claim metadata are treated as abandoned. This also recovers rows created before the lease migration.
- If the maximum attempt count has already been consumed when a claim expires, the row is marked `FAILED` instead of being dispatched again.
- A claim token fences off a worker that resumes after another worker has taken over. Its final status update will not overwrite the newer claim.

## Delivery guarantee

The worker provides **at-least-once** delivery, not exactly-once side effects. A process can complete a handler and crash before recording `DONE`; the event may then be delivered again after its lease expires. Handlers that call external systems must therefore use an idempotency key derived from the outbox event ID, or otherwise make duplicate delivery safe.

The claim token protects the database state from a late worker. It cannot undo or prevent an external side effect that was already performed by a handler before the worker lost its lease.

## Operational notes

The default lease is 300 seconds. Keep handlers comfortably below that duration, or add lease renewal before introducing long-running handlers. Inspect `FAILED` rows and their `last_error` value during operational review; do not silently reset them without understanding the cause.
