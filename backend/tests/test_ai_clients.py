"""DeepSeek + Bedrock clients (httpx mocked) and graceful degradation when the network/provider fails."""
from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.services.ai import cache, embeddings, llm

REAL_JSON_CALL, REAL_LLM_AVAILABLE = llm.json_call, llm.llm_available
REAL_EMBED_TEXTS, REAL_EMBED_AVAILABLE = embeddings.embed_texts, embeddings.embeddings_available


class Out(BaseModel):
    answer: str


def resp(status=200, body=None, text=None):
    r = httpx.Response(status, json=body) if text is None else httpx.Response(status, text=text)
    r.request = httpx.Request("POST", "https://x")
    return r


def chat(content, finish="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


@pytest.fixture()
def real_llm(monkeypatch):
    monkeypatch.setattr(llm, "json_call", REAL_JSON_CALL)
    monkeypatch.setattr(llm, "llm_available", REAL_LLM_AVAILABLE)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    llm.reset()
    cache.clear_memory()


@pytest.fixture()
def real_emb(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_texts", REAL_EMBED_TEXTS)
    monkeypatch.setattr(embeddings, "embeddings_available", REAL_EMBED_AVAILABLE)
    monkeypatch.setattr(embeddings.time, "sleep", lambda s: None)
    monkeypatch.setattr(settings, "aws_bearer_token_bedrock", "tok")
    monkeypatch.setattr(settings, "embedding_dim", 4)
    embeddings.reset()
    cache.clear_memory()


def test_llm_unavailable_without_key(monkeypatch):
    monkeypatch.setattr(llm, "json_call", REAL_JSON_CALL)
    monkeypatch.setattr(llm, "llm_available", REAL_LLM_AVAILABLE)
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    assert not llm.llm_available()
    with pytest.raises(llm.LLMUnavailable):
        llm.json_call("s", "u", Out)


def test_llm_request_shape_and_fenced_json(real_llm, monkeypatch):
    seen = {}

    def post(url, headers=None, json=None, timeout=None):  # noqa: A002
        seen.update(url=url, headers=headers, body=json)
        return resp(body=chat('```json\n{"answer": "ok"}\n```'))

    monkeypatch.setattr(httpx, "post", post)
    out = llm.json_call("sys json", "user", Out)
    assert out.answer == "ok"
    assert seen["url"].endswith("/chat/completions") and seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["body"]["response_format"] == {"type": "json_object"} and seen["body"]["temperature"] == 0


def test_llm_retries_invalid_json_then_succeeds_and_caches(real_llm, monkeypatch):
    replies = iter([chat("not json"), chat(""), chat('{"answer": "fine"}')])
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (calls.append(1), resp(body=next(replies)))[1])
    assert llm.json_call("s", "unique-user-1", Out, cache_kind="t").answer == "fine"
    assert len(calls) == 3
    assert llm.json_call("s", "unique-user-1", Out, cache_kind="t").answer == "fine"
    assert len(calls) == 3  # served from cache


def test_llm_gives_up_with_llmerror_on_garbage(real_llm, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(body=chat('{"wrong": 1}')))
    with pytest.raises(llm.LLMError):
        llm.json_call("s", "u", Out)


def test_llm_auth_failure_is_unavailable_and_trips_breaker(real_llm, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(401, {"error": "bad key"}))
    with pytest.raises(llm.LLMUnavailable):
        llm.json_call("s", "u", Out)
    assert not llm.llm_available()  # cool-down so every later call fails fast


@pytest.mark.parametrize("exc", [httpx.ProxyError("403 Forbidden"), httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("eof")])
def test_llm_network_errors_become_unavailable(real_llm, monkeypatch, exc):
    def post(*a, **k):
        raise exc

    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(llm.LLMUnavailable):
        llm.json_call("s", "u", Out)


def test_llm_5xx_exhaustion_is_llmerror(real_llm, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(503, {"e": 1}))
    with pytest.raises(llm.LLMError):
        llm.json_call("s", "u", Out)


# ------------------------------------------------------------------ embeddings
def test_titan_request_shape_normalisation_and_cache(real_emb, monkeypatch):
    seen = []

    def post(url, headers=None, content=None, timeout=None):
        seen.append((url, headers, json.loads(content)))
        return resp(body={"embedding": [3.0, 4.0, 0.0, 0.0]})

    monkeypatch.setattr(httpx, "post", post)
    v = embeddings.embed_texts(["hello titan", "hello titan", "other"])
    assert v[0] == v[1] == pytest.approx([0.6, 0.8, 0, 0])
    url, headers, body = seen[0]
    assert url == "https://bedrock-runtime.us-east-1.amazonaws.com/model/amazon.titan-embed-text-v2%3A0/invoke"
    assert headers["Authorization"] == "Bearer tok" and body["dimensions"] == 4 and body["normalize"] is True
    assert len(seen) == 2  # duplicate text de-duplicated
    embeddings.embed_texts(["hello titan"])
    assert len(seen) == 2  # cached
    assert embeddings.cosine(v[0], v[0]) == pytest.approx(1) and embeddings.cosine([0, 0], [1, 1]) == 0


@pytest.mark.parametrize("exc", [httpx.ProxyError("403 Forbidden"), httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
def test_titan_network_errors_become_unavailable(real_emb, monkeypatch, exc):
    def post(*a, **k):
        raise exc

    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.embed_texts(["x1"])
    assert not embeddings.embeddings_available()


def test_titan_expired_token_and_garbage_response(real_emb, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(403, {"message": "expired"}))
    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.embed_texts(["t-exp"])
    embeddings.reset()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp(text="<html>oops</html>"))
    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.embed_texts(["t-garbage"])


def test_no_token_means_unavailable(monkeypatch):
    monkeypatch.setattr(embeddings, "embeddings_available", REAL_EMBED_AVAILABLE)
    monkeypatch.setattr(settings, "aws_bearer_token_bedrock", "")
    assert not embeddings.embeddings_available()


# ------------------------------------------------------------------ the pipeline degrades instead of failing
def test_pipeline_degrades_when_provider_network_is_blocked(db, demo_pdfs, monkeypatch):
    """Keys are set but every outbound call fails (e.g. blocked proxy): resume must parse with rules + keyword matching."""
    from app.models import Application, Assessment, Resume
    from app.services import pipeline
    from tests.ai_helpers import mk_app, mk_job, mk_resume, mk_user

    monkeypatch.setattr(llm, "json_call", REAL_JSON_CALL)
    monkeypatch.setattr(llm, "llm_available", REAL_LLM_AVAILABLE)
    monkeypatch.setattr(embeddings, "embed_texts", REAL_EMBED_TEXTS)
    monkeypatch.setattr(embeddings, "embeddings_available", REAL_EMBED_AVAILABLE)
    monkeypatch.setattr(settings, "deepseek_api_key", "k")
    monkeypatch.setattr(settings, "aws_bearer_token_bedrock", "t")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(embeddings.time, "sleep", lambda s: None)
    llm.reset()
    embeddings.reset()
    cache.clear_memory()

    def blocked(*a, **k):
        raise httpx.ProxyError("403 Forbidden")

    monkeypatch.setattr(httpx, "post", blocked)
    rec = mk_user(db, "r@example.com", "Rita", "recruiter")
    job = mk_job(db, rec)
    u = mk_user(db, "c@example.com", "Aisha Rahman")
    r = mk_resume(db, u, demo_pdfs["strong"])
    a = mk_app(db, job, u, r)
    pipeline.enqueue_resume(r.id)
    db.expire_all()
    res = db.get(Resume, r.id)
    assert res.parse_status == "parsed", res.parse_error
    assert res.extraction_method == "rules"
    assert any("rule-based" in w for w in res.warnings) and any("Semantic" in w for w in res.warnings)
    app = db.get(Application, a.id)
    assert app.processing_state == "done" and app.status == "ai_assessed"
    asm = db.scalars(select(Assessment).where(Assessment.application_id == a.id)).one()
    assert asm.semantic_available is False and asm.summary_method == "template" and asm.total_score >= 70
