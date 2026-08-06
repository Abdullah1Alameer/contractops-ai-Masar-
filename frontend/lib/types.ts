export type ContractStatus = "processing" | "ready" | "needs_review" | "failed" | "unsupported";

export type ContractType = "main" | "subcontract" | null;

export type WorkflowReviewStatus =
  | "sent"
  | "opened"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "expired"
  | "cancelled";

export type WorkflowNegotiationStatus =
  | "pending_analysis"
  | "ready"
  | "edited_by_legal"
  | "sent_to_client"
  | "client_responded"
  | "accepted"
  | "closed";

export type WorkflowApprovalStatus =
  | "in_progress"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "cancelled";

export type WorkflowSignatureStatus =
  | "draft"
  | "created"
  | "sent"
  | "viewed"
  | "partially_signed"
  | "completed"
  | "declined"
  | "expired"
  | "cancelled"
  | "error";

export interface WorkflowSummary {
  review_status: WorkflowReviewStatus | null;
  negotiation_status: WorkflowNegotiationStatus | null;
  approval_status: WorkflowApprovalStatus | null;
  signature_status: WorkflowSignatureStatus | null;
}

export interface ClauseSource {
  id?: string;
  clause_ref: string | null;
  quote: string;
  page: number;
  char_start: number;
  char_end: number;
}

export interface ContractListItem {
  id: string;
  title: string;
  type: ContractType;
  contract_category: string | null;
  supported: boolean | null;
  classification_confidence: number | null;
  party_b: string | null;
  value_sar: number | null;
  end_date?: string | null;
  status: ContractStatus;
  stage?: string | null;
  workflow_summary?: WorkflowSummary | null;
  current_version_number?: number | null;
  total_versions?: number;
  obligation_counts: { pending: number; overdue: number };
  created_at?: string | null;
  created_by?: string | null;
}

export interface ExtractionRow {
  field_name: string;
  value_json: any;
  confidence: number | null;
  status: string;
  clause: ClauseSource | null;
}

export interface ContractDetail {
  id: string;
  title: string;
  type: ContractType;
  parent_main_contract_id: string | null;
  party_a: string | null;
  party_b: string | null;
  value_sar: number | null;
  start_date: string | null;
  end_date: string | null;
  governing_law: string | null;
  retention_pct: number | null;
  bond_expiry: string | null;
  warranty_end: string | null;
  language: string | null;
  calendar: string | null;
  status: ContractStatus;
  stage?: string;
  current_version_number?: number | null;
  total_versions?: number;
  contract_category: string | null;
  supported: boolean | null;
  classification_confidence: number | null;
  classification_message: string | null;
  extractions: ExtractionRow[];
  execution_date?: string | null;
  commencement_date?: string | null;
  date_facts?: Record<string, unknown> | null;
  risk?: RiskSummary | null;
  summary_status?: SummaryStatus;
  summary_is_stale?: boolean;
}

export type SummaryStatus = "not_generated" | "generating" | "ready" | "failed";

export interface SummaryCitation {
  clause_ref: string;
  page: number;
  quote: string;
}

export interface SummaryItem {
  text: string;
  citations: SummaryCitation[];
}

export interface SummarySection {
  status: "stated" | "not_stated";
  overview: string;
  items: SummaryItem[];
}

export type SummarySections = Record<string, SummarySection>;

export interface ContractSummaryPayload {
  status: SummaryStatus;
  summary_ar: SummarySections | null;
  summary_en: SummarySections | null;
  error_code: string | null;
  error_detail: string | null;
  generated_at: string | null;
  model: string | null;
  prompt_version?: string | null;
  is_stale: boolean;
}

export interface LayoutBlock {
  text: string;
  bbox: [number, number, number, number];
  direction: "rtl" | "ltr" | "mixed";
  column: number;
}

export interface RiskBreakdownItem {
  category: string;
  count: number;
  points: number;
  explanation: string;
  explanation_ar?: string;
}

