from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.core.deps import DB, Recruiter
from app.core.errors import Conflict, NotFound
from app.core.pagination import Limit, Offset, set_total
from app.models import Application, DuplicateFlag, Job, User
from app.schemas.analytics import DuplicateOut
from app.services import duplicates
from app.services.access import candidate_brief
from app.services.audit import log_event

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


def _visible_candidates(recruiter):
    """Subquery of the candidates a recruiter may see here (applicants to their jobs): evaluated inside the database."""
    return select(Application.candidate_id).join(Job, Job.id == Application.job_id).where(Job.recruiter_id == recruiter.id)


def _out(flag: DuplicateFlag, users: dict[uuid.UUID, User]) -> DuplicateOut:
    return DuplicateOut(
        id=flag.id, status=flag.status, reasons=list(flag.reasons or []), similarity=flag.similarity,
        candidate_a=candidate_brief(users[flag.candidate_a_id]), candidate_b=candidate_brief(users[flag.candidate_b_id]),
        created_at=flag.created_at,
    )


def _users(db, flags) -> dict[uuid.UUID, User]:
    ids = {f.candidate_a_id for f in flags} | {f.candidate_b_id for f in flags}
    if not ids:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(ids)).options(joinedload(User.profile))).unique().all()
    return {u.id: u for u in rows}


def _flag_for(db, recruiter, flag_id: uuid.UUID) -> DuplicateFlag:
    visible = _visible_candidates(recruiter)
    flag = db.scalar(
        select(DuplicateFlag).where(
            DuplicateFlag.id == flag_id, DuplicateFlag.candidate_a_id.in_(visible) | DuplicateFlag.candidate_b_id.in_(visible)
        )
    )
    if flag is None:
        raise NotFound("Duplicate flag not found")
    return flag


@router.get("", response_model=list[DuplicateOut])
def list_duplicates(
    response: Response, db: DB, user: Recruiter,
    status: Literal["pending", "confirmed", "dismissed", "all"] = "pending", limit: Limit = 200, offset: Offset = 0,
):
    visible = _visible_candidates(user)
    where = [DuplicateFlag.candidate_a_id.in_(visible) | DuplicateFlag.candidate_b_id.in_(visible)]
    if status != "all":
        where.append(DuplicateFlag.status == status)
    flags = list(db.scalars(select(DuplicateFlag).where(*where).order_by(DuplicateFlag.created_at.desc()).limit(limit).offset(offset)).all())
    set_total(response, len(flags), limit, offset, lambda: db.scalar(select(func.count()).select_from(DuplicateFlag).where(*where)) or 0)
    users = _users(db, flags)
    return [_out(f, users) for f in flags if f.candidate_a_id in users and f.candidate_b_id in users]


def _resolve(db, user, flag_id: uuid.UUID, status: str) -> DuplicateOut:
    flag = _flag_for(db, user, flag_id)
    if flag.status != "pending":
        raise Conflict(f"This duplicate flag was already {flag.status}", code="already_resolved")
    if status == "confirmed":
        duplicates.merge(db, flag, user)  # links records; never deletes
    flag.status, flag.resolved_by = status, user.id
    log_event(db, entity_type="duplicate", entity_id=flag.id, action=f"duplicate_{status}", actor=user)
    db.commit()
    return _out(flag, _users(db, [flag]))


@router.post("/{flag_id}/confirm", response_model=DuplicateOut)
def confirm(flag_id: uuid.UUID, db: DB, user: Recruiter):
    return _resolve(db, user, flag_id, "confirmed")


@router.post("/{flag_id}/dismiss", response_model=DuplicateOut)
def dismiss(flag_id: uuid.UUID, db: DB, user: Recruiter):
    return _resolve(db, user, flag_id, "dismissed")
