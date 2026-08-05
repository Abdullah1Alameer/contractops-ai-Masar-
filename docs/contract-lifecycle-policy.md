# ContractOps AI — Canonical Contract Lifecycle Policy

Policy status: **Proposed — requires product and engineering approval before Phase 2B implementation**  
Prepared: 2026-08-05  
Scope: contract business lifecycle, workflow integration, transition validation, UI mapping, migration/backfill, and proof strategy.

## 1. Policy principles

1. `contracts.stage` represents only the contract's business lifecycle.
2. AI ingestion, review, negotiation, approval, signature, and version statuses remain separate state domains.
3. Every business-stage mutation must pass through one transition service.
4. A workflow status may refine a stage but must not silently replace the persisted business stage.
5. Every successful stage transition is atomic with its workflow update and activity event.
6. Terminal contracts cannot be reopened by directly changing `contracts.stage`; a separate formal new contract or amendment entity is required.
7. Unknown stages and invalid transitions fail closed with a structured conflict response.
8. The simulated/local signature provider must always be described as a demo workflow, not as legally binding electronic signature.

## 2. Separate state domains

### A. Ingestion status — `contracts.status`

Canonical values:

- `processing`: file upload, extraction, classification, or intelligence generation is running.
- `ready`: ingestion completed and the contract is usable.
- `needs_review`: ingestion completed but classification or extracted facts require human review.
- `failed`: ingestion failed.
- `unsupported`: the document is valid but outside supported contract categories.

`ai_review` is **not** a business stage. Landing may retain an `ai_review` display bucket derived from `contracts.status=needs_review`.

### B. Business lifecycle — `contracts.stage`

Recommended canonical values:

1. `draft`
2. `ready_for_client`
3. `client_review`
4. `negotiation`
5. `internal_review`
6. `ready_to_sign`
7. `partially_signed`
8. `signed`
9. `active`
10. `completed`
11. `rejected`
12. `cancelled`
13. `terminated`

Changes from the proposed list:

- Remove `ai_review`; it belongs to ingestion status.
- Keep `ready_for_client`; it represents completed internal preparation before external review.
- Rename current `approved` to `ready_to_sign`; the business meaning is clearer.
- Rename current `awaiting_signature` to `ready_to_sign`; request-level `draft`, `sent`, and `viewed` remain signature statuses.
- Add `terminated`; early termination must not be conflated with natural completion or cancellation before execution.

### C. Review workflow — `review_requests.status`

- `sent`
- `opened`
- `approved`
- `rejected`
- `changes_requested`
- `expired`
- `cancelled` (new canonical value)

### D. Negotiation workflow — `negotiations.workflow_status`

- `pending_analysis`
- `ready`
- `edited_by_legal`
- `sent_to_client`
- `client_responded`
- `accepted`
- `closed`

`closed` requires a closure outcome recorded in activity metadata or a future explicit `outcome` field:

- `agreement_reached`
- `counterparty_rejected`
- `internally_abandoned`
- `superseded`

The editing status in `negotiations.status` remains separate: `draft`, `approved`, `edited`, `sent`, `closed`.

### E. Approval workflow — `approval_workflows.status`

- `in_progress`
- `approved`
- `rejected`
- `changes_requested`
- `cancelled`

Approval-step statuses remain `locked`, `pending`, `approved`, `rejected`, `changes_requested`, and optional `skipped` only when an authorized policy explicitly permits skipping.

### F. Signature workflow — `signature_requests.status`

- `draft`
- `created`
- `sent`
- `viewed`
- `partially_signed`
- `completed`
- `declined`
- `expired`
- `cancelled`
- `error`

Signer statuses remain `waiting`, `invited`, `opened`, `signed`, `declined`, and `expired`.

### G. Version status — `contract_versions.status`

Recommended values:

- `processing`
- `ready`
- `needs_review`
- `approved`
- `signed`
- `superseded`
- `failed`

Version status describes a document revision. It never substitutes for `contracts.stage`. Every workflow must reference the current version, and a stale workflow cannot advance the contract.

## 3. Canonical business stages

