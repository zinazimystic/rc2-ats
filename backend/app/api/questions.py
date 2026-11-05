from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import DB, Recruiter
from app.core.errors import ServiceUnavailable
from app.models import InterviewQuestion
from app.schemas.common import Msg
from app.schemas.interview import QuestionGenerateIn, QuestionIn, QuestionOut, QuestionPatch
from app.services import questions as q_service
from app.services.access import get_owned_application, get_owned_question
from app.services.ai import llm
from app.services.audit import log_event

router = APIRouter(tags=["questions"])


def _list(db, application_id: uuid.UUID) -> list[InterviewQuestion]:
    return list(
        db.scalars(
            select(InterviewQuestion).where(InterviewQuestion.application_id == application_id)
            .order_by(InterviewQuestion.position, InterviewQuestion.created_at)
        ).all()
    )


@router.get("/applications/{application_id}/questions", response_model=list[QuestionOut])
def list_questions(application_id: uuid.UUID, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    return _list(db, a.id)


@router.post("/applications/{application_id}/questions/generate", response_model=list[QuestionOut])
def generate(application_id: uuid.UUID, body: QuestionGenerateIn, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    try:
        q_service.generate_questions(db, a, body)
    except (llm.LLMUnavailable, llm.LLMError) as exc:
        db.rollback()
        raise ServiceUnavailable(f"Question generation is unavailable right now: {exc}", code="llm_unavailable")
    log_event(db, entity_type="application", entity_id=a.id, application_id=a.id, action="questions_generated", actor=user)
    db.commit()
    return _list(db, a.id)


@router.post("/applications/{application_id}/questions", response_model=QuestionOut, status_code=201)
def add_question(application_id: uuid.UUID, body: QuestionIn, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    pos = (db.scalar(select(func.max(InterviewQuestion.position)).where(InterviewQuestion.application_id == a.id)) or 0) + 1
    q = InterviewQuestion(
        application_id=a.id, difficulty=body.difficulty, category=body.category.strip() or "skill", question=body.question.strip(),
        answer_guidelines=[g.strip() for g in body.answer_guidelines if g.strip()],
        related_skill=body.related_skill, position=pos, is_edited=False,
    )
    db.add(q)
    db.commit()
    return q


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def patch_question(question_id: uuid.UUID, body: QuestionPatch, db: DB, user: Recruiter):
    q, _ = get_owned_question(db, user, question_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field != "related_skill":
            continue
        if field == "answer_guidelines":
            value = [g.strip() for g in value if g.strip()]
        elif isinstance(value, str):
            value = value.strip()
        setattr(q, field, value)
    q.is_edited = True
    db.commit()
    return q


@router.delete("/questions/{question_id}", response_model=Msg)
def delete_question(question_id: uuid.UUID, db: DB, user: Recruiter):
    q, _ = get_owned_question(db, user, question_id)
    db.delete(q)
    db.commit()
    return Msg(detail="Question deleted")


@router.post("/questions/{question_id}/regenerate", response_model=QuestionOut)
def regenerate(question_id: uuid.UUID, db: DB, user: Recruiter):
    q, _ = get_owned_question(db, user, question_id)
    try:
        q = q_service.regenerate_question(db, q)
    except (llm.LLMUnavailable, llm.LLMError) as exc:
        db.rollback()
        raise ServiceUnavailable(f"Question generation is unavailable right now: {exc}", code="llm_unavailable")
    db.commit()
    return q
