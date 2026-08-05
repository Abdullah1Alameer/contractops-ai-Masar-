# ContractOps AI — System Feature and Workflow Audit

Audit date: 2026-08-05  
Repository: current local working tree  
Method: static chain tracing, database inspection, API smoke execution, backend/frontend verification, route crawl, and targeted runtime reproduction. No uploaded contract contents or personal data are included.

## Evidence labels

- **INSPECTED** — code, schema, wiring, or configuration was traced.
- **EXECUTED** — a command/API/database path was run during this audit.
- **MANUALLY_UNVERIFIED** — browser behavior was not exercised with Playwright/Cypress.
- **PROVIDER_UNVERIFIED** — requires OpenAI or an external provider not exercised here.

The status labels in this report use exactly the requested vocabulary. Under the strict definition, the presence of code or passing unit tests is not sufficient for `FULLY_WORKING`.

# 1. Executive Summary

## Readiness

- **Overall implementation readiness: 54%**
- **End-to-end product readiness: 18%**
- **UX readiness: 41%**
- **Golden lifecycle readiness: 25%**

These are conservative weighted estimates based on complete-chain evidence, not file counts. The production frontend cannot currently build, browser E2E automation is absent, and the database contains no persisted review, negotiation, approval, signature, monitored-thread, review-package, or summary records.

## Status counts

Across the 39 audited feature groups:

- `FULLY_WORKING`: **0**
- `PARTIALLY_WORKING`: **16**
- `UI_ONLY`: **3**
- `BACKEND_ONLY`: **4**
- `PLACEHOLDER`: **6**
- `BROKEN`: **4**
- `DEAD`: **2**
- `NOT_IMPLEMENTED`: **3**
- `UNVERIFIED`: **1**

Zero `FULLY_WORKING` is intentional: no major user workflow has both complete browser proof and persisted end-to-end state under the definition supplied for this audit.

## Top five blockers

1. **P0 — Production build fails.** `npm run build` fails while minifying `pdf.worker.min.mjs`: `import.meta cannot be used outside of module code`.
2. **P0 — PDF.js breaks server rendering.** `/flowdown` returns HTTP 500 because importing `SourceViewer` evaluates PDF.js on the server: `DOMMatrix is not defined`.
3. **P1 — DOCX upload is broken.** `_docx_blocks()` accesses nonexistent `CT_PPr.bidi`; valid DOCX/Arabic-filename smoke uploads return 422.
4. **P1 — Lifecycle is not continuous.** Review decisions and negotiation actions do not update `contracts.stage`; frontend pipeline keys and backend `workflow_summary` shapes disagree.
5. **P1 — Core lifecycle remains unproven.** Current DB has no review/approval/signature/negotiation records; tests predominantly mock services and stage transitions.

## Execution results

- **Backend:** `197 passed, 7 warnings` — EXECUTED.
- **Frontend Vitest:** `2 passed` — EXECUTED.
- **TypeScript:** `npx tsc --noEmit` passed — EXECUTED.
- **Production build:** failed — EXECUTED.
- **Lint:** failed operationally because `next lint` opens the interactive first-time ESLint setup; no configured noninteractive lint gate.
- **API smoke:** 7 endpoint checks passed, 2 failed; 10/10 negative checks and 6/6 orphan checks passed.
- **Route crawl against dev server:** most static routes returned 200; `/flowdown` returned 500. Public route results became unreliable after concurrent `.next` build artifacts changed, so those are MANUALLY_UNVERIFIED rather than classified from that crawl.
- **Browser automation:** no project Playwright/Cypress suite.
- **DB integrity:** no clause/extraction/version orphans in targeted checks. Four processing contracts were older than one hour at one sampling point.
- **DB feature usage:** 0 summaries, reviews, negotiations, approvals, signatures, monitored threads, and review packages; all sampled contracts had `stage=negotiation`; 0 contracts had `page_layout`.

# 2. Feature Status Matrix

