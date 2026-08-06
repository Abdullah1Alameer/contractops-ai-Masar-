# Negotiation Flow Bugfix Report

Status: Applied and verified. Branch `feature/timeline-payment-tracker`.

Scope: reproduce, trace, and fix the five known negotiation bugs below, then
run a focused regression audit of the negotiation flow, the review→negotiation
handoff, version flow through negotiation, the negotiation list/dashboard, and
the lifecycle transitions directly touched by negotiation. Nothing outside
that scope was touched — review, approval, signature, email, and the lifecycle
engine's transition rules are unchanged.

---

## Bug 1 — False empty negotiation state

**Reported symptom**: the Negotiation tab shows "لم يُرصد أي مسألة تفاوض
منظمة" / "No structured negotiation issue detected" even though a real,
active `changes_requested` negotiation exists further down the tab.

**Root cause**: `app/contracts/[id]/page.tsx` renders two independent
components in the Negotiation tab, stacked vertically:

1. `NegotiationOpportunitiesPanel` — a separate, *proactive* "AI-suggested
   other clauses worth negotiating" feature, backed by its own
   `negotiation_opportunities` table/endpoint. It is optional and frequently
   empty (most contracts have no AI-suggested opportunities beyond the one
   the client actually raised).
2. `NegotiationPanel` — the real, actionable negotiation workspace, driven by
   `fetchNegotiations(contractId)` / the `Negotiation` table.

When (1) had zero rows, it rendered a full `EmptyState` with exactly the
reported string (`negotiation.noOpportunities`). Because it sits above (2),
it visually read as "the whole tab is empty," even though the real
negotiation was present just below.

