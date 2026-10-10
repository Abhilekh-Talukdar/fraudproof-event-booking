# 002 — Mock payment state machine

## Context

An external payment provider is failure-prone: a client can retry after a lost
response, a provider can decline, and a held reservation can expire while a
payment is in progress. Integrating a real provider before modelling these
states would hide the core correctness problem.

## Decision

Use a deterministic mock payment endpoint during portfolio development.

- `APPROVED` atomically transitions `HELD -> CONFIRMED`, `reserved -> sold`,
  and `PAYMENT_PENDING -> PAID`.
- `DECLINED` atomically transitions `HELD -> RELEASED`, returns reserved
  inventory to available, and records `PAYMENT_FAILED`.
- Each checkout request needs its own idempotency key and stores the complete
  response for 24 hours.

## Consequences

The API can exercise retry, decline, expiry, and state-transition behavior
without any payment secrets or financial data. A later provider adapter and
webhook handler must preserve these transitions and idempotency guarantees.
