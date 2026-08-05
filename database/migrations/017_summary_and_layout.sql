-- Bilingual executive summary + page layout geometry for PDF viewer / citations

ALTER TABLE contracts ADD COLUMN IF NOT EXISTS page_layout JSONB;

CREATE TABLE IF NOT EXISTS contract_summaries (
  contract_id UUID PRIMARY KEY REFERENCES contracts(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'not_generated',
  summary_ar JSONB,
  summary_en JSONB,
  error_code TEXT,
  error_detail TEXT,
  model TEXT,
  prompt_version TEXT,
  source_hash TEXT,
  generated_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contract_summaries_status ON contract_summaries (status);
