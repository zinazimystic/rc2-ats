"""Text helpers for building counterfactual resume variants (fairness check)."""
from __future__ import annotations

import re

_SWAP = {"he": "she", "she": "he", "his": "her", "her": "his", "himself": "herself", "herself": "himself", "mr": "Ms", "ms": "Mr", "mrs": "Mr"}
_PRON = re.compile(r"\b(he|she|his|her|himself|herself)\b", re.I)


def swap_pronouns(text: str) -> str:
    def rep(m: re.Match) -> str:
        w = m.group(0)
        out = _SWAP[w.lower()]
        return out.capitalize() if w[:1].isupper() else out

    return _PRON.sub(rep, text)


def swap_name(text: str, names: list[str], new_name: str) -> str:
    out = text
    new_parts = new_name.split()
    for name in names:
        parts = [p for p in re.split(r"\s+", name.strip()) if p]
        out = re.sub(re.escape(name.strip()), new_name, out, flags=re.I)
        for i, p in enumerate(parts):
            if len(p) >= 3:
                out = re.sub(r"(?<![A-Za-z])" + re.escape(p) + r"(?![A-Za-z])", new_parts[min(i, len(new_parts) - 1)], out, flags=re.I)
    from app.services.parsing.redaction import detect_name_line

    nl = detect_name_line(out)
    if nl and new_name not in out[nl[0]:nl[1]]:
        out = out[: nl[0]] + new_name + out[nl[1]:]
    return out
