# 003 — HMAC-signed, single-use tickets

## Decision

Issue an opaque, QR-ready token after a successful payment. Its canonical JSON
payload contains only ticket, order, event, version, issue/expiry, and nonce
identifiers; it contains no personal information. The API signs the canonical
payload with HMAC-SHA256 and stores its hash and signature alongside the ticket.

Ticket verification authenticates the signature before trusting the payload,
matches it against the persisted ticket record, checks expiry and event context,
then conditionally changes `ISSUED -> USED`.

## Why HMAC now

One modular backend both issues and verifies tickets, so HMAC is the smallest
correct primitive. An asymmetric signing scheme is a later option if scanner
verification is deployed independently and must not possess the signing key.

## Security properties

- Editing an ID, version, or timestamp breaks the signature.
- The database remains the admission source of truth; a token alone is not
  sufficient.
- Conditional consumption lets only one concurrent scanner admit a ticket.
- Transfer/revocation will increment the version or change status in a later
  milestone, invalidating the old representation.