export interface RiskFindingItem {
  id: string;
  category: string;
  code: string;
  points: number;
  count: number;
  explanation: string | null;
  explanation_ar: string | null;
  link_tab: string | null;
  source_clause_id: string | null;
  source: ClauseSource | null;
}

export interface RiskSummary {
  score: number;
  level: string;
  breakdown: RiskBreakdownItem[];
  calculation_version: string;
  generated_at?: string;
  findings?: RiskFindingItem[];
}

export interface ObligationRow {
  id: string;
  title?: string | null;
  description: string;
  responsible_party: string | null;
  beneficiary?: string | null;
  trigger_type?: string | null;
  trigger_event?: string | null;
  temporal_rule?: Record<string, unknown> | null;
  dependencies?: string[];
  contract_required_evidence?: string[];
  suggested_evidence?: string[];
  completion_criteria?: string | null;
  due_date: string | null;
  penalty_text: string | null;
  status: "pending" | "done" | "overdue" | string;
  source: ClauseSource | null;
  confidence: number | null;
}

export interface NoticePeriodItem {
  purpose: string;
  days: number;
  clause_ref: string | null;
  quote: string;
  page: number;
  confidence: number;
  clause_id: string | null;
  char_start: number | null;
  char_end: number | null;
  verified: boolean;
}

export interface SourceTarget {
  page: number;
  char_start: number;
  char_end: number;
  quote?: string;
}

export interface DeadlineRow {
  id: string;
  contract_id: string;
  type: string;
  title: string | null;
  description: string | null;
  event_date: string | null;
  deadline_date: string | null;
  source_trigger_date: string | null;
  notice_period_days: number | null;
  days_remaining: number | null;
  severity: string;
  status: string;
  time_barred: boolean;
  needs_review: boolean;
  review_reason: string | null;
  responsible_party: string | null;
  clause_ref: string | null;
  quote: string | null;
  page: number | null;
  confidence: number | null;
  verified: boolean;
  char_start: number | null;
  char_end: number | null;
  event_type?: string | null;
  base_date?: string | null;
  base_date_type?: string | null;
  direction?: string | null;
  offset_value?: number | null;
  offset_unit?: string | null;
  computed_date?: string | null;
  calculation_explanation?: string | null;
  calculation_explanation_ar?: string | null;
  condition_text?: string | null;
  temporal_rule?: Record<string, unknown> | null;
}

export interface NegotiationOpportunityRow {
  id: string;
  category: string;
  clause_ref: string | null;
  issue: string | null;
  recommendation: string | null;
  suggested_counterproposal: string | null;
  confidence: number | null;
  human_decision_required: boolean;
  negotiability: string | null;
  business_impact?: string | null;
  legal_impact?: string | null;
  financial_impact?: string | null;
  current_text?: string | null;
}

export interface DeadlineSummary {
  total: number;
  critical: number;
  within_14_days: number;
  missed_or_time_barred: number;
  needs_review: number;
}

export interface DeadlinesResponse {
  deadlines: DeadlineRow[];
  summary: DeadlineSummary;
}

export interface Precondition {
  id: string;
  label: string;
  type: string;
  required: boolean;
  completed: boolean;
}

export interface PaymentMilestoneRow {
  id: string;
  contract_id: string;
  sequence: number;
  type: string;
  label: string | null;
  description: string | null;
  amount_sar: number | null;
  amount_percentage: number | null;
  due_date: string | null;
  status: string;
  readiness_percentage: number;
  claimable: boolean;
  paid: boolean;
  preconditions: Precondition[];
  missing_preconditions: string[];
  clause_ref: string | null;
  quote: string | null;
  page: number | null;
  confidence: number | null;
  verified: boolean;
  char_start: number | null;
  char_end: number | null;
  created_at: string | null;
  updated_at: string | null;
  next_due_date?: string | null;
  frequency?: string | null;
  due_rule?: { type?: string; day?: number } | null;
  role?: string | null;
  parent_seq?: number | null;
  calculation_explanation?: string | null;
  responsible_party?: string | null;
  beneficiary?: string | null;
  trigger_event?: string | null;
}