| Stage | Business meaning | Entry condition | Allowed actions | Forbidden actions | Next stages | Return/rollback | Terminal | EN / AR label | Landing bucket | Dashboard impact | Entry activity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `draft` | Contract exists but internal preparation or ingestion is incomplete. | Upload/create, or a pre-execution current version is replaced. | Upload/replace file, run/retry AI, edit metadata, cancel. | Client review, approval, signature, activation. | `ready_for_client`, `cancelled` | None | No | Draft / مسودة | `draft` or derived `ai_review` | Draft/preparation count; excluded from active workflow KPIs. | `contract_created` or `contract_returned_to_draft` |
| `ready_for_client` | Ingestion and internal preparation are complete; no external review is active. | `status` is `ready` or accepted `needs_review`, supported document, current version established, required internal preparation complete. | Send client review, create revised version, approved review waiver, cancel. | Negotiation without client feedback, approval without client approval/waiver, signature. | `client_review`, `internal_review` by explicit waiver, `draft`, `cancelled` | `draft` when a new pre-execution version starts processing. | No | Ready for client / جاهز للإرسال للعميل | `draft` (the existing pre-client preparation bucket) | Ready-to-send KPI. | `contract_ready_for_client` |
| `client_review` | The current version is with the client for initial review. | A review request for the current version is created successfully. | Open portal, comment, approve, reject, request changes, resend, cancel review, expire review. | Internal approval, signature, unrelated version switch without cancelling review. | `internal_review`, `negotiation`, `rejected`, `ready_for_client`, `cancelled` | `ready_for_client` on review cancellation/expiry. | No | Client review / مراجعة العميل | `sent_to_client` or `client_reviewing` from review status. | Pending/open review KPIs. | `contract_entered_client_review` |
| `negotiation` | Terms are unresolved and one or more negotiation items/rounds are active. | Client requests changes, internal approval requests changes, or an authorized amendment negotiation begins. | Analyze, edit, send counterproposal, receive response, create next round, accept, close, abandon. | Approval while unresolved items exist, signature, activation. | `internal_review`, `rejected`, `cancelled` | Remains `negotiation` across rounds. | No | Negotiation / تفاوض | `negotiating` | Active-negotiation KPI and legal attention queue. | `contract_entered_negotiation` |
| `internal_review` | Commercial terms are settled or explicitly waived and the contract is queued for or undergoing ordered internal approval. | Client approved, all negotiations accepted/closed as agreed, or authorized review waiver; current version is not stale. | Start approval, approve ordered steps, request changes, reject, cancel approval workflow, return to negotiation. | Signature before final approval, client review on the same version, out-of-order approval. | `ready_to_sign`, `negotiation`, `rejected`, `cancelled` | Approval workflow cancellation returns to `internal_review`; changes return to `negotiation`. | No | Internal approval / موافقة داخلية | `internal_review` | Pending role-specific approval KPIs. | `contract_entered_internal_review` |
| `ready_to_sign` | The current version has completed internal approval and is eligible for signature. | Final approval step succeeds, current version marked approved, no unresolved/stale workflow. | Create/send/cancel/replace signature request, edit signer metadata before signing, cancel contract. | Client review, negotiation, activation, changing signed content in place. | `partially_signed`, `signed`, `internal_review`, `cancelled` | Signature expiry/cancellation/error returns or remains here; decline goes to `internal_review` for legal triage. | No | Ready to sign / جاهز للتوقيع | `awaiting_signature` | Ready-to-sign and active-signature KPIs. | `contract_ready_to_sign` |
| `partially_signed` | At least one required signer signed the approved version, but not all have signed. | First valid signature is persisted and request status becomes `partially_signed`. | Remaining signers open/sign, resend active signer, decline, cancel/expire under authorized policy. | Modify document or signer order, start another request, negotiate directly. | `signed`, `ready_to_sign`, `internal_review` | Expiry/cancellation/error invalidates the incomplete request and returns to `ready_to_sign`; decline goes to `internal_review`. | No | Partially signed / موقّع جزئيًا | `awaiting_signature` | Partially-signed KPI and escalation queue. | `contract_partially_signed` |
| `signed` | All required signers completed the approved version, but business activation has not occurred. | Signature request is `completed`, signed artifact and certificate are generated, hashes verified. | Activate now when eligible, schedule activation, download artifacts, cancel before effective date only through privileged legal void process. | Edit signed version, ordinary rollback to negotiation/review, create another signature request. | `active`, exceptionally `cancelled` through legal void policy. | No ordinary rollback. | No | Signed / موقّع | `signed` | Signed-awaiting-activation KPI. | `contract_signed` |
| `active` | The executed agreement is in force and operational obligations are tracked. | Signed contract reaches its effective/start condition or an authorized user activates it. | Track obligations, payments, notices, renewals; initiate formal amendment; complete or terminate. | Direct client review/negotiation of the executed version, changing signed document, cancellation as if unsigned. | `completed`, `terminated` | No direct rollback; amendment is a separate version-scoped/formal process. | No | Active / ساري | `active` | Active portfolio value, obligations, deadlines, renewals. | `contract_activated` |
| `completed` | Contract naturally expired or all performance/closeout requirements were completed. | End/close condition met and unresolved obligations/renewal decisions are cleared. | Read, report, archive, export. | Review, negotiation, approval, signature, activation. | None; a new amendment/renewal contract is required. | None | Yes | Completed / مكتمل | `completed` | Completed KPI; excluded from live operational queues. | `contract_completed` |
| `rejected` | A client or authorized internal approver definitively rejected the transaction. | Initial client rejection, negotiation rejection without continuation, or internal approval veto. | Read, report, archive, clone into a new contract draft with explicit authorization. | Signature, activation, direct negotiation restart, changing stage in place. | None in the same lifecycle. | New contract/amendment entity only, never direct stage mutation. | Yes | Rejected / مرفوض | Excluded from active pipeline; shown in closed-outcome reporting. | Rejected KPI and reason reporting. | `contract_rejected` |
| `cancelled` | The organization intentionally stopped the pre-execution transaction. | Authorized cancellation before activation, negotiation abandonment, or legal void before effective date. | Read, report, archive, clone into a new contract draft. | Review, negotiation, approval, signature, activation. | None in the same lifecycle. | New contract/amendment entity only. | Yes | Cancelled / ملغى | Excluded from active pipeline; shown in closed-outcome reporting. | Cancellation KPI and reason reporting. | `contract_cancelled` |
| `terminated` | An active contract ended early under a termination right or settlement. | Authorized termination record with reason, effective date, actor, and evidence. | Closeout obligations, final payment, report, archive. | Review/signature of executed version, reactivation, ordinary completion transition. | None; amendment/reinstatement requires a new formal instrument. | None | Yes | Terminated / تم إنهاؤه | Excluded from active pipeline; shown in closed-outcome reporting. | Termination KPI, closeout deadlines, liabilities. | `contract_terminated` |

