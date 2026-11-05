# RC3 Talent Intelligence Platform — Build Plan (target: 60 min)

## Context
RC3 "Web App Development" task: build an AI recruitment platform. Recruiters post jobs, candidates upload resumes, the AI extracts evidence and produces explainable job-relevance scores, the pipeline runs through to interview scheduling, and recruiters get analytics plus the "advanced talent intelligence" features (spec §3.10).

**Rubric:** architecture and completeness 30, AI and matching 25, parsing 15, UI 15, innovation, testing, security and deployment 15. The win condition is the demo: a Backend Developer job (Python, Django, PostgreSQL, Docker), 3 applicants, evidence-based scores, a shortlist, interview questions, an interview scheduled, and the dashboard updating. Hardcoded AI does not count.

**What the user wants:** a modular, "proper" build where everything works, edge cases are handled, and the UI is polished, done in about 1 hour. Code goes to `https://github.com/zinazimystic/rc2-ats` (currently empty).

**Locked stack:** Next.js frontend, FastAPI backend, Supabase Postgres + pgvector for all data, DeepSeek for the LLM, AWS Bedrock Titan Text Embeddings V2 for embeddings, Dockerfiles and compose, no deployment.

**Machine facts (checked):**
- Node 24.18 and npm 11.16.
- Python **3.14 only**. Windows cp314 wheels exist for psycopg-binary, pymupdf 2.1 (abi3), numpy, rapidfuzz, bcrypt, lxml, sqlalchemy 2.1 and pydantic-core ≤2.46.
- **pydantic-core version risk.** The newest pydantic (2.14) pins pydantic-core 2.50.2, which may lack a Windows cp314 wheel. If the install tries to build it from source, pin `pydantic>=2.12,<2.14`.
- **Major-version bumps since my knowledge:** openai SDK 3.x, PyMuPDF 2.x, SQLAlchemy 2.1. So:
  - DeepSeek is called with **raw httpx** against its OpenAI-compatible `/chat/completions`, with no SDK.
  - The PyMuPDF calls (`pymupdf.open(stream=...)`, `needs_pass`, `get_text`) get checked in the smoke test.
- **No Docker**, no uv.
- gh is logged in as `zinazimystic`, and the git identity is set.
- `C:\RC2` and the remote repo are both empty.

**Credentials:**
- The Bedrock API key is a short-term bearer token: us-east-1, valid 12 hours (until about 17:00 UTC on Nov 5).
- The DeepSeek key and the Supabase URL come later.
- So the build must run and be fully verifiable before those arrive: local SQLite plus the Titan key, with the LLM path degrading to labelled rule-based extraction.

**Your answers:**
- I write the pasted Bedrock key into `backend/.env` only. It is gitignored, never echoed and never committed.
- Commit milestones on `main` and push once everything is verified.
- DeepSeek and Supabase get added to `.env` when you send them.

## Key decisions
1. **Evidence-first AI.** Every extracted item and every AI claim carries a verbatim resume quote with character offsets. A verifier checks each quote against the resume text. Unverified items get zero score credit and are flagged for review. This one mechanism covers explainability (§3.4, §3.5), hallucination verification and candidate comparison.
2. **The LLM extracts and the code scores.** Scoring is a pure function, so it is deterministic, testable and immune to prompt injection. The LLM only does extraction, requirement parsing, question generation and the narrative summary.
3. **Fairness by construction.** Name, contacts and protected attributes are redacted *before* any LLM call, and the scoring input type has no protected fields. A counterfactual check proves the score delta is 0.
4. **Portable DB.** Production uses Supabase Postgres with pgvector, through the session pooler and psycopg3 with `prepare_threshold=None`. Dev and tests fall back to SQLite when `DATABASE_URL` is empty: vectors stored as JSON and cosine computed in numpy. This is needed because there is no Docker and the Supabase URL isn't here yet.
5. **Graceful degradation.**
   - No DeepSeek key, or it fails: rule-based extraction, flagged `method=rules`. Question generation returns a clear 503 and manual questions are allowed.
   - No Titan, or the token has expired: keyword and alias matching only, with a `semantic_available=false` banner.
