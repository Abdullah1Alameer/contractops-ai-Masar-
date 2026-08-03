-- F3 — Payment Conditions Tracker
ALTER TABLE payment_milestones DROP CONSTRAINT IF EXISTS payment_milestones_status_check;
ALTER TABLE payment_milestones ADD CONSTRAINT payment_milestones_status_check CHECK (
  status IN ('blocked','claimable','paid','overdue','needs_review')
);

ALTER TABLE payment_milestones
  ADD COLUMN IF NOT EXISTS type text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS amount_percentage numeric,
  ADD COLUMN IF NOT EXISTS due_date date,
  ADD COLUMN IF NOT EXISTS paid boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS paid_at timestamptz,
  ADD COLUMN IF NOT EXISTS confidence numeric(3,2),
  ADD COLUMN IF NOT EXISTS generated boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
