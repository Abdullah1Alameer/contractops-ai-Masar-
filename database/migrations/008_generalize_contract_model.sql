-- Generalize contract relationship (parent / child / standalone)
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS relationship_type text;

UPDATE contracts SET relationship_type = 'parent' WHERE type = 'main' AND relationship_type IS NULL;
UPDATE contracts SET relationship_type = 'child' WHERE type = 'subcontract' AND relationship_type IS NULL;
UPDATE contracts SET relationship_type = 'standalone' WHERE relationship_type IS NULL;
