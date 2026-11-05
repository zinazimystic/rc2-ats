"""AWS Bedrock Titan Text Embeddings V2 over REST with a Bedrock API key (bearer token)."""
from __future__ import annotations

import json
import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.services.ai import cache

log = logging.getLogger("app.ai.embeddings")

MAX_INPUT_CHARS = 8000
_disabled_until = 0.0


class EmbeddingUnavailable(Exception):
    """No credentials, expired token, or provider unreachable."""


def embeddings_available() -> bool:
    return bool(settings.aws_bearer_token_bedrock.strip()) and time.time() >= _disabled_until


def reset() -> None:
    global _disabled_until
    _disabled_until = 0.0


def _disable(seconds: float) -> None:
    global _disabled_until
    _disabled_until = time.time() + seconds


def _url() -> str:
    return f"https://bedrock-runtime.{settings.aws_region}.amazonaws.com/model/{quote(settings.bedrock_embed_model, safe='')}/invoke"


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _embed_remote(text: str) -> list[float]:
    headers = {
        "Authorization": f"Bearer {settings.aws_bearer_token_bedrock.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {"inputText": text[:MAX_INPUT_CHARS] or " ", "dimensions": settings.embedding_dim, "normalize": True}
    last: Exception | None = None
    for attempt in range(5):
        try:
            r = httpx.post(_url(), headers=headers, content=json.dumps(body), timeout=30.0)
        except httpx.TransportError as exc:
            last = exc
            if attempt >= 1 and not isinstance(exc, httpx.TimeoutException):
                break
            time.sleep(min(8, 1.5 * 2**attempt))
            continue
        if r.status_code in (401, 403):
            _disable(300)
            raise EmbeddingUnavailable("Bedrock rejected the credentials (token invalid or expired).")
        if r.status_code in (429, 500, 502, 503, 504):
            last = RuntimeError(f"Bedrock {r.status_code}")
            time.sleep(min(10, 1.5 * 2**attempt))
            continue
        if r.status_code >= 400:
            raise EmbeddingUnavailable(f"Bedrock error {r.status_code}: {r.text[:160]}")
        vec = r.json().get("embedding")
        if not vec:
            raise EmbeddingUnavailable("Bedrock returned no embedding.")
        return _normalize([float(x) for x in vec])
    _disable(30)
    raise EmbeddingUnavailable(f"Bedrock is unreachable: {last}")


def _key(text: str) -> str:
    return cache.make_key("embed", settings.bedrock_embed_model, str(settings.embedding_dim), text[:MAX_INPUT_CHARS])


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed many texts (order preserved, L2-normalised, dim = settings.embedding_dim). Cached by content."""
    if not texts:
        return []
    if not embeddings_available():
        raise EmbeddingUnavailable("Embeddings are not configured (set AWS_BEARER_TOKEN_BEDROCK).")
    out: list[list[float] | None] = [None] * len(texts)
    todo: dict[str, list[int]] = {}
    all_keys = [_key(t) for t in texts]
    hits = cache.get_many(list(dict.fromkeys(all_keys)))  # one DB round trip for the whole batch
    for i, t in enumerate(texts):
        k = all_keys[i]
        hit = hits.get(k)
        if hit and "v" in hit and len(hit["v"]) == settings.embedding_dim:
            out[i] = hit["v"]
        else:
            todo.setdefault(k, []).append(i)
    if todo:
        keys = list(todo)
        first = [texts[todo[k][0]] for k in keys]
        try:
            with ThreadPoolExecutor(max_workers=min(8, len(keys))) as ex:
                vecs = list(ex.map(_embed_remote, first))
        except EmbeddingUnavailable:
            raise
        except Exception as exc:  # any provider/parsing failure degrades to keyword matching
            _disable(30)
            raise EmbeddingUnavailable(f"Embedding call failed: {type(exc).__name__}") from exc
        for k, v in zip(keys, vecs):
            for i in todo[k]:
                out[i] = v
        cache.put_many([(k, "embedding", {"v": v}) for k, v in zip(keys, vecs)])
    return out  # type: ignore[return-value]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(va @ vb / (na * nb))
