# Task 4 — Canonical Signature Lifecycle and SMTP Invitations

## Delivered

- Added PostgreSQL-backed signature lifecycle integration coverage.
- Replaced signature-service lifecycle mutations with `LifecycleService.transition()`;
  no legacy stage helper or direct stage assignment remains in the signature service.
- Draft request creation now validates the canonical eligible state and completed approval,
  persists signers/request/version references in one transaction, remains
  `ready_to_sign`, and creates no outbound mail.
- Explicit send and retry persist an eligible signer's outbound attempt before crossing
  SMTP; delivery result is written in the follow-up transaction. Tokens remain absent
  from events and outbound rows.
- Partial signing commits signer evidence, the lifecycle transition, next signer
  invitation, and pending delivery together; SMTP follows that commit. Final signing
  creates artifacts/certificate, marks the version signed with `commit=False`, and
  leaves the contract `signed`.
- Added reasoned cancellation, expiry lifecycle processing, decline triage to
  `internal_review`, stale/current-version guards, deterministic `SignatureError`
  router mapping, and authorized manual activation requiring reason/evidence.
- Compensating deletion removes known signature artifacts when a completion transaction
  fails.

## TDD evidence

### RED

Command:

```text
cd backend && pytest tests/test_signature_lifecycle_integration.py -q
```

Observed expected pre-implementation failure:

```text
ImportError: cannot import name 'SignatureError' from 'app.services.signature'
```

This proved the requested deterministic service error contract did not exist.

### GREEN

Command:

```text
cd backend && pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py -q
```

Output:

```text
19 passed, 3 skipped, 7 warnings
```

Required regression command:

```text
cd backend && pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_approval_lifecycle_integration.py -q
```

Output:

```text
88 passed, 3 skipped, 7 warnings in 193.94s
```

## Transaction decisions

1. Request creation: contract/version/approval eligibility locks, request, signer rows,
   lifecycle/audit events, and original-artifact reference commit as Transaction A.
2. Send/retry: request/signer/lifecycle changes plus one pending `OutboundMessage` commit
   before SMTP. Delivery marks `sending` and then `sent`/`failed` in Transaction B.
3. Partial signature: signer evidence, request status, lifecycle events, next signer,
   and that signer's pending attempt commit together; next SMTP send occurs afterward.
4. Final signature: signer evidence, signed artifact/certificate references, request
   completion, version status, and lifecycle/audit events commit together. Known file
   keys are deleted if that DB transaction fails.

## Self-review

- Confirmed `signature.py` contains no `set_stage`, `transition_stage`, or direct
  `contract.stage` assignment.
- Confirmed all lifecycle-changing actions lock contract/request/current version and
  reject stale request versions before mutation.
- Preserved only three legacy unit-test skips whose mocked legacy helpers conflict with
  the canonical persistence path; equivalent persisted behavior is covered by the new
  integration suite.

## Concern

The existing project test configuration emits seven third-party deprecation warnings
(FastAPI TestClient, Hijri converter, and PyMuPDF); they predate Task 4 and do not
affect the passing lifecycle assertions.

## Fix round 1

### Findings addressed

- Reworked public signer-open into the same locked request/contract/current-version
  transaction model used by signing. It now rejects stale, expired, closed, and
  out-of-order requests deterministically and persists `signature_viewed`.
- Protected and public routers now map `SignatureError`, `LifecycleError`, and
  `EmailDeliveryError` to their declared HTTP status and safe payload.
- Failed delivery attempts bypass resend cooldown, so a failed invitation is immediately
  retryable without altering the durable request/link.
- Normalized signature creation stage checks through `normalize_stage`; read-only
  `can_create` now evaluates canonical stage, current approved version, approved
  workflow, unresolved negotiations, and active requests.
- Added cancellation-reason submission and activation client action to the frontend.
- Added persisted coverage for open/viewed, idempotent expiry, and authorized manual
  activation (missing evidence, wrong role, valid signed-to-active flow).

### Strict TDD evidence

RED:

```text
pytest tests/test_outbound_messages.py::test_failed_delivery_does_not_start_resend_cooldown -q
FAILED: EmailDeliveryError: email_resend_cooldown

pytest tests/test_signature_lifecycle_integration.py::test_open_is_locked_current_and_emits_viewed_transition ... -q
FAILED: expected signature_viewed activity event
```

GREEN focused:

```text
3 passed, 7 warnings
```

Full backend coverage:

```text
pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_approval_lifecycle_integration.py tests/test_outbound_messages.py -q
101 passed, 3 skipped, 7 warnings in 221.50s
```

Frontend:

```text
npm test
5 files passed, 20 tests passed
```

### Self-review

- No direct stage mutation or legacy stage helper was reintroduced in the signature
  service.
- Open, sign, decline, resend, cancellation, expiry, and activation all use locked
  contract/request/current-version paths before lifecycle mutation.