export interface PaymentSummary {
  total: number;
  claimable_sar: number;
  blocked_sar: number;
  overdue_sar: number;
  paid_sar: number;
  needs_review_count: number;
}

export interface MilestonesResponse {
  milestones: PaymentMilestoneRow[];
  summary: PaymentSummary;
}

export interface FlowdownClauseSource {
  clause_id: string;
  clause_ref: string | null;
  quote: string | null;
  page: number | null;
  char_start: number | null;
  char_end: number | null;
}

export interface FlowdownFindingRow {
  id: string;
  category: string;
  status: string;
  risk_level: string;
  explanation: string | null;
  recommendation: string | null;
  explanation_ar?: string | null;
  explanation_en?: string | null;
  recommendation_ar?: string | null;
  recommendation_en?: string | null;
  confidence: number | null;
  main_citation: string | null;
  sub_citation: string | null;
  main_source: FlowdownClauseSource | null;
  sub_source: FlowdownClauseSource | null;
}

export interface FlowdownSummary {
  overall_risk_score: number;
  critical_count: number;
  missing_count: number;
  conflict_count: number;
  coverage_pct: number;
  total: number;
}

export interface FlowdownResponse {
  main: { id: string; title: string | null };
  sub: { id: string; title: string | null };
  findings: FlowdownFindingRow[];
  summary: FlowdownSummary;
}

export interface FlowdownContractOption {
  id: string;
  title: string;
  contract_category: string | null;
}

export interface FlowdownContractsList {
  main: FlowdownContractOption[];
  sub: FlowdownContractOption[];
}

export type DeliveryStatus = "pending" | "sending" | "sent" | "failed" | "cancelled";

export interface DeliveryRow {
  id: string;
  message_type: string;
  recipient: string;
  subject: string;
  contract_id: string;
  review_request_id: string | null;
  signature_request_id: string | null;
  signer_id: string | null;
  status: DeliveryStatus;
  attempt_count: number;
  provider_message_id: string | null;
  safe_error_code: string | null;
  created_at: string | null;
  sent_at: string | null;
  failed_at: string | null;
}

export type ReviewStatus =
  | "sent"
  | "opened"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "expired";

export interface ReviewCommentRow {
  id: string;
  clause_ref: string | null;
  page: number | null;
  comment: string;
  created_at: string | null;
}

export interface ReviewRequestRow {
  id: string;
  contract_id: string;
  recipient_name: string;
  recipient_email: string;
  sender_name: string | null;
  sender_email: string | null;
  message: string | null;
  status: ReviewStatus;
  expires_at: string | null;
  opened_at: string | null;
  responded_at: string | null;
  created_at: string | null;
  comments: ReviewCommentRow[];
  decision: string | null;
  overall_comment: string | null;
  review_link?: string;
  token?: string;
  contract_title?: string;
  version_id?: string | null;
  is_stale?: boolean;
  contract_stage?: string | null;
  actionable?: boolean;
  terminal_decision?: string | null;
  next_allowed_actions?: string[];
  delivery?: DeliveryRow | null;
  delivery_history?: DeliveryRow[];
}

export interface SendReviewResponse {
  review_link: string;
  email: { subject: string; body: string; review_link: string };
  request: ReviewRequestRow;
  delivery?: DeliveryRow | null;
}

export interface ReviewPortalObligationRow {
  id: string;
  title: string | null;
  description: string | null;
  responsible_party: string | null;
  beneficiary: string | null;
  trigger_type: string | null;
  trigger_event: string | null;
  completion_criteria: string | null;
  contract_required_evidence: string[];
  suggested_evidence: string[];
  due_date: string | null;
  penalty_text: string | null;
  status: string;
  clause_ref: string | null;
  page: number | null;
  quote: string | null;
}

