# Demo Readiness — Final Report

**Release:** SMTP review/signature golden path
**Plan:** `docs/superpowers/plans/2026-08-05-golden-path-release.md`
**Design:** `docs/superpowers/specs/2026-08-05-golden-path-release-design.md`
**Date:** 2026-08-06
**Branch:** `feature/timeline-payment-tracker`

## 1. The one demonstrable path

```
Upload → AI extraction → client review email → public review →
request changes → negotiation (AI counterproposal) → client accepts →
internal approval (4 ordered roles) → ordered signature emails →
both signers sign → signed artifacts (PDF + certificate) →
manual activation
```

This exact path is proven end to end, against the live API and a real
Postgres database, by `scripts/golden_path_smoke.py`. It uses a local
capture SMTP server (no real inbox, no external provider) so every email
send is a real SMTP transaction that is asserted, not mocked.

## 2. Evidence

### 2.1 Golden-path smoke (`scripts/golden_path_smoke.py`)

```
$ backend/.venv/bin/python3 scripts/golden_path_smoke.py
{
  "base_url": "http://127.0.0.1:8000",
  "smtp": "127.0.0.1:1025",
  "checks_total": 69,
  "checks_passed": 69,
  "checks_failed": 0,
  "cleanup": {
    "deleted_contracts": 1,
    "remaining_golden_path_contracts": 0,
    "db_residue": {
      "outbound_messages": 0, "review_requests": 0, "negotiations": 0,
      "approval_workflows": 0, "approval_steps": 0, "signature_requests": 0,
      "activity_events": 0, "contract_versions": 0, "signature_signers": 0
    },
    "storage_keys_tracked": 6,
    "storage_keys_removed_in_cleanup": [ "...6 files, all removed..." ]
  },
  "error": null
}
```

Full per-check detail is written to `scripts/golden_path_smoke_results.json`
on every run (gitignored-equivalent scratch artifact, regenerated each time).

What it proves, concretely:

- Real upload (`POST /api/contracts`) + real AI extraction
  (`POST /api/contracts/{id}/extract`) against the configured OpenAI key —
  content is treated as provider-dependent (not asserted), only structural
  success is (`supported: true`, extraction succeeded).
- Review invitation delivered through local SMTP: captured message is
  multipart (text + html), carries the exact `/review/{token}` portal
  link, contract enters `client_review`.
- Public client requests changes with a comment → negotiation row seeded,
  contract enters `negotiation`. A duplicate decision on the now-closed
  review is rejected `409 review_closed` (stale/duplicate-mutation check).
- Real AI negotiation analysis (`POST /api/negotiation/analyze`) — again
  provider-dependent content, checked structurally
  (`workflow_status: ready`, non-empty counter wording).
- Legal approves the AI wording (`status: approved`) and sends it
  (`POST /negotiations/{id}/send`) — this step intentionally does **not**
  go through SMTP (see §6, negotiation follow-up email is deferred scope);
  the public follow-up link is used directly, matching the design doc's
  "negotiation agreement" language (not "negotiation email").
- Public client accepts the counterproposal → negotiation resolves
  `accepted`, contract enters `internal_review`.
- Four ordered internal approvals (`business_owner → legal → finance →
  executive`) → contract enters `ready_to_sign`, current version
  `approved`.
- Signature request created with two ordered signers (no emails sent yet),
  then explicit Send invites **only** the first signer — delivered through
  local SMTP, captured message carries the exact `/sign/{token}` link.
- Signer one opens and signs → contract `partially_signed`, signer two is
  auto-invited and that invitation is also captured over local SMTP.
  Signer one attempting to sign again is rejected `409 signer_closed`
  (stale/duplicate-mutation check).
- Signer two opens and signs → contract `signed`, current version
  `signed`, signed PDF + certificate PDF both download as real PDFs.
- Manual activation by an authorized role (`legal`) with a non-empty
  reason and evidence → contract `active`.
- Read-back verification: contract summary, dashboard summary, and
  version lineage (showing both the original version and the
  negotiation-counterproposal version) all return `200`; the full
  activity-event trail contains every expected canonical event
  (`version_sent_for_review` … `contract_activated`); outbound-message
  row counts are exact (`1` review invitation, `2` signature invitations).
- **Cleanup**: the synthetic contract and every cascaded row (outbound
  messages, review/negotiation/approval/signature rows, activity events,
  versions) are deleted, and all 6 tracked storage files (original,
  signed PDF, certificate, two signature-value files) are removed and
  verified gone. Zero residue.

