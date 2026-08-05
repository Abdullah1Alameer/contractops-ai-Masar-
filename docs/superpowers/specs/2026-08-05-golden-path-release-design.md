# ContractOps Golden Path Release Design

## Objective

Deliver one production-safe demo path:

Upload → AI analysis → client review email → public review → request changes →
negotiation agreement → internal approval → ordered signature emails → signed →
manual activation.

The release extends existing review, negotiation, approval, version, signature,
activity, and lifecycle code. It does not introduce external email/e-sign
providers, queues, analytics, reports, dashboard redesign, or global backfills.

## Existing Capabilities Reused

- `LifecycleService.transition()` and lifecycle policy rules.
- Persisted review requests, public review portal, immutable decisions, stale
  checks, negotiation seeding, and activity events.
- Negotiation resolution and ordered internal approvals.
- Signature requests/signers, public signer portal, typed/drawn signatures,
  ordered-signing checks, signed PDF, and signature certificate.
- Existing internal review/signature panels, public bilingual pages, storage,
  rate limiting, API client, workflow summaries, pipeline buckets, and synthetic
  cleanup patterns.

## Configuration

Add the requested SMTP variables and `PORTAL_TOKEN_SECRET`. Configuration is
read at call time so tests can safely override environment values.

- TLS and SSL cannot both be enabled.
- SMTP timeout is bounded and positive.
- Enabled delivery requires host, port, from address, and portal secret.
- Demo/production delivery requires an HTTPS, non-localhost `PUBLIC_APP_URL`.
- Local/test mode may use HTTP localhost for local SMTP/API verification.
- Credentials and secret values are never returned or logged.

`.env.example` contains placeholders only. Existing `REVIEW_BASE_URL` remains a
compatibility fallback when delivery is disabled.

## Secure Public Tokens

New review and signer links use a cryptographically random nonce. The public
token is derived from that nonce and `PORTAL_TOKEN_SECRET` with HMAC-SHA256.
The database stores the nonce and token hash, never the public token. The token
is reproducible from nonce plus the application secret, allowing Copy Link and
Retry to reuse the same still-valid URL.

Public lookup hashes the presented token. Existing review requests with legacy
raw tokens remain readable; there is no global migration or backfill. Signature
tokens continue to be signer/request scoped. Activity and outbound records must
not contain public tokens.

## Outbound Delivery Persistence

Add `outbound_messages` with:

- identity/type/recipient/safe subject;
- contract and optional review/signature/signer foreign keys;
- `pending|sending|sent|failed|cancelled`;
- attempt count, provider message ID, safe error code;
- created/sent/failed timestamps.

No credentials, body, token, contract content, or signature data is stored.
Each retry creates a new attempt row for the same workflow and same link. A
short cooldown prevents repeated resend abuse. The active workflow is not
duplicated and the lifecycle stage is unchanged.

## SMTP Service

`send_email(...)` is the only SMTP entry point. It validates the recipient,
safe configuration, text and HTML content, then uses `smtplib.SMTP` or
`smtplib.SMTP_SSL` with the configured timeout and optional STARTTLS/login.
It returns only:

```json
{
  "status": "sent | failed",
  "provider_message_id": "string | null",
  "safe_error_code": "string | null",
  "sent_at": "timestamp | null"
}
```

SMTP exceptions are mapped to deterministic safe codes and never exposed
publicly. Acceptance by `send_message` is required before an attempt is sent.

## Transaction Pattern

Transaction A locks the workflow/contract, validates eligibility and staleness,
persists workflow/token state and a pending outbound row, then commits.

SMTP is called only after Transaction A has completed.

Transaction B locks the outbound row, increments attempt count, and persists
`sent` or `failed` with safe metadata, then commits. SMTP failure preserves the
workflow and valid link.

Public signer completion that unlocks another signer persists the signing
mutation, lifecycle events, and next pending invitation atomically. The SMTP
attempt for that invitation occurs only after commit.

