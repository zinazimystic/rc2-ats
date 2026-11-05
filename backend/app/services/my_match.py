"""Candidate-facing job fit ("what do I need to work on"). Reuses the recommendation scorer; never touches recruiter data."""
from __future__ import annotations

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import Conflict, NotFound
from app.models import Application, CandidateProfile, Job, Resume, User, job_vector_options
from app.schemas.common import JobBrief
from app.schemas.search import (
    MyMatchComponents, MyMatchImprovement, MyMatchOut, MyMatchRequirement, MyMatchResume,
)
from app.services import search
from app.services.parsing.normalizer import taxonomy


def band(score: float) -> str:
    return "strong" if score >= 75 else "good" if score >= 55 else "partial" if score >= 35 else "low"


def _join(items: list[str], limit: int = 4) -> str:
    return ", ".join(items[:limit]) + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _tips(results, components, resume: Resume) -> list[str]:  # noqa: ANN001
    tips: list[str] = []
    missing_req = [r.skill for r in sorted(results, key=lambda r: -r.importance) if r.kind == "required" and r.status in ("missing_evidence", "confirmed_absent")]
    partial = [r.skill for r in results if r.status == "partial" and r.credit < 0.7]
    if missing_req:
        tips.append(f"Show where you've used {_join(missing_req, 3)}: add it to a role or project bullet, or learn the basics and build a small project.")
    if partial:
        tips.append(f"{_join(partial, 3)} only partly come through in your resume. Name the tool directly and describe what you built with it.")
    unverified = [s.name for s in resume.skills if not s.removed and s.verification == "unverified"]
    if unverified:
        tips.append(f"{len(unverified)} skill(s) on your resume have no supporting detail. Add a line about where you used them so they count.")
    exp = components.get("experience")
    if exp is not None and exp.applicable:
        d = exp.details
        if d.get("missing_evidence") or d.get("undated_roles"):
            tips.append("Add start and end dates to each role so your experience can be counted.")
        elif d.get("required_years", 0) and d.get("relevant_years", 0) < d["required_years"]:
            tips.append(f"This role asks for about {d['required_years']:g} years of relevant experience. Highlight related work, internships or freelance projects.")
    pr = components.get("projects")
    if pr is not None and pr.details.get("missing_evidence"):
        tips.append("Add one or two projects with the tools you used and what you achieved.")
    ql = components.get("qualifications")
    if ql is not None and ql.applicable and ql.details.get("missing_evidence"):
        tips.append("List your education and any certifications so they can be matched to the role.")
    generic = [
        "Mirror the job's wording for skills you really have, so the match is easy to see.",
        "Quantify results where you can, for example users served, time saved or performance gained.",
        "Keep your summary short and focused on the skills this job asks for most.",
    ]
    for g in generic:
        if len(tips) >= 3:
            break
        tips.append(g)
    return tips[:5]