| Feature | Status | UI | API | Service | DB | AI | Persistence | Tests | Evidence | Main issue | Recommended action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Landing/Home pipeline | BROKEN | Yes | Real summary/list | Real aggregate | Real | No | Read-only | Unit shape only | INSPECTED | FE expects `workflow_summary.review`; API emits `review_status`; stale filter links | Fix shape and URL filters |
| Dashboard | PARTIALLY_WORKING | Yes | `/dashboard/summary` real | Aggregate | Real | No | Read-only | API/query ceiling | EXECUTED | Uses wall clock, not demo clock; some links ignore `role`; overdue mapping not rendered | Align clock/filters |
| Reports | UI_ONLY | Yes | Contracts list only | None | No report rows | No | No | None | INSPECTED | “Turnaround” is signature count; no export/report generation | Relabel or hide |
| PDF upload | PARTIALLY_WORKING | Yes | Yes | Storage + preflight | Contract/version | Extraction later | Yes | No full HTTP upload test | INSPECTED | No duplicate detection/progress; browser path unverified | Add integration/E2E |
| DOCX upload | BROKEN | Yes | Returns 422 | `_docx_blocks` crashes | No valid new row expected | No | No | Missed by tests | EXECUTED | `CT_PPr.bidi` does not exist | Fix first |
| Classification/extraction | PARTIALLY_WORKING | Yes | Yes | Pipeline | Many tables | OpenAI | Yes | Mostly unit/mocked | INSPECTED | Post-processing failures swallowed; provider not exercised | Surface post-step status |
| AI Contract Reader | PARTIALLY_WORKING | Yes | Yes | Serializers | Extractions/clauses | Upstream | Yes | No browser E2E | INSPECTED | Complete rendering/refetch not proven | Add golden-path E2E |
| Original PDF viewer | BROKEN | Yes | File/raw work | Geometry stored only after reextract | `page_layout` | No | 0 rows populated | 1 mocked FE test | EXECUTED | Build/SSR PDF.js failures; existing contracts have zero blocks | Fix bundling + backfill |
| AI Summary | UNVERIFIED | Yes | Yes | Implemented | Table exists, 0 rows | OpenAI | Intended | Mocked service/component | EXECUTED/PROVIDER_UNVERIFIED | No persisted summary; production build blocks UI proof | Backfill and E2E |
| Risk analysis | PARTIALLY_WORKING | Yes | Yes | Deterministic | 2 findings | No | Yes | Band tests only | INSPECTED | Obligation `needs_review` check cannot occur with allowed statuses; source detail limited | Fix status model |
| Obligations | PARTIALLY_WORKING | Yes | GET/PATCH | Extraction/rebuild | 57 rows | Upstream | Yes | Minimal unit | EXECUTED read | No auto-overdue; re-extract can lose completion state | Preserve manual state |
| Notices | PARTIALLY_WORKING | Yes | Via detail/deadlines | Extraction + temporal | Persisted extraction | Upstream | Yes | Helper tests | INSPECTED | UI joins deadline by title/purpose string | Use stable IDs |
| Deadlines/demo clock | PARTIALLY_WORKING | Yes | Yes | Deterministic | 41 rows | No | Yes | Good unit coverage | EXECUTED read | Pipeline can swallow rebuild failure; dashboard clock diverges | Add post-step state |
| Payments | PARTIALLY_WORKING | Yes | Yes | Deterministic | 16 rows | Upstream | Yes | Good service tests | EXECUTED read | No complete browser/API persistence proof | Add seeded API E2E |
| Flowdown | BROKEN | Yes | Real | AI comparison | 92 findings | OpenAI | Yes | Unit tests | EXECUTED | `/flowdown` SSR 500; smoke POST 422 for available pair | Fix viewer import, seed pair |
| Client review portal | PARTIALLY_WORKING | Yes | Internal/public routes | Real | 0 rows | Dossier deterministic | Intended | Mocked service | INSPECTED | No SMTP; no stage transition; no persisted execution proof | Test and connect stage |
| Review email delivery | NOT_IMPLEMENTED | Copy-link only | No send route | Template builder only | Review row | No | Link only | Template unit | INSPECTED | No SMTP/provider | Label explicitly |
| Clause negotiation | PARTIALLY_WORKING | Yes | Yes | Real | 0 rows | OpenAI | Intended | Heavy mocks | PROVIDER_UNVERIFIED | Analyze not automatic; stage unchanged | Integration test |
| Negotiation monitor | PLACEHOLDER | Yes | Yes | Demo seed/simulated connector | 0 real rows | OpenAI | Demo | Unit mocks | INSPECTED | Demo inbox and outbound presented weakly as product | Label simulated |
| Gmail/Outlook | NOT_IMPLEMENTED | No settings | Factory selects | Every method raises | None | No | No | None | INSPECTED | Skeleton connectors | Hide config |
| Internal approvals | PARTIALLY_WORKING | Yes | Yes | Ordered workflow | 0 rows | No | Intended | Stage writer mocked | INSPECTED | No API/DB golden-chain proof; demo roles only | Integration E2E |
| Visual signature workflow | PLACEHOLDER | Yes | Yes | Local PDF/certificate | 0 rows | No | Intended | Service mocks | INSPECTED | Demonstration signature, not licensed/legal e-sign | Label demo |
| Signit | NOT_IMPLEMENTED | No usable settings | Factory selects | Raises | None | No | No | Skeleton test only | INSPECTED | Adapter TODO | Hide provider |
| Versions/history | PARTIALLY_WORKING | Yes | Yes | Real | 8 rows | Compare uses AI | Yes | Service tests | EXECUTED read | 31 contracts lacked versions at sampling; re-extract endpoint has no UI | Backfill/history E2E |
| Version re-extract | BACKEND_ONLY | No | `POST /versions/{id}/extract` | Real | Updates | OpenAI | Yes | Limited | INSPECTED | No UI path | Connect or document |
| Monitor create/link/version actions | BACKEND_ONLY | No | Multiple routes | Real/demo | Tables | Some AI | Intended | Unit only | INSPECTED | No usable frontend | Connect selectively |
| Re-extract text/layout | BACKEND_ONLY | No action | `POST /reextract-text` | Real | Layout/raw | No | Yes | Unit only | INSPECTED | Needed for all old PDFs, but unreachable | Add admin action |
| Uploaded signature method | BACKEND_ONLY | No | Accepted by backend | Real/demo | Signer | No | Yes | Service only | INSPECTED | Public UI offers draw/type only | Remove or expose |
| Activity/audit | PARTIALLY_WORKING | Yes | Yes | Real | 12 events | No | Yes | Scattered | EXECUTED read | Some writes swallowed; cache invalidation incomplete | Centralize event guarantees |
| Templates | PLACEHOLDER | Yes | None | Seed array | None | No | No | None | INSPECTED | Static `TEMPLATE_SEED`; create drawer coming soon | Hide or mark samples |
| Legal playbook | PARTIALLY_WORKING | Read-only | Yes | Real | 1 playbook/8 rules | Used by monitor | Yes | Rule tests | EXECUTED DB | Hardcoded playbook UUID; no selector/version UI | Add list selector |
| Notifications | PLACEHOLDER | Yes | None | `MOCK` | None | No | No | None | INSPECTED | Static names/events | Connect activity or hide |
| Command palette/search | UI_ONLY | Yes | None | Static nav filter | None | No | No | None | INSPECTED | Not contract search; missing routes | Rename to navigation |
| Settings | PLACEHOLDER | Yes | None | None | None | No | No | None | INSPECTED | Disabled inputs only | Hide or roadmap |
| Help | PLACEHOLDER | Yes | None | None | None | No | No | None | EXECUTED 200 | Self-link action | Hide/fix |
| Delete contract | PARTIALLY_WORKING | Yes | Yes | Cascade + storage | FK cascade | No | Yes | Smoke script path not reached in failed run | INSPECTED | No audit event; no browser proof | Add API/browser test |
| Bulk export | UI_ONLY | Yes | None | Client JSON | Current list only | No | Download only | None | INSPECTED | Called export but not a report | Relabel |
| Authentication/roles | PLACEHOLDER | UI role switch | Demo bearer | Single token/header | No users/tenants | No | Local storage | Boundary snippets | INSPECTED | Not real authorization | Never present as production auth |
| Bilingual/RTL | PARTIALLY_WORKING | Broad i18n | Bilingual fields vary | Mixed | Mixed | Summary/prompts | Yes | Unit only | INSPECTED | PDF viewer broken; risk/activity copy incomplete; no AR browser E2E | Add AR E2E |
| Legacy dashboard endpoint | DEAD | Unused | Static fake | None | None | No | No | Smoke sees placeholder header | EXECUTED | Superseded by `/dashboard/summary` | Remove/deprecate |
| Superseded UI/helpers | DEAD | Unreachable | Nine unused API exports | None | None | No | No | Static reference scan | EXECUTED | `Header`, `StatusBadge`, `IconButton`, unused clients | Remove after confirmation |

