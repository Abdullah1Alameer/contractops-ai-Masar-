# Feature 15 — Consent Documents & Performance

## Consent / authorization (Part A)

### Classifier
- Added nine consent/authorization categories to `GENERAL_SUPPORTED_CATEGORIES` (e.g. Employment Screening Consent, Other Legal Consent).
- Updated `CLASSIFIER_SYSTEM` with consent trigger language and explicit still-unsupported personal docs (CV, ID-only, etc.).
- Post-LLM deterministic gate: CV-only and ID-only regex overrides; consent triggers map low-confidence/unknown/personal hits to `Other Legal Consent` with `needs_review=True` and `message=needs_classification_review`.
- New classifier result field: `needs_review` (default false). `category_to_type` returns `None` for consent categories; flowdown eligibility excludes consent set.

### Extraction
- New `backend/app/ai/consent_schema.py` with `CONSENT_EXTRACTION_SCHEMA` and `consent_terms` persistence.
- `run_extraction` branches to `_run_consent_extraction`: no commercial extraction, no obligations, no flowdown; `relationship_type=standalone`, `type=None`.
- Unsupported uploads are **retained** with `status=unsupported` (no file delete) so reclassify/analyze-anyway can run.

### API
- `POST /api/contracts/{id}/reclassify` — sets category, `supported=True`, logs `contract_reclassified`, re-runs extraction.

### Upload UX
- `UnsupportedContractWarning`: compact layout, **Analyze anyway**, reclassify dropdown, collapsible supported list, “Needs classification review” title when message is `needs_classification_review`.
- Upload page passes `contract_id` and wires reclassify.

## Performance (Parts B–K)

### Backend
- `GET /api/dashboard/summary` — KPIs, recent contracts/activity, deadline/payment/review/approval/signature summaries, plus `aggregate` block for legacy dashboard panels (bulk deadline/milestone queries, ≤15 SELECTs per request).
- `GET /api/contracts?include=workflow_summary,current_version` — bulk workflow summary map + optional current version payload.
- Migration `database/migrations/014_perf_indexes.sql` — idempotent indexes on hot FK/status columns.

### Frontend cache
- `frontend/lib/cache.ts` — `useCachedFetch` (dedup, stale-while-revalidate, keepPrevious via `isValidating`, AbortController on unmount), `mutate`, `invalidateByPrefix`, `invalidateContract`.
- Dashboard → `dashboard:summary`; contracts list → `contracts:list` with include param; contract detail → `contract:{id}` + `obligations:{id}`; activity tab → `activity:{id}`.
- Mutations (`reclassify`, review send, approval patch, set current version, obligation toggle) invalidate relevant prefixes.

### UI / shell
- `RefreshingDot` on dashboard revalidation; skeletons only when cached data is null.
- `next/dynamic` for heavy contract tabs (SourceViewer, negotiation, approvals, signature, versions, documents, activity).
- Sidebar: lucide guard comment, explicit `prefetch` on primary routes.
- `next.config.mjs`: `optimizePackageImports` for `lucide-react`; ANALYZE note in file comment.

## Tests
- `backend/tests/test_classifier_consent.py` — consent supported, CV/ID blocked, uncertain consent + reclassify activity.
- `backend/tests/test_dashboard_summary.py` — summary shape, SELECT ceiling (≤15), contracts `include=workflow_summary`.
- **146** backend tests passing (`pytest tests -q`).

## Bundle (after F15 build)
| Route | First Load JS |
|-------|----------------|
| `/dashboard` | 130 kB |
| `/contracts` | 130 kB |
| `/contracts/[id]` | 139 kB |
| Shared | 87.2 kB |

Dashboard no longer imports heavy contract tab panels; detail route split via dynamic chunks.

## Request reduction (dashboard)
- **Before:** `GET /contracts` + 5× activity + N× (deadlines + milestones) + separate review/approval/signature summaries + optional flowdown.
- **After:** single `GET /api/dashboard/summary`.

## Known limitations
- Dashboard deadline/payment aggregates use `date.today()` for bulk serialization (demo clock on dashboard may differ from per-contract F2/F3 views until unified).
- Query ceiling test counts SQLAlchemy SELECT statements only; ORM flush/update from review expiry skipped on dashboard path via `skip_expire=True`.
- Reclassify requires the contract row to still exist (unsupported uploads are kept, not deleted).
