# Task 5 — Minimal Bilingual Review and Signature UI

## Delivered

- Review send no longer claims a generic success: `SendForReviewDialog` reads the
  persisted `delivery.status` returned by the (pre-existing) send/resend endpoints and
  reports a distinct bilingual "link created, email sent" vs. "link created, email
  failed — retry or copy the link" outcome via toast and inline panel state. A failed
  delivery still keeps the copy-link action available.
- `ReviewHistoryPanel` now renders each review's persisted `DeliveryStatusBadge`,
  attempt count, and sent/failed timestamp (with `safe_error_code` when failed) after a
  plain data refresh — no action required to see current state. A `Retry Email` button
  calls the existing `resend` service through a new `resendContractReview` API
  function and reports the real outcome (sent vs. failed) rather than an optimistic
  success; it is only offered when the row is `actionable`. `Copy Link` is offered
  whenever a `review_link` is present, independent of delivery outcome.
- `SignaturePanel`'s signer rows now show the same persisted delivery badge/attempts/
  timestamps per signer, sourced from a new backend `delivery` field per signer. Both
  `Resend` and `Copy Signing Link` are gated on a new backend-computed `eligible` flag
  (currently `invited`/`opened` signer status and a non-terminal request), so a signer
  who has not yet been invited exposes no action at all, and a signed/declined signer
  loses it once their turn passes. Resend and the bulk "send" action report a real
  failed/sent toast based on delivery outcome instead of an unconditional "sent".
- The public `/sign/[token]` page now always renders a fixed bilingual
  "Demo electronic signature / توقيع إلكتروني تجريبي — ... not a certified legally
  binding e-signature provider" disclosure line, on every branch: loading, error,
  declined, completed (read-only), waiting-for-prior-signer, and the active signing
  form. Generic silent/blank failures are gone: load failures, submit failures, and
  decline failures all surface the deterministic backend error code (via
  `apiErrorCode`) through a retry-capable error view or a toast, never a bare
  `common.error` string.
- Extended `frontend/lib/types.ts` with `DeliveryStatus`/`DeliveryRow`, and threaded
  `delivery`/`delivery_history` onto `ReviewRequestRow`/`SendReviewResponse`, and
  `delivery`/`eligible`/`signer_link` onto `SignatureSignerRow`, matching the backend's
  `serialize_delivery`/`serialize_signer_internal` shapes exactly.
- Added `resendContractReview` to `frontend/lib/api.ts` (targets the pre-existing
  `/api/contracts/{id}/reviews/{id}/resend` route) and widened
  `resendSignatureSigner`'s return type to include the `delivery` field the backend
  already returns.
- Added ~12 new bilingual i18n keys (`review.send.successSent/successFailed`,
  `review.retryEmail/retrySuccess/retryFailed`, `delivery.status.*`,
  `delivery.attempts/sentAt/failedAt/errorCode`, `signature.deliverySent/
  deliveryFailed/demoDisclosure/errorWithCode`, `common.copied`) in both `ar` and `en`
  dictionaries, and removed the now-dead `review.send.success` key it replaced.
- Backend: `app/services/signature.py` now looks up each signer's `latest_delivery`
  (message type `signature_invitation`) and computes `eligible` using the same
  status/terminal-request rule `resend_signer` already enforces, exposing
  `delivery`/`eligible`/`signer_link` per signer from both `create_request` and
  `serialize_request` (i.e. the GET bundle used after every refresh). A non-eligible
  signer's `signer_link` and `delivery` are `None`/absent — no token leaks for a
  waiting signer.

## Files changed

- `frontend/components/SendForReviewDialog.tsx`
- `frontend/components/ReviewHistoryPanel.tsx`
- `frontend/components/SignaturePanel.tsx`
- `frontend/app/sign/[token]/page.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/lib/i18n.tsx`
- `backend/app/services/signature.py`
- New tests: `frontend/components/SendForReviewDialog.vitest.tsx`,
  `frontend/components/ReviewHistoryPanel.vitest.tsx`,
  `frontend/app/sign/[token]/page.vitest.tsx`