# 3. Dead Feature Report

## Confirmed dead

1. **Legacy dashboard API**
   - Path: `backend/app/routers/placeholders.py`
   - Symbol: `dashboard_placeholder`
   - Why: static values plus `X-Placeholder: true`; frontend uses `/api/dashboard/summary`.
   - Visible: not through current UI; visible to API consumers.
   - Demo impact: misleading smoke/API output.
   - Action: **remove/deprecate**.

2. **Superseded frontend components**
   - `frontend/components/Header.tsx`
   - `frontend/components/ui/StatusBadge.tsx`
   - `frontend/components/ui/IconButton.tsx`
   - Why: no production imports; shell uses `TopHeader`, contract status uses other components.
   - Visible: no.
   - Action: **remove** after one final import check.

3. **Unused API client exports**
   - Examples: `apiWithMeta`, `fetchContractRisk`, `reextractContractText`, `rebuildDeadlines`, `rebuildMilestones`, `getFlowdown`, `fetchApprovalSummary`, `fetchSignatureSummary`, `listPlaybooks`.
   - Why: optimized repository reference scan found no UI consumers.
   - Action: connect the necessary admin functions; otherwise **remove**.

4. **Stale docs/comments/i18n**
   - `README.md` and `docs/README_HANDOFF.md` still describe F2–F5 as placeholders.
   - `models.py` comments say the pipeline never writes derived tables, but it does.
   - `dashboard.wip`, `common.wip`, `common.placeholderData` are orphan translation keys.
   - Action: **update/remove**.

