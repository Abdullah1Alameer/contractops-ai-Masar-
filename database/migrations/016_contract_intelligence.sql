-- Contract intelligence engines: typed dates, temporal rules, risk, negotiation

ALTER TABLE contracts
  ADD COLUMN IF NOT EXISTS execution_date date,
  ADD COLUMN IF NOT EXISTS commencement_date date,
  ADD COLUMN IF NOT EXISTS date_facts jsonb;

ALTER TABLE deadlines
  ADD COLUMN IF NOT EXISTS event_type text,
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS temporal_rule jsonb,
  ADD COLUMN IF NOT EXISTS condition_key text,
  ADD COLUMN IF NOT EXISTS calculation_explanation text,
  ADD COLUMN IF NOT EXISTS calculation_explanation_ar text;

ALTER TABLE payment_milestones DROP CONSTRAINT IF EXISTS payment_milestones_status_check;
ALTER TABLE payment_milestones ADD CONSTRAINT payment_milestones_status_check CHECK (
  status IN (
    'blocked', 'claimable', 'paid', 'overdue', 'needs_review',
    'scheduled', 'due', 'inactive'
  )
);

ALTER TABLE payment_milestones
  ADD COLUMN IF NOT EXISTS role text,
  ADD COLUMN IF NOT EXISTS parent_seq integer,
  ADD COLUMN IF NOT EXISTS frequency text,
  ADD COLUMN IF NOT EXISTS due_rule jsonb,
  ADD COLUMN IF NOT EXISTS next_due_date date,
  ADD COLUMN IF NOT EXISTS period_start date,
  ADD COLUMN IF NOT EXISTS period_end date,
  ADD COLUMN IF NOT EXISTS responsible_party text,
  ADD COLUMN IF NOT EXISTS beneficiary text,
  ADD COLUMN IF NOT EXISTS trigger_event text,
  ADD COLUMN IF NOT EXISTS temporal_rule jsonb,
  ADD COLUMN IF NOT EXISTS calculation_explanation text,
  ADD COLUMN IF NOT EXISTS calculation_explanation_ar text;

ALTER TABLE obligations
  ADD COLUMN IF NOT EXISTS title text,
  ADD COLUMN IF NOT EXISTS beneficiary text,
  ADD COLUMN IF NOT EXISTS trigger_type text,
  ADD COLUMN IF NOT EXISTS trigger_event text,
  ADD COLUMN IF NOT EXISTS temporal_rule jsonb,
  ADD COLUMN IF NOT EXISTS dependencies jsonb,
  ADD COLUMN IF NOT EXISTS contract_required_evidence jsonb,
  ADD COLUMN IF NOT EXISTS suggested_evidence jsonb,
  ADD COLUMN IF NOT EXISTS completion_criteria text,
  ADD COLUMN IF NOT EXISTS manual_status boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS risk_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  category text NOT NULL,
  code text NOT NULL,
  points integer NOT NULL DEFAULT 0,
  count integer NOT NULL DEFAULT 1,
  explanation text,
  explanation_ar text,
  link_tab text,
  source_clause_id uuid REFERENCES clauses(id) ON DELETE SET NULL,
  calculation_version text NOT NULL DEFAULT 'risk-v2',
  generated boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_findings_contract ON risk_findings(contract_id);

CREATE TABLE IF NOT EXISTS negotiation_opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  category text NOT NULL,
  clause_ref text,
  current_text text,
  issue text,
  business_impact text,
  legal_impact text,
  financial_impact text,
  recommendation text,
  suggested_counterproposal text,
  confidence numeric(3, 2),
  human_decision_required boolean NOT NULL DEFAULT true,
  negotiability text,
  source_clause_id uuid REFERENCES clauses(id) ON DELETE SET NULL,
  generated boolean NOT NULL DEFAULT true,
  human_decision text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_negotiation_opportunities_contract ON negotiation_opportunities(contract_id);