export interface ReviewPortalRiskItem {
  type: "finding" | "penalty" | "deadline" | "comparison" | string;
  category: string | null;
  label: string;
  detail: string | null;
  detail_ar: string | null;
  severity: string;
  link_tab: string | null;
  contributes_to_score: boolean;
  // penalty/finding source fields (finding items now carry the same
  // resolved clause source risk_engine.serialize_risk() already computes)
  cap?: string | null;
  rate?: string | null;
  quote?: string | null;
  clause_ref?: string | null;
  page?: number | null;
}

export interface ReviewPortalRisks {
  score: number;
  level: string;
  calculation_version: string | null;
  items: ReviewPortalRiskItem[];
  count: number;
}

export interface ReviewPortalPayload {
  contract: {
    id: string;
    title: string | null;
    party_a: string | null;
    party_b: string | null;
    value_sar: number | null;
    start_date: string | null;
    end_date: string | null;
    governing_law: string | null;
    status: string;
    contract_category: string | null;
  };
  ai_summary: string;
  business_summary: ContractSummaryPayload;
  document_url: string;
  notices: NoticePeriodItem[];
  obligations: ReviewPortalObligationRow[];
  timeline: { deadlines: DeadlineRow[]; summary: DeadlineSummary };
  payments: { milestones: PaymentMilestoneRow[]; summary: PaymentSummary };
  comparison: FlowdownResponse | null;
  comparison_unavailable_reason: "not_linked" | "not_yet_compared" | null;
  risks: ReviewPortalRisks;
  recipient_name: string;
  status: ReviewStatus;
  expires_at: string | null;
  opened_at: string | null;
  responded_at: string | null;
  comments: ReviewCommentRow[];
  decision: string | null;
  overall_comment: string | null;
  read_only: boolean;
  contract_stage: string | null;
  actionable: boolean;
  is_stale: boolean;
  terminal_decision: string | null;
  next_allowed_actions: string[];
}

export interface NegotiationRow {
  id: string;
  contract_id: string;
  review_request_id: string | null;
  review_comment_id: string | null;
  clause_ref: string | null;
  original_clause: string | null;
  reviewer_comment: string | null;
  reviewer_decision: string | null;
  ai_summary: string | null;
  business_impact: string | null;
  legal_impact: string | null;
  risk_level: string | null;
  recommendation: string | null;
  reasoning: string | null;
  counter_clause: string | null;
  counter_clause_ar: string | null;
  pros: string[];
  cons: string[];
  status: string;
  editing_status: string;
  edited_by_lawyer: boolean;
  sent_review_request_id: string | null;
  workflow_status: string;
  closure_outcome:
    | "agreement_reached"
    | "counterparty_rejected"
    | "internally_abandoned"
    | "superseded"
    | null;
  lawyer_final_clause: string | null;
  lawyer_final_clause_ar: string | null;
  sent_at: string | null;
  final_summary: Record<string, unknown> | null;
  confidence: number | null;
  created_at: string | null;
  updated_at: string | null;
  version_id?: string | null;
  current_version_id?: string | null;
  is_stale?: boolean;
  actionable?: boolean;
  contract_stage?: string | null;
  current_round?: number;
  total_rounds?: number;
  unresolved_count?: number;
  next_allowed_actions?: string[];
  analysis_status?: string;
  human_decision_required?: boolean;
  assigned_lawyer?: string | null;
}

export interface NegotiationCandidate {
  review_id: string;
  comment_id: string | null;
  clause_ref: string | null;
  reviewer_comment: string | null;
  review_status: string;
  original_clause: string | null;
  negotiation: NegotiationRow | null;
}

export interface NegotiationsResponse {
  negotiations: NegotiationRow[];
  candidates: NegotiationCandidate[];
}

