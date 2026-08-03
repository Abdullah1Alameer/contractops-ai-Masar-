# ContractOps AI — SRS & Implementation Blueprint
**3-Day Hackathon Build · 4 Developers in Parallel · v1.0**

> Rule of the build: nothing is implemented that does not appear in the demo.
> Contract-first development — the API contract and JSON schemas in this document are frozen after Hour 2 of Day 1.

---

## 0. Scope Trim — Removed for 3 Days

**Do not build:** real authentication (one seeded workspace, one bearer token from env `DEMO_BEARER_TOKEN`) · Google Drive sync/Picker (drag-drop upload only) · OCR/scanned PDFs (text PDFs + DOCX only; scanned files rejected politely; demo runs on 4–5 curated contracts) · WhatsApp/email delivery (Daily Brief and reminders render in-app) · cron/queues (deadlines computed at read time; simulated "today" via demo clock) · multi-tenant, roles, audit logs, settings.

**Merged:** Contract Timeline → a strip on Contract Detail rendered from `deadlines` · Smart Reminders → alerts computed from `deadlines` (same code path as Time-Bar Guardian).

**[STRETCH]** One-click bilingual Notice Draft (single endpoint + one dialog) — Day-3 only.

---

## 1. Stack (fixed — no debates)

- **Frontend:** Next.js 14 + Tailwind + shadcn/ui. Arabic-first: `dir="rtl"` default, AR/EN toggle, all strings in one i18n dictionary (`frontend/lib/i18n.ts`).
- **Backend:** FastAPI (Python 3.11), monolith. `pdfplumber` (PDF text), `python-docx` (DOCX), `hijri-converter` (deterministic Hijri↔Gregorian — **never** the LLM).
- **DB/Storage:** Postgres + file storage on Supabase.
- **AI:** Claude API (claude-sonnet), structured JSON, temperature 0. All prompts live in `backend/app/ai/`.
- **Repo:** monorepo; each developer owns folders nobody else touches (§9).

---

## 2. Database Schema (frozen Day 1 Hour 2)

```sql
contracts
  id uuid PK · title text · type enum(main, subcontract)
  parent_main_contract_id uuid FK->contracts NULL   -- links sub to its main
  party_a text · party_b text · value_sar numeric NULL
  start_date date · end_date date · governing_law text
  retention_pct numeric NULL · bond_expiry date NULL · warranty_end date NULL
  language enum(ar,en,mixed) · calendar enum(gregorian,hijri,mixed)
  status enum(processing,ready,failed) · file_url text · raw_text text
  created_at timestamptz            INDEX(type), INDEX(parent_main_contract_id)

clauses            -- every extracted value points here (click-to-source)
  id uuid PK · contract_id FK · clause_ref text        -- e.g. '20.1'
  quote text · page int · char_start int · char_end int      INDEX(contract_id)

extractions        -- field-level results with confidence
  id uuid PK · contract_id FK · field_name text · value_json jsonb
  confidence numeric(3,2) · clause_id FK->clauses NULL
  status enum(auto,verified,edited)        UNIQUE(contract_id, field_name)

obligations
  id uuid PK · contract_id FK · description text · responsible_party text
  due_date date NULL · penalty_text text NULL · reminder_days_before int DEFAULT 3
  status enum(pending,done,overdue) · source_clause_id FK->clauses
  INDEX(contract_id), INDEX(due_date)

deadlines          -- the Time-Bar Guardian's table
  id uuid PK · contract_id FK
  type enum(notice_window,bond_expiry,warranty_end,payment,contract_expiry)
  label text · notice_period_days int NULL   -- read from the contract, never assumed
  deadline_date date · severity enum(info,warning,critical)
  source_clause_id FK->clauses · triggered_by_event_id FK->events NULL
  INDEX(contract_id), INDEX(deadline_date)

events             -- demo trigger: "delay event logged"
  id uuid PK · contract_id FK · type text · description text · event_date date

payment_milestones
  id uuid PK · contract_id FK · seq int · label text · amount_sar numeric NULL
  preconditions jsonb    -- [{text, met bool}] · status enum(blocked,claimable,paid)
  source_clause_id FK->clauses        UNIQUE(contract_id, seq)

flowdown_findings
  id uuid PK · main_contract_id FK · subcontract_id FK
  obligation_summary text · status enum(mirrored,partial,missing)
  main_clause_id FK->clauses · sub_clause_id FK->clauses NULL
  risk_note text · severity enum(low,medium,high)
  INDEX(main_contract_id, subcontract_id)

demo_state         -- simulated clock, one row
  id int PK default 1 · today date not null
```

