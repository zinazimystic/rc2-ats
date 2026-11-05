"""Shared builders for AI-core tests (direct DB objects; no HTTP)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models import Application, CandidateProfile, Job, JobRequirement, Resume, User

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_demo_resumes.py"


def load_demo_module():
    spec = importlib.util.spec_from_file_location("make_demo_resumes", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mk_user(db, email, name, role="candidate", *, opt_in=False, interests=None):
    u = User(email=email, password_hash="x", full_name=name, role=role)
    db.add(u)
    db.flush()
    if role == "candidate":
        db.add(CandidateProfile(user_id=u.id, talent_pool_opt_in=opt_in, interests=interests or []))
    db.commit()
    return u


DEFAULT_REQS = [("Python", "required", 5), ("Django", "required", 5), ("PostgreSQL", "required", 4), ("Docker", "required", 4),
                ("Redis", "preferred", 2), ("CI/CD", "preferred", 2), ("AWS", "preferred", 2)]


def mk_job(db, recruiter, *, title="Backend Developer", reqs=None, min_years=3.0, edu="bachelor", desc=None, **kw):
    job = Job(recruiter_id=recruiter.id, title=title, description=desc or "Build backend APIs with Python and Django on PostgreSQL.",
              min_experience_years=min_years, education_level=edu, **kw)
    db.add(job)
    db.flush()
    for i, (skill, kind, imp) in enumerate(DEFAULT_REQS if reqs is None else reqs):
        db.add(JobRequirement(job_id=job.id, skill=skill, kind=kind, importance=imp, position=i))
    db.commit()
    return job


def mk_resume(db, user, data: bytes, filename="resume.pdf"):
    import hashlib

    r = Resume(candidate_id=user.id, filename=filename, content_type="application/pdf", size=len(data),
               sha256=hashlib.sha256(data).hexdigest(), file_bytes=data, parse_status="pending", is_current=True)
    db.add(r)
    db.commit()
    return r


def mk_app(db, job, user, resume):
    a = Application(job_id=job.id, candidate_id=user.id, resume_id=resume.id, status="submitted", processing_state="queued")
    db.add(a)
    db.commit()
    return a
