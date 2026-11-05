"""STUB - Agent A replaces this with the real DeepSeek client. Signatures are the contract (docs/CONTRACT.md)."""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """No API key configured, or the provider is unreachable."""


class LLMError(Exception):
    """The provider answered but the output could not be used after retries."""


def llm_available() -> bool:
    raise NotImplementedError


def json_call(system: str, user: str, model: type[T], *, max_tokens: int = 4000, cache_kind: str | None = None) -> T:
    raise NotImplementedError