# 4. UI-Only Feature Report

1. **Reports metrics**
   - Page/component: `/reports`, `frontend/app/reports/page.tsx`
   - Visible action: stage bars, turnaround, bottlenecks.
   - Missing behavior: no report service, export, turnaround calculation, or persisted report.
   - Impact: labels overstate simple counts.
   - Action: **relabel or hide**.

2. **Command palette “search”**
   - Component: `CommandPalette.tsx`
   - Visible action: search box/⌘K.
   - Missing behavior: no contract/entity/API/Arabic search; filters static routes.
   - Impact: search promise is misleading.
   - Action: **rename to Navigate** until connected.

3. **Bulk export**
   - Page: `/contracts`
   - Visible action: bulk export.
   - Missing behavior: no report API; downloads current client-side JSON only.
   - Impact: incomplete data/export semantics.
   - Action: **relabel**.

4. **Documents tab**
   - Component: `ContractDocumentsTab` inside contract detail.
   - Visible action: version list.
   - Missing behavior: no download/open action, despite version download API existing elsewhere.
   - Action: **connect**.

5. **Header workflow shortcuts**
   - Component: `ContractHeader`
   - Buttons only switch to approval/signature tabs; they do not start/create.
   - Impact: acceptable navigation, but wording implies immediate operation.
   - Action: **clarify wording**.

# 5. Backend-Only Feature Report

1. `POST /api/contracts/{id}/reextract-text`
   - Needed for all legacy contracts (`page_layout` coverage was 0/39).
   - Reachable manually by authenticated API.
   - Action: **connect** as explicit admin/backfill operation.

2. `POST /api/versions/{id}/extract`
   - Re-runs extraction for a version.
   - Reachable manually.
   - Action: **connect** in Versions panel or document as internal.

3. Negotiation monitor:
   - Thread create/patch, manual email import, email-contract linking, attachment-version creation, package patch, rounds endpoint.
   - Reachable manually through `/api/negotiation-monitor/*`.
   - Action: connect only the intended golden-path actions; document the rest as internal.

4. Uploaded-signature method
   - Backend accepts it; signer UI only supports type/draw.
   - Action: **remove** unsupported surface or expose with privacy/file validation.

# 6. Placeholder and Simulated Feature Report

## Valid fixtures/tests

- Vitest `vi.mock`, Python `MagicMock`, synthetic PDFs, demo contract fixtures.
- Action: leave.

## Clearly labeled demo seed

- `negotiation_monitor/demo_seed.py`
- Simulated inbox fixture
- `DemoStoryPlayer`
- Action: leave for demo, add production-disable switch.

## Placeholder accidentally shown as real

- Notifications use fixed static organizations/events. A demo hint exists, but cards still look operational.
- Reports use real contract rows but misleading business labels.
- Signature provider is returned as `demo`, but internal UI does not prominently show it.
- Import/send email UI does not consistently say “simulated”.
- Action: **label/hide**.

## Fake product behavior

- `/api/dashboard` static KPI values.
- `TEMPLATE_SEED` cards and create drawer.
- Settings disabled forms.
- Help placeholder.
- Single bearer token and local demo role presented in a user menu.
- Action: remove API fake; mark remaining surfaces roadmap/demo.

# 7. Intended Workflow Map

`Landing → Upload/Create → AI Analysis → Internal Review → Client Review → Negotiation → Internal Approval → Signature → Active Contract → Obligations/Deadlines/Payments → Completion/Archive`

Intended transitions:

1. Upload persists original document and initial version.
2. Extraction persists clauses, structured fields, intelligence, summary, and citations.
3. Internal user validates findings.
4. Review request creates a secure public token and sends an invitation.
5. Client approves or requests changes.
6. Negotiation produces human-reviewed counterproposals/version changes.
7. Ordered internal approvals authorize signature.
8. Legally valid provider signs final version.
9. Active operations drive obligations, deadlines, payments, dashboard, and archive.

# 8. Actual Executable Workflow Map

Legend: ✅ Working, 🟡 Partial, ❌ Broken, ⚪ Not implemented, 🔵 Simulated, ❓ Unverified.

1. **Landing** — 🟡
   - Action/page: open `/`.
   - API: `/api/dashboard/summary`, contracts list, monitor threads.
   - Persisted change: none.
   - Blocker: client-review pipeline buckets are broken by response-shape mismatch.

2. **Upload PDF** — 🟡
   - Action/page: `/upload`.
   - API: `POST /contracts`, then `POST /extract`.
   - State: contract/version then extraction rows.
   - Blocker: no browser proof; live AI required.

3. **Upload DOCX** — ❌
   - API returns 422 from the paragraph-direction crash.

4. **AI analysis** — 🟡
   - Extraction core exists and data is present for old contracts.
   - Downstream deadline/payment/risk failures can be silently swallowed.

