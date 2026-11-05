"""Realistic volume for query-count tests: recruiters, jobs, candidates with parsed resumes (skills, chunks, embeddings),
applications with assessments, notes, interviews + feedback, audit events, notifications and duplicate flags.
Direct ORM inserts (no HTTP) so thousands of rows seed quickly. `grow()` can be called repeatedly to scale the world up."""
from __future__ import annotations

import uuid
from datetime import timedelta

from app.db.types import utcnow
from app.models import (
    Application, Assessment, AuditEvent, CandidateProfile, CandidateSkill, DuplicateFlag, Interview, InterviewFeedback,
    InterviewQuestion, Job, JobRequirement, Notification, RecruiterNote, Resume, ResumeChunk, User,
)
from tests.fakes import fake_embed

SKILLS = ["Python", "Django", "PostgreSQL", "Docker", "Redis", "AWS", "React", "Kubernetes", "FastAPI", "Git"]
STATUSES = ["submitted", "parsed", "ai_assessed", "recruiter_review", "shortlisted", "interview", "selected", "rejected"]


class World:
    def __init__(self) -> None:
        self.recruiters: list[User] = []
        self.jobs: list[Job] = []  # open jobs of recruiter 0 (the one the tests sign in as)
        self.candidates: list[User] = []
        self.apps: list[Application] = []
        self.resumes: list[Resume] = []
        self.interviews: list[Interview] = []
        self.counter = 0


def _user(db, email, name, role):
    u = User(email=email, password_hash="x", full_name=name, role=role, email_verified_at=utcnow())
    db.add(u)
    db.flush()
    return u


def _job(db, rec, title, n_req=6):
    j = Job(recruiter_id=rec.id, title=title, department="Eng", location="Remote", description=f"{title}: build services with Python.",
            min_experience_years=3, education_level="bachelor", embedding=fake_embed(title))
    db.add(j)
    db.flush()
    for i in range(n_req):
        db.add(JobRequirement(job_id=j.id, skill=SKILLS[i % len(SKILLS)], kind="required" if i < 4 else "preferred",
                              importance=3 + i % 3, position=i, embedding=fake_embed(SKILLS[i % len(SKILLS)])))
    db.flush()
    return j


def _assessment(db, app, job, score):
    reqs = [{"requirement_id": str(uuid.uuid4()), "skill": s, "kind": "required", "importance": 4,
             "status": "evidenced" if i % 2 == 0 else "missing_evidence", "credit": 1.0 if i % 2 == 0 else 0.0,
             "match_type": "exact", "evidence": [{"quote": f"used {s} daily", "start": 5, "end": 20}], "explanation": "x"}
            for i, s in enumerate(SKILLS[:4])]
    db.add(Assessment(application_id=app.id, job_version=job.version, total_score=score,
                      components={"skills": {"score": score, "weight": 50, "points": score / 2}}, requirements=reqs,
                      strengths=["Strong Python"], gaps=["No Docker"], flags=[], summary="ok", summary_method="template"))


def _resume(db, c, k, *, current):
    text = f"Candidate {k}\nBackend engineer. Built APIs with Python, Django and PostgreSQL for five years.\n" * 6
    r = Resume(candidate_id=c.id, filename=f"cv{k}.pdf", content_type="application/pdf", size=2048,
               sha256=uuid.uuid4().hex + uuid.uuid4().hex, file_bytes=b"%PDF-1.4 " + b"x" * 4096, text=text, page_count=1,
               parse_status="parsed", extraction_method="rules", is_current=current, doc_embedding=fake_embed(text),
               parsed={"contact": {"name": c.full_name}, "summary": "Backend engineer",
                       "experience": [{"title": "Backend Engineer", "company": "Acme", "start_date": "2019-01", "end_date": None,
                                       "current": True, "description": "APIs", "skills": ["Python", "Django"]}],
                       "education": [{"degree": "BSc Computer Science", "level": "bachelor", "field": "Computer Science"}],
                       "projects": [{"name": "Shop", "description": "e-commerce API", "tech": ["Python", "Django"]}]})
    db.add(r)
    db.flush()
    for i, s in enumerate(SKILLS[: 5 + k % 3]):
        db.add(CandidateSkill(resume_id=r.id, name=s, raw_name=s, source="rules", verification="verified", evidence=f"used {s}", start=3, end=20))
    for i in range(3):
        db.add(ResumeChunk(resume_id=r.id, idx=i, section="experience", text=f"chunk {i} python django postgresql {k}", start_char=i * 30,
                           end_char=i * 30 + 29, embedding=fake_embed(f"chunk {i} python django {k}")))
    return r


