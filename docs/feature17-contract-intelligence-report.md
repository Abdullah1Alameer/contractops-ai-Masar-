# Feature 17 — Contract Intelligence Engines (Corrective)

## Root causes

1. Deadline engine used English regex triggers that did not match real clause text (`before the contract end date`, `commencement date of work`), yielding `trigger_unresolved`.
2. Settlement notices were misclassified as `payment_window` because `purpose` contained “payment”.
3. Payment engine treated empty preconditions + missing due date as `claimable`, double-counting salary components in dashboard totals.
4. Risk score in the UI was a local heuristic (`overdue*15 + pending*2`), not persisted or explainable.
5. Contract header dates (execution, commencement, starting, end) were collapsed; commencement was missing for probation resolution.
6. Due-day-of-month and probation exclusion language existed in `raw_text` but was not used by downstream engines.

## Files changed (high level)

- Migration: `database/migrations/016_contract_intelligence.sql`
- Models: `backend/app/models.py`
- Services: `date_semantics.py`, `temporal_rules.py`, `temporal_inference.py`, `deadlines.py`, `payments.py`, `risk_engine.py`, `negotiation_opportunities.py`, `intelligence.py`
- Extraction: `backend/app/ai/schemas.py`, `prompts.py`, `pipeline.py`
- API: `backend/app/routers/contracts.py`
- Frontend: contract detail page, `DeadlineTimeline`, `PaymentTracker`, `NegotiationOpportunitiesPanel`, `types.ts`, `api.ts`, `i18n.tsx`
- Tests: `test_temporal_rules.py`, `test_contractemp_fixture.py`, `test_risk_engine.py`, `test_negotiation_opportunities.py`, `test_obligation_engine.py`, updates to `test_payment_engine.py`

## contractEmp verification (automated DB, demo today 2026-08-03)

After `POST /api/contracts/{id}/intelligence/rebuild`:

| Item | Result |
|------|--------|
| Renewal notice | 2026-11-05, scheduled |
| Probation end | 2026-02-14, needs_review (excluded days) |
| Settlement after contract end | 2026-11-22, scheduled |
| Settlement after termination | inactive, awaiting_trigger |
| Total wage | 2500 SAR, next due 2026-08-30, scheduled, not claimable |
| Components | role=component, excluded from payment summary totals |
| Risk | explainable breakdown (risk-v2), score from persisted findings |

## Test commands

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build
python database/migrate.py
```

## Demo steps

1. Open contract `contractEmp` → Notice tab: resolved deadlines and rebuild button.
2. Timeline tab: explanations and inactive termination settlement.
3. Milestones tab: total wage scheduled on day 30 with component breakdown.
4. Risk tab: score + “Why this score?” breakdown from API.
5. Negotiation tab: structured opportunities above review-driven negotiation panel.
6. Optional: `POST /api/contracts/{id}/intelligence/rebuild` with selective `targets`.

## Known limitations

- Business-day and holiday calendars are not implemented; business-day offsets and probation holiday adjustments remain provisional + `needs_review`.
- Negotiation opportunities use deterministic clause heuristics, not LLM analysis; no market benchmarks unless playbook data exists.
- Manual browser acceptance was not executed in this session; DB/API verification was.