- Extended test: `frontend/components/SignaturePanel.vitest.tsx`,
  `backend/tests/test_signature_lifecycle_integration.py`

## TDD evidence

### Backend RED

Added `test_bundle_exposes_persisted_signer_delivery_only_for_eligible_signer` to
`test_signature_lifecycle_integration.py`, then stashed only the
`app/services/signature.py` implementation change (keeping the new test):

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py::test_bundle_exposes_persisted_signer_delivery_only_for_eligible_signer -q -p no:warnings
```

```text
>       assert first["eligible"] is True
E       KeyError: 'eligible'
1 failed in 9.02s
```

### Backend GREEN

Implementation restored:

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py::test_bundle_exposes_persisted_signer_delivery_only_for_eligible_signer -q -p no:warnings
1 passed in 12.69s
```

Required regression:

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_outbound_messages.py tests/test_reviews.py -q -p no:warnings
79 passed, 1 error in 144.78s
```

The one error (`test_final_artifact_failure_rolls_back_completion_and_removes_orphan_signature`)
is `sqlalchemy.exc.OperationalError: ... could not receive data from server: Operation
timed out` against the remote Postgres instance — a transient network flake, not a
regression: that test file's own logic was untouched by Task 5 except for the new test
above, and the test passes cleanly in isolation:

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py::test_final_artifact_failure_rolls_back_completion_and_removes_orphan_signature -q -p no:warnings
1 passed in 12.36s
```

Also reran the originally-reported full backend suite as a second confirmation:

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_outbound_messages.py -q -p no:warnings
39 passed in 123.23s
```

### Frontend RED

All four Task 5 vitest files (three new, one extended) were written first. RED was
captured by stashing only the seven implementation files
(`SendForReviewDialog.tsx`, `ReviewHistoryPanel.tsx`, `SignaturePanel.tsx`,
`app/sign/[token]/page.tsx`, `lib/api.ts`, `lib/i18n.tsx`, `lib/types.ts`) while keeping
every test file (including the pre-existing Task 4 `SignaturePanel.vitest.tsx` cases):

```text
cd frontend && npx vitest run --reporter=basic
```

```text
 ✓ lib/pipeline.vitest.ts (11 tests)
 ✓ components/contract/AiSummaryPanel.vitest.tsx (1 test)
 ✓ components/SourceViewer.vitest.tsx (4 tests)
 ✓ components/SourceViewer.ssr.vitest.ts (2 tests)
 ✓ lib/api.vitest.ts (2 tests)
   × Public sign page — deterministic errors and disclosure (6 failing)
   × SendForReviewDialog delivery honesty (3 failing)
   × ReviewHistoryPanel persisted delivery (5 failing, 1 passing pre-existing-shape case)
   × SignaturePanel signer delivery and eligibility (5 failing)
   ✓ SignaturePanel artifacts/activation/cancellation (9 passing — untouched Task 4 cases)

 Test Files  4 failed | 5 passed (9)
      Tests  19 failed | 30 passed (49)
```

The 19 failures are exactly the new Task 5 assertions (delivery honesty, persisted
delivery/eligibility display, retry/copy actions, deterministic public-page error
codes, and the always-visible disclosure); every pre-existing Task 4 test kept passing
unmodified, confirming no rewrite of existing coverage.

### Frontend GREEN

Implementation restored:

```text
cd frontend && npx vitest run --reporter=basic
 ✓ lib/pipeline.vitest.ts (11 tests)
 ✓ components/contract/AiSummaryPanel.vitest.tsx (1 test)
 ✓ components/SourceViewer.vitest.tsx (4 tests)
 ✓ app/sign/[token]/page.vitest.tsx (6 tests)
 ✓ components/ReviewHistoryPanel.vitest.tsx (6 tests)
 ✓ components/SendForReviewDialog.vitest.tsx (3 tests)
 ✓ components/SignaturePanel.vitest.tsx (14 tests)
 ✓ components/SourceViewer.ssr.vitest.ts (2 tests)
 ✓ lib/api.vitest.ts (2 tests)

 Test Files  9 passed (9)
      Tests  49 passed (49)
