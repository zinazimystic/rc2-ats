"""Deterministic fallback extractor (and recall booster): taxonomy scan + regex for sections, roles, degrees, dates."""
from __future__ import annotations

import re

from app.schemas.resume import EducationItem, ExperienceItem, ParsedResume, ProjectItem
from app.services.parsing import dates
from app.services.parsing.normalizer import taxonomy
from app.services.parsing.redaction import URL_RE
from app.services.parsing.sections import Section, section_text
from app.services.parsing.types import SkillDraft
from app.services.parsing.verifier import line_around

_BULLET = re.compile(r"^\s*(?:[-•*·▪◦●–]|\d+[.)])\s+")
_TITLE_WORDS = re.compile(
    r"\b(engineer|developer|programmer|manager|analyst|intern|internship|lead|architect|consultant|designer|scientist|administrator|"
    r"specialist|director|officer|coordinator|associate|executive|assistant|technician|tester|qa|devops|sre|head|founder|"
    r"freelance[r]?|trainee|supervisor|representative|recruiter|accountant|teacher|lecturer|researcher)\b",
    re.I,
)
_LEVELS: list[tuple[str, re.Pattern]] = [
    ("phd", re.compile(r"\bph\.?\s?d\b|\bdoctorate\b|\bdoctor of\b", re.I)),
    ("master", re.compile(r"\bmaster'?s?\b|\bm\.?\s?sc\b|\bmba\b|\bm\.?\s?tech\b|\bm\.?\s?eng\b|\bmca\b|\bpost[- ]?graduate\b|\bM\.?S\.?(?=\s+in\b|,)|\bM\.?A\.?(?=\s+in\b|,)", re.I)),
    ("bachelor", re.compile(r"\bbachelor'?s?\b|\bb\.?\s?sc\b|\bb\.?\s?tech\b|\bb\.?\s?eng\b|\bbca\b|\bundergraduate\b|\bB\.?E\.?(?=\s+in\b|,|\s+\()|\bB\.?S\.?(?=\s+in\b|,)|\bB\.?A\.?(?=\s+in\b|,)", re.I)),
    ("diploma", re.compile(r"\bdiploma\b|\bassociate'?s?\s+degree\b|\bassociate of\b", re.I)),
    ("high_school", re.compile(r"\bhigh school\b|\bsecondary school\b|\ba[- ]levels?\b|\bhsc\b|\bssc\b|\bintermediate\b|\bgcse\b", re.I)),
]
_INSTITUTION = re.compile(r"\b(university|college|institute|school|academy|polytechnic|universit[àé]t?)\b", re.I)
_SPLIT = re.compile(r"\s+\|\s+|\s+@\s+|\s+at\s+|\s+[–—-]\s+|,\s+|\s{3,}|\t")


def _strip_bullet(s: str) -> str:
    return _BULLET.sub("", s).strip()


def _evidence_for(text: str, start: int, end: int, cap: int = 300) -> tuple[str, int, int]:
    end = min(end, start + cap)
    s = text[start:end]
    lead = len(s) - len(s.lstrip())
    s2 = s.strip()
    return s2, start + lead, start + lead + len(s2)


# --------------------------------------------------------------------------- skills
def scan_skills(text: str, sections: list[Section]) -> list[SkillDraft]:
    """Every taxonomy skill literally present in the text, with the most informative occurrence as evidence."""
    tax = taxonomy()
    best: dict[str, tuple[int, int, str, int]] = {}  # name -> (rank, start, matched, end)
    sec_rank = {"experience": 0, "projects": 0, "summary": 1, "other": 1, "header": 2, "education": 2, "certifications": 2, "skills": 3, "awards": 3}

    def rank_at(pos: int) -> int:
        for s in sections:
            if s.start <= pos < s.end:
                return sec_rank.get(s.name, 2)
        return 2

    for h in tax.find(text):
        r = rank_at(h.start)
        cur = best.get(h.name)
        if cur is None or r < cur[0]:
            best[h.name] = (r, h.start, h.matched, h.end)
    out: list[SkillDraft] = []
    for name, (_, s, matched, e) in best.items():
        ls, le = line_around(text, s, e)
        ev, es, ee = _evidence_for(text, ls, le, 240)
        out.append(SkillDraft(name, matched, tax.category(name), ev, es, ee, "verified", "rules"))
    return out


