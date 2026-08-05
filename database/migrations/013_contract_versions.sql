-- Feature 10: Contract Version Control

CREATE TABLE IF NOT EXISTS contract_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  version_number int NOT NULL,
  version_label text,
  parent_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  source text NOT NULL DEFAULT 'initial_upload',
  status text NOT NULL DEFAULT 'draft',
  change_summary text,
  file_path text,
  extracted_json jsonb,
  ai_summary text,
  created_by text,
  review_request_id uuid,
  negotiation_id uuid,
  approval_workflow_id uuid,
  signature_request_id uuid,
  hash_sha256 text,
  is_current boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(contract_id, version_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contract_versions_current
  ON contract_versions (contract_id) WHERE is_current;

CREATE INDEX IF NOT EXISTS idx_contract_versions_contract ON contract_versions(contract_id);

CREATE TABLE IF NOT EXISTS version_comparisons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  from_version_id uuid NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,
  to_version_id uuid NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,
  diff_json jsonb,
  ai_explanation text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(from_version_id, to_version_id)
);

ALTER TABLE review_requests ADD COLUMN IF NOT EXISTS version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL;
ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL;
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL;
ALTER TABLE signature_requests ADD COLUMN IF NOT EXISTS version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL;

-- Backfill Version 1 for every existing contract
INSERT INTO contract_versions (
  id, contract_id, version_number, version_label, source, status, file_path, is_current, created_at
)
SELECT
  gen_random_uuid(),
  c.id,
  1,
  'v1',
  'initial_upload',
  CASE WHEN c.status IN ('ready', 'needs_review') THEN c.status ELSE 'draft' END,
  c.file_url,
  true,
  COALESCE(c.created_at, now())
FROM contracts c
WHERE NOT EXISTS (
  SELECT 1 FROM contract_versions cv WHERE cv.contract_id = c.id AND cv.version_number = 1
);

UPDATE review_requests rr
SET version_id = cv.id
FROM contract_versions cv
WHERE cv.contract_id = rr.contract_id AND cv.version_number = 1 AND rr.version_id IS NULL;

UPDATE negotiations n
SET version_id = cv.id
FROM contract_versions cv
WHERE cv.contract_id = n.contract_id AND cv.version_number = 1 AND n.version_id IS NULL;

UPDATE approval_workflows aw
SET version_id = cv.id
FROM contract_versions cv
WHERE cv.contract_id = aw.contract_id AND cv.version_number = 1 AND aw.version_id IS NULL;

UPDATE signature_requests sr
SET version_id = cv.id
FROM contract_versions cv
WHERE cv.contract_id = sr.contract_id AND cv.version_number = 1 AND sr.version_id IS NULL;
