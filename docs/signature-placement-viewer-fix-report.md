# Signature Field-Placement Document Viewer — Fix Report

Status: Applied and verified. Branch `feature/timeline-payment-tracker`.
Scope: the document viewer inside "تحديد موضع التوقيع في المستند" (the
signature field-placement panel) only. No signature lifecycle logic
(request creation, sending, signing, embedding, certificate generation,
lifecycle transitions) was touched.

---

## Root cause

`frontend/components/SignatureFieldPlacer.tsx` fetched
`fetchContractFileBlob(contractId)` → `GET /api/contracts/{id}/file`,
which returns the **contract's raw uploaded file, byte-for-byte, with its
real MIME type**. For any contract whose original upload was a `.docx`
(or any non-PDF format), this endpoint returns actual Word/other bytes —
not a PDF. The component then fed those bytes straight into
`pdfjs.getDocument({ data: buf })`, which threw immediately (invalid PDF
header), setting `pdfError = true`. The component's only response to that
error state was:

```tsx
{pdfError ? (
  <p className="text-sm text-danger-600">{t("detail.viewer.pdfFallback")}</p>
) : ( /* canvas + page nav */ )}
```

`detail.viewer.pdfFallback` is the exact string from the bug report:
*"تعذّر عرض ملف PDF. يتم عرض النص المستخرج الآمن بدلاً منه."* ("The PDF
could not be displayed. Showing the safe extracted-text fallback
instead.") — **but no text fallback was ever fetched or rendered.** The
component had no code path that called the extracted-text endpoint at
all. The message was aspirational, not descriptive: it claimed a
fallback that the component was never wired to produce.

### Confirmed live, against the real demo dataset

```
$ curl .../api/contracts/{id}/file       →  200, application/vnd.openxmlformats...  (real DOCX bytes)
$ curl .../api/signature-requests/{id}/document (new endpoint) → 200, application/pdf (real, renderable PDF)
```

The demo contract behind this exact bug report is DOCX-sourced. Every
DOCX-sourced contract's signature field-placement panel was broken this
way — this was not an edge case, it was the default for any non-PDF
upload, which is why it was flagged release-blocking.

### The audit, point by point

| Audit item | Finding |
|---|---|
| Current version source file type | `Contract.file_url` — whatever the original upload was (PDF, DOCX, or none); no per-version file type guarantee |
| Original file path | `Contract.file_url` — the raw upload, served as-is by `/api/contracts/{id}/file` |
| Generated/renderable PDF path | `SignatureRequest.original_file_url` — a **real PDF snapshot**, already computed at `create_request()` time by `signature_pdf.py::original_bytes()` (pass-through if the upload was really a PDF; otherwise a PDF generated from the extracted text via PyMuPDF) — this existed all along, for the public signer portal, and was simply never used by the internal placement viewer |
| Document/content endpoint used by the buggy viewer | `GET /api/contracts/{id}/file` — raw passthrough, no format guarantee |
| MIME type / Content-Disposition | Correctly reflects the real file (`application/vnd.openxmlformats...` for `.docx`) — the endpoint was behaving correctly; it was simply the wrong endpoint for this use case |
| Frontend PDF viewer URL construction | `fetchContractFileBlob(contractId)` — contract-scoped, not request/version-scoped |
| Auth/CORS | Bearer token + `X-Demo-Role` header, same-origin API base — not implicated; both old and new endpoints use the same pattern |
| DOCX/template PDF rendition | **Already existed** for the public flow (`original_bytes()`/`SignatureRequest.original_file_url`) — just not reused internally |
| Extracted-text endpoint/field | `GET /api/contracts/{id}/raw?page=N` → `{ text, blocks, total_pages, ... }` — exists and is used correctly elsewhere (`SourceViewer.tsx`), but was never called by `SignatureFieldPlacer.tsx` |
| Fallback rendering component | Did not exist in `SignatureFieldPlacer.tsx` — only the claim-text `<p>` |
| Loading/empty/error precedence | No loading state existed at all (blank UI while fetching, indistinguishable from "broken"); error state showed the misleading message; no distinct "genuinely nothing available" state existed |

---

## Fix

### Backend — one new, read-only, internal endpoint

`app/services/signature.py`:
- Extracted the existing public logic
  (`get_document_bytes(raw_token, db)`'s snapshot-then-regenerate
  behavior) into a shared helper, `_document_bytes_for_request(req, db)`.
- Added `get_document_bytes_for_request(request_id, db)` — the same
  guaranteed-renderable-PDF logic, addressed by `request_id` instead of a
  signer's public token, for internal (bearer-token) callers.

`app/routers/signature.py`:
- `GET /api/signature-requests/{request_id}/document` — protected route
  (same auth pattern as every other internal signature endpoint), returns
  `application/pdf`, 404 `not_found` for an unknown request.

This is the **exact same document** the public signer will eventually
see for that request — tied to the request's own `version_id`, so the
placement viewer and the actual signing experience can never disagree
about which document is being annotated.

No change was made to `create_request()`, `send_request()`,
`submit_signature()`, `build_signed_pdf()`, staleness checks, or any
lifecycle transition — this fix only adds a new way to *read* a document
that was already being computed and stored.

### Frontend — real state machine, real fallback

`frontend/components/SignatureFieldPlacer.tsx` was rewritten around an
explicit `ViewerState = "loading" | "pdf" | "text" | "empty"`:

1. **`loading`** — shown immediately on mount / on `requestId` change,
   distinct from both success and error (`t("common.loading")`).
2. Fetches `fetchSignatureRequestDocumentBlob(requestId)` (new API
   function, hits the new endpoint) instead of the contract's raw file.
3. **`pdf`** — if pdfjs parses the fetched bytes successfully (now the
   overwhelmingly common case, since the endpoint always returns a real
   PDF), renders every page via the existing canvas + page-nav UI,
   unchanged from before.
4. **`text`** — if PDF parsing genuinely still fails (corrupted blob,
   worker failure — a real defensive path, not the primary fix target
   anymore since the source is now always a real PDF), fetches
   `GET /api/contracts/{contractId}/raw?page=1` and renders the **actual
   extracted text**, with clause-level blocks (heading + body, using the
   same `blocks`/`direction` layout data `SourceViewer.tsx` uses) when
   available, or plain paragraph text otherwise. Page navigation refetches
   the corresponding page. The "PDF could not be displayed" disclosure now
   renders **above real, visible content** — never alone over a blank
   area.
5. **`empty`** — if neither the PDF nor the extracted text can be
   obtained (e.g. a contract with no `raw_text` at all), shows a distinct,
   honest, deterministic message: *"تعذّر عرض المستند: لا يوجد ملف PDF
   صالح ولا نص مستخرج لهذا العقد..."* — never the "showing extracted text"
   claim when nothing is actually shown.
6. **Field placement is click-driven on whichever visible surface is
   active** (`pdf` canvas or `text` container) — the same coordinate math
   (`getBoundingClientRect()`-relative x/y) works identically for both, so
   a deterministic page + normalized position is always recorded
   regardless of which representation is showing.
7. **"Save field positions" is disabled** whenever `hasVisibleDocument`
   is false — i.e. during `loading` and in the `empty` state — in
   addition to the pre-existing "at least one field" gate. A warning
   (*"يجب تحميل نسخة مرئية من المستند قبل حفظ مواضع الحقول"*) explains
   why when relevant.
8. The document fetch is keyed on **`requestId`**, not `contractId` —
   switching to a different signature request (a new version's request)
   refetches and re-renders from scratch, since each request is pinned to
   its own version's document snapshot.

---

## Files changed

Backend:
- `app/services/signature.py` — `_document_bytes_for_request()` (shared
  helper), `get_document_bytes_for_request()` (new).
- `app/routers/signature.py` — `GET /signature-requests/{id}/document`
  (new).
- `tests/test_signature_document_viewer.py` (new, 7 tests).

Frontend:
- `components/SignatureFieldPlacer.tsx` — rewritten around the
  `ViewerState` state machine described above.
- `lib/api.ts` — `fetchSignatureRequestDocumentBlob()` (new).
- `lib/i18n.tsx` — `signature.fields.noDocument`,
  `signature.fields.documentRequired` (new keys, Arabic + English).
- `components/SignatureFieldPlacer.vitest.tsx` — rewritten/expanded (14
  tests, 10 new).
- `components/SignaturePanel.vitest.tsx` — mock updated for the renamed
  dependency (`fetchSignatureRequestDocumentBlob`/`api` instead of
  `fetchContractFileBlob`).

## Before / after

| | Before | After |
|---|---|---|
| DOCX-sourced contract | Blank viewer + misleading "showing text fallback" message | Renders the guaranteed-PDF snapshot (real content, generated from extracted text) |
| PDF-sourced contract | Worked (when the raw file happened to be a real PDF) | Still works, now via the request-scoped, version-pinned endpoint |
| Genuinely broken PDF bytes | Same misleading message, blank area | Real extracted-text fallback rendered, with the disclosure shown alongside actual content |
| No PDF and no extracted text at all | Same misleading message | Distinct, honest "cannot be displayed, no valid PDF or extracted text" message |
| Save button | Enabled once ≥1 field existed, regardless of whether anything was visible | Also requires a visible document representation (`pdf` or `text` state) |
| Document source | Contract's raw upload (`/contracts/{id}/file`) | Signature request's own version-pinned PDF snapshot (`/signature-requests/{id}/document`) |

---

## Tests

Backend (`tests/test_signature_document_viewer.py`, all new):
1. `test_uploaded_pdf_renders_in_placement_view`
2. `test_uploaded_docx_obtains_a_renderable_representation` — first
   confirms the raw contract-file endpoint really does return non-PDF
   bytes (proving the bug is real), then confirms the new endpoint
   returns a real PDF containing the actual extracted clause text.
3. `test_generated_template_contract_renders`
4. `test_document_endpoint_falls_back_to_regenerating_when_snapshot_missing`
   — defensive path when `original_file_url` is unexpectedly absent.
5. `test_unknown_request_returns_deterministic_not_found`
6. `test_document_is_tied_to_the_exact_version_the_request_was_created_against`
7. `test_stale_version_cannot_receive_fields` — confirms the pre-existing
   `replace_fields()` staleness guard (unchanged) still refuses to attach
   fields to a request whose version has been superseded, even though the
   document remains viewable.

Frontend (`components/SignatureFieldPlacer.vitest.tsx`, 10 new + 4
pre-existing):
- Fetches the request's own document, not the contract's raw file.
- PDF renders in the placement view.
- DOCX/template-sourced request (endpoint already returns a real PDF) —
  renders identically, no frontend special-casing needed.
- Broken PDF falls back to real extracted text, not a blank area.
- Text fallback includes actual extracted contract content.
- Text fallback renders clause block layout (heading + body) when
  available.
- No-document state shows the honest, distinct error — never the
  misleading fallback claim.
- Save disabled while the viewer shows no document (empty state).
- Save disabled while the document is still loading.
- Switching `requestId` refetches and refreshes the displayed document.
- All 4 pre-existing behaviors (missing-signer warning, click-to-place +
  save, AI-suggested-field marking, locked-after-send) still pass
  unchanged.

## Verification

- **Focused backend**: `tests/test_signature_document_viewer.py` — 7/7.
  `tests/test_signature_field_placement.py` (pre-existing, unaffected) —
  green. `tests/test_signature_lifecycle_integration.py` (pre-existing,
  unaffected) — green.
- **Focused frontend**: `components/SignatureFieldPlacer.vitest.tsx` —
  14/14. `components/SignaturePanel.vitest.tsx` — 22/22 (mock updated for
  the renamed dependency, no behavioral change).
- **Full frontend suite**: 167/167 (10 net new).
- **TypeScript**: `npx tsc --noEmit` — clean.
- **Production build**: `npm run build` — compiled successfully, all
  routes unchanged.
- **Real API smoke**, against the live backend and the actual demo
  contract behind this bug report (DOCX-sourced, request id
  `a678f3b8-...`):
  ```
  GET /api/contracts/{id}/file                        → 200, DOCX bytes (confirms the bug's source)
  GET /api/signature-requests/{id}/document (new)      → 200, application/pdf, 1 real page, real extracted text
  ```
  Confirmed the returned PDF opens and its text content is the contract's
  actual extracted text, not a placeholder.
- **Browser/manual smoke**: not literally executed — no browser
  automation tool is available in this session. The live API trace above
  exercises the exact request the browser's `fetch()` call would make and
  confirms the response is what the rewritten viewer now expects (a real,
  parseable PDF) instead of what it received before (raw DOCX bytes that
  pdfjs could never parse).

## Remaining limitations

- The `text` (extracted-text) fallback path is now a genuine defensive
  path rather than the primary fix — since `/signature-requests/{id}/document`
  always returns a real PDF, PDF parse failures should be rare (network
  interruption, browser PDF worker crash, storage corruption). It is
  still fully implemented and tested, not left as dead code.
- Text-fallback mode does not render a literal page image — clicking to
  place a field records a normalized position relative to the rendered
  text container, not relative to a true page layout. This is an honest
  trade-off: the alternative (blocking placement entirely without a PDF)
  would leave the internal user unable to configure a route at all for a
  document that can only ever produce extracted text.
- No change was made to how `original_bytes()` generates a PDF from
  extracted text (still a simple single-page-per-language text box,
  pre-existing from earlier work) — this fix is scoped to *using* that
  existing capability from the internal viewer, not improving its layout
  fidelity.
