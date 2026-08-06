# Configurable Approval Routes — Report

Status: Applied and verified. Branch `feature/timeline-payment-tracker`.

Scope: replace the Internal Approval flow's hardcoded four-role approval
chain with a configurable, per-contract approval route, plus reusable
saved route templates. Nothing else in the lifecycle was touched —
`LifecycleService` transition rules, review, negotiation, and signature
behavior are unchanged; the only new lifecycle-adjacent behavior is that
`approval_route_configured` is now logged alongside the existing
`approval_workflow_started` event, both while the contract stays in
`internal_review` exactly as before.

---

## Root cause

`app/services/approvals.py::_resolve_sequence()` accepted an
`approver_names: dict | None` parameter (exposed on the API as
`StartApprovalBody.approver_names`), validated that any keys in it were
known roles, and then **discarded it**:

```python
def _resolve_sequence(approver_names: dict | None) -> list[str]:
    names = approver_names or {}
    unknown = [role for role in names if role not in ALLOWED_DEMO_ROLES]
    if unknown:
        _raise(422, "invalid_approval_sequence", unknown_roles=sorted(unknown))
    sequence = list(DEFAULT_ROLES)   # <- always this, regardless of input
    ...
    return sequence
```

`DEFAULT_ROLES = ["business_owner", "legal", "finance", "executive"]` was
the only sequence `start_workflow()` could ever produce. The
`approver_names` dict could only ever supply a *display name* for one of
those four fixed roles (`approver_name=names.get(step_role)`); it could
never add, remove, reorder, or reassign a step. The frontend
(`ApprovalsPanel.tsx`) matched this exactly: a hardcoded `CHAIN` constant
of the same four roles rendered four step cards unconditionally, and its
"Start" button called `startApproval(contractId)` with no body at all.

Confirmed via direct audit, matching every question the brief asked:

| Question | Answer |
|---|---|
| Workflows hardcode four roles? | Yes — `DEFAULT_ROLES`, always returned |
| Route steps generated from constants? | Yes — `_resolve_sequence()` ignored its own input |
| Role order fixed? | Yes — same four, same order, every time |
| Frontend assumes four approvals? | Yes — `CHAIN` was a literal 4-entry array, rendered as 4 fixed cards regardless of `workflow.steps.length` |
| Tests assume a fixed sequence? | Yes — `tests/test_approval_lifecycle_integration.py` and `tests/test_approvals.py` both asserted the literal `ROLE_SEQUENCE`/`DEFAULT_ROLES` |

---

## Data model

New tables (`database/migrations/021_configurable_approval_routes.sql`):

- **`approval_routes`** / **`approval_route_steps`** — reusable, saved
  route templates. `id, name, scope, active, created_by, created_at,
  updated_at`; steps: `route_id, step_order, role, approver_name,
  required`. Never bound to a contract.
- **`contract_approval_routes`** / **`contract_approval_route_steps`** —
  the contract-specific *configured* route, before (and then snapshotted
  into) a real workflow. `status`: `draft` (editable) → `started` (locked,
  once a workflow exists) → `cancelled` (once that workflow is
  cancelled — a fresh `configure` call then creates a new draft, never
  reusing or mutating this row). `source_route_id` records provenance
  when copied from a saved template, but is otherwise inert — the steps
  themselves are a real, independent copy.
- **`approval_steps.required`** (new column) — snapshot of "is this step
  mandatory," carried from the route into the real workflow step.
- **`approval_workflows.route_name`**, **`approval_workflows.contract_route_id`**
  (new columns) — traceability from a started workflow back to the exact
  route (and, transitively, template) it came from.

`ApprovalWorkflow`/`ApprovalStep` themselves are otherwise unchanged —
same table, same columns, same `step_order`/`status` state machine. A
route is *snapshotted* into these tables exactly as the old hardcoded
sequence used to be; only the source of the snapshot changed.

**Role vocabulary.** The demo's role-identity model
(`app/deps.py::ALLOWED_DEMO_ROLES`, what `X-Demo-Role` can claim) was
widened additively from `{business_owner, legal, finance, executive}` to
add `sales` and `manager` — needed because a route step can only ever be
acted on by someone presenting that exact role, and the spec's examples
(`Sales → Legal → Manager`) require those two. No existing role was
removed or renamed.

---

## APIs

All under the existing `approvals` router (`app/routers/approvals.py`),
protected by the existing bearer token + `X-Demo-Role` header:

| Method & path | Purpose |
|---|---|
| `PUT /api/contracts/{id}/approval-route` | Configure (or replace, while still draft) the contract's route. Body: `name?, steps[], source_route_id?, save_as_route?, save_as_route_name?`. |
| `GET /api/contracts/{id}/approval-route` | Latest configured route (draft/started/cancelled) for the contract, or `null`. |
| `POST /api/contracts/{id}/approvals/start` | Unchanged path; body no longer accepts `approver_names` — it now requires a `draft` route to already exist. |
| `GET /api/approval-routes` | List saved templates (`?include_inactive=true` to include archived ones). Also returns `available_roles`. |
| `POST /api/approval-routes` | Create a saved template. |
| `GET /api/approval-routes/{id}` | Template detail/preview. |
| `PUT /api/approval-routes/{id}` | Edit a template's name/steps — **only** the template; never touches any contract copy already made from it. |
| `POST /api/approval-routes/{id}/archive` | Deactivate (soft-delete) a template. |

All existing approval endpoints (`GET /approvals`, `PATCH
/approvals/{step_id}`, `POST /approvals/cancel`, `GET /activity`, `GET
/approvals/summary`) are unchanged in shape and behavior; `serialize_workflow()`
gained `route_name`, `contract_route_id`, and a literal `"workflow_type":
"sequential"` field (see below), and each step gained `required`.

### Expected flow, as implemented

```
internal_review
  → PUT .../approval-route   (configure; logs approval_route_configured)
  → POST .../approvals/start (snapshot route → real steps; logs approval_workflow_started)
  → PATCH .../approvals/{step_id} × N, strictly in order
  → final step approved → LifecycleService.transition(..., APPROVAL_COMPLETED, ...)
  → ready_to_sign
```

`start_workflow()` validates, in order: draft route exists and has ≥1
step (`422 approval_route_required` / `422 approval_steps_required`),
stage is `internal_review`, current version exists and is usable, no
active workflow already (`409 approval_already_active`), no active
signature request, no unresolved negotiations unless an authorized
override is presented (unchanged mechanism from the prior negotiation
sub-task). All of this — and the snapshot of route → steps — happens
inside one transaction; the route is marked `started` in the same commit.
`contract.stage` is never assigned directly anywhere in this path;
`LifecycleService.transition(..., APPROVAL_STARTED, ...)` (self-transition,
stays `internal_review`) and, on the final step,
`LifecycleService.transition(..., APPROVAL_COMPLETED, ...)` are the only
ways the stage ever moves.

---

## Sequential vs. parallel

The workflow engine's completion/advancement logic
(`ApprovalStep.step_order`, `ApprovalWorkflow.current_step_order`, and
`act_on_step()`'s out-of-order guard) has exactly one execution model:
step *N* unlocks only once step *N-1* is resolved. There is no code path
anywhere that opens two steps at once. Per the explicit instruction not to
fake capability, this implementation:

- Never offers a "parallel" or "mixed" option in the route builder.
- Returns a literal `"workflow_type": "sequential"` on every workflow and
  contract-route payload.
- Shows a permanent, honest note in the route builder UI: *"This backend
  currently supports sequential approvals only... Parallel approval is
  not supported yet."*

No schema or engine change was made to add parallel execution — that
would be a materially larger change (concurrent step unlocking, a
different completion condition, different UI for "N of M in this step
group") than "the smallest safe data model needed" calls for here.

---

## Authorization

`ROUTE_ADMIN_ROLES = {"legal", "executive"}` gates every route-mutating
action: configure a contract's route, create/update/archive a saved
template. The brief asked for "legal, executive, or the existing
approval-admin role" — **no `approval_admin` role exists anywhere in this
demo's role model** (checked directly; there is no such role in
`deps.py`, `approvals.py`, or any router). `legal`/`executive` already
serve as this app's elevated-authorization tier elsewhere (e.g. the
negotiation unresolved-negotiations override from the prior sub-task
uses the identical set), so they were reused rather than inventing a new
role identity that has no other meaning in the system. This is called out
explicitly rather than silently substituted.

Enforced, all via deterministic errors (not silent failures):

- Non-admin role attempting to configure/create/update/archive a route →
  `403 approval_route_role_required`.
- Assigning a role outside the known vocabulary → `422 invalid_approver`.
- There is no per-user account system in this demo (single shared demo
  workspace, identity is only the `X-Demo-Role` header) — "assign users
  outside the organization" has no meaningful backend check to add beyond
  the role-vocabulary check above; `approver_name` is a free-text label
  for display/audit only, not a second identity gate. This limitation is
  the same one every other feature in this codebase that mentions "named
  approvers" already lives with (e.g. `ApprovalStep.approver_name`
  pre-dates this change).