## 4. Review decision policy

| Action | Review status | Contract stage | Negotiation creation | Approval eligibility | Activity | Notifications | Reversible |
|---|---|---|---|---|---|---|---|
| Review request created | `sent` | `ready_for_client` → `client_review` | No | No | `review_sent`, `contract_entered_client_review` | Client invitation; internal confirmation. | Request may be cancelled before a decision. |
| Client opens review | `opened` | Remains `client_review` | No | No | `review_opened` | Optional internal viewed notification. | No need to reverse; status is historical. |
| Client approves | `approved` | `client_review` → `internal_review` | No | Yes, after current-version and unresolved-workflow validation. | `review_approved`, `contract_entered_internal_review` | Legal/approval owners notified. | Decision is immutable; supersede with a new review/version. |
| Client rejects | `rejected` | `client_review` → `rejected` | No automatic negotiation | No | `review_rejected`, `contract_rejected` | Internal owner and sender notified. | Terminal in this lifecycle; a new contract/amendment entity is required. |
| Client requests changes | `changes_requested` | `client_review` → `negotiation` | Create `pending_analysis` negotiation items for actionable comments, or one contract-level item when no clause comment exists. | No while unresolved items exist. | `review_changes_requested`, `contract_entered_negotiation`, `negotiation_analysis_requested` | Legal team notified. | Cannot erase the decision; later rounds supersede it. |
| Review expires | `expired` | `client_review` → `ready_for_client` | No | No | `review_expired`, `contract_ready_for_client` | Internal owner notified; optional client expiry notice. | New review request may be issued. |
| Review cancelled | `cancelled` | `client_review` → `ready_for_client` | No | No | `review_cancelled`, `contract_ready_for_client` | Client notified if link was sent/opened; internal owner notified. | New review request may be issued. |

Review invariants:

- Only one actionable initial review for the current version may be active.
- A stale review may be viewed read-only but cannot mutate stage.
- Review decisions are append-only; status must not be reset.
- A client review is required by default. An explicit `client_review_waived` action may move `ready_for_client` to `internal_review` only for an authorized role with a mandatory reason and activity event.

## 5. Negotiation policy

