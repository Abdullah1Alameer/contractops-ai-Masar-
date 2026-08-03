# ContractOps AI — Full System Test Report

**Date:** 2026-08-04  
**Branch tested:** `feature/timeline-payment-tracker` (local)  
**Environment:** Current `.env` + Supabase PostgreSQL; backend `http://127.0.0.1:8000`; frontend build verified (no browser automation).  
**Evidence artifact:** [scripts/qa_results.json](../scripts/qa_results.json) (full AI run); re-run with `python3 scripts/qa_api_smoke.py` (add `--skip-ai` to avoid OpenAI cost).

---

## 1. Executive Summary

| Item | Result |
|------|--------|
| **Overall status** | **Demo-ready for hackathon** with manual UI walkthrough required |
| **Demo readiness (automated + static)** | **~88%** (browser E2E not executed) |
| **Critical blockers** | **0** for core backend flows |
| **High-risk issues** | 2 (placeholder `/api/dashboard`; payment milestone PATCH not hit on QA subcontract sample) |
| **Automated tests** | **49/49 pytest pass**; **22/22** API happy-path; **12/12** negative API; **11/11** DB integrity (AI run) |
| **Frontend build** | Pass (`npm run build`, ~9.5s) |
| **Typecheck** | Pass (`npx tsc --noEmit`) |

**Phase 1 — Environment**

