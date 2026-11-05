"""Verify that an AI-extracted quote really exists in the resume and recover its character offsets."""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.services.parsing.redaction import Redacted

_TRANS = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-",
    " ": " ", "•": "*", "●": "*", "·": "*", "ﬁ": "fi", "ﬂ": "fl",
}
FUZZY_MIN = 90


@dataclass
class Verified:
    verification: str  # verified | fuzzy | unverified
    start: int | None = None
    end: int | None = None
    quote: str | None = None  # the verbatim original slice when found


def normalize_with_map(s: str) -> tuple[str, list[int]]:
    """Lower-case, unify quotes/dashes, collapse whitespace. Returns (norm, norm_index -> original_index)."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for i, ch in enumerate(s):
        ch = _TRANS.get(ch, ch)
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
            continue
        prev_space = False
        for c in ch.lower():
            out.append(c)
            idx.append(i)
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


class Index:
    """Pre-normalised resume text; build once, verify many quotes."""

    def __init__(self, text: str, redacted: Redacted | None = None):
        self.text = text
        self.norm, self.map = normalize_with_map(text)
        self.redacted = redacted
        if redacted is not None:
            self.rnorm, self.rmap = normalize_with_map(redacted.text)
        else:
            self.rnorm, self.rmap = "", []

    def _span(self, i: int, n: int, m: list[int]) -> tuple[int, int]:
        return m[i], m[i + n - 1] + 1

    def verify(self, quote: str | None, *, min_len: int = 3) -> Verified:
        q, _ = normalize_with_map(quote or "")
        q = q.strip(" .,:;-*")
        if len(q) < min_len:
            return Verified("unverified")
        i = self.norm.find(q)
        if i >= 0:
            s, e = self._span(i, len(q), self.map)
            return Verified("verified", s, e, self.text[s:e])
        if self.redacted is not None:
            j = self.rnorm.find(q)
            if j >= 0:
                rs, re_ = self._span(j, len(q), self.rmap)
                s, e = self.redacted.to_original(rs, re_)
                if e > s:
                    return Verified("verified", s, e, self.text[s:e])
        if len(q) >= 8 and self.norm:
            al = fuzz.partial_ratio_alignment(q, self.norm)
            if al is not None and al.score >= FUZZY_MIN and al.dest_end > al.dest_start:
                s = self.map[al.dest_start]
                e = self.map[min(al.dest_end, len(self.map)) - 1] + 1
                return Verified("fuzzy", s, e, self.text[s:e])
        return Verified("unverified")

    def contains_term(self, term: str) -> bool:
        t, _ = normalize_with_map(term)
        return bool(t) and re.search(r"(?<![a-z0-9+#])" + re.escape(t) + r"(?![a-z0-9+#])", self.norm) is not None


def line_around(text: str, start: int, end: int, max_len: int = 220) -> tuple[int, int]:
    """Expand [start,end) to the surrounding line (capped), for use as an evidence quote."""
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    le = len(text) if le < 0 else le
    if le - ls > max_len:
        a = max(ls, start - max_len // 2)
        b = min(le, end + max_len // 2)
        return a, b
    return ls, le
