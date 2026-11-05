"""LLM extraction + verification, fairness, search, recommendations, talent pool, questions, job extraction."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.errors import ServiceUnavailable
from app.models import Application, Assessment, InterviewQuestion, Resume, User
from app.schemas.interview import QuestionGenerateIn
from app.schemas.search import TalentSearchIn
from app.services import fairness, jobs_ai, pipeline, questions, search
from app.services.parsing import extractor, files
from tests.ai_helpers import mk_app, mk_job, mk_resume, mk_user
from tests.fakes import install_fake_llm
from tests.test_pipeline import _run, _setup


# ----------------------------------------------------------------------------- LLM extraction
def _llm_extraction(system, user, model):
    return {
        "summary": "Backend engineer",
        "skills": [
            {"name": "Postgres", "evidence": "Led a Django REST Framework platform serving 2M requests per day"},  # quote lacks the skill
            {"name": "Django", "evidence": "Led a Django REST Framework platform serving 2M requests per day"},
            {"name": "Kubernetes", "evidence": "Orchestrated 400 Kubernetes clusters across three continents"},  # hallucinated
            {"name": "Python", "evidence": "Python service that ingests events through Redis queues"},
        ],
        "experience": [{"title": "Senior Backend Engineer", "company": "Nimbus Labs", "start_date": "2021-03", "end_date": None, "current": True,
                        "description": "Led platform", "skills": ["Django"], "evidence": "Senior Backend Engineer | Nimbus Labs | Mar 2021 - Present"}],
        "education": [], "projects": [], "certifications": [], "total_years_claimed": 12,
    }


def test_llm_extraction_is_verified_and_sees_no_pii(demo_pdfs, monkeypatch):
    calls = install_fake_llm(monkeypatch, _llm_extraction)
    text = files.extract_text(demo_pdfs["strong"]).text
    ex = extractor.extract(text, ["Aisha Rahman"])
    seen = calls[0]["user"]
    for pii in ("Aisha", "Rahman", "aisha.rahman@example.com", "1234567", "github.com"):
        assert pii not in seen, pii
    assert "<resume>" in seen and "UNTRUSTED" in calls[0]["system"]
    by = {s.name: s for s in ex.skills}
    assert ex.method == "llm"
    assert by["Django"].verification == "verified" and text[by["Django"].start:by["Django"].end] == by["Django"].evidence
    assert by["Kubernetes"].verification == "unverified" and by["Kubernetes"].start is None  # hallucination caught
    assert by["PostgreSQL"].verification == "verified"  # quote didn't mention it, but the scanner found it literally
    assert any(f.type == "unverified_claim" for f in ex.flags)
    assert ex.parsed.total_years_claimed == 6.0  # the LLM's "12" is not in the resume, so the stated "6 years" wins
    assert ex.parsed.experience[0].verification == "verified" and ex.parsed.experience[0].current
    assert ex.parsed.contact.email == "aisha.rahman@example.com"  # contacts came from regex, not the LLM


def test_unverified_llm_skill_gets_only_half_credit(db, demo_pdfs, monkeypatch):
    install_fake_llm(monkeypatch, lambda s, u, m: {"skills": [{"name": "Docker", "evidence": "made up quote nowhere in resume"}]} if m.__name__ == "LLMExtraction"
                     else {"summary": "ok", "learning": []})
    rec, job, out = _setup(db, demo_pdfs, ("weak",))
    _run(db, out)
    a = db.scalars(select(Assessment).where(Assessment.application_id == out["weak"][2])).one()
    docker = next(r for r in a.requirements if r["skill"] == "Docker")
    assert docker["credit"] == 0.5 and docker["match_type"] == "self_reported" and docker["status"] == "partial"
    assert any(f["type"] == "unverified_claim" for f in a.flags)
    assert a.summary_method == "llm" and db.get(Resume, out["weak"][1]).extraction_method == "llm"


def test_llm_failure_falls_back_to_rules(demo_pdfs, monkeypatch):
    from app.services.ai import llm

    def boom(*a):
        raise llm.LLMError("garbage")

    install_fake_llm(monkeypatch, boom)
    ex = extractor.extract(files.extract_text(demo_pdfs["partial"]).text, [])
    assert ex.method == "rules" and any("failed" in w for w in ex.warnings) and {s.name for s in ex.skills} >= {"Python", "Flask"}


# ----------------------------------------------------------------------------- fairness
def test_fairness_counterfactuals_pass(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    res = fairness.run_fairness_check(db, db.get(Application, out["strong"][2]))
    assert {v.name for v in res.variants} == {"name_swap", "gender_swap", "age_shift", "nationality_swap"}
    assert res.passed and res.max_abs_delta == 0
    assert all(v.model_input_identical and v.delta == 0 for v in res.variants)
    stored = db.scalars(select(Assessment).where(Assessment.application_id == out["strong"][2])).one().total_score
    assert res.baseline_score == pytest.approx(stored, abs=0.2)


def test_fairness_without_resume_text_is_graceful(db):
    rec = mk_user(db, "r@example.com", "R", "recruiter")
    job = mk_job(db, rec)
    u = mk_user(db, "c@example.com", "C")
    r = mk_resume(db, u, b"%PDF-1.4")
    a = mk_app(db, job, u, r)
    res = fairness.run_fairness_check(db, a)
    assert res.variants == [] and res.passed


# ----------------------------------------------------------------------------- search / recommendations / talent pool
def test_talent_search_semantic_respects_access(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs)
    _run(db, out)
    other_rec = mk_user(db, "other@example.com", "Other Rec", "recruiter")
    res = search.talent_search(db, rec, TalentSearchIn(query="Django PostgreSQL Docker backend engineer"))
    assert res.mode == "semantic" and res.detected_skills == ["Django", "PostgreSQL", "Docker"]
    assert res.results[0].candidate.full_name == "Aisha Rahman" and res.results[0].skill_coverage == 100
    top = res.results[0]
    assert top.evidence and all(e.start is not None for e in top.evidence) and top.applications[0].job_title == "Backend Developer"
    assert [r.score for r in res.results] == sorted((r.score for r in res.results), reverse=True)
    # another recruiter sees none of these candidates (nobody opted in, nobody applied to their jobs)
    assert search.talent_search(db, other_rec, TalentSearchIn(query="Django PostgreSQL")).results == []


def test_talent_search_keyword_fallback_and_pool_optin(db, demo_pdfs, monkeypatch):
    rec, job, out = _setup(db, demo_pdfs)
    _run(db, out)
    other_rec = mk_user(db, "other@example.com", "Other Rec", "recruiter")
    from app.services.ai import embeddings

    monkeypatch.setattr(embeddings, "embeddings_available", lambda: False)
    res = search.talent_search(db, rec, TalentSearchIn(query="Flask MySQL"))
    assert res.mode == "keyword" and res.warning and res.results[0].candidate.full_name == "Omar Siddiqui"
    # opt in -> visible to anyone; merged duplicates and retention expiry are excluded
    prof = db.get(User, out["partial"][0].id).profile
    prof.talent_pool_opt_in = True
    db.commit()
    got = search.talent_search(db, other_rec, TalentSearchIn(query="Flask MySQL")).results
    assert [r.candidate.full_name for r in got] == ["Omar Siddiqui"] and got[0].in_talent_pool
    from datetime import timedelta
    from app.db.types import utcnow

    prof.retention_until = utcnow() - timedelta(days=1)
    db.commit()
    assert search.talent_search(db, other_rec, TalentSearchIn(query="Flask MySQL")).results == []
    prof.retention_until, prof.merged_into_id = None, out["strong"][0].id
    db.commit()
    assert search.talent_search(db, other_rec, TalentSearchIn(query="Flask MySQL")).results == []


def test_search_job_filter_requires_ownership(db, demo_pdfs):
    from app.core.errors import NotFound

    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    other_rec = mk_user(db, "other@example.com", "Other Rec", "recruiter")
    with pytest.raises(NotFound):
        search.talent_search(db, other_rec, TalentSearchIn(query="Django", job_id=job.id))
    assert search.talent_search(db, rec, TalentSearchIn(query="Django", job_id=job.id)).results


def test_recommendations_skip_applied_and_rank(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    j2 = mk_job(db, rec, title="Frontend Developer", reqs=[("React", "required", 5), ("JavaScript", "required", 4)], min_years=1, edu="none")
    j3 = mk_job(db, rec, title="Data Engineer", reqs=[("Python", "required", 5), ("PostgreSQL", "required", 4), ("Spark", "required", 4)], min_years=2, edu="none")
    j4 = mk_job(db, rec, title="Closed Role", reqs=[("Python", "required", 5)], status="closed")
    cand = db.get(User, out["strong"][0].id)
    recs = search.recommend_jobs(db, cand)
    titles = [r.job.title for r in recs]
    assert "Backend Developer" not in titles and "Closed Role" not in titles  # applied + closed excluded
    assert titles[0] == "Data Engineer" and titles.index("Data Engineer") < titles.index("Frontend Developer")
    assert "Spark" in recs[0].missing_skills and "Python" in recs[0].matched_skills and recs[0].reason
    assert search.recommend_jobs(db, mk_user(db, "new@example.com", "No Resume")) == []


def test_talent_pool_for_job(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    j2 = mk_job(db, rec, title="Another Backend Role", reqs=[("Python", "required", 5), ("Docker", "required", 3)], min_years=1)
    pool = search.talent_pool(db, j2, rec)
    assert len(pool) == 1 and pool[0].candidate.full_name == "Aisha Rahman" and pool[0].previously_applied_to == "Backend Developer"
    assert pool[0].invited is False
    assert search.talent_pool(db, job, rec) == []  # she already applied to this job
    from app.services.notifications import notify

    notify(db, user_id=out["strong"][0].id, type="job_invite", title="invite", link=f"/candidate/jobs/{j2.id}")
    db.commit()
    assert search.talent_pool(db, j2, rec)[0].invited is True


# ----------------------------------------------------------------------------- questions
def _q_handler(system, user, model):
    import json

    ctx = json.loads(user.split("<context>")[1].split("</context>")[0])
    quote = (ctx.get("projects") or [{}])[0].get("evidence_quote", "")[:60]
    qs = [
        {"difficulty": "beginner", "category": "skill", "question": "What is a Django model and how does it map to a table?", "answer_guidelines": ["ORM", "migrations", "fields"], "related_skill": "Django"},
        {"difficulty": "beginner", "category": "skill", "question": "What is a Django model and how does it map to a database table?", "answer_guidelines": ["dup"]},
        {"difficulty": "intermediate", "category": "gap", "question": "How would you containerize this service with Docker?", "answer_guidelines": ["Dockerfile", "compose", "volumes", "healthchecks"], "related_skill": "Docker"},
        {"difficulty": "advanced", "category": "project", "question": "In your Talent Tracker API, how did you design full-text search?", "answer_guidelines": ["tsvector", "GIN index", "ranking"], "related_skill": "PostgreSQL", "source_quote": quote},
        {"difficulty": "advanced", "category": "project", "question": "Tell me about the Atlantis migration you led.", "answer_guidelines": ["x"], "source_quote": "I led the Atlantis migration of 4000 servers"},
    ]
    return {"questions": qs}


def test_question_generation_dedupes_verifies_quotes_and_persists(db, demo_pdfs, monkeypatch):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    install_fake_llm(monkeypatch, _q_handler)
    app = db.get(Application, out["strong"][2])
    qs = questions.generate_questions(db, app, QuestionGenerateIn(beginner=2, intermediate=2, advanced=2))
    db.commit()
    texts = [q.question for q in qs]
    assert sum("Django model" in t for t in texts) == 1  # near-duplicate removed
    proj = [q for q in qs if q.category == "project"]
    assert {q.source_verified for q in proj} == {True, False}
    ok = next(q for q in proj if q.source_verified)
    resume_text = db.scalars(select(Resume).where(Resume.id == out["strong"][1])).one().text
    assert ok.source_quote in resume_text
    assert [q.position for q in qs] == list(range(len(qs))) and qs[0].difficulty == "beginner"
    # regenerate replaces content, keeps difficulty/category, avoids existing questions
    target = ok
    install_fake_llm(monkeypatch, lambda s, u, m: {"questions": [
        {"difficulty": "advanced", "category": "project", "question": "How did you design full-text search in the Talent Tracker API?", "answer_guidelines": ["a"]},
        {"difficulty": "advanced", "category": "project", "question": "What trade-offs did you make in the realtime metrics pipeline?", "answer_guidelines": ["a", "b", "c"]}]})
    new = questions.regenerate_question(db, target)
    assert new.id == target.id and new.difficulty == "advanced" and new.category == "project" and "trade-offs" in new.question
    # append mode keeps the existing set
    install_fake_llm(monkeypatch, lambda s, u, m: {"questions": [{"difficulty": "beginner", "category": "skill", "question": "Explain what an index is in PostgreSQL.", "answer_guidelines": ["a"]}]})
    more = questions.generate_questions(db, app, QuestionGenerateIn(beginner=1, intermediate=0, advanced=0, append=True))
    assert len(more) == len(qs) + 1
    assert db.scalar(select(InterviewQuestion.id).where(InterviewQuestion.application_id == app.id).limit(1))


def test_questions_503_without_llm(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    with pytest.raises(ServiceUnavailable) as e:
        questions.generate_questions(db, db.get(Application, out["strong"][2]), QuestionGenerateIn())
    assert e.value.code == "llm_unavailable" and e.value.status_code == 503


# ----------------------------------------------------------------------------- job extraction
JD = """We are hiring a Backend Developer.

