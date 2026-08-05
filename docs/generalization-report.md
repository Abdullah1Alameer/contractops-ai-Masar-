# ContractOps AI — generalization report

**Scope:** Expand from construction-only positioning to multi-industry commercial contract operations without API rebuild.

## Database

- **Migration `008_generalize_contract_model.sql`:** adds `contracts.relationship_type` (`parent` | `child` | `standalone`) with backfill from legacy `type` (`main` / `subcontract`).
- Applied via `backend/.venv/bin/python database/migrate.py`.

## Backend

| Area | Change |
|------|--------|
| `backend/app/ai/classifier.py` | General supported categories + legacy aliases; personal docs hard-blocked; `relationship_type_for_category`, `is_comparison_eligible`; generalized classifier prompt. |
| `backend/app/ai/pipeline.py` | Sets `relationship_type` after classification. |
| `backend/app/models.py` | `relationship_type` column. |
| `backend/app/routers/contracts.py` | List/detail JSON includes `relationship_type`. |
| `backend/app/ai/prompts.py` | Commercial extraction system prompt (same JSON schema shape). |
| `backend/app/ai/flowdown_prompt.py` | Contract Comparison narrative; expanded category enum; bilingual AR/EN fields preserved. |
| `backend/app/services/flowdown.py` | Eligibility: any two distinct ready supported commercial contracts; pickers share eligible list. |

## Frontend

- `frontend/lib/i18n.tsx` — AR/EN tagline, nav, flowdown (Primary/Related), dashboard KPIs, unsupported messaging, category keys, comparison category labels, timeline/payment tab titles.
- `frontend/lib/utils.ts` — `CATEGORY_TO_KEY` / supported keys for general + legacy labels.
- `frontend/app/layout.tsx` — metadata description generalized.

## Docs

- `README.md` — multi-industry positioning.
- Demo construction seed data unchanged.

## Tests

- **New:** `backend/tests/test_classifier_general.py` (supported/unsupported sets, mappings, comparison eligibility).
- **Updated:** `backend/tests/test_flowdown_engine.py` (same-id rejection, cross-industry pair OK, personal ineligible).
- **Result:** `69 passed` (`pytest backend/tests -q`).

## Build verification

- `npx tsc --noEmit` — OK (via Next build typecheck).
- `npm run build` — OK.

## Known limitations

- Extraction JSON schema keys unchanged (construction-specific optional fields remain in schema; null when absent).
- Comparison API still uses `main_contract_id` / `subcontract_id` field names.
- Flow-down status labels (e.g. “fully flowed down”) retained for API/UI compatibility.
- Live OpenAI runs across 10 document types not automated in CI (cost); unit tests cover gate and eligibility.