| Check | Result |
|-------|--------|
| `OPENAI_API_KEY`, `AI_MODEL`, `DATABASE_URL`, `DEMO_TOKEN` | SET (values not logged) |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_TOKEN` | SET in `frontend/.env.local` |
| `.env` gitignored | Yes (`.gitignore:1`) |
| Migrations `_migrations` | `001`–`006` applied |
| `import app.main` | OK |
| Frontend production build | OK |

---

## 2. Test Matrix (by feature)

| Feature | Test case | Expected | Actual | Pass | Evidence |
|---------|-----------|----------|--------|------|----------|
| F0 RTL/i18n | `document.documentElement.dir` toggles AR/EN | RTL/LTR | Code in `frontend/lib/i18n.tsx` | **Partial** | Static only; **UI not executed** |
| F1 Upload | POST valid DOCX | 201 | 201 | Pass | `qa_api_smoke.py` |
| F1 Upload | Oversize / corrupt / .txt | 413/422/400 | Match | Pass | negative matrix |
| F1 Extract | Subcontract DOCX | `status=ready`, clauses/obligations | 6 obligations, 10 clauses, ~22s | Pass | `ai.supported_extract` |
| F1.5 Classification | Employment DOCX | `supported=false`, no obligations | `supported=false`, category Employment, 0 obligations | Pass | `ai.employment` |
| F1 Obligations | PATCH status | 200 | 200 | Pass | endpoint matrix |
| F1 Raw / source | GET `/raw?page=1` | 200 + text | 200 | Pass | endpoint matrix |
| F2 Deadlines | GET when not ready | 409 | 409 | Pass | negative |
| F2 Deadlines | GET + rebuild ×2 | Stable row count | 3→3→3 | Pass | `db_integrity` |
| F2 Events | POST event | 201 | 201 | Pass | endpoint matrix |
| F2 Demo clock | GET/POST today | Persist ISO date | 200/200 | Pass | endpoint matrix |
| F3 Payments | GET milestones | 200 | 200 | Pass | endpoint matrix |
| F3 Payments | PATCH paid/precondition | 200 + persist | **Not run** on QA sub (0 milestones) | **Partial** | Unit tests cover engine |
| F4 Flow-down | POST valid pair | 200, real findings | 23 findings, ~20s | Pass | `ai.flowdown` |
| F4 Flow-down | Rerun | Same finding count | 23→23 | Pass | `db_integrity` |
| F4 Flow-down | Wrong pair / same id | 422 | 422 | Pass | negative |
| F5 Dashboard | UI KPIs from real data | No placeholder banner | Client aggregation in `app/dashboard/page.tsx` | Pass | Static + no `apiWithMeta` usage on page |
| F5 Dashboard | GET `/api/dashboard` | Real aggregation | **Placeholder** `X-Placeholder: true` | **Known** | Not used by current UI |
| Delete | CASCADE + 404 after delete | Empty children | Pass | `delete cascade` in JSON |
| Auth | Missing Bearer | 401 | 401 | Pass | negative |

---

## 3. Endpoint Matrix

| Method | Path | Expected | Actual | Schema / notes | DB effect | Result |
|--------|------|----------|--------|----------------|-----------|--------|
| GET | `/healthz` | 200 | 200 | `{ok:true}` | None | Pass |
| GET | `/api/contracts` | 200 | 200 | Array of list items | Read | Pass (~1127 ms) |
| POST | `/api/contracts` | 201 | 201 | `{id,status}` | Insert contract + storage | Pass |
| GET | `/api/contracts/{id}` | 200 | 200 | ContractDetail shape | Read | Pass (~669 ms) |
| DELETE | `/api/contracts/{id}` | 204 | 204 | — | Cascade delete + file remove | Pass |
| POST | `/api/contracts/{id}/extract` | 200 | 200 | Pipeline report | Clauses, extractions, obligations, rebuild hooks | Pass (AI) |
| GET | `/api/contracts/{id}/obligations` | 200 | 200 | ObligationRow[] | Read | Pass |
| PATCH | `/api/obligations/{id}` | 200 | 200 | Updated row | Update | Pass |
| GET | `/api/contracts/{id}/raw` | 200 | 200 | page text + char_start | Read | Pass |
| GET | `/api/contracts/{id}/deadlines` | 200/409 | Match | DeadlinesResponse | Read / gate | Pass |
| POST | `/api/contracts/{id}/deadlines/rebuild` | 200 | 200 | DeadlinesResponse | Replace deadlines | Pass |
| POST | `/api/contracts/{id}/events` | 201 | 201 | Event + deadlines | Insert event, rebuild | Pass |
| GET | `/api/contracts/{id}/milestones` | 200 | 200 | MilestonesResponse | Read | Pass (~964 ms) |
| POST | `/api/contracts/{id}/milestones/rebuild` | 200 | 200 | MilestonesResponse | Replace milestones | Pass |
| PATCH | `/api/milestones/{id}` | 200 | 200 | PaymentMilestoneRow | JSONB preconditions / paid | **Not exercised in smoke** (0 milestones on sub DOCX) |
| GET | `/api/flowdown/contracts` | 200 | 200 | main[] + sub[] | Read | Pass |
| GET | `/api/flowdown?main_id&sub_id` | 200 | 200 | FlowdownResponse | Read cache | Pass (~1297 ms) |
| POST | `/api/flowdown` | 200 | 200 | FlowdownResponse | Upsert findings | Pass (AI) |
| GET | `/api/dashboard` | 200 | 200 | Static JSON | **None (placeholder)** | Pass HTTP; **not real data** |
| GET/POST | `/api/demo/today` | 200 | 200 | `{today}` | demo_settings | Pass |
| GET | `/api/hijri` | — | — | Not in smoke run | — | **Not executed** |

**Placeholder audit:** Only `GET /api/dashboard` returned `X-Placeholder: true` ([placeholders.py:256-264](../backend/app/routers/placeholders.py)). F2/F3/F4 deadline, milestone, and flow-down routes are **real**.

---

## 4. Data Flow Results

| Flow | Status | Notes |
|------|--------|-------|
| **A — Upload → extract → DB → UI** | **Working** | `contracts.py` upload → `run_extraction` → models; frontend upload → extract → redirect ([upload/page.tsx](../frontend/app/upload/page.tsx)) |
| **B — Timeline** | **Working** | Notice/extractions → `deadlines.build_deadlines_for_contract` → GET deadlines → `DeadlineTimeline.tsx` |
| **C — Payment tracker** | **Partial** | Engine + PATCH wired; QA subcontract had **0 milestones** after extract — demo should use a contract with payment rows (e.g. seeded main PDF) |
| **D — Flow-down** | **Working** | `run_flowdown` → `flowdown_findings` → GET/POST API → Flowdown* components |
| **E — Dashboard** | **Working** | Client-side aggregation in [dashboard/page.tsx](../frontend/app/dashboard/page.tsx); does **not** call placeholder `/api/dashboard` |

---

## 5. Workflow Results

| Workflow | Status | Notes |
|----------|--------|-------|
| 1 Valid contract (full UI) | **Partial** | Backend steps verified via API; **UI not executed** |
| 2 Unsupported contract | **Partial** | Employment blocked via API; UI warning component exists — **not clicked** |
| 3 Flow-down | **Partial** | POST + citations API verified; dual SourceViewer — **not executed** |
| 4 Delete contract | **Partial** | DELETE + cascade verified; confirm/toast — **not executed** (code uses `useConfirm`) |
| 5 Language toggle | **Partial** | i18n + `dir` on `<html>` — **not executed** |
| 6 Dashboard | **Partial** | Aggregation logic + real GETs — **not executed** in browser |

---

## 6. Bugs Found

| ID | Severity | Summary | Reproduction | Root cause | Fix | Retest |
|----|----------|---------|--------------|------------|-----|--------|
| QA-1 | **Medium** | QA smoke left orphan contract on Arabic filename upload | Run smoke before cleanup fix | Second upload overwrote `qa_id` | **Fixed:** smoke script deletes extra upload id | `--skip-ai` smoke pass |
| QA-2 | **Low** | `GET /api/dashboard` returns fake KPIs | Call endpoint | F5 backend not implemented | **No fix** (frontend bypasses); document for API consumers | N/A |
| QA-3 | **Medium** | Payment PATCH not covered in integration smoke | Extract `sub_contract.docx` | Sample has 0 milestones in extract | **Recommendation:** demo with contract that has milestones | pytest payment engine pass |
| QA-4 | **Low** | `npm audit` reports Next.js advisories | `npm audit --production` | Dependency version | Report only; upgrade out of scope pre-demo | N/A |

No **blocker** or **critical** defects found in executed tests.

---

## 7. Known Limitations (expected, not bugs)

- Demo auth: single shared `DEMO_TOKEN` (not production RBAC).
- Dashboard API still placeholder; **UI uses client aggregation** (by design for this release).
- Dashboard N+1 calls (list + per-contract deadlines/milestones) — slow on large tenants (~1s+ per call observed on Supabase latency).
- Flow-down coverage on dashboard uses first cached Main+Sub pair only.
- Arabic **contract text** extraction not live-tested this cycle (only Arabic **title** DB round-trip + RTL code path).
- Scanned PDF path not live-tested (upload rejects with `scanned_pdf_not_supported` — negative path for corrupt PDF only).
- Browser workflows, keyboard/focus, toasts, and modals: **manual checklist required**.
- `hijri-converter` deprecation warning in pytest (use `hijridate` later).

---

## 8. Demo Readiness Checklist

| Area | Status |
|------|--------|
| Upload | ✅ Ready (API + validation) |
| Classification | ✅ Ready (employment blocked) |
| Extraction | ✅ Ready (sub DOCX tested) |
| Obligations | ✅ Ready |
| Click-to-source | ✅ Ready (`/raw` + offsets; UI manual) |
| Timeline | ✅ Ready |
| Demo clock | ✅ Ready |
| Payment Tracker | 🟡 Needs attention (use contract **with** milestones in demo) |
| Flow-Down | ✅ Ready |
| Dashboard | ✅ Ready (UI aggregation; ignore `/api/dashboard`) |
| Arabic | 🟡 Needs attention (RTL manual pass; AR contract optional) |
| English | ✅ Ready |
| Delete confirmation | 🟡 Needs attention (wired in code; manual click) |
| Toasts | 🟡 Needs attention (manual) |
| Production build | ✅ Ready |

---

## 9. Exact Demo Script (safe sequence)

1. Start backend (`uvicorn app.main:app`) and frontend (`npm run dev`). Confirm `.env` / `.env.local` loaded.
2. **Language:** Show AR header toggle → switch EN → back AR (watch `dir`).
3. **Dashboard:** Open `/dashboard` — confirm KPIs load (skeleton then numbers), no WIP banner; click a panel link to a contract.
4. **Upload:** Upload `database/demo_contracts/sub_contract.docx` (or existing seeded subcontract PDF if milestones needed).
5. Wait for extract; open contract detail — summary cards, obligations tab, click **clause** → SourceViewer highlight.
6. **Timeline tab:** Show deadlines; open **demo clock**, shift date, confirm severity/count changes.
7. **Payments tab:** Use a contract **with milestones** (seeded main PDF if sub has none) — tick precondition → claimable → mark paid → refresh tab.
8. **Flow-down:** `/flowdown` — select Main + Sub from dropdowns → Run → show KPI row + findings → **View Main/Sub** citations.
9. **Delete:** `/contracts` → Delete → **Cancel** → Delete again → Confirm → success toast; verify row gone.
10. Close with dashboard refresh showing updated counts.

**Avoid live:** second flow-down run during demo (20s+ AI) unless already cached; oversized file upload.

---

## 10. Final Verdict

| Question | Answer |
|----------|--------|
| **Ready for hackathon demo?** | **Yes**, if presenter runs the manual UI checklist once and uses a **milestone-rich** contract for F3. |
| **Fix before sleeping?** | Run through §9 once in the browser (~15 min). Optionally delete any stray `QA-*` or `عقد_اختبار` processing rows. |
| **Can wait until tomorrow?** | Next.js npm audit upgrades; real `/api/dashboard` backend; Playwright smoke; Arabic contract PDF test. |
| **Do not touch anymore?** | Extraction/classification prompts, flow-down schema, payment JSONB persistence fix, dashboard client aggregation, i18n key set. |

---

## Appendix A — Automated commands

```bash
# Phase 2
pytest backend/tests -q          # 49 passed, ~0.8s
cd frontend && npx tsc --noEmit    # pass
cd frontend && npm run build     # pass, ~9.5s

