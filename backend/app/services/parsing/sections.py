"""Resume section detection and section-aware chunking (offsets always index the original text)."""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADINGS: list[tuple[str, re.Pattern]] = [
    ("summary", re.compile(r"^(professional\s+)?(summary|profile|objective|about(\s+me)?|career\s+objective)$", re.I)),
    ("experience", re.compile(r"^((professional|work|relevant|employment)\s+)?(experience|history)(\s+history)?$|^employment(\s+history)?$|^career\s+history$", re.I)),
    ("education", re.compile(r"^(education(al)?(\s+background|\s+qualifications?)?|academic(s|\s+background|\s+qualifications?)?|qualifications?)$", re.I)),
    ("skills", re.compile(r"^((technical|key|core|professional)\s+)?(skills|competencies|technologies|tech\s+stack|skills\s*&\s*tools|tools)(\s+&\s+technologies)?$", re.I)),
    ("projects", re.compile(r"^((personal|academic|selected|key|side)\s+)?projects?$", re.I)),
    ("certifications", re.compile(r"^(certifications?|licen[sc]es?(\s*&\s*certifications?)?|courses|training|certificates)$", re.I)),
    ("awards", re.compile(r"^(awards?|honou?rs|achievements|publications|volunteer(ing)?|languages|interests|references)$", re.I)),
]


@dataclass
class Section:
    name: str
    start: int
    end: int
    heading_end: int  # body starts here


def _heading_name(line: str) -> str | None:
    s = line.strip().strip(":").strip()
    s = re.sub(r"^[\W_]+|[\W_]+$", "", s)
    if not s or len(s) > 45 or len(s.split()) > 5:
        return None
    for name, pat in _HEADINGS:
        if pat.match(s):
            return name
    return None


def detect_sections(text: str) -> list[Section]:
    marks: list[tuple[str, int, int]] = []  # name, line_start, line_end
    pos = 0
    for line in text.split("\n"):
        n = _heading_name(line)
        if n:
            marks.append((n, pos, pos + len(line)))
        pos += len(line) + 1
    sections: list[Section] = []
    first = marks[0][1] if marks else len(text)
    if first > 0 and text[:first].strip():
        sections.append(Section("header", 0, first, 0))
    for i, (name, ls, le) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        sections.append(Section(name, ls, end, min(le + 1, end)))
    if not sections:
        sections.append(Section("other", 0, len(text), 0))
    return sections


def section_at(sections: list[Section], pos: int) -> str | None:
    for s in sections:
        if s.start <= pos < s.end:
            return s.name
    return None


def section_text(text: str, sections: list[Section], name: str) -> tuple[str, int]:
    """Concatenate nothing: return the first matching section body and its start offset ('' , 0 when absent)."""
    for s in sections:
        if s.name == name:
            return text[s.heading_end:s.end], s.heading_end
    return "", 0


@dataclass
class ChunkDraft:
    idx: int
    section: str | None
    text: str
    start: int
    end: int
    embedding: list[float] | None = None


MAX_CHUNKS = 40


def chunk_text(text: str, sections: list[Section] | None = None, *, lo: int = 400, hi: int = 800) -> list[ChunkDraft]:
    sections = sections or detect_sections(text)
    total = len(text.strip())
    if total > MAX_CHUNKS * hi * 0.85:  # long document: scale the target so we stay under the cap
        scale = total / (MAX_CHUNKS * hi * 0.85)
        lo, hi = int(lo * scale), int(hi * scale)
    chunks: list[ChunkDraft] = []
    for sec in sections:
        chunks.extend(_chunk_section(text, sec, lo, hi))
    chunks = _merge_tiny(text, chunks, lo // 2)
    chunks = chunks[:MAX_CHUNKS]
    for i, c in enumerate(chunks):
        c.idx = i
    return chunks


def _chunk_section(text: str, sec: Section, lo: int, hi: int) -> list[ChunkDraft]:
    out: list[ChunkDraft] = []
    cur_start: int | None = None
    cur_end = 0
    pos = sec.start
    for line in text[sec.start:sec.end].split("\n"):
        ls, le = pos, pos + len(line)
        pos = le + 1
        if not line.strip():
            continue
        # split over-long single lines
        pieces = [(ls, le)] if le - ls <= hi else _split_long(text, ls, le, hi)
        for ps, pe in pieces:
            if cur_start is None:
                cur_start, cur_end = ps, pe
            elif (pe - cur_start) > hi and (cur_end - cur_start) >= lo:
                out.append(_mk(text, sec.name, cur_start, cur_end))
                cur_start, cur_end = ps, pe
            elif (pe - cur_start) > hi:  # would overflow but current is small: flush anyway
                out.append(_mk(text, sec.name, cur_start, cur_end))
                cur_start, cur_end = ps, pe
            else:
                cur_end = pe
    if cur_start is not None:
        out.append(_mk(text, sec.name, cur_start, cur_end))
    return out


def _split_long(text: str, s: int, e: int, hi: int) -> list[tuple[int, int]]:
    parts, a = [], s
    while e - a > hi:
        cut = text.rfind(" ", a + hi // 2, a + hi)
        cut = cut if cut > a else a + hi
        parts.append((a, cut))
        a = cut + 1 if text[cut:cut + 1] == " " else cut
    parts.append((a, e))
    return parts


def _mk(text: str, section: str, s: int, e: int) -> ChunkDraft:
    return ChunkDraft(0, section, text[s:e], s, e)


def _merge_tiny(text: str, chunks: list[ChunkDraft], min_len: int) -> list[ChunkDraft]:
    out: list[ChunkDraft] = []
    for c in chunks:
        if out and len(c.text) < min_len and out[-1].section == c.section:
            prev = out[-1]
            out[-1] = ChunkDraft(0, prev.section, text[prev.start:c.end], prev.start, c.end)
            continue
        out.append(c)
    return out
