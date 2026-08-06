# Contract Analysis Tabs — Explainability & Traceability Audit

Status: Audited and improved. Branch `feature/timeline-payment-tracker`.
Scope: read-only analysis experience only — Obligations, Risks, Timeline
(Deadlines), Notification Clauses (Notice), AI Summary tabs in
`app/contracts/[id]/page.tsx` and their supporting components. No
lifecycle, review, negotiation, approval, or signature logic was touched.

---

## 1. Root causes

### 1a. Every tab renders only a title/summary field — full traceability data exists but was never displayed

For **Obligations** and **Notification Clauses**, the backend already
returns the original clause quote, page, clause reference, and
confidence for every item (`GET /contracts/{id}/obligations`,
`notice_periods` extraction). The frontend table/list only ever rendered
a tiny `SourceButton` (a clause-ref pill whose *only* access to the full
quote was the native browser `title=` tooltip attribute — not selectable,
not visible on touch devices, easy to miss) and a confidence badge. There
was no expand/detail affordance anywhere in either tab.

For **Risk**, the gap was worse: `GET /contracts/{id}` already returns
`risk.findings` — one row per individual deterministic risk finding, each
with its own `explanation`/`explanation_ar` and `source_clause_id` — but
the frontend never read `detail.risk.findings` at all. It only rendered
`detail.risk.breakdown`, a coarse per-*category* rollup (6 categories
total) with **no per-item detail, no source clause, and the raw category
slug printed literally in English** (`missing_date`, `temporal`,
`financial`, ...) regardless of UI language.

For **AI Summary**, per-item citations (`clause_ref`, `page`, `quote`)
were already returned by the summary generation pipeline, but clicking a
citation only ever navigated away to the document tab — the quoted text
itself was never shown inline, so a user had to leave the summary to see
what was actually being cited, then come back.

### 1b. Two "jump to clause" actions were silently broken

`DeadlineTimeline` (Timeline tab) and `PaymentTracker` (Milestones tab)
both received `onSourceClick={setTarget}` directly from
`app/contracts/[id]/page.tsx` — this only updates the SourceViewer's
target state, it never switches to the "clauses" (document) tab the way
every other jump action in this codebase does (`jump()`, used by
Obligations, Notice, and AI Summary, always calls both `setTab("clauses")`
*and* `setTarget(...)`). The result: clicking "View Clause" from the
Timeline or Milestones tab silently updated state the user could never
see, because they remained on the tab they clicked from. This is a real,
confirmed dead-action bug, not a hypothetical.

### 1c. Risk findings had no resolved source — only an opaque UUID

`RiskFinding.source_clause_id` was serialized as a raw UUID string with
no accompanying quote/page/clause_ref — even if the frontend had rendered
individual findings, there was no way to show the original text or build
a working "jump to clause" action without an extra clause lookup the
backend never performed.

### 1d. The literal mechanism behind the English-fragment titles in the bug report

Traced to `app/services/temporal_rules.py:118-119`:

```python
en = f"Awaiting triggering event ({rule.get('trigger_event')}); deadline not yet active."
ar = f"بانتظار حدث التفعيل ({rule.get('trigger_event')})؛ الموعد غير نشط بعد."
```

