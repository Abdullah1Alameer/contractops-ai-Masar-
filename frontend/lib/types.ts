export type ContractStatus = "processing" | "ready" | "needs_review" | "failed";

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
  type: "main" | "subcontract";
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
  type: "main" | "subcontract";
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