export interface NegotiationBoardItem {
  negotiation_id: string;
  contract_id: string;
  contract_title: string | null;
  counterparty: string | null;
  clause_ref: string | null;
  issue: string | null;
  workflow_status: string;
  editing_status: string;
  contract_stage: string | null;
  risk_level: string | null;
  recommendation: string | null;
  assigned_lawyer: string | null;
  waiting_party: "client" | "lawyer" | null;
  message_count: number;
  sent_at: string | null;
  updated_at: string | null;
  days_waiting: number | null;
  sla_status: "ok" | "approaching" | "overdue" | null;
  critical_deadlines: number;
  missed_deadlines: number;
  is_stale: boolean;
}

export interface NegotiationBoardSummary {
  total_active: number;
  pending: number;
  waiting_client: number;
  waiting_lawyer: number;
  high_risk: number;
  overdue: number;
}

export interface NegotiationBoardResponse {
  items: NegotiationBoardItem[];
  summary: NegotiationBoardSummary;
}

export interface SendNegotiationResponse {
  negotiation: NegotiationRow;
  review_link: string;
  email: { subject: string; body: string; review_link: string };
  request: ReviewRequestRow;
}

export interface ApprovalStepRow {
  id: string;
  step_order: number;
  role: string;
  approver_name: string | null;
  status: string;
  required?: boolean;
  comment: string | null;
  acted_at: string | null;
}

export interface ApprovalWorkflowView {
  id: string;
  contract_id: string;
  status: string;
  current_step_order: number;
  started_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  steps: ApprovalStepRow[];
  current_step: ApprovalStepRow | null;
  allowed_actions: string[];
  next_allowed_actions?: string[];
  approved_count: number;
  remaining_count: number;
  completed_step_count?: number;
  total_step_count?: number;
  current_required_role?: string | null;
  contract_stage?: string | null;
  actionable?: boolean;
  stale?: boolean;
  is_stale?: boolean;
  override_used?: boolean;
  version_id?: string | null;
  route_name?: string | null;
  contract_route_id?: string | null;
  // The backend engine only ever gates the next step on the previous one
  // being resolved — always "sequential" today. Never rendered as if
  // parallel/mixed execution were actually possible.
  workflow_type?: "sequential";
}

export interface ApprovalsResponse {
  workflow: ApprovalWorkflowView | null;
  unresolved_negotiations: { id: string; clause_ref: string | null; workflow_status: string }[];
}

// Configurable approval routes — see docs/configurable-approval-routes-report.md.
export interface ApprovalRouteStepInput {
  role: string;
  approver_name?: string | null;
  required?: boolean;
}

export interface ApprovalRouteStepRow {
  id: string;
  step_order: number;
  role: string;
  approver_name: string | null;
  required: boolean;
}

export interface SavedApprovalRoute {
  id: string;
  name: string;
  scope: string;
  active: boolean;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  steps: ApprovalRouteStepRow[];
  step_count: number;
}

export interface ContractApprovalRoute {
  id: string;
  contract_id: string;
  name: string | null;
  source_route_id: string | null;
  status: "draft" | "started" | "cancelled";
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  steps: ApprovalRouteStepRow[];
  step_count: number;
  workflow_type: "sequential";
}

