# Feature 10 — Contract Version Control

## Summary

Every contract revision is stored as an **immutable version row**. Existing contracts are backfilled as **v1**. New uploads create v2, v3, … without overwriting prior files. Review, negotiation, approval, and signature workflows stamp a `version_id`; when the current version changes, workflows surface **`is_stale`** so teams restart approval/signature on the latest document.

## Database

- **Migration `013_contract_versions.sql`**
  - `contract_versions` — immutable revision log with `extracted_json`, `hash_sha256`, `is_current`
  - `version_comparisons` — cached diff + AI explanation
  - Nullable `version_id` on `review_requests`, `negotiations`, `approval_workflows`, `signature_requests`
  - Backfill v1 for all existing contracts + link workflows to v1

Run: `backend/.venv/bin/python database/migrate.py`

## Architecture

| Component | Path |
|-----------|------|
| Service | [backend/app/services/versions.py](backend/app/services/versions.py) |
| Router | [backend/app/routers/versions.py](backend/app/routers/versions.py) |
| Models | [backend/app/models.py](backend/app/models.py) (`ContractVersion`, `VersionComparison`) |
| Extraction hook | [backend/app/ai/pipeline.py](backend/app/ai/pipeline.py) → `sync_version_snapshot` |
| Upload hook | [backend/app/routers/contracts.py](backend/app/routers/contracts.py) → `create_initial_version` |

## APIs (Bearer protected)

| Method | Path |
|--------|------|
| GET | `/api/contracts/{id}/versions` |
| POST | `/api/contracts/{id}/versions` (multipart: file, source, change_summary) |
| GET | `/api/contracts/{id}/versions/compare?from_id=&to_id=` |
| POST | `/api/versions/{id}/set-current` |
| POST | `/api/versions/{id}/extract` |
| GET | `/api/versions/{id}/download` |

Contract list/detail add `current_version_number` and `total_versions`.

## Integration (F6–F9)

- **Review** — stamps `version_id`; activity `version_sent_for_review`
- **Negotiation** — stamps `version_id` on analyze
- **Approval** — stamps `version_id` on start; marks version `approved` on completion; `is_stale` on workflow JSON
- **Signature** — stamps `version_id` on create; marks version `signed` on completion; `is_stale` on request JSON

## Frontend

- **Versions** tab — [VersionsPanel.tsx](frontend/components/VersionsPanel.tsx), [CreateVersionDialog.tsx](frontend/components/CreateVersionDialog.tsx)
- Stale banner on Approvals + Signature tabs when `is_stale`

## Manual demo

1. Open a contract → **Versions** tab → confirm **v1** (current).
2. **Create New Version** → upload revised PDF → v2 becomes current after extract.
3. Compare v1 ↔ v2 → structural diff + AI explanation.
4. Start approval on v1, then upload v3 → approval tab shows stale banner.

## Verification

- `pytest backend/tests -q`: **126+** passing
- `npx tsc --noEmit` + `npm run build`: OK

## Known limitations

- Backfill v1 does not populate `extracted_json` until next extract/sync (run extract or open contract after migrate).
- Diff is extraction-field based, not sentence-level PDF redline.
- AI compare requires OpenAI (falls back to short message if unavailable).
- `set-current` repoints `contracts.file_url` for F1–F5 compatibility but does not rewind workflow rows automatically.
- No per-version RBAC or branch merge.
