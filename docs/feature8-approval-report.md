# Feature 7 polish + Feature 8 — Internal Legal Approval Workflow

## Summary

Feature 7 gains explicit **negotiation workflow status**, lawyer final wording (EN/AR), a three-part clause view, rationale cards, and a post-send **final summary**. Feature 8 adds a **four-step internal approval chain** (Business Owner → Legal → Finance → Executive), contract **lifecycle stage**, **activity events**, an **Approvals** tab, **demo role switcher** (`X-Demo-Role`), and dashboard KPIs.

## Database

- **Migration `011_approval_workflow.sql`**
  - `contracts.stage` — `negotiation | internal_review | approved | awaiting_signature` (default `negotiation`)
  - `negotiations` — `workflow_status`, `lawyer_final_clause`, `lawyer_final_clause_ar`, `sent_at`, `final_summary`
  - `approval_workflows`, `approval_steps`, `activity_events`

Run: `backend/.venv/bin/python database/migrate.py`

## Backend (key paths)

| Area | Path |
|------|------|
| Migration | `database/migrations/011_approval_workflow.sql` |
| Models | `backend/app/models.py` |
| Lifecycle | `backend/app/services/lifecycle.py` (sole writer of `contracts.stage`) |
| Approvals | `backend/app/services/approvals.py` |
| Negotiation polish | `backend/app/services/negotiation.py` |
| Router | `backend/app/routers/approvals.py` |
| Demo role | `backend/app/deps.py` (`demo_role` header) |
| Contracts JSON | `backend/app/routers/contracts.py` (`stage` field) |
| Main | `backend/app/main.py` |

### Approval APIs (Bearer + `X-Demo-Role`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/contracts/{id}/approvals/start` | `{ approver_names?, force? }` |
| GET | `/api/contracts/{id}/approvals` | Workflow, steps, allowed actions, unresolved negotiations |
| PATCH | `/api/approvals/{step_id}` | `{ status, comment }` |
| POST | `/api/contracts/{id}/approvals/cancel` | Cancel active workflow |
| GET | `/api/contracts/{id}/activity` | Activity timeline |
| GET | `/api/approvals/summary` | Dashboard KPI counts |

### Lifecycle rules

- Start approval: contract stage `negotiation` or `internal_review` → moves to `internal_review`.
- Step **approved**: unlock next; final step → workflow `approved`, stage `approved`.
- **Rejected** / **changes_requested**: require comment; workflow terminal; stage back to `negotiation`.
- **Cancel**: active workflow only; stage back to `negotiation`.
- Unresolved negotiations block start unless `force=true` (logged in activity metadata).

Public review (`/api/review/{token}`) unchanged — no approval fields in payload.

## Frontend

| Path | Change |
|------|--------|
| `frontend/lib/api.ts` | `X-Demo-Role`, approval/activity helpers |
| `frontend/lib/types.ts` | Approval + negotiation polish types, `stage` on contracts |
| `frontend/components/DemoRoleSwitcher.tsx` | Header role switcher |
| `frontend/components/NegotiationPanel.tsx` | Status badge, 3-column clauses, rationale, summary |
| `frontend/components/ApprovalsPanel.tsx` | Stepper, actions, start/cancel, activity |
| `frontend/app/contracts/[id]/page.tsx` | Approvals tab |
| `frontend/app/dashboard/page.tsx` | Approval KPI row (links to `/contracts?stage=…`) |
| `frontend/app/contracts/page.tsx` | Client filter by `?stage=` |
| `frontend/lib/i18n.tsx` | `approval.*`, `role.*`, `negotiation.workflow.*`, `activity.*` |

## Manual testing

1. Migrate + start backend/frontend.
2. Reject a review → **Negotiation** tab → Analyze → edit lawyer final EN/AR → Send → verify summary card.
3. **Approvals** tab → Start workflow (use **Proceed anyway** if unresolved warning).
4. Switch **Demo Role** in header; approve in order BO → Legal → Finance → Executive.
5. Try wrong role (403) and out-of-order step (409); reject with comment returns stage to negotiation.
6. Dashboard approval KPIs reflect DB state.

## Verification

- `backend/.venv/bin/python -m pytest backend/tests -q`: **104 passed**
- `cd frontend && npx tsc --noEmit && npm run build`: OK

## Known limitations

- Demo role via `X-Demo-Role` only — no real RBAC/auth.
- No digital signature (Feature 9), email notifications, or workflow builder UI.
- Activity events are approval-scoped for now.
- Dashboard “pending role” KPIs count active workflows by current step role; contract list filter is by `stage` only (role query param reserved for future UX).
- `force` start with unresolved negotiations is audit-logged only.