export interface ActivityEventRow {
  id: string;
  event_type: string;
  actor: string | null;
  role: string | null;
  step_order: number | null;
  comment: string | null;
  created_at: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface ApprovalSummaryKpis {
  internal_review: number;
  pending_business_owner: number;
  pending_legal: number;
  pending_finance: number;
  pending_executive: number;
  approved_awaiting_signature: number;
}

export interface SignatureSignerRow {
  id: string;
  signer_order: number;
  name: string;
  email: string;
  role: string;
  status: string;
  opened_at: string | null;
  signed_at: string | null;
  declined_at?: string | null;
  decline_reason?: string | null;
  signature_type?: string | null;
  delivery?: DeliveryRow | null;
  eligible?: boolean;
  signer_link?: string | null;
}

export interface SignatureRequestRow {
  id: string;
  contract_id: string;
  provider: string;
  status: string;
  subject: string;
  message: string | null;
  signing_order_enabled: boolean;
  expires_at: string;
  sent_at: string | null;
  completed_at: string | null;
  declined_at?: string | null;
  decline_reason?: string | null;
  signed_file_url?: string | null;
  certificate_file_url?: string | null;
  original_hash?: string | null;
  signed_hash?: string | null;
  signers: SignatureSignerRow[];
  progress: { completed: number; total: number };
  is_stale?: boolean;
  version_id?: string | null;
  fields?: SignatureField[];
}

// Signature field placement — see docs/signature-placement-and-template-flow-report.md.
export type SignatureFieldType = "signature" | "initials" | "name" | "date";

export interface SignatureField {
  id: string;
  signer_id: string;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  field_type: SignatureFieldType;
  required: boolean;
  ai_suggested: boolean;
}

export interface SignatureFieldInput {
  signer_id: string;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  field_type: SignatureFieldType;
  required: boolean;
}

export interface SignatureEventRow {
  id: string;
  action: string;
  actor: string | null;
  signer_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

export interface SignatureBundleResponse {
  request: SignatureRequestRow | null;
  events: SignatureEventRow[];
  can_create?: boolean;
  deliveries?: DeliveryRow[];
}

export interface SignatureSummaryKpis {
  awaiting_signature: number;
  partially_signed: number;
  completed_signatures: number;
  declined_requests: number;
  expiring_soon: number;
}

export interface SignerPublicPayload {
  contract_title: string;
  sender_name: string;
  subject: string;
  message: string | null;
  signer: {
    name: string;
    role: string;
    order: number;
    status: string;
    opened_at: string | null;
    signed_at: string | null;
  };
  progress: { completed: number; total: number; order_enabled: boolean };
  expires_at: string;
  consent_text: { en: string; ar: string };
  document_url: string;
  provider_label: string;
  request_status: string;
  waiting_for_prior: boolean;
  read_only: boolean;
  declined: boolean;
  fields: SignatureField[];
}

// Templates — see docs/signature-placement-and-template-flow-report.md.
export interface TemplateSummary {
  id: string;
  key: string;
  title_en: string;
  title_ar: string;
  category: string | null;
  language: "ar" | "en" | "both";
  industry: string | null;
  usage_count: number;
  updated_at: string | null;
}

export interface TemplateVariableField {
  key: string;
  label_en: string;
  label_ar: string;
  type: "text" | "textarea" | "number" | "date";
  required: boolean;
}

export interface TemplateDetail extends TemplateSummary {
  description_en: string | null;
  description_ar: string | null;
  variables: TemplateVariableField[];
  clauses: { title_en: string; title_ar: string }[];
}

export interface TemplatePreview {
  template: TemplateSummary;
  missing_variables: string[];
  sections_en: { title: string; body: string }[];
  sections_ar: { title: string; body: string }[];
}

export interface ContractVersionRow {
  id: string;
  contract_id: string;
  version_number: number;
  version_label: string;
  source: string;
  status: string;
  change_summary: string | null;
  created_by: string | null;
  is_current: boolean;
  created_at: string | null;
  ai_summary: string | null;
  review_status?: string | null;
  approval_status?: string | null;
  signature_status?: string | null;
  restored_by?: string | null;
  restored_at?: string | null;
  extracted_json?: Record<string, unknown> | null;
  risk_score?: number | null;
  negotiation_status?: string | null;
  workflow_stale_count?: number;
  event_count?: number;
  last_activity_at?: string | null;
  created_by_display?: string | null;
  signed_at?: string | null;
  approved_at?: string | null;
  review_completed_at?: string | null;
  negotiation_completed_at?: string | null;
  is_superseded?: boolean;
  is_signed?: boolean;
  is_approved?: boolean;
  display_status?: string;
  workflow_summary?: WorkflowSummary;
}

export interface VersionLineageEvent {
  event_id: string;
  version_id: string;
  version_number: number | null;
  event_type: string;
  event_category: string;
  title_key: string;
  description?: string | null;
  actor?: string | null;
  actor_role?: string | null;
  timestamp?: string | null;
  status?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  metadata?: Record<string, unknown>;
  source_version_id?: string | null;
  target_version_id?: string | null;
}

export interface VersionLineageVersion {
  id: string;
  version_number: number;
  version_label: string;
  source: string;
  status: string;
  is_current: boolean;
  is_approved: boolean;
  is_signed: boolean;
  is_superseded: boolean;
  created_by: string | null;
  created_by_display: string | null;
  created_at: string | null;
  change_summary: string | null;
  parent_version_id: string | null;
  risk_score: number | null;
  workflow_summary: WorkflowSummary;
  workflow_stale_count: number;
  event_count: number;
  last_activity_at: string | null;
  signed_at: string | null;
  approved_at: string | null;
  review_completed_at: string | null;
  negotiation_completed_at: string | null;
  review_status?: string | null;
  approval_status?: string | null;
  signature_status?: string | null;
  negotiation_status?: string | null;
  events: VersionLineageEvent[];
}

export interface VersionLineageTransition {
  from_version_id: string;
  to_version_id: string;
  reason: string;
  created_at: string | null;
  actor: string | null;
}

export interface VersionLineageResponse {
  contract_id: string;
  current_version_id: string | null;
  current_version_number: number | null;
  versions: VersionLineageVersion[];
  transitions: VersionLineageTransition[];
}

export interface VersionCompareChangeSection {
  summary: string;
  items: string[];
}

export interface VersionCompareClauseItem {
  clause_ref: string;
  note: string;
}

export interface VersionCompareRich {
  executive_summary: string;
  overall_risk_score: number;
  recommendation: string;
  risk_changes: VersionCompareChangeSection;
  financial_changes: VersionCompareChangeSection;
  legal_changes: VersionCompareChangeSection;
  liability_changes: VersionCompareChangeSection;
  termination_changes: VersionCompareChangeSection;
  confidentiality_changes: VersionCompareChangeSection;
  timeline_changes: VersionCompareChangeSection;
  payment_changes: VersionCompareChangeSection;
  added_clauses: VersionCompareClauseItem[];
  removed_clauses: VersionCompareClauseItem[];
  modified_clauses: VersionCompareClauseItem[];
}

export interface VersionCompareDiff {
  schema_version?: number;
  added_fields?: string[];
  removed_fields?: string[];
  modified_fields?: string[];
  rich?: VersionCompareRich;
  derived_flags?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface VersionHistoryResponse {
  versions: ContractVersionRow[];
  current_version_number: number | null;
  total_versions: number;
}

export interface VersionCompareResult {
  from_version_id: string;
  to_version_id: string;
  from_version_number?: number;
  to_version_number?: number;
  from_extracted_json?: Record<string, unknown> | null;
  to_extracted_json?: Record<string, unknown> | null;
  diff: VersionCompareDiff;
  ai_explanation: string;
  cached?: boolean;
}

export interface NegotiationMonitorThread {
  id: string;
  contract_id: string;
  contract_title: string | null;
  counterparty_name: string | null;
  counterparty_email: string | null;
  subject: string | null;
  status: string;
  overall_risk_score: number | null;
  detected_action: string | null;
  requires_attention: boolean;
  last_message_at: string | null;
  assigned_lawyer: string | null;
  contract_stage?: string | null;
  is_stale?: boolean;
  actionable?: boolean;
  provider?: string;
  simulated?: boolean;
  next_allowed_actions?: string[];
}

export interface NegotiationReviewPackageRow {
  id: string;
  thread_id: string;
  status: string;
  executive_summary: string | null;
  overall_risk_score: number | null;
  recommendation: string | null;
  package_json: Record<string, unknown> | null;
  draft_email_subject_en: string | null;
  draft_email_subject_ar: string | null;
  draft_email_body_en: string | null;
  draft_email_body_ar: string | null;
  lawyer_edited_json: Record<string, unknown> | null;
}
