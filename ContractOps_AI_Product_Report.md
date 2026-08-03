# ContractOps AI
**AI-Powered Subcontract Intelligence Platform — Product Report**

> "We don't generate contracts. We manage everything that happens after they're signed." — August 2026

---

## 1. Vision

**Construction companies don't lose money because they don't have contracts. They lose money because they forget what those contracts require.**

ContractOps AI is an AI Contract Operations Manager that continuously monitors subcontract agreements, tracks obligations, prevents penalties, and assists project teams throughout the subcontract lifecycle — from award to close-out. It deliberately ignores owner contracts (e.g., PIF ↔ main contractor), which are heavily lawyered and well managed, and focuses on the internal subcontract network where the operational losses actually occur: electrical, concrete, gypsum, HVAC, tile, steel, labor supply, equipment rental, and finishing.

## 2. The Problem

Validated directly with an Engineering Manager at one of Saudi Arabia's largest real estate companies (multiple PIF projects):

> "We don't have problems with owner contracts." The problems live in the subcontracts: missed obligations, missed notice deadlines, payment-condition confusion, delay penalties, expired bonds and warranties, scope conflicts, flow-down mistakes, late approvals, missing documents — discovered only after they become expensive.

The independent evidence base is stark:

- **Under FIDIC-based contracts (the norm on Vision 2030 project chains), missing a notice window doesn't cost a penalty — it forfeits the entire claim.** The Privy Council confirmed in 2026 that Sub-Clause 20.1 is a hard condition precedent.
- **HKA's Saudi guidance states verbatim that contractors "sabotage their claims by failing to give notice."**
- **KSA EOT claims average 97.2% of planned schedule; payment disputes affect 31.6% of Saudi projects; the Middle East runs the world's costliest construction disputes (~US$82–86M average).**
- **Saudi FIDIC is heavily amended — notice periods vary contract by contract (7/14/21/28 days), which is exactly why manual tracking fails.**

## 3. The Solution

Upload subcontract agreements. The AI reads every contract, extracts every important clause, and then continuously monitors the contract until completion. Instead of storing contracts, the platform actively manages them: obligations become tasks, notice periods become countdowns, deviations become flags, and drafting notices becomes one click — always human-approved.

## 4. Core Features (Full Product)

> Note: this section describes the complete product vision. The 3-day MVP scope is the subset defined in Section 6 — features 5 (Notice Generator), 7 (Playbook Compliance), 9 (Claims Assistant), 11 (Contract Chat), and standalone 12 (Reminder Engine — merged into Time-Bar Guardian) are roadmap or stretch, not MVP.

### 1. AI Contract Reader (bilingual, Hijri-aware)
Upload PDF, Word, or Google Drive documents (via Drive Picker). The AI extracts parties, contract value, start and completion dates, payment terms, notice periods, obligations, deliverables, penalties, governing law, retention, performance bond, and warranty — in Arabic or English, with Hijri dates detected and converted. Every extracted value links to the exact clause in the original contract (click-to-source): trust is proven, not requested.

### 2. AI Obligation Tracker ⭐
Legal clauses become actionable tasks. "Submit shop drawings within 14 days" becomes: Responsible — Aluminum Contractor · Due — 14 days · Status — Pending · Reminder — 3 days before · Penalty — visible if missed. A 150-page contract becomes a project task list.

### 3. Payment Conditions Tracker
Not just milestones — preconditions. "Payment No. 3 requires: Engineer approval, inspection passed, concrete completed. Until all conditions are met, the payment remains blocked."

### 4. Time-Bar Guardian ⭐⭐⭐⭐⭐
The AI reads each contract's own notice periods — 7, 14, 21, or 28 days, never hardcoded, because Saudi FIDIC is heavily amended — and starts countdowns automatically. Missing the notice deadline can mean losing the claim; this is the platform's flagship protection.

### 5. AI Notice Generator
One click: Generate Delay Notice. The AI reads the contract, reads the triggering clause, drafts the notice in Arabic and English, and cites the supporting clause. Always reviewed by a human before sending — decision support, never auto-sent legal action.

### 6. Flow-Down X-Ray ⭐⭐⭐⭐⭐ (hero feature)
Compare the main contract against each subcontract. The AI detects obligations that were not flowed down: "Owner contract: LD = SAR 50,000/day. Subcontract: no LD clause. ⚠ Main contractor carries the full risk alone." No competitor — local or global — was identified offering contract-pair flow-down comparison. GCC law firms actively warn that "back-to-back is not enough."

### 7. Company Playbook Compliance
Every subcontract checked against internal standards in seconds: "Maximum payment period: 30 days. Contract says: 120 days → Not Company Compliant." This answers the customer's second validated pain — slow, manual review of every subcontract before approval.

### 8. Delay & Penalty Monitor
Tracks delay clauses, liquidated damages, extension of time, and notice windows. "Remaining before penalty: 12 days."

### 9. AI Claims Assistant (V2)
User: "Concrete supplier delayed 8 days." The AI checks the contract, delay clauses, notice requirements, and evidence needed — then advises whether a claim is possible and drafts it. Deferred to V2 for legal-accuracy maturity.

### 10. Smart Dashboard
Active contracts, upcoming obligations and payments, contracts near expiry, notice deadlines, high-risk contracts, bonds expiring, retention status, claims status — the commercial manager's morning view.

