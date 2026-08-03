-- ContractOps AI — core schema
-- Owned tables (written by the F1 AI pipeline): contracts, clauses, extractions, obligations
-- Teammate tables (created empty here, populated by F2/F3/F4): deadlines, events, payment_milestones, flowdown_findings

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE contracts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text,
  type text CHECK (type IN ('main','subcontract')),
  parent_main_contract_id uuid NULL REFERENCES contracts(id),
  party_a text,
  party_b text,
  value_sar numeric NULL,
  start_date date NULL,
  end_date date NULL,
  governing_law text NULL,
  retention_pct numeric NULL,
  bond_expiry date NULL,
  warranty_end date NULL,
  language text CHECK (language IN ('ar','en','mixed')) NULL,
  calendar text CHECK (calendar IN ('gregorian','hijri','mixed')) NULL,
  status text NOT NULL DEFAULT 'processing' CHECK (status IN ('processing','ready','failed','needs_review')),
  file_url text,
  raw_text text,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_contracts_type ON contracts(type);
CREATE INDEX idx_contracts_parent ON contracts(parent_main_contract_id);

CREATE TABLE clauses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  clause_ref text,
  quote text,
  page int,
  char_start int,
  char_end int
);
CREATE INDEX idx_clauses_contract ON clauses(contract_id);

CREATE TABLE extractions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  field_name text NOT NULL,
  value_json jsonb,
  confidence numeric(3,2),
  clause_id uuid NULL REFERENCES clauses(id),
  status text DEFAULT 'auto' CHECK (status IN ('auto','verified','edited')),
  UNIQUE(contract_id, field_name)
);

CREATE TABLE obligations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  description text,
  responsible_party text,
  due_date date NULL,
  penalty_text text NULL,
  reminder_days_before int DEFAULT 3,
  status text DEFAULT 'pending' CHECK (status IN ('pending','done','overdue')),
  source_clause_id uuid REFERENCES clauses(id)
);
CREATE INDEX idx_obligations_contract ON obligations(contract_id);
CREATE INDEX idx_obligations_due ON obligations(due_date);

-- ============ F2: deadlines engine (EMPTY — teammate populates) ============
CREATE TABLE deadlines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  type text CHECK (type IN ('notice_window','bond_expiry','warranty_end','payment','contract_expiry')),
  label text,
  notice_period_days int NULL,
  deadline_date date,
  severity text CHECK (severity IN ('info','warning','critical')),
  source_clause_id uuid REFERENCES clauses(id),
  triggered_by_event_id uuid NULL
);

CREATE TABLE events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  type text,
  description text,
  event_date date
);

-- ============ F3: payment milestones (EMPTY — teammate populates) ============
CREATE TABLE payment_milestones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  seq int,
  label text,
  amount_sar numeric NULL,
  preconditions jsonb,
  status text CHECK (status IN ('blocked','claimable','paid')),
  source_clause_id uuid REFERENCES clauses(id),
  UNIQUE(contract_id, seq)
);

-- ============ F4: flow-down comparison (EMPTY — teammate populates) ============
CREATE TABLE flowdown_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  main_contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  subcontract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  obligation_summary text,
  status text CHECK (status IN ('mirrored','partial','missing')),
  main_clause_id uuid REFERENCES clauses(id),
  sub_clause_id uuid NULL REFERENCES clauses(id),
  risk_note text,
  severity text CHECK (severity IN ('low','medium','high'))
);