- Existing skipped signature unit tests are legacy mock-only tests superseded by
  persisted integration coverage; they remain explicitly marked while the canonical
  behavior is exercised through real PostgreSQL/API paths.

## Fix round 2

- Added the canonical `partially_signed + signature_viewed → partially_signed` rule
  and proved signer two can open once after signer one signs, with no duplicate audit.
- Removed obsolete skipped mock-only signature tests; the Task 4 signature suite now
  has no skipped tests.
- Added raw-token persistence assertions across activity/signature event metadata and
  outbound records after the full signing journey.
- Creation now blocks unresolved negotiations; read-only eligibility returns false for
  unknown stages instead of raising.
- UI cancellation and activation now use bilingual prompts, surface failures through a
  toast, require reason/evidence, and hide activation after a successful action.

### TDD evidence

RED:

```text
pytest tests/test_signature_lifecycle_integration.py::test_second_signer_opens_after_partial_signature_once -q
FAILED: expected 200, received 409
```

GREEN:

```text
pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_outbound_messages.py -q
67 passed, 7 warnings

npm test && npx tsc --noEmit
20 frontend tests passed; TypeScript passed
```

## Fix round 3

- Activation API coverage now asserts service/router error payloads for whitespace
  reason/evidence and unauthorized roles, and verifies exactly one activation event.
- Replaced browser prompts with inline cancellation and activation fields. Activation is
  restricted to completed requests on a `signed` contract stage and hides locally after
  success.
- Added persisted current-version unresolved-negotiation creation blocking coverage.

### TDD evidence

RED:

```text
pytest tests/test_signature_lifecycle_integration.py::test_manual_activation_requires_authorized_evidence_and_moves_signed_contract -q
FAILED: expected one contract_activated event, found two
```

GREEN:

```text
pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_approval_lifecycle_integration.py tests/test_outbound_messages.py -q
103 passed, 7 warnings

npx tsc --noEmit && npm test
TypeScript passed; 20 frontend tests passed
```

## Fix round 4

### Findings addressed

- **Artifact regression (critical).** Signed-PDF and certificate downloads were nested inside
  the `contractStage === "signed"` branch, so activating a contract removed the executed
  documents from the panel. Downloads are now gated on the completed request and the
  presence of each artifact reference, so they survive `signed`, `active`, and every later
  stage. Only the activation form stays gated to a `signed`, not-yet-activated contract.
- **Activation audit privacy.** `activate_contract` passed the raw operator `reason` and
  `evidence` into `LifecycleService.transition()`, which copies transition metadata into the
  persisted `contract_activated` activity row. Activation now records
  `activation_ready`/`reason_present`/`evidence_present` plus keyed, truncated
  `reason_fingerprint`/`evidence_fingerprint` values. Both inputs remain mandatory at the
  service boundary; only the raw text is dropped. Fingerprints are emitted solely when the
  deployment secret is configured, because a plain digest of short free text is recoverable.
- **Missing activation API cases.** Added persisted `activation_not_ready` and
  `workflow_stale` 409 cases that assert the exact error code, unchanged contract stage,
  unchanged request status, and a byte-identical activity event list.
- **Lifecycle refresh.** `SignaturePanel` now accepts
  `onLifecycleChange?: () => void | Promise<void>` and the contract page passes its `load`
  callback, matching `ApprovalsPanel`. Successful send, cancel, and activation await the
  callback so the stage badge and stepper refresh; the refreshed `active` stage removes the
  activation form.
- **UI quality.** Success toasts for send/cancel/activate, deterministic `apiErrorCode`
  error surfacing on every action including downloads and resend, distinct bilingual
  validation strings for a missing activation reason, missing activation evidence, and a
  missing cancellation reason, styled bordered fields inside labelled cards, and per-action
  `loading`/`disabled` state that blocks concurrent submissions.

### Strict TDD evidence

#### Backend RED

Command:

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py -q -k "activation_never_persists or activation_not_ready or stale_request_returns_workflow_stale" -p no:warnings
```

Output:

```text
>           assert raw_reason not in payload
E           assert 'Counterpart...yla Al-Harbi' not in "{'to': 'act...eady': True}"
E
E             'Counterparty count... CFO Layla Al-Harbi' is contained here:
E               reason': 'Counterparty countersigned on 2026-04-01 per CFO Layla Al-Harbi', 'evidence': 'Scanned wet-ink page stored at vault://legal/482-secret', 'request_id': '6846b410-1820-46f2-9574-07dc05555bb7', 'version_id': 'de66f236-0049-4fe2-aa4a-085ef00f402b', 'current_version': True, 'activation_ready': True}

tests/test_signature_lifecycle_integration.py:541: AssertionError
=========================== short test summary info ============================
FAILED tests/test_signature_lifecycle_integration.py::test_activation_never_persists_raw_reason_or_evidence
1 failed, 2 passed, 14 deselected in 10.28s
```

The two new 409 cases passed on first run: they lock in already-correct guard behavior that
had no persisted API-level coverage, so only the metadata leak was genuinely red.

#### Backend GREEN

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py -q -k "activation_never_persists or activation_not_ready or stale_request_returns_workflow_stale" -p no:warnings
3 passed, 14 deselected in 10.47s
```

