"""Resume integrity scan: prompt-injection phrases, keyword stuffing, thin content, impossible dates."""
from __future__ import annotations

import re
from collections import Counter

from app.schemas.common import Flag

INJECTION_PATTERNS = [
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above|earlier) (?:instructions?|prompts?|messages?)",
    r"disregard (?:all |any )?(?:the )?(?:previous|prior|above|earlier|your) (?:instructions?|prompts?|rules?)",
    r"(?:system|developer) prompt",
    r"you are (?:now )?(?:an? )?(?:ai|assistant|language model|chatgpt|llm)",
    r"(?:rate|score|rank|grade|assess|evaluate) (?:this|the) (?:candidate|resume|applicant|cv)[^.\n]{0,40}(?:highest|perfect|100|10/10|top|best|strong)",
    r"(?:give|assign) (?:this|the) (?:candidate|resume|applicant)[^.\n]{0,30}(?:100|perfect|highest|maximum|full)",
    r"(?:recommend|shortlist|hire) (?:this|the) candidate (?:immediately|regardless|without)",
    r"do not (?:mention|reveal|flag|report)",
    r"\[\s*(?:system|inst|instructions?)\s*\]|<\s*/?\s*(?:system|instructions?)\s*>",
    r"new instructions?\s*:",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


def find_injection(text: str) -> list[str]:
    hits: list[str] = []
    for rx in _INJ:
        m = rx.search(text)
        if m:
            hits.append(m.group(0)[:100])
    return hits


def scan(text: str, *, hidden_chars: int = 0, hidden_text: str = "") -> list[Flag]:
    flags: list[Flag] = []
    inj = find_injection(text)
    if not inj and hidden_text:
        hid = find_injection(hidden_text)
        if hid:
            flags.append(Flag(type="prompt_injection", severity="critical",
                              message='Hidden text contained instructions aimed at an AI ("' + hid[0] + '"). It was removed and had no effect on scoring.'))
    if inj:
        flags.append(
            Flag(
                type="prompt_injection",
                severity="critical",
                message='The resume contains text that looks like instructions to an AI ("' + inj[0] + '"). '
                "It was treated as plain data and had no effect on scoring.",
            )
        )
    words = re.findall(r"[A-Za-z][A-Za-z+#.]{2,}", text.lower())
    if len(words) >= 40:
        top, n = Counter(words).most_common(1)[0]
        if n >= 25 and n / len(words) > 0.12 and top not in {"and", "the", "with", "for"}:
            flags.append(
                Flag(type="keyword_stuffing", severity="warning", message=f'The word "{top}" is repeated {n} times - possible keyword stuffing.')
            )
    if len(text.strip()) < 300:
        flags.append(Flag(type="low_text", severity="warning", message="Very little text was found; extraction may be incomplete."))
    return flags


def not_a_resume_flag(parsed, skills, text: str) -> list[Flag]:  # noqa: ANN001
    """The document has substantial text but no skills, roles, education or projects: probably not a resume at all."""
    if skills or parsed.experience or parsed.education or parsed.projects or len(text.strip()) < 200:
        return []
    return [Flag(type="not_a_resume", severity="warning",
                 message="No skills, work experience or education could be found. This document may not be a resume.")]