**Fix**:
- `NegotiationOpportunitiesPanel.tsx`: no longer renders a full-page empty
  state. If there are zero AI-suggested opportunities (or it's loading), the
  component now renders nothing (`return null`), instead of claiming the tab
  itself has nothing in it.
- `NegotiationPanel.tsx`: the real empty state (`negotiation.empty` — "No
  negotiation items yet — appears when the client rejects or requests
  changes") only ever renders when `candidates.length === 0`, i.e. when zero
  negotiation items genuinely exist for the contract.
- Every negotiation item now renders as a compact `NegotiationSummaryCard`
  (issue/clause ref, workflow status badge, risk level, negotiation score,
  assigned lawyer, last activity, waiting-party text, "Open details" button)
  in a grid immediately below the cards — see Bug 4.

**Files changed**: `components/NegotiationOpportunitiesPanel.tsx`,
`components/NegotiationPanel.tsx`.

**Before/after**:
- Before: contract with an active negotiation and zero AI-suggested
  opportunities → full "no negotiation issue detected" empty state, real
  negotiation invisible without scrolling past it.
- After: same contract → summary card renders immediately, detail workspace
  directly below it; the opportunities panel renders nothing when it has
  nothing to say.

---

## Bug 2 — "Adopt AI Recommendation" appears to do nothing

**Reported symptom**: clicking "Adopt AI Recommendation" produces no visible
change; manually typing into the lawyer-proposal textarea behaves
differently and lets the user continue.

**Root cause**: `NegotiationResult`'s "Approve" button called
`onClick={() => save({ status: "approved" })}` — a `PATCH` that only flips
the invisible `status` field. The two visible, editable textareas
(`finalEn`/`finalAr`, bound to `lawyer_final_clause`/`lawyer_final_clause_ar`)
were initialized once from `row.lawyer_final_clause ?? ""` and were **never**
touched by this handler. So the click did something (a real PATCH went out
and `status` really did flip to `approved` server-side), but nothing the
user could see changed — hence "appears to do nothing." Manually typing felt
different because typing *does* update the visible textarea via
`onChange`/`onBlur → saveFinal()`.

This was a legibility/trust bug, not strictly a dead end — `send_updated()`
already falls back to `counter_clause` when `lawyer_final_clause` is empty,
so a send would still have worked — but the UI gave no honest indication of
what it was about to send.

**Fix** (`components/NegotiationPanel.tsx`):
- New `adoptAiRecommendation()` handler: copies `draft.counter_clause` /
  `draft.counter_clause_ar` into the *same visible* `finalEn`/`finalAr`
  state the lawyer would type into, then persists both together with the
  approval in one `PATCH`:
  ```ts
  await patchNegotiation(row.id, {
    status: "approved",
    lawyer_final_clause: en || undefined,
    lawyer_final_clause_ar: ar || undefined,
  });
  ```
  This uses the same single-call persistence path the repo's existing
  "Approve" action already used — adoption doesn't introduce a new save
  trigger, it just makes the existing one carry the field the user actually
  sees.
- A derived (not locally-`useState`-flagged — see rationale below) `adopted`
  boolean renders a small "AI recommendation adopted — review before
  sending" badge whenever the persisted `lawyer_final_clause` exactly
  matches the persisted `counter_clause`.
- The textareas remain fully editable after adopting — editing them still
  goes through the existing `onBlur → saveFinal()` path, so a lawyer can
  adopt-then-tweak before sending.
- `adoptAiRecommendation()` never calls `sendNegotiationUpdated()` — nothing
  is sent to the client from this click. Only the explicit "Send" button
  (unchanged) dispatches the counterproposal.

**Why `adopted` is derived, not local state**: this file already has a
documented bug class where `onUpdated()` (called after any successful PATCH)
triggers the parent's `loading` skeleton, which unmounts and remounts the
detail workspace — silently wiping any local-only `useState` set right
before the refetch resolves. `adopted` is instead computed each render from
persisted row fields, so it survives that remount by construction.

**Tests added** (`components/NegotiationPanel.vitest.tsx`):
- "copies the AI counter clause into the visible lawyer-proposal field and
  persists it via the existing approve action" — asserts the textarea's DOM
  value actually changes, the exact PATCH payload sent, and that
  `sendNegotiationUpdated` is never called.
- "still allows editing the adopted text before it is sent" — adopts, then
  edits the now-visible text and confirms the edit is what gets saved.

**Backend tests added** (`backend/tests/test_negotiation_lifecycle_integration.py`):
- `test_adopt_ai_recommendation_patch_persists_visible_proposal_fields` —
  the single combined PATCH (`status` + `lawyer_final_clause(_ar)`)
  persists all three fields, moves `workflow_status` to `edited_by_legal`,
  and does **not** set `sent_at` (nothing was sent).
- `test_adopted_recommendation_can_then_be_sent_as_counterproposal` — the
  adopted proposal survives into `/send` unchanged.

---

## Bug 3 — Confusing/duplicate "Negotiations" and "Negotiation Monitor" navigation

**Reported symptom**: two overlapping nav destinations; the Monitor page
reads as empty/broken (its email-thread feature has no data for the real
negotiation flow), and "Negotiations" was a bare contract list.

**Fix**: replaced both with one unified page, `/negotiations`.

### Backend

New read model, `negotiation_board()`
(`backend/app/services/negotiation.py`), backing `GET /api/negotiations/board`
(`backend/app/routers/negotiation.py`). One row per **active** (non-terminal:
excludes `workflow_status` in `{accepted, closed}`) `Negotiation`, across
every contract, with:

| Field | Source | Notes |
|---|---|---|
| `contract_title`, `counterparty`, `contract_stage` | `Contract` | real, joined |
| `clause_ref`, `issue`, `workflow_status`, `editing_status`, `risk_level`, `recommendation` | `Negotiation` | real |
| `assigned_lawyer` | `final_summary.lifecycle.legal_edited_by` | best-effort heuristic — see "Unavailable data" below |
| `waiting_party` | derived from `workflow_status` via `_waiting_party()` | `client` / `lawyer` / `null` |
| `message_count` | bulk-counted `NegotiationMessage` rows, grouped by negotiation | real, not an estimate |
| `sent_at`, `updated_at`, `days_waiting` | `Negotiation.sent_at` / real elapsed time | real |
| `sla_status` | `ok` / `approaching` / `overdue`, derived from `days_waiting` at 3/7-day thresholds, only when `workflow_status == sent_to_client` | **operational bucket, not a stored SLA policy** — see below |
| `critical_deadlines`, `missed_deadlines` | bulk-aggregated `Deadline` rows for the contract | real |
| `is_stale` | `negotiation.version_id != current_version(contract).id` | real |

`summary` gives real counts: `total_active`, `pending`, `waiting_client`,
`waiting_lawyer`, `high_risk`, `overdue`.

Both the message-count and deadline aggregates are bulk-queried (one query
each across all contracts on the page, not N+1 per row).

### Frontend

- `app/negotiations/page.tsx` — rewritten. Six summary tiles (from the real
  `summary` object), filter chips (`all` / `pending` / `waiting_client` /
  `waiting_lawyer` / `high_risk` / `overdue`), free-text search over
  contract name/counterparty, and one card per active negotiation showing
  every field above plus an "Open negotiation" link to
  `/contracts/{id}?tab=negotiation&item={negotiation_id}`.
- `app/negotiations/monitor/page.tsx` — replaced with a client-side redirect
  to `/negotiations`, so any bookmark/old link lands somewhere useful
  instead of 404ing. `app/negotiations/monitor/[threadId]/page.tsx` (the
  per-thread detail route) was left untouched — it isn't part of the
  confusing top-level duplication being fixed here.
- `components/shell/Sidebar.tsx` — removed the separate "Negotiation
  Monitor" nav entry; one "المفاوضات" / "Negotiations" entry remains.

### Honest handling of unavailable data

Per the explicit instruction not to invent metrics the schema can't support:

- **"Unread messages"** was part of the original ask but is **not shown** —
  there is no read/unread column anywhere on `NegotiationMessage` or any
  related table. Real `message_count` is shown instead (labeled as message
  count, not unread count), and this omission is called out in a code
  comment on the page and in this report rather than faked.
- **SLA** — there is no `sla_due_at`/`sla_hours` field or stored SLA policy
  anywhere in the schema. `sla_status` is a clearly-labeled *derived,
  operational* bucket computed from the real `sent_at` timestamp at
  documented 3/7-day thresholds — not a claim that a formal SLA policy
  exists.
- **"Assigned lawyer"** — there is no assignment table/feature. The value
  shown is a best-effort heuristic: whichever legal actor's edit last set
  `final_summary.lifecycle.legal_edited_by` on that item. This is the same
  heuristic used consistently in both `negotiation_board()` and
  `serialize_negotiation()` (the per-contract detail view), and renders as
  `—` when no legal actor has edited the item yet, rather than a fabricated
  name.

**Tests added**: `app/negotiations/page.vitest.tsx` (lists real fields;
filters for waiting-client/waiting-lawyer/high-risk/overdue; search; real
summary counts; empty state only when genuinely zero; stale flag rendered),
`app/negotiations/monitor/page.vitest.tsx` (redirect). Backend:
`test_board_excludes_terminal_items_and_buckets_summary_correctly`,
`test_board_message_count_matches_negotiation_messages`,
`test_board_flags_stale_negotiation_against_current_version`,
`test_board_overdue_sla_from_real_sent_at_and_missed_deadline`.

---

## Bug 4 — Negotiation details and summary disconnected

**Reported symptom**: no clear hierarchy from summary → selected detail; the
detail workspace could render far from an unrelated empty-state block (see
Bug 1).

**Fix**: `NegotiationPanel.tsx` now maintains one `selectedKey` (auto-set to
the highlighted/deep-linked item, else the first candidate) and renders:

1. The summary-card grid (`NegotiationSummaryCard` per candidate — same
   canonical `candidates` array the detail workspace reads from; there is no
   second dataset).
2. Immediately below, in a `<div id="negotiation-detail-workspace">`: the
   *selected* candidate's original clause, then either an "Analyze" prompt
   (if not yet analyzed) or the full `NegotiationResult` workspace.

Clicking a card (or its "Open details" button, or `Enter`/`Space` for
keyboard users — the card is a proper `role="button"`) sets `selectedKey`,
which swaps the detail workspace to that candidate. Status labels
(`waitingStateKey()`) are localized and identical between the card and the
detail workspace (`wsKey()`), and both explain the current next step:

- **waiting-for-client** (`sent_to_client`): the detail workspace shows the
  delivery state banner, "Copy client link," last-sent info via
  `final_summary`, and Abandon — unchanged from the prior sub-task's
  `sent_to_client`-is-not-a-dead-end fix.
- **waiting-for-legal** (`pending_analysis`/`ready`/`edited_by_legal`/
  `client_responded`): the card shows "بانتظار إجراء من القانوني" /
  "Waiting for legal action"; the detail workspace offers Analyze or the
  Adopt/Edit/Send actions.
- **closed/accepted**: no longer appears on the summary grid at all (only
  active items are candidates from `fetchNegotiations`), matching the
  unified board's same exclusion rule.
- **stale**: the detail workspace's existing stale banner (unchanged) —
  "belongs to an earlier version" — plus a restart-from-current-version
  action when applicable.

**Test added**: "selecting a different summary card swaps the detail
workspace to match" (`NegotiationPanel.vitest.tsx`).

---

## Bug 5 — Version flow through negotiation (focused audit)

Traced the path: current version → client review → request changes →
negotiation seed → AI analysis → lawyer proposal → counterproposal →
follow-up review → accepted agreement → internal review → new version (if
created) → approval → signature.

**Findings**:

1. **Negotiation creation is pinned to the version under review.**
   `Negotiation.version_id` is set at seed time to the `ContractVersion` the
   triggering `ReviewRequest`/`ReviewComment` was raised against (`app/services/reviews.py`
   creates the seed off the current version at send-time). Confirmed live in
   the smoke run: the negotiation's `version_id` matched `v1` immediately
   after seeding.

2. **Staleness is checked before every mutating action.**
   `_is_stale(negotiation, current)` (true when `negotiation.version_id !=
   current_version(contract).id`) gates every write path via
   `_validate_actionable()` — edits, sends, and (from the prior sub-task)
   the internal agreement override all reject stale items with
   `workflow_stale` (409). This was already covered by
   `test_stale_negotiation_cannot_be_edited_or_sent` and
   `test_internal_agreement_override_rejects_stale_version`, both still
   green. `negotiation_board()`'s `is_stale` flag and the unified page's
   warning badge use the exact same comparison, so the list-level signal and
   the enforcement are the same check, not two independently-maintained
   ones.

3. **Sending a counterproposal creates a new version and re-points the
   negotiation at it, atomically.** `send_updated()` calls
   `stage_negotiation_snapshot()` to create the new `ContractVersion`, then
   sets `negotiation.version_id = new_version.id` and creates the follow-up
   `ReviewRequest` against that same new version, all inside one
   transaction (`test_counterproposal_send_is_atomic_and_idempotent`
   asserts this). Confirmed live: after `/send`, `neg.version_id` no longer
   matched the original `v1` id.

4. **New versions never silently orphan open negotiations.**
   `supersede_version_negotiations()` is the codified answer for "what
   happens to negotiation items when a version they don't reference gets
   superseded by a different one" (e.g. a fresh manual upload while a
   negotiation is mid-flight): it closes the old-version items with
   `outcome=SUPERSEDED`, stamps `superseded_by_version_id` into
   `final_summary.lifecycle`, and — only when the contract is still in the
   `negotiation` stage — logs the transition through `LifecycleService`
   (`NEGOTIATION_SUPERSEDED`), never by assigning `contract.stage` directly.
   This function pre-dates this sub-task and was not modified; it was
   audited here to confirm Bug 5's "no cross-version orphaning" requirement
   already holds structurally.

5. **The follow-up review is tied to the exact version that was sent**, via
   `review.version_id = new_version.id` at creation, and
   `apply_followup_review_decision()` re-validates that the negotiation
   being resolved is not stale relative to the review's own version before
   accepting/closing it — confirmed live: the follow-up `ReviewRequest`
   created in step 8 of the smoke run referenced the same version id the
   negotiation was re-pointed to in step 7.

6. **Acceptance closes the correct items and transitions once, not per-item.**
   `apply_followup_review_decision()` on `approve` only fires
   `LifecycleService.transition(..., NEGOTIATION_ACCEPTED, ...)` once all
   negotiation items for that version are resolved
   (`test_partial_then_final_acceptance_moves_stage_only_when_all_resolved`,
   unchanged, still green) — confirmed live: with the smoke run's single
   item, acceptance moved the contract straight to `internal_review` and
   left exactly one `Negotiation` row, with `workflow_status == "accepted"`.

7. **Comparison/version listings are not version-scoped for
   obligations/deadlines/payments/risk/clauses** — this is a pre-existing,
   structural limitation already documented in
   `docs/review-portal-data-audit.md` from the prior sub-task: no
   `version_id` column exists on `Obligation`, `Deadline`,
   `PaymentMilestone`, `RiskFinding`, or `Clause`. It is out of this
   sub-task's scope (the instruction was explicitly to document, not
   schema-migrate, unless a confirmed release-blocking bug required it —
   none was found; the negotiation flow itself is correctly version-scoped
   via `Negotiation.version_id`, only these adjacent contract-wide tables
   are not). No change was made here.

