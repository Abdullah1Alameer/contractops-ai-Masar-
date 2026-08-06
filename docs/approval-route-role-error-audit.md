# Approval Route Save Flow — `approval_route_role_required` Audit

Status: Audited, root cause confirmed, fixed. Branch
`feature/timeline-payment-tracker`. Frontend-only change — the backend
behavior was verified correct and was not modified.

---

## Trace

### Frontend validation
None existed. `ApprovalRouteBuilder.tsx` had no awareness of the current
acting demo role at all — any role could open the builder, fill in
steps, and attempt to save.

### Payload construction (`ApprovalRouteBuilder.tsx::start()`)

```ts
const body = {
  name: routeName.trim() || null,
  steps: steps.map((s) => ({
    role: s.role,
    approver_name: s.approver_name.trim() || null,
    required: s.required,
  })),
  source_route_id: sourceRouteId,
  save_as_route: saveAsRoute,
  save_as_route_name: saveAsRoute ? saveAsRouteName.trim() || routeName.trim() || null : null,
};
await configureApprovalRoute(contractId, body);
```

### Request body actually sent (confirmed via `lib/api.ts::configureApprovalRoute`)

`PUT /api/contracts/{id}/approval-route`, headers include
`X-Demo-Role: <whatever the Demo Role Switcher currently holds>`
(`demoRoleHeader()` in `lib/api.ts`, reading `localStorage["demoRole"]`,
defaulting to `"legal"` only when the header is entirely absent from
`localStorage`). Body:

```json
{
  "name": "...",
  "steps": [{ "role": "legal", "approver_name": null, "required": true }, ...],
  "source_route_id": null,
  "save_as_route": false,
  "save_as_route_name": null
}
```

### Backend validation (`app/routers/approvals.py::configure_contract_route_route`
→ `app/services/approval_routes.py::configure_contract_route`)

```python
def configure_contract_route(contract_id, db, *, name, steps, ..., role, actor):
    acting_role = _require_route_admin(role)   # <-- first line executed
    clean_steps = _validate_steps(steps)        # payload validation happens AFTER this
    ...

def _require_route_admin(role: str) -> str:
    acting_role = normalize_demo_role(role)
    if acting_role not in ROUTE_ADMIN_ROLES:      # ROUTE_ADMIN_ROLES = {"legal", "executive"}
        _raise(403, "approval_route_role_required", required_roles=sorted(ROUTE_ADMIN_ROLES))
    return acting_role
```

**`_require_route_admin()` runs before any request-body validation at
all.** It checks only the `X-Demo-Role` header (the acting identity),
never the `steps` payload.

### Response

`403 { "detail": { "error": "approval_route_role_required", "required_roles": ["executive", "legal"] } }`

### Localization mapping (before this fix)

None. `ApprovalRouteBuilder.tsx`:

```ts
} catch (error) {
  toast.error(apiErrorCode(error, t("common.error")));
}
```

`apiErrorCode(error, fallback)` returns `error.code` verbatim when the
error is an `ApiError` — i.e. the raw string `"approval_route_role_required"`
was passed directly into `toast.error(...)` with no `t()` lookup. This is
exactly the reported symptom.

---

## Root cause

**Confirmed, not guessed:** `approval_route_role_required` is a pure
**authorization** check on the acting `X-Demo-Role`, evaluated before the
request body is inspected at all. It is returned whenever the currently
selected demo role (Demo Role Switcher) is anything other than `legal` or
`executive` — e.g. `business_owner`, `finance`, `sales`, or `manager` —
regardless of what the route/steps payload contains.

Verified against every alternative the brief asked to rule out:

| Candidate cause | Verified | Evidence |
|---|---|---|
| A required role is missing from steps | **No** | `_require_route_admin()` runs and can raise 403 before `_validate_steps()` ever inspects `steps` |
| `role_id` not sent | **No such field exists** | Approvers are identified by a plain `role` string enum, never an ID |
| `approver_name` missing | **No** | Always optional (`str \| None`), never a cause of any error |
| `email` missing | **No such field exists** | No email field appears anywhere in the route/step schema on either side |
| `required` flag missing | **No** | Defaults to `true` server-side and client-side; never validated as "required to be present" |
| Payload shape differs from backend expectations | **No** | `ConfigureRouteBody`/`RouteStepBody` (Pydantic) match `ApprovalRouteStepInput`/the constructed `body` object field-for-field |

