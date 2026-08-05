-- Feature 7: AI Negotiation Assistant
CREATE TABLE IF NOT EXISTS negotiations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  review_request_id uuid REFERENCES review_requests(id) ON DELETE SET NULL,
  review_comment_id uuid REFERENCES review_comments(id) ON DELETE SET NULL,
  clause_ref text,
  original_clause text,
  reviewer_comment text,
  reviewer_decision text,
  ai_summary text,
  business_impact text,
  legal_impact text,
  risk_level text,
  recommendation text,
  reasoning text,
  counter_clause text,
  counter_clause_ar text,
  pros jsonb,
  cons jsonb,
  status text NOT NULL DEFAULT 'draft',
  edited_by_lawyer boolean NOT NULL DEFAULT false,
  sent_review_request_id uuid REFERENCES review_requests(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_negotiations_contract ON negotiations(contract_id);
CREATE INDEX IF NOT EXISTS idx_negotiations_review ON negotiations(review_request_id);

CREATE TABLE IF NOT EXISTS negotiation_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  negotiation_id uuid NOT NULL REFERENCES negotiations(id) ON DELETE CASCADE,
  author text NOT NULL,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