**Conclusion**: no release-blocking version-flow defect was found. The
negotiation flow's own version scoping (`Negotiation.version_id`, staleness
gating, atomic version-creation-on-send, supersession-on-new-upload,
version-pinned follow-up reviews) is sound and was verified live end-to-end.
The one honestly-documented gap (contract-wide tables lacking `version_id`)
is unchanged from the prior audit and was not touched, per the explicit
instruction against broad schema migration.

---

## Files changed

Backend:
- `app/services/negotiation.py` — `negotiation_board()`, `_waiting_party()`,
  `_WAITING_ON_LAWYER`/`_WAITING_ON_CLIENT`, `assigned_lawyer` field in
  `serialize_negotiation()`.
- `app/routers/negotiation.py` — `GET /api/negotiations/board`.
- `tests/test_negotiation_lifecycle_integration.py` — 8 new tests (listed
  above).

Frontend:
- `components/NegotiationOpportunitiesPanel.tsx` — no full-page empty state.
- `components/NegotiationPanel.tsx` — summary cards, selection state, Adopt
  AI Recommendation fix, waiting-party helpers.
- `components/NegotiationPanel.vitest.tsx` — 5 new tests.
- `lib/api.ts`, `lib/types.ts` — `fetchNegotiationBoard`,
  `NegotiationBoardItem`/`Summary`/`Response`, `assigned_lawyer` on
  `NegotiationRow`.