# --------------------------------------------------------------------------- experience
def _split_header(parts_src: list[str]) -> tuple[str | None, str | None]:
    title = company = None
    for src in parts_src:
        for tok in [t.strip(" -–—|,") for t in _SPLIT.split(src) if t and t.strip(" -–—|,")]:
            if _TITLE_WORDS.search(tok) and title is None:
                title = tok
            elif company is None and not _BULLET.match(tok):
                company = tok
    if title and company and title == company:
        company = None
    return title, company


def parse_experience(text: str, sections: list[Section]) -> list[ExperienceItem]:
    body, base = section_text(text, sections, "experience")
    if not body.strip():
        return []
    lines: list[tuple[int, int, str]] = []
    pos = base
    for ln in body.split("\n"):
        lines.append((pos, pos + len(ln), ln))
        pos += len(ln) + 1
    anchors = []  # (line index, match)
    for i, (_, _, ln) in enumerate(lines):
        if _BULLET.match(ln):
            continue
        m = dates.RANGE_RE.search(ln)
        if m and dates.parse_date(m["s"]):
            anchors.append((i, m))
    items: list[ExperienceItem] = []
    tax = taxonomy()
    for k, (i, m) in enumerate(anchors):
        ls, le, ln = lines[i]
        remnant = (ln[: m.start()] + " " + ln[m.end():]).strip(" \t|,-–—()")
        header_from = i
        prev = lines[i - 1][2] if i > 0 else ""
        prev_ok = (
            i > 0
            and prev.strip()
            and not _BULLET.match(prev)
            and len(prev.strip()) <= 100
            and not dates.RANGE_RE.search(prev)
            and (k == 0 or i - 1 > anchors[k - 1][0])
        )
        # the previous line belongs to this role when the date line itself lacks a title or company
        if prev_ok and (len(remnant) < 3 or not _TITLE_WORDS.search(remnant) or "|" not in remnant and "," not in remnant and " at " not in remnant):
            header_from = i - 1
            src = [prev, remnant]
        else:
            src = [remnant]
        title, company = _split_header(src)
        # description runs until the next role's header
        nxt = anchors[k + 1][0] if k + 1 < len(anchors) else len(lines)
        if k + 1 < len(anchors):
            ni = anchors[k + 1][0]
            pl = lines[ni - 1][2] if ni > 0 else ""
            if ni - 1 > i and pl.strip() and not _BULLET.match(pl) and len(pl.strip()) <= 100:
                nxt = ni - 1
            else:
                nxt = ni
        desc_lines = [_strip_bullet(l[2]) for l in lines[i + 1 : nxt] if l[2].strip()]
        description = "\n".join(desc_lines).strip() or None
        s_iv = dates.parse_date(m["s"])
        e_raw = m["e"]
        current = e_raw.strip().lower() in dates.PRESENT
        e_iv = None if current else dates.parse_date(e_raw, end=True)
        hs = lines[header_from][0]
        ev, es, ee = _evidence_for(text, hs, le)
        skills = tax.skills_in((description or "") + " " + " ".join(src))
        items.append(
            ExperienceItem(
                title=title, company=company, start_date=dates.iso_month(s_iv), end_date=dates.iso_month(e_iv),
                current=current, description=description, skills=skills, evidence=ev, start=es, end=ee,
            )
        )
    return items


# --------------------------------------------------------------------------- education
def _level_of(line: str) -> str | None:
    for level, rx in _LEVELS:
        if rx.search(line):
            return level
    return None


