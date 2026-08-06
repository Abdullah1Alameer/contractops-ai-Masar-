# Contract Lifecycle — Final Stage Audit

**Date:** 2026-08-06
**Branch:** `feature/timeline-payment-tracker`
**Status:** Primary bug fixed at root cause. Full stage-by-stage audit complete. No dead ends remain in the implemented stage set (`draft` → `active`, plus `rejected`/`cancelled`); `completed`/`terminated` remain intentionally out of scope (see §6).

---

## 1. Root cause of new contracts entering `negotiation`

Reproduced exactly as specified (upload → extract → read back every field) against the live API and database — see §5.2 for the full trace and raw output.

**Before this fix**, a freshly uploaded contract read back as:

```
stage: negotiation   status: processing → ready
review_status: none   negotiation_status: none
approval_status: none   signature_status: none
current version status: ready
activity events: [extraction_completed, intelligence_rebuilt]
```

**The mechanism, traced precisely:**

`backend/app/models.py`:
```python
stage = Column(Text, nullable=False, default="negotiation")
```

`POST /api/contracts` (`backend/app/routers/contracts.py::upload_contract`, the frozen F1 endpoint) constructs `Contract(id=..., title=..., type=..., file_url=..., status="processing")` **without ever setting `stage`**. SQLAlchemy applies the Column's Python-side `default=` at INSERT time, so every new contract silently received `stage="negotiation"` on creation — before any negotiation, review, or any lifecycle event had occurred.

The database column itself carried a matching default:
```sql
-- database/migrations/011_approval_workflow.sql
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT 'negotiation';
```

This default was set when the `stage` column was first added, **before the canonical lifecycle engine (`backend/app/services/lifecycle.py`) existed** — at that point there was no `draft`/`ready_for_client` concept yet, and `'negotiation'` served as a generic "needs attention" catch-all for backfilling pre-existing rows. Nothing was ever updated when the canonical `ContractStage` enum (`draft`, `ready_for_client`, `client_review`, `negotiation`, …) was introduced later.

**Every other place traced and cleared** (extraction pipeline, dashboard/serialization, legacy stage aliases, seed/demo logic, version creation, frontend fallbacks) does **not** set or assume `stage` — they all read it as given. The two defaults above were the sole source.

### Fix (smallest safe change, no backfill)

1. `backend/app/models.py` — `Contract.stage` Python default changed `"negotiation" → "draft"`.
2. `database/migrations/019_contract_stage_default_draft.sql` — `ALTER TABLE contracts ALTER COLUMN stage SET DEFAULT 'draft'`.

Both are **default-only** changes. No existing row's `stage` value is touched, no backfill, fully additive and reversible (`ALTER COLUMN ... SET DEFAULT 'negotiation'` would revert it). Applied via `python database/migrate.py` (migration `019` tracked in `_migrations`, applied cleanly, all 18 prior migrations already applied — see §5.1).

**Verified after the fix** (same reproduction, live trace):
```
upload  -> status=201 stage=draft
extract -> status=200 stage=draft   (extraction does NOT move stage)
```

---

## 2. `CONTRACT_READY_FOR_CLIENT` — existed but was never called

`backend/app/services/lifecycle.py` already defined the rule:
```python
_rule(ContractStage.DRAFT, LifecycleEvent.CONTRACT_READY_FOR_CLIENT,
      ContractStage.READY_FOR_CLIENT, validator=_validate_ready)
```
but grep across every router and service confirmed **zero callers**. Implemented the missing integration:

- **New service:** `backend/app/services/contract_lifecycle.py::mark_ready_for_client()`
  Validates, in order: current version exists (`409 no_current_version`); no active review on that version (`409 review_already_active`); no unresolved negotiation (`409 unresolved_negotiations`); then calls `LifecycleService.transition(contract, CONTRACT_READY_FOR_CLIENT, actor, metadata={contract_ready, supported, version_id})` — the rule's own `_validate_ready` validator raises `409 contract_not_ready` if extraction isn't finished or the document is unsupported. One `db.commit()`, `db.rollback()` on any exception. Activity event (`contract_ready_for_client`) is written from `transition.activity_metadata` only if `transition.changed` — identical pattern to every other domain service (`signature.py::_transition`, `negotiation.py::_transition_and_log`).
