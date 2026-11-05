from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.schemas.auth import HealthComponent, HealthOut
from app.services.ai import embeddings, llm

router = APIRouter(tags=["health"])


def _probe(fn) -> HealthComponent:
    try:
        ok = bool(fn())
        return HealthComponent(ok=ok, detail=None if ok else "not configured or unreachable")
    except Exception as exc:  # noqa: BLE001
        return HealthComponent(ok=False, detail=str(exc)[:120] or exc.__class__.__name__)


@router.get("/health", response_model=HealthOut)
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db = HealthComponent(ok=True)
    except Exception as exc:  # noqa: BLE001
        db = HealthComponent(ok=False, detail=str(exc)[:120])
    llm_c, emb_c = _probe(llm.llm_available), _probe(embeddings.embeddings_available)
    return HealthOut(
        status="ok" if db.ok and llm_c.ok and emb_c.ok else "degraded",
        database=db,
        database_backend=engine.dialect.name,
        llm=llm_c,
        llm_model=settings.deepseek_model,
        embeddings=emb_c,
        embedding_model=settings.bedrock_embed_model,
        embedding_dim=settings.embedding_dim,
    )