6. **UI: shadcn/ui** (Radix + Tailwind v4). Around it: TanStack Query (polling and mutations), TanStack Table (ranked applicants), Recharts via shadcn `chart`, Sonner toasts, lucide icons, react-hook-form with zod, and next-themes for dark mode.
7. **Auth:** our own JWT in an httpOnly SameSite=Lax cookie, plus Bearer support for Swagger and tests. Passwords use bcrypt. The Next `rewrites()` proxy makes `/api/*` same-origin, so no CORS and no token in JS.
8. **Background work:** an in-process `ThreadPoolExecutor` task runner, recovery of stuck jobs on startup, and `TASKS_EAGER=true` in tests. Run a single uvicorn worker, documented.

## Repository layout
```
backend/
  app/main.py                      app factory, routers, exception handlers, startup (init_db, recover tasks)
  app/core/config.py security.py errors.py deps.py ratelimit.py
  app/db/base.py session.py types.py init_db.py vector.py
  app/models/  user.py job.py resume.py application.py interview.py audit.py misc.py
  app/schemas/ auth.py job.py resume.py application.py assessment.py interview.py analytics.py search.py common.py
  app/services/ai/llm.py embeddings.py prompts.py cache.py
  app/services/parsing/ files.py pdf.py docx.py sections.py redaction.py extractor.py rules_extractor.py
                        normalizer.py verifier.py dates.py integrity.py
  app/services/matching/ matcher.py scorer.py explain.py
  app/services/ pipeline.py tasks.py workflow.py interviews.py questions.py jobs_ai.py analytics.py
                search.py duplicates.py fairness.py notifications.py access.py
  app/api/ auth.py jobs.py candidates.py resumes.py applications.py interviews.py questions.py
           search.py analytics.py duplicates.py notifications.py health.py
  app/data/skills_taxonomy.json    ~120 skills: aliases, category, related{skill:weight}, learn hint
  tests/ conftest.py fakes.py test_*.py
  scripts/ smoke_test.py make_demo_resumes.py seed_demo.py
  requirements.txt  Dockerfile  .dockerignore  .env.example  pytest.ini
frontend/  Next.js App Router + src/ (see "Frontend")
docker-compose.yml   README.md   .gitignore
```

## Data model (SQLAlchemy 2, portable types in `db/types.py`)
- **Portable types:**
  - `Uuid` primary keys.
  - `JSONType = JSON().with_variant(JSONB, "postgresql")`.
  - `UTCDateTime`, a TypeDecorator that is always timezone-aware UTC.
  - `Embedding = Vector(1024).with_variant(JSON, "sqlite")`.
  - Enums stored as strings (`native_enum=False`).
  - The HNSW cosine index is created on Postgres only (`ddl_if`).
- **Tables:**
  - `users`: email unique and lowercased, password_hash, full_name, role (recruiter or candidate), is_active.
  - `candidate_profiles`: headline, phone, location, links, interests, talent_pool_opt_in, retention_until, merged_into_id.
  - `resumes`: candidate_id, filename, content_type, size, sha256, `file_bytes` (deferred), text, page_count, parse_status (pending, processing, parsed, failed), parse_error, warnings, integrity_flags, extraction_method (llm or rules), parsed (contact, summary, education, experience, projects, certifications, total_years_claimed), doc_embedding, is_current.
  - `resume_chunks`: resume_id, idx, section, text, start_char, end_char, embedding.
  - `candidate_skills`: resume_id, name (canonical), raw_name, category, presence (present or absent), source (ai, rules, candidate or recruiter), verification (verified, fuzzy, unverified or self_reported), evidence quote, start, end, removed, updated_by.
  - `jobs`: recruiter_id, title, department, location, employment_type, work_mode, salary_min, salary_max, currency, description, min_experience_years, education_level, qualifications, weights (default 50/25/15/10), status (open or closed), version, embedding.
  - `job_requirements`: skill, kind (required or preferred), importance 1–5, embedding.
  - `applications`: job_id, candidate_id, resume_id (a snapshot), status, processing_state (queued, processing, done, failed), processing_error, cover_note, is_duplicate. **unique(job_id, candidate_id)**.
  - `assessments`: application_id (unique), job_version, total_score, override_score, override_reason, overridden_by, components, requirements, strengths, gaps, learning_suggestions, summary, summary_method, flags, semantic_available, model_info.
  - `audit_events`: entity_type, entity_id, application_id, action, from_value, to_value, actor_id, actor_role, note, data, created_at.
  - `recruiter_notes`, `interview_questions` (difficulty, category, question, answer_guidelines[], related_skill, source_quote, source_verified, is_edited, position).
  - `interviews`: interviewer name and email, type, start_at, end_at, location, status (scheduled, completed, cancelled), has_conflict, conflict_details.
  - `interview_feedback`: ratings JSON (1–5), recommendation, comments. Unique (interview, author).
  - `notifications`: user_id or recipient_email (simulated email outbox), type, title, body, link, read.
  - `duplicate_flags`: ordered candidate pair, unique; reasons; similarity; status (pending, confirmed, dismissed).
  - `ai_cache`: sha256 key, kind, JSON value. Caches LLM outputs and embeddings.
