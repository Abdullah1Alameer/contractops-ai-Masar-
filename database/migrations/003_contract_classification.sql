-- Contract classification gate (Stage 0 before extraction)

ALTER TABLE contracts DROP CONSTRAINT IF EXISTS contracts_status_check;
ALTER TABLE contracts ADD CONSTRAINT contracts_status_check
  CHECK (status IN ('processing','ready','failed','needs_review','unsupported'));

ALTER TABLE contracts
  ADD COLUMN IF NOT EXISTS contract_category text NULL,
  ADD COLUMN IF NOT EXISTS supported boolean NULL,
  ADD COLUMN IF NOT EXISTS classification_confidence numeric(3,2) NULL,
  ADD COLUMN IF NOT EXISTS classification_message text NULL;

UPDATE contracts SET
  contract_category = CASE type WHEN 'main' THEN 'Main Construction Contract'
                                WHEN 'subcontract' THEN 'Subcontract Agreement' END,
  supported = true,
  classification_confidence = 1.00
WHERE contract_category IS NULL AND type IN ('main','subcontract');

ALTER TABLE contracts DROP CONSTRAINT IF EXISTS contracts_type_check;
ALTER TABLE contracts ADD CONSTRAINT contracts_type_check
  CHECK (type IS NULL OR type IN ('main','subcontract'));

CREATE INDEX IF NOT EXISTS idx_contracts_category ON contracts(contract_category);