5. **PDF/source viewing** — ❌
   - File endpoint works, but production build and SSR fail; old contracts have no geometry.

6. **Summary** — ❓
   - API/status/UI exist; current DB has no rows and live generation was not executed.

7. **Send client review** — 🟡
   - Creates persisted token/link; no actual email delivery.

8. **Client portal** — 🟡
   - Public routes/services exist; no current persisted request or browser E2E.
   - Decision does not move contract lifecycle stage.

9. **Negotiation recommendation** — 🟡
   - UI/API/service exist; requires live AI and no persisted evidence exists.

10. **Email monitor** — 🔵
    - Simulated import/outbound and demo seed only; Gmail/Outlook absent.

11. **Internal approval** — 🟡
    - Ordered service and UI exist; role is demo header; no persisted execution proof.

12. **Signature** — 🔵
    - Local visual signing/PDF/certificate; not licensed cryptographic e-sign.

13. **Activation** — 🟡
    - Signature service intends to move `signed → active`; no persisted proof.

14. **Post-signature operations** — 🟡
    - Existing deadlines/payments/obligations are readable and mutable in parts.
    - Automatic overdue and dashboard/demo-clock continuity are incomplete.

15. **Completion/archive** — ⚪
    - Not a canonical backend lifecycle stage; only frontend derivation by end date.

# 9. Lifecycle State Machine Audit

## Current status domains

- Contract processing: `processing`, `ready`, `needs_review`, `failed`, `unsupported`.
- Contract workflow stage: `negotiation`, `internal_review`, `approved`, `awaiting_signature`, `partially_signed`, `signed`, `active`.
- Review: `sent`, `opened`, `approved`, `rejected`, `changes_requested`, `expired`.
- Negotiation workflow: `pending_analysis`, `ready`, `edited_by_legal`, `sent_to_client`, `client_responded`, `accepted`, `closed`.
- Approval: `in_progress`, `approved`, `rejected`, `changes_requested`, `cancelled`; steps `locked`, `pending`, decision statuses.
- Signature request: `draft`, `created`, `sent`, `viewed`, `partially_signed`, `completed`, `declined`, `expired`, `cancelled`, `error`.
- Summary: `not_generated`, `generating`, `ready`, `failed`.
- Version: `draft`, `processing`, `ready`, `needs_review`, `under_review`, `approved`, `signed` in different paths.

## Mismatches and impossible states

1. `contracts.stage` has no DB CHECK; only service calls validate.
2. Review decisions do not update stage.
3. Negotiation monitor and clause negotiation do not update stage.
4. Signature creation moves contract to `awaiting_signature` while request is still draft.
5. Frontend stepper contains `draft`, `client_review`, `awaiting_client`, `completed`, absent from backend lifecycle.
6. Dashboard counts `rejected`/`declined` contract stages that lifecycle code cannot set.
7. List API emits `workflow_summary.review_status`; landing expects `workflow_summary.review`.
8. Version status is displayed through a stage badge even though version and contract semantics differ.
9. Contracts can remain `processing`; at least four exceeded one hour during inspection.
10. All current contracts remained at `negotiation`, demonstrating no persisted lifecycle progression.

## Canonical model recommendation (report only)

Keep three orthogonal layers:

1. Ingestion: `processing → ready | needs_review | unsupported | failed`.
2. Deal lifecycle: `negotiation → client_review → internal_review → ready_to_sign → partially_signed → active → completed`, with `rejected/cancelled` terminal branches.
3. Sub-workflows: review, negotiation, approval, signature, monitoring, and version states linked through events.

Do not migrate until transition rules and frontend mapping are agreed.

# 10. Complete Manual Test Scenarios

Each scenario must capture browser screenshot, Network request/response, relevant DB rows by synthetic contract ID, and activity events. Use synthetic/redacted documents only.

## Scenario 1 — New contract upload and AI analysis

- Persona/preconditions: Business owner; valid bilingual synthetic PDF; OpenAI configured.
- Start: `/upload`.
- Actions: upload; wait; open detail; inspect summary/risk/obligations/notices/payments; click citations.
- Expected visible: explicit progress, ready/needs-review state, bilingual sections, original PDF page.
- Expected API/DB: contract + initial version + raw/layout + clauses/extractions/intelligence + summary; one extraction activity.
- Next stage: negotiation.
- Pass: refresh preserves all data and citations open correct page.
- Current expected result: **FAIL** because production PDF viewer build is broken; summary is unverified.
- Cleanup: delete synthetic contract; verify storage and child rows gone.

## Scenario 2 — Broken/unsupported file

- Persona: Business owner.
- Actions: corrupt PDF, `.txt`, oversized file, valid unsupported contract.
- Visible: bilingual specific errors; unsupported record clearly classified.
- DB: invalid preflight files create no row; unsupported classified record may remain intentionally.
- Activity: none for invalid upload; classification event for retained record.
- Pass: no orphan file/half-created processing row.
- Evidence: upload form, network 4xx, DB count before/after.
- Cleanup: delete retained unsupported synthetic record.