def my_match(db: Session, user: User, job_id: uuid.UUID, resume_id: uuid.UUID | None = None) -> MyMatchOut:
    """Round trips: job+requirements+applied flags (1), resume+skills (1), chunks (1), interests (1)."""
    row = db.execute(
        select(
            Job,
            exists().where(Application.job_id == Job.id, Application.candidate_id == user.id, Application.status != "withdrawn"),
            exists().where(Application.job_id == Job.id, Application.candidate_id == user.id),
        )
        .options(*job_vector_options(join=True))
        .where(Job.id == job_id)
    ).unique().first()
    if row is None:
        raise NotFound("Job not found")
    job, applied_active, applied_any = row
    if job.status != "open" and not applied_any:
        raise NotFound("Job not found")
    brief = JobBrief(id=job.id, title=job.title, department=job.department, location=job.location, status=job.status)

    if resume_id is not None:
        resume = db.scalars(
            select(Resume).where(Resume.id == resume_id, Resume.candidate_id == user.id, Resume.deleted_at.is_(None))
            .options(joinedload(Resume.skills))
        ).unique().first()
        if resume is None:
            raise NotFound("Resume not found")
        if resume.parse_status != "parsed":
            raise Conflict("This resume is still being read. Try again in a moment.", code="resume_not_ready")
    else:
        resume = search.best_resume(db, user)
    if resume is None:
        return MyMatchOut(
            job=brief, needs_resume=True, already_applied=bool(applied_active), band="low",
            tips=["Upload your resume to see how well you match this job and what to work on."],
        )

    interests = tuple(db.scalar(select(CandidateProfile.interests).where(CandidateProfile.user_id == user.id)) or ())
    # full scoring (project relevance included) so this matches what the employer's assessment will compute
    _, results, sc = search._score_against(job, resume, interests, with_projects=True)
    total = round(min(100.0, sc.total + search._interest_boost(interests, job)), 1)
    tax = taxonomy()

    comps = {k: (round(v.score, 1) if v.applicable else None) for k, v in sc.components.items()}
    reqs = [
        MyMatchRequirement(
            skill=r.skill, kind=r.kind, importance=r.importance, status=r.status, matched_as=r.matched_as,
            evidence=(r.evidence[0].quote[:300] if r.evidence else None),
        )
        for r in results
    ]
    ev_req = [r for r in results if r.kind == "required" and r.status == "evidenced"]
    n_req = sum(1 for r in results if r.kind == "required")
    strengths: list[str] = []
    if ev_req:
        strengths.append(f"Your resume shows {len(ev_req)} of {n_req} required skills: {_join([r.skill for r in sorted(ev_req, key=lambda r: -r.importance)])}.")
    pref = [r.skill for r in results if r.kind == "preferred" and r.status == "evidenced"]
    if pref:
        strengths.append(f"You also cover nice-to-have skills: {_join(pref)}.")
    exp = sc.components.get("experience")
    if exp is not None and exp.applicable and exp.details.get("required_years") and exp.details.get("relevant_years", 0) >= exp.details["required_years"]:
        strengths.append(f"Your relevant experience ({exp.details['relevant_years']:.1f} years) meets what the job asks for.")
    pr = sc.components.get("projects")
    if pr is not None and pr.details.get("top") and pr.score >= 50:
        strengths.append("Your projects are relevant to this role.")
    gaps: list[str] = []
    ordered = sorted(results, key=lambda r: (r.kind != "required", -r.importance))
    for r in ordered:
        tag = "required" if r.kind == "required" else "nice to have"
        if r.status == "missing_evidence":
            gaps.append(f"We couldn't find {r.skill} on your resume ({tag}).")
        elif r.status == "confirmed_absent":
            gaps.append(f"You've marked {r.skill} as something you haven't used ({tag}).")
        elif r.status == "partial" and r.kind == "required" and r.credit < 0.7:
            gaps.append(f"{r.skill} only partly shows up on your resume.")
    if exp is not None and exp.applicable and exp.details.get("required_years") and exp.details.get("relevant_years", 0) < exp.details["required_years"]:
        gaps.append(f"The job asks for about {exp.details['required_years']:g} years of relevant experience; we found {exp.details.get('relevant_years', 0):.1f}.")
    if pr is not None and pr.details.get("missing_evidence"):
        gaps.append("No projects were found on your resume.")
    gap_names = [
        r.skill for r in ordered
        if r.status in ("missing_evidence", "confirmed_absent") or (r.status == "partial" and r.credit < 0.7)
    ]
    improvements = [MyMatchImprovement(skill=g, suggestion=tax.learn_hint(g)) for g in gap_names[:5]]

    return MyMatchOut(
        job=brief, resume=MyMatchResume(id=resume.id, filename=resume.filename), needs_resume=False, score=total, band=band(total),
        components=MyMatchComponents(**{k: comps.get(k) for k in ("skills", "experience", "projects", "qualifications")}),
        requirements=reqs, strengths=strengths, gaps=gaps[:8], improvements=improvements,
        tips=_tips(results, sc.components, resume), already_applied=bool(applied_active),
        semantic_available=bool(job.embedding is not None and any(c.embedding is not None for c in resume.chunks)),
    )
