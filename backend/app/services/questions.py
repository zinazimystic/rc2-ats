"""STUB - Agent A replaces this."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Application, InterviewQuestion
from app.schemas.interview import QuestionGenerateIn


def generate_questions(db: Session, application: Application, spec: QuestionGenerateIn) -> list[InterviewQuestion]:
    raise NotImplementedError


def regenerate_question(db: Session, question: InterviewQuestion) -> InterviewQuestion:
    raise NotImplementedError
