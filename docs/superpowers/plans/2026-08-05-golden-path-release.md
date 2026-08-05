# SMTP Review and Signature Golden Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete one persisted, demonstrable contract lifecycle with SMTP review/signature delivery, ordered prototype signing, signed state, and manual activation.

**Architecture:** Reuse canonical review, negotiation, approval, version, signature, activity, storage, and lifecycle services. Add one provider-independent SMTP boundary and one generic outbound-attempt table. Workflow state commits before SMTP; a second locked transaction persists safe delivery results.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy/PostgreSQL, stdlib `smtplib`/`email`, pytest, Next.js/React/TypeScript, Vitest.

## Global Constraints

- Never assign `contract.stage` directly; use `LifecycleService.transition()`.
- Never hold a database transaction open during SMTP.
- Never persist or log SMTP credentials, public tokens, email bodies, contract content, or signature data.
- Preserve current review, negotiation, approval, version, lineage, activity, and artifact behavior.
- Local electronic signatures must be labeled as a demo/prototype.
- Real-inbox delivery is not claimed without credentials and public HTTPS URL.
- Use synthetic/redacted test data and clean all smoke residue.

---

### Task 1: SMTP Configuration and Delivery Boundary

**Files:**
- Modify: `.env.example`
- Modify: `backend/app/config.py`
- Create: `backend/app/services/email_delivery.py`
- Create: `backend/tests/test_email_delivery.py`
- Create: `scripts/smtp_smoke.py`

**Interfaces:**
- Produces: `EmailDeliveryError(status_code, code)`, `EmailDeliveryResult`, `validate_email_configuration()`, `validate_recipient()`, and `send_email(...)`.

- [ ] **Step 1: Write failing SMTP tests**

Cover valid HTML/text delivery through an injected local SMTP client, invalid
recipient, disabled delivery, TLS+SSL conflict, missing config, non-positive
timeout, localhost/non-HTTPS public URL rejection in demo/production, safe
connection/send failures, and absence of credentials from results/errors.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && pytest tests/test_email_delivery.py -q`

Expected: import failure because `app.services.email_delivery` does not exist.

- [ ] **Step 3: Implement minimal SMTP service and config**

Use `EmailMessage` with plain text and HTML alternatives. Use `SMTP_SSL` for
SSL or `SMTP` plus `starttls()` for TLS, bounded timeout, optional login, and
`send_message()`. Return only `sent|failed`, provider message ID when supplied,
safe error code, and UTC timestamp. Add requested safe placeholders to
`.env.example`.

- [ ] **Step 4: Add safe SMTP smoke command**

`scripts/smtp_smoke.py --to user@example.com` validates config, sends a
non-confidential message, prints only safe status/code, and exits non-zero on
failure.

- [ ] **Step 5: Run focused tests and compile**

Run: `cd backend && pytest tests/test_email_delivery.py -q && python -m compileall -q app/services/email_delivery.py ../scripts/smtp_smoke.py`

Expected: all pass.

### Task 2: Outbound Attempt Persistence and Secure Reproducible Tokens

**Files:**
- Create: `database/migrations/018_email_delivery.sql`
- Modify: `backend/app/models.py`
- Create: `backend/app/services/outbound_messages.py`
- Modify: `backend/app/services/reviews.py`
- Modify: `backend/app/services/signature.py`
- Create: `backend/tests/test_outbound_messages.py`
- Modify: `backend/tests/test_reviews.py`
- Modify: `backend/tests/test_signature.py`

**Interfaces:**
- Produces: `OutboundMessage`, `create_pending_attempt(...)`,
  `record_delivery_result(...)`, `latest_delivery(...)`,
  `serialize_delivery(...)`, `enforce_resend_cooldown(...)`.
- Produces token helpers that persist a random nonce and SHA-256 token hash and
  regenerate the same public token with HMAC-SHA256 plus `PORTAL_TOKEN_SECRET`.

- [ ] **Step 1: Apply migration and write failing persisted tests**

Add `token_nonce`/`token_hash` compatibility columns to reviews,
`token_nonce` to signature signers, and `outbound_messages` with requested
states/fields/FKs/indexes. Tests assert state transitions, row locking,
attempt counts, no body/token columns, cooldown, workflow scoping, and safe
serialization.

- [ ] **Step 2: Verify RED**

Run: `python database/migrate.py && cd backend && pytest tests/test_outbound_messages.py -q`

Expected: failures because model/service are missing.

- [ ] **Step 3: Implement outbound service**

Create pending rows in caller transaction. After workflow commit, set
`sending`, commit, invoke `send_email`, then lock and persist sent/failed in a
fresh transaction. Each resend creates a new row but uses the same workflow.

- [ ] **Step 4: Implement token compatibility**

New rows store nonce/hash and reproduce links from nonce+secret. Public lookups
hash presented tokens. Legacy review plaintext tokens remain readable. Tokens
must never be included in activity metadata or outbound rows.

- [ ] **Step 5: Run focused tests**

Run: `cd backend && pytest tests/test_outbound_messages.py tests/test_reviews.py tests/test_signature.py -q`

Expected: all pass.

### Task 3: Review SMTP Send, Resend, Read-Back, and Public Throttling

**Files:**
- Modify: `backend/app/services/reviews.py`
- Modify: `backend/app/routers/reviews_internal.py`
- Modify: `backend/app/routers/reviews_public.py`
- Modify: `backend/tests/test_review_lifecycle_integration.py`

**Interfaces:**
- Produces: review send response containing request, safe delivery, and Copy
  Link; `resend_review_email(review_id, ...)` reuses request/token.
- Adds: `POST /api/contracts/{contract_id}/reviews/{review_id}/resend`.

- [ ] **Step 1: Write failing persisted review-email tests**

Assert Transaction A survives SMTP failure; failed is never sent; retry changes
delivery to sent without a second review request or stage transition; same link
is reused; rate-limit errors are deterministic; sent status is read back; no
token appears in activities; localhost URL validation maps safely.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/test_review_lifecycle_integration.py -q`