| Event | Negotiation state | Contract stage | Required side effects |
|---|---|---|---|
| Analysis started | `pending_analysis` | Enter/remain `negotiation` | Link current version and source review/comment; emit `negotiation_analysis_started`. |
| AI recommendation generated | `ready` | Remain `negotiation` | Persist recommendation and evidence; emit `negotiation_analyzed`. AI output is advisory. |
| Legal edits recommendation | `edited_by_legal` | Remain `negotiation` | Preserve AI/original text and legal-edited text; emit `negotiation_edited`. |
| Counterproposal sent | `sent_to_client`; editing status `sent` | Remain `negotiation` | Create follow-up review request for current version/round; emit `counterproposal_sent`; notify counterparty. |
| Counterparty accepts | `accepted` | Move to `internal_review` only when every active item is `accepted` or `closed` with `agreement_reached` | Freeze accepted wording into a new/current version when needed; emit `negotiation_accepted`, `contract_entered_internal_review`; notify approval owners. |
| Counterparty rejects | `closed`, outcome `counterparty_rejected` | `rejected` | Close all open round items; emit `negotiation_rejected`, `contract_rejected`; notify internal owner. |
| Counterparty requests another round | `client_responded`, followed by next item/round `pending_analysis` | Remain `negotiation` | Increment round, preserve lineage, emit `negotiation_round_started`; notify legal. |
| Negotiation closed with agreement | `closed`, outcome `agreement_reached` | `internal_review` when no unresolved items remain | Emit `negotiation_closed` and stage event. |
| Negotiation closed without agreement by internal owner | `closed`, outcome `internally_abandoned` | `cancelled` | Mandatory reason; emit `negotiation_abandoned`, `contract_cancelled`. |
| Negotiation superseded by a new version | `closed`, outcome `superseded` | Remain `negotiation` or `draft` according to the formal version action | Mark old workflow stale; never let it advance stage. |

Approval is blocked if any current-version negotiation has a status outside `accepted` or `closed` with `agreement_reached`.

## 6. Internal approval policy

### Start conditions

Internal approval may start only when:

1. `contracts.stage=internal_review`.
2. `contracts.status` is `ready` or an authorized human accepted `needs_review`.
3. The contract is supported.
4. A current version exists and is not stale.
5. Client review is `approved`, an explicit review waiver exists, or all negotiations ended with agreement.
6. No unresolved negotiation exists.
7. No approval workflow is already `in_progress`.
8. No active signature request exists.

### Ordered steps

Default order remains:

1. Business owner
2. Legal
3. Finance
4. Executive

Only the current pending role can act. Skipping requires a configured policy, an authorized actor, and `approval_step_overridden` with reason.

### Outcomes

| Action | Approval state | Contract stage | Policy |
|---|---|---|---|
| Start | `in_progress` | Remains `internal_review` | Emit `approval_workflow_started`. |
| Intermediate approve | `in_progress` | Remains `internal_review` | Unlock exactly the next step. |
| Final approve | `approved` | `ready_to_sign` | Mark current version approved; emit `approval_workflow_completed`, `contract_ready_to_sign`. |
| Reject | `rejected` | `rejected` | A veto is terminal for this lifecycle; emit `approval_rejected`, `contract_rejected`. |
| Request changes | `changes_requested` | `negotiation` | Approval becomes terminal/stale; create or reopen negotiation round; emit `approval_changes_requested`, `contract_entered_negotiation`. |
| Cancel approval workflow | `cancelled` | Remains `internal_review` | Cancellation stops the workflow, not the contract; emit `approval_workflow_cancelled`. |
| Explicit return to negotiation | `cancelled` or `changes_requested` according to reason | `negotiation` | Mandatory reason; emit `contract_returned_to_negotiation`. |

The current `force=True` behavior must not silently bypass unresolved negotiations. A privileged override must:

- require legal or executive authorization,
- require a reason,
- identify every overridden negotiation,
- close each with an explicit outcome,
- emit `approval_override_used`,
- never skip approval roles unless a separate step-override policy permits it.

## 7. Signature policy

### Creation eligibility

A signature request may be created only when:

- `contracts.stage=ready_to_sign`,
- current version status is `approved`,
- no unresolved/stale workflow exists,
- no active signature request exists,
- signer identities/order and expiry are valid,
- provider mode is explicit.

Creating a draft request does **not** change the stage; it remains `ready_to_sign`.

### Outcomes