- Empty route → `422 approval_steps_required` (also enforced at the
  Pydantic layer via `min_length=1`).
- Duplicate active workflow → `409 approval_already_active` (on start).
- Modifying route configuration after a workflow has started → `409
  approval_route_locked` (on configure) — distinct from
  `approval_already_active`, which is what `start` itself returns for a
  duplicate start attempt. The two codes map cleanly to the two different
  calls the spec's error list distinguishes.
- Completed approval evidence is never deleted or overwritten — cancelling
  a workflow only flips its `status`/marks remaining steps `locked`; every
  already-`approved`/`rejected`/`changes_requested` step keeps its
  `acted_at`/`acted_by`/`comment` exactly as recorded (unchanged behavior,
  pre-dates this change, re-verified by test #13 below).

---

## Saved-route behavior

- Selecting a saved route for a contract **copies** its steps into a new
  `ContractApprovalRoute`/`ContractApprovalRouteStep` row set — a real,
  independent copy, not a reference (`source_route_id` records where it
  came from, nothing more).
- Editing a saved template (`PUT /api/approval-routes/{id}`) only ever
  touches `approval_routes`/`approval_route_steps`. It cannot reach a
  `ContractApprovalRoute` or `ApprovalStep` row by construction — those
  live in different tables with no back-reference from template to copy.
  Verified directly (test #8 below): editing a template after a workflow
  has already started from it leaves that workflow's persisted steps
  byte-for-byte unchanged.
- "Customize a copied route before starting" needs no special backend
  endpoint: the frontend fetches the template's steps, pre-fills the
  builder, the user edits freely, and the *edited* set (not the
  template's original set) is what gets submitted to `configure`.

---

## Frontend

- **`components/ApprovalRouteBuilder.tsx`** (new) — shown whenever no
  active workflow exists and the contract is in `internal_review`:
  saved-route dropdown (pre-fills the builder for customization), add /
  remove / move-up / move-down approvers, per-step role select +
  optional named-approver text + required checkbox, step numbers, live
  ordered preview ("1. Legal — 2. Sales — 3. Executive"), optional route
  name, "Save as reusable route" + name, and a permanent sequential-only
  disclosure. The save action is disabled with zero steps (client-side
  belt to match the server's `422`).
- **`components/ApprovalsPanel.tsx`** (rewritten) — no more `CHAIN`
  constant or generic "Start" button:
  - No workflow yet → renders `ApprovalRouteBuilder` (or, once a draft
    route exists, a compact "route ready" card with its real ordered
    steps and a genuinely separate **"Start Approval Workflow"** button —
    the spec's "show Start Approval Workflow only after a valid route
    exists" is literal here: the button does not exist until
    `contractRoute.status === "draft"` with ≥1 step).
  - Workflow exists → step cards are generated from `workflow.steps` (any
    length, not padded/truncated to four), current-step highlighting,
    out-of-order visual flag, `route_name` and `workflow_type` shown,
    optional-step badge, cancellation (unchanged mechanism, now
    surfaces correctly regardless of route length).
- **`components/contract/ContractHeader.tsx`** — the `internal_review`
  shortcut button's label changed from "Start Internal Approval" to
  "Configure Approval Route" (`t("approval.configureRoute")`). Its
  behavior was already "switch to the Approvals tab" (`onStartApproval={()
  => setTab("approvals")}` in `app/contracts/[id]/page.tsx`) — it never
  called `startApproval()` directly — so the label now accurately
  describes what actually happens: it opens the tab, which shows the
  route builder, not an instant hardcoded workflow.
- **`components/DemoRoleSwitcher.tsx`** — added `sales`/`manager` to the
  switchable demo roles, matching the widened role vocabulary.

---

## Files changed

Backend:
- `database/migrations/021_configurable_approval_routes.sql` — new tables/columns.
- `app/models.py` — `ApprovalRoute`, `ApprovalRouteStep`,
  `ContractApprovalRoute`, `ContractApprovalRouteStep`;
  `ApprovalStep.required`; `ApprovalWorkflow.route_name`/`contract_route_id`.
- `app/deps.py` — widened `ALLOWED_DEMO_ROLES`.
- `app/services/approval_routes.py` (new) — all route CRUD, validation,
  copy-on-select, configure/lock/cancel-unlock logic.
- `app/services/approvals.py` — `start_workflow()` now snapshots from the
  configured draft route instead of `DEFAULT_ROLES`; `cancel_workflow()`
  marks the associated route `cancelled`; `serialize_step`/`serialize_workflow`
  report `required`/`route_name`/`contract_route_id`/`workflow_type`;
  `_resolve_sequence()` removed (dead code — its only behavior was
  "always return the hardcoded four").
- `app/routers/approvals.py` — new route endpoints; `StartApprovalBody`
  no longer accepts `approver_names`.
- `tests/test_approvals.py`, `tests/test_approval_lifecycle_integration.py`
  — updated for the removed `_resolve_sequence()`/`approver_names` (see
  Tests below); all pre-existing assertions about behavior (ordering,
  out-of-order blocking, override handling, cancel/restart, final-step
  transition) are unchanged and still pass.
- `tests/test_approval_routes.py` (new) — 19 tests.

Frontend:
- `components/ApprovalRouteBuilder.tsx` (new).
- `components/ApprovalsPanel.tsx` (rewritten).
- `components/contract/ContractHeader.tsx` — shortcut label.
- `components/DemoRoleSwitcher.tsx` — added roles.
- `lib/api.ts`, `lib/types.ts` — new route endpoints/types;
  `startApproval()` no longer sends `approver_names`.
- `lib/i18n.tsx` — new keys, Arabic + English, including the exact
  requested strings `"Configure Approval Route"` / `"تحديد مسار الموافقات"`.
- `components/ApprovalRouteBuilder.vitest.tsx` (new, 7 tests),
  `components/ApprovalsPanel.vitest.tsx` (updated + 2 new step-count tests).

---

## Tests

All 17 required scenarios, mapped to what was actually written
(`backend/tests/test_approval_routes.py` unless noted):

1. One-step Executive route — `test_one_step_executive_route`.
2. Legal → Sales → Executive order preserved through persistence and
   approval — `test_legal_sales_executive_order_preserved`.
3. Existing four-role route saved and reused —
   `test_four_role_route_saved_and_reused`.
4. Empty route rejected — `test_empty_route_is_rejected`.
5. Duplicate approver rejected (plus the "unless explicitly supported"
   carve-out) — `test_duplicate_approver_is_rejected`,
   `test_duplicate_role_with_distinct_named_approvers_is_allowed`.
6. Unauthorized user cannot configure — `test_unauthorized_role_cannot_configure_route`.
7. Saved route copied into contract-specific steps —
   `test_saved_route_copied_into_contract_specific_steps`.
8. Editing a saved route doesn't mutate a started workflow —
   `test_editing_saved_route_does_not_mutate_started_workflow`.
9. Workflow stays in `internal_review` while pending —
   `test_workflow_remains_in_internal_review_while_pending`.
10. Out-of-order approval blocked — `test_out_of_order_approval_is_blocked`.
11. Final configured approver → `ready_to_sign` —
    `test_final_configured_approver_moves_to_ready_to_sign` (uses a
    `sales → manager` route, proving it's not special-cased to `executive`).
12. Route cannot be edited after start — `test_route_cannot_be_edited_after_start`.
13. Cancel with reason preserves audit history —
    `test_cancel_with_reason_preserves_audit_history`.
14. Restart creates a new workflow and steps —
    `test_restart_creates_new_workflow_and_steps`.
15/16. Frontend does not assume four steps; stepper uses real counts —
    `frontend/components/ApprovalsPanel.vitest.tsx`, two new tests
    rendering 1-step and 6-step workflows and asserting card counts match.
17. Existing lifecycle/negotiation/signature/review tests remain green —
    full suite result below.

Plus additional tests beyond the required 17: `invalid_approver` for an
unknown role, `approval_route_required` when starting with no configured
route, `approval_route_locked` vs `approval_already_active` distinguished
on the same active-workflow state, list/archive of saved routes.

Backend unit-level: `tests/test_approvals.py`'s two tests for the removed
`_resolve_sequence()` were replaced with equivalent tests for its
replacement, `approval_routes._validate_steps()` (order preservation,
unknown-role rejection, empty rejection, duplicate rejection).

`tests/test_approval_lifecycle_integration.py` (the pre-existing 35-test
suite) required one behavioral test rewrite: the "unknown approver role"
test used to POST `approver_names` to `/approvals/start` — that field no
longer exists, so the test was moved to configure-time
(`test_configure_route_with_unknown_approver_role_is_rejected`, asserting
the new `422 invalid_approver`). Every other test in that file needed only
its `start_approval()` test helper updated to configure a route (default
four-role, unless a test explicitly requests otherwise) before starting —
no assertion about ordering, blocking, override, cancellation, or final
transition changed.

---

## Verification

- **Focused**: `tests/test_approval_routes.py` — 19/19 passed.
  `tests/test_approvals.py` — 19/19 passed (includes the 4 rewritten
  unit tests). `tests/test_approval_lifecycle_integration.py` — 35/35
  passed, unchanged behavior.
- **Full backend suite**: `pytest -q` — see below.
- **Frontend**: `npx tsc --noEmit` clean. `npx vitest run` — 21 test
  files, 153 tests, all passed (144 pre-existing + 9 new: 7 in
  `ApprovalRouteBuilder.vitest.tsx`, 2 in `ApprovalsPanel.vitest.tsx`).
  `npm run build` — compiled successfully, all routes including the
  unchanged route list build clean.
- **Real API/DB smoke — the exact 11-step manual smoke requested**: ran
  as a scripted trace against the live backend/Postgres (no browser
  automation tool available this session — see limitation below):
  reached `internal_review` → configured Legal → Sales → Executive →
  saved it as "Standard Commercial" → started the workflow (confirmed
  `route_name` recorded) → approved in order (legal, then sales, then
  executive) → confirmed `contract_stage == ready_to_sign` both in the
  API response and via direct DB read-back → created a second contract →
  fetched "Standard Commercial"'s detail (3 steps) → customized the copy
  down to a single Executive step (confirmed the *copy* has 1 step while
  the template still shows 3) → started and completed that one-step
  workflow → re-fetched "Standard Commercial" and confirmed its steps are
  still exactly `legal → sales → executive`, byte-for-byte, and its name
  is unchanged. All synthetic contracts and the test template were
  deleted afterward.
- **Manual/browser smoke**: not literally executed — no browser
  automation tool is available in this session. The scripted API/DB trace
  above follows the identical request sequence (configure → save →
  start → approve × N → verify stage → new contract → select saved route
  → customize → start → complete → verify original unchanged) a browser
  session driving the UI would produce.

### Full backend suite result

```
FAILED tests/test_dashboard_summary.py::test_dashboard_summary_query_ceiling
FAILED tests/test_review_lifecycle_integration.py::test_review_resend_cooldown_is_deterministic
2 failed, 453 passed in 972.30s (0:16:12)
```

Both failures are pre-existing, unrelated to approvals (a query-plan
timing assertion and an SMTP resend-cooldown timing assertion), and were
already documented as flaky in earlier work on this branch. No test that
touches approvals, negotiation, signature, review, or lifecycle behavior
regressed.

---

## Migration impact

Purely additive: two new columns on `approval_steps`
(`required`, default `true`) and `approval_workflows`
(`route_name`, `contract_route_id`, both nullable), and four new tables.
No existing row's data changes meaning; every pre-existing
`ApprovalWorkflow`/`ApprovalStep` reads exactly as it did before (`required`
defaults to `true`, matching every step's actual historical behavior —
"every step was mandatory" was the truth before this change too, just
implicitly). No backfill was necessary or performed.

## Remaining limitations

- **No real per-user identity/authentication system exists in this demo**
  (confirmed during the audit — the whole app authenticates as one shared
  demo workspace, distinguished only by the `X-Demo-Role` header).
  "Assign named users" is therefore implemented as a free-text
  `approver_name` label for display/audit, not a second, independently
  authenticated identity gate — the role field remains the only thing
  that actually gates who can act on a step. This is not a regression
  introduced here; it is the pre-existing architecture, stated honestly
  rather than papered over.
- **Sequential only.** No parallel or mixed-mode approval exists in the
  engine; the UI states this plainly rather than offering a toggle that
  would do nothing. Adding real parallel execution (concurrent step
  groups, a different completion condition, N-of-M semantics) would be a
  materially larger change than this fix's scope.
- **No `approval_admin` role exists.** `legal`/`executive` serve as the
  route-configuration authorization tier, reusing this app's existing
  elevated-role convention rather than inventing a new, otherwise-meaningless
  role.
- **`scope` on `approval_routes` is a placeholder.** This demo is a
  single implicit workspace/tenant; the column exists so a genuinely
  multi-tenant deployment has somewhere to scope routes without a further
  migration, but nothing in this implementation actually enforces or
  varies by scope today.
- **"Optional" (non-required) steps are captured and displayed but not
  skippable.** The sequential engine's completion condition is still
  "every configured step must be resolved" — marking a step
  `required: false` records intent and renders an "optional" badge, but
  does not change whether the workflow can complete without it. Building
  true skip-if-optional logic touches the same completion-detection code
  path this fix deliberately left alone (`_approve_step`'s
  `is_final`/advancement logic), and doing so safely was judged out of
  "the smallest safe data model needed" for this fix. This is stated
  explicitly rather than silently under-delivering the "which steps are
  mandatory" requirement.
