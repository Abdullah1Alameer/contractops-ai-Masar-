# Feature 6 — Client Review Portal

## Summary

Secure token-based external review workflow: internal users send a link; clients open `/review/{token}` without login, read AI dossier, comment, and approve / reject / request changes.

## Database

- **Migration `009_client_review_portal.sql`**
  - `review_requests` — token, recipient, sender, status, expiry, timestamps
  - `review_comments` — clause-level comments
  - `review_responses` — one decision per request (unique on `review_request_id`)

## Backend files

| File | Role |
|------|------|
| `backend/app/models.py` | `ReviewRequest`, `ReviewComment`, `ReviewResponse` |
| `backend/app/services/reviews.py` | Token, dossier, email template, decisions, comments |
| `backend/app/routers/reviews_internal.py` | Protected: send, contract history, dashboard summary |
| `backend/app/routers/reviews_public.py` | Public: GET review, approve/reject/changes/comment |
| `backend/app/main.py` | Router registration (public routes without bearer) |
| `backend/app/config.py` | `REVIEW_BASE_URL` (default `http://localhost:3000`) |

## APIs

**Protected (Bearer `DEMO_TOKEN`):**

- `POST /api/contracts/{id}/review/send`
- `GET /api/contracts/{id}/reviews`
- `GET /api/reviews/summary`

**Public (token only):**

- `GET /api/review/{token}`
- `POST /api/review/{token}/approve`
- `POST /api/review/{token}/reject` — `{ reason }`
- `POST /api/review/{token}/request-changes` — `{ general_comment }`
- `POST /api/review/{token}/comment` — `{ comment, clause_ref?, page? }`

Send response includes `review_link` and `email: { subject, body, review_link }` (no SMTP).

## Frontend

| Path / component | Purpose |
|------------------|---------|
| `frontend/app/review/[token]/page.tsx` | Public review portal |
| `frontend/components/SendForReviewDialog.tsx` | Create link + email preview |
| `frontend/components/ReviewHistoryPanel.tsx` | Contract review history |
| `frontend/app/contracts/[id]/page.tsx` | Send button + Review tab |
| `frontend/app/dashboard/page.tsx` | Contract review status section |
| `frontend/lib/api.ts` | `publicApi*` + review helpers |
| `frontend/lib/types.ts` | Review types |
| `frontend/lib/i18n.tsx` | `review.*` AR/EN keys |

## Tests

- `backend/tests/test_reviews.py` — 8 service-level tests
- Full suite: **77 passed** (`pytest backend/tests -q`)
- `npx tsc --noEmit` + `npm run build` — OK

## Known limitations

- No SMTP; email is template-only in API response
- No digital signature or negotiation
- One decision per review link; after respond, link is read-only
- Expired links: GET still returns dossier; writes return 403
- Tokens are URL-safe random strings (not signed JWTs)
- Public page uses app shell (header visible); reviewer cannot access other contracts without tokens

## Env

- `REVIEW_BASE_URL` — base URL for generated links (backend `.env`)