- **Application status:** `submitted → parsed → ai_assessed → recruiter_review → shortlisted|rejected → interview → selected|rejected`, plus `withdrawn`.
  - **System transitions:** submitted→parsed and parsed→ai_assessed.
  - **Recruiter transitions:**

    | From | To |
    |---|---|
    | submitted, parsed | recruiter_review, rejected (manual override when AI fails) |
    | ai_assessed | recruiter_review, shortlisted, rejected |
    | recruiter_review | shortlisted, rejected |
    | shortlisted | interview, rejected |
    | interview | selected, rejected |
    | rejected | recruiter_review ("reconsider"; reason required) |

  - **Candidate:** any non-terminal status → withdrawn.
  - **Mechanics:** rows are locked `FOR UPDATE` during a transition. Every change writes an audit event and sends a candidate notification.
  - **Candidate-facing labels:** Submitted, Under review, Shortlisted, Interview scheduled, Selected, Not selected, Withdrawn.

## API contract (prefix `/api`; errors are `{detail, code, errors?}`)
- **Auth:**
  - `POST auth/register` takes `{email, password ≥8 with a letter and a digit, full_name, role, invite_code?}`. A recruiter needs `RECRUITER_INVITE_CODE` if it is set.
  - `POST auth/login` is rate-limited to 5 per minute per IP+email.
  - `POST auth/logout`, `GET auth/me`, and `GET health`, which returns db, llm and embedding status.
- **Jobs:**
  - `GET jobs?status&q` returns the recruiter's own jobs with per-status counts, or open jobs for a candidate.
  - `POST jobs`, `GET/PATCH jobs/{id}`. A PATCH that changes requirements, weights, experience or education bumps the version and re-scores all applications in the background.
  - `POST jobs/{id}/close|reopen`.
  - `POST jobs/extract-requirements {title?, description}` returns `{required_skills[{skill,importance,verified}], preferred_skills[], min_experience_years, education_level, qualifications[], method, warnings[]}`.
  - `GET jobs/{id}/applications?status&min_score&skill&q&sort` returns ranked rows.
  - `GET jobs/{id}/compare?ids=a,b[,c,d]`.
  - `GET jobs/{id}/talent-pool` and `POST jobs/{id}/talent-pool/{candidate_id}/invite`.
- **Candidate:**
  - `GET/PATCH candidates/me/profile`.
  - `POST candidates/me/resumes` (multipart) and `GET candidates/me/resumes`.
  - `GET candidates/me/recommendations`.
- **Resumes:**
  - `GET resumes/{id}` returns detail, text, parsed data and skills. It is open to the owner, or to a recruiter with access.
  - `GET resumes/{id}/file`.
  - `PATCH resumes/{id}/parsed` for candidate corrections.
  - `POST resumes/{id}/skills {name, presence}`, `PATCH/DELETE skills/{id}` (confirm, rename or remove), and `POST resumes/{id}/reprocess`.
- **Applications:**
  - Candidate: `POST applications {job_id, cover_note?}`, `GET applications/me` (labels, timeline, interviews), `POST applications/{id}/withdraw`.
  - Recruiter: `GET applications/{id}` returns detail with assessment and `allowed_transitions`. `POST applications/{id}/transition {to_status, reason?}`, `.../reprocess`, `.../override {score, reason}`, `GET/POST .../notes`, `DELETE notes/{id}`, `GET .../history`, `POST .../fairness-check`.