- `app/negotiations/page.tsx` — rewritten as the unified page.
- `app/negotiations/page.vitest.tsx` — 9 new tests.
- `app/negotiations/monitor/page.tsx` — redirect.
- `app/negotiations/monitor/page.vitest.tsx` — 1 new test.
- `components/shell/Sidebar.tsx` — removed duplicate nav entry.
- `lib/i18n.tsx` — new keys (Arabic + English, both blocks):
  `negotiation.aiRecommendationAdopted`, `negotiation.aiRecommendationAdoptedBadge`,
  `negotiation.card.lawyer`, `negotiation.card.lastActivity`,
  `negotiation.card.openDetails`, `negotiation.overallIssue`,
  `negotiation.waitingOn.client`, `negotiation.waitingOn.lawyer`,
  `negotiationsBoard.*` (subtitle, filters, metrics, search, empty states,
  messages, waitingDays, deadlineFlag, open). English label of
  `negotiation.approve` updated to "Adopt AI Recommendation" to match the
  actual button behavior.

## Verification

- **Backend**: `tests/test_negotiation_lifecycle_integration.py` — 25/25
  passed (17 pre-existing unchanged + 8 new). Full suite: `pytest -q` —
  420 passed, 2 failed (`test_dashboard_summary_query_ceiling`,
  `test_review_resend_cooldown_is_deterministic`) — both pre-existing,
  unrelated to negotiation, documented in earlier sub-tasks this session.
