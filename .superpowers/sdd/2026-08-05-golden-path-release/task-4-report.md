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
