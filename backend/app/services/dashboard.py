"""Candidate home screen in one request. Round trips (user row cached 30 s, otherwise +1):
profile, resumes+skills, applications+jobs, status timelines, scheduled interviews, open jobs+requirements, resume chunks
(lazy, only when a parsed resume exists), unread count = 8."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.types import utcnow
from app.models import Application, CandidateProfile, Job, Notification, Resume, User
from app.schemas.dashboard import CandidateDashboardOut, UpcomingInterviewOut
from app.services import applications as app_service
from app.services import jobs as job_service
from app.services import profile as profile_service
from app.services import resumes as resume_service
from app.services import search

TERMINAL = resume_service.TERMINAL_STATUSES
OPEN_JOBS_SHOWN = 50
OPEN_JOBS_SCORED = 300
RECOMMENDATIONS = 6


def ensure_profile(db: Session, user: User) -> CandidateProfile:
    p = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if p is None:
        p = CandidateProfile(user_id=user.id, links=[], interests=[])
        db.add(p)
        db.flush()
    return p


def build(db: Session, user: User) -> CandidateDashboardOut:
    prof = ensure_profile(db, user)
    all_resumes = list(
        db.scalars(
            select(Resume).where(Resume.candidate_id == user.id).options(joinedload(Resume.skills)).order_by(Resume.created_at.desc())
        ).unique()
    )
    apps = list(
        db.scalars(
            select(Application).where(Application.candidate_id == user.id).options(joinedload(Application.job)).order_by(Application.created_at.desc())
        ).unique()
    )
    live = [r for r in all_resumes if r.deleted_at is None]

    # per-resume usage derived from the applications we already hold (no extra query)
    stats: dict = {}
    for a in apps:
        if a.resume_id is None:
            continue
        count, active = stats.get(a.resume_id, (0, False))
        stats[a.resume_id] = (count + 1, active or a.status not in TERMINAL)
    resume_outs = [resume_service.to_resume_out(r, stats.get(r.id)) for r in live]

    names = {r.id: r.filename for r in all_resumes}
    cand_apps = app_service.to_candidate_applications(db, apps, names)  # timelines + interviews: 2 queries

    now = utcnow()
    job_by_app = {a.id: a.job for a in apps}
    upcoming = sorted(
        (
            UpcomingInterviewOut(**iv.model_dump(), application_id=ca.id, job_id=ca.job.id, job_title=job_by_app[ca.id].title)
            for ca in cand_apps
            if ca.status not in ("withdrawn", "rejected")
            for iv in ca.interviews
            if iv.status == "scheduled" and iv.end_at >= now
        ),
        key=lambda i: i.start_at,
    )

    jobs = list(
        db.scalars(
            select(Job).where(Job.status == "open").options(joinedload(Job.requirements)).order_by(Job.created_at.desc()).limit(OPEN_JOBS_SCORED)
        ).unique()
    )
    applied_active = {a.job_id for a in apps if a.status != "withdrawn"}
    applied_any = {a.job_id for a in apps}
    open_items = job_service.to_list_items(db, jobs[:OPEN_JOBS_SHOWN], user, applied=applied_active)

    current = profile_service.current_resume(live)
    recs = []
    if current is not None:
        recs = search.recommend_from(current, jobs, applied_any, tuple(prof.interests or ()), RECOMMENDATIONS)  # chunks: 1 lazy query

    unread = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.channel == "in_app", Notification.read.is_(False)
        )
    ) or 0
    db.commit()  # only persists a freshly created profile row
    return CandidateDashboardOut(
        profile=profile_service.profile_out(user, prof, current),
        resumes=resume_outs,
        applications=cand_apps,
        recommendations=recs,
        open_jobs=open_items,
        upcoming_interviews=upcoming,
        unread_notifications=int(unread),
    )
