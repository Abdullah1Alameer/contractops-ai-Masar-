# Public Client Review Portal — Data Completeness Audit

**Date:** 2026-08-06
**Scope:** `GET /api/review/{token}` and `app/review/[token]/page.tsx` only. No lifecycle stage or `LifecycleService` change — verified untouched (see §6).

## 1. How the audit was done

Traced every tab from database → serializer → endpoint → frontend type →
component, then proved it with a real newly uploaded contract (upload →
extract → intelligence rebuild → send for review → fetch the public
portal), comparing the public payload byte-for-byte against the internal
ground-truth endpoints (`GET /contracts/{id}`, `/obligations`,
`/deadlines`, `/milestones`) for the same contract. Raw traces are not
committed (scratch output); the reproduction script and assertions are
now permanent as `backend/tests/test_review_portal_data_completeness.py`.

## 2. Root causes, tab by tab

### Risks — **the reported bug, confirmed and fixed**

- **Source tables/fields:** `risk_findings` (category, code, points,
  explanation, explanation_ar) via `risk_engine.serialize_risk()` — the
  exact function `GET /contracts/{id}` uses for the internal risk score
  shown in `RiskScoreRing`/`detail.riskWhy`.
- **Backend (before):** `reviews.py::build_risk_summary()` was a
  completely separate, ad-hoc computation that never called
  `risk_engine.serialize_risk()` at all. It only produced an item when
  there was a penalty extraction, a `missed_or_time_barred` deadline
  count, a `critical` deadline count, or a high/critical flowdown
  finding — none of which cover the actual risk-v2 score (which comes
  from `RiskFinding` rows generated for `needs_review` deadlines/
  milestones/obligations and date inconsistencies). A contract with a
  real, non-zero internal score (e.g. one unresolved date reference) but
  no penalties/missed-deadlines/comparison findings showed **zero**
  public risk items — "No data yet" — while the internal panel showed a
  real score.