Expected: new cases fail because delivery/resend are absent.

- [ ] **Step 3: Implement service/router orchestration**

Keep `create_review_request` authoritative. Commit request plus pending attempt,
perform SMTP, record result, and return safe deterministic responses. Add resend
cooldown and reuse. Add public review throttling using existing rate limiter.

- [ ] **Step 4: Run review regressions**

Run: `cd backend && pytest tests/test_reviews.py tests/test_review_lifecycle_integration.py tests/test_negotiation_lifecycle_integration.py -q`

Expected: all pass.

### Task 4: Canonical Signature Lifecycle and SMTP Invitations

**Files:**
- Modify: `backend/app/services/signature.py`
- Modify: `backend/app/services/versions.py`
- Modify: `backend/app/routers/signature.py`
- Modify: `backend/app/routers/signature_public.py`
- Create: `backend/tests/test_signature_lifecycle_integration.py`

**Interfaces:**
- Produces deterministic `SignatureError(status_code, code)`.
- Adds explicit send/retry delivery, expiry processing, reasoned cancellation,
  and `activate_contract(...)`.
- Adds: `POST /api/signature-requests/{request_id}/activate`.

- [ ] **Step 1: Write persisted signature journey tests**

Cover eligibility/current approved version/completed approval/unresolved
negotiation/active request; draft creation leaves `ready_to_sign`; only signer
one is emailed; failed delivery preserves request/link; retry reuses link;
first sign transitions to `partially_signed` and queues/sends signer two;
out-of-order/duplicate/stale actions have no mutations; final sign creates one
artifact/certificate, marks version signed, and leaves contract `signed`;
manual activation transitions to `active`; decline→`internal_review`;
cancel/expiry→`ready_to_sign`; atomic artifact failure rolls back completion.

- [ ] **Step 2: Verify RED**

Run: `cd backend && pytest tests/test_signature_lifecycle_integration.py -q`

Expected: failures exposing legacy commits/stages and missing delivery.

- [ ] **Step 3: Replace legacy stage helpers**

Use row locks and `LifecycleService.transition()` events only. Remove internal
commits from signature helpers. Change `mark_version_signed(..., commit=False)`
so final signing is one caller-owned database transaction. Do not auto-activate.

- [ ] **Step 4: Wire invitation transaction pattern**

