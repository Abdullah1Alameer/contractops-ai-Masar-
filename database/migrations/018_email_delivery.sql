-- Golden path email delivery persistence and reproducible public tokens.

ALTER TABLE review_requests
  ALTER COLUMN token DROP NOT NULL,
  ADD COLUMN IF NOT EXISTS token_nonce text,
  ADD COLUMN IF NOT EXISTS token_hash text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_review_requests_token_hash
  ON review_requests(token_hash)
  WHERE token_hash IS NOT NULL;

ALTER TABLE signature_signers
  ADD COLUMN IF NOT EXISTS token_nonce text;

CREATE TABLE IF NOT EXISTS outbound_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_type text NOT NULL,
  recipient text NOT NULL,
  subject text NOT NULL,
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  review_request_id uuid REFERENCES review_requests(id) ON DELETE CASCADE,
  signature_request_id uuid REFERENCES signature_requests(id) ON DELETE CASCADE,
  signer_id uuid REFERENCES signature_signers(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')),
  attempt_count int NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  provider_message_id text,
  safe_error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  failed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_outbound_messages_contract_created
  ON outbound_messages(contract_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_review_created
  ON outbound_messages(review_request_id, created_at DESC)
  WHERE review_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outbound_messages_signature_created
  ON outbound_messages(signature_request_id, signer_id, created_at DESC)
  WHERE signature_request_id IS NOT NULL;
