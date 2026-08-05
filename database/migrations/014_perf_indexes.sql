-- Feature 15: performance indexes (idempotent)

CREATE INDEX IF NOT EXISTS idx_contracts_stage ON contracts(stage);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contract_versions_contract_id ON contract_versions(contract_id);
CREATE INDEX IF NOT EXISTS idx_review_requests_contract_id ON review_requests(contract_id);
CREATE INDEX IF NOT EXISTS idx_review_requests_status ON review_requests(status);
CREATE INDEX IF NOT EXISTS idx_negotiations_contract_id ON negotiations(contract_id);
CREATE INDEX IF NOT EXISTS idx_approval_workflows_contract_id ON approval_workflows(contract_id);
CREATE INDEX IF NOT EXISTS idx_signature_requests_contract_id ON signature_requests(contract_id);
CREATE INDEX IF NOT EXISTS idx_activity_events_contract_id ON activity_events(contract_id);
CREATE INDEX IF NOT EXISTS idx_activity_events_contract_created ON activity_events(contract_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deadlines_contract_id ON deadlines(contract_id);
CREATE INDEX IF NOT EXISTS idx_payment_milestones_contract_id ON payment_milestones(contract_id);
