"""Resume -> structured data. LLM extraction on redacted text, every quote verified against the original; rules fallback."""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Flag
from app.schemas.resume import EducationItem, ExperienceItem, ParsedResume, ProjectItem
from app.services.ai import llm, prompts
from app.services.parsing import dates, rules_extractor
from app.services.parsing.normalizer import taxonomy
from app.services.parsing.redaction import extract_contacts, redact
from app.services.parsing.sections import detect_sections
from app.services.parsing.types import Extraction, SkillDraft
from app.services.parsing.verifier import Index

log = logging.getLogger("app.parsing")
_LEVELS = {"none", "high_school", "diploma", "bachelor", "master", "phd"}
_RANK = {"verified": 0, "fuzzy": 1, "unverified": 2}


# --------------------------------------------------------------------------- LLM output schema (lenient)
class _Skill(BaseModel):
    name: str
    category: str | None = None
    evidence: str | None = None


class _Exp(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    description: str | None = None
    skills: list[str] = []
    evidence: str | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _s(cls, v):
        return None if v is None else str(v)


class _Edu(BaseModel):
    degree: str | None = None
    level: str | None = None
    field: str | None = None
    institution: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    evidence: str | None = None

    @field_validator("start_year", "end_year", mode="before")
    @classmethod
    def _y(cls, v):
        try:
            return int(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None


class _Proj(BaseModel):
    name: str | None = None
    description: str | None = None
    tech: list[str] = []
    url: str | None = None
    evidence: str | None = None


class LLMExtraction(BaseModel):
    summary: str | None = None
    skills: list[_Skill] = []
    experience: list[_Exp] = []
    education: list[_Edu] = []
    projects: list[_Proj] = []
    certifications: list[str] = []
    total_years_claimed: float | None = None

    @field_validator("total_years_claimed", mode="before")
    @classmethod
    def _t(cls, v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None


# --------------------------------------------------------------------------- helpers
def _best(a: SkillDraft | None, b: SkillDraft) -> SkillDraft:
    if a is None:
        return b
    return b if _RANK[b.verification] < _RANK[a.verification] else a


def _month(raw: str | None, *, end: bool = False) -> str | None:
    if not raw:
        return None
    d = dates.parse_date(raw, end=end)
    if d is None:
        return None
    return d.strftime("%Y-%m") if len(raw.strip()) > 4 else d.strftime("%Y")


def _ev(v) -> dict:  # noqa: ANN001
    return {"evidence": v.quote[:300] if v.quote else None, "start": v.start, "end": v.end, "verification": v.verification}


def _skill_supported(name: str, quote: str) -> bool:
    tax = taxonomy()
    canon = tax.canonical(name)
    if canon in tax.skills_in(quote):
        return True
    return bool(re.search(r"(?<![A-Za-z0-9+#])" + re.escape(name.strip()) + r"(?![A-Za-z0-9+#])", quote, re.I))


def _llm_extract(redacted_text: str) -> LLMExtraction:
    return llm.json_call(
        prompts.RESUME_EXTRACT_SYSTEM,
        f"<resume>\n{redacted_text}\n</resume>\nReturn the json object now.",
        LLMExtraction,
        max_tokens=4000,
        cache_kind="resume_extract",
    )


# --------------------------------------------------------------------------- main entry
def extract(text: str, names: list[str] | tuple[str, ...] = ()) -> Extraction:
    """Extract structured data from the ORIGINAL resume text. Offsets in the result index into `text`."""
    tax = taxonomy()
    sections = detect_sections(text)
    red = redact(text, list(names))
    idx = Index(text, red)
    contact = extract_contacts(text, names[0] if names else None)
    rules_parsed, rules_skills = rules_extractor.extract(text, sections)
    rules_by_name = {s.name: s for s in rules_skills}
    warnings: list[str] = []
    flags: list[Flag] = []

    out: LLMExtraction | None = None
    if llm.llm_available():
        try:
            out = _llm_extract(red.text)
        except llm.LLMUnavailable as exc:
            warnings.append(f"AI extraction unavailable ({exc}); used rule-based extraction.")
        except llm.LLMError as exc:
            warnings.append(f"AI extraction failed ({exc}); used rule-based extraction.")
        except Exception as exc:  # never let a provider problem fail the resume
            log.warning("unexpected LLM failure: %s", exc)
            warnings.append("AI extraction failed unexpectedly; used rule-based extraction.")
    else:
        warnings.append("AI extraction is not configured; used rule-based extraction (evidence still verified).")

    if out is None:
        parsed = rules_parsed.model_copy(update={"contact": contact})
        return Extraction(parsed, rules_skills, "rules", warnings, flags)

    # ---- skills
    merged: dict[str, SkillDraft] = {}
    unverified = 0
    for s in out.skills[:200]:
        raw = (s.name or "").strip()
        if not raw or len(raw) > 80:
            continue
        canon = tax.canonical(raw)
        v = idx.verify(s.evidence)
        status = v.verification
        if status != "unverified" and v.quote and not _skill_supported(raw, v.quote):
            status = "unverified"  # the quote does not actually mention the skill
        if status == "unverified" and canon in rules_by_name:
            r = rules_by_name[canon]  # the skill is literally in the resume: use the scanner's evidence
            d = SkillDraft(canon, raw, tax.category(canon) or s.category, r.evidence, r.start, r.end, "verified", "ai")
        elif status == "unverified":
            d = SkillDraft(canon, raw, tax.category(canon) or s.category, (s.evidence or None) and s.evidence[:300], None, None, "unverified", "ai")
        else:
            d = SkillDraft(canon, raw, tax.category(canon) or s.category, v.quote[:300] if v.quote else None, v.start, v.end, status, "ai")
        merged[canon] = _best(merged.get(canon), d)
    for name, r in rules_by_name.items():  # recall: anything literally present counts
        if name not in merged:
            merged[name] = r
    unverified = sum(1 for s in merged.values() if s.verification == "unverified")
    skills = sorted(merged.values(), key=lambda s: s.name.lower())

    # ---- experience
    exp: list[ExperienceItem] = []
    for e in out.experience[:20]:
        v = idx.verify(e.evidence)
        sd = _month(e.start_date)
        cur = bool(e.current) or (e.end_date or "").strip().lower() in dates.PRESENT
        ed = None if cur else _month(e.end_date, end=True)
        sk = [tax.canonical(x) for x in e.skills if x and x.strip()]
        desc_skills = tax.skills_in(e.description or "")
        exp.append(
            ExperienceItem(
                title=e.title, company=e.company, start_date=sd or e.start_date, end_date=ed or (None if cur else e.end_date),
                current=cur, description=e.description, skills=sorted(set(sk) | set(desc_skills)), **_ev(v),
            )
        )
    if not exp:
        exp = rules_parsed.experience

    # ---- education
    edu: list[EducationItem] = []
    for e in out.education[:8]:
        v = idx.verify(e.evidence)
        level = e.level if e.level in _LEVELS else rules_extractor._level_of(e.degree or "") or None
        edu.append(
            EducationItem(degree=e.degree, level=level, field=e.field, institution=e.institution,
                          start_year=e.start_year, end_year=e.end_year, **_ev(v))
        )
    if not edu:
        edu = rules_parsed.education

    # ---- projects
    proj: list[ProjectItem] = []
    for p in out.projects[:10]:
        v = idx.verify(p.evidence)
        tech = sorted({tax.canonical(t) for t in p.tech if t and t.strip()} | set(tax.skills_in(p.description or "")))
        proj.append(ProjectItem(name=p.name, description=p.description, tech=tech, url=p.url, **_ev(v)))
    if not proj:
        proj = rules_parsed.projects

    certs = [c.strip() for c in out.certifications if c and c.strip()][:15] or rules_parsed.certifications
    claimed = out.total_years_claimed
    if claimed is not None and not any(abs(float(m) - claimed) < 0.01 for m in re.findall(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", text, re.I)):
        claimed = None  # a claim not stated in the resume is not trusted
    if claimed is None:
        claimed = rules_parsed.total_years_claimed

    bad = sum(1 for i in [*exp, *edu, *proj] if i.verification == "unverified")
    if unverified or bad:
        flags.append(
            Flag(
                type="unverified_claim",
                severity="warning",
                message=f"{unverified + bad} AI-extracted item(s) could not be matched to the resume text. "
                "They get no automatic score credit until a recruiter or the candidate confirms them.",
            )
        )
    parsed = ParsedResume(
        contact=contact, summary=(out.summary or rules_parsed.summary), education=edu, experience=exp, projects=proj,
        certifications=certs, total_years_claimed=claimed,
    )
    return Extraction(parsed, skills, "llm", warnings, flags)


def date_flags(parsed: ParsedResume) -> list[Flag]:
    """Impossible / suspicious dates in experience."""
    flags: list[Flag] = []
    today = dates.today()
    for e in parsed.experience:
        s, en = dates.parse_date(e.start_date), dates.parse_date(e.end_date, end=True)
        if s and en and en < s:
            flags.append(Flag(type="date_inconsistency", severity="warning", message=f"{e.title or 'A role'}: end date is before start date."))
        if s and s > today:
            flags.append(Flag(type="date_inconsistency", severity="warning", message=f"{e.title or 'A role'}: start date is in the future."))
    return flags
