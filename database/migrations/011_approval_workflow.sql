-- Feature 8: Internal Legal Approval Workflow + Feature 7 negotiation polish columns
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT 'negotiation';

ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS workflow_status text NOT NULL DEFAULT 'pending_analysis';
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS lawyer_final_clause text;
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS lawyer_final_clause_ar text;
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS sent_at timestamptz;
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS final_summary jsonb;

UPDATE negotiations SET workflow_status = 'ready' WHERE ai_summary IS NOT NULL AND workflow_status = 'pending_analysis';
UPDATE negotiations SET workflow_status = 'sent_to_client' WHERE status = 'sent' AND workflow_status NOT IN ('accepted', 'closed', 'client_responded');

CREATE TABLE IF NOT EXISTS approval_workflows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'in_progress',
  current_step_order int NOT NULL DEFAULT 1,
  started_by text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_approval_workflows_contract ON approval_workflows(contract_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_workflows_one_active
  ON approval_workflows (contract_id) WHERE status = 'in_progress';

CREATE TABLE IF NOT EXISTS approval_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_id uuid NOT NULL REFERENCES approval_workflows(id) ON DELETE CASCADE,
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  step_order int NOT NULL,
  role text NOT NULL,
  approver_name text,
  status text NOT NULL DEFAULT 'locked',
  comment text,
  acted_at timestamptz,
  acted_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workflow_id, step_order)
);
CREATE INDEX IF NOT EXISTS idx_approval_steps_workflow ON approval_steps(workflow_id);

CREATE TABLE IF NOT EXISTS activity_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  actor text,
  role text,
  step_order int,
  comment text,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_events_contract ON activity_events(contract_id);
