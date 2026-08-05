# Feature 7 — AI Negotiation Assistant

## Summary

After a client **rejects** or **requests changes** on a review, the legal team can open the **Negotiation** tab on a contract, run **Analyze with AI** (Prompt B), review structured impact cards, edit counter-clauses, and **Send updated version** (new review link).

## Database

- **Migration `010_negotiation_engine.sql`**
  - `negotiations` — AI output + lawyer edits, linked to contract/review/comment
  - `negotiation_messages` — optional AI/lawyer message log (AI turn stored on analyze)

## Files changed / added

| Area | Path |
|------|------|
| Migration | `database/migrations/010_negotiation_engine.sql` |
| Prompt B | `backend/app/ai/negotiation_prompt.py` |
| Service | `backend/app/services/negotiation.py` |
| Router | `backend/app/routers/negotiation.py` |
| Models | `backend/app/models.py` (`Negotiation`, `NegotiationMessage`) |
| Main | `backend/app/main.py` |
| Frontend | `frontend/components/NegotiationPanel.tsx` |
| Contract UI | `frontend/app/contracts/[id]/page.tsx` (Negotiation tab) |
| API/types/i18n | `frontend/lib/api.ts`, `types.ts`, `i18n.tsx` |
| Tests | `backend/tests/test_negotiation.py` |

## APIs added (Bearer protected)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/negotiation/analyze` | `{ review_id, comment_id? }` → negotiation row |
| GET | `/api/contracts/{id}/negotiations` | `{ negotiations, candidates }` |
| PATCH | `/api/negotiations/{id}` | Lawyer edits |
| POST | `/api/negotiations/{id}/send` | New review request + link + email template |

## Manual testing

1. Run migration: `backend/.venv/bin/python database/migrate.py`
2. Start backend + frontend; open a **ready** contract.
3. **Send for review** → open public link → **Reject** (with reason) or **Request changes** (+ optional clause comment).
4. Contract detail → **Negotiation** tab → **Analyze with AI** (requires `OPENAI_API_KEY`).
5. Approve / edit counter-clause → **Send updated version** → copy new review link.

## Verification results

- `pytest backend/tests -q`: **85 passed** (includes 8 negotiation tests)
- `npx tsc --noEmit` + `npm run build`: OK

## Known limitations

- Single-turn AI per analyze (no chat thread UI; `negotiation_messages` reserved for future).
- Analyze calls OpenAI (not mocked in CI except unit tests with `complete_json` patched).
- Send creates a new review link via existing review service; no SMTP.
- Bilingual counter-clauses can drift if lawyer edits only one language.
- No inline diff view between original and counter clause.
- Candidates appear only for reviews in `rejected` / `changes_requested` status.