The only thing distinguishing a successful save from this exact 403 is
**which role is currently active in the Demo Role Switcher when Save is
clicked** — nothing about the steps, names, or route configuration
itself.

## Conclusion: this is both

Per the instruction ("if this is a frontend validation issue, prevent
submission... if this is only a missing translation, map the error") —
this investigation found **both** are true simultaneously, for two
different call paths:

1. **A frontend validation gap** — the intended, expected case (a
   non-admin user opens the builder in the normal course of using the
   app) should never reach the API at all. Fixed by gating the builder on
   the acting role client-side, mirroring the backend's own
   `ROUTE_ADMIN_ROLES` check exactly.
2. **A missing translation** — for the residual case where the backend
   *still* rejects the request (e.g. the role was switched in another
   browser tab between page load and clicking Save — a real race, not
   hypothetical, since the role lives in `localStorage` and is
   cross-tab), the raw error code must never reach the user. Fixed with
   an explicit `ERROR_KEYS` map, the same established pattern already
   used elsewhere in this codebase (`app/upload/page.tsx`'s `ERROR_KEYS`).

---

## Fix

`frontend/components/ApprovalRouteBuilder.tsx`:

- Tracks the acting demo role the same way `NegotiationPanel.tsx`'s
  existing agreement-override gate already does: read
  `localStorage[DEMO_ROLE_STORAGE]` on mount, and subscribe to
  `DEMO_ROLE_EVENT` so the gate updates live if the role is switched
  while the builder is open.
- `ROUTE_ADMIN_ROLES = new Set(["legal", "executive"])` — an exact,
  intentional mirror of the backend's own set.
- When the acting role isn't admin-eligible: shows a persistent, visible,
  localized explanation ("You don't have permission to configure the
  approval route... Current role: X. Switch role... to continue.") and
  disables "Save Approval Route" — the invalid submission is prevented
  before the API is ever called, not just described after failing.
- `start()` also re-checks the gate defensively before constructing the
  request, in case the button were somehow triggered anyway.
- `ERROR_KEYS: Record<string, TKey>` maps every backend error code this
  endpoint can actually raise (`approval_route_role_required`,
  `approval_steps_required`, `invalid_approver`, `duplicate_approver`,
  `invalid_stage_transition`, `approval_route_locked`) to a localized
  message; a new `showApiError()` helper replaces the two raw
  `toast.error(apiErrorCode(...))` call sites. Any other/unexpected code
  still falls back to the generic error message — never a raw code
  string.

No backend change was made — `_require_route_admin()`'s behavior is
correct and intentional (route configuration genuinely should be
restricted to legal/executive, per
`docs/configurable-approval-routes-report.md`'s authorization design);
the bug was entirely in how the frontend anticipated and reported that
restriction.

---

## Tests

`components/ApprovalRouteBuilder.vitest.tsx` (7 new):
1. Non-admin role (`finance`): shows the explanation, disables Save, and
   confirms clicking the (disabled) button never calls the API.
2. `legal` role: no warning shown, submission proceeds normally.
3. `executive` role: no warning shown, submission proceeds normally.
4. A raw `approval_route_role_required` rejection from the backend (the
   residual race case) is mapped to the localized message — asserts the
   toast is never called with the raw code string.
5. Another backend code (`approval_route_locked`) also maps correctly.
6. An unmapped/unexpected code falls back to the generic error message,
   never showing the raw code.
7. The gate updates live when the role switcher changes without
   remounting the component.

All 7 pre-existing tests in the same file continue to pass unchanged
(they run as `legal`, the default role, so were never exercising the
gate — now explicitly covered by the new tests above).

## Verification

- **Focused**: `ApprovalRouteBuilder.vitest.tsx` — 14/14 (7 pre-existing
  + 7 new).
- **Full frontend suite**: 182/182 (7 net new).
- **TypeScript**: `npx tsc --noEmit` — clean.
- **Production build**: `npm run build` — compiled successfully, no
  route size regression beyond the expected small increase.
- **Backend**: not modified; no backend tests needed re-running (the
  full backend suite was already verified green immediately prior to
  this fix in the same session).
