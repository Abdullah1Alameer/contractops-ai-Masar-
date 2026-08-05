-- Feature 6: Client Review Portal
CREATE TABLE IF NOT EXISTS review_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  token text NOT NULL UNIQUE,
  recipient_name text NOT NULL,
  recipient_email text NOT NULL,
  sender_name text,
  sender_email text,
  message text,
  status text NOT NULL DEFAULT 'sent',
  expires_at timestamptz NOT NULL,
  opened_at timestamptz,
  responded_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_review_requests_contract ON review_requests(contract_id);

CREATE TABLE IF NOT EXISTS review_comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_request_id uuid NOT NULL REFERENCES review_requests(id) ON DELETE CASCADE,
  clause_ref text,
  page int,
  comment text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_responses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_request_id uuid NOT NULL UNIQUE REFERENCES review_requests(id) ON DELETE CASCADE,
  decision text NOT NULL,
  overall_comment text,
  created_at timestamptz NOT NULL DEFAULT now()
);
