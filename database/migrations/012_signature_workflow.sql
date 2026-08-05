-- Feature 9: Digital Signature Workflow

CREATE TABLE IF NOT EXISTS signature_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  provider text NOT NULL DEFAULT 'simulated',
  external_id text,
  status text NOT NULL DEFAULT 'draft',
  created_by text,
  subject text NOT NULL,
  message text,
  signing_order_enabled boolean NOT NULL DEFAULT true,
  expires_at timestamptz NOT NULL,
  sent_at timestamptz,
  completed_at timestamptz,
  declined_at timestamptz,
  decline_reason text,
  original_file_url text,
  signed_file_url text,
  certificate_file_url text,
  original_hash text,
  signed_hash text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signature_requests_contract ON signature_requests(contract_id);
CREATE INDEX IF NOT EXISTS idx_signature_requests_status ON signature_requests(status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_signature_requests_one_active
  ON signature_requests (contract_id)
  WHERE status IN ('draft', 'created', 'sent', 'viewed', 'partially_signed');

CREATE TABLE IF NOT EXISTS signature_signers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signature_request_id uuid NOT NULL REFERENCES signature_requests(id) ON DELETE CASCADE,
  signer_order int NOT NULL,
  name text NOT NULL,
  email text NOT NULL,
  role text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'waiting',
  opened_at timestamptz,
  signed_at timestamptz,
  declined_at timestamptz,
  decline_reason text,
  signature_type text,
  signature_value_url text,
  consent_text text,
  ip_address text,
  user_agent text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(signature_request_id, signer_order)
);

CREATE INDEX IF NOT EXISTS idx_signature_signers_request ON signature_signers(signature_request_id);
CREATE INDEX IF NOT EXISTS idx_signature_signers_token_hash ON signature_signers(token_hash);

CREATE TABLE IF NOT EXISTS signature_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signature_request_id uuid NOT NULL REFERENCES signature_requests(id) ON DELETE CASCADE,
  signer_id uuid REFERENCES signature_signers(id) ON DELETE SET NULL,
  actor text,
  action text NOT NULL,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signature_events_request ON signature_events(signature_request_id);
