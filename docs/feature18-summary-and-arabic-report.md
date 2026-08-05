# Feature 18 — AI Summary + Arabic Document Rendering

## Root causes (verified)

### Issue 1 — Empty AI Summary tab
The tab read `extractions` rows named `contract_summary` / `ai_summary`, but **no backend code ever wrote those fields**. Extraction schema and pipeline had no executive-summary LLM step. This was a missing feature, not a silent failure or naming mismatch.

### Issue 2 — Broken Arabic display
1. **Extraction:** `_looks_garbled()` discarded pdfplumber output (presentation-form Arabic) and kept PyMuPDF `get_text()`, which stored **~1,905 single-character Arabic tokens** in `contracts.raw_text` for contract `12cbe823-d000-4a49-8a32-706959099b82`.
2. **Viewer:** `SourceViewer` rendered that text in a `<pre>` inheriting global `dir="rtl"`, with no PDF renderer and no block-level bidi.

## Fixes

- **`contract_summaries` table** + bilingual JSON summaries with `status` (`not_generated` | `generating` | `ready` | `failed`), idempotent `source_hash`, safe error codes.
- **LLM summary** via `summary_prompt.py` + `services/summary.py`; auto-scheduled after `POST /extract`; manual `POST /summary/generate` (backfill/retry).
- **`GET /contracts/{id}/summary`**, `summary_status` on contract detail.
- **`GET /contracts/{id}/file`** serves original PDF/DOCX bytes (authenticated fetch for PDF.js).
- **`contracts.page_layout` JSONB** + geometry-aware `textextract.py` (pdfplumber words, NFKC + visual RTL-run reorder when presentation forms present, horizontal gap column splits).
- **`POST /contracts/{id}/reextract-text`** re-anchors clauses by quote search.
- **SourceViewer:** PDF.js canvas + bbox overlays; text fallback with `dir="auto"` + `.bidi-plaintext`.
- **`AiSummaryPanel`:** generate / regenerate / retry / poll / bilingual sections with citation jump.

## Re-extraction quality (contract `12cbe823-…`, redacted)

| Metric | Before (DB) | After (new extractor) |
|--------|-------------|------------------------|
| Arabic single-char tokens | 1905 | 108 |
| Avg Arabic token length | 2.30 | 5.03 |
| Page 1 blocks (geometry) | 0 | 70 |

Run **`POST /api/contracts/12cbe823-d000-4a49-8a32-706959099b82/reextract-text`** on a running backend to persist layout + refreshed `raw_text`, then **`POST .../summary/generate`** for backfill.

## APIs changed / added

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/contracts/{id}/summary` | Summary payload + status |
| POST | `/api/contracts/{id}/summary/generate` | Async generate/backfill (`force`) |
| GET | `/api/contracts/{id}/file` | Original document bytes |
| POST | `/api/contracts/{id}/reextract-text` | Re-extract + re-anchor clauses |
| GET | `/api/contracts/{id}/raw` | Adds `blocks`, `width`, `height`, `file_type` |
| GET | `/api/contracts/{id}` | Adds `summary_status`, `summary_is_stale` |

## Database

- Migration **`017_summary_and_layout.sql`**: `contract_summaries`, `contracts.page_layout`.

## Tests executed

```text
backend: 197 passed (pytest -q)
frontend: npx tsc --noEmit — OK
frontend: npm run test — 2 passed (vitest)
frontend: npm run build — OK
```

New backend tests: `test_bidi_text.py`, `test_pdf_geometry.py`, `test_contract_summary.py`.  
New frontend tests: `AiSummaryPanel.vitest.tsx`, `SourceViewer.vitest.tsx`.

## Manual verification (contract `12cbe823-…`)

1. Apply migration `017` (`python database/migrate.py`).
2. `POST /reextract-text` for the contract ID above.
3. Open contract → **Document** tab: PDF pages render (not garbled pre text).
4. **AI Summary** tab → **Generate summary** (or wait after re-extract if auto job ran).
5. Click a citation chip → Document tab opens on cited page; quote panel or highlight appears.
6. Force-fail test: unset `OPENAI_API_KEY`, generate → failed state with safe message and **Retry**.

## Privacy

No personal names, IDs, or financial values from the uploaded contract appear in this report, tests, or logs—only contract UUID and aggregate token statistics.