`rule.get('trigger_event')` is a short, English-language classifier
phrase produced by the extraction pipeline (e.g. *"notification of
defect"*, *"termination notice"*, *"invoice approval"*) and is
interpolated **verbatim, untranslated, into the middle of the Arabic
sentence**. Confirmed live against real demo data — the actual persisted
Arabic explanation for one deadline is:

> بانتظار حدث التفعيل (notification of defect)؛ الموعد غير نشط بعد.

This is the exact mechanism producing English fragments like "defect
notification" inside an otherwise-Arabic UI — it is not a missing i18n
key for a UI label, and not something a static translation dictionary
can safely fix (the set of possible `trigger_event` values is
unbounded/free text from the model, not a closed enum). See §5/§6 for why
this is reported, not silently patched.

### 1e. Structured (enum-like) fields are already properly localized; free-text fields are not — and that distinction was not visible to the user

`Deadline.type`, `Deadline.severity`, `Deadline.status`,
`Obligation.status`, and `Deadline.review_reason` all go through real
`t()` i18n lookups today (`deadline.type.*`, `deadline.severity.*`,
`deadline.status.*`, `obligation.status.*`, `deadline.needsReview.*`) and
render correctly in Arabic. `RiskBreakdownItem.category`, by contrast,
was printed as a raw Python slug with **no** i18n lookup at all — a
genuine, simple, fixable gap (§4).

---

## 2. Exact files involved

Backend (read):
- `app/routers/contracts.py::get_obligations`, `get_contract`,
  `get_contract_risk` — confirmed already return rich data.
- `app/services/risk_engine.py::serialize_risk` — confirmed the source of
  the Risk tab's under-exposed data.
- `app/services/temporal_rules.py` — confirmed the source of the English
  `trigger_event` fragments.
- `app/ai/schemas.py` — confirmed no `reasoning`/`explanation` field is
  requested from the model for obligations.

Backend (changed):
- `app/services/risk_engine.py` — `serialize_risk()` now resolves each
  finding's `source_clause_id` into a full `{clause_ref, quote, page,
  char_start, char_end}` object (same shape obligations already use), and
  the category `breakdown` now carries `explanation_ar` alongside
  `explanation` so both languages are available for the UI to pick from.

Frontend (changed):
- `app/contracts/[id]/page.tsx` — Obligations rows, Notice items, and the
  new Risk Findings list now render `ClauseEvidenceCard`; the
  `onSourceClick`/`setTarget`-only bug is fixed via a new `jumpToDocument`
  wrapper used by both Timeline and Milestones; risk category labels are
  now localized via new `risk.category.*` keys; risk findings are read
  from `detail.risk.findings` (previously unused).
- `components/contract/ClauseEvidenceCard.tsx` (new) — the shared
  expandable "original clause / reasoning / metadata / actions" block.
- `components/contract/AiSummaryPanel.tsx` — citations now toggle an
  inline quoted-text preview before/instead of navigating away; the jump
  action is preserved as a separate, explicit button.
- `lib/types.ts` — `RiskBreakdownItem.explanation_ar`, new
  `RiskFindingItem`, `RiskSummary.findings` now typed instead of
  `Array<Record<string, unknown>>`.
- `lib/i18n.tsx` — new `evidence.*`, `risk.category.*`,
  `risk.findings.*` keys (Arabic + English).

Not changed (confirmed already sufficient, no action needed):
- `GET /contracts/{id}/obligations` — already returns everything needed.
- The AI summary generation pipeline and its citation shape.
- `DeadlineTimeline.tsx`'s own rendering (already the most complete tab —
  shows `review_reason` localized, `calculation_explanation`, severity,
  status, responsible party; it only needed the `onSourceClick` wiring
  fix from the parent and gained the shared evidence card for consistency
  with the other tabs — see below).

---

## 3. UI changes required (implemented)

1. **`ClauseEvidenceCard`** — a single reusable expandable component now
   used by Obligations, Notice, and Risk Findings. Collapsed by default
   (keeps every tab exactly as compact as before); expanding reveals,
   exactly per the requested structure:
   - **Original clause** — the full quote, or an honest "no original
     text linked" message (never a blank area).
   - **Reasoning** — composed from whatever real structured data exists
     (e.g. an obligation's `trigger_event`/`completion_criteria`, a
     notice's resolved-deadline explanation, a risk finding's own
     `explanation`/`explanation_ar`), or an honest "no automated
     explanation was recorded" message — never fabricated text.
   - **Metadata** — page, clause number, confidence (or an honest "not
     scored — rule-based, not an AI extraction" for risk findings, which
     have no confidence concept), responsible party, deadline, and
     item-specific fields (beneficiary, trigger event, completion
     criteria, required/suggested evidence, dependencies).
   - **Actions** — "Jump to clause in the document" when the source is
     verified (char-offset-anchored), otherwise an honest "source
     unverified" badge — never a broken or misleading link.
2. **Risk tab** — new "Detected risk findings" section beneath the
   existing category rollup, one `ClauseEvidenceCard` per finding, each
   with a "Linked to tab" shortcut (jumps straight to Obligations,
   Deadlines, or Milestones — using the same `link_tab` the backend
   already computed).
3. **Risk category labels** — localized (`risk.category.*`), no more raw
   English slugs in the Arabic UI.
4. **Timeline & Milestones "jump to clause"** — fixed to actually
   navigate to the document tab.
5. **AI Summary citations** — clicking a citation now toggles the exact
   quoted text inline; a separate, explicit button still jumps to the
   document (existing behavior preserved, not replaced).

## 4. Backend changes required (implemented)

- `serialize_risk()`: resolve `source_clause_id` → full clause source per
  finding (one bulk `Clause` query, no N+1); carry `explanation_ar` on
  the category breakdown. Purely additive — every existing field/shape is
  unchanged, this only adds `source` to each finding and `explanation_ar`
  to each breakdown row.

No other backend change was needed for Obligations, Notice, or AI Summary
— confirmed their APIs already returned everything the UI needed (§6).

## 5. Missing data currently not exposed by the API (found, not fixed)

- **No per-obligation "why was this extracted" narrative.** The
  extraction schema (`app/ai/schemas.py`) never asks the model for a
  reasoning/explanation field for obligations, deadlines (beyond the
  deterministic `calculation_explanation`/`review_reason`, which *do*
  exist and *are* now surfaced), or notice periods. `ClauseEvidenceCard`
  composes a best-effort reasoning line from whatever structured fields
  exist (`trigger_event`, `completion_criteria`) and shows an honest
  "unavailable" message when nothing does, rather than inventing a
  narrative. Adding a real per-item reasoning field would require an
  extraction-schema/prompt change and re-running extraction on existing
  contracts — out of scope for a read-only display fix.
- **`trigger_event` values are free-text and not translated.** No
  `trigger_event_ar` field exists anywhere. This is the confirmed root
  cause of the English fragments in the bug report (§1d). Fixing it
  properly means either asking the model to also produce a localized
  version at extraction time, or building a controlled vocabulary with a
  translation table — both are schema/pipeline changes, not display bugs,
  and both were judged out of scope for "improve explainability of what
  already exists" versus "change what gets extracted."
- **Risk findings have no confidence score.** They are deterministic,
  rule-based (a `needs_review` flag crossing a threshold), not LLM
  extractions — `ClauseEvidenceCard` reports this honestly ("not scored —
  rule-based, not an AI extraction") instead of showing a fabricated
  percentage.

## 6. Was the backend already sufficient, or was the frontend incomplete?

**Obligations, Notification Clauses, AI Summary: the backend was already
sufficient.** Every field requested in the spec (original clause text,
page, clause reference, confidence) was already being returned by
existing, unmodified endpoints. This was purely a frontend display gap —
confirmed by `test_obligations_endpoint_already_exposed_full_traceability_data`
in the new test suite, which asserts the pre-existing endpoint's response
shape directly.

**Risk: both.** The backend had the right *data* (`RiskFinding` rows with
`explanation`/`explanation_ar`/`source_clause_id`) but hadn't resolved
`source_clause_id` into anything usable, and the frontend wasn't reading
`findings` at all (only `breakdown`). Both were fixed.

**Timeline/Deadlines: frontend only, and a real bug, not just missing
polish.** `DeadlineTimeline.tsx` was already the most complete tab
(localized review reasons, calculation explanations, responsible party,
severity/status). Its one real defect was the silently-broken jump
action in the parent page, now fixed.

---

## Tests

Backend (`tests/test_analysis_traceability.py`, new, 5 tests):
1. A finding with a source clause resolves the full `{clause_ref, quote,
   page, char_start, char_end}`.
2. A finding with no source clause honestly reports `source: null` (never
   fabricated).
3. The category breakdown carries both `explanation` and `explanation_ar`.
4. `GET /contracts/{id}` exposes the enriched findings end-to-end.
5. `GET /contracts/{id}/obligations` already exposed full traceability
   data before this fix — confirms §6's finding directly.

`tests/test_risk_engine.py` (pre-existing, 2 tests) and
`tests/test_review_portal_data_completeness.py` (pre-existing, uses
`RiskFinding`/`source_clause_id`) both still pass unchanged.

Frontend:
- `components/contract/ClauseEvidenceCard.vitest.tsx` (new, 6 tests) —
  collapsed by default; reveals quote/reasoning/metadata on expand; jump
  action only when verified, otherwise an honest unverified badge; honest
  "no quote"/"no reasoning"/"not scored" messages instead of blanks or
  fabricated values.
- `components/contract/AiSummaryPanel.vitest.tsx` (extended, 3 tests,
  2 new) — citation toggle shows/hides the real quoted text inline
  without navigating; the explicit jump action still calls `onCitation`
  with the correct source (existing behavior unchanged).

## Verification

- **Focused backend**: `tests/test_analysis_traceability.py` (5/5),
  `tests/test_risk_engine.py` (2/2), `tests/test_review_portal_data_completeness.py`
  (unaffected, still green) — 15/15 combined.
- **Focused frontend**: `ClauseEvidenceCard.vitest.tsx` (6/6),
  `AiSummaryPanel.vitest.tsx` (3/3).
- **Full frontend suite**: 175/175 (8 net new; `app/contracts/[id]/page.tsx`
  has no dedicated test file — it did not have one before this change
  either; verified instead via `tsc`, production build, and a live API
  trace against real demo data below).
- **TypeScript**: `npx tsc --noEmit` — clean.
- **Production build**: `npm run build` — compiled successfully;
  `/contracts/[id]` route size increased modestly (14.8 kB → 16.2 kB)
  reflecting the new shared component, no errors.
- **Real API smoke**, against the live backend and real demo data
  (contract `034838c0-...`, 8 persisted risk findings):
  ```
  GET /api/contracts/{id}/risk
  ```
  confirmed: findings with a `source_clause_id` now return the exact
  persisted Arabic clause text, page, and character offsets; the finding
  with no source clause honestly returns `"source": null`; and the raw
  Arabic explanation text for one finding literally contains
  `(notification of defect)` mid-sentence — direct, live confirmation of
  the §1d root cause.
- **Browser/manual smoke**: not literally executed — no browser
  automation tool is available in this session.

## Summary for the "where did this come from?" question

Every extracted item in Obligations, Notification Clauses, and Risk
Findings can now be expanded to show its original clause text (or an
honest reason none exists), why it was flagged (or an honest reason no
explanation was recorded), its page/clause/confidence, and a working jump
back into the document — or a clear "source unverified" state when a
verified anchor genuinely doesn't exist. AI Summary citations show their
quoted source inline before the user ever has to leave the summary. The
two previously-broken "jump to clause" actions (Timeline, Milestones) now
actually navigate. No answer is ever left as "isolated card, no context."