| Signature event | Request status | Contract stage | Policy |
|---|---|---|---|
| Request created | `draft` or `created` | `ready_to_sign` | Emit `signature_request_created`; no legal-binding claim for simulated provider. |
| Request sent | `sent` | `ready_to_sign` | Invite eligible signer(s); emit `signature_request_sent`. |
| Request/signer viewed | `viewed` | `ready_to_sign` | Emit `signature_link_opened`. |
| First/subsequent but incomplete signer signs | `partially_signed` | `partially_signed` | Persist signer evidence; emit `signer_signed`, `contract_partially_signed`. |
| All required signers sign | `completed` | `signed` | Generate/verify signed artifact and certificate; emit `signature_request_completed`, `contract_signed`. |
| Signer declines | `declined` | `internal_review` | Legal triage decides whether to correct signer/package (`ready_to_sign`), renegotiate (`negotiation`), reject, or cancel. |
| Request expires | `expired` | `ready_to_sign` | Incomplete signatures cannot be reused; emit `signature_request_expired`. |
| Request cancelled | `cancelled` | `ready_to_sign` | Emit `signature_request_cancelled`; preserve audit history. |
| Provider/document error | `error` | `ready_to_sign` | Emit `signature_request_failed`; expose retry/replacement action. |

`signed` must be a durable stage. It must no longer be immediately overwritten by `active` in the same transaction.

## 8. Post-signature policy

### Activation

Recommended policy: **hybrid activation**.

- If the signed contract has a verified effective/start date at or before the current business date and no unresolved activation condition, activation may occur automatically after signature completion.
- If the verified date is in the future, remain `signed` and activate on that date through a durable scheduled job.
- If commencement is event-based, missing, disputed, or marked `needs_review`, activation is manual and requires an authorized actor plus evidence/comment.
- Activation emits `contract_activated` and starts operational obligation/deadline monitoring.

### Completion

A contract becomes `completed` when:

- its natural end/close condition occurred,
- renewal/extension was resolved,
- no blocking closeout obligation remains, or an authorized closeout override is recorded.

Passing `end_date` alone should raise a completion candidate, not silently complete the contract.

### Archive

Archive is not a lifecycle stage. It is a document/visibility state such as `archived_at`, `archived_by`, and optional retention metadata. Completed, rejected, cancelled, and terminated contracts may all be archived.

### Termination

Early termination uses `stage=terminated`, not `completed`. A termination record must capture:

- reason/type,
- effective date,
- actor/authority,
- source notice or evidence,
- remaining closeout obligations and payments.

## 9. Transition matrix

All invalid transitions return HTTP `409` with:

```json
{
  "error": "invalid_stage_transition",
  "current_stage": "draft",
  "event": "signature_completed",
  "allowed_next_stages": ["ready_for_client", "cancelled"]
}
```

Authorization failures return `403`; missing entities return `404`; malformed decisions return `422`; stale-version conflicts return `409 workflow_stale`.