### 11. AI Contract Chat (bilingual)
"Which subcontract expires next month?" · "أي مقاول باطن ينتهي ضمانه هذا الشهر؟" · "Show contracts with performance bonds expiring this week." Cited answers across the whole portfolio.

### 12. Smart Reminder Engine
Automatic reminders for obligations, payments, bonds, insurance, warranty, notice periods, and contract expiry.

## 5. Competitive Landscape (condensed)

| Player | What it ships | Why it doesn't own our cell |
|---|---|---|
| Signit (KSA, $15M) | CLM + e-signature; generic playbook AI; 700+ orgs | No construction vertical; signature lifecycle, not operational life; future integration target |
| Lexilio (UK → GCC) | FIDIC time-bar + notices + playbook; GCC sales page; claimed Saudi Landbridge deployment | English-only, no Arabic/Hijri; accelerator-stage, unproven delivery — the race is to the Arabic layer |
| Document Crunch (Trimble, ~$250M) | Construction playbook review of subcontracts & flow-downs; 10K+ projects | US-centric, English; no shipped time-bar/notice engine found; no MENA |
| CEMAR / Sypro / FastDraft | Contract-event & deadline workflow (NEC/FIDIC), a decade mature | Both parties must administer in-tool from day one; UK, enterprise, English |
| Procore / Aconex / Textura | Commercial admin, correspondence, payment workflow in GCC | Carry contracts and notices without understanding them; integration targets |
| FirstBit / Tactive / PMWeb / Salis | Arabic construction ERP, billing, tenders, owner-side commitments | No contract intelligence of any kind |

**The open cell, verified across three research rounds: the operational life of the subcontract, in Arabic — AI review + time-bar guardianship + bilingual notices + flow-down analysis + Hijri awareness, at SME-reachable pricing. Lexilio is racing toward it in English; the Arabic layer is the moat it hasn't started.**

## 6. MVP — 3-Day Hackathon (final selected scope)

Build only these, in this order (numbering matches the SRS and team task split):

- **F0. Arabic-First Experience** — cross-cutting: RTL default, AR/EN toggle, dual Hijri/Gregorian dates everywhere, bilingual extraction
- **F1. AI Contract Reader & AI Obligation Tracker** — extraction + click-to-source (the trust foundation; day-one morning: run 4–5 real subcontracts through it and grade honestly before any UI), then clauses become tasks
- **F2. Time-Bar Guardian + Contract Timeline + Smart Reminder System** — countdowns read from each contract's own notice clauses (never hardcoded); timeline strip and in-app reminders are the same data, same code path
- **F3. Payment Conditions Tracker** — "Payment No. 3 requires…" preconditions checklist; blocked until all conditions are met
- **F4. Flow-Down X-Ray** — the hero demo moment
- **F5. Executive Dashboard** — the visual payoff

**Stretch (build only if ahead of schedule):**
- **AI Notice Generator (thin)** — one endpoint + one dialog: bilingual clause-cited draft, human-approved. It was the money moment of demo Beat 3; it is one prompt away once Time-Bar Guardian works.
- **Playbook Compliance (thin)** — five company rules, red/green table; answers the customer's second validated pain. Keep on the roadmap slide regardless so the story stays complete.

## 7. Version 2 Roadmap

- AI Claims Assistant · Payment Intelligence · Bond & Warranty Management
- OCR improvements for scanned Arabic contracts
- Primavera P6, Procore, and Aconex integrations
- Subcontractor performance scoring (the data moat) · Predictive risk engine

## 8. Positioning

> ContractOps AI is not another contract generator or e-signature platform. It is an AI Contract Operations Platform built specifically for Saudi construction companies to manage the operational lifecycle of subcontracts after they are signed — preventing missed obligations, avoiding penalties, protecting claims, and giving complete visibility over every subcontract from award to close-out.

### Prepared answers for the hard questions

- **"Why not Signit?"** — Signit is the signature lifecycle; we're the operational life. Their industry pages don't list construction. FIDIC claims logic, flow-down analysis, and Hijri math are a vertical operations product, not a CLM feature.
- **"Why not Document Crunch?"** — They validated the category at a ~$250M exit — for North America, in English, with no shipped time-bar engine. The Arabic, Hijri-dated, KSA-amended-FIDIC layer is our product, not their roadmap.
- **"Why trust it?"** — Click-to-source on every value; human-approved notices, never auto-sent; and notice periods read from your amended contract, not FIDIC defaults — the exact mistake that kills claims today.

## 9. Conditions Before Demo Day

- **Time-bar engine must read notice periods from the contract — never hardcode.** Difference between flagship and liability.
- **3–5 more interviews with commercial/contracts managers at actual contractors** — the pitch needs one quote from someone who lost money to a missed notice.
- **Demo on curated, clean documents; state the OCR limitation honestly.**

## Sources (Key)

- Full evidence base: Saudi Subcontract AI Competitor & Market Study (companion document, 5-agent research)
- pinsentmasons.com — FIDIC in KSA; KSA FIDIC-based government contract system
- charlesrussellspeechlys.com — Privy Council on FIDIC 20.1; "back-to-back is not enough"
- hka.com — Managing risks and claims in Saudi Arabia; CRUX
- news.trimble.com — Trimble–Document Crunch acquisition
- lexilio.co — Lexilio platform and GCC/MENA page
- signit.sa — Signit product and industries pages
- arcadis.com — Middle East construction disputes
