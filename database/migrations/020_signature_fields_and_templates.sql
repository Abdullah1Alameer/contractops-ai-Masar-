-- Bug fixes: (1) signature field placement inside the actual document,
-- (2) real, backend-backed contract templates for "Use Template".
-- See docs/signature-placement-and-template-flow-report.md.

-- ---------------------------------------------------------------------
-- Signature fields: one row per placed field (signature/initials/name/
-- date) for a signer within a signature request. Coordinates are
-- normalized (0..1) relative to the PDF page identified by page_number,
-- so they render correctly regardless of on-screen zoom/DPI.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signature_fields (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signature_request_id uuid NOT NULL REFERENCES signature_requests(id) ON DELETE CASCADE,
  signer_id uuid NOT NULL REFERENCES signature_signers(id) ON DELETE CASCADE,
  version_id uuid REFERENCES contract_versions(id) ON DELETE SET NULL,
  page_number integer NOT NULL,
  x numeric(7,5) NOT NULL,
  y numeric(7,5) NOT NULL,
  width numeric(7,5) NOT NULL,
  height numeric(7,5) NOT NULL,
  field_type text NOT NULL DEFAULT 'signature'
    CHECK (field_type IN ('signature', 'initials', 'name', 'date')),
  required boolean NOT NULL DEFAULT true,
  ai_suggested boolean NOT NULL DEFAULT false,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signature_fields_request ON signature_fields(signature_request_id);
CREATE INDEX IF NOT EXISTS idx_signature_fields_signer ON signature_fields(signer_id);

-- ---------------------------------------------------------------------
-- Contract templates: real records backing "Use Template", replacing the
-- frontend-only seed list that silently redirected to /upload.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contract_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key text UNIQUE NOT NULL,
  title_en text NOT NULL,
  title_ar text NOT NULL,
  category text,
  language text NOT NULL DEFAULT 'both',
  industry text,
  description_en text,
  description_ar text,
  variables jsonb NOT NULL DEFAULT '[]',
  clauses jsonb NOT NULL DEFAULT '[]',
  usage_count integer NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE contracts
  ADD COLUMN IF NOT EXISTS template_id uuid REFERENCES contract_templates(id) ON DELETE SET NULL;

INSERT INTO contract_templates
  (key, title_en, title_ar, category, language, industry, description_en, description_ar, variables, clauses, usage_count)
VALUES
(
  'msa', 'Master Service Agreement', 'اتفاقية خدمات رئيسية', 'Commercial', 'both', 'Technology',
  'A master services agreement establishing the general commercial and legal terms governing an ongoing services relationship between two parties.',
  'اتفاقية خدمات رئيسية تحدد الشروط التجارية والقانونية العامة الناظمة لعلاقة خدمات مستمرة بين طرفين.',
  $vars${
    "fields": [
      {"key": "party_a", "label_en": "Service Provider", "label_ar": "مقدم الخدمة", "type": "text", "required": true},
      {"key": "party_b", "label_en": "Client", "label_ar": "العميل", "type": "text", "required": true},
      {"key": "effective_date", "label_en": "Effective Date", "label_ar": "تاريخ السريان", "type": "date", "required": true},
      {"key": "term_months", "label_en": "Term (months)", "label_ar": "المدة (بالأشهر)", "type": "number", "required": true},
      {"key": "governing_law", "label_en": "Governing Law", "label_ar": "القانون الحاكم", "type": "text", "required": true},
      {"key": "service_description", "label_en": "Service Description", "label_ar": "وصف الخدمة", "type": "textarea", "required": true},
      {"key": "contract_value", "label_en": "Contract Value (SAR)", "label_ar": "قيمة العقد (ريال)", "type": "number", "required": false}
    ]
  }$vars$::jsonb,
  $cls${
    "sections": [
      {"title_en": "Scope of Services", "title_ar": "نطاق الخدمات", "body_en": "{{party_a}} shall provide the following services to {{party_b}}: {{service_description}}.", "body_ar": "يقدم {{party_a}} الخدمات التالية إلى {{party_b}}: {{service_description}}."},
      {"title_en": "Term", "title_ar": "المدة", "body_en": "This Agreement is effective as of {{effective_date}} and continues for {{term_months}} months unless terminated earlier in accordance with its terms.", "body_ar": "يسري هذا الاتفاق اعتبارًا من {{effective_date}} ويستمر لمدة {{term_months}} شهرًا ما لم يُنهَ قبل ذلك وفقًا لأحكامه."},
      {"title_en": "Fees", "title_ar": "الرسوم", "body_en": "The total contract value is SAR {{contract_value}}, payable per the schedule agreed by the parties.", "body_ar": "تبلغ القيمة الإجمالية للعقد {{contract_value}} ريال سعودي، تُدفع وفق الجدول المتفق عليه بين الطرفين."},
      {"title_en": "Confidentiality", "title_ar": "السرية", "body_en": "Each party shall keep confidential all non-public information disclosed by the other party in connection with this Agreement.", "body_ar": "يلتزم كل طرف بالحفاظ على سرية جميع المعلومات غير العلنية التي يفصح عنها الطرف الآخر فيما يتعلق بهذا الاتفاق."},
      {"title_en": "Termination", "title_ar": "الإنهاء", "body_en": "Either party may terminate this Agreement for material breach not cured within thirty (30) days of written notice.", "body_ar": "يجوز لأي من الطرفين إنهاء هذا الاتفاق في حال الإخلال الجوهري الذي لا يُعالَج خلال ثلاثين (30) يومًا من الإشعار الكتابي."},
      {"title_en": "Governing Law", "title_ar": "القانون الحاكم", "body_en": "This Agreement is governed by the laws of {{governing_law}}.", "body_ar": "يخضع هذا الاتفاق لقوانين {{governing_law}}."}
    ]
  }$cls$::jsonb,
  42
),
(
  'nda', 'Mutual NDA', 'اتفاقية عدم إفصاح متبادلة', 'Legal', 'both', 'All sectors',
  'A mutual non-disclosure agreement protecting confidential information exchanged between two parties during discussions or collaboration.',
  'اتفاقية عدم إفصاح متبادلة تحمي المعلومات السرية المتبادلة بين طرفين أثناء المناقشات أو التعاون.',
  $vars${
    "fields": [
      {"key": "party_a", "label_en": "Disclosing/Receiving Party A", "label_ar": "الطرف الأول", "type": "text", "required": true},
      {"key": "party_b", "label_en": "Disclosing/Receiving Party B", "label_ar": "الطرف الثاني", "type": "text", "required": true},
      {"key": "effective_date", "label_en": "Effective Date", "label_ar": "تاريخ السريان", "type": "date", "required": true},
      {"key": "term_months", "label_en": "Confidentiality Term (months)", "label_ar": "مدة السرية (بالأشهر)", "type": "number", "required": true},
      {"key": "governing_law", "label_en": "Governing Law", "label_ar": "القانون الحاكم", "type": "text", "required": true}
    ]
  }$vars$::jsonb,
  $cls${
    "sections": [
      {"title_en": "Definition of Confidential Information", "title_ar": "تعريف المعلومات السرية", "body_en": "Confidential Information means any non-public information disclosed by {{party_a}} or {{party_b}} in connection with their discussions, whether oral or written.", "body_ar": "تعني المعلومات السرية أي معلومات غير علنية يفصح عنها {{party_a}} أو {{party_b}} فيما يتعلق بمناقشاتهما، سواء شفهيًا أو كتابيًا."},
      {"title_en": "Obligations", "title_ar": "الالتزامات", "body_en": "Each party shall use the other's Confidential Information solely to evaluate a potential relationship and shall not disclose it to third parties.", "body_ar": "يلتزم كل طرف باستخدام المعلومات السرية للطرف الآخر فقط لتقييم علاقة محتملة، ويمتنع عن الإفصاح عنها لأطراف ثالثة."},
      {"title_en": "Term", "title_ar": "المدة", "body_en": "This Agreement is effective as of {{effective_date}} and the confidentiality obligations survive for {{term_months}} months thereafter.", "body_ar": "يسري هذا الاتفاق اعتبارًا من {{effective_date}} وتستمر التزامات السرية لمدة {{term_months}} شهرًا بعد ذلك."},
      {"title_en": "Governing Law", "title_ar": "القانون الحاكم", "body_en": "This Agreement is governed by the laws of {{governing_law}}.", "body_ar": "يخضع هذا الاتفاق لقوانين {{governing_law}}."}
    ]
  }$cls$::jsonb,
  88
),
(
  'sow', 'Statement of Work', 'بيان نطاق العمل', 'Delivery', 'en', 'Professional services',
  'A statement of work defining the specific deliverables, timeline, and acceptance criteria for a discrete engagement under a master agreement.',
  'بيان نطاق عمل يحدد المخرجات والجدول الزمني ومعايير القبول لمهمة محددة بموجب اتفاقية رئيسية.',
  $vars${
    "fields": [
      {"key": "party_a", "label_en": "Service Provider", "label_ar": "مقدم الخدمة", "type": "text", "required": true},
      {"key": "party_b", "label_en": "Client", "label_ar": "العميل", "type": "text", "required": true},
      {"key": "project_name", "label_en": "Project Name", "label_ar": "اسم المشروع", "type": "text", "required": true},
      {"key": "effective_date", "label_en": "Start Date", "label_ar": "تاريخ البدء", "type": "date", "required": true},
      {"key": "deliverables", "label_en": "Deliverables", "label_ar": "المخرجات", "type": "textarea", "required": true},
      {"key": "contract_value", "label_en": "Contract Value (SAR)", "label_ar": "قيمة العقد (ريال)", "type": "number", "required": false}
    ]
  }$vars$::jsonb,
  $cls${
    "sections": [
      {"title_en": "Scope", "title_ar": "النطاق", "body_en": "This Statement of Work covers the project \"{{project_name}}\" performed by {{party_a}} for {{party_b}}, starting {{effective_date}}.", "body_ar": "يغطي بيان نطاق العمل هذا مشروع \"{{project_name}}\" الذي ينفذه {{party_a}} لصالح {{party_b}}، ابتداءً من {{effective_date}}."},
      {"title_en": "Deliverables", "title_ar": "المخرجات", "body_en": "The deliverables under this engagement are: {{deliverables}}.", "body_ar": "تتمثل المخرجات بموجب هذه المهمة في: {{deliverables}}."},
      {"title_en": "Fees", "title_ar": "الرسوم", "body_en": "The total value of this engagement is SAR {{contract_value}}.", "body_ar": "تبلغ القيمة الإجمالية لهذه المهمة {{contract_value}} ريال سعودي."},
      {"title_en": "Acceptance", "title_ar": "القبول", "body_en": "Deliverables are deemed accepted unless {{party_b}} raises written objections within ten (10) business days of delivery.", "body_ar": "تُعتبر المخرجات مقبولة ما لم يقدم {{party_b}} اعتراضات كتابية خلال عشرة (10) أيام عمل من التسليم."}
    ]
  }$cls$::jsonb,
  31
),
(
  'vendor', 'Vendor Agreement', 'اتفاقية مورّد', 'Procurement', 'ar', 'Retail',
  'A vendor agreement governing the supply of goods or services, including pricing, delivery, and warranty terms.',
  'اتفاقية مورّد تنظم توريد السلع أو الخدمات، بما في ذلك التسعير والتسليم وشروط الضمان.',
  $vars${
    "fields": [
      {"key": "party_a", "label_en": "Buyer", "label_ar": "المشتري", "type": "text", "required": true},
      {"key": "party_b", "label_en": "Vendor", "label_ar": "المورّد", "type": "text", "required": true},
      {"key": "effective_date", "label_en": "Effective Date", "label_ar": "تاريخ السريان", "type": "date", "required": true},
      {"key": "governing_law", "label_en": "Governing Law", "label_ar": "القانون الحاكم", "type": "text", "required": true},
      {"key": "contract_value", "label_en": "Contract Value (SAR)", "label_ar": "قيمة العقد (ريال)", "type": "number", "required": false},
      {"key": "payment_terms", "label_en": "Payment Terms", "label_ar": "شروط الدفع", "type": "text", "required": true}
    ]
  }$vars$::jsonb,
  $cls${
    "sections": [
      {"title_en": "Supply Terms", "title_ar": "شروط التوريد", "body_en": "{{party_b}} shall supply goods/services to {{party_a}} as agreed, effective {{effective_date}}.", "body_ar": "يلتزم {{party_b}} بتوريد السلع/الخدمات إلى {{party_a}} وفق ما يُتفق عليه، اعتبارًا من {{effective_date}}."},
      {"title_en": "Pricing and Payment", "title_ar": "التسعير والدفع", "body_en": "The total contract value is SAR {{contract_value}}, payable under the following terms: {{payment_terms}}.", "body_ar": "تبلغ القيمة الإجمالية للعقد {{contract_value}} ريال سعودي، وتُدفع وفق الشروط التالية: {{payment_terms}}."},
      {"title_en": "Warranty", "title_ar": "الضمان", "body_en": "{{party_b}} warrants that all goods/services conform to the specifications agreed with {{party_a}}.", "body_ar": "يضمن {{party_b}} مطابقة جميع السلع/الخدمات للمواصفات المتفق عليها مع {{party_a}}."},
      {"title_en": "Governing Law", "title_ar": "القانون الحاكم", "body_en": "This Agreement is governed by the laws of {{governing_law}}.", "body_ar": "يخضع هذا الاتفاق لقوانين {{governing_law}}."}
    ]
  }$cls$::jsonb,
  19
)
ON CONFLICT (key) DO NOTHING;