| Current stage | Event | Required conditions | Next stage | Side effects | Invalid/error response |
|---|---|---|---|---|---|
| `draft` | Ingestion started/completed/failed | Current version | No stage change | Update ingestion/version status and extraction events. | Stale version → `409 workflow_stale`. |
| `draft` | Mark ready for client | Ingestion usable; supported; preparation complete | `ready_for_client` | `contract_ready_for_client` | Not ready/unsupported → `409 contract_not_ready`. |
| `draft` | Cancel contract | Authorized owner; reason | `cancelled` | Cancel active jobs; `contract_cancelled` | Unauthorized → `403`. |
| `ready_for_client` | Send initial review | Current version; no active review | `client_review` | Create review, notify client, review/stage events. | Active review → `409 review_already_active`. |
| `ready_for_client` | Waive client review | Authorized policy/role; mandatory reason | `internal_review` | `client_review_waived`, stage event. | Missing authority/reason → `403`/`422`. |
| `ready_for_client` | Replace current version | No active downstream workflow | `draft` | New current version, ingestion `processing`. | Active workflow → `409 workflow_active`. |
| `client_review` | Client opens | Active current-version review | Same | `review_opened` | Closed/stale → read-only or `409`. |
| `client_review` | Client approves | Active current-version review | `internal_review` | Persist immutable response; notify owners. | Duplicate decision → `409 review_closed`. |
| `client_review` | Client requests changes | Active review | `negotiation` | Create pending negotiation items; notify legal. | Duplicate/stale → `409`. |
| `client_review` | Client rejects | Active review | `rejected` | Close review; notify owner. | Duplicate/stale → `409`. |
| `client_review` | Review expires/cancelled | No decision yet | `ready_for_client` | Close link; notify internal owner; notify client when an opened/sent request is actively cancelled. | Already decided → `409 review_closed`. |
| `negotiation` | Start/analyze/edit round | Current version; authorized legal actor for edits | Same | Persist round/item/activity. | Stale/current round closed → `409`. |
| `negotiation` | Send counterproposal | Legal-approved wording; active item | Same | New follow-up review, email, round event. | Missing wording/already sent → `409`. |
| `negotiation` | Counterparty requests another round | Active sent round | Same | Close response phase, create next round. | No active round → `409`. |
| `negotiation` | All items accepted/agreed | Every current item resolved | `internal_review` | Freeze accepted current version; notify approvers. | Any unresolved item → `409 unresolved_negotiations`. |
| `negotiation` | Counterparty rejects | Authenticated current response | `rejected` | Close all items; rejection events. | Stale response → `409`. |
| `negotiation` | Internal abandonment | Authorized owner; reason | `cancelled` | Close items; cancellation event. | Missing reason/authority → `422`/`403`. |
| `internal_review` | Start approval | All approval start conditions | Same | Create ordered steps; activity. | Unresolved/stale/active workflow → `409`. |
| `internal_review` | Approve current step | Correct role and order | Same | Complete step; unlock next. | Wrong role/order → `403`/`409`. |
| `internal_review` | Final step approved | All prior steps approved | `ready_to_sign` | Mark version approved; completion events. | Missing prior step → `409 out_of_order`. |
| `internal_review` | Request changes | Comment required | `negotiation` | Close approval; create negotiation round. | Missing comment → `422`. |
| `internal_review` | Reject | Authorized current approver; comment | `rejected` | Close approval and contract. | Wrong role/order → `403`/`409`. |
| `internal_review` | Cancel approval workflow | Authorized internal actor | Same | Workflow `cancelled`; no stage regression. | No active workflow → `409`. |
| `ready_to_sign` | Create/send/view signature | Approved current version; valid signer setup | Same | Signature request/events/notifications. | Not approved/active request → `409`. |
| `ready_to_sign` | First/all signer signs | Valid consent/token/evidence | `partially_signed` or `signed` | Persist signatures; generate artifacts on completion. | Invalid order/token → `403`/`409`. |
| `ready_to_sign` | Expire/cancel/error request | Active request | Same | Close request; preserve audit. | Terminal request → `409 request_closed`. |
| `ready_to_sign` | Signer declines | Active eligible signer | `internal_review` | Decline event; legal triage task. | Ineligible signer → `409`. |
| `partially_signed` | Additional signer signs | Correct order/token | Same or `signed` | Persist evidence; invite next signer. | Out of order → `409`. |
| `partially_signed` | Expire/cancel/error | Authorized or timeout | `ready_to_sign` | Invalidate incomplete request; preserve evidence. | Terminal request → `409`. |
| `partially_signed` | Signer declines | Eligible signer; reason | `internal_review` | Close request; triage task. | Missing reason → `422`. |
| `signed` | Effective condition met | Verified date/condition or authorized manual activation | `active` | Start operational monitoring; activation event. | Condition unmet → `409 activation_not_ready`. |
| `signed` | Legal void before effective date | Privileged legal action; evidence/reason | `cancelled` | Void event; preserve signed artifacts. | Already active → `409`. |
| `active` | Complete | End/close conditions and closeout policy | `completed` | Completion event; final reporting. | Blocking obligations → `409 closeout_incomplete`. |
| `active` | Terminate | Authorized termination record | `terminated` | Termination/closeout events and tasks. | Missing authority/evidence → `403`/`422`. |
| `active` | Begin amendment | Formal amendment/version process | Remains `active` | Create amendment workflow without mutating executed-version stage. | Direct review mutation → `409 amendment_required`. |
| `completed` | Any workflow event | None permitted | Same | Audit denied attempt if required. | `409 terminal_contract`. |
| `rejected` | Any workflow event | None permitted | Same | Creating a separate new contract/amendment is a different command. | `409 terminal_contract`. |
| `cancelled` | Any workflow event | None permitted | Same | Creating a separate new contract/amendment is a different command. | `409 terminal_contract`. |
| `terminated` | Any workflow event | None permitted | Same | New reinstatement instrument is separate. | `409 terminal_contract`. |

Explicitly invalid:

- `draft → signed`
- `draft → active`
- `ready_for_client → ready_to_sign`
- `client_review → ready_to_sign`
- `negotiation → ready_to_sign` while any item is unresolved
- `internal_review → signed`
- `completed → negotiation`
- `rejected → ready_to_sign`
- `cancelled → active`
- `terminated → active`
- `active → client_review` without a formal amendment/version process

## 10. Current repository gap analysis