- **Frontend**: `npx tsc --noEmit` — clean. `npx vitest run` — 16 test
  files, 132 tests, all passed (117 pre-existing + 15 new: 5 in
  `NegotiationPanel.vitest.tsx`, 9 in `app/negotiations/page.vitest.tsx`, 1
  in `app/negotiations/monitor/page.vitest.tsx`). `npm run build` —
  compiled successfully, 19/19 static pages; `/negotiations` 3.79 kB,
  `/negotiations/monitor` 374 B (was a full page).
- **Real API/DB smoke**: a synthetic contract was seeded directly (draft
  stage + one current version, mirroring real-upload output) and driven
  through every subsequent step via the live HTTP API against the running
  backend/Postgres: mark-ready → send review → client requests changes
  (payment reduction) → unified board shows it correctly (not empty,
  `waiting_party: lawyer`) → AI analyze → Adopt AI Recommendation (verified
  the persisted `lawyer_final_clause` matches the AI proposal) → send
  counterproposal → unified board flips to `waiting_party: client` with
  real message count/risk/SLA bucket → client approves the follow-up →
  contract reaches `internal_review` → read-back confirmed exactly one
  `Negotiation` row (`workflow_status: accepted`), `version_id` correctly
  re-pointed to the sent version, and the item no longer appears on the
  active board. All synthetic data was deleted afterward — zero residue.
- **Manual/browser smoke**: not literally executed — no browser automation
  tool is available in this session (declined earlier in the session). The
  scripted API/DB trace above is the closest rigorous equivalent and
  exercises the same backend code paths the UI calls.

## Remaining limitations (unchanged, explicitly not addressed here)

- No read/unread tracking for negotiation messages (no schema for it).
- No stored SLA policy (`sla_status` is a documented operational
  approximation from real timestamps, not a configured policy).
- No lawyer-assignment feature (`assigned_lawyer` is a best-effort
  last-editor heuristic).
- `Obligation`/`Deadline`/`PaymentMilestone`/`RiskFinding`/`Clause` remain
  contract-wide, not version-scoped (pre-existing, documented in
  `docs/review-portal-data-audit.md`; out of this sub-task's scope).
- `send_updated()` still does not create an outbound email/SMTP delivery
  attempt record for the counterproposal itself (a previously-documented,
  deferred-scope gap; the public review link it generates is delivered via
  the existing copy-link/manual-send affordances, unchanged here).