def parse_education(text: str, sections: list[Section]) -> list[EducationItem]:
    body, base = section_text(text, sections, "education")
    whole = False
    if not body.strip():
        body, base, whole = text, 0, True
    items: list[EducationItem] = []
    lines: list[tuple[int, str]] = []
    pos = base
    for ln in body.split("\n"):
        lines.append((pos, ln))
        pos += len(ln) + 1
    used: set[int] = set()
    for i, (p, ln) in enumerate(lines):
        if i in used or not ln.strip():
            continue
        level = _level_of(ln)
        if not level:
            continue
        if whole and not (_INSTITUTION.search(ln) or re.search(r"\b(degree|in|of)\b", ln, re.I)):
            continue
        if level == "high_school" and whole:
            continue
        window = [ln] + [l for _, l in lines[i + 1 : i + 3] if l.strip() and not _level_of(l)]
        joined = " ".join(window)
        inst = None
        for w in window:
            if _INSTITUTION.search(w):
                inst = next((t.strip() for t in re.split(r"\s*[|,–—]\s*|\s+-\s+", w) if _INSTITUTION.search(t)), w.strip())
                break
        fm = re.search(r"\b(?:in|of)\s+([A-Z][A-Za-z&/ ]{2,50}?)(?=\s*(?:[,|(\-–—]|$|\bfrom\b|\bat\b))", ln)
        years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", joined)]
        ev, es, ee = _evidence_for(text, p, p + len(ln))
        items.append(
            EducationItem(
                degree=_strip_bullet(ln)[:160], level=level, field=fm.group(1).strip() if fm else None, institution=inst,
                start_year=min(years) if len(years) > 1 else None, end_year=max(years) if years else None,
                evidence=ev, start=es, end=ee,
            )
        )
        used.update({i})
    return items[:6]


# --------------------------------------------------------------------------- projects / certs / misc
def parse_projects(text: str, sections: list[Section]) -> list[ProjectItem]:
    body, base = section_text(text, sections, "projects")
    if not body.strip():
        return []
    tax = taxonomy()
    blocks: list[dict] = []
    pos = base
    for ln in body.split("\n"):
        s, e = pos, pos + len(ln)
        pos = e + 1
        if not ln.strip():
            continue
        is_bullet = bool(_BULLET.match(ln))
        cur = blocks[-1] if blocks else None
        if not is_bullet and len(ln.strip()) <= 100 and (cur is None or cur["desc"]):
            blocks.append({"head": ln.strip(), "hs": s, "he": e, "desc": [], "end": e})
        elif cur is not None:
            cur["desc"].append(_strip_bullet(ln))
            cur["end"] = e
    items: list[ProjectItem] = []
    for b in blocks[:8]:
        head = b["head"]
        name, tail = head, ""
        m = re.match(r"^(.{3,60}?)\s+(?:[–—]|-|\|)\s+(.+)$", head)
        if m:
            name, tail = m.group(1), m.group(2)
        desc = " ".join(([tail] if tail else []) + b["desc"]).strip()
        blob = head + " " + desc
        url = URL_RE.search(blob)
        ev, es, ee = _evidence_for(text, b["hs"], b["end"], 400)
        items.append(
            ProjectItem(
                name=_strip_bullet(name)[:120], description=desc or None, tech=tax.skills_in(blob),
                url=url.group(0) if url else None, evidence=ev, start=es, end=ee,
            )
        )
    return items


def parse_certifications(text: str, sections: list[Section]) -> list[str]:
    body, _ = section_text(text, sections, "certifications")
    out = []
    for ln in body.split("\n"):
        t = _strip_bullet(ln)
        if 4 <= len(t) <= 140:
            out.append(t)
    return out[:15]


def years_claimed(text: str) -> float | None:
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?(?:\s+(?:professional|relevant|total|hands-on))?(?:\s+(?:work\s+)?experience)?", text, re.I)
    if m:
        v = float(m.group(1))
        return v if 0 < v <= 50 else None
    return None


def extract(text: str, sections: list[Section]) -> tuple[ParsedResume, list[SkillDraft]]:
    summary_body, _ = section_text(text, sections, "summary")
    summary = re.sub(r"\s+", " ", summary_body).strip()[:600] or None
    parsed = ParsedResume(
        summary=summary,
        education=parse_education(text, sections),
        experience=parse_experience(text, sections),
        projects=parse_projects(text, sections),
        certifications=parse_certifications(text, sections),
        total_years_claimed=years_claimed(text),
    )
    return parsed, scan_skills(text, sections)