- **Questions:**
  - `GET applications/{id}/questions`.
  - `POST .../questions/generate {beginner, intermediate, advanced, include_projects}`.
  - `POST .../questions` (manual), `PATCH/DELETE questions/{id}`, `POST questions/{id}/regenerate`.
- **Interviews:**
  - `GET/POST applications/{id}/interviews {interviewer_name, interviewer_email, interview_type, start_at ISO, duration_minutes, location?, notes?, force?}` returns 201, or 409 `{conflicts[]}`.
  - `PATCH interviews/{id}` (reschedule or cancel) and `GET interviews?from&to`.
  - `POST interviews/{id}/feedback {ratings{technical,communication,problem_solving,culture_fit}, recommendation, comments}`.
- **Search, analytics and admin:**
  - `POST search/talent {query, job_id?, limit?}` returns `{detected_skills, mode, results[{candidate, score, matched_skills, evidence[{quote,start,end,similarity}], applications}]}`.
  - `GET analytics/overview?job_id`.
  - `GET duplicates?status` and `POST duplicates/{id}/confirm|dismiss`.
  - `GET notifications`, `POST notifications/{id}/read`, `POST notifications/read-all`.
- **`AssessmentOut`:**
  - Scores: `total_score`, `override_score`, `effective_score`.
  - `components{skills|experience|projects|qualifications: {score, weight, details}}`.
  - `requirements[{requirement_id, skill, kind, importance, status: evidenced|partial|missing_evidence|confirmed_absent, credit, match_type: exact|alias|related|semantic|self_reported, evidence[{quote,start,end,similarity}], explanation}]`.
  - Narrative: `strengths`, `gaps`, `learning_suggestions[{skill,suggestion}]`, `summary`, `summary_method`.
  - Status: `flags[{type,message,severity}]`, `semantic_available`, `stale`.
- **Access rules:**
  - Recruiters manage only the jobs they own.
  - Candidates see only their own data and get a 404, not a 403, for anyone else's.
  - Notes, scores and rankings are never in candidate responses (separate schemas).
  - Search and talent pool only cover candidates who applied to the recruiter's jobs, or who opted in and are within their retention date. Merged duplicates are excluded.

## AI pipeline (`services/pipeline.py`)
**Resume upload:**
1. **Validate:**
   - Detect the type by magic bytes: `%PDF-`, or a DOCX zip containing `word/document.xml`.
   - Size must be at most 5 MB and not zero.
   - The same sha256 for the same candidate reuses the existing parse.
2. **Extract** with PyMuPDF, `get_text(sort=True)`, up to 10 pages and 60k characters. DOCX uses python-docx.
   - Fails cleanly on encrypted (`needs_pass`), corrupt, and scanned or empty files (under 50 characters), each with a user-friendly message.
   - **Integrity scan:** white or tiny-font hidden text is stripped and flagged (anti keyword-stuffing). Prompt-injection phrases are flagged.
3. **Redact** names (from the account plus the first-line heuristic), emails, phones, URLs, addresses and protected-attribute lines (DOB, age, gender, marital status, nationality, religion), and neutralize gendered pronouns. The redaction keeps an offset map back to the original text. Contacts are extracted locally by regex.
4. **DeepSeek extraction:**
   - httpx `POST {DEEPSEEK_BASE_URL}/chat/completions`, `response_format={"type":"json_object"}`, the word "json" plus an example shape in the prompt, temperature 0, `max_tokens` 4000, and a 90-second timeout.
   - The resume is wrapped in `<resume>` tags with an "untrusted data" system prompt.
   - Empty content or `finish_reason=length` triggers a retry. Concurrency is capped at 4 by a semaphore.
   - Every item needs a verbatim `evidence` quote.
   - Validated with Pydantic. On failure it retries once with the error, then falls back to the rules extractor (alias scan plus regex for degrees and dates).
   - Cached by the hash of the redacted text.