- **New endpoint:** `POST /api/contracts/{contract_id}/mark-ready-for-client` (`backend/app/routers/contract_lifecycle.py`, registered in `main.py`). Protected (bearer + demo role), so "authorized internal role only" is satisfied the same way every other internal action in this codebase is (no additional per-role restriction — matches how "Start Approval" isn't further role-gated either).
- **New button:** `ContractHeader.tsx` — **"Mark Ready for Client Review" / "تجهيز العقد لمراجعة العميل"**, visible only when `stage === "draft" && status ∈ {ready, needs_review}`. Calls `markContractReadyForClient()`, refreshes contract data on success, surfaces deterministic errors via toast.

No direct `contract.stage = ...` assignment anywhere in the new code — confirmed by inspection and by the persisted tests in §4.

---

## 3. Stage table

| Stage | Entry Event | UI Action | Endpoint | Role | External Dependency | Next Stage | Verified |
|---|---|---|---|---|---|---|---|
| `draft` | Upload (`contract_created`, implicit — no event fired) | **Mark Ready for Client Review** | `POST /contracts/{id}/mark-ready-for-client` | any internal | No | `ready_for_client` | ✅ |
| `ready_for_client` | `contract_ready_for_client` | **Send for review** (Create Review Link) | `POST /contracts/{id}/review/send` | any internal | No | `client_review` | ✅ |
| `client_review` | `review_sent` | Client: Approve / Reject / Request changes. Internal: Copy Link / Retry Email (no stage jump) | `POST /review/{token}/approve\|reject\|request-changes` | client (public token) | **Yes** | `internal_review` / `rejected` / `negotiation` | ✅ |
| `negotiation` | `review_changes_requested` or `approval_changes_requested` | Analyze → Approve wording → Send to client; while waiting: Copy client link / **Record Agreement Reached** / Abandon | `POST /negotiation/analyze`, `PATCH /negotiations/{id}`, `POST /negotiations/{id}/send`, `POST /negotiations/{id}/record-agreement`, `POST /negotiations/{id}/abandon` | legal (send); legal/executive (record-agreement override) | Yes, unless overridden | `internal_review` (all resolved) / `rejected` / `cancelled` | ✅ |
| `internal_review` | `negotiation_accepted` or `review_approved` | Start Approval → ordered Approve/Reject/Request changes per role | `POST /contracts/{id}/approvals/start`, `PATCH /approvals/{step_id}` | business_owner → legal → finance → executive, in order | No | `ready_to_sign` / `negotiation` / `rejected` | ✅ |
| `ready_to_sign` | `approval_workflow_completed` / `contract_ready_to_sign` | Create Signature Request → Send | `POST /contracts/{id}/signature-request`, `POST /signature-requests/{id}/send` | any internal | Yes (signers, once sent) | `partially_signed` | ✅ |
| `partially_signed` | `signer_signed` (not all) | Signer signs (public); internal Retry/Copy Link/Cancel | `POST /public/sign/{token}/submit` | signer (public token) | Yes | `signed` | ✅ |
| `signed` | `signature_request_completed` / `contract_signed` | **Activate** | `POST /signature-requests/{id}/activate` | legal/executive | No (manual only — see §6) | `active` | ✅ |
| `active` | `contract_activated` | Track obligations/payments/deadlines; no further lifecycle action required | — | any internal | No | *(steady state)* | ✅ |
| `rejected` | `review_rejected` / `approval_rejected` / `negotiation_rejected` | Read-only, terminal | — | — | — | *(terminal)* | ✅ |
| `cancelled` | `negotiation_abandoned` | Read-only, terminal | — | — | — | *(terminal)* | ✅ (via Abandon) |
| `completed` | — | *(no writer implemented — deferred, see §6)* | — | — | — | — | ⬜ deferred |
| `terminated` | — | *(no writer implemented — deferred, see §6)* | — | — | — | — | ⬜ deferred |

Waiting/blocked messaging and deterministic errors, per stage (all pre-existing or fixed this session, none newly invented beyond what the backend already returns):

- **`client_review`**: `ReviewHistoryPanel` shows the delivery badge (sent/failed/pending), attempts, timestamps, and a stale-version warning when applicable; `409 review_closed` on a duplicate decision.
- **`negotiation`**: `NegotiationPanel` shows "Waiting for the client's response" with Copy Link / Record Agreement Reached / Abandon once a counterproposal is sent — never zero actions. `403 negotiation_override_role_required`, `422 negotiation_reason_required`, `409 negotiation_closed`, `409 workflow_stale`.
- **`internal_review`**: `ApprovalsPanel` shows "Unresolved negotiations" + a "Go to Negotiation tab" button when blocked, and "Waiting for: <role>" when it isn't the viewer's turn. `403 approval_role_required`, `409 approval_out_of_order`, `409 approval_already_active`, `422 approval_reason_required`.
- **`ready_to_sign`**: `SignaturePanel` empty state explains the stage requirement when not yet eligible. `409 version_not_approved`, `409 approval_not_complete`, `409 active_request_exists`.
- **`partially_signed`**: ordered signer rows show waiting/invited/signed status; Retry/Copy Link remain available per eligible signer.
- **`signed`**: Activate button with mandatory reason + evidence. `403 signature_activation_forbidden`, `422 activation_reason_evidence_required`, `409 activation_not_ready`.

---

## 4. Tests added (persisted, real DB/API)

`backend/tests/test_contract_lifecycle_integration.py` (new, 8 tests, strict TDD — endpoint didn't exist before this session, so these were 404 before implementation):

1. `test_new_contract_defaults_to_draft_not_negotiation` — commits a bare `Contract()` with `stage` omitted, reads it back, asserts `"draft"`. Directly exercises the mechanism every insert path (including the frozen upload endpoint) uses.
2. `test_mark_ready_for_client_requires_current_version` → `409 no_current_version`.
3. `test_mark_ready_for_client_rejects_unfinished_extraction` → `409 contract_not_ready`.
4. `test_mark_ready_for_client_rejects_unsupported_document` → `409 contract_not_ready`.
5. `test_mark_ready_for_client_rejects_active_review` → `409 review_already_active`.
6. `test_mark_ready_for_client_succeeds_and_is_atomic_with_activity` — 200, stage → `ready_for_client`, `contract_ready_for_client` activity event persisted.
7. `test_mark_ready_for_client_only_valid_from_draft` — from `negotiation`, deterministic `409 invalid_stage_transition` (proves `LifecycleService` itself enforces the source stage — the service adds no separate check).
8. `test_mark_ready_for_client_then_send_for_review_chains_correctly` — `draft → ready_for_client → client_review` through two real endpoint calls in sequence.

`frontend/lib/pipeline.vitest.ts` (+4 tests): draft-while-processing buckets as `draft` never `negotiating`; draft-with-extraction-complete buckets as `draft`; `ready_for_client` buckets as `draft`; `client_review` buckets by review status, falling back to `sent_to_client` rather than `draft` when `workflow_summary` is absent.

`frontend/components/contract/ContractHeader.vitest.tsx` (+6 tests): action shown only for draft+extraction-complete; hidden while still processing; hidden for every other stage; no negotiation/approval/signature action leaks into draft; calls the endpoint and refreshes on success; deterministic error surfaced on failure.

All pre-existing review/negotiation/approval/signature/golden-path tests re-run and green (see §5).

---

## 5. Verification

### 5.1 Migration

```
$ python database/migrate.py
skip  001_init.sql ... skip  018_email_delivery.sql (all already applied)
apply 019_contract_stage_default_draft.sql
done.

$ SELECT column_default FROM information_schema.columns
  WHERE table_name='contracts' AND column_name='stage';
'draft'::text
```

### 5.2 Real API/database smoke — full chain, every stage captured

Scripted trace (no browser tools available this session — see limitation in §6), real AI extraction, real Postgres, synthetic contract deleted with zero residue after:

```
=== 1. UPLOAD ===
POST /api/contracts -> 201, stage=draft

=== 2. EXTRACT ===
POST /contracts/{id}/extract -> 200, stage=draft

=== 3. MARK READY FOR CLIENT ===
POST /contracts/{id}/mark-ready-for-client -> 200, stage=ready_for_client

=== 4. SEND FOR CLIENT REVIEW ===
POST /contracts/{id}/review/send -> stage=client_review

=== 5. CLIENT REQUESTS CHANGES ===
POST /review/{token}/request-changes -> 200, stage=negotiation

=== 6. NEGOTIATE: analyze -> approve -> send ===
analyze -> workflow_status=ready, stage=negotiation
send counterproposal -> stage=negotiation

=== 7. CLIENT ACCEPTS ===
POST /review/{token}/approve -> 200, stage=internal_review

=== 8. INTERNAL APPROVAL (4 ordered roles) ===
approvals/start -> 200, stage=internal_review
all 4 approved -> stage=ready_to_sign

=== 9. SIGNATURE ===
signature-request create -> stage=ready_to_sign
signature-request send -> stage=ready_to_sign
signer one signs -> stage=partially_signed
signer two signs (last) -> stage=signed

=== 10. ACTIVATE ===
POST /signature-requests/{id}/activate -> 200, stage=active

residual contract rows: 0
```

Activity trail (44 events, chronological) confirms every transition logged exactly once, ending: `... contract_ready_for_client, contract_entered_client_review, review_sent, ... contract_entered_negotiation, ... negotiation_accepted, contract_entered_internal_review, ... contract_ready_to_sign, ... contract_partially_signed, ... contract_signed, ... contract_activated`.

`scripts/golden_path_smoke.py` updated to call the real `mark-ready-for-client` endpoint (the SQL-bridge workaround it previously needed is deleted) and now asserts `stage == "draft"` immediately after upload and after extraction:

```
$ python3 scripts/golden_path_smoke.py
checks_total: 73, checks_passed: 73, checks_failed: 0
db_residue: all zero, storage residue: all removed
```

### 5.3 Focused + full backend suite

```
$ pytest tests/test_contract_lifecycle_integration.py -q
8 passed

$ pytest -q
406 passed, 2 failed, 602s
```

The 2 failures are pre-existing and unrelated (neither file touched this session, both were failing identically in the prior session's full run):
- `test_review_lifecycle_integration.py::test_review_resend_cooldown_is_deterministic` — a stale Task-3 test never updated after Task 4 intentionally changed cooldown-bypass-on-failure semantics (documented in `docs/demo-readiness-final.md`).
- `test_dashboard_summary.py::test_dashboard_summary_query_ceiling` — a hard SELECT-count ceiling against the shared live dev database; unrelated to lifecycle/contract code.

### 5.4 Full frontend suite, TypeScript, production build

```
$ npx vitest run
Test Files  13 passed (13)
     Tests  102 passed (102)

$ npx tsc --noEmit
(exit 0, no output)

$ npm run build
✓ Compiled successfully
✓ Generating static pages (19/19)
```

### 5.5 Browser/manual smoke

**Not executed as an actual browser session** — no browser automation tool was available this session (declined during setup). §5.2's scripted trace is the API-level equivalent, capturing stage/endpoint/result at every step exactly as specified. For a true click-through: open `http://localhost:3000/contracts/{id}` for a freshly uploaded contract and confirm the stepper highlights Draft, "Mark Ready for Client Review" is the only visible action, and each subsequent stage shows exactly the action listed in §3's table with no dead ends.

---

## 6. Files changed

**Backend**
- `backend/app/models.py` — `Contract.stage` default `negotiation → draft`
- `database/migrations/019_contract_stage_default_draft.sql` — new, DB column default
- `backend/app/services/contract_lifecycle.py` — new, `mark_ready_for_client()`
- `backend/app/routers/contract_lifecycle.py` — new, `POST /contracts/{id}/mark-ready-for-client`
- `backend/app/main.py` — registers the new router
- `backend/tests/test_contract_lifecycle_integration.py` — new, 8 tests

**Frontend**
- `frontend/lib/api.ts` — `markContractReadyForClient()`
- `frontend/components/contract/ContractHeader.tsx` — new button + handler
- `frontend/app/contracts/[id]/page.tsx` — passes `onLifecycleChange` to `ContractHeader`
- `frontend/lib/i18n.tsx` — `contract.markReadyForClient*` (EN+AR)
- `frontend/lib/pipeline.ts` — `KNOWN_STAGES` now includes every canonical stage (was missing `ready_for_client`, `client_review`, `rejected`, `cancelled`, `terminated` — would have spuriously dev-warned "unknown stage"); `SERVER_STAGE` corrected from mapping five different buckets to the single stale literal `"negotiation"` to accurate per-bucket values; `bucketContract()` now checks `client_review`/`ready_for_client` directly rather than relying solely on derived `workflow_summary` fields
- `frontend/components/contract/ContractHeader.vitest.tsx`, `frontend/lib/pipeline.vitest.ts` — new/updated tests

**Migration impact:** one new file, default-only, zero data risk, applied and verified (§5.1). No rollback needed; would be a one-line revert if ever required.

---

## 7. Manual demo flow (exact)

1. `/upload` — upload a real PDF/DOCX. Stage: **draft**.
2. Wait for extraction to finish (AiSummaryPanel/extraction status).
3. Contract header → **"Mark Ready for Client Review"**. Stage: **ready_for_client**. Stepper moves to Draft-step's right edge (draft/ready_for_client share one visual step per §3.4 of the original brief — both are pre-client preparation).
4. Contract header → **"Send for review"**, fill recipient, submit. Stage: **client_review**. Review tab shows delivery badge.
5. Open the copied public review link in a new tab → **Request changes** with a comment. Stage: **negotiation**.
6. Negotiation tab → **Analyze with AI** → review AI output → **Approve** → **Send to client** (copies the follow-up link).
7. Open the follow-up link (as the client) → **Approve**. Stage: **internal_review**. *(Or, without a real counterparty: Negotiation tab → **Record Agreement Reached**, enter a reason, confirm — same transition, audited override.)*
8. Approvals tab → **Start Internal Approval**, then approve as each of the four roles (switch the demo-role header each time). Stage: **ready_to_sign**.
9. Signature tab → **Create Signature Request** (two ordered signers) → **Send**.
10. Open signer one's link → sign. Stage: **partially_signed**. Open signer two's link → sign. Stage: **signed**.
11. Signature tab → **Activate** with a reason + evidence. Stage: **active**.

## 8. Remaining limitations

- **`completed` and `terminated` have no writer** in this release — matches `docs/contract-lifecycle-policy.md`'s own gap analysis (§10) and is explicitly a pending product decision (§11, item 8: "approve that end date creates a completion candidate, not automatic completion"), not something this fix set out to build.
- **Activation is manual-only.** The policy's recommended "hybrid" auto/manual activation (auto-activate when the verified effective date has passed) is not implemented; every `signed` contract requires the explicit Activate action regardless of date. Deferred, matches `docs/demo-readiness-final.md`.
- **No "clone into new draft" action** from a terminal (`rejected`/`cancelled`) contract — policy requires a separate formal entity, not a direct stage rollback; that entity doesn't exist yet.
- Two pre-existing, unrelated backend test failures remain open (§5.3), neither touched by nor caused by this change.
- Browser/manual smoke was executed as a scripted API-level equivalent, not an actual browser session (§5.5).
