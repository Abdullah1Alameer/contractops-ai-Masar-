# Feature 12 — Premium Enterprise UI/UX (presentation-only)

## Summary

Extended the Feature 11 shell with a teal enterprise design system (`#0F766E`), new shared components, and deep UI rewrites for Dashboard, Contracts, Contract Detail, Negotiation, Approvals, Versions, Templates, Reports, and Settings. No backend, API, or business-logic changes.

## Design tokens

- [frontend/tailwind.config.ts](frontend/tailwind.config.ts): full `brand` teal scale, `neutral` ramp, `shadow-elevation-*`, `shadow-panel`, `rounded-card` / `rounded-xl2`, extended semantic color 200 steps.
- [frontend/app/globals.css](frontend/app/globals.css): `.surface-card`, `.surface-panel`, typography helpers (`.text-title`, `.text-eyebrow`, `.text-hint`), `.pill`, `.kbd`, link utilities.

## New shared components

| Component | Path |
|-----------|------|
| Drawer | `frontend/components/ui/Drawer.tsx` |
| DropdownMenu | `frontend/components/ui/DropdownMenu.tsx` |
| ProgressBar | `frontend/components/ui/ProgressBar.tsx` |
| RiskScoreRing | `frontend/components/ui/RiskScoreRing.tsx` |
| Stat | `frontend/components/ui/Stat.tsx` |
| SectionHeader | `frontend/components/ui/SectionHeader.tsx` |
| StageBadge | `frontend/components/ui/StageBadge.tsx` |
| StatusBadge | `frontend/components/ui/StatusBadge.tsx` |
| ActionMenu | `frontend/components/ui/ActionMenu.tsx` |

## Shell

- [frontend/components/shell/Sidebar.tsx](frontend/components/shell/Sidebar.tsx): SVG nav icons, active rail indicator.
- [frontend/components/shell/TopHeader.tsx](frontend/components/shell/TopHeader.tsx): notifications drawer trigger, `UserMenu` (role + language), mobile primary action row.
- [frontend/components/shell/NotificationsDrawer.tsx](frontend/components/shell/NotificationsDrawer.tsx): mock timeline feed.
- [frontend/components/shell/UserMenu.tsx](frontend/components/shell/UserMenu.tsx): profile popover with `DemoRoleSwitcher`.
- [frontend/components/shell/ShellContext.tsx](frontend/components/shell/ShellContext.tsx): `notificationsOpen` state.

## Activity helper

- [frontend/lib/activity.ts](frontend/lib/activity.ts): `mapActivityEvents()` for consistent timeline labels/tones across Dashboard, Contract Detail, Approvals.

## Screens updated

- **Dashboard**: 9 KPI `Stat` cards, merged activity timeline, AI insights (risk list), recent contract updates.
- **Contracts**: `StageBadge`, owner/created columns, `ActionMenu`, bulk JSON export.
- **Contract detail**: hero stats + `RiskScoreRing`, workflow stepper, tabs for Document, Risk, Documents, Activity; documents list from versions API.
- **Negotiation panel**: recommendation row (impact cards + score ring + strategy), three-column Original / Client / Lawyer layout.
- **Approvals panel**: progress bar, step cards, unified activity timeline.
- **Versions panel**: version cards, compare drawer, restore confirm.
- **Templates**: card grid from [frontend/lib/templatesSeed.ts](frontend/lib/templatesSeed.ts) (sample data).
- **Reports**: client-side stage bars + signature/approval counters.
- **Settings**: tabbed placeholder forms.

## i18n

Extended [frontend/lib/i18n.tsx](frontend/lib/i18n.tsx) (AR + EN) with dashboard KPI keys, negotiation/approval/versions/templates/reports/settings/user/notifications/stage labels, and detail tab keys.

## Verification

```bash
cd frontend && npx tsc --noEmit && npm run build
```

- Typecheck: **pass**
- Production build: **pass**

Backend pytest unchanged (no backend edits); expect **126** tests still passing.

## Known limitations

- Notifications feed is mocked; templates/reports/settings use static or client-only data (labeled where applicable).
- Template library has no API; “Use template” routes to upload.
- User sign-out is disabled placeholder.
- Compare drawer falls back to JSON diff when findings shape differs from flowdown.
- Dashboard activity samples first five contracts’ activity endpoints (not a global feed API).
