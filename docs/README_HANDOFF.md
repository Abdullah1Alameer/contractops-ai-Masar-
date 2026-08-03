# Handoff — F2 / F3 / F4 / F5 teammates

**Read this before writing code.** F0+F1 (AI core) are complete and their API
surface is FROZEN. You build on top without touching `backend/app/ai/`.

## 1. Schema ownership

| Table | Written by | Notes |
|---|---|---|
| `contracts`, `clauses`, `extractions`, `obligations` | **F1 pipeline (frozen)** | read-only for you (except `obligations.status`, patched by the UI) |
| `deadlines`, `events` | **F2** | created empty by migrations |
| `payment_milestones` | **F3** | created empty by migrations |
| `flowdown_findings` | **F4** | created empty by migrations |
| `demo_settings` | shared | demo clock — already implemented for real |

## 2. Where your input data lives (THE handoff point)

The AI pipeline extracts notice periods and payment milestones but does **not**
populate your tables. It stores them in `extractions.value_json`:

```sql
SELECT value_json FROM extractions
WHERE contract_id = :id AND field_name = 'notice_periods';
-- [{purpose, days, clause_ref, quote, page, confidence,
--   clause_id, char_start, char_end, verified}, ...]

SELECT value_json FROM extractions
WHERE contract_id = :id AND field_name = 'payment_milestones';
-- [{seq, label, amount_sar, amount_pct, preconditions:[...], clause_ref,
--   quote, page, confidence, clause_id, char_start, char_end, verified}, ...]
```

Also available the same way: `field_name = 'obligations'` (includes
`due_in_days` for relative deadlines) and `'penalties'`.

Rules:
- `clause_id` points into `clauses` — **carry it into your rows** (`source_clause_id`)
  so the UI can deep-link your deadlines/milestones to the contract text.
- `verified: false` items have NO clause link and confidence ≤ 0.5 — treat as
  needing human review, never render them as a clickable source.
- Date columns on `contracts` (start/end/bond_expiry/warranty_end) are already
  converted to **Gregorian** via hijri-converter. The raw string + calendar live
  in the matching `extractions.value_json` (`{raw, calendar, gregorian}`).
  **Never convert dates with an LLM.**

## 3. Your endpoints (already routed, returning placeholder JSON)

Search `backend/app/routers/placeholders.py` for your `TODO(F2/F3/F4/F5)` block.
Each placeholder returns realistic JSON with header `X-Placeholder: true`; the
frontend already renders it (contract-detail tabs, /dashboard, /flowdown), so
replacing the placeholder with real DB reads lights the UI up with **zero
routing work**. Keep the response shapes.

- F2: `GET /api/contracts/{id}/deadlines`, `POST /api/contracts/{id}/events`
- F3: `GET /api/contracts/{id}/milestones`, `PATCH /api/milestones/{id}`
- F4: `POST /api/flowdown` (the demo subcontract deliberately lacks a
  back-to-back LD clause — your engine must flag it as `missing`)
- F5: `GET /api/dashboard`
- Demo clock (real, ready): `GET/POST /api/demo/today`

## 4. Frozen API surface (F1)

`shared/openapi.json` is the snapshot. Full endpoints:
`POST /api/contracts`, `POST /api/contracts/{id}/extract`, `GET /api/contracts`,
`GET /api/contracts/{id}`, `GET /api/contracts/{id}/obligations`,
`PATCH /api/obligations/{id}`, `GET /api/contracts/{id}/raw?page=n`,
`GET /api/util/hijri?date=`.
Auth: header `Authorization: Bearer <DEMO_TOKEN>` on every route.

## 5. How to run seed + eval

```bash
python database/seed/make_contracts.py   # generate demo .docx + ground_truth.json
# backend running on :8000, then:
python database/seed/seed.py             # reset DB + upload + extract via real API
cd backend && python -m app.ai.eval      # grading table vs ground truth (GO/NO-GO)
```

## 6. Frontend conventions

- ALL UI strings go in `frontend/lib/i18n.tsx` (ar + en keys — no hardcoded text).
- Dates render through `<DualDate date={iso} />` (dual hijri/gregorian).
- Confidence chips: `<ConfidenceChip confidence={x} />` (amber below 0.7).
- Deep-link to contract text: pass `{page, char_start, char_end}` to the
  SourceViewer target (see `app/contracts/[id]/page.tsx`).