5. **Verify** each quote:
   - Exact match on normalized text first (whitespace, case, quotes and dashes), with an index map back to the original offsets.
   - Otherwise a match on the redacted text mapped back.
   - Otherwise a rapidfuzz partial alignment of at least 90, which counts as `fuzzy`.
   - Otherwise `unverified`, and flagged.
   - A skill also counts as unsupported if neither it nor an alias appears in its quote.
6. **Normalize:** alias taxonomy (JS→JavaScript, Postgres→PostgreSQL, k8s→Kubernetes, and so on), dedupe, then store `candidate_skills`.
7. **Chunk and embed:**
   - Chunks are section-aware, 400–800 characters on line boundaries, at most 40.
   - Titan V2 via httpx with `Authorization: Bearer`, 1024 dimensions, normalized, 8 threads, backoff on 429/5xx. A 401/403 raises `EmbeddingUnavailable`.
   - The doc embedding is the mean of the chunk embeddings. Embeddings are cached.
8. **Duplicate detection:** same email (gmail-normalized), same phone (last 10 digits), or a near-identical document (cosine ≥ 0.97, or fuzzy ≥ 92). Creates a pending flag.
9. **Trigger** assessment of every queued application that uses this resume.

**Assessment, per application:**
- `matcher` builds requirement results, then `scorer` computes the score, then `explain` writes the text, plus one DeepSeek narrative call. The narrative input is the structured results only. Its learning areas must be a subset of the gap skills, and it falls back to a template.
- **Skills (50):** weight per requirement = importance × (1 if required, 0.5 if preferred). Credit is the best of:

  | Evidence | Credit | Status |
  |---|---|---|
  | Exact or alias match on a verified or fuzzy skill | 1.0 | evidenced |
  | Unverified or self-reported skill | 0.5 | partial |
  | Related skill in the taxonomy | min(0.7, relation weight) | partial |
  | Semantic best chunk ≥ `SEM_STRONG` (0.55) | 0.7 | partial |
  | Semantic best chunk ≥ `SEM_WEAK` (0.40) | 0.35 | partial |
  | Declared absent | 0 | confirmed_absent |
  | Nothing found | 0 | missing_evidence |

  The thresholds are env-configurable and get calibrated on the demo resumes.
- **Experience (25):** parse dates ("Jan 2020", "2020-01", "2020", "Present") and merge overlapping intervals.
  - Relevant years come from roles whose skills overlap the requirements or whose title is semantically similar to the job.
  - Score = min(1, (relevant + 0.25 × other) / required years). If the job requires 0 years: 1.0 with any experience, 0.5 with none. A verified "N years" claim is the fallback when there are no dated roles.
- **Projects (15):** take the mean of the top two projects. Each project scores 0.5 × semantic similarity to the job (scaled from 0.25–0.65 onto 0–1) + 0.5 × overlap with required tech. No projects means 0, flagged as missing evidence.
- **Qualifications (10):** compare degree levels on the ordinal scale (none, high school, diploma, bachelor, master, PhD), weighted 0.8, plus field relevance weighted 0.2.
  - If the job lists certifications, the blend becomes 0.6 degree level and 0.4 certifications matched.
  - No education evidence counts as missing evidence, not "no degree".
- **Total:** a component that doesn't apply (for example, a job with no requirements) is dropped and the weights are renormalized. The total is rounded to 1 decimal. A recruiter override needs a reason and is audited.
- **Fairness check:** build counterfactual variants (name, gender, DOB/age, nationality, pronouns), then redact, extract (cached) and score each one. Report whether the model input was identical, plus the score delta per variant. Pass means every delta is 0.
- **Questions:** DeepSeek generates beginner, intermediate and advanced questions plus project-based ones, with 3–5 answer-guideline bullets each and a related skill. Source quotes on project questions are verified, and duplicates are removed. Regenerate keeps the same difficulty and category and avoids existing questions.
- **Job extraction:** DeepSeek turns the description into a requirements draft. Each skill is verified against the description, and the recruiter edits and confirms it. The fallback is a taxonomy scan.
- **Search:**
  - The query is embedded and matched against chunk vectors (pgvector `<=>` on Postgres, numpy on SQLite) over accessible candidates, then grouped per candidate.
  - Score = 0.6 × semantic + 0.4 × coverage of the skills detected in the query.
  - The keyword fallback is used when embeddings are unavailable.