## Review Delivery

The existing review creation service remains authoritative for eligibility,
current-version checks, lifecycle transition, and activity. The internal send
operation:

1. creates one review request and secure token;
2. creates one pending email attempt;
3. commits;
4. sends the email;
5. records delivery read-back.

Email subjects use a non-sensitive contract reference. HTML and text bodies
contain company identity, sender when available, review action, expiry, the
link fallback, and a warning not to forward.

Resend reuses the active request and token, creates a new delivery attempt,
does not transition the contract, and enforces cooldown. Internal responses and
UI expose safe delivery status, recipient, attempts, timestamps, Retry, and
Copy Link.

The public review portal and canonical decisions remain unchanged:

- approve → `internal_review`;
- request changes → `negotiation`;
- reject with reason → `rejected`.

Terminal, stale, expired, and cancelled reviews remain non-actionable.

## Signature Lifecycle

Creation requires:

- contract stage `ready_to_sign`;
- current version with status `approved`;
- completed current-version approval;
- no unresolved current-version negotiation;
- no active signature request;
- valid unique signer order and emails.

Creation leaves the contract in `ready_to_sign`, creates one draft request and
ordered waiting signers, logs `signature_request_created`, and commits once.
No invitation is sent until explicit Send.

Send invites only the currently eligible signer, creates a pending delivery
attempt, commits, sends, and records the result. Failure leaves the signer and
request valid with Retry/Copy Link.

All public actions lock and validate request, signer, current version, stage,
expiry, terminal state, and signer order. Expected errors use the requested
deterministic codes.

Intermediate signing atomically:

- marks the signer signed;
- marks the request partially signed;
- transitions `ready_to_sign → partially_signed`;
- logs signer and contract partial-sign events;
- unlocks the next signer;
- creates its pending invitation.

After commit, the next invitation is sent and delivery state persisted.

Final signing atomically generates existing PDF/certificate artifacts, marks
the request completed and version signed, transitions to `signed`, and records
completion events. It does not auto-activate.

Authorized manual activation requires a non-empty reason/evidence and performs
`signed → active` with `contract_activated`.

Decline requires a reason and returns `ready_to_sign|partially_signed →
internal_review`. Cancellation and expiry return active requests to
`ready_to_sign`; completed requests cannot be cancelled. All stage changes use
`LifecycleService.transition()`.

The local implementation is always labeled:
“Demo electronic signature / توقيع إلكتروني تجريبي” and is not represented as
a certified legally binding provider.

## Minimal Frontend

Only existing review and signature surfaces are extended:

- review send/history: recipient, delivery badge, attempts/timestamps,
  Retry Email, Copy Link;
- signature panel: ordered signer delivery state, explicit Send, Retry, Copy
  Link, partial/completed artifacts, manual Activate;
- public signer page: deterministic errors and persistent bilingual prototype
  disclosure.

Existing public review capabilities, document rendering, summaries, comments,
RTL/LTR, loading, and persistence are retained. No unrelated layout redesign.

## Verification

TDD uses a local/mock SMTP server. Persisted tests cover SMTP validation and
failure/retry, review delivery and workflow reuse, signature eligibility,
ordering, lifecycle outcomes, artifacts, activation, stale/atomic behavior,
token leakage, and summaries.

Release verification runs focused suites, full backend/frontend suites,
TypeScript, production build, local SMTP smoke, and a synthetic API/database
golden-path smoke. Smoke cleanup verifies zero database/file residue in
`finally`.

Real-inbox delivery is explicitly reported as not executed until working SMTP
credentials and an externally reachable HTTPS `PUBLIC_APP_URL` are supplied.

## Deferred Scope

Gmail API, Microsoft Graph, SendGrid, Resend, Signit, DocuSign, certified
e-signature assertions, queues, analytics, reports, dashboards, global stage
migration, old-data backfill, and broad notification/UX refactors are deferred.