### Existing stage behavior

Current `backend/app/services/lifecycle.py` allows only:

- `negotiation`
- `internal_review`
- `approved`
- `awaiting_signature`
- `partially_signed`
- `signed`
- `active`

Current writes:

- Approval start → `internal_review`
- Approval final approval → `approved`
- Approval reject/changes/cancel → `negotiation`
- Signature request creation → `awaiting_signature`
- Signature cancellation → `approved`
- Partial signing → `partially_signed`
- Signature completion → `signed`, immediately followed by `active`
- Signature decline → `negotiation`

### Missing transitions

- Upload/AI does not establish `draft` or `ready_for_client`.
- Review create/open/approve/reject/changes/expire never updates stage.
- Negotiation analyze/send/accept/reject/close never updates stage.
- Signature expiry never updates stage.
- No `completed`, `cancelled`, `rejected`, or `terminated` writer exists.
- Version replacement resets ingestion status but leaves the old business stage unchanged.
- No durable signed-to-active scheduling exists.

### Conflicts and impossible states

- `contracts.stage` defaults to `negotiation` at upload, before any negotiation exists.
- Dashboard reads `rejected` and `declined` stages that the lifecycle service rejects.
- `signed` is not durable because signature completion immediately writes `active`.
- Approval service uses workflow status `approved`, while parts of version-lineage code check for `completed`.
- Version-lineage approval step timestamps reference `decided_at`, but the model stores `acted_at`.
- Approval `force=True` can bypass unresolved negotiations.
- Approval cancellation currently returns to negotiation even when no changes were requested.
- Signature decline currently jumps directly to negotiation instead of legal triage.
- A new current version can produce `contracts.status=processing` with `contracts.stage=active`.
- `set_stage()` commits internally, splitting workflow updates, stage updates, and activities across transactions.

### Frontend/backend naming conflicts

- Current backend `approved` means proposed `ready_to_sign`.
- Current backend `awaiting_signature` also maps to proposed `ready_to_sign`.
- Landing `ai_review` is a derived bucket, not a valid ingestion or business stage.
- Workflow stepper maps `negotiation` to both Draft and Negotiation; the first match highlights Draft.
- `stage.completed` and several signature labels are missing.
- Dashboard and aggregate links often filter raw stage while Landing uses workflow-aware buckets.
- Version status is sometimes rendered through a contract-stage badge.

### Central-service bypasses

- Review and negotiation services do not call lifecycle transitions.
- Database/manual SQL can write any `contracts.stage`; there is no CHECK constraint.
- Current lifecycle service validates only target membership, not `(current stage, event, target)` transitions.
- Direct workflow status patching can create combinations inconsistent with `contracts.stage`.

### Database and backward compatibility

Current database facts:

- `contracts.stage` is free text with default `negotiation`.
- `contracts.status` has a CHECK constraint for ingestion values.
- Workflow tables use mostly unconstrained text statuses.
- Partial unique indexes enforce one active approval and one active signature request.
- Activity events are append-only free-text events.

Required after policy approval:

1. Backfill existing stages before adding a CHECK constraint.
2. Add a CHECK matching the approved canonical stage set.
3. Consider lifecycle timestamps/reason fields for completion, rejection, cancellation, and termination.
4. Add `cancelled` review status to shared constants/types.
5. Preserve read compatibility for current `approved` and `awaiting_signature` rows during migration.

Recommended deterministic backfill precedence:

1. Explicit terminal activity/closure record → corresponding terminal stage.
2. Completed signature + effective condition met → `active`; otherwise `signed`.
3. Partial signature → `partially_signed`.
4. Active signature request or approved workflow → `ready_to_sign`.
5. In-progress approval → `internal_review`.
6. Active negotiation → `negotiation`.
7. Sent/opened initial review → `client_review`.
8. Ingestion `ready`/accepted `needs_review` → `ready_for_client`.
9. Ingestion `processing`/`failed`/`unsupported` → `draft`.

Do not infer `completed`, `rejected`, `cancelled`, or `terminated` without explicit evidence.

### Test gaps

- Approval and signature tests mock lifecycle calls rather than proving persisted stage changes.
- Review tests assert request status but not contract stage or activity.
- Negotiation-round tests do not prove contract transitions.
- No test covers a complete persisted journey.
- No browser Playwright/Cypress suite proves stepper, pipeline, deep links, and refresh persistence.

## 11. Critical product decisions requiring approval

