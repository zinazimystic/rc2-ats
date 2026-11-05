# RC3 Talent Intelligence Platform

AI recruitment platform: recruiters post jobs, candidates upload resumes, an **evidence-first** AI pipeline extracts and
verifies skills, produces **explainable, deterministic** relevance scores, and the pipeline runs through shortlisting,
interview questions, scheduling and analytics.

| Layer | Tech |
|---|---|
| Frontend | Next.js (App Router, TypeScript), Tailwind v4, shadcn/ui-style components (Radix), TanStack Query + Table, Recharts, Sonner, react-hook-form + zod, next-themes |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2 |
| Database | **Supabase Postgres + pgvector** (SQLite fallback for local dev when `DATABASE_URL` is empty) |
| LLM | DeepSeek (OpenAI-compatible API) — extraction, requirement parsing, question generation, narrative |
| Embeddings | AWS Bedrock **Titan Text Embeddings V2** (1024-dim) |

Design docs: [`docs/design.md`](docs/design.md) (spec, scoring, data model) and [`docs/CONTRACT.md`](docs/CONTRACT.md) (API contract).

## Architecture highlights
- **Evidence-first.** Every extracted skill/claim carries a verbatim resume quote with character offsets; a verifier checks it
  against the resume text. Unverified items earn no score credit and are flagged. The UI highlights these quotes in the resume.
- **The LLM extracts, code scores.** Scoring is a pure, deterministic function (testable, immune to prompt injection).
- **Fairness by construction.** Name/contact/protected attributes are redacted before any LLM call; a counterfactual
  *fairness check* on every application proves the score doesn’t move.
- **Graceful degradation.** No LLM → labelled rule-based extraction; no embeddings → keyword/alias matching with a visible banner.
- **Same-origin auth.** The browser only talks to Next.js; `/api/*` is proxied to FastAPI (`rewrites()`), so the JWT lives in an
  httpOnly SameSite=Lax cookie — no CORS, no token in JavaScript.

## Quick start (local, no Docker)
```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then edit — see below
uvicorn app.main:app --port 8000                       # single worker (in-process task runner)

# 2. Frontend (new terminal)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev          # http://localhost:3000
```

### Docker
```bash
cp backend/.env.example backend/.env   # fill in credentials
docker compose up --build              # web: :3000, api: :8000
```
Containers are for local/CI use only; nothing here deploys anywhere.

## Environment variables
**Never commit real credentials.** `.env*` files are gitignored; only `backend/.env.example` is tracked.

| Variable (backend/.env) | Purpose |
|---|---|
| `DATABASE_URL` | Supabase **session pooler** URL (`postgresql+psycopg://…?sslmode=require`). Empty → local SQLite. |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `COOKIE_SECURE` | Auth. Use a long random secret; `COOKIE_SECURE=true` behind HTTPS. |
| `RECRUITER_INVITE_CODE` | Optional; when set, recruiter sign-up requires it. |
| `MAX_UPLOAD_MB` | Resume upload limit (default 5). |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` | LLM. |
| `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `BEDROCK_EMBED_MODEL`, `EMBEDDING_DIM` | Titan embeddings via Bedrock API key. |

| Variable (frontend) | Purpose |
|---|---|
| `BACKEND_URL` (alias `API_URL`) | Where Next.js proxies `/api/*`. Default `http://localhost:8000`. Baked at build time (Docker build arg `API_URL`). |

The header bar shows live **DB / LLM / Embeddings** health dots (from `GET /api/health`).

## Demo walkthrough (the winning path)
1. **Register** a recruiter (`/register`, role *Recruiter*; add the invite code if configured).
2. **New job** → paste a *Backend Developer* description (Python, Django, PostgreSQL, Docker) → **Extract requirements with AI** →
   review/edit skills & weights → **Create job**.
3. In a private window **register 3 candidates**; each uploads a resume under *Resume & profile*, reviews the parsed
   skills/experience (correct anything), then applies from *Jobs for you*.
4. Back as the recruiter, open the job: applicants appear **ranked by score** and update live while the AI works.
5. Open a candidate: score ring, component breakdown, per-requirement **verbatim evidence** (click a quote to jump to it,
   highlighted, in the resume), strengths/gaps, learning suggestions, **fairness check**, **override** (audited).
6. Select 2–4 applicants → **Compare** side-by-side. **Shortlist** the best.
7. *Questions* tab → **Generate** tailored beginner/intermediate/advanced questions (edit, regenerate, add manually).
8. *Interviews* tab → **Schedule** (conflicts are detected; “Schedule anyway” to override) → candidate is notified;
   leave feedback afterwards. See everything on the *Interviews* calendar.
9. **Dashboard** shows the funnel, score distribution, skill gaps and activity updating. Also try *Talent search*,
   *Duplicates* and the *Email outbox* (simulated emails).

## Frontend structure
```
frontend/src
  app/                login, register, recruiter/*, candidate/*
  components/ui/      button, card, input, badge, dialog, tabs, table, misc (shadcn-style, Radix + Tailwind)
  components/app/     shell, job-form, resume-editor, notifications, application/* (assessment, resume, questions, interviews…)
  lib/                api client (ApiError, 401 handling), auth gate, types (mirror of backend schemas), formatting
```
Quality gates: `npx tsc --noEmit`, `npm run lint`, `npm run build`.

## Testing
Backend: `cd backend && pytest`. Smoke test against real services: `python scripts/smoke_test.py`.
