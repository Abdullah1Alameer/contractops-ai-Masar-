-- F4 — Flow-Down X-Ray
ALTER TABLE flowdown_findings DROP CONSTRAINT IF EXISTS flowdown_findings_status_check;
ALTER TABLE flowdown_findings ADD CONSTRAINT flowdown_findings_status_check CHECK (
  status IN ('fully_flowed_down','modified','missing','weaker','stronger','conflict')
);

ALTER TABLE flowdown_findings DROP CONSTRAINT IF EXISTS flowdown_findings_severity_check;
ALTER TABLE flowdown_findings ADD CONSTRAINT flowdown_findings_severity_check CHECK (
  severity IN ('critical','high','medium','low','informational')
);

ALTER TABLE flowdown_findings
  ADD COLUMN IF NOT EXISTS category text NOT NULL DEFAULT 'other',
  ADD COLUMN IF NOT EXISTS explanation text,
  ADD COLUMN IF NOT EXISTS recommendation text,
  ADD COLUMN IF NOT EXISTS main_citation text,
  ADD COLUMN IF NOT EXISTS sub_citation text,
  ADD COLUMN IF NOT EXISTS confidence numeric(3,2),
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_flowdown_pair_time
  ON flowdown_findings(main_contract_id, subcontract_id, created_at DESC);