def seed_base(db) -> World:
    w = World()
    for i in range(3):
        w.recruiters.append(_user(db, f"rec{i}@example.com", f"Recruiter {i}", "recruiter"))
    for i in range(4):
        w.jobs.append(_job(db, w.recruiters[0], f"Backend Developer {i}"))
    for r in w.recruiters[1:]:
        _job(db, r, "Other recruiter job")
    db.commit()
    return w


def grow(db, w: World, n_candidates: int, *, extra_jobs: int = 0, extra_for_first: int = 0) -> None:
    """Add `n_candidates` candidates (each with resume, skills, chunks, 1-2 applications, assessment, notes, interviews,
    notifications). `extra_jobs` adds open jobs for recruiter 0 and the others; `extra_for_first` gives candidate 0
    more resumes and applications (to jobs of recruiter 1)."""
    now = utcnow()
    rec = w.recruiters[0]
    for _ in range(n_candidates):
        w.counter += 1
        k = w.counter
        c = _user(db, f"cand{k}@example.com", f"Candidate {k}", "candidate")
        db.add(CandidateProfile(user_id=c.id, headline="Backend engineer", location="Lahore", talent_pool_opt_in=(k % 2 == 0),
                                interests=["python"], links=[], phone=f"+9230012{k:05d}"))
        r = _resume(db, c, k, current=True)
        w.candidates.append(c)
        w.resumes.append(r)
        for j in (w.jobs[k % len(w.jobs)], w.jobs[(k + 1) % len(w.jobs)])[: 1 + k % 2]:
            a = Application(job_id=j.id, candidate_id=c.id, resume_id=r.id, status=STATUSES[k % len(STATUSES)], processing_state="done")
            db.add(a)
            db.flush()
            _assessment(db, a, j, 20 + (k * 7) % 80)
            for n in range(2):
                db.add(RecruiterNote(application_id=a.id, author_id=rec.id, body=f"note {n} for {k}"))
            for action in ("application_submitted", "status_change", "status_change"):
                db.add(AuditEvent(entity_type="application", entity_id=a.id, application_id=a.id, action=action, actor_id=rec.id,
                                  actor_role="recruiter", from_value="submitted", to_value="parsed"))
            db.add(InterviewQuestion(application_id=a.id, difficulty="beginner", question=f"Question {k}?", answer_guidelines=["a", "b"], position=0))
            if k % 3 == 0:
                iv = Interview(application_id=a.id, scheduled_by=rec.id, interviewer_name=f"Interviewer {k}", interviewer_email=f"iv{k}@example.com",
                               start_at=now + timedelta(days=1, hours=k), end_at=now + timedelta(days=1, hours=k, minutes=45))
                db.add(iv)
                db.flush()
                db.add(InterviewFeedback(interview_id=iv.id, author_id=rec.id,
                                         ratings={"technical": 4, "communication": 4, "problem_solving": 3, "culture_fit": 5},
                                         recommendation="yes", comments="good"))
                w.interviews.append(iv)
            w.apps.append(a)
            db.add(Notification(user_id=c.id, type="application_status", title=f"Update {k}", link="/candidate"))
            db.add(Notification(user_id=rec.id, type="new_application", title=f"New application {k}", link="/recruiter"))
        db.add(Notification(type="email_sim", channel="email_sim", sender_id=rec.id, recipient_email=c.email, title=f"Mail {k}"))
        if len(w.candidates) > 1 and k % 5 == 0:
            a_id, b_id = sorted([c.id, w.candidates[-2].id], key=str)
            db.add(DuplicateFlag(candidate_a_id=a_id, candidate_b_id=b_id, reasons=["same_phone"], similarity=0.9))
    db.flush()
    for i in range(extra_jobs):
        w.jobs.append(_job(db, rec, f"Extra job {w.counter}-{i}"))
        for other in w.recruiters[1:]:
            _job(db, other, f"Extra other {w.counter}-{i}")
    if extra_for_first and w.candidates:
        c0 = w.candidates[0]
        for i in range(extra_for_first):
            r = _resume(db, c0, 1000 + w.counter + i, current=False)
            j = _job(db, w.recruiters[1], f"Applied extra {w.counter}-{i}")
            a = Application(job_id=j.id, candidate_id=c0.id, resume_id=r.id, status="recruiter_review", processing_state="done")
            db.add(a)
            db.flush()
            _assessment(db, a, j, 55)
    db.commit()