Creation persists no mail. Send creates pending attempt for current eligible
signer, commits, sends, and records result. Intermediate signing commits next
pending invitation with signing mutation, then sends after commit. Retry reuses
the signer token and request.

- [ ] **Step 5: Implement deterministic router errors and activation**

Map the requested 403/404/409/422/502/503 codes. Cancellation and activation
require reason/evidence and authorized demo roles.

- [ ] **Step 6: Run signature and lifecycle regressions**

Run: `cd backend && pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_approval_lifecycle_integration.py -q`

Expected: all pass.

### Task 5: Minimal Bilingual Review and Signature UI

**Files:**
- Modify: `frontend/components/SendForReviewDialog.tsx`
- Modify: `frontend/components/ReviewHistoryPanel.tsx`
- Modify: `frontend/components/SignaturePanel.tsx`
- Modify: `frontend/app/sign/[token]/page.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/i18n.tsx`
- Modify/Create: focused `*.vitest.ts(x)` tests beside existing frontend tests

**Interfaces:**
- Consumes safe delivery payloads and resend/activation endpoints.
- Exposes delivery badge, attempts/timestamps, Retry, Copy Link, and manual
  activation without changing existing page structure.

- [ ] **Step 1: Write failing component/API tests**

Assert failed delivery does not render notified success; Copy Link remains
available; Retry calls resend; signature signer deliveries render; activation
requires a reason; bilingual prototype disclosure is always present.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test`

- [ ] **Step 3: Implement minimal UI/API/types/i18n**

Preserve existing layout and RTL/LTR. Use deterministic API error codes. Keep
links out of console logging.

- [ ] **Step 4: Run frontend tests and TypeScript**

Run: `cd frontend && npm test && npx tsc --noEmit`

Expected: all pass.

### Task 6: Local SMTP and Golden-Path Smokes

**Files:**
- Create: `scripts/golden_path_smoke.py`
- Create: `backend/tests/test_smtp_local_integration.py`
- Update: `.gitignore` if smoke artifacts need exclusion

**Interfaces:**
- Uses live API/database and a local capture SMTP server with synthetic data.

- [ ] **Step 1: Write local SMTP integration test**

Start a local stdlib SMTP capture server, send review/signature messages, assert
both MIME alternatives and portal URL shapes, and stop/clean in `finally`.

- [ ] **Step 2: Implement golden-path smoke**

Upload/create synthetic contract, use deterministic existing setup where AI is
provider-dependent, transition through client review changes, negotiation
agreement, ordered approval, two ordered signers, signed, and manual active.
Verify summaries, bucket, lineage, events, outbound rows, exact row counts, and
stale mutation rejection. Delete DB rows and files in `finally`, then verify
zero residue.

- [ ] **Step 3: Run both smokes**

Run:

```bash
cd backend && pytest tests/test_smtp_local_integration.py -q
cd .. && python scripts/golden_path_smoke.py
```

Expected: all checks pass and cleanup reports zero residue.

### Task 7: Release Verification and Demo Report

**Files:**
- Create: `docs/demo-readiness-final.md`

- [ ] **Step 1: Run focused backend suites**

Run SMTP, review, negotiation, approval, signature, lifecycle, version, and
extraction test files.

- [ ] **Step 2: Run full backend suite**

Run: `cd backend && pytest tests -q`

- [ ] **Step 3: Run frontend suite, TypeScript, and production build**

Run: `cd frontend && npm test && npx tsc --noEmit && npm run build`

- [ ] **Step 4: Run SMTP and golden-path smokes**

Run local SMTP smoke and golden-path smoke; verify API/database read-back and
zero residue.

- [ ] **Step 5: Perform browser/manual smoke where available**

Open internal review/signature and public review/sign pages. Verify bilingual
copy, failure/success states, Copy/Retry, ordered signing, artifacts, activation,
and no browser console errors. Record any unexecuted item honestly.

- [ ] **Step 6: Write final demo report**

Include exact path, evidence, SMTP status/setup, HTTPS/tunnel requirement,
prototype disclosure, deferred scope, startup commands, 5–7 minute script,
recovery actions, test/build results, limitations, real-inbox checklist, and:

`feat(release): complete SMTP review, signature lifecycle, and golden path`
