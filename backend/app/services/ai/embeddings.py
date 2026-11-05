"""STUB - Agent A replaces this with the real Bedrock Titan V2 client."""
from __future__ import annotations


class EmbeddingUnavailable(Exception):
    """No credentials, expired token, or provider unreachable."""


def embeddings_available() -> bool:
    raise NotImplementedError


def embed_texts(texts: list[str]) -> list[list[float]]:
    raise NotImplementedError


def embed_text(text: str) -> list[float]:
    raise NotImplementedError


def cosine(a: list[float], b: list[float]) -> float:
    raise NotImplementedError
