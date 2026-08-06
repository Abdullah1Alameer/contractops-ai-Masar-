# Signature Placement & Template Flow — Bugfix Report

Status: Applied and verified. Branch `feature/timeline-payment-tracker`.

Scope: two concrete release-facing gaps —

1. The signer portal never showed *where* a signature would land inside the
   actual contract document.
2. "Use Template" on the Templates page silently redirected to the generic
   `/upload` page, forgetting which template (if any) was selected.

Nothing outside these two flows was touched. `/review/{token}` (client
review decisions) and `/sign/{token}` (electronic signature) remain
distinct, separate portals — this work only changes what happens *inside*
`/sign/{token}` and *before* a document reaches upload.

---

## Bug 1 — Signature portal and document placement

### Current behavior traced end-to-end (before the fix)

`ready_to_sign → create signature request → define signers → send →
signer opens /sign/{token} → signer signs → embed → certificate →
partially_signed/signed`. Every step up to "signer signs" worked. The gap
was entirely in **embed**:

- `SignatureSigner` (`backend/app/models.py`) stores `signature_type` and
  `signature_value_url` — the captured mark itself — but **no page number,
  no coordinates, nothing about location.** No table anywhere in the schema
  recorded where a signature should or did go.
- The signer portal (`app/sign/[token]/page.tsx`) *did* show the real PDF
  (via an `<iframe src={publicSignDocumentUrl(token)}>`), so the document
  itself was visible — but nothing on it indicated where the signer's mark
  would be placed, and there was no way to navigate to a specific location.
- `build_signed_pdf()` (`backend/app/services/signature_pdf.py`) **always
  appended a brand-new page** at the end of the document listing every
  signer's name/role/timestamp with their captured mark stacked
  vertically underneath. This is the literal root cause of "the signature
  isn't clearly placed inside the actual document" — it never was; it was
  always a summary page bolted onto the end, identical regardless of what
  clause or signature block the original document actually had.
- Multiple ordered signers did not have distinct locations — they all
  landed on the same appended page, differentiated only by vertical
  stacking order.
- There was no concept of staleness for a "location" because there was no
  location to begin with.

**Conclusion: the schema could not support real placement.** A migration
was required — this was not fixable in the frontend alone, and the fix
below does not fake it there.

### Fix — data model

New table, `signature_fields` (`database/migrations/020_signature_fields_and_templates.sql`,
model `SignatureField` in `backend/app/models.py`):