1. **Stage set:** approve removal of `ai_review`, replacement of `approved`/`awaiting_signature` with `ready_to_sign`, and addition of `terminated`.
2. **Initial client rejection:** approve terminal `rejected`; do not automatically create negotiation.
3. **Internal approval rejection:** approve terminal `rejected`; only `changes_requested` returns to negotiation.
4. **Signature decline:** approve return to `internal_review` for legal triage rather than automatic negotiation.
5. **Activation:** approve hybrid automatic/manual activation based on verified effective conditions.
6. **Review waiver:** decide which contract categories and roles may skip client review.
7. **Override:** approve removal of unrestricted `force=True` in favor of audited legal/executive override.
8. **Completion:** approve that end date creates a completion candidate, not automatic completion while closeout remains.
9. **Amendments:** approve a separate version-scoped amendment lifecycle; Phase 2B should block direct `active → client_review`.
10. **Terminal reopening:** approve creation of a separate new contract/amendment entity instead of direct terminal-stage rollback.

## 12. Smallest safe Phase 2B implementation plan

| Order | Work item | Size | Primary files | Deliverable |
|---|---|---:|---|---|
| 1 | Canonical enums/constants | S | `backend/app/services/lifecycle.py`, `frontend/lib/types.ts` | Matching backend/frontend stage and event vocabularies; ingestion and workflow enums remain separate. |
| 2 | Transition validation service | M | `backend/app/services/lifecycle.py`, new `backend/tests/test_lifecycle.py` | Event-based transition matrix, conditions, structured `409` errors, one atomic stage/activity write without internal commits. |
| 3 | Review integration | M | `backend/app/services/reviews.py`, review routers/tests | Create/open/approve/reject/changes/expire/cancel transitions and activities for current version. |
| 4 | Negotiation integration | L | `backend/app/services/negotiation.py`, negotiation monitor bridge, tests | Round/outcome policy, unresolved guards, accepted/rejected/abandoned stage transitions. |
| 5 | Approval integration | M | `backend/app/services/approvals.py`, tests | Strict start gate, ordered outcomes, terminal reject, changes return, audited override, `ready_to_sign`. |
| 6 | Signature integration | M | `backend/app/services/signature.py`, tests | Creation eligibility, durable `signed`, decline triage, expiry/cancel/error rollback, activation trigger. |
| 7 | Frontend labels and stepper | M | `frontend/lib/i18n.tsx`, `WorkflowStepper.tsx`, stage badges/header/action gating | EN/AR labels, one step resolver, lifecycle-aware action visibility. |
| 8 | Dashboard and Landing effects | M | `backend/app/services/dashboard.py`, `frontend/lib/pipeline.ts`, dashboard/landing links | KPIs and filters based on canonical stage plus workflow refinements; no impossible-stage counts. |
| 9 | Database constraint/validation | M | New migration after approval, `backend/app/models.py` | Backfill, canonical stage CHECK, plus `stage_changed_at`, `closed_at`, `closure_reason`, and `closure_metadata`; reversible migration procedure. |
| 10 | Migration/backfill execution | M | Migration script and validation queries | Dry-run classification report, explicit ambiguous-row quarantine, post-migration integrity checks. |
| 11 | Integration tests | L | New backend integration test module; existing workflow tests | Real DB journey without mocking lifecycle: draft → review → negotiation/approval → signature → signed/active plus failure branches. |
| 12 | Browser golden-path test | L | New Playwright configuration/spec | Upload/seed, review portal, negotiation, four approvals, two signatures, activation, refresh persistence, pipeline/dashboard/activity verification. |

Recommended implementation order:

1. Approve this policy and critical decisions.
2. Implement constants and transition service with failing tests.
3. Integrate review, negotiation, approval, and signature one domain at a time, stopping for verification after each.
4. Align frontend labels/actions and portfolio reporting.
5. Generate a backfill report, then apply the migration/constraint.
6. Finish with real DB integration and browser golden-path proof.

## 13. Acceptance criteria for Phase 2B

- Every stage transition is validated by current stage, event, actor, current version, and workflow conditions.
- No service assigns `contract.stage` directly.
- Workflow update, stage update, version update, and activity event commit atomically.
- Review, negotiation, approval, signature, Landing, dashboard, stepper, versions, and activity use the approved vocabulary.
- Invalid transitions produce deterministic errors and tests.
- Existing rows receive an explainable backfilled stage.
- A full persisted golden path and principal failure branches pass without mocking lifecycle transitions.
- Browser proof confirms labels, actions, counts, deep links, refresh persistence, and no unknown-state warnings.
