-- F4 bilingual — store explanation + recommendation in both AR and EN
ALTER TABLE flowdown_findings
  ADD COLUMN IF NOT EXISTS explanation_ar text,
  ADD COLUMN IF NOT EXISTS explanation_en text,
  ADD COLUMN IF NOT EXISTS recommendation_ar text,
  ADD COLUMN IF NOT EXISTS recommendation_en text;
