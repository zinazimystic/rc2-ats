"""Helpers for API tests: a fake resume/assessment pipeline (Agent A's real one is tested separately)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
JOB_BODY = {
    "title": "Backend Developer",
    "description": "We need a backend developer with Python, Django, PostgreSQL and Docker experience.",
    "min_experience_years": 2,
    "education_level": "bachelor",
    "requirements": [
        {"skill": "Python", "kind": "required", "importance": 5},
        {"skill": "Django", "kind": "required", "importance": 4},
        {"skill": "Docker", "kind": "preferred", "importance": 2},
    ],
}


@pytest.fixture()
def fake_pipeline(monkeypatch):
    """Replace the AI pipeline: resumes 'parse' instantly, assessments score = share of required skills present."""
    from app.db.session import SessionLocal
    from app.db.types import utcnow
    from app.models import Application, Assessment, CandidateSkill, Job, Resume
    from app.services import pipeline, workflow

    skills_by_name = {"alice": ["Python", "Django", "Docker"], "bob": ["Python"], "carol": ["Java"]}

    def enqueue_resume(rid):
        with SessionLocal() as db:
            r = db.get(Resume, rid)
            from app.models import User

            owner = db.get(User, r.candidate_id)
            r.parse_status, r.text, r.page_count, r.extraction_method = "parsed", f"{owner.full_name} resume text", 1, "rules"
            r.parsed = {"contact": {"name": owner.full_name}, "experience": [], "education": [], "projects": []}
            key = owner.full_name.split()[0].lower()
            r.skills.clear()
            for s in skills_by_name.get(key, []):
                r.skills.append(CandidateSkill(name=s, raw_name=s, source="rules", verification="verified", evidence=s))
            db.commit()
            apps = db.query(Application).filter(Application.candidate_id == r.candidate_id).all()
            ids = [a.id for a in apps if a.resume_id == rid]
        for i in ids:
            enqueue_assessment(i)

    def enqueue_assessment(aid):
        with SessionLocal() as db:
            a = db.get(Application, aid)
            job = db.get(Job, a.job_id)
            r = db.get(Resume, a.resume_id)
            have = {s.name.lower() for s in r.skills if not s.removed and s.presence == "present"}
            reqs, hit = [], 0
            for jr in job.requirements:
                ok = jr.skill.lower() in have
                hit += ok and jr.kind == "required"
                reqs.append({
                    "requirement_id": str(jr.id), "skill": jr.skill, "kind": jr.kind, "importance": jr.importance,
                    "status": "evidenced" if ok else "missing_evidence", "credit": 1.0 if ok else 0.0,
                    "match_type": "exact" if ok else "none", "evidence": [], "explanation": "",
                })
            total_req = max(1, sum(1 for jr in job.requirements if jr.kind == "required"))
            score = round(100 * hit / total_req, 1)
            old = db.query(Assessment).filter_by(application_id=aid).first()
            if old:
                db.delete(old)
                db.flush()
            db.add(Assessment(
                application_id=aid, job_version=job.version, total_score=score,
                components={"skills": {"score": score, "weight": 100, "points": score}},
                requirements=reqs, strengths=["fake"], gaps=[], flags=[],
            ))
            a.processing_state, a.assessed_at = "done", utcnow()
            workflow.system_transition(db, a, "parsed")
            workflow.system_transition(db, a, "ai_assessed")
            db.commit()

    monkeypatch.setattr(pipeline, "enqueue_resume", enqueue_resume)
    monkeypatch.setattr(pipeline, "enqueue_assessment", enqueue_assessment)
    return pipeline


def upload(client, name: str = "cv.pdf", data: bytes = PDF, ctype: str = "application/pdf"):
    return client.post("/api/candidates/me/resumes", files={"file": (name, data, ctype)})


def make_job(recruiter, **over):
    r = recruiter.post("/api/jobs", json={**JOB_BODY, **over})
    assert r.status_code == 201, r.text
    return r.json()


def apply_to(candidate, job_id):
    return candidate.post("/api/applications", json={"job_id": job_id})


def future(hours: float = 24, minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)).replace(microsecond=0).isoformat()


@pytest.fixture()
def world(make_client, fake_pipeline):
    """A recruiter, a second recruiter, three candidates (alice/bob/carol) who each applied to one job."""
    rec = make_client("recruiter", "rec@example.com", "Rita Recruiter")
    rec2 = make_client("recruiter", "rec2@example.com", "Other Recruiter")
    job = make_job(rec)
    cands, apps = {}, {}
    for n in ("alice", "bob", "carol"):
        c = make_client("candidate", f"{n}@example.com", f"{n.title()} Tester")
        assert upload(c, f"{n}.pdf").status_code == 201
        r = apply_to(c, job["id"])
        assert r.status_code == 201, r.text
        cands[n], apps[n] = c, r.json()
    return type("World", (), dict(rec=rec, rec2=rec2, job=job, cands=cands, apps=apps))