## Scenario 3 — Send contract to client

- Preconditions: ready synthetic contract/version.
- Actions: contract Review tab/header; enter synthetic recipient; send; copy link; open portal.
- Visible: sent state and secure link.
- DB/API: `review_requests.status=sent`, token hash/version ID, no token leakage in internal list.
- Activity: `review_sent`.
- Next stage expected: client review.
- Current caveat: no SMTP; contract stage remains negotiation.
- Pass: refresh preserves request and portal shows only allowed dossier.

## Scenario 4 — Client approves

- Actions: open review link; inspect document/summary; approve.
- Visible: terminal thanks/read-only state; internal history updated.
- DB: review `approved`, response timestamp.
- Activity: approval event with actor/time.
- Next expected: internal approval or approved review state.
- Current expected: **PARTIAL**; contract stage does not transition.

## Scenario 5 — Client requests changes

- Actions: add clause comment, reason, proposed wording; submit changes.
- Visible: internal review history and negotiation candidate.
- DB: comments/response; negotiation row only after explicit analyze path.
- Activity: changes-requested event.
- Next: negotiation.
- Pass: no automatic unsupported AI claim; user can deliberately analyze.

## Scenario 6 — AI negotiation recommendation

- Preconditions: changes-requested review; AI configured.
- Actions: analyze; inspect business/legal/financial impact, sources/playbook; edit; accept/reject/send.
- Visible: confidence, human-decision warning, citations.
- DB: negotiation and messages/workflow status.
- Activity: analyzed/edited/sent.
- Pass: refresh preserves edits; stale source is detected.
- Current: provider/browser unverified.

## Scenario 7 — Email revision monitor

- Preconditions: clearly labeled simulated thread and attachment.
- Actions: import same email twice; analyze; create/inspect revision; package; approve; send.
- Visible: “Simulated” labels; duplicate prevention; round timeline.
- DB: one inbound email/version, package, round, outbound event.
- Activity: monitor lineage events.
- Next: awaiting counterparty.
- Pass: duplicate import cannot create duplicate version.
- Cleanup: remove demo rows only in isolated test DB.

## Scenario 8 — Internal approval

- Preconditions: no unresolved negotiation or explicit override reason.
- Actions: start legal→finance→executive; switch demo roles; approve first; reject second; inspect return; restart.
- Visible: ordered locks, role denial, required comments.
- DB: workflow/steps and stage transitions.
- Activity: start, each decision, stage changes.
- Pass: cannot act out of order; refresh persists.
- Current: service tests mock the actual stage writer; needs integration proof.

## Scenario 9 — Digital signature

- Preconditions: contract stage approved; synthetic signers.
- Actions: create ordered request; send; first signer signs; second signs; download PDF/certificate.
- Visible: prominent demo/non-legal disclosure; partial/completed status.
- DB/files: signers/events/request, signed PDF, certificate, hashes.
- Activity: request, open, sign, complete, active.
- Next: active.
- Pass: second cannot sign early; invalid token rejected; artifacts match request.
- Caveat: never call this legally binding.

## Scenario 10 — Version lifecycle

- Actions: initial upload; client revision; counteroffer; approval; signature; compare; set current; download; lineage.
- DB: immutable version rows, one current version, comparisons/events.
- Activity: version-created/current/approved/signed.
- Pass: old bytes unchanged; lineage links are valid; refresh persists.
- Current: many current contracts lack versions; backfill needed.

## Scenario 11 — Post-signature operations

- Preconditions: active synthetic contract with dated obligations/notices/payments.
- Actions: move demo clock; complete obligation; log event; mark payment; refresh dashboard.
- DB: event/deadline/payment/obligation changes.
- Activity: each manual operation.
- Pass: dashboard and detail use identical demo date and totals.
- Current expected: **FAIL** on dashboard clock consistency and obligation auto-overdue.

## Scenario 12 — Arabic and English

- Actions: switch UI languages; upload Arabic/mixed PDF and DOCX; inspect viewer/summary/comments/review/approval/signature/email copy.
- Visible: correct RTL/LTR, no reversed glyphs, keyboard/focus retained.
- DB: logical-order extracted text and direction metadata.
- Pass: exact citations and no PII leakage.
- Current: PDF viewer broken; DOCX upload broken; no full Arabic E2E.

## Scenario 13 — Dashboard accuracy

- Preconditions: known synthetic rows with manually calculated totals.
- Actions: compare DB, `/dashboard/summary`, landing and dashboard; follow every filter link; mutate; refresh.
- Activity: mutation event.
- Pass: exact equality and correct filtered list.
- Current expected: **FAIL** for demo-clock and ignored `role/status/bucket` filters.

