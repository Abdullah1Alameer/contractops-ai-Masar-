# Feature 9 — Digital Signature Workflow

## Summary

After internal approval (`stage=approved`), legal can create a **signature request** with ordered signers, send invitation templates, and collect **drawn or typed** signatures via public `/sign/[token]` links. On completion the system generates a **demo signed PDF** (original unchanged) and a **Demo Signature Audit Certificate**, then moves the contract to **`active`**.

Provider architecture supports **`simulated`** (default) and a **`signit`** adapter skeleton for future integration.

## Database

- **Migration `012_signature_workflow.sql`**
  - `signature_requests`, `signature_signers` (token stored as SHA-256 hash), `signature_events`
  - Partial unique index: one active request per contract

Run: `backend/.venv/bin/python database/migrate.py`

## Provider architecture

| Path | Role |
|------|------|
| [backend/app/integrations/esign/base.py](backend/app/integrations/esign/base.py) | `ESignProvider` ABC |
| [backend/app/integrations/esign/simulated.py](backend/app/integrations/esign/simulated.py) | Hackathon default |
| [backend/app/integrations/esign/signit.py](backend/app/integrations/esign/signit.py) | Skeleton only (`NotImplementedError`) |
| [backend/app/config.py](backend/app/config.py) | `ESIGN_PROVIDER=simulated\|signit` |

## Lifecycle (sole writer: [lifecycle.py](backend/app/services/lifecycle.py))

| Stage | When |
|-------|------|
| `approved` | After Feature 8 approval |
| `awaiting_signature` | Signature request created |
| `partially_signed` | Some signers done, not all |
| `signed` | Brief transition during finalize |
| `active` | After signed PDF + certificate stored |
| `negotiation` | Signer **decline** (documented revert rule) |

Illegal transitions → HTTP **409**.

## APIs

### Protected (Bearer + optional `X-Demo-Role`)

| Method | Path |
|--------|------|
| POST | `/api/contracts/{id}/signature-request` |
| GET | `/api/contracts/{id}/signature-request` |
| POST | `/api/signature-requests/{id}/send` |
| POST | `/api/signature-requests/{id}/cancel` |
| POST | `/api/signature-requests/{id}/resend/{signer_id}` |
| GET | `/api/signature-requests/{id}/signed-document` |
| GET | `/api/signature-requests/{id}/certificate` |
| GET | `/api/signature/summary` |

### Public (signer token only)

| Method | Path |
|--------|------|
| GET | `/api/public/sign/{token}` |
| POST | `/api/public/sign/{token}/open` |
| POST | `/api/public/sign/{token}/submit` |
| POST | `/api/public/sign/{token}/decline` |
| GET | `/api/public/sign/{token}/document` |

Public payload is allow-listed (no negotiation, approval, AI, or comparison fields). Rate limiting is in-memory per IP/token.

## Frontend

- Internal: **Signature** tab — [SignaturePanel.tsx](frontend/components/SignaturePanel.tsx), [CreateSignatureDialog.tsx](frontend/components/CreateSignatureDialog.tsx)
- Public: [app/sign/[token]/page.tsx](frontend/app/sign/[token]/page.tsx) — draw/type signature, consent, decline
- Dashboard signature KPI row + contract list `?stage=` filters

## PDF / certificate

- [signature_pdf.py](backend/app/services/signature_pdf.py) — PyMuPDF append signature page + bilingual demo footer; separate audit certificate PDF with SHA-256 hashes
- Original `contracts.file_url` is never overwritten

## Manual testing

1. Complete Feature 8 approval → contract `approved`
2. Signature tab → Create request (2 signers, signing order on) → Send
3. Open first signer link → draw signature → consent + name confirm → Submit
4. Open second link → sign → download signed PDF + certificate internally
5. Confirm contract `active` and dashboard KPIs update

## Verification

- `pytest backend/tests -q`: **118 passed**
- `npx tsc --noEmit` + `npm run build`: OK

## Known limitations

- **Simulated** provider only in production demo; Signit not wired
- No SMTP — email templates returned via API only
- DOCX originals may render as demo PDF cover
- Typed signature uses system fonts (no proprietary files)
- Rate limit is single-process in-memory
- Decline returns contract to **`negotiation`** (not `internal_review`)
- Not a licensed trust-service or legally certified signature
