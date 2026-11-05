# Build contract (read with `docs/design.md`)

`docs/design.md` is the full spec (scoring, pipeline, data model, UI). This file pins the **exact API surface,
conventions and module interfaces** so that backend and frontend can be built in parallel.
The Pydantic models in `backend/app/schemas/*.py` are the source of truth for every request/response shape.

## Conventions
- All routes live under `/api`. Routers declare routes as `""` / `"/{id}"` (never a trailing `/`); the app is created with
  `FastAPI(redirect_slashes=False)`.
- Errors are JSON `{ "detail": str, "code": str, "errors"?: [...] }` (422 validation → `code="validation_error"`).
  Schedule conflicts: 409 with `ConflictErrorOut` (`code="schedule_conflict"`).
- Auth: JWT in httpOnly cookie `ats_session` (SameSite=Lax) set by login/register; `Authorization: Bearer` also accepted.
  401 = not signed in. 403 = wrong role. 404 (not 403) for objects the user may not see.
- Datetimes are ISO-8601 UTC. DB stores naive UTC; `UTCDateTime` type returns tz-aware UTC. Naive inputs are treated as UTC.
- IDs are UUID strings. Scores are floats 0..100 rounded to 1 decimal.
- Services call AI through *module attributes* (`from app.services.ai import llm, embeddings`; `llm.json_call(...)`) so
  tests can monkeypatch them. Never `from ... import json_call`.
- One DB session per request (`get_db`) and one per background task. Avoid N+1 queries (remote Postgres has high latency):
  use `selectinload`/`joinedload` and batch queries.
- Python must run on 3.12 (Docker) and 3.14 (dev machine). No Python 3.13+ only syntax.
- Candidates never receive scores, notes, rankings, other candidates' data (separate `Candidate*` schemas).

## Status model
`submitted → parsed → ai_assessed → recruiter_review → shortlisted | rejected → interview → selected | rejected`, plus `withdrawn`.
System transitions (pipeline): `submitted→parsed`, `parsed→ai_assessed`. Everything else is recruiter- or candidate-driven and is
validated by `services/workflow.py` (`ALLOWED_TRANSITIONS`). Scheduling an interview moves `shortlisted → interview` automatically.
Recruiter labels: Submitted, Parsed, AI Assessment Available, Recruiter Review, Shortlisted, Interview, Selected, Rejected, Withdrawn.
Candidate labels (`status_label`): Submitted, Under review (parsed / ai_assessed / recruiter_review), Shortlisted,
Interview scheduled, Selected, Not selected, Withdrawn.