---

## 3. API Surface (frontend codes against mocks from Hour 2)

```
POST  /api/contracts                 multipart {file, type, parent_main_contract_id?}
                                     -> 201 {id, status:'processing'} | 400 unsupported/scanned
GET   /api/contracts                 -> 200 [{id,title,type,party_b,value_sar,status,risk_counts}]
GET   /api/contracts/{id}            -> 200 full record + extractions[] + referenced clauses
POST  /api/contracts/{id}/extract    idempotent; runs AI pipeline -> 200 | 502 ai_failed
GET   /api/contracts/{id}/obligations-> 200 [{...obligation, source:{clause_ref,quote,page}}]
PATCH /api/obligations/{id}          {status} -> 200
GET   /api/contracts/{id}/deadlines  -> 200 [{...deadline, days_remaining}]   (uses demo today)
GET   /api/contracts/{id}/milestones -> 200 milestones with preconditions
PATCH /api/milestones/{id}           {precondition_index, met} -> 200 recomputed status
POST  /api/contracts/{id}/events     {type, description, event_date}
                                     -> 201 event + newly created notice_window deadline
POST  /api/flowdown                  {main_contract_id, subcontract_id} -> 200 findings[]
GET   /api/dashboard                 -> 200 aggregates (§5 F5)
GET   /api/reminders                 -> 200 deadlines/obligations within reminder window
GET   /api/demo/today · POST /api/demo/today {date}          -- simulated clock
[STRETCH] POST /api/deadlines/{id}/notice-draft
          -> {subject_ar, body_ar, subject_en, body_en, cited_clauses[]}

Status codes: 200/201 · 400 validation · 404 · 422 unprocessable file
              502 AI failure {error, retryable:true}
Error body:   {error: string, detail?: string}
Auth: constant bearer token (env DEMO_BEARER_TOKEN) on every endpoint.
```

---

## 4. AI Module (critical path)

### 4.1 Pipeline
```
upload -> pdfplumber/python-docx text extraction (backend)
       -> ai.extract_contract(raw_text)         [Prompt A]
       -> validate vs JSON Schema; confidence < 0.70 => status='needs_review'
       -> backend writes contracts/clauses/extractions/obligations/deadlines/milestones
ai.flowdown_compare(main_text, sub_text)        [Prompt B] -> flowdown_findings
[STRETCH] ai.draft_notice(excerpts, event, deadline)   [Prompt C]
```

### 4.2 Prompt A — extract_contract output schema
```json
{ "language": "ar|en|mixed", "calendar": "gregorian|hijri|mixed",
  "parties": {"a":"","b":""}, "value_sar": 0, "start_date":"", "end_date":"",
  "governing_law":"", "retention_pct":0, "bond_expiry":"", "warranty_end":"",
  "notice_periods":[{"purpose":"","days":0,"clause_ref":"","quote":"","page":0}],
  "obligations":[{"description":"","responsible_party":"","due_in_days_or_date":"",
                  "penalty_text":"","clause_ref":"","quote":"","page":0}],
  "payment_milestones":[{"seq":1,"label":"","amount_sar":0,"preconditions":[],
                         "clause_ref":"","quote":"","page":0}],
  "penalties":[{"type":"","rate":"","cap":"","clause_ref":"","quote":"","page":0}] }
```
- Every field: `{value, confidence 0..1, clause_ref, quote, page}`.
- Dates: return **raw string + detected calendar**; backend converts Hijri via `hijri-converter`.
- Prompt rules: answer ONLY from the text · null + confidence 0 when absent · never invent clause refs · quotes must be **verbatim substrings** (backend verifies by search).