Required regression command:

```text
cd backend && python -m pytest tests/test_signature_lifecycle_integration.py tests/test_signature.py tests/test_lifecycle.py tests/test_approval_lifecycle_integration.py tests/test_outbound_messages.py -q -p no:warnings
106 passed in 249.93s (0:04:09)
```

#### Frontend RED

`frontend/components/SignaturePanel.vitest.tsx` is collected by the existing
`include: ["**/*.vitest.tsx", "**/*.vitest.ts"]` config. RED was captured by stashing only
the three implementation files (`SignaturePanel.tsx`, `i18n.tsx`, `contracts/[id]/page.tsx`)
and keeping the new test:

```text
cd frontend && npx vitest run components/SignaturePanel.vitest.tsx --reporter=basic
  × keeps signed artifact downloads on an active contract while hiding the activation form
    → Unable to find an element with the text: تنزيل العقد الموقّع.
  × keeps signed artifact downloads on a stage that follows activation
    → Unable to find an element with the text: تنزيل العقد الموقّع.
  ✓ offers artifact downloads and the activation form on a signed contract
  × downloads the signed contract and the certificate for the completed request
    → Unable to find an element with the text: تنزيل العقد الموقّع.
  × blocks activation and reports each missing field distinctly
    → expected "spy" to be called with arguments: [ 'سبب التفعيل مطلوب قبل تفعيل العقد' ]
  × sends the trimmed reason and evidence, refreshes the lifecycle, and confirms success
    → expected "spy" to be called at least once
  × surfaces the backend error code and leaves the lifecycle untouched
    → expected "spy" to be called with arguments: [ 'activation_not_ready' ]
  × hides the activation form once the reloaded contract is active
    → Unable to find an element with the text: تنزيل العقد الموقّع.
  × requires a reason, then submits it and refreshes the lifecycle
    → expected "spy" to be called with arguments: [ 'سبب الإلغاء مطلوب قبل إلغاء الطلب' ]

 Test Files  1 failed (1)
      Tests  8 failed | 1 passed (9)
```

The one passing case is the `signed`-stage baseline, which the previous round already
satisfied; the eight failures are exactly the round 4 findings.

#### Frontend GREEN

```text
cd frontend && npx vitest run --reporter=basic
 ✓ components/SourceViewer.ssr.vitest.ts (2 tests) 263ms
 ✓ lib/pipeline.vitest.ts (11 tests) 5ms
 ✓ lib/api.vitest.ts (2 tests) 2ms
 ✓ components/contract/AiSummaryPanel.vitest.tsx (1 test) 29ms
 ✓ components/SourceViewer.vitest.tsx (4 tests) 49ms
 ✓ components/SignaturePanel.vitest.tsx (9 tests) 99ms

 Test Files  6 passed (6)
      Tests  29 passed (29)
```

TypeScript and the production Next.js build:

```text
cd frontend && npx tsc --noEmit
TSC_OK

cd frontend && npm run build
 ✓ Compiled successfully
 ✓ Generating static pages (19/19)
```

### Self-review

- Grepped `signature.py` for transition metadata carrying `reason`, `evidence`, `token`,
  `signature_value`, or `email`. The only remaining raw value is the signer-authored
  decline reason, which the lifecycle rule requires as a mandatory field and which the
  product already exposes as `decline_reason`.
- No raw tokens, reasons, or evidence are logged client side: every error path surfaces
  only the deterministic backend error code through `apiErrorCode`.
- Activation fingerprints are keyed HMAC-SHA256 truncated to 16 hex characters, so they
  correlate repeated attestations without being reversible from the audit trail.
- Reset the local `activated` guard on `contractId` change so the flag cannot leak across
  contracts when the panel instance is reused.
- The new frontend test registers `afterEach(cleanup)` explicitly, because the project
  vitest config does not enable `globals`, so Testing Library auto-cleanup is not installed.
  Without it, leaked DOM from a previous render produces false duplicate-element failures.

### Concerns

- The activation fingerprint reuses `PORTAL_TOKEN_SECRET` as its HMAC key, since that is
  the only deployment secret currently exposed by `get_email_delivery_settings()`. A
  dedicated audit-fingerprint secret would be cleaner if audit hashing spreads to other
  workflows.
- Raw signer decline reasons and approval comments still persist in activity metadata by
  design. If the privacy rule is meant to cover all operator free text, that is a
  separate lifecycle-wide change spanning the approval and review services.
- `npm run lint` is not usable in this repository: `next lint` has no committed ESLint
  configuration and drops into an interactive setup prompt. Verification relied on
  `tsc --noEmit`, `vitest`, and `next build` instead.
