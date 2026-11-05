"""One-off: drop stored job / requirement embeddings so they are recomputed with the current `builders.req_text` wording.

Run this (once) after deploying a change to the requirement text or the skills taxonomy, then re-queue assessments:
    python scripts/reembed_jobs.py && python scripts/seed_bulk.py --stage reprocess
(Embeddings are recomputed lazily on the next assessment.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import update  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import Job  # noqa: E402
from app.models.job import JobRequirement  # noqa: E402

if __name__ == "__main__":
    with SessionLocal() as db:
        a = db.execute(update(JobRequirement).values(embedding=None)).rowcount
        b = db.execute(update(Job).values(embedding=None)).rowcount
        db.commit()
    print(f"cleared {a} requirement and {b} job embeddings")