## Endpoints  (R = recruiter, C = candidate, * = any signed-in user)
| Method & path | Role | Request → Response |
|---|---|---|
| GET `/health` | public | → `HealthOut` |
| POST `/auth/register` | public | `RegisterIn` → `UserOut` 201 (+cookie) |
| POST `/auth/login` | public | `LoginIn` → `UserOut` (+cookie), rate-limited |
| POST `/auth/logout` | * | → `Msg` |
| GET `/auth/me` | * | → `UserOut` |
| GET `/jobs?status=&q=` | * | → `list[JobListItem]` (R: own jobs, C: open jobs + `has_applied`) |
| POST `/jobs` | R | `JobIn` → `JobOut` 201 |
| POST `/jobs/extract-requirements` | R | `JobExtractIn` → `JobExtractOut` |
| GET `/jobs/{id}` | * | → `JobOut` |
| PATCH `/jobs/{id}` | R(owner) | `JobUpdate` → `JobOut` (changes to requirements/weights/experience/education bump `version` and re-queue assessments) |
| POST `/jobs/{id}/close` · `/reopen` | R(owner) | → `JobOut` |
| GET `/jobs/{id}/applications?status=&min_score=&skill=&q=&sort=score\|date\|name` | R(owner) | → `JobApplicantsOut` (ranked by effective score desc by default) |
| GET `/jobs/{id}/compare?ids=a,b,c` | R(owner) | → `CompareOut` (2–4 application ids) |
| GET `/jobs/{id}/talent-pool` | R(owner) | → `list[TalentPoolItem]` |
| POST `/jobs/{id}/talent-pool/{candidate_id}/invite` | R(owner) | → `Msg` (creates candidate notification) |
| GET `/candidates/me/profile` · PATCH | C | `ProfileIn` → `ProfileOut` |
| POST `/candidates/me/resumes` (multipart field `file`) | C | → `ResumeOut` 201 (parse runs in background; poll `GET /resumes/{id}`) |
| GET `/candidates/me/resumes` | C | → `list[ResumeOut]` |
| GET `/candidates/me/recommendations` | C | → `list[RecommendationOut]` |
| GET `/resumes/{id}` | owner C or R with access | → `ResumeDetailOut` |
| GET `/resumes/{id}/file` | owner C or R with access | PDF/DOCX bytes (inline) |
| PATCH `/resumes/{id}/parsed` | C(owner) | `ParsedPatchIn` → `ResumeDetailOut` (re-queues the candidate's open applications) |
| POST `/resumes/{id}/skills` | C(owner) or R with access | `SkillAddIn` → `CandidateSkillOut` 201 |
| PATCH `/skills/{id}` · DELETE `/skills/{id}` | same | `SkillPatchIn` → `CandidateSkillOut` · `Msg` |
| POST `/resumes/{id}/reprocess` | C(owner) or R with access | → `ResumeOut` 202 |
| POST `/applications` | C | `ApplyIn` → `CandidateApplicationOut` 201 (409 if already applied, 409 if job closed, 422 if no parsed-able resume) |
| GET `/applications/me` | C | → `list[CandidateApplicationOut]` |
| POST `/applications/{id}/withdraw` | C(owner) | → `CandidateApplicationOut` |
| GET `/applications/{id}` | R(owner of job) | → `ApplicationDetailOut` |
| POST `/applications/{id}/transition` | R(owner) | `TransitionIn` → `ApplicationDetailOut` (422 on illegal transition; `reason` required for reject/reconsider) |
| POST `/applications/{id}/reprocess` | R(owner) | → `ApplicationDetailOut` 202 |
| POST `/applications/{id}/override` | R(owner) | `OverrideIn` → `AssessmentOut` (audited) |
| GET/POST `/applications/{id}/notes` · DELETE `/notes/{id}` | R(owner) | `NoteIn` → `NoteOut` |
| GET `/applications/{id}/history` | R(owner) | → `list[HistoryEventOut]` (audit trail) |
| POST `/applications/{id}/fairness-check` | R(owner) | → `FairnessOut` |
| GET `/applications/{id}/questions` | R(owner) | → `list[QuestionOut]` |
| POST `/applications/{id}/questions/generate` | R(owner) | `QuestionGenerateIn` → `list[QuestionOut]` (synchronous, up to ~60 s; 503 `llm_unavailable` when no LLM) |
| POST `/applications/{id}/questions` | R(owner) | `QuestionIn` → `QuestionOut` 201 |
| PATCH/DELETE `/questions/{id}` | R(owner) | `QuestionPatch` → `QuestionOut` · `Msg` |
| POST `/questions/{id}/regenerate` | R(owner) | → `QuestionOut` |
| GET `/applications/{id}/interviews` | R(owner) | → `list[InterviewOut]` |
| POST `/applications/{id}/interviews` | R(owner) | `InterviewIn` → `InterviewOut` 201 or 409 `ConflictErrorOut` |
| PATCH `/interviews/{id}` | R(owner) | `InterviewPatch` → `InterviewOut` or 409 |
| GET `/interviews?from=&to=&status=` | R | → `list[InterviewOut]` (own jobs) |
| POST `/interviews/{id}/feedback` | R(owner) | `FeedbackIn` → `InterviewOut` |
| POST `/search/talent` | R | `TalentSearchIn` → `TalentSearchOut` |
| GET `/analytics/overview?job_id=` | R | → `AnalyticsOut` |
| GET `/duplicates?status=pending` | R | → `list[DuplicateOut]` |
| POST `/duplicates/{id}/confirm` · `/dismiss` | R | → `DuplicateOut` (confirm = link records, never delete) |
| GET `/notifications?unread=` · POST `/notifications/{id}/read` · POST `/notifications/read-all` | * | → `list[NotificationOut]` · `NotificationOut` · `Msg` |
| GET `/notifications/outbox` | R | → `list[NotificationOut]` (simulated emails sent by this recruiter) |

Resume processing is asynchronous: after upload, `parse_status` goes `pending → processing → parsed | failed`.
Applications go `processing_state: queued → processing → done | failed`; the UI polls every 2 s while any item is queued/processing.

## Module interfaces (Python)
Foundation (written first, do not change signatures without telling the lead):
- `app.core.config.settings` (pydantic-settings), `app.core.errors` (`AppError`, `NotFound`, `Forbidden`, `Conflict`, `Unauthorized`,
  `BadRequest`, `Unprocessable`, `ServiceUnavailable`, `install_handlers(app)`).
- `app.db.session`: `engine`, `SessionLocal`, `get_db()`; `app.db.init_db.init_db()`; `app.db.types.utcnow()`.
- `app.models.*` (SQLAlchemy 2.0, all re-exported from `app.models`).
- `app.services.audit.log_event(db, ...)`, `app.services.notifications.notify(db, ...)`,
  `app.services.workflow.{ALLOWED_TRANSITIONS, allowed_transitions, transition, system_transition, status_label}`.

Agent A — AI core (`app/services/ai/`, `parsing/`, `matching/`, `pipeline.py`, `tasks.py`, `jobs_ai.py`, `questions.py`, `search.py`,
`duplicates.py`, `fairness.py`):
```python
# ai/llm.py
class LLMUnavailable(Exception): ...
class LLMError(Exception): ...
def llm_available() -> bool
def json_call(system: str, user: str, model: type[T], *, max_tokens: int = 4000, cache_kind: str | None = None) -> T
# ai/embeddings.py
class EmbeddingUnavailable(Exception): ...
def embeddings_available() -> bool
def embed_texts(texts: list[str]) -> list[list[float]]      # order preserved, L2-normalised, dim = settings.embedding_dim
def embed_text(text: str) -> list[float]
def cosine(a, b) -> float
# tasks.py
def submit(fn, *args, **kwargs) -> None     # ThreadPoolExecutor; runs inline when settings.tasks_eager
def recover_stuck() -> int                   # requeue resumes/applications stuck in 'processing' > 5 min (call at startup)
# pipeline.py
def process_resume(resume_id: UUID) -> None            # extract -> redact -> LLM/rules -> verify -> normalise -> chunk+embed -> duplicates -> queue assessments
def assess_application(application_id: UUID) -> None   # matcher + scorer + explain -> Assessment; system_transition to parsed / ai_assessed
def enqueue_resume(resume_id: UUID) -> None            # tasks.submit(process_resume, ...)
def enqueue_assessment(application_id: UUID) -> None   # sets processing_state='queued' then tasks.submit(assess_application, ...)
# jobs_ai.py
def extract_job_requirements(title: str | None, description: str) -> JobExtractOut
def embed_job(job_id: UUID) -> None                    # embeds job text + each requirement; failures tolerated
# questions.py
def generate_questions(db, application: Application, spec: QuestionGenerateIn) -> list[InterviewQuestion]   # flushes, caller commits; raises ServiceUnavailable
def regenerate_question(db, question: InterviewQuestion) -> InterviewQuestion
# search.py
def talent_search(db, recruiter: User, req: TalentSearchIn) -> TalentSearchOut
def recommend_jobs(db, candidate: User, limit: int = 10) -> list[RecommendationOut]
def talent_pool(db, job: Job, recruiter: User) -> list[TalentPoolItem]
# duplicates.py
def detect_for_resume(db, resume: Resume) -> list[DuplicateFlag]
def merge(db, flag: DuplicateFlag, actor: User) -> None
# fairness.py
def run_fairness_check(db, application: Application) -> FairnessOut
```

Agent B — API (`app/main.py`, `app/api/*`, `core/security.py`, `core/deps.py`, `core/ratelimit.py`, `services/access.py`,
`services/interviews.py`, `services/analytics.py`, `services/applications.py`, `services/jobs.py`) calls the above through module attributes.
Agent C — frontend (`frontend/**`).

## Demo accounts (seed script only)
Created by `backend/scripts/seed_demo.py` through the public API; credentials are defined in that script and the README only.
