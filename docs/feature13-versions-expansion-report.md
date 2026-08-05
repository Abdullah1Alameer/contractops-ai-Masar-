# Feature 13 — Contract Version Control Expansion

## Summary

Builds on Feature 10 with a **rich AI comparison rubric** (`schema_version: 2`), **workflow-aware version cards**, a **lifecycle timeline**, **split-view diff UI**, and **stale-restart UX** on Review and Negotiation. No new database migration.

## Backend

### Rich compare (`backend/app/services/versions.py`)

- `COMPARE_SCHEMA` v2: executive summary, overall risk score, recommendation, eight change buckets, added/removed/modified clauses.
- Cached comparisons invalidate when `diff_json.schema_version != 2` (regenerate in place).
- Deterministic `_fallback_rich()` when OpenAI is unavailable.
- Compare response adds `from_extracted_json`, `to_extracted_json`, version numbers.
- Activity: `ai_comparison_generated`, `version_restored`, `current_version_changed`, `version_approved`, `version_signed`.

### Version serialization

- `serialize_version(v, db)` adds `review_status`, `approval_status`, `signature_status`, `restored_by`, `restored_at`, `extracted_json`.

### Stale flags

- `serialize_review_request` → `is_stale`, `version_id`.
- `serialize_negotiation(n, db)` → `is_stale`, `version_id`.

## Frontend

| Area | Path |
|------|------|
| Lifecycle timeline | `components/contract/VersionLifecycleTimeline.tsx` |
| Versions tab | `components/VersionsPanel.tsx` — cards, audit lines, lg compare drawer (AI + split tabs) |
| Review stale | `components/ReviewHistoryPanel.tsx` |
| Negotiation stale | `components/NegotiationPanel.tsx` |
| Drawer width | `components/ui/Drawer.tsx` (`size="lg"`) |
| Types | `lib/types.ts` — `VersionCompareRich`, workflow fields |
| i18n | AR+EN compare sections, audit, stale restart, activity events |

## Verification

- `pytest backend/tests -q`: **129** passed
- `npx tsc --noEmit` + `npm run build`: OK

## Manual demo

1. Contract → **Versions** → lifecycle timeline + cards with Review/Approval/Signature pills.
2. Compare v1 ↔ v2 → **AI insight** tab (risk ring + sections) and **Split view** tab.
3. Restore an older version → activity shows restored + current version changed.
4. After uploading a new version, open **Review** / **Negotiation** → stale banner + restart CTA.

## Out of scope (unchanged)

Dashboard stale KPIs, PDF redline, IP/device audit, RBAC.
