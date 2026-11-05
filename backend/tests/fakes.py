"""Test doubles for the AI providers. Agent A extends `install_fakes` with a smarter fake LLM.

Default behaviour: embeddings are a deterministic hashed bag-of-words (so similar texts are close),
the LLM is unavailable (pipeline must fall back to the rules extractor).
"""
from __future__ import annotations

import hashlib
import math
import re

from app.core.config import settings


def fake_embed(text: str) -> list[float]:
    dim = settings.embedding_dim
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9\+#\.]+", (text or "").lower())
    grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for g in grams:
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def install_fakes(monkeypatch, *, llm: bool = False) -> None:
    from app.services.ai import embeddings, llm as llm_mod

    monkeypatch.setattr(embeddings, "embeddings_available", lambda: True)
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts: [fake_embed(t) for t in texts])
    monkeypatch.setattr(embeddings, "embed_text", fake_embed)
    monkeypatch.setattr(
        embeddings, "cosine", lambda a, b: float(sum(x * y for x, y in zip(a, b)))
    )
    if not llm:
        monkeypatch.setattr(llm_mod, "llm_available", lambda: False)

        def _unavailable(*a, **k):
            raise llm_mod.LLMUnavailable("LLM disabled in tests")

        monkeypatch.setattr(llm_mod, "json_call", _unavailable)


def install_fake_llm(monkeypatch, handler) -> list[dict]:
    """Make the LLM 'available' and route json_call to `handler(system, user, model) -> dict | BaseModel`.

    Returns a list that records every call as {"system", "user", "model"} so tests can assert on what the LLM saw.
    """
    from app.services.ai import llm as llm_mod

    calls: list[dict] = []

    def _json_call(system, user, model, *, max_tokens=4000, cache_kind=None):
        calls.append({"system": system, "user": user, "model": model.__name__})
        out = handler(system, user, model)
        return out if isinstance(out, model) else model.model_validate(out)

    monkeypatch.setattr(llm_mod, "llm_available", lambda: True)
    monkeypatch.setattr(llm_mod, "json_call", _json_call)
    return calls
