-- Configurable approval routes: replaces the hardcoded four-role approval
-- sequence with a per-contract configured route, optionally copied from a
-- reusable saved template. See docs/configurable-approval-routes-report.md.

-- Snapshot of "must this step be completed" onto the actual workflow step,
-- not just the route definition it came from.
ALTER TABLE approval_steps
  ADD COLUMN IF NOT EXISTS required boolean NOT NULL DEFAULT true;

-- Traceability from a started workflow back to the contract-specific route
-- (and, transitively, the reusable template) it was snapshotted from.
ALTER TABLE approval_workflows
  ADD COLUMN IF NOT EXISTS route_name text,
  ADD COLUMN IF NOT EXISTS contract_route_id uuid;

-- Reusable, org-scoped saved route templates.
CREATE TABLE IF NOT EXISTS approval_routes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  -- Single-workspace demo has one implicit tenant; this column exists so a
  -- real multi-tenant deployment has somewhere to scope routes without a
  -- further migration. See "remaining limitations" in the report.
  scope text NOT NULL DEFAULT 'default',
  active boolean NOT NULL DEFAULT true,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approval_route_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id uuid NOT NULL REFERENCES approval_routes(id) ON DELETE CASCADE,
  step_order integer NOT NULL,
  role text NOT NULL,
  approver_name text,
  required boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (route_id, step_order)
);

-- Contract-specific configured route. Draft until a workflow is started
-- from it (status -> 'started'); editing/replacing is only allowed while
-- draft. A cancelled workflow marks its route 'cancelled', not deleted, so
-- history is preserved and a fresh configure() call can create a new draft.
CREATE TABLE IF NOT EXISTS contract_approval_routes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  name text,
  source_route_id uuid REFERENCES approval_routes(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'draft',
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_contract_approval_routes_contract ON contract_approval_routes(contract_id);

CREATE TABLE IF NOT EXISTS contract_approval_route_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_route_id uuid NOT NULL REFERENCES contract_approval_routes(id) ON DELETE CASCADE,
  step_order integer NOT NULL,
  role text NOT NULL,
  approver_name text,
  required boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (contract_route_id, step_order)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'approval_workflows_contract_route_id_fkey'
  ) THEN
    ALTER TABLE approval_workflows
      ADD CONSTRAINT approval_workflows_contract_route_id_fkey
      FOREIGN KEY (contract_route_id) REFERENCES contract_approval_routes(id) ON DELETE SET NULL;
  END IF;
END $$;
