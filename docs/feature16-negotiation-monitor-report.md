# Feature 16 — AI Negotiation Monitor Agent

## Summary

Adds a monitored negotiation workflow: simulated/manual email ingest, thread matching, revision detection, proposed immutable versions, three-way comparison (previous / standard template / playbook), bilingual lawyer review packages, human-approved outbound send, rounds, lineage events, and counterparty memory.

## Database

- Migration: [`database/migrations/015_negotiation_monitor.sql`](../database/migrations/015_negotiation_monitor.sql)
- New tables: `negotiation_threads`, `negotiation_emails`, `negotiation_attachments`, `negotiation_rounds`, `negotiation_review_packages`, `legal_playbooks`, `playbook_rules`, `counterparty_profiles`
- `contracts.is_template`, `contracts.template_category`

## Connectors

- [`backend/app/integrations/email/`](../backend/app/integrations/email/): `EmailConnector` ABC, full `SimulatedEmailConnector`, typed `GmailConnector` / `OutlookConnector` skeletons
- Config: `EMAIL_PROVIDER=simulated` (default)

## Matching (priority)

1. External thread id  
2. Reply reference  
3. Specific subject ↔ contract title (never generic subject alone)  
4. Counterparty email + single active thread  
5. Document hash  
6. Manual link / `needs_review`

## Revision detection

- SHA-256 dedupe; text extract via existing `textextract` pipeline  
- Proposed versions: `source=client_revision`, `status=under_review`, `make_current=false` via extended `create_new_version`

## Comparison & playbook

- [`comparison.py`](../backend/app/services/negotiation_monitor/comparison.py): previous diff + heuristic template deviations  
- [`playbook.py`](../backend/app/services/negotiation_monitor/playbook.py): rule mapping (payment days, liability, governing law)  
- LLM synthesis: [`review_package.py`](../backend/app/services/negotiation_monitor/review_package.py) with strict JSON schema + deterministic fallback

## APIs

- `/api/negotiation-monitor/*` — threads, import, analyze, packages, approve/send  
- `/api/playbooks` — read-only playbook  
- `/api/counterparties/{email}/negotiation-memory`

## UI

- `/negotiations/monitor` — inbox list + import from simulated inbox  
- `/negotiations/monitor/[threadId]` — three-column workspace  
- `/playbook` — read-only rules

## Approval & send

- Required approvers derived from package `changes[].required_approver`  
- Send blocked until active approval workflow completes or explicit `override_reason` (audited in `lawyer_edited_json`)  
- No automatic send on analyze/import

## Lineage

15 event types in `MONITOR_LINEAGE_EVENTS`; logged via `log_monitor_event` → `activity_events`

## Tests

New tests under `backend/tests/test_email_*.py`, `test_playbook_deviation.py`, `test_outbound_send.py`, etc.

## Manual demo script

1. Open `/negotiations/monitor` — seeded thread **Vendor MSA — Al-Falak Ltd** (after first API list call).  
2. **Import email** → pick `sim-msg-msa-revision-v2`.  
3. **Analyze** → review package with payment / liability / governing law findings.  
4. Edit AR/EN draft → **Confirm** → **Approve & send** (use override if Finance approval not started).  
5. Contract lineage shows monitor events.

## Known limitations

- Gmail/Outlook not live; no inbox polling  
- Template comparison is heuristic + LLM (not full clause graph)  
- Proposed versions skip full extraction pipeline until promoted current  
- Playbook editor out of scope (read-only UI + SQL seed)
