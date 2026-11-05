"""Skill taxonomy: canonical names, alias matching, related skills. Data lives in app/data/skills_taxonomy.json."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "data" / "skills_taxonomy.json"

# short / common-English aliases that must be written in a specific case to count
_UPPER_ONLY = {"rest", "sh", "ml", "hr", "orm", "http", "dns", "sso", "ci cd"}
_CAP_ONLY = {"node", "spring", "express", "apache", "shell", "oracle", "rails", "documentation", "analytics"}
_DELIM_BEFORE = set(",;/|(:•·-*•")
_DELIM_AFTER = set(",;/|)")


@dataclass(frozen=True)
class SkillHit:
    name: str  # canonical
    start: int
    end: int
    matched: str  # surface text found


class Taxonomy:
    def __init__(self, data: dict):
        self.skills: dict[str, dict] = data["skills"]
        self._lookup: dict[str, str] = {}
        for name, d in self.skills.items():
            self._lookup[_key(name)] = name
            for a in d.get("aliases", []):
                self._lookup.setdefault(_key(a), name)
        self._patterns: list[tuple[str, re.Pattern, bool]] = []
        for name, d in self.skills.items():
            for surface in [name, *d.get("aliases", [])]:
                pat = self._build_pattern(name, surface, bool(d.get("strict")))
                if pat is not None:
                    self._patterns.append((name, pat, bool(d.get("strict")) and len(surface) <= 2))

    @staticmethod
    def _build_pattern(canonical: str, surface: str, strict: bool) -> re.Pattern | None:
        low = surface.lower()
        esc = re.escape(surface).replace(r"\ ", r"[\s\-]?" if " " in surface and len(surface) > 6 else r"\s+")
        guard_l, guard_r = r"(?<![A-Za-z0-9+#])", r"(?![A-Za-z0-9+#])"
        # allow a trailing dot / hyphen / "+" but not letters or digits ("Java" must not match "JavaScript"; "C" not "C++")
        if low in _UPPER_ONLY:
            body = re.escape(surface.upper())
            return re.compile(guard_l + body + guard_r)
        if low in _CAP_ONLY:
            body = "(?:" + re.escape(surface.capitalize()) + "|" + re.escape(surface.upper()) + ")"
            return re.compile(guard_l + body + guard_r)
        if strict and surface == canonical:
            return re.compile(guard_l + esc + guard_r)  # case-sensitive
        if strict:
            return re.compile(guard_l + esc + guard_r, re.I)
        return re.compile(guard_l + esc + guard_r, re.I)

    def canonical(self, name: str) -> str:
        n = (name or "").strip()
        return self._lookup.get(_key(n), n)

    def known(self, name: str) -> bool:
        return _key(name) in self._lookup

    def category(self, name: str) -> str | None:
        d = self.skills.get(self.canonical(name))
        return d.get("category") if d else None

    def related(self, name: str) -> dict[str, float]:
        d = self.skills.get(self.canonical(name))
        return dict(d.get("related", {})) if d else {}

    def describe(self, name: str) -> str:
        """Natural-language phrasing of a skill for embedding: a curated description, else the name plus a few aliases."""
        canon = self.canonical(name)
        d = self.skills.get(canon)
        if not d:
            return name
        if d.get("describe"):
            return d["describe"]
        aliases = [a for a in d.get("aliases", []) if len(a) > 3][:5]
        return f"{canon} ({', '.join(aliases)})" if aliases else canon

    def learn_hint(self, name: str) -> str:
        d = self.skills.get(self.canonical(name))
        return d["learn"] if d else f"Build a small hands-on project using {name} and study its documentation."

    def find(self, text: str) -> list[SkillHit]:
        """All taxonomy skill mentions in `text` (every occurrence, canonicalised, sorted by position)."""
        hits: list[SkillHit] = []
        for name, pat, needs_context in self._patterns:
            for m in pat.finditer(text):
                if needs_context and not _has_delimiters(text, m.start(), m.end()):
                    continue
                hits.append(SkillHit(name, m.start(), m.end(), m.group(0)))
        hits.sort(key=lambda h: (h.start, -(h.end - h.start)))
        # drop hits fully covered by a longer hit of the same position (e.g. "Spring Boot" vs "Spring")
        out: list[SkillHit] = []
        last_end = -1
        for h in hits:
            if h.start < last_end and h.end <= last_end:
                continue
            out.append(h)
            last_end = max(last_end, h.end)
        return out

    def skills_in(self, text: str) -> list[str]:
        seen: dict[str, None] = {}
        for h in self.find(text):
            seen.setdefault(h.name, None)
        return list(seen)


def _has_delimiters(text: str, s: int, e: int) -> bool:
    i = s - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    before_ok = i < 0 or text[i] == "\n" or text[i] in _DELIM_BEFORE
    j = e
    while j < len(text) and text[j] in " \t":
        j += 1
    after_ok = j >= len(text) or text[j] == "\n" or text[j] in _DELIM_AFTER
    return before_ok and after_ok


def _key(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", (s or "").strip().lower())


@lru_cache(maxsize=1)
def taxonomy() -> Taxonomy:
    with open(TAXONOMY_PATH, encoding="utf-8") as fh:
        return Taxonomy(json.load(fh))


def canonical(name: str) -> str:
    return taxonomy().canonical(name)