- **Recommendations and talent pool:** both reuse the scorer (verified skills, profile interests boost, projects). Recommendations skip jobs the candidate already applied to. Talent pool covers opted-in candidates within retention who have no application yet, and "invite" sends a notification.

## Frontend (Next.js App Router, TypeScript, shadcn new-york, indigo primary, dark mode)
- **Setup:** `next.config` has rewrites `/api/:path*` → `${API_URL}/api/:path*`, `output: "standalone"`, and a raised proxy timeout. Route protection checks the cookie in middleware/proxy, and each role layout guards with `useMe()`.
- **`src/lib`:**
  - `api.ts`: fetch wrapper that throws `ApiError`. A 401 redirects to `/login`.
  - `types.ts`: mirrors the backend schemas.
  - `queries.ts`: TanStack hooks per domain. They poll every 2 seconds while processing.
  - `status.ts` (labels, colors, transitions) and `format.ts`.
- **Shell:** sidebar and topbar with a notifications bell (unread count), theme toggle and user menu. Skeletons, empty states, error toasts, and buttons disabled while a mutation is pending.
- **Recruiter pages:**
  - Dashboard: KPI cards, applications by job and stage, stage funnel, shortlist rate, AI turnaround and time to decision, top skill gaps, recent activity.
  - Jobs list and new/edit: AI "Extract requirements", an editable requirements table, a weights editor that must sum to 100.
  - Job detail tabs:
    - Applicants: ranked table with score bar, mini component bars, matched/missing chips, flags and filters; multi-select to compare.
    - Talent pool.
    - Settings.
  - Application detail: a header with ScoreRing, status, action buttons with reason dialogs, and score override. Tabs:
    - Evidence: requirement matrix; clicking an item highlights the span in the Resume tab.
    - Resume: full text with `<mark>` spans, integrity flags.
    - Breakdown: chart plus explanations and learning areas.
    - Skills: verify, correct, add, mark absent.
    - Questions: generate, edit, regenerate, delete, add.
    - Interviews: schedule form with a conflict warning and "schedule anyway", list, feedback form.
    - Notes.
    - History: audit timeline.
    - Fairness.
  - Compare, Talent search, Interviews schedule (with simulated email outbox), Duplicates review.
- **Candidate pages:**
  - Dashboard: applications with a status stepper and interview info, withdraw, recommendations.
  - Profile: resume dropzone with live parse status, parsed-data editor, skills (add, remove, "I don't have this"), talent-pool opt-in and retention.
  - Jobs browse and detail with apply. Shows "already applied" and "closed" states.

## Security checklist
- bcrypt hashing.
- JWT (HS256, 8-hour lifetime) in an httpOnly SameSite=Lax cookie, with `COOKIE_SECURE` in production.
- Role dependencies plus object-level checks.
- Pydantic validation with length caps everywhere.
- Upload checks by magic bytes and size. Files are stored in the database, never executed or served from disk.
- Login rate limiting.
- The resume is treated as untrusted in prompts, and injection is flagged.
- The LLM never sees PII.
- Secrets only in `.env` (gitignored). `.env.example` is committed.
- Security headers via middleware.
- No stack traces in API errors.

## Testing (`pytest`, SQLite, `TASKS_EAGER`, fake LLM and embedder)
- **Unit:** parsing (normal, empty, encrypted, corrupt, wrong type, hidden text, DOCX), redaction, verifier, normalizer, dates, scorer (weights, renormalization, missing vs absent, determinism, override), workflow transitions, conflict overlap, injection detector, fairness.
- **API:**
  - Auth and RBAC: 403 and 404s, notes hidden from candidates.
  - Full flow: job → upload → apply → assessment → shortlist → questions → schedule → 409 conflict → feedback → select. Analytics counts.
  - Search with the access filter, duplicates, closed job and duplicate application.
- **Frontend:** `npm run build`, which type-checks and lints.
- **E2E:** `scripts/seed_demo.py` drives the real API through the exact demo scenario.