### 2.2 Local SMTP integration test (`backend/tests/test_smtp_local_integration.py`)

```
$ pytest tests/test_smtp_local_integration.py -q
2 passed
```

Asserts, per email type (review invitation, signature invitation):
real multipart MIME (`text/plain` + `text/html`), non-empty single-line
subject, exact portal-URL presence (decoded through the MIME
transfer-encoding so a soft-wrapped long link is still matched
correctly), and that the `PORTAL_TOKEN_SECRET` value never appears
anywhere in the message.

### 2.3 Backend test suite

```
$ pytest -q
392 passed, 1 failed, 10 warnings in ~564s
```

The one failure, `test_review_lifecycle_integration.py::
test_review_resend_cooldown_is_deterministic`, is a **pre-existing**
mismatch, not a regression from this work: Task 4's fix round 1
(commit `8aea0c0`, "fix(signature): harden public lifecycle actions")
intentionally changed `enforce_resend_cooldown` so a **failed** delivery
no longer starts the cooldown (an operator can retry immediately after a
failure) — see `.superpowers/sdd/2026-08-05-golden-path-release/
task-4-report.md` and the dedicated passing test
`test_outbound_messages.py::test_failed_delivery_does_not_start_resend_cooldown`.
This one Task-3-era test still exercises the old "cooldown applies even
after a failed send" assumption and was never updated for that
intentional Task 4 change. It was found, diagnosed, and a fix was drafted
during this session; the fix was explicitly declined ("ignore the
previously rejected test edit... do not rewrite completed work") so the
test is left as-is and reported here instead. It does not affect the
golden path or any currently-shipped behavior — the behavior it asserts
was deliberately superseded three commits before this release finished.

Two other tests (`test_approval_lifecycle_integration.py::
test_overridden_negotiation_no_longer_blocks_final_approval` and
`test_signature_lifecycle_integration.py::
test_bundle_exposes_persisted_signer_delivery_only_for_eligible_signer`)
were observed to fail once during a full-suite run earlier in this
session, alongside the cooldown failure. Both pass individually and
pass when their whole file is run in isolation; re-running the full suite
afterward reproduced only the one known cooldown failure. This is
consistent with order-dependent flakiness in the ~390-test full run, not
a deterministic defect — noted here for honesty, not treated as a
blocker.

### 2.4 Frontend

```
$ npm test        # vitest run --reporter=basic
 Test Files  9 passed (9)
      Tests  64 passed (64)

$ npx tsc --noEmit
(exit 0, no output)

$ npm run build
 ✓ Compiled successfully
 ✓ Generating static pages (19/19)
```

### 2.5 Other smokes run this session

- `scripts/approval_lifecycle_smoke.py`: 68/68 checks passed, zero DB
  residue. (Pre-existing approval guard-matrix smoke; run again here only
  to confirm the `version_lineage.py` fix below didn't regress it.)
- `scripts/qa_api_smoke.py`: 21/22 endpoint checks passed (12/12 negative,
  10/10 DB-integrity). The one failure, `POST /api/flowdown` returning
  `422` instead of `200`, is in an unrelated subsystem (flowdown/
  placeholders) never touched by this release; not investigated further
  as out of scope.

## 3. Blocker found and fixed during this work

While building the golden-path smoke, `GET /api/contracts/{id}/versions/
lineage` returned `500` the first time it was exercised with real
approved approval steps. Root cause:
`backend/app/services/version_lineage.py` referenced
`ApprovalStep.decided_at`, a column that does not exist on the model
(the real column is `acted_at` — see `backend/app/models.py`). Fixed
both references (`timestamp` and `_sort_ts`) to use `step.acted_at`.
This is a one-line-class fix to a genuinely broken, previously-unexercised
endpoint, not a design change, and is covered by the golden-path smoke's
lineage read-back assertion going forward.

## 4. Known pre-existing gap this release bridges (not fixed)

`POST /api/contracts` (the frozen F1 upload endpoint) never fires the
`contract_ready_for_client` lifecycle event, so a freshly uploaded
contract is left at the `contracts.stage` **database default**
(`'negotiation'` — see `database/migrations/011_approval_workflow.sql`)
instead of entering the `draft → ready_for_client → client_review`
pipeline the lifecycle engine otherwise encodes; nothing in the current
codebase ever calls that transition. `scripts/golden_path_smoke.py`
bridges this one gap with an explicit, audited stage write (a plain
`UPDATE` plus a `contract_stage_changed` activity row — the same effect
as the existing `app.services.lifecycle.set_stage` legacy-compat helper)
immediately after extraction, and documents it in the script's own
docstring. The frozen upload endpoint itself was not touched. This is
pre-existing structural debt outside the scope of Tasks 1–5 (which build
on whatever stage a contract already happens to be in); it did not block
this release but is worth a follow-up ticket to wire
`CONTRACT_READY_FOR_CLIENT` into the real upload/extract flow.

## 5. SMTP status and setup for this demo

This machine's `backend/.env` (gitignored, not committed) is now
configured for a **working local demo**, not a real inbox:

```
APP_ENV=local
EMAIL_DELIVERY_ENABLED=true
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=contracts@contractops.local
SMTP_FROM_NAME=ContractOps Demo
SMTP_USE_TLS=false
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=5
PUBLIC_APP_URL=http://localhost:3000
PORTAL_TOKEN_SECRET=<generated, 48-byte random token>
```

`PORTAL_TOKEN_SECRET` is mandatory for *any* review/signature link to be
generated (`portal_token_secret_missing` otherwise) — it was previously
unset on this machine (flagged as a deferred blocker after Task 2); it is
now set. With no local capture SMTP server listening on `127.0.0.1:1025`,
sends will safely resolve to `failed` / `smtp_connection_failed` — the
workflow still proceeds (review/signature request created, stage
transitions happen), Retry and Copy Link remain available. This is the
designed graceful-failure path (`app/services/outbound_messages.py:
deliver_pending_attempt` catches `EmailDeliveryError` and records
`failed` rather than raising).

**Real-inbox delivery is not claimed and was not executed.** To actually
deliver to a real mailbox: replace `SMTP_HOST`/`SMTP_PORT`/
`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_FROM_EMAIL` with real provider
credentials, and set `APP_ENV=demo` or `APP_ENV=production` plus a real
externally-reachable **HTTPS** `PUBLIC_APP_URL` (the HTTPS/non-localhost
check in `email_delivery._validate_public_url` only activates for
`demo`/`production`, so this environment's `APP_ENV=local` intentionally
skips it — do not set `local` when demoing over a real domain).

### 5.1 HTTPS / tunnel requirement

For a demo where a real external recipient must click the review/sign
link from an email or from outside this machine, `PUBLIC_APP_URL` (and
the frontend's own public URL, which the emailed links are built from via
`REVIEW_BASE_URL`) must be an HTTPS URL reachable from the internet
(e.g. an ngrok/Cloudflare tunnel in front of `localhost:3000`, or a real
deployed frontend). None of that is configured on this machine; today's
demo is entirely `localhost`-scoped by design.

## 6. Deferred scope (unchanged from the design doc)

Gmail API, Microsoft Graph, SendGrid, Resend, Signit, DocuSign, certified
e-signature assertions, queues, analytics, reports, dashboards, global
stage migration, old-data backfill, and broad notification/UX refactors.
Additionally, confirmed during this session: the negotiation
counterproposal follow-up email (`POST /api/negotiations/{id}/send`)
returns email content in its response but does not persist an outbound
attempt or call SMTP — only the initial review invitation and signature
invitations go through the delivery boundary built in Tasks 1–4. This
matches the design doc's wording ("negotiation agreement", not
"negotiation email") and is exercised in the golden path via the token
returned directly by the API, not an emailed link.

## 7. Prototype disclosure

The local signature implementation is a **demo / prototype electronic
signature** ("Demo electronic signature / توقيع إلكتروني تجريبي"),
not a certified legally binding e-signature provider. This label is
persistent and bilingual on the public signer page and was verified
present by the Task 5 frontend test suite
(`app/sign/[token]/page.vitest.tsx`).

## 8. Startup commands

```bash
# Database (once, or after adding a new migration)
python database/migrate.py

# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
#  --reload is convenient for development, but note: env vars are only
#  re-read from .env when the worker process itself restarts, not on
#  every --reload code-change cycle.

# Frontend
cd frontend
npm run dev            # http://localhost:3000

# Golden-path smoke (needs the backend already running)
python3 scripts/golden_path_smoke.py

# Local SMTP integration test (self-contained, no running server needed)
cd backend && pytest tests/test_smtp_local_integration.py -q
```

## 9. 5–7 minute demo script

1. **Upload** (`/upload`): upload a real PDF/DOCX contract. Extraction
   runs automatically; wait for clauses/obligations to populate.
2. **Send for review** (`/contracts/[id]`): open the Review panel, fill
   in a client name/email, Send. Point out the delivery badge (Sent),
   recipient, and timestamp; show Copy Link.
3. **Public review** (open the copied link in a new tab/incognito):
   walk the bilingual public review page, click "Request changes" with a
   short comment.
4. **Negotiation** (`/negotiations` or the contract's negotiation panel):
   run AI analysis on the client's comment, show the generated
   counter-wording (EN/AR), approve it, send the updated terms.
5. **Public accept**: open the new public review link, approve the
   updated terms — point out the contract now shows two versions in
   version history/lineage.
6. **Approvals** (`/approvals` or the contract's approval panel): start
   the workflow, approve as each of the four roles in order (switch the
   demo role header each time) — call out that each step unlocks only
   the next one, and skipping ahead is rejected.
7. **Signature** (`/contracts/[id]` signature panel): create a signature
   request with two ordered signers, Send — only the first signer is
   invited; show the delivery badge and Copy Link for that signer.
8. **Public signing**: open signer one's link, sign (typed signature +
   consent) — point out signer two's invitation appears immediately
   after, then open signer two's link and sign.
9. **Signed artifacts + activation**: show the signed PDF and signature
   certificate downloads, then manually Activate with a reason/evidence
   as an authorized role — contract is now `active`.

## 10. Recovery actions

- **Delivery failed / no local SMTP listener running**: the workflow is
  never blocked — Retry re-attempts the same link (safe, idempotent);
  Copy Link always works regardless of delivery status.
- **Wrong demo role selected mid-approval**: the API rejects
  out-of-order/wrong-role approvals deterministically
  (`403 approval_role_required` / `409 approval_out_of_order`); nothing
  is corrupted, just re-select the correct role header and retry.
- **Stale tab / superseded version**: any action against a superseded
  review, negotiation, or signature returns a deterministic
  `409 workflow_stale`; refresh the page to pick up the current state.
- **Local backend restarted mid-demo**: since `.env` is only re-read at
  process start, if SMTP/portal-secret env vars were changed, fully stop
  and restart the `uvicorn` process (not just save the file) before
  continuing.
- **Smoke residue suspected**: `scripts/golden_path_smoke.py` and
  `scripts/approval_lifecycle_smoke.py` both delete every row and file
  they create in a `finally` block and print a residue report; re-running
  either after an aborted demo is safe.

## 11. Limitations

- No real-inbox email was sent or received in this session — only local
  SMTP capture, which is a real SMTP transaction but not a real mailbox.
- Browser/manual click-through smoke (design doc §"Perform browser/
  manual smoke where available") was **not executed** this session; the
  frontend dev server was left running throughout and `npm test` +
  `tsc --noEmit` + `npm run build` all pass, but no manual browser pass
  was performed. Recorded honestly rather than assumed.
- The one stale backend test (§2.3) and the one unrelated `qa_api_smoke.py`
  flowdown failure (§2.5) remain open, both explicitly out of this
  release's scope.
- The `draft → ready_for_client` gap (§4) means any *other* caller of the
  real upload API (outside this smoke script) will also need that bridge
  until a follow-up wires `CONTRACT_READY_FOR_CLIENT` into
  upload/extract.

## 12. Real-inbox delivery checklist (not executed — for a future session)

- [ ] Real SMTP credentials for `SMTP_HOST` / `SMTP_PORT` /
      `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` from an actual
      provider (e.g. a transactional-email SMTP relay).
- [ ] `APP_ENV=demo` or `production`.
- [ ] `PUBLIC_APP_URL` set to a real, externally reachable **HTTPS** URL
      (tunnel or real deployment) — required by
      `email_delivery._validate_public_url` once `APP_ENV` leaves
      `local`.
- [ ] `REVIEW_BASE_URL` (or its replacement) pointed at that same public
      HTTPS frontend URL so emailed links resolve for an external
      recipient.
- [ ] Send one review + one signature invitation to a real mailbox you
      control and confirm receipt, rendering, and that the links open the
      live public pages.
- [ ] Re-run `scripts/golden_path_smoke.py` against that live
      configuration to confirm the full path still holds with real
      delivery instead of local capture.

---

Commit for this work:

`feat(release): complete SMTP review, signature lifecycle, and golden path`
