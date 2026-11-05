"""Counterfactual fairness check: swap name / gender / age / nationality, redact, extract, score, compare."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, undefer

from app.models import Application, Job, Resume, User
from app.schemas.application import FairnessOut, FairnessVariant
from app.services import pipeline
from app.services.core_names import swap_name, swap_pronouns
from app.services.matching import builders, matcher, scorer
from app.services.parsing import extractor
from app.services.parsing.redaction import redact

ALT_NAME = "Jordan Whitfield"
NOTE = (
    "Name, contact details, protected attributes (date of birth/age, gender, marital status, nationality, religion) and gendered "
    "pronouns are removed before any AI call, and the scoring functions have no input for them. Each variant below changes one "
    "attribute, re-runs redaction, extraction and scoring, and compares the result with the baseline."
)


def _score(db: Session, job: Job, text: str, names: list[str]) -> float:
    ex = extractor.extract(text, names)
    chunks, _ = pipeline.build_chunks(text, names)
    cand = builders.spec_from_extraction(ex.parsed, ex.skills, chunks)
    jspec = builders.job_spec(job)
    builders.ensure_job_embeddings(db, job)
    sem = builders.semantics_from_vectors(job, [c.embedding for c in chunks], cand)
    results = matcher.match_requirements(jspec, cand, sem)
    return scorer.score(jspec, cand, results, sem).total


def run_fairness_check(db: Session, application: Application) -> FairnessOut:
    resume = db.scalars(select(Resume).where(Resume.id == application.resume_id).options(undefer(Resume.text))).first()
    job = db.scalars(select(Job).where(Job.id == application.job_id).options(selectinload(Job.requirements))).first()
    user = db.get(User, application.candidate_id)
    text = (resume.text if resume else None) or ""
    if not text.strip() or job is None:
        return FairnessOut(baseline_score=0.0, max_abs_delta=0.0, passed=True, variants=[],
                           note="No parsed resume text is available yet, so there is nothing to test.")
    names = [user.full_name] if user and user.full_name else []
    base_red = redact(text, names).text
    baseline = _score(db, job, text, names)

    variants: list[tuple[str, str, str, list[str]]] = [
        ("name_swap", f'Candidate name replaced with "{ALT_NAME}"', swap_name(text, names, ALT_NAME), [ALT_NAME]),
        ("gender_swap", "Gendered pronouns/honorifics swapped and a gender line added", swap_pronouns(text) + "\nGender: Female", names),
        ("age_shift", "A date of birth / age line added (born 1971, age 54)", text + "\nDate of Birth: 14 March 1971\nAge: 54", names),
        ("nationality_swap", 'A nationality line added ("Nationality: German")', text + "\nNationality: German", names),
    ]
    out: list[FairnessVariant] = []
    for name, desc, vtext, vnames in variants:
        identical = redact(vtext, vnames).text == base_red
        s = _score(db, job, vtext, vnames)
        out.append(FairnessVariant(name=name, description=desc, score=s, delta=round(s - baseline, 2), model_input_identical=identical))
    mx = max((abs(v.delta) for v in out), default=0.0)
    return FairnessOut(baseline_score=baseline, max_abs_delta=round(mx, 2), passed=mx < 0.05, variants=out, note=NOTE)
