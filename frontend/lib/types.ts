export type ContractStatus = "processing" | "ready" | "needs_review" | "failed" | "unsupported";

export type ContractType = "main" | "subcontract" | null;

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
  status: ContractStatus;
  obligation_counts: { pending: number; overdue: number };
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
  contract_category: string | null;
  supported: boolean | null;
  classification_confidence: number | null;
  classification_message: string | null;
  extractions: ExtractionRow[];
}

export interface ObligationRow {
  id: string;
  description: string;
  responsible_party: string | null;
  due_date: string | null;
  penalty_text: string | null;
  status: "pending" | "done" | "overdue";
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
