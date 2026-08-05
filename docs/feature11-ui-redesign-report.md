# Feature 11 — Enterprise UI/UX Redesign (presentation-only)

## Summary

Replaced the top navigation shell with a collapsible sidebar, top header (breadcrumbs, search, notifications mock, role switcher, language toggle), and client-side command palette (⌘/Ctrl+K). Refreshed dashboard, contracts list, contract detail, and public review/signer layouts. Added shared UI primitives and lifecycle shortcut pages. No backend or API changes.

## Screens changed

| Area | Changes |
|------|---------|
| Global layout | `AppShell`, public routes `/review/*` and `/sign/*` render without sidebar |
| Dashboard | Lifecycle KPI row, two-column panels, review list with link to `/reviews` |
| Contracts | `DataTable`, search, filter chips, sort, bulk select + delete, pagination (25) |
| Contract detail | `ContractHeader`, `WorkflowStepper`, tabbed UX (overview, AI summary, clauses/source, activity, existing panels) |
| Review portal | Brand header, two-column desktop (document + actions sidebar), sticky mobile decision bar |
| Sign portal | Progress chips, framed document iframe, sticky primary sign action on mobile |

## New routes

- `/reviews` — client review list (summary API)
- `/negotiations`, `/approvals`, `/signatures` — stage-filtered contract aggregates + link to `/contracts?stage=…`
- `/versions` — contracts with multiple versions
- `/templates`, `/reports`, `/settings`, `/help` — placeholder `EmptyState` pages

## Components added

- Shell: `AppShell`, `Sidebar`, `TopHeader`, `Breadcrumbs`, `CommandPalette`, `ShellContext`, `PageContainer`
- Contract: `ContractHeader`, `WorkflowStepper`
- UI: `DataTable`, `Tabs` (`TabList`, `TabTrigger`, `TabPanel`), `Timeline`
- Pages: `PlaceholderPage`, `StageAggregatePage`

## Design system

- `Badge` tone `subtle` for stage/status pills
- `globals.css`: `.chip`, `.chip-active`, `.data-cell`, `.section-title`, `.hairline-b`
- i18n: nav, shell, stepper, dashboard sections, common filters/sort, placeholders

## Verification

```bash
cd frontend && npx tsc --noEmit && npm run build
```

- Build: **success** (17 app routes)
- Backend pytest: unchanged (no backend edits in this feature)

## Manual smoke checklist

- [ ] Sidebar collapse persists (`localStorage` key `sidebar.collapsed`)
- [ ] ⌘/Ctrl+K opens command palette
- [ ] Dashboard KPI links navigate with `?stage=` where applicable
- [ ] Contracts search, chips, pagination, bulk delete
- [ ] Contract detail stepper reflects `contract.stage`
- [ ] Review + sign pages at 375px / 768px / 1440px, RTL and LTR

## Known limitations

- Notifications menu is mocked (no feed API)
- Templates, Reports, Settings, Help are placeholders
- Command palette uses static nav commands only (no server-side recent contracts yet)
- Lifecycle aggregate pages filter client-side over `/api/contracts` (no dedicated aggregate endpoints)
- Dashboard “Recent activity” panel is empty until a cross-contract activity API exists
- AI summary tab uses extraction fields when present; may show empty otherwise
