# Public Review Portal — Audit, Redesign, and Document Access

> **Addendum — document viewer showing `{"detail":"Not Found"}`:** see
> [Post-implementation fix](#post-implementation-fix--document-viewer-showing-detailnot-found)
> at the end of this document.

Status: Audited, root causes confirmed, implemented. Branch
`feature/timeline-payment-tracker`. Scope: the Public Review Portal
(`/review/{token}`) only. The backend review workflow (statuses,
decisions, lifecycle transitions, comment threading) was **not**
redesigned — every existing route, status machine, and authorization
check behaves exactly as before. What changed is what data reaches the
portal and how it is presented.

Also covers the follow-on "document access across the app" ask: the
Main Contracts List, the Contract detail Documents tab, and the
single-source-of-truth confirmation for the contract file.

---

## Audit

### 1. Missing Contract Viewer

**Confirmed by a full read of `backend/app/routers/reviews_public.py`
(pre-change): no document/file route existed at all.** The only routes
were `GET /review/{token}`, and `POST .../approve|reject|request-changes|comment`.
Unlike the signature flow — which already had a public document
mechanism the internal viewer just needed a counterpart for (Phase C of
this session) — here there was genuinely nothing to wire up. This is an
"add the smallest backend addition required" case, not a "wire up
unused" case.

The frontend confirmed the same gap: `ReviewPortalPayload` had no
document/file field, and the page never rendered anything but extracted
data.

### 2. Weak AI Summary

`build_ai_summary()` (`reviews.py`) is a plain metadata bullet list
(title/parties/value/governing law/term/obligation count/timeline
counts/payment counts) joined with `\n` — exactly the reported symptom.
**Root cause is not a missing AI capability.** A real, already-generated,
already-stored business summary exists: `ContractSummary` /
`serialize_summary()` (`services/summary.py`) — the exact same
purpose / parties / term & key dates / financial terms / key
obligations / termination & renewal / notable risks / next-steps
structure `AiSummaryPanel.tsx` already renders on the internal Contract
Analysis page, each item carrying page/clause-ref/quote citations. The
public portal simply never called it.

### 3–4. Risk / Obligations traceability

- `risk_engine.serialize_risk()` already resolves each finding's
  `source_clause_id` into `{clause_ref, quote, page, char_start,
  char_end}` (done in Phase D of this session, for the internal Risk
  tab). `build_risk_summary()` in `reviews.py` called `serialize_risk()`
  but only copied `category/label/detail/severity/link_tab` out of each
  finding — the resolved `source` object was computed and then dropped.
- `_serialize_obligations()` joins `Clause` via `source_clause_id` and
  already has `clause.quote` in scope in the loop, but the output dict
  never included it.

Both are "computed but not serialized" bugs — zero new backend
computation was required, only plumbing.

### 5. Timeline

`DeadlineRow`/`Deadline` already carries `clause_ref`, `quote`, and
`page` (confirmed via `deadlines.py` / `types.ts`) — they were reaching
the payload, just never rendered with a jump action or the quote text in
the portal UI. Pure frontend gap.

### 6. Comparison tab

Present, and, per instruction, out of scope for a single-contract review
portal — removed entirely from the frontend (tab entry, render block,
and the now-unused `FlowdownFindings`/`FlowdownSummary` imports). Left
the backend's `comparison`/`comparison_unavailable_reason` dossier
fields as-is (cheap to compute, other internal callers may still use the
dossier shape) rather than touching backend workflow, per the explicit
"do not redesign the backend workflow" constraint.

### 7. Files (whole app)

Grepped `app/contracts/page.tsx` and `app/contracts/[id]/page.tsx` for
any use of the file-fetching primitives — zero hits in either. Yet
`GET /api/contracts/{id}/file` (`routers/contracts.py`) already exists,
already works, and already returns the correct MIME type and
`Content-Disposition: inline`. Same finding as problem #1 but inverted:
here the backend endpoint already exists and was simply never wired into
any UI. `ContractDocumentsTab` (the internal "Files" tab) rendered only
a bare list of version labels/dates — no download/preview/open link at
all, not even to the working endpoint.

### 8. Traceability

Same root cause as #3/#4/#5 — the "why/where" data existed in the
backend response shape in most cases (quote/clause_ref/page) but had no
jump action anywhere in the portal (`SourceRef` rendered text only, no
click behavior), and in the risk-finding and obligations cases the quote
itself wasn't even reaching the payload.

---

## Root causes, summarized

| Problem | Root cause | Fix type |
|---|---|---|
| No contract viewer | No public document endpoint existed | New, minimal backend endpoint (reuses existing PDF logic) |
| Weak AI summary | A real summary exists and was never reused | Backend: expose it under a new key, unchanged existing key kept |
| Risk findings lack quote/page | Computed by `serialize_risk()`, dropped in `build_risk_summary()` | Backend: pass 3 already-computed fields through |
| Obligations lack quote | Computed in-loop, never serialized | Backend: add 1 field |
| Timeline lacks jump action | Data present, no UI action | Frontend only |
| Comparison tab present | Wrong surface for a single-contract review | Frontend: remove entirely |
| No document access on Contracts list / Files tab | Backend endpoint exists, never wired into UI | Frontend only |
| No traceability anywhere | Combination of the above | Backend (quote passthrough) + frontend (jump actions) |

No fabricated data was introduced anywhere — every field shown is either
an existing stored value or an existing computed value that was already
being thrown away before reaching the client.

---

## Implementation

### Backend changes

- **`backend/app/routers/reviews_public.py`** — new
  `GET /review/{token}/document`. Mirrors the exact
  `_rate(request, token)` → `_load(token, db)` → `expire_if_needed(req,
  db)` pattern every other route in this file already uses (the same
  authorization boundary, not a new one), then serves
  `services/signature_pdf.py::original_bytes(contract)` as
  `application/pdf` — the same single source of truth already used by
  the signature flow (real PDF pass-through if the upload actually is a
  PDF, otherwise a PDF generated from the extracted text). No new PDF
  logic was written.
- **`backend/app/services/reviews.py`**:
  - `_serialize_obligations()` — added `"quote": clause.quote if clause
    else None`.
  - `build_risk_summary()` — each `"finding"`-type item now also carries
    `quote` / `clause_ref` / `page`, read from the `source` object
    `serialize_risk()` already resolves. No new query, no new
    computation.
  - `build_review_dossier()` — added `"business_summary":
    serialize_summary(c, db)`. The pre-existing `"ai_summary"` metadata
    string is untouched and still present under its own key, per "Keep
    metadata separately."
  - `build_public_payload()` — added `"document_url":
    f"/api/review/{public_token_for_request(req)}/document"`.
    `public_token_for_request()` is the existing helper (already used
    for the review-link email) that reconstructs the plaintext token
    deterministically from the stored nonce — `req.token` itself is
    `None` for real requests (only the hash is persisted), so the
    email-link mechanism was reused rather than inventing a new one.

No migration, no new tables, no changes to any lifecycle/status/decision
logic.

### Frontend changes

- **`frontend/app/review/[token]/page.tsx`** (rewritten):
  - New persistent "Contract document" card, always visible above the
    tabs (not gated behind a tab — "a contract review portal must always
    expose the contract itself"): native `<iframe>` PDF viewer
    (`publicReviewDocumentUrl(token)`, `#page=N` fragment support for
    jump actions), Download button (fetches the blob and saves it under
    the contract's title via a new `triggerBlobDownload()` helper), Open
    in new tab button.
  - The old `<pre>{ai_summary}</pre>` block replaced with a structured,
    read-only `BusinessSummary` render (purpose / key obligations /
    notable risks / financial terms / term & key dates / termination &
    renewal / next steps), each item's citations rendered as
    clickable chips that jump the embedded viewer to that page — the
    same visual pattern `AiSummaryPanel.tsx` already uses, minus the
    internal-only generate/regenerate controls. An honest "not yet
    available" message shows when `business_summary.status !== "ready"`
    (never a fabricated summary). The existing metadata (value / law /
    term dates) stays under the "summary" tab, now explicitly labeled
    "Key contract details" — kept separate, not merged into the new
    executive summary.
  - `SourceRef` upgraded: now renders the original clause quote (when
    present) and a "Jump to clause in the document" action that scrolls
    the document card into view and sets its page fragment — applied
    uniformly to Risks, Obligations, Timeline, and Payments items (the
    Payments backend fields were already complete; only the frontend
    action was missing there).
  - Comparison tab removed completely: the `Tab` type, the `tabs` array
    entry, the render block, and the now-dead `FlowdownFindings` /
    `FlowdownSummary` imports.
- **`frontend/lib/api.ts`** — `publicReviewDocumentUrl(token)` (URL
  builder, unauthenticated public route, mirrors the existing
  `publicSignDocumentUrl`) and `fetchReviewDocumentBlob(token)`.
- **`frontend/lib/utils.ts`** — `triggerBlobDownload(blob, filename)`, a
  small shared helper (a throwaway `<a download>` link) so a fetched
  blob can be saved under a real filename instead of only being
  openable via `window.open(URL.createObjectURL(...))`.
- **`frontend/lib/types.ts`** — `ReviewPortalPayload` gained
  `business_summary: ContractSummaryPayload` and `document_url: string`;
  `ReviewPortalObligationRow` gained `quote: string | null`;
  `ReviewPortalRiskItem`'s existing optional `quote/clause_ref/page`
  fields are now also populated for `"finding"`-type items, not just
  `"penalty"`.
- **`frontend/app/contracts/page.tsx`** (Main Contracts List) — added
  "Download contract document" / "Open contract document" to each row's
  action menu, using the existing `fetchContractFileBlob()` +
  `triggerBlobDownload()` — confirmed the backend endpoint already
  existed (`GET /api/contracts/{id}/file`) and was simply never called
  from here; no new backend endpoint was added.
- **`frontend/app/contracts/[id]/page.tsx`** (Files tab) — added a
  "Current document" row with Download / Open actions above the
  existing version list, using the same existing endpoint. The version
  list itself stays label/date-only: `GET /api/contracts/{id}/file`
  only ever serves the contract's *current* file — there is no
  per-version file storage or retrieval endpoint in the schema, so
  adding one would be new backend surface beyond what was asked
  ("Main Contracts List" / "Files" access), not a wiring gap. Documented
  here rather than silently implied.

### i18n

New keys added to both the Arabic and English blocks in
`frontend/lib/i18n.tsx`: `review.portal.document.*`,
`review.portal.summary.*`, `list.downloadDocument`,
`list.openDocument`, `detail.documents.*`. The now-unused
`review.portal.tab.comparison` / `noComparison` /
`comparisonNotLinked` / `comparisonNotYetCompared` keys were removed
(confirmed no other file referenced them).

---

## Permission audit

Confirmed, consistent with every other phase of this session's audits:
**this codebase has no per-user or per-reviewer permission system.**
There are exactly two authorization mechanisms in the whole app:

1. **Internal app**: a single shared demo bearer token
   (`DEMO_TOKEN`) plus an `X-Demo-Role` header that selects among a
   fixed set of role labels (`business_owner`, `legal`, `finance`,
   `executive`, `sales`, `manager`). A handful of specific actions
   (e.g. configuring an approval route) check that header against an
   allow-list; everything else — including contract file
   download/preview — has no role check at all. **Anyone holding the
   shared demo bearer token can download or preview any contract's
   file today**, exactly as they could already view every other field
   on that contract's detail page.
2. **Public review portal**: a single per-request token
   (`ReviewRequest.token_hash`/`token_nonce`), valid until
   `expires_at` or a terminal decision. There is no concept of "this
   reviewer has document-download permission but not X" — the token
   either resolves to a live request or it doesn't.

Given that, the "permission-aware document access" requirement
(hide download/open when the reviewer lacks permission) has **no real
flag to branch on** in the current schema. Implementing a UI toggle for
a permission that doesn't exist anywhere server-side would be exactly
the kind of fabricated control the audit's own traceability principle
argues against — and it would create a false sense of enforcement,
since a determined client could still hit the document endpoint
directly with dev tools regardless of what the UI shows.

**What was actually implemented, honestly matching the one real
boundary that exists:** the document viewer, download, and open actions
render whenever the portal itself loaded successfully — i.e. whenever
the token is valid. That is the same condition under which every other
piece of the dossier (obligations, risks, timeline) is already shown.
There is no separate, weaker "read this data but not the PDF" tier to
represent, because none exists in the backend today. If per-reviewer
document permissions become a real product requirement, it needs a
schema change first (e.g. a `can_download_document` flag on
`ReviewRequest`, enforced in the new document route) — that is
explicitly flagged here as follow-up work, not implemented as a
frontend-only illusion.

**Backend remains the enforcement point for the one real boundary that
does exist:** `GET /review/{token}/document` calls `expire_if_needed()`
before serving bytes, exactly like `build_public_payload()` does before
serving the dossier — an expired or nonexistent token cannot fetch the
document regardless of what the frontend renders (see
`tests/test_review_document_access.py`).

---

## Single source of truth confirmation

`services/signature_pdf.py::original_bytes(contract)` is now used by:

- The signature field-placement viewer (`GET
  /signature-requests/{id}/document`, Phase C of this session).
- The public signer portal.
- **The public review portal (`GET /review/{token}/document`, this
  change).**

All three resolve to the exact same rule: the real uploaded file if it
is genuinely a PDF, otherwise a PDF generated on the fly from
`contract.raw_text`. No new PDF-generation logic was introduced. The
Main Contracts List and the Contract detail Files tab use the sibling
endpoint `GET /api/contracts/{id}/file`, which reads the same
`contract.file_url` from the same `storage` service — there is exactly
one place a contract's file bytes live (`storage.get(contract.file_url)`),
and every surface in the app that shows the document reads from it.

---

## Files changed

**Backend**
- `backend/app/routers/reviews_public.py` — new document endpoint.
- `backend/app/services/reviews.py` — obligation quote, risk finding
  source passthrough, business summary, document URL.
- `backend/tests/test_review_document_access.py` — new (5 tests).
- `backend/tests/test_review_portal_data_completeness.py` — extended
  (traceability assertions, document/business-summary presence,
  updated the internal-fields-leak test to account for the intentional
  `document_url`).
- `backend/tests/test_approvals.py` — fixed a pre-existing mock missing
  `token`/`token_nonce` (surfaced by the new `document_url` field).

**Frontend**
- `frontend/app/review/[token]/page.tsx` — rewritten.
- `frontend/app/review/[token]/page.vitest.tsx` — extended (document
  viewer, executive summary, comparison-tab-removed coverage); removed
  the obsolete comparison-tab tests.
- `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/lib/utils.ts`
  — new helpers/types described above.
- `frontend/app/contracts/page.tsx` — Main Contracts List download/open
  actions.
- `frontend/app/contracts/[id]/page.tsx` — Files tab current-document
  actions.
- `frontend/lib/i18n.tsx` — new/removed keys, both languages.

---

## Verification

- **Backend focused**: `test_review_document_access.py` (5/5),
  `test_review_portal_data_completeness.py` (13/13),
  `test_approvals.py::test_public_review_payload_no_approval_keys` (1/1)
  — all passing.
- **Backend full suite**: 471 passed / 2 pre-existing failures, both
  confirmed present before this change by stashing the diff and
  re-running each in isolation
  (`test_review_resend_cooldown_is_deterministic` — timing-sensitive;
  `test_dashboard_summary_query_ceiling` — a query-count assertion that
  fails against the shared remote dev database's current row volume).
  Neither touches review-portal or document-access code.
- **Frontend**: `npx tsc --noEmit` — clean. Full `vitest run` — 184/184
  passing (17 in the rewritten portal page test file). `npm run build`
  — compiled successfully, all routes generated, no size regression
  beyond the expected small increase on `/review/[token]`,
  `/contracts`, and `/contracts/[id]`.

---

## Post-implementation fix — document viewer showing `{"detail":"Not Found"}`

**Symptom reported:** after the above shipped, opening a real review
link showed the document card, but the embedded viewer rendered raw
JSON — `{"detail":"Not Found"}` — instead of the PDF.

### Trace

1. Frontend request: the iframe's `src` resolved to
   `http://localhost:8000/api/review/{token}/document` (correct URL,
   matching `document_url` in the payload and the route declared in
   `reviews_public.py`).
2. Backend route check: `curl http://127.0.0.1:8000/openapi.json` on the
   **already-running** local dev `uvicorn` process showed
   `/api/review/{token}/document` **absent** from the live route table,
   even though the source file on disk plainly contains it.
3. Root cause: the dev backend (`uvicorn app.main:app --host 127.0.0.1
   --port 8000`, no `--reload`) had been started *before* this feature's
   backend changes were written, and was never restarted — it was still
   serving the pre-fix code. `{"detail":"Not Found"}` is Starlette's
   generic 404 body for a route that doesn't exist at all (distinct from
   this endpoint's own explicit `{"detail":{"error":"review_not_found"}}`
   for an invalid *token*) — that shape was the direct fingerprint of
   "the route itself isn't registered," not an application-level error.
4. Confirmed the fix by restarting the backend with `--reload` and
   re-checking `openapi.json` — the route appeared — then running a full
   live round-trip against a real, already-sent review request:
   `GET /review/{token}` → `document_url` present, `GET
   /review/{token}/document` → `200`, `content-type: application/pdf`,
   body starts with `%PDF-1.7`, and `GET
   /review/bogus-token/document` → `404` with the endpoint's own
   `review_not_found` error body.

### Hardening (independent of the root cause above)

A stale server explains this specific incident, but requirements
#7/#9/#10 ask for the viewer to never show raw JSON *regardless of
why* the document request fails (expired mid-session, the storage file
missing, a future regression). The iframe previously pointed directly
at the API URL — if that request ever fails for any reason, the
browser's native PDF viewer has no choice but to render whatever bytes
came back, JSON included. Fixed in
`frontend/app/review/[token]/page.tsx`:

- The document is now fetched and verified as a blob (`fetchReviewDocumentBlob`)
  *before* anything is handed to the iframe. The iframe's `src` is only
  ever a same-origin `blob:` URL built from bytes already confirmed to
  be `application/pdf` — never a live request the browser could resolve
  to JSON.
- Three explicit states: `loading` (skeleton placeholder), `ready`
  (iframe + Download/Open shown), `unavailable` (a plain "The contract
  document could not be displayed" message — Download/Open are not
  shown either, since there is nothing to download).
- Jump-to-page (`#page=N`) now targets the blob URL directly — no
  behavior change for that feature.
- New i18n keys: `review.portal.document.unavailable` /
  `...unavailableHint`, both languages.

### Tests added

`frontend/app/review/[token]/page.vitest.tsx`:
- Confirms the document is fetched and verified as a blob, and the
  iframe's `src` is the resulting `blob:` URL, never the raw API path.
- Confirms a rejected document fetch renders the "unavailable" state
  with no `<iframe>` in the DOM and no Download/Open buttons.
- Confirms a non-PDF response (e.g. a JSON error body wrapped in a
  blob) is treated the same as a failure — same "unavailable" state,
  still no `<iframe>`.

### Verification (this fix)

- **Live smoke, real data**: restarted the dev backend, sent a fresh
  request through `/api/contracts/{id}/review/send` where needed, and
  round-tripped an actual pre-existing review request end-to-end —
  portal payload, document fetch (200/`application/pdf`/`%PDF-1.7`),
  and an invalid-token document fetch (404/`review_not_found`) all
  confirmed directly against the running server, not just via
  `TestClient`.
- **Frontend**: `npx tsc --noEmit` clean. Full `vitest run` — 186/186
  passing (19 in the portal page test file, 2 new). `npm run build` —
  compiled successfully.
- **Backend**: unchanged in this fix (the endpoint itself was already
  correct — pending route registration was an environment/process
  issue, not a code defect); no backend files touched, so the earlier
  471-passed / 2-pre-existing-failures baseline still applies.

**Operational note:** if this recurs, check whether the backend process
serving requests was started before the latest backend change — long-
running dev servers started without `--reload` (or a production
deployment that hasn't redeployed) will silently keep serving old
routes with no error at startup.
