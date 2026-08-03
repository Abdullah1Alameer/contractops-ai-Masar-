# ContractOps AI

إدارة عقود الباطن للمقاولات السعودية — hackathon project.
F0 (أساس عربي RTL) + F1 (الاستخراج الذكي بالمصادر الموثقة) مكتملة؛ F2–F5 placeholders جاهزة للفريق (انظر `docs/README_HANDOFF.md`).

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for local Postgres) — or a Supabase `DATABASE_URL`

## Setup (once)

```bash
cp .env.example .env          # then put your real OPENAI_API_KEY
docker-compose up -d          # postgres + auto-applies database/migrations on first boot

cd backend
python -m venv .venv
.venv\Scripts\activate        # (Windows) — source .venv/bin/activate on mac/linux
pip install -r requirements.txt

cd ../frontend
npm install
copy .env.local.example .env.local
```

> Using Supabase instead of Docker? Set `DATABASE_URL` in `.env` and run
> `python database/migrate.py` to apply migrations.

## Run (two commands)

```bash
# terminal 1 — backend
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2 — frontend
cd frontend && npm run dev
```

Open http://localhost:3000 — واجهة عربية RTL افتراضياً، تبديل AR/EN من الهيدر.

## Demo data + eval gate

```bash
python database/seed/make_contracts.py   # generates the 2 Arabic demo .docx + ground_truth.json
python database/seed/seed.py             # resets DB, uploads both through the real API, extracts
cd backend && python -m app.ai.eval      # Day-1 GO/NO-GO grading table
```

## Repo layout

```
frontend/            Next.js 14 app router, Tailwind, Arabic-first RTL
backend/app/         FastAPI monolith (main.py, routers/, services/, models.py)
backend/app/ai/      AI core (F1): client.py, prompts.py, schemas.py, verify.py, pipeline.py, eval.py
shared/              openapi.json snapshot + extraction JSON schema + i18n keys
database/            migrations/*.sql, seed/, demo_contracts/
docs/                README_HANDOFF.md — read this first if you're on F2/F3/F4/F5
```

`.env` keys: `OPENAI_API_KEY`, `AI_MODEL`, `DATABASE_URL`, `DEMO_TOKEN` (+ `NEXT_PUBLIC_*` for the frontend).
