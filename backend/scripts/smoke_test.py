"""Environment smoke test: Supabase Postgres + pgvector, DeepSeek, Bedrock Titan, PyMuPDF.

Independent of the app's AI modules (talks to the providers directly) so it can diagnose credentials/network.
Never prints secrets. Run:  .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402

OK, FAIL, SKIP = "[ OK ]", "[FAIL]", "[SKIP]"
results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    print(f"{status} {name}" + (f" - {detail}" if detail else ""), flush=True)


def check_db() -> None:
    from sqlalchemy import text

    from app.db.session import engine

    t0 = time.time()
    try:
        with engine.connect() as conn:
            version = conn.execute(text("select version()")).scalar() if engine.dialect.name == "postgresql" else "sqlite"
            record("database connect", OK, f"{engine.dialect.name} in {time.time() - t0:.2f}s ({str(version)[:40]})")
            if engine.dialect.name == "postgresql":
                try:
                    dist = conn.execute(text("select '[1,2,3]'::vector <=> '[1,2,4]'::vector")).scalar()
                    record("pgvector operator", OK, f"cosine distance {dist:.5f}")
                except Exception as exc:
                    conn.rollback()
                    record("pgvector operator", FAIL, str(exc).splitlines()[0][:150])
            else:
                record("pgvector operator", SKIP, "sqlite fallback (numpy cosine)")
    except Exception as exc:
        record("database connect", FAIL, str(exc).splitlines()[0][:200])


def check_init_db() -> None:
    from sqlalchemy import inspect

    from app.db.init_db import init_db
    from app.db.session import engine

    try:
        t0 = time.time()
        init_db()
        tables = inspect(engine).get_table_names()
        record("init_db / create tables", OK, f"{len(tables)} tables in {time.time() - t0:.1f}s")
    except Exception as exc:
        record("init_db / create tables", FAIL, str(exc).splitlines()[0][:200])


def check_deepseek() -> None:
    if not settings.deepseek_api_key:
        record("deepseek", SKIP, "DEEPSEEK_API_KEY not set")
        return
    body = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": "Reply with json only, e.g. {\"skills\": [\"x\"]}."},
            {"role": "user", "content": "Extract skills from: 'Built REST APIs in Python and Django on PostgreSQL.' Output json."},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 300,
        "thinking": {"type": "disabled"},
    }
    t0 = time.time()
    try:
        r = httpx.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json=body,
            timeout=60,
        )
        if r.status_code != 200:
            record("deepseek", FAIL, f"HTTP {r.status_code}: {r.text[:160]}")
            return
        content = r.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        record("deepseek", OK, f"{settings.deepseek_model} json mode in {time.time() - t0:.1f}s -> {parsed}")
    except Exception as exc:
        record("deepseek", FAIL, str(exc)[:200])


def check_titan() -> None:
    if not settings.aws_bearer_token_bedrock:
        record("bedrock titan", SKIP, "AWS_BEARER_TOKEN_BEDROCK not set")
        return
    url = f"https://bedrock-runtime.{settings.aws_region}.amazonaws.com/model/{quote(settings.bedrock_embed_model, safe='')}/invoke"
    t0 = time.time()
    try:
        r = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.aws_bearer_token_bedrock}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"inputText": "Experience building REST APIs with Django", "dimensions": settings.embedding_dim, "normalize": True},
            timeout=30,
        )
        if r.status_code != 200:
            record("bedrock titan", FAIL, f"HTTP {r.status_code}: {r.text[:160]}")
            return
        emb = r.json()["embedding"]
        record("bedrock titan", OK, f"dim={len(emb)} in {time.time() - t0:.1f}s")
    except Exception as exc:
        record("bedrock titan", FAIL, str(exc)[:200])


def check_pdf() -> None:
    try:
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Jane Doe - Backend Developer\nPython, Django, PostgreSQL, Docker")
        data = doc.tobytes()
        doc.close()
        back = pymupdf.open(stream=data, filetype="pdf")
        text = back[0].get_text("text", sort=True)
        ok = "Django" in text
        record("pymupdf roundtrip", OK if ok else FAIL, f"v{pymupdf.VersionBind}, extracted {len(text)} chars")
    except Exception as exc:
        record("pymupdf roundtrip", FAIL, str(exc)[:200])


if __name__ == "__main__":
    print(f"Database backend: {'sqlite' if settings.is_sqlite else 'postgresql'}")
    check_db()
    if "--no-init" not in sys.argv:
        check_init_db()
    check_deepseek()
    check_titan()
    check_pdf()
    failed = [r for r in results if r[1] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed or skipped")
    sys.exit(1 if failed else 0)