## Scenario 14 — Delete contract

- Actions: begin delete; cancel; retry/confirm; open direct URL; refresh dashboard.
- DB/files: contract, related rows and source file removed; child parent pointer nulled as designed.
- Activity: deletion cannot persist on deleted contract; external audit strategy must be defined.
- Pass: cancel has no effect; direct API is 404; no orphans.
- Cleanup: none.

## Scenario 15 — Failure recovery

- Actions: AI auth/rate failure, simulated email failure injection, DB interruption, expired review, invalid sign token, double-click mutations, refresh mid-generation.
- Visible: safe bilingual errors, retry/cancel, no raw provider secrets.
- DB: explicit failed states or atomic rollback; no permanent `generating/processing`.
- Activity: failure/retry events where meaningful.
- Pass: idempotency and recovery after restart.
- Current: summary jobs are in-process only; durable recovery is absent.

# 11. UX Evaluation Scores

Scores are 1–5 and reflect current executable behavior.

| Workflow | Discoverability | Clarity | Feedback | Recoverability | Consistency | Efficiency | Trust | Privacy | Accessibility | Continuity | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Upload/analysis | 5 | 3 | 3 | 2 | 3 | 4 | 3 | 3 | 3 | 2 | DOCX break, silent downstream failures |
| Reader/viewer | 4 | 3 | 2 | 2 | 3 | 3 | 4 | 4 | 3 | 1 | Build/SSR blocker |
| Summary | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 3 | 2 | Good state UI, no real execution proof |
| Client review | 4 | 3 | 3 | 3 | 3 | 4 | 3 | 4 | 3 | 2 | No delivery, no stage transition |
| Negotiation | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 2 | AI and lifecycle unverified |
| Monitor | 3 | 2 | 3 | 2 | 3 | 3 | 2 | 2 | 3 | 2 | Simulation labeling weak |
| Approvals | 4 | 4 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | Demo role, no E2E |
| Signature | 4 | 2 | 4 | 3 | 3 | 4 | 1 | 3 | 3 | 3 | Must disclose non-legal demo |
| Versions | 4 | 3 | 3 | 2 | 2 | 3 | 3 | 4 | 3 | 3 | Status/stage semantics mixed |
| Operations | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 4 | 3 | 2 | Dashboard clock divergence |
| Dashboard | 5 | 3 | 3 | 2 | 3 | 4 | 2 | 4 | 3 | 2 | Stale deep links/count semantics |
| Arabic/English | 4 | 3 | 2 | 2 | 3 | 3 | 3 | 4 | 3 | 2 | No complete Arabic proof |

# 12. Automated Test Coverage Gaps

## Existing coverage

- 32 backend test files, mostly unit/service.
- 2 frontend component tests with mocked API/PDF behavior.
- API-level evidence mainly dashboard/consent and the standalone smoke script.
- No browser E2E suite.

## False confidence

1. Approval tests patch `set_stage`; signature tests patch `transition_stage`.
2. Review, negotiation, monitor, and provider tests use `MagicMock`.
3. Summary tests mock AI and DB.
4. SourceViewer test mocks PDF.js/file loading.
5. No refresh persistence test.
6. No full upload→extract HTTP test.
7. No full public review/sign HTTP sequence.
8. No authorization matrix; one demo token/header is not production auth.
9. No production build test in CI capable of catching the PDF worker failure.
10. Lint is not configured noninteractively.

## Minimum proof suite

1. Real test DB: PDF and DOCX upload→extract→persist.
2. Production build and SSR route test for every page importing PDF.js.
3. Review send→public decision→internal refresh.
4. Negotiation analyze/edit/send with stub provider at HTTP boundary.
5. Approval sequence without mocking lifecycle service.
6. Two-signer public signature sequence and generated artifacts.
7. Version create/compare/current/download/lineage.
8. Demo-clock equality across detail/dashboard.
9. Duplicate email/version and duplicate-button idempotency.
10. Arabic browser test for mixed PDF and DOCX.
11. Delete cascade/storage/direct URL test.
12. Auth/role negative matrix for all protected routes.

# 13. Bugs and Integration Failures

## P0

- Production build fails on PDF.js worker minification.
- PDF.js server import crashes `/flowdown`.

## P1

- DOCX extraction crashes on `CT_PPr.bidi`.
- Home workflow shape mismatch prevents client-review buckets.
- Review/negotiation lifecycle transitions are missing.
- Existing contracts have no page layout; re-extract is backend-only.
- No durable queue/recovery for summary jobs.

## P2

- Dashboard uses `date.today()` instead of demo clock.
- Pipeline suppresses derived-engine/activity errors.
- Obligation risk rule checks an impossible status.
- URL links emit ignored `role`, `status`, `bucket` filters.
- Signature and email simulation are insufficiently disclosed.
- Current DB contains no evidence for lifecycle workflows.
- Reports labels do not represent their values.

