"""Recruiter dashboard aggregates, computed in a handful of set-based queries."""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.types import utcnow
from app.models import Application, AuditEvent, Interview, Job, User
from app.schemas.analytics import (
    ActivityItem,
    AnalyticsOut,
    JobStageCount,
    Kpis,
    ScoreBucket,
    SkillGap,
    StageCount,
)
from app.schemas.common import JobBrief
from app.services import workflow
from app.services.access import job_brief

FUNNEL = ["submitted", "parsed", "ai_assessed", "recruiter_review", "shortlisted", "interview", "selected", "rejected"]
SHORTLIST_PLUS = {"shortlisted", "interview", "selected"}
BUCKETS = ["0-20", "20-40", "40-60", "60-80", "80-100"]


def _bucket(score: float) -> str:
    return BUCKETS[min(int(score // 20), 4)]


def overview(db: Session, recruiter: User, job: Job | None = None) -> AnalyticsOut:
    jobs = db.scalars(select(Job).where(Job.recruiter_id == recruiter.id).order_by(Job.created_at.desc())).all()
    scope_jobs = [job] if job else list(jobs)
    job_ids = [j.id for j in scope_jobs]
    apps: list[Application] = []
    if job_ids:
        apps = list(
            db.scalars(
                select(Application)
                .where(Application.job_id.in_(job_ids), Application.status != "withdrawn")
                .options(selectinload(Application.assessment))
            ).all()
        )

    now = utcnow()
    upcoming = 0
    if job_ids:
        upcoming = len(
            db.scalars(
                select(Interview.id)
                .join(Application, Application.id == Interview.application_id)
                .where(Application.job_id.in_(job_ids), Interview.status == "scheduled", Interview.end_at >= now)
            ).all()
        )

    by_status = Counter(a.status for a in apps)
    kpis = Kpis(
        active_jobs=sum(1 for j in scope_jobs if j.status == "open"),
        total_jobs=len(scope_jobs),
        total_applications=len(apps),
        shortlisted=sum(by_status[s] for s in SHORTLIST_PLUS),
        pending_reviews=by_status["ai_assessed"] + by_status["recruiter_review"],
        interviews_scheduled=upcoming,
        selected=by_status["selected"],
        rejected=by_status["rejected"],
    )

    per_job: dict[uuid.UUID, Counter] = defaultdict(Counter)
    for a in apps:
        per_job[a.job_id][a.status] += 1
    applications_by_job = [
        JobStageCount(job_id=j.id, title=j.title, total=sum(per_job[j.id].values()), by_stage=dict(per_job[j.id]))
        for j in scope_jobs
    ]
    funnel = [StageCount(stage=s, label=workflow.status_label(s), count=by_status[s]) for s in FUNNEL]

    proc = [(a.assessed_at - a.created_at).total_seconds() for a in apps if a.assessed_at]
    decide = [(a.decided_at - a.created_at).total_seconds() / 3600 for a in apps if a.decided_at]

    assessed = [a for a in apps if a.assessment is not None]
    gap_counter: Counter = Counter()
    dist: Counter = Counter()
    for a in assessed:
        dist[_bucket(a.assessment.effective_score)] += 1
        for r in a.assessment.requirements or []:
            if r.get("kind") == "required" and r.get("status") in ("missing_evidence", "confirmed_absent"):
                gap_counter[r["skill"]] += 1
    gaps = [
        SkillGap(skill=s, count=n, percent=round(100 * n / len(assessed), 1)) for s, n in gap_counter.most_common(8)
    ]

    return AnalyticsOut(
        kpis=kpis,
        applications_by_job=applications_by_job,
        stage_funnel=funnel,
        shortlist_rate=round(kpis.shortlisted / len(apps), 3) if apps else None,
        avg_processing_seconds=round(sum(proc) / len(proc), 1) if proc else None,
        avg_time_to_decision_hours=round(sum(decide) / len(decide), 1) if decide else None,
        top_skill_gaps=gaps,
        score_distribution=[ScoreBucket(bucket=b, count=dist[b]) for b in BUCKETS],
        recent_activity=_activity(db, job_ids),
        job_filter=job_brief(job) if job else None,
    )


def _activity(db: Session, job_ids: list[uuid.UUID], limit: int = 12) -> list[ActivityItem]:
    if not job_ids:
        return []
    rows = db.execute(
        select(AuditEvent, User.full_name, Job.title)
        .join(Application, Application.id == AuditEvent.application_id)
        .join(Job, Job.id == Application.job_id)
        .join(User, User.id == Application.candidate_id)
        .where(Application.job_id.in_(job_ids))
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    ).all()
    items = []
    for ev, cand, title in rows:
        if ev.action == "status_change":
            text = f"{cand} → {workflow.status_label(ev.to_value or '')} · {title}"
        elif ev.action == "override":
            text = f"Score overridden for {cand} · {title}"
        elif ev.action == "note_added":
            text = f"Note added on {cand} · {title}"
        elif ev.action.startswith("interview_"):
            text = f"{ev.action.replace('_', ' ').capitalize()} · {cand} · {title}"
        elif ev.action == "application_submitted":
            text = f"{cand} applied · {title}"
        else:
            text = f"{ev.action.replace('_', ' ').capitalize()} · {cand} · {title}"
        items.append(ActivityItem(at=ev.created_at, text=text, application_id=ev.application_id))
    return items