### 4.3 Failure handling
- Malformed JSON → one repair retry; second failure → `contract.status='failed'`, 502 retryable.
- Quote not found verbatim → drop clause link, keep value, force confidence ≤ 0.5, flag "needs review". **Click-to-source must never highlight wrong text.**
- **Day-1 morning gate:** run the 4–5 curated contracts through Prompt A and hand-grade (parties, value, dates, notice periods, LDs). If notice-period accuracy < 100%, fixing the prompt outranks every other task.

---

## 5. Feature Specs

### F0 — Arabic-First (Dev A, cross-cutting)
RTL default · AR/EN toggle persists · dual dates everywhere via `<DualDate/>` · Arabic renders in PDF viewer. Edge: mixed-language contracts ("mixed" chip) · Arabic numerals ٠١٢٣ normalized in backend.
**Accept:** every page usable in RTL · toggle without reload · dual dates on every deadline/obligation.

### F1 — AI Contract Reader & Obligation Tracker (Dev C + B + A)
Upload (≤20MB, .pdf/.docx with text layer) → extract → persist → register + detail + click-to-source + confidence chips (<0.70 = "review" badge) → obligation status PATCH.
**Accept:** upload→ready ≤60s · 100% of values open their source quote · Arabic contract fully extracted.
Edge: duplicate upload (warn, allow) · zero obligations (empty state) · >20MB reject · corrupted 422.

