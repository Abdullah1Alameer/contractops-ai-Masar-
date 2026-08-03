-- F2: Time-Bar Guardian — extend deadlines for rebuildable engine

ALTER TABLE deadlines DROP CONSTRAINT IF EXISTS deadlines_type_check;
ALTER TABLE deadlines ADD CONSTRAINT deadlines_type_check CHECK (
  type IN (
    'notice_deadline', 'submission_deadline', 'contract_expiry', 'bond_expiry',
    'warranty_expiry', 'insurance_expiry', 'payment_deadline', 'other'
  )
);

ALTER TABLE deadlines DROP CONSTRAINT IF EXISTS deadlines_severity_check;
ALTER TABLE deadlines ADD CONSTRAINT deadlines_severity_check CHECK (
  severity IN ('normal', 'info', 'warning', 'critical')
);

ALTER TABLE deadlines
  ADD COLUMN IF NOT EXISTS title text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS source_trigger_date date,
  ADD COLUMN IF NOT EXISTS needs_review boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS review_reason text,
  ADD COLUMN IF NOT EXISTS responsible_party text,
  ADD COLUMN IF NOT EXISTS confidence numeric(3,2),
  ADD COLUMN IF NOT EXISTS generated boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

DELETE FROM deadlines WHERE type IN ('notice_window', 'warranty_end', 'payment');

ALTER TABLE deadlines DROP CONSTRAINT IF EXISTS deadlines_triggered_by_event_fk;
ALTER TABLE deadlines
  ADD CONSTRAINT deadlines_triggered_by_event_fk
  FOREIGN KEY (triggered_by_event_id) REFERENCES events(id) ON DELETE CASCADE;