```

### Type check and production build

```text
cd frontend && npx tsc --noEmit
(exit 0, no output)

cd frontend && npm run build
 ✓ Compiled successfully
 ✓ Generating static pages (19/19)
```

## Self-review

- Grepped every changed frontend/backend file for `console.log|error|warn|info|debug`
  and `logger.`/`logging.` — none were added; no signing/review token or link is ever
  logged. `signer_link`/`review_link`/raw tokens only ever reach the DOM via React
  state and `navigator.clipboard.writeText`.
- Verified the new `eligible` gate on the backend reuses the exact same status/terminal
  check `resend_signer` (the mutating endpoint) already enforces, so the UI's
  Retry/Copy-Link visibility can never diverge from what the server would actually
  accept — a client can't be shown an action the server will reject with
  `not_active_signer`.
- Verified a non-eligible signer's `signer_link` is `None` server-side (not merely
  hidden client-side): the new backend test asserts the *second* signer's raw token
  never appears anywhere in the bundle response while `waiting`.
- Confirmed `resendContractReview` and the widened `resendSignatureSigner` return type
  target/consume endpoints (`/reviews/{id}/resend`, `/resend/{signerId}`) and response
  shapes (`delivery`) that already existed pre-Task-5 (Task 4's `resend_review_email`/
  `resend_signer` services); Task 5 only added frontend consumption of fields the
  backend was already returning, except for the new per-signer bundle exposure.
- Removed the now-orphaned `review.send.success` i18n key (both languages) after
  replacing its only call site with `successSent`/`successFailed`, so no dead
  translation entries were left behind.
- Confirmed every new/changed user-facing string has both an `ar` and an `en` entry
  and reused existing RTL-safe layout primitives (`flex flex-wrap`, `Badge`, `Button`)
  rather than any new fixed-direction styling.
- Confirmed the `PrototypeDisclosure` bilingual text is a single fixed string (not
  translated per-locale) since the brief calls for a fixed bilingual disclosure, and
  it is rendered before the early `return` in every branch of `SignPage`, including
  the loading and error states.
- `npm run lint` / `next lint` is not usable in this repository (no committed ESLint
  config; `next lint` drops into an interactive setup wizard non-interactively).
  Verification relied on `tsc --noEmit`, `vitest`, and `next build`, consistent with
  Task 4's documented approach.

## Concerns

- The pre-existing flaky remote-Postgres timeout
  (`test_final_artifact_failure_rolls_back_completion_and_removes_orphan_signature`)
  reproduced again during this task's full-suite run; it is unrelated to Task 5 (the
  test's own scenario was not touched) and passes reliably in isolation, but the
  remote DB's occasional connection drops remain an environment concern worth flagging
  to whoever owns CI infrastructure.
- `eligible`/`signer_link` are computed per signer on every `serialize_request` call
  (one extra `latest_delivery` query per signer). This is consistent with the existing
  N+1-per-signer pattern already used elsewhere in `signature.py` (e.g. resend cooldown
  checks) and bundles are small (few signers), so it was not optimized further to keep
  the change minimal.
- Attempt-count and timestamps are truncated client-side with `.slice(0, 19)` (drops
  timezone offset) purely for compact display; the full ISO value is still available
  in `DeliveryRow` if a future task needs exact-offset rendering.

## Commit

```text
7d840f7 feat(review-signature): persisted delivery status, retry/copy actions, and deterministic public errors
14 files changed, 1294 insertions(+), 40 deletions(-)
```