- **Verified with the real contract from the bug report:** internal
  `risk.score = 2, level = "low"`, one finding (`temporal`, "Date
  reference could not be fully resolved"). Old public payload:
  `risks.items = [{"type": "penalty", ...}]` — the real finding never
  appeared; if this contract had also lacked a penalty clause, the tab
  would have shown nothing at all.
- **Fix:** `build_risk_summary()` now sources `score`/`level` directly
  from `risk_engine.serialize_risk()` (identical numbers to internal),
  and turns every `RiskFinding` into an item with `contributes_to_score:
  true`. The old penalty/missed-deadline/comparison heuristics are kept
  as supplementary context, explicitly marked
  `contributes_to_score: false`, so the two kinds of signal (what backs
  the number vs. what's merely relevant) are never conflated — this is
  how "the visible score is explained" without silently dropping
  genuinely useful operational-risk context.
- **Public safety:** only category/code/points/explanation/explanation_ar/
  link_tab/clause_ref/page — the same fields already shown internally.
  No actor names, no negotiation strategy.

### Obligations — extracted values missing from their own tab

- **Source:** `obligations` table — `title`, `beneficiary`,
  `trigger_type`, `trigger_event`, `completion_criteria`,
  `suggested_evidence`, `contract_required_evidence` all exist on the
  model and are shown on the **internal** obligations view, but
  `reviews.py::_serialize_obligations()` only ever selected
  `id/description/responsible_party/due_date/penalty_text/status/
  clause_ref/page` — a narrower, undocumented subset. This is the
  concrete case of "extracted values appear in the summary count
  (`ai_summary` says "Obligations tracked: 1") but not in the dedicated
  tab."
- **Fix:** enriched to the full safe field set (verified: none of it is
  internal-only — it's the same data the internal Obligations view
  already renders).

### Timeline — "only event names with missing dates/details"

- **Source:** `deadlines` table via `deadlines.serialize_deadline()` —
  already returns a rich object (`status`, `severity`,
  `source_trigger_date`, `notice_period_days`,
  `calculation_explanation(_ar)`, `clause_ref`, `page`, ...); this is the
  **same function** the internal `DeadlineTimeline` component consumes.
  The backend was never the problem here.
- **Root cause:** the frontend rendered only `d.title ?? d.type` and
  `d.deadline_date ?? "—"`, discarding everything else already present
  in the API response.
- **Nuance confirmed with the real contract:** the notice deadline's
  `deadline_date` is genuinely `null` — the base date couldn't be
  resolved (`review_reason: "missing_base_date"`). That is a correct,
  honest null, not a bug. What was missing was showing *why*
  (`calculation_explanation`) instead of a bare "—".
- **Fix:** frontend now renders status badge, notice-period days,
  source-trigger date, and — specifically when the date is unresolved —
  the calculation explanation (language-matched, `dir="auto"`), plus a
  clause/page source reference. No backend change needed.

### Payments — same shape of gap as Timeline

- **Source:** `payments.serialize_milestone()` — already rich
  (`status`, `due_date`, `responsible_party`, `beneficiary`,
  `trigger_event`, `calculation_explanation`), shared with the internal
  `PaymentTracker`. Frontend rendered only `label` + `amount_sar`.
- **Fix:** frontend now renders status badge, due date, and a source
  reference. No backend change needed.
- Noted, not fixed (out of this audit's scope): the traced real contract
  extracted 1 milestone during `POST /extract`
  (`counts.milestones: 1`) but `GET /contracts/{id}/milestones` returned
  `[]` for both the internal and public endpoints — identical behavior
  on both, so it is an **extraction-accuracy** question, not a public-
  portal-completeness discrepancy, and is outside this task's scope.

### Comparison — confirmed the "only one version" hypothesis is wrong

- **What "Comparison" actually means here:** a flowdown clause
  comparison between a **main contract and a linked subcontract**
  (`FlowdownFinding` rows via `flowdown.list_flowdown_for_pair`). It has
  no relationship to `contract_versions` at all — there is no per-
  version diff feature wired into this endpoint.
- **Verified:** the real audited contract is `type: "main"` with no
  linked subcontract. `comparison` is correctly `null` regardless of how
  many versions the contract has — tested explicitly (§4) by creating a
  second contract with two versions and confirming comparison is still
  `null` for the same reason.
- **Fix:** added `comparison_unavailable_reason` (`"not_linked"` vs.
  `"not_yet_compared"`, computed from `Contract.parent_main_contract_id`
  and its inverse) and rewrote the empty-state copy to state the real
  reason instead of a generic message that invited the "must need
  another version" misreading. No version-comparison feature was added —
  that would be new scope, not a completeness fix to what exists.

### Summary tab

No bug found beyond the two items above already surfacing in `ai_summary`
counts but not their own tabs (now fixed). `data.contract` fields shown
are already a safe, complete subset (`value_sar`, `governing_law`,
`start_date`, `end_date`); no source table issue.

### Clause comments

Already correct — `ReviewComment` rows scoped to `review_request_id`
(inherently scoped to this exact review, not contract-wide), rendered
in full, no changes needed.

## 3. Version scoping — what's true and what isn't achievable

**Requirement:** "Scope all data to the review request's exact contract
version." **Finding:** `obligations`, `deadlines`, `payment_milestones`,
`risk_findings`, `clauses`, and `extractions` have **no `version_id`
column** — they are contract-wide, not version-snapshotted. A new
version's (re-)extraction overwrites/regenerates these rows in place
(`app/ai/pipeline.py`); there is no historical per-version copy to
recover. This is a pre-existing, structural fact across the whole
intelligence layer, not something introduced by or fixable within this
audit's "smallest safe fix" scope (adding `version_id` to six tables plus
migrating every read path would be a significant schema change, not a
completeness fix).

What this audit *did* do given that constraint: `build_review_dossier`
already correctly avoids ever *pretending* precision it doesn't have.
When a review is stale (`is_stale: true` — the review's version is no
longer current), the portal now shows an explicit notice that the
obligations/timeline/payments/risk data reflects the **latest** version,
not necessarily what existed when the review was sent — honest framing
instead of silent staleness. `review_comments` (genuinely
review-request-scoped) were already correctly isolated per review.

## 4. Root cause of RTL/LTR mixing

No direction handling existed at all for extracted/bilingual text —
quotes, AI-picked explanations, and `explanation_ar` fields were either
never rendered (Risks/Timeline, before this fix) or rendered without any
`dir` attribute. The page's own `dir` follows the *viewer's* selected UI
language, which is independent of the *language of each extracted
field* (a contract quote is usually English; a risk `explanation_ar` is
always Arabic; a party name could be either). Fix: every
extracted/bilingual text node (`Bidi` helper component) now carries
`dir="auto"`, letting the browser's Unicode bidi algorithm resolve each
element from its own first strong character — the standard, JS-free
solution for per-field-homogeneous-but-page-heterogeneous content
(confirmed this is the intended approach per
`backend/app/services/bidi_text.py`'s own docstring: "display uses ...
Unicode bidi", not a backend-computed direction).

## 5. Loading / empty / error states

- **Loading:** unchanged — top-level spinner text while the one dossier
  fetch is in flight (single API call backs the whole page; there is no
  per-tab fetch to distinguish).
- **Error ("failed to load"):** was showing the raw error code as the
  only text (e.g. literally `review_not_found`) with no framing. Now
  shows a translated "Failed to load the review" heading with the raw
  code underneath (kept for support/debugging), plus Retry — clearly
  distinct from "this tab has no data."
- **Empty ("no extracted data"):** was one generic `common.empty`
  string shared by every tab. Now each tab has its own specific,
  accurate empty-state sentence (e.g. "No obligations were extracted
  from this contract.") so a reviewer can tell "nothing here" from
  "something broke," per tab.

## 6. `LifecycleService` / lifecycle stages — untouched

Confirmed by diff: this change touches only `reviews.py`'s dossier-
building functions (`build_risk_summary`, `_serialize_obligations`,
`build_review_dossier`, `_comparison_unavailable_reason`) plus the
frontend rendering. No file under `backend/app/services/lifecycle.py`
was modified, no `LifecycleService.transition()` call site was added or
changed, and no `contract.stage` write was touched.

## 7. Files changed

**Backend**
- `backend/app/services/reviews.py` — `build_risk_summary()` rewritten
  to source from `risk_engine.serialize_risk()`; `_serialize_obligations()`
  enriched; new `_comparison_unavailable_reason()`;
  `build_review_dossier()` returns `comparison_unavailable_reason`.
- `backend/tests/test_review_portal_data_completeness.py` (new) — 8
  persisted tests, one per finding above.

**Frontend**
- `frontend/lib/types.ts` — `ReviewPortalObligationRow`,
  `ReviewPortalRiskItem`, `ReviewPortalRisks`, updated
  `ReviewPortalPayload` (`notices` now typed, `comparison_unavailable_reason`
  added).
- `frontend/app/review/[token]/page.tsx` — Risks/Obligations/Timeline/
  Payments tabs rewritten to render the enriched fields; `Bidi`/`SourceRef`
  helpers; tab-specific empty states; translated load-failure state;
  stale-review notice.
- `frontend/lib/i18n.tsx` — ~25 new EN+AR keys under `review.portal.*`
  and `obligation.status.*`.
- `frontend/app/review/[token]/page.vitest.tsx` (new) — 15 tests, one or
  more per tab covering enrichment, empty states, RTL isolation, and the
  stale-review notice.

## 8. Migration impact

None. No schema change — every fix reads columns that already exist
(`Obligation.title/beneficiary/trigger_type/trigger_event/
completion_criteria/suggested_evidence`, `RiskFinding.*`,
`Contract.parent_main_contract_id`).

## 9. Test / build results

```
$ pytest tests/test_review_portal_data_completeness.py tests/test_reviews.py \
         tests/test_review_lifecycle_integration.py -q
37 passed  (0 new failures)

$ pytest -q   # full backend suite
414 passed, 2 failed
```
The 2 failures are the same pre-existing, already-documented, unrelated
issues from prior sessions (`test_review_resend_cooldown_is_deterministic`
— stale Task-3 test; `test_dashboard_summary_query_ceiling` — DB-row-count-
sensitive, unrelated file). Neither file was touched by this change.

```
$ npx vitest run          # full frontend suite
Test Files  14 passed (14)
     Tests  117 passed (117)

$ npx tsc --noEmit        # clean, no output

$ npm run build           # ✓ Compiled successfully, 19/19 static pages

$ python3 scripts/golden_path_smoke.py
checks_total: 73, checks_passed: 73, checks_failed: 0, zero residue
```

## 10. Manual verification with the same real contract

Re-uploaded the identical synthetic contract used to reproduce the
original bug report (same text: 60-day notice clause with an
unresolvable base date, 0.5%/week penalty clause), rebuilt its risk
findings, and re-fetched the public portal against the fixed backend:

```
internal risk score/level: 2 low
public  risk score/level:  2 low     <- now match exactly (was: risks.items=[] equivalent, "No data yet")
comparison: None  reason: not_linked  <- accurate; contract has one version, but that is NOT why comparison is empty
obligation fields present: [..., 'beneficiary', 'completion_criteria', 'suggested_evidence', 'title', 'trigger_event', 'trigger_type']
timeline deadline fields present: [..., 'calculation_explanation', 'calculation_explanation_ar', ...] (already present, now rendered)
```

Contract deleted after verification (zero residual rows).

## 11. Which empty states are legitimate

- **Payments tab empty** for the audited contract: legitimate — 0
  milestones exist in the database for either the internal or public
  endpoint (an extraction-accuracy question, not a portal bug — see §2).
- **Comparison tab empty**: legitimate for any standalone contract not
  linked as a main/subcontract pair — unrelated to version count,
  confirmed by the new `not_linked` reason and a dedicated test with a
  linked-but-uncompared pair proving the two cases are distinguishable.
- **Risks tab empty**: only legitimate when `risk_engine.serialize_risk()`
  genuinely returns zero findings *and* there are no penalty/timeline/
  comparison supplementary items — i.e., only when there is truly nothing
  to show, not (as before) whenever the ad-hoc heuristic happened not to
  fire.