## P3/P4

- Help self-link.
- Missing command-palette routes.
- Dead components/client helpers.
- Stale README/comments/i18n.
- `.env.example` omits provider/review/storage variables.

# 14. Prioritized Repair Plan

| Priority | Issue/workflow | Files | Complexity | Dependencies | Action/order |
|---|---|---|---|---|---|
| P0 | Build/SSR PDF.js | `SourceViewer.tsx`, Next config/package | M | PDF.js/Next compatibility | Fix before any demo |
| P0 | DOCX upload crash | `textextract.py` | S | python-docx XML API | Fix second |
| P1 | Workflow summary mismatch | `dashboard.py`, `types.ts`, `pipeline.ts` | S | Canonical shape decision | Fix third |
| P1 | Missing review transitions | `reviews.py`, `lifecycle.py`, UI | M | Lifecycle product decision | Fix fourth |
| P1 | Geometry backfill | reextract service, admin UI/script | M | Viewer fixed | Backfill legacy contracts |
| P1 | Golden-path integration tests | backend API + browser suite | L | Stable workflows | Add before feature work |
| P1 | Pipeline post-step status | `pipeline.py`, models/API/UI | M | Failure semantics | Stop silent success |
| P2 | Demo clock dashboard | `services/dashboard.py` | S | None | Use persisted demo date |
| P2 | Obligation overdue/risk | obligations/risk/intelligence | M | Canonical statuses | Fix deterministic rule |
| P2 | Simulated provider labels | signature/monitor UI | XS | None | Label or hide |
| P2 | Stale deep links | contracts list/pipeline/dashboard | S | Filter contract | Implement filters |
| P2 | Durable jobs | summary/provider jobs | L | Queue infra | Roadmap after demo |
| P2 | Reports/templates/settings/help | pages/nav | XS–L | Product scope | Hide or mark roadmap |
| P3 | Cache/activity refresh | cache + panels | M | Mutation inventory | Standardize invalidation |
| P4 | Dead code/docs | listed files | S | Final search | Remove/update last |

# 15. Golden Demo Workflow

The safest scenario today is narrower than the intended lifecycle:

1. Use an **existing ready PDF contract** with a current version; do not upload DOCX.
2. Open contract detail and verify existing overview/risk/obligation/deadline/payment API data.
3. Avoid `/flowdown` and any PDF viewer route until PDF.js is fixed.
4. Demonstrate deterministic deadline/payment engines and demo clock on the contract tab, noting dashboard divergence.
5. Demonstrate review-link creation as **copy-link only**, clearly saying no email is sent.
6. If demonstrating negotiation, use explicit simulated/test AI and label it provider-dependent.
7. Start approval with the demo role switcher.
8. Demonstrate local visual signing only after approval and prominently state it is a non-legal demo.
9. Show version lineage and activity if the selected contract has persisted rows.
10. Do not claim Gmail, Outlook, Signit, notification delivery, report generation, or legal e-sign.

This sequence is not currently proven end-to-end and cannot be called production-ready until the P0 blockers and a browser test pass.

# 16. Final Verdict

## Can a real user complete the entire contract lifecycle today?

**No.** The current working tree cannot produce a successful production frontend build, DOCX upload is broken, PDF.js crashes an SSR route, live email/e-sign providers do not exist, and lifecycle continuity is incomplete.

## Where does the workflow currently stop?

The first hard stop depends on input:

- DOCX: upload preflight.
- PDF in production build: frontend deployment.
- Review lifecycle: no actual email and no contract-stage transition after decision.
- Signature: only a visual simulated implementation, not production legal e-sign.

## Which features only look implemented?

- Notifications, templates, settings, help.
- Reports beyond simple client counts.
- Command palette as “search”.
- Live Gmail/Outlook/Signit.
- Legal digital signature.
- Legacy dashboard endpoint.
- Some home pipeline stages and role/status deep links.

## Which features should be hidden until fixed?

- `/flowdown` while SSR is broken.
- Settings and Help if “coming soon” pages are unacceptable in demo.
- Template creation/use claims.
- Notifications as operational events.
- Provider choices for Gmail/Outlook/Signit.
- Any “legally binding” signature language.

## What must be repaired first?

1. PDF.js build/SSR integration.
2. DOCX extraction.
3. Workflow-summary and lifecycle transitions.
4. Existing-contract geometry backfill.
5. A real test-DB + browser golden-path suite.

## Best complete scenario we can test today

After fixing the two P0 runtime defects, the best candidate is:

`Existing ready PDF → inspect persisted intelligence → create copy-only client review → public decision → manually start ordered demo approval → local visual demo signature → active stage → inspect deadlines/payments/activity`.

It must remain labeled **demo/simulated**, and it needs an automated end-to-end test before it can be classified `FULLY_WORKING`.