### F2 — Time-Bar Guardian + Timeline + Reminders (Dev B + D + A)
- `deadline_date = event_date + notice_period_days` **(from extraction — zero hardcoded durations, grep-checkable)**.
- `days_remaining = deadline_date − demo_today`. Severity: >14 info · 3–14 warning · <3 critical; negative ⇒ `time_barred: true` (red "time-barred" state — keep it, it's a demo moment).
- Timeline strip = deadlines on an axis. Reminders = deadlines/obligations within window, in-app bell.
- Log-event dialog → new countdown appears immediately, citing clause ("14 days per 20.1 as amended").
**Accept:** event creates correctly-cited countdown · moving demo-today changes severities live · no notice clause ⇒ "none found — review contract".
**[STRETCH]** Notice Draft button on notice_window deadlines → bilingual draft dialog, cited clauses, "Approve & copy" (no sending).

### F3 — Payment Conditions Tracker (Dev B + A, thin)
Milestones from Prompt A · checklist UI · PATCH precondition → recompute (all met ⇒ claimable; `paid` only from `claimable`). Empty preconditions ⇒ claimable with note. Amounts as % ⇒ store both.
**Accept:** ticking last precondition flips status instantly · every milestone cites its clause.

### F4 — Flow-Down X-Ray (Dev C + A) — HERO
Pair selector (main + subs via `parent_main_contract_id`) → Prompt B → findings table (mirrored ✓ / partial ⚠ / missing ✗), each row cites main clause + sub clause (or "absent"), severity sort, summary banner.
**Accept:** seeded demo pair yields the LD gap ("SAR 50,000/day not mirrored — you carry it alone") with both sources clickable · ≤90s.
Edge: sub with no linked main (disabled + hint) · both Arabic · flowed down but weaker ⇒ `partial` + risk_note.

### F5 — Executive Dashboard (Dev D + A)
`GET /api/dashboard` → `{contracts_total, by_status, sar_under_management, deadlines_next_30d[], critical_count, obligations_overdue, bonds_expiring_60d, flowdown_high_risk_count, daily_brief:{generated_ar, generated_en}}`. Brief composed by **template** from aggregates (AI-phrased = stretch). All rows deep-link.
**Accept:** loads ≤2s · every number traceable · brief reads correctly in Arabic.

---

## 6. Dependency Diagram
```
Upload (F1)
  └─ Text extraction (backend)
       └─ Prompt A extraction (Dev C)      <== CRITICAL PATH
            ├─ contracts/clauses/extractions → Contract Detail + click-to-source
            ├─ obligations                   → Obligation Tracker (F1)
            ├─ notice_periods → deadlines    → Time-Bar Guardian (F2)
            │                    ├─ Timeline strip (F2)
            │                    ├─ Alerts/reminders (F2)
            │                    └─ [STRETCH] Notice draft
            └─ payment_milestones            → Payment Conditions (F3)
Prompt B (needs TWO extracted contracts)     → Flow-Down X-Ray (F4)
All tables ──────────────────────────────────→ Dashboard (F5)
```

## 7. API Communication
```
Next.js frontend --HTTP/JSON--> FastAPI backend --SQL--> Postgres (Supabase)
                                    │  └--files--> Supabase Storage
                                    └--HTTPS--> Claude API (ai/ module only)
Frontend NEVER calls Claude directly. Frontend uses mock server (openapi.json)
until real endpoints land.
```

## 8. 4-Developer Split (no shared files = no merge conflicts)
- **Dev A — Frontend** (`frontend/`): D1 shell+RTL/i18n+upload+list vs mocks · D2 contract detail (PDF pane, click-to-source, obligations, deadlines, milestones) · D3 flow-down, dashboard, alerts, polish.
- **Dev B — Backend core** (`backend/app/` except `ai/`): D1 H0–2 freeze schema+openapi+mocks, then upload/text/CRUD · D2 deadlines engine + hijri + events + milestones · D3 seed script, demo clock, hardening.
- **Dev C — AI** (`backend/app/ai/` + `shared/schemas/`): D1 am Prompt A gate (GO/NO-GO) · D1 pm validation+quote verification · D2 Prompt B tuning on demo pair · D3 stretch notice draft, regression run.
- **Dev D — Integration & data** (`database/`, dashboard hooks, demo assets): D1 Supabase+storage+migrations+curate 4–5 demo contracts (one Arabic, one main+sub pair) · D2 dashboard aggregates + alerts · D3 demo run-throughs ×3, seed reset.

## 9. Folder Structure
```
contractops/
  frontend/           # Dev A — Next.js
    app/ (upload, contracts/[id], flowdown, dashboard)
    components/ (DualDate, ConfidenceChip, PdfPane, CountdownBadge, ...)
    lib/i18n.ts  lib/api.ts
  backend/            # Dev B
    app/main.py  routers/  services/ (deadlines.py, hijri.py, textextract.py)
    app/ai/           # Dev C — prompts.py, schemas.py, client.py, verify.py
  shared/             # frozen: openapi.json + JSON schemas + i18n keys
  database/           # Dev D — migrations/, seed/, demo_contracts/
  docs/               # this SRS, demo script, grading checklist
```

## 10. Day Plan
```
Day 1  H0–2  ALL: freeze schema, openapi.json, JSON schemas, mock server
       H2–4  Dev C: Prompt A gate on real contracts   (GO/NO-GO before lunch)
       pm    Upload → extract → persist → contract detail visible end-to-end
Day 2  am    Deadlines engine + events + countdowns (F2) · milestones (F3)
       pm    Flow-Down X-Ray (F4) working on the demo pair
Day 3  am    Dashboard (F5) + alerts + Arabic polish
       pm    [STRETCH] notice draft · seed reset · demo rehearsal ×3 (incl. Arabic Q)
```
**Definition of done, every feature:** works on the seeded demo data via the demo script, in Arabic, with click-to-source — not "works on my machine".