# Phase 3–5 (backend must be running)
python3 scripts/qa_api_smoke.py           # full + AI (~2 min)
python3 scripts/qa_api_smoke.py --skip-ai # fast regression (~1 min)
```

## Appendix B — Performance smoke (ms, Supabase latency)

| Endpoint | ms |
|----------|-----|
| GET `/api/contracts` | 1127 |
| GET `/api/contracts/{id}` | 669 |
| GET `/api/contracts/{id}/deadlines` | 1083 |
| GET `/api/contracts/{id}/milestones` | 964 |
| GET `/api/flowdown` (cached) | 1297 |
| POST `/extract` (AI) | 22055 |
| POST `/flowdown` (AI) | 19931 |
| Frontend `npm run build` | ~9450 |

**Demo note:** First dashboard load may feel slow due to parallel per-contract fetches; warm cache helps.

## Appendix C — Manual UI checklist (NOT EXECUTED)

- [ ] Delete: ESC / click-outside / focus trap / loading on confirm
- [ ] Toast on delete success and upload error
- [ ] All tabs on contract detail
- [ ] Responsive widths 375 / 768 / 1024
- [ ] No console errors / hydration warnings
- [ ] Empty states on dashboard with zero contracts
- [ ] Flow-down loading banner (`motion-safe:animate-pulse`)

## Appendix D — Security static checks

| Check | Result |
|-------|--------|
| `.env` in git | Ignored ✅ |
| Secrets in `.next/static` | No `sk-` / `postgres://` patterns found in grep ✅ |
| Upload filename | `os.path.basename` + UUID prefix ([storage.py](../backend/app/services/storage.py)) ✅ |
| Upload size/type | Server-side in [contracts.py](../backend/app/routers/contracts.py) ✅ |
| SQL injection | SQLAlchemy ORM / parameterized migrations ✅ |
| `window.confirm` / `alert` in frontend | None found ✅ |
| npm audit | Multiple Next.js advisories — **report only** |

---

*Report generated as part of Hackathon QA Cycle. Re-run evidence: `scripts/qa_api_smoke.py` + `scripts/qa_results.json`.*