| Column | Meaning |
|---|---|
| `signature_request_id`, `signer_id` | which request/signer this field belongs to |
| `version_id` | the contract version the field was placed against (set from the request's own `version_id` at save time) |
| `page_number` | 1-indexed PDF page |
| `x`, `y`, `width`, `height` | normalized `0..1` position/size relative to the page — resolution-independent, so it renders correctly at any zoom/DPI |
| `field_type` | `signature` \| `initials` \| `name` \| `date` |
| `required` | whether it must be filled before the request can complete |
| `ai_suggested` | true only for a not-yet-confirmed AI suggestion; every row actually persisted through the save endpoint is `false` |

### Fix — backend behavior

`backend/app/services/signature.py`:

- `suggest_fields(request_id, db)` — a heuristic suggestion (one signature
  field per signer, near the bottom of the document's last page, staggered
  so ordered signers don't collide). **Never persists anything.** Returned
  fields are marked `ai_suggested: true` for the frontend to render
  distinctly.
- `replace_fields(request_id, db, fields, actor)` — the only way fields are
  ever persisted. Validates every field references a real signer on the
  request, a real page number (checked against the actual PDF's page
  count via PyMuPDF), a valid `field_type`, and in-range normalized
  coordinates. Requires the request to still be in `draft`/`created` (not
  yet sent) and not stale. **Always saves with `ai_suggested = False`** —
  even if the internal user submitted an AI suggestion verbatim, going
  through this endpoint is the explicit confirmation the spec requires. AI
  never finalizes placement silently.
- `send_request()` now requires every signer to have at least one
  confirmed `signature`-type field, or it returns `409
  signature_fields_required`. This is the actual enforcement — a request
  cannot be sent to signers with no defined location.
- `build_public_payload()` (what `/sign/{token}` renders) now includes
  `fields`, filtered to **only the requesting signer's own fields** — a
  signer token can never see, and therefore can never fill, another
  signer's field.
- `build_signed_pdf()` (`signature_pdf.py`) was rewritten: for each signer
  with confirmed fields, it opens the *original* PDF and inserts the
  signature image (or typed text, or deterministic text for
  `initials`/`name`/`date`) directly onto the referenced page at the exact
  confirmed rectangle. **No page is appended for signatures anymore.** A
  small demo-disclosure footnote is stamped in the corner of the last page
  instead of eating a whole page. The old append-a-summary-page behavior
  is kept, but only as `_append_legacy_signature_page()` — a fallback for
  the (now impossible-to-create-new) case of a signature request with zero
  persisted fields, so a pre-existing signed PDF in storage can still be
  regenerated without crashing.

### Fix — internal UI (field placement)

New component, `frontend/components/SignatureFieldPlacer.tsx`, rendered
inside `SignaturePanel` between request creation and send:

- Renders the actual PDF (via `pdfjs-dist`, same rendering approach as the
  existing contract source viewer) with page navigation.
- Internal user picks a signer + field type, then clicks on the page to
  place a field; clicking an existing field removes it.
- "Suggest signature fields with AI" populates draft fields from
  `suggest_fields()`, visibly tagged (amber border + "AI suggestion"
  label) and distinct from confirmed fields (brand-colored border) — they
  are not saved until "Save field placement" is clicked.
- Locked (read-only) once the request has been sent — matches the backend,
  which refuses field changes past that point.
- `SignaturePanel`'s "Send" button is disabled with an explanatory tooltip
  until every signer has a confirmed signature field, mirroring the
  backend's own guard so the UI never lets a user attempt a send that
  would be rejected.

### Fix — public signer portal

New component, `frontend/components/SignerDocumentViewer.tsx`, replaces
the bare `<iframe>` in `app/sign/[token]/page.tsx`:

- Renders the real PDF via `pdfjs-dist` (not an opaque iframe), with page
  navigation.
- Shows "Field X of N" progress and highlights the signer's current
  required field with a ring/border overlay drawn at its exact normalized
  position.
- "Jump to your next required field" scrolls/pages to it.
- If a signer somehow has zero confirmed fields (should not happen given
  the `send_request()` guard, but handled honestly rather than silently),
  shows an explicit message instead of a blank canvas.
- The sign page's submit button stays disabled until the signer has
  visited every one of their required fields at least once — "field
  cannot be submitted before being completed" now applies to the whole
  field set, not only the signature-capture widget.

### Ordered signers, staleness, versioning

- Two ordered signers get distinct field sets — enforced structurally,
  since fields are keyed by `signer_id` and the public payload filters to
  the requesting signer's own rows only.
- `_is_stale()` (unchanged, pre-existing check) still gates every
  mutating action — `replace_fields()` refuses to save against a stale
  request, and `send_request()`/`open_signer()`/`submit_signature()` all
  already refused stale requests before this fix. Fields inherit the
  request's `version_id` at save time, so there is no separate,
  independently-driftable "field version" to go stale on its own.

### Required UX checklist

| Requirement | Status |
|---|---|
| "Demo electronic signature / توقيع إلكتروني تجريبي" disclosure | Unchanged, already present on every state of `/sign/{token}` |
| Document visible alongside signing controls | Now the real rendered PDF, not an iframe |
| "field 1 of N" progress | `SignerDocumentViewer` progress chip |
| Jump to required field | "Jump to your next required field" button + clickable field list |
| Field cannot be submitted before completed | Submit disabled until all required fields visited + signature captured + consent + name confirmation |
| Loading / render-failure / stale / already-signed / out-of-order states | All pre-existing states kept (loading, `pdfError` fallback, `workflow_stale`, `read_only`+signed, `waiting_for_prior`) — untouched except the document viewer swap |
| RTL/LTR | Unchanged layout; field labels and progress text go through the existing i18n system in both languages |
| No tokens/raw signature data in logs | Unchanged — nothing new is logged; fields carry only coordinates/type, never signature bytes |

---

## Bug 2 — Template selection flow

### Root cause

`frontend/lib/templatesSeed.ts` was a **frontend-only, hardcoded array** —
there was no backend template model at all. `app/templates/page.tsx`'s
"Use Template" button was:

```tsx
onClick={() => (window.location.href = "/upload")}
```

No template ID was passed anywhere; the upload page had (and has) no
concept of a template. Every template's button did the exact same thing —
reproduced for all four seed templates (`msa`, `nda`, `sow`, `vendor`),
confirmed by reading the seed and the click handler directly (no per-card
branching existed to check).

### Fix — data model

New table, `contract_templates`, and `contracts.template_id` (nullable
FK), both in `database/migrations/020_signature_fields_and_templates.sql`.
Seeded with the same four templates the old frontend list had
(`msa`/`nda`/`sow`/`vendor`), now with real `description_en/ar`,
`variables` (typed field list: key/label/type/required), and `clauses`
(title + body with `{{variable}}` placeholders) — enough to drive an
actual generation flow instead of a static card.

### Fix — backend

`backend/app/services/templates.py` + `backend/app/routers/templates.py`:

- `GET /api/templates` — list.
- `GET /api/templates/{id}` — detail (title, category, language, industry,
  description, variables, clause titles, usage count, last updated).
  Unknown ID → `404 template_not_found` (deterministic, not a silent
  redirect).
- `POST /api/templates/{id}/preview` — renders every clause with the
  given variables substituted (`{{key}}` → value, or `[key]` if the
  variable is missing so gaps are visible rather than silently blank),
  and reports which required variables are still missing. This is *the
  same rendering function* used to build the final document, so the
  preview the user approves is exactly what gets created.
- `POST /api/templates/{id}/create-contract` — validates all required
  variables are present (`422 template_variables_missing` otherwise, with
  the exact missing keys), generates the PDF via PyMuPDF from the same
  clause-rendering function, creates the `Contract` (`stage="draft"`,
  `template_id` set, `party_a`/`party_b`/`governing_law` populated from
  variables where given), creates version 1
  (`create_initial_version()` — the same helper normal upload uses —
  with `source` then overwritten to `"template_generated"`), logs
  `contract_created_from_template` via the existing activity-log
  service, and increments the template's `usage_count` — **only inside
  the same transaction that persists the contract**, so a failure before
  that point (bad variables, generation failure) leaves nothing behind
  and never increments usage.

### Fix — frontend

- `app/templates/page.tsx` — now fetches real templates from the backend
  (`fetchTemplates()`); each card links to `/templates/{real-uuid}`
  instead of hardcoding `/upload`.
- `app/templates/[id]/page.tsx` — new page implementing the full flow:
  1. **Detail** — title, category/language/industry, description, clauses
     included, last updated, usage count.
  2. **"Create Contract from Template"** → **Form** — one input per
     template variable (text/textarea/number/date based on its declared
     type), required ones marked.
  3. **"Preview document"** → **Preview** — the exact rendered sections
     (same call the backend uses to generate the final PDF), in the
     current UI language. Missing required variables block the preview
     with an inline warning rather than silently proceeding.
  4. **"Confirm and create contract"** — calls create-contract, then
     immediately calls the same `POST /api/contracts/{id}/extract`
     endpoint the normal upload flow calls (`app/upload/page.tsx`'s exact
     pattern), and redirects to `/contracts/{id}` — so a
     template-generated contract goes through the identical
     extraction/classification/summary pipeline as an uploaded one, and
     "continues through the canonical lifecycle normally" from `draft`
     onward with zero special-casing.
  - A refresh or a direct deep link to `/templates/{id}` re-fetches the
    same template detail from the backend (the ID lives in the URL, not
    transient client state), so the selection survives navigation.

Deep-link/refresh preservation, unknown-template handling, and the upload
page itself were explicitly not touched — the instruction's "if upload is
intentionally part of the flow" branch does not apply here, since the
generation-and-preview flow replaces the need to route through `/upload`
at all.

---

## Files changed

Backend:
- `database/migrations/020_signature_fields_and_templates.sql` — new
  tables (`signature_fields`, `contract_templates`), `contracts.template_id`,
  seed data for the four templates.
- `app/models.py` — `SignatureField`, `ContractTemplate`,
  `Contract.template_id`.
- `app/services/signature.py` — field CRUD/suggest, `send_request()`
  guard, `build_public_payload()` fields, `serialize_request()` fields.
- `app/services/signature_pdf.py` — `build_signed_pdf()` rewritten to
  embed at confirmed field locations; legacy fallback preserved.
- `app/routers/signature.py` — `GET/PUT` fields, `GET` suggest.
- `app/services/templates.py`, `app/routers/templates.py` — new.
- `app/main.py` — registers the templates router.
- `tests/test_signature_lifecycle_integration.py` — `_create()` now places
  default fields via the new endpoint so every existing send/sign test
  reflects the new required step; all 19 pre-existing tests pass
  unchanged in behavior.
- `tests/test_smtp_local_integration.py` — same field-placement step added
  before the one signature-request send test in that file.
- `tests/test_signature_field_placement.py`, `tests/test_template_creation.py`
  — new, 7 + 5 tests.

Frontend:
- `components/SignatureFieldPlacer.tsx`, `components/SignerDocumentViewer.tsx`
  — new.
- `components/SignaturePanel.tsx` — renders the placer, gates Send on
  field completeness.
- `app/sign/[token]/page.tsx` — real document viewer replaces the iframe;
  submit gated on all-fields-viewed.
- `app/templates/page.tsx` — real backend list, real per-template links.
- `app/templates/[id]/page.tsx` — new, the full detail → form → preview →
  create flow.
- `lib/api.ts`, `lib/types.ts` — new field/template API functions and
  types.
- `lib/i18n.tsx` — new keys, Arabic + English, mirrored.
- New tests: `components/SignatureFieldPlacer.vitest.tsx`,
  `components/SignerDocumentViewer.vitest.tsx`,
  `app/templates/page.vitest.tsx`, `app/templates/[id]/page.vitest.tsx` (4
  + 3 + 1 + 4 = 12 new tests); `components/SignaturePanel.vitest.tsx` and
  `app/sign/[token]/page.vitest.tsx` updated with the new mocks/fixtures
  their existing tests now require.

## Verification

- **Backend, focused**: `tests/test_signature_field_placement.py` (7/7),
  `tests/test_template_creation.py` (5/5),
  `tests/test_signature_lifecycle_integration.py` (19/19, unchanged
  behavior), `tests/test_smtp_local_integration.py` (2/2) — all green.
- **Backend, full suite**: `pytest -q` — see results below.
- **Frontend**: `npx tsc --noEmit` clean. `npx vitest run` — 20 test
  files, 144 tests, all passed (132 pre-existing + 12 new). `npm run
  build` — compiled successfully, 21 routes including the new
  `/templates/[id]`.
- **Real API/DB smoke — signature placement** (scripted, no browser tool
  available this session — see limitation note below): created a
  synthetic two-page contract at `ready_to_sign`, created a two-signer
  ordered request, confirmed `send` is blocked with
  `signature_fields_required` before any fields exist, placed signer
  one's field on page 1 and signer two's fields on page 2, sent, had each
  signer open their portal and confirmed each saw *only* their own
  field(s) on the correct page, signed both, downloaded the final signed
  PDF and confirmed: still exactly 2 pages (no appended page), "Signer
  One" text present on page 1 and absent from page 2, "Signer Two" text
  present on page 2 and absent from page 1, certificate downloadable,
  contract stage reached `signed`. All synthetic data cleaned up
  afterward.
- **Real API/DB smoke — template creation**: listed templates, opened the
  Master Service Agreement detail, confirmed description/variables/clauses
  present, filled all variables, previewed (confirmed substitution),
  created the contract, confirmed via direct DB read-back: `stage ==
  draft`, `template_id` set to the MSA template's real ID,
  `party_a`/`party_b` recorded, exactly one `ContractVersion` at
  `version_number = 1` with `source == "template_generated"`, the
  generated PDF (read back from storage) contains the substituted
  variable values, and `usage_count` incremented by exactly 1. Then ran
  the normal `/extract` endpoint on it and confirmed it completes
  (`status: ready`) exactly like an uploaded contract. Synthetic contract
  and usage-count bump reverted afterward.
- **Manual/browser smoke**: not literally executed — no browser
  automation tool is available in this session. The scripted API/DB
  traces above exercise the identical backend code paths the UI calls,
  including the exact request sequence a browser session would produce
  (create → block-until-fields → place → send → open per-signer → sign →
  download/verify), and are the closest rigorous equivalent available.

## Honest limitations

- **Field placement UI is click-to-place, not drag-to-resize.** An
  internal user picks a signer/type and clicks a spot on the page; there
  is no resize handle. This was a deliberate scope call to keep the
  placement UI shippable within this fix's boundaries — fields can still
  be removed and re-placed.
- **AI suggestion is a heuristic, not a real layout-understanding model.**
  It proposes one signature field per signer near the bottom of the last
  page, staggered so ordered signers don't overlap — it does not analyze
  the document to find an actual signature block or "Signature:" line.
  This satisfies "visibly marked, must be confirmed" but should not be
  read as AI document understanding.
- **Non-signature field types (`initials`/`name`/`date`) are
  auto-filled, not separately captured from the signer.** When a signer
  submits their signature, any `initials`/`name`/`date` fields belonging
  to them are filled deterministically (derived initials, their name on
  file, the signing timestamp) rather than prompting for separate input.
  This keeps the existing single-capture signing UX intact while still
  giving internal users real per-field-type placement control.
- **Legacy signature requests created before this fix** (none exist in
  the demo dataset as of this change, but the code path is defensive)
  have no persisted fields and fall back to the old appended-summary-page
  behavior if their PDF is ever regenerated — they cannot retroactively
  gain placement without a human placing fields, which `send_request()`
  no longer allows for *new* requests but cannot enforce retroactively
  on already-sent ones.
- **Template documents are generated with PyMuPDF's basic text-box
  layout** (title + clause sections stacked per page), not a rich
  document-formatting engine — acceptable for the demo generation flow,
  not a substitute for a real templating/merge engine.
- **The four seed templates' variables/clauses are illustrative**,
  written for this fix, not sourced from real legal templates — same
  caveat the original frontend-only seed list already carried, just now
  backed by real generation instead of a dead-end redirect.

## Demo instructions

**Signature placement**: open a contract at `ready_to_sign` → Signature
tab → Create Signature Request (define signers) → in the new "Signature
placement in the document" card, pick a signer and field type, click on
the rendered page to place a field (or click "Suggest signature fields
with AI" and then Save to confirm the suggestion) → repeat for every
signer → Save field placement → Send (disabled until every signer has a
signature field) → open the generated `/sign/{token}` link for each
signer in turn — the real document renders with a "Field 1 of N"
indicator and a jump button to their highlighted field → sign → download
the completed contract and certificate once all signers finish.

**Template creation**: Templates page → pick a card → review the detail
page → "Create Contract from Template" → fill the variable form → Preview
document → Confirm and create contract → redirected straight into the new
contract at `draft`, ready to continue through Mark Ready for Client
Review exactly like an uploaded contract.