## Docker and config (no deploy)
- **`backend/Dockerfile`:** python:3.12-slim, non-root, healthcheck on `/api/health`, uvicorn with a single worker.
- **`frontend/Dockerfile`:** node:22-alpine multi-stage, standalone output, `ARG API_URL`.
- **`docker-compose.yml`:** `api` (env_file `backend/.env`, `api-data` volume for the SQLite fallback) and `web` (`API_URL=http://api:8000`, depends on api being healthy). Not runnable here because Docker isn't installed. It will be written carefully but untested.
- **`backend/.env.example`:**
  - `DATABASE_URL` (empty means SQLite).
  - DeepSeek: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL=deepseek-chat`, `DEEPSEEK_BASE_URL`.
  - Bedrock: `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION=us-east-1`, `BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0`, `EMBEDDING_DIM=1024`.
  - App: `JWT_SECRET`, `RECRUITER_INVITE_CODE`, `COOKIE_SECURE`, `MAX_UPLOAD_MB`, `SEM_STRONG`, `SEM_WEAK`.

## Execution (parallel, about 60 minutes)
1. **0–10 min, me (foundation and contract):**
   - `git init`, `.gitignore` (covers `.env*` except `.env.example`, `.venv`, `node_modules`, `*.db`), add remote.
   - Write `backend/.env` with the Bedrock key, a generated `JWT_SECRET`, and blanks for DeepSeek and Supabase.
   - Create the venv: Python 3.14, or uv-managed 3.12 if any wheel is missing.
   - Backend foundation: config, db and portable types, all models, all Pydantic schemas, core security, deps and errors, `main.py`, the taxonomy, and `conftest`/`fakes`.
   - Frontend scaffold: create-next-app, shadcn init and add, providers, `api.ts`.
2. **10–35 min, three background subagents with no file overlap:**
   - **A, AI core:** `services/ai/*`, `services/parsing/*`, `services/matching/*`, `pipeline.py`, `tasks.py`, `search.py`, `duplicates.py`, `fairness.py`, `questions.py`, `jobs_ai.py`, and their unit tests.
   - **B, API:** `api/*`, `workflow.py`, `interviews.py`, `analytics.py`, `notifications.py`, `access.py`, `core/ratelimit.py`, and the API tests. It calls A's functions through the signatures stubbed in step 1.
   - **C, Frontend:** all of `frontend/src/**` against the schemas.
   - **Me in parallel:** Dockerfiles and compose, `make_demo_resumes.py` (strong; partial with Flask and no Docker; weak; a scanned/empty PDF; a duplicate), `seed_demo.py`, `smoke_test.py`, and the README (architecture diagram, §3.1–3.10 traceability matrix, AI design, setup, tests, limitations).
   - **Each subagent brief** includes:
     - The files it owns. It must not edit anything else, and asks me instead.
     - The stub signatures it implements or calls.
     - The contract sections above.
     - A definition of done. A and B: their pytest files pass. C: `npm run build` passes, with no `any` in API types.
   - **Order if time gets tight:**
     - P0, the demo path: auth, jobs, parsing, matching, pipeline, questions, scheduling, dashboard.
     - P1: search, compare, fairness, hallucination flags.
     - P2: duplicates, talent pool, recommendations.
   - All three tiers are in scope. The order only decides what gets verified first.
   - Demo accounts and passwords live only in `seed_demo.py` and the README, never in chat.
3. **35–55 min, me (integrate):**
   - Run pytest, start the API on SQLite with real Titan, and run the smoke test and seed demo.
   - Calibrate `SEM_*` from the printed similarities.
   - Run `next build` and `next dev`, then walk the demo in the browser pane. Fix bugs.
4. **55–60 min:** final README, commit, push (per your choice), and report what was verified versus what is pending credentials.

## Verification
- `pytest -q` is all green.
- `python scripts/smoke_test.py` passes DB, pgvector (Postgres only), Titan, DeepSeek and PyMuPDF.
- `python scripts/seed_demo.py` runs the full demo scenario and prints the ranking. The strong candidate must rank first, and Docker must show as missing evidence for the partial candidate.
- `npm run build` passes.
- A browser walkthrough of both roles: recruiter dashboard updates, evidence highlighting, conflict warning, candidate status stepper.
- When the user supplies credentials: set `DATABASE_URL` to the Supabase session pooler and add `DEEPSEEK_API_KEY`. Rerun the smoke test and seed demo, and confirm `method=llm` and the pgvector search path.
