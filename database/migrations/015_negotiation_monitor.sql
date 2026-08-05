-- Feature 16: AI Negotiation Monitor Agent

ALTER TABLE contracts ADD COLUMN IF NOT EXISTS is_template BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS template_category TEXT NULL;

CREATE TABLE IF NOT EXISTS legal_playbooks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  contract_category text,
  language text NOT NULL DEFAULT 'ar',
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS playbook_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  playbook_id uuid NOT NULL REFERENCES legal_playbooks(id) ON DELETE CASCADE,
  clause_category text NOT NULL,
  rule_name text NOT NULL,
  preferred_position text,
  fallback_position text,
  unacceptable_position text,
  approval_required_role text,
  severity text NOT NULL DEFAULT 'medium',
  guidance text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_playbook_rules_playbook ON playbook_rules(playbook_id);

CREATE TABLE IF NOT EXISTS negotiation_threads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  base_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  current_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  counterparty_name text,
  counterparty_email text,
  subject text,
  status text NOT NULL DEFAULT 'draft',
  monitoring_enabled boolean NOT NULL DEFAULT true,
  standard_template_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  playbook_id uuid REFERENCES legal_playbooks(id) ON DELETE SET NULL,
  assigned_lawyer text,
  external_thread_id text,
  last_message_at timestamptz,
  last_analyzed_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_negotiation_threads_contract ON negotiation_threads(contract_id);
CREATE INDEX IF NOT EXISTS idx_negotiation_threads_counterparty ON negotiation_threads(counterparty_email);
CREATE INDEX IF NOT EXISTS idx_negotiation_threads_status ON negotiation_threads(status);

CREATE TABLE IF NOT EXISTS negotiation_emails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id uuid REFERENCES negotiation_threads(id) ON DELETE CASCADE,
  external_message_id text,
  external_thread_id text,
  provider text NOT NULL DEFAULT 'simulated',
  direction text NOT NULL DEFAULT 'inbound',
  sender_name text,
  sender_email text,
  recipients_json jsonb,
  cc_json jsonb,
  subject text,
  body_text text,
  body_html text,
  reply_reference text,
  received_at timestamptz,
  sent_at timestamptz,
  classification text,
  processing_status text NOT NULL DEFAULT 'received',
  linked_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  requires_response boolean NOT NULL DEFAULT false,
  match_confidence numeric(4, 3),
  needs_manual_link boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_negotiation_emails_provider_ext
  ON negotiation_emails(provider, external_message_id)
  WHERE external_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_negotiation_emails_thread ON negotiation_emails(thread_id, created_at DESC);

CREATE TABLE IF NOT EXISTS negotiation_attachments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_id uuid NOT NULL REFERENCES negotiation_emails(id) ON DELETE CASCADE,
  filename text NOT NULL,
  mime_type text,
  size_bytes bigint,
  file_url text,
  file_hash_sha256 text,
  document_type text,
  processing_status text NOT NULL DEFAULT 'received',
  created_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_negotiation_attachments_hash ON negotiation_attachments(file_hash_sha256);
CREATE INDEX IF NOT EXISTS idx_negotiation_attachments_email ON negotiation_attachments(email_id);

CREATE TABLE IF NOT EXISTS negotiation_rounds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id uuid NOT NULL REFERENCES negotiation_threads(id) ON DELETE CASCADE,
  round_number int NOT NULL,
  inbound_email_id uuid REFERENCES negotiation_emails(id) ON DELETE SET NULL,
  outbound_email_id uuid REFERENCES negotiation_emails(id) ON DELETE SET NULL,
  base_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  proposed_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  review_package_id uuid,
  status text NOT NULL DEFAULT 'received',
  opened_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(thread_id, round_number)
);

CREATE TABLE IF NOT EXISTS negotiation_review_packages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id uuid NOT NULL REFERENCES negotiation_threads(id) ON DELETE CASCADE,
  email_id uuid REFERENCES negotiation_emails(id) ON DELETE SET NULL,
  base_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  proposed_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  template_version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  executive_summary text,
  overall_risk_score int,
  recommendation text,
  package_json jsonb,
  status text NOT NULL DEFAULT 'generating',
  generated_at timestamptz,
  reviewed_by text,
  reviewed_at timestamptz,
  draft_email_subject_en text,
  draft_email_subject_ar text,
  draft_email_body_en text,
  draft_email_body_ar text,
  lawyer_edited_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE negotiation_rounds
  DROP CONSTRAINT IF EXISTS negotiation_rounds_review_package_id_fkey;
ALTER TABLE negotiation_rounds
  ADD CONSTRAINT negotiation_rounds_review_package_id_fkey
  FOREIGN KEY (review_package_id) REFERENCES negotiation_review_packages(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS counterparty_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  counterparty_email text NOT NULL UNIQUE,
  counterparty_name text,
  memory_json jsonb,
  computed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seed default playbook (idempotent)
INSERT INTO legal_playbooks (id, name, contract_category, language, status)
VALUES (
  'a1000000-0000-4000-8000-000000000001'::uuid,
  'Default Commercial Playbook',
  'MSA',
  'ar',
  'active'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO playbook_rules (playbook_id, clause_category, rule_name, preferred_position, fallback_position, unacceptable_position, approval_required_role, severity, guidance)
SELECT 'a1000000-0000-4000-8000-000000000001'::uuid, v.*
FROM (VALUES
  ('Payment Terms', 'Net payment days', '30 days', '45 days', 'More than 60 days', 'finance', 'high', 'Counter with fallback before accepting extended terms.'),
  ('Liability', 'Liability cap', 'Contract value', '2x contract value', 'Unlimited liability', 'legal', 'critical', 'Reject unlimited liability; cap at contract value.'),
  ('Governing Law', 'Jurisdiction', 'Kingdom of Saudi Arabia', 'GCC arbitration with Saudi seat', 'Foreign governing law without approval', 'legal', 'high', 'Escalate governing law changes.'),
  ('Indemnity', 'Indemnity scope', 'Mutual limited indemnity', 'Broader mutual with cap', 'One-sided unlimited indemnity', 'legal', 'high', 'Require mutual caps.'),
  ('Termination', 'Notice period', '30 days written notice', '60 days', 'Immediate termination without cause', 'legal', 'medium', 'Align with playbook notice periods.'),
  ('Confidentiality', 'Term', '3 years post-termination', '5 years', 'Perpetual without carve-outs', 'compliance', 'medium', 'Limit perpetual confidentiality.'),
  ('IP Ownership', 'Background IP', 'Each party retains background IP', 'Limited license', 'Assignment of background IP', 'legal', 'high', 'No assignment of pre-existing IP.'),
  ('Data Transfer', 'Cross-border data', 'KSA data residency', 'Approved SCCs with DPA', 'Unrestricted cross-border transfer', 'compliance', 'high', 'Compliance review required.')
) AS v(clause_category, rule_name, preferred_position, fallback_position, unacceptable_position, approval_required_role, severity, guidance)
WHERE NOT EXISTS (
  SELECT 1 FROM playbook_rules pr WHERE pr.playbook_id = 'a1000000-0000-4000-8000-000000000001'::uuid LIMIT 1
);
