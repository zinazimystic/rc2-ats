"""Tolerant date parsing + interval maths for work-experience calculations."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.db.types import utcnow

_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
            ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"),
            ("nov", "november"), ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
PRESENT = {"present", "current", "now", "ongoing", "today", "till date", "to date", "date"}
_DATE = r"(?:(?:[A-Za-z]{3,9})\.?,?\s+\d{4}|\d{1,2}/\d{4}|\d{4}-\d{1,2}|\d{4})"
RANGE_RE = re.compile(
    rf"(?P<s>{_DATE})\s*(?:-|–|—|to|until|till)\s*(?P<e>present|current|now|ongoing|today|{_DATE})",
    re.I,
)


def today() -> date:
    return utcnow().date()


def parse_date(raw: str | None, *, end: bool = False) -> date | None:
    """'Jan 2020' | '2020-01' | '01/2020' | '2020' | 'Present' -> date (first of month; year-only end -> Dec)."""
    if not raw:
        return None
    s = raw.strip().lower().rstrip(".,")
    if s in PRESENT:
        return today()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m:
        return _mk(int(m[1]), int(m[2]))
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", s)
    if m:
        return _mk(int(m[2]), int(m[1]))
    m = re.fullmatch(r"([a-z]{3,9})\.?,?\s+(\d{4})", s)
    if m and m[1] in _MONTHS:
        return _mk(int(m[2]), _MONTHS[m[1]])
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return _mk(int(m[1]), 12 if end else 1)
    return None


def _mk(year: int, month: int) -> date | None:
    if not (1950 <= year <= today().year + 6) or not (1 <= month <= 12):
        return None
    return date(year, month, 1)


def iso_month(d: date | None) -> str | None:
    return d.strftime("%Y-%m") if d else None


@dataclass(frozen=True)
class Interval:
    start: date
    end: date

    @property
    def months(self) -> int:
        return max(0, (self.end.year - self.start.year) * 12 + (self.end.month - self.start.month) + 1)


def to_interval(start: str | None, end: str | None, current: bool = False) -> Interval | None:
    s = parse_date(start)
    e = today() if current else parse_date(end, end=True)
    if s is None or e is None:
        return None
    if e < s:
        return None
    if e > today():
        e = today()
    return Interval(s, e)


def merge(intervals: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for iv in sorted(intervals, key=lambda i: (i.start, i.end)):
        if out and iv.start <= _next_month(out[-1].end):
            if iv.end > out[-1].end:
                out[-1] = Interval(out[-1].start, iv.end)
        else:
            out.append(iv)
    return out


def _next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def total_years(intervals: list[Interval]) -> float:
    return round(sum(i.months for i in merge(intervals)) / 12.0, 2)


def subtract_years(all_iv: list[Interval], relevant: list[Interval]) -> float:
    """Years covered by `all_iv` but not by `relevant` (month granularity)."""
    def months(ivs: list[Interval]) -> set[int]:
        s: set[int] = set()
        for i in ivs:
            y, m = i.start.year, i.start.month
            while (y, m) <= (i.end.year, i.end.month):
                s.add(y * 12 + m)
                m += 1
                if m > 12:
                    y, m = y + 1, 1
        return s

    return round(len(months(all_iv) - months(relevant)) / 12.0, 2)


def relevant_years(relevant: list[Interval]) -> float:
    return total_years(relevant)