Requirements:
- 3+ years of backend experience
- Strong Python and Django skills
- Solid PostgreSQL and Docker knowledge
- Bachelor's degree in Computer Science

Nice to have:
- Redis or Celery
- AWS
"""


def test_job_extraction_rules_fallback():
    out = jobs_ai.extract_job_requirements("Backend Developer", JD)
    assert out.method == "rules" and out.warnings
    req = {s.skill for s in out.required_skills}
    pref = {s.skill for s in out.preferred_skills}
    assert {"Python", "Django", "PostgreSQL", "Docker"} <= req and {"Redis", "Celery", "AWS"} <= pref and not (req & pref)
    assert out.min_experience_years == 3 and out.education_level == "bachelor"
    assert all(s.verified and s.evidence for s in out.required_skills)


def test_job_extraction_llm_flags_skills_not_in_description(monkeypatch):
    install_fake_llm(monkeypatch, lambda s, u, m: {
        "required_skills": [{"skill": "Postgres", "importance": 5, "evidence": "Solid PostgreSQL and Docker knowledge"}, {"skill": "Kubernetes", "importance": 4}],
        "preferred_skills": [{"skill": "redis", "importance": 2, "evidence": "Redis or Celery"}],
        "min_experience_years": 3, "education_level": "bachelor", "qualifications": ["Bachelor's in CS"]})
    out = jobs_ai.extract_job_requirements("Backend Developer", JD)
    assert out.method == "llm"
    by = {s.skill: s for s in [*out.required_skills, *out.preferred_skills]}
    assert by["PostgreSQL"].verified and by["Redis"].verified and by["Kubernetes"].verified is False
    assert any("Kubernetes" in w for w in out.warnings) and out.qualifications == ["Bachelor's in CS"]


def test_job_extraction_llm_error_falls_back(monkeypatch):
    from app.services.ai import llm

    def boom(*a):
        raise llm.LLMUnavailable("network down")

    install_fake_llm(monkeypatch, boom)
    out = jobs_ai.extract_job_requirements("Backend Developer", JD)
    assert out.method == "rules" and any("network down" in w for w in out.warnings)


def test_embed_job_is_tolerant(db, monkeypatch):
    from app.models import Job
    from app.services.ai import embeddings

    rec = mk_user(db, "r@example.com", "R", "recruiter")
    job = mk_job(db, rec)
    jobs_ai.embed_job(job.id)
    db.expire_all()
    j = db.get(Job, job.id)
    assert j.embedding and all(r.embedding for r in j.requirements)
    monkeypatch.setattr(embeddings, "embed_texts", lambda t: (_ for _ in ()).throw(embeddings.EmbeddingUnavailable("x")))
    jobs_ai.embed_job(job.id)  # must not raise
    jobs_ai.embed_job(__import__("uuid").uuid4())  # unknown id: no-op
