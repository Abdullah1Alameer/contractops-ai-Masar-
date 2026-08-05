# Feature 14 — Version Lineage and Workflow History

## Summary

Turns the Versions tab into a **contract lineage view**: per-version workflow events, transition reasons, risk scores, and deep links to Review / Negotiation / Approval / Signature tabs. No new database migration.

## Backend

| Piece | Path |
|-------|------|
| Lineage aggregation | [backend/app/services/version_lineage.py](backend/app/services/version_lineage.py) |
| API | `GET /api/contracts/{id}/versions/lineage` in [backend/app/routers/versions.py](backend/app/routers/versions.py) |
| Extended list serializer | [backend/app/services/versions.py](backend/app/services/versions.py) → `enrich_version_fields` |
| Activity writes | [pipeline.py](backend/app/ai/pipeline.py), [reviews.py](backend/app/services/reviews.py), [negotiation.py](backend/app/services/negotiation.py), [lifecycle.py](backend/app/services/lifecycle.py), [versions.py](backend/app/services/versions.py) |

### Risk score priority

1. `extracted_json.risk_score`
2. Latest comparison `diff_json.rich.overall_risk_score`
3. Heuristic from clauses / missing extractions / overdue obligations
4. `null` → UI shows “Not calculated”

### Lineage response

- Versions ordered by `version_number`
- `events[]` with stable `event_type`, `event_category`, whitelisted `metadata`
- `transitions[]` with mapped `reason` (e.g. `client_revision` → `client_requested_changes`)
- Legacy activity names aliased (e.g. `approval_workflow_started` → `approval_started`)

## Frontend

| Piece | Path |
|-------|------|
| Lineage view (default) | [frontend/components/contract/VersionLineage.tsx](frontend/components/contract/VersionLineage.tsx) |
| Event drawer + deep links | [frontend/components/contract/EventDetailDrawer.tsx](frontend/components/contract/EventDetailDrawer.tsx) |
| Demo story | [frontend/components/contract/DemoStoryPlayer.tsx](frontend/components/contract/DemoStoryPlayer.tsx) |
| Versions tab | [frontend/components/VersionsPanel.tsx](frontend/components/VersionsPanel.tsx) — Lineage / Cards toggle |
| Query-param navigation | [frontend/app/contracts/[id]/page.tsx](frontend/app/contracts/[id]/page.tsx) |
| Link helper | [frontend/lib/lineageLinks.ts](frontend/lib/lineageLinks.ts) |

Deep link examples:

- `/contracts/{id}?tab=review&review={review_id}`
- `/contracts/{id}?tab=negotiation&item={negotiation_id}`
- `/contracts/{id}?tab=approvals&workflow={workflow_id}`
- `/contracts/{id}?tab=signature&request={signature_request_id}`

## Verification

- `pytest backend/tests -q`: **135** passing
- `npx tsc --noEmit` + `npm run build`: OK

## Manual demo

1. Open contract → **Versions** → default **Lineage** view with transitions and expandable events.
2. Click an event → drawer → **Open in workflow**.
3. **Lifecycle story** → step through real events; final presenter note in AR/EN.
4. Switch to **Cards** → rich status pills, risk, last activity.
5. Create version → **Change reason** + required summary.

## Known limitations

- Event-to-version fallback uses timestamps when `metadata.version_number` is missing on old rows.
- `approval_marked_stale` / `signature_marked_stale` one-time logs deferred (stale still computed via `is_stale`).
- Demo story skips missing steps; does not appear on public review/sign pages.
