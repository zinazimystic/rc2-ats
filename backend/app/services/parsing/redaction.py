"""Remove PII and protected attributes before any text reaches an LLM, keeping an offset map to the original."""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field

from app.schemas.resume import ContactInfo

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]]+|(?:linkedin\.com|github\.com|gitlab\.com|bitbucket\.org)/[^\s<>()\[\]]+", re.I)
PHONE_RE = re.compile(r"(?<![\w.])(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{2,4}\)[\s.\-]?|\d{2,4}[\s.\-])?\d{3,4}[\s.\-]?\d{3,4}(?![\w])")
_YEAR_RANGE = re.compile(r"^(?:19|20)\d{2}\D+(?:19|20)\d{2}$")
ADDRESS_RE = re.compile(
    r"\b\d{1,5}[A-Za-z]?\s+(?:[A-Z][\w.]*\s+){1,4}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Boulevard|Blvd|Drive|Dr|Block|Sector)\b\.?",
)
PROTECTED_LINE_RE = re.compile(
    r"^\s*(?:[-•*]\s*)?(?:date\s+of\s+birth|d\.?o\.?b\.?|birth\s*date|born|age|gender|sex|marital\s+status|nationality|"
    r"religion|citizenship|father'?s\s+name|mother'?s\s+name|spouse|ethnicity|race|caste|visa\s+status|"
    r"place\s+of\s+birth|passport(?:\s+no\.?)?|cnic|ssn|national\s+id)\b[^\n]*$",
    re.I | re.M,
)
_PRONOUNS = {
    "he": "they", "she": "they", "his": "their", "her": "their", "hers": "theirs",
    "him": "them", "himself": "themselves", "herself": "themselves",
}
PRONOUN_RE = re.compile(r"\b(he|she|his|hers|her|him|himself|herself)\b", re.I)
HONORIFIC_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Mx)\.?(?=\s)", re.I)
_NAME_LINE_RE = re.compile(r"^[A-Z][A-Za-z'\-\.]+(?:\s+[A-Z][A-Za-z'\-\.]+){1,3}$|^[A-Z][A-Z'\-\.]+(?:\s+[A-Z][A-Z'\-\.]+){1,3}$")
_NOT_NAMES = re.compile(r"curriculum|resume|vitae|summary|experience|education|skills|projects|profile|contact|objective|certif", re.I)


@dataclass
class Seg:
    rs: int  # redacted start
    re_: int  # redacted end
    os: int  # original start
    oe: int  # original end
    replaced: bool


@dataclass
class Redacted:
    text: str
    segs: list[Seg] = field(default_factory=list)

    def to_original(self, a: int, b: int) -> tuple[int, int]:
        """Map a [a,b) span of the redacted text back to the original text."""
        return self._pos(a, False), self._pos(b, True)

    def _pos(self, p: int, is_end: bool) -> int:
        if not self.segs:
            return p
        starts = [s.rs for s in self.segs]
        i = max(0, bisect_right(starts, p) - 1 if not is_end else bisect_right(starts, max(p - 1, 0)) - 1)
        seg = self.segs[i]
        if seg.replaced:
            return seg.oe if is_end else seg.os
        return min(seg.os + (p - seg.rs), seg.oe)


def _case_like(src: str, repl: str) -> str:
    return repl.capitalize() if src[:1].isupper() else repl


def detect_name_line(text: str) -> tuple[int, int] | None:
    """Heuristic: the first non-empty line is usually the candidate's name."""
    pos = 0
    for line in text.split("\n")[:6]:
        stripped = line.strip()
        if stripped:
            if (
                _NAME_LINE_RE.match(stripped)
                and not _NOT_NAMES.search(stripped)
                and not re.search(r"[\d@]", stripped)
                and len(stripped.split()) <= 4
            ):
                off = line.index(stripped)
                return pos + off, pos + off + len(stripped)
            return None
        pos += len(line) + 1
    return None


def _spans(text: str, names: list[str], neutralize: bool) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for m in PROTECTED_LINE_RE.finditer(text):
        # drop the whole line (incl. its newline) so the model input is identical with or without the attribute
        has_next = text[m.end():m.end() + 1] == "\n"
        spans.append((m.start(), m.end() + (1 if has_next else 0), ""))
    for m in EMAIL_RE.finditer(text):
        spans.append((m.start(), m.end(), "[EMAIL]"))
    for m in URL_RE.finditer(text):
        spans.append((m.start(), m.end(), "[URL]"))
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 9 <= len(digits) <= 15 and not _YEAR_RANGE.match(m.group(0).strip()):
            spans.append((m.start(), m.end(), "[PHONE]"))
    for m in ADDRESS_RE.finditer(text):
        spans.append((m.start(), m.end(), "[ADDRESS]"))
    nl = detect_name_line(text)
    if nl:
        spans.append((nl[0], nl[1], "[NAME]"))
    for name in names:
        name = (name or "").strip()
        if not name:
            continue
        parts = [name] + [t for t in re.split(r"\s+", name) if len(t) >= 3]
        for part in parts:
            for m in re.finditer(r"(?<![A-Za-z])" + re.escape(part) + r"(?![A-Za-z])", text, re.I):
                spans.append((m.start(), m.end(), "[NAME]"))
    if neutralize:
        for m in HONORIFIC_RE.finditer(text):
            spans.append((m.start(), m.end(), ""))
        for m in PRONOUN_RE.finditer(text):
            spans.append((m.start(), m.end(), _case_like(m.group(0), _PRONOUNS[m.group(0).lower()])))
    return spans


def redact(text: str, names: list[str] | tuple[str, ...] = (), *, neutralize: bool = True) -> Redacted:
    """Redact PII/protected attributes. Returns text + a mapping back to original offsets."""
    spans = _spans(text, list(names), neutralize)
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    chosen: list[tuple[int, int, str]] = []
    last_end = -1
    for s, e, r in spans:
        if s >= last_end and e > s:
            chosen.append((s, e, r))
            last_end = e
    out: list[str] = []
    segs: list[Seg] = []
    cur_o = 0
    cur_r = 0
    for s, e, r in chosen:
        if s > cur_o:
            out.append(text[cur_o:s])
            segs.append(Seg(cur_r, cur_r + (s - cur_o), cur_o, s, False))
            cur_r += s - cur_o
        out.append(r)
        segs.append(Seg(cur_r, cur_r + len(r), s, e, True))
        cur_r += len(r)
        cur_o = e
    if cur_o < len(text):
        out.append(text[cur_o:])
        segs.append(Seg(cur_r, cur_r + (len(text) - cur_o), cur_o, len(text), False))
    return Redacted("".join(out).rstrip(), segs)  # trailing blank lines left by removed lines carry no information


def redact_plain(text: str, names: list[str] | tuple[str, ...] = ()) -> str:
    return redact(text, names).text


def extract_contacts(text: str, account_name: str | None = None) -> ContactInfo:
    """Contact details are pulled locally with regex; they never go to the LLM."""
    email = EMAIL_RE.search(text)
    phone = None
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 9 <= len(digits) <= 15 and not _YEAR_RANGE.match(m.group(0).strip()):
            phone = m.group(0).strip()
            break
    links: list[str] = []
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,;")
        if u not in links and "@" not in u:
            links.append(u)
    nl = detect_name_line(text)
    name = text[nl[0]:nl[1]].strip() if nl else (account_name or None)
    return ContactInfo(name=name, email=email.group(0).lower() if email else None, phone=phone, links=links[:6])
