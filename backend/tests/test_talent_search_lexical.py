"""Talent search must find exact, case-insensitive mentions such as '.NET', 'C#' and 'Node.js' even when embeddings say little."""
from __future__ import annotations

import pytest

from app.models import Application, Job, Resume, User
from app.schemas.search import TalentSearchIn
from app.services import search
from app.services.search import _term_groups
from app.services.parsing.normalizer import taxonomy


def test_term_groups_expand_aliases_and_keep_symbols():
    tax = taxonomy()
    groups = dict(_term_groups(".NET developers with C#", tax.skills_in(".NET developers with C#"), tax))
    assert ".NET" in groups and "dotnet" in groups[".NET"] and ".net" in groups[".NET"]
    assert "C#" in groups


@pytest.mark.parametrize("query", [".net", ".NET", "dotnet", "Asp.Net core", "NET developer .net", "c#"])
def test_dotnet_resume_is_found_case_insensitively(db, query):
    rec = User(email="r@x.com", password_hash="x", full_name="Rec", role="recruiter")
    cand = User(email="c@x.com", password_hash="x", full_name="Dev Eloper", role="candidate")
    db.add_all([rec, cand]); db.flush()
    job = Job(recruiter_id=rec.id, title="Backend", description="d" * 20)
    db.add(job); db.flush()
    db.add(Application(job_id=job.id, candidate_id=cand.id))
    db.add(Resume(candidate_id=cand.id, filename="a.pdf", sha256="s", size=1, parse_status="parsed", is_current=True,
                  text="Senior engineer. Built services in C# and ASP.NET Core on the .NET platform, SQL Server."))
    db.commit()
    out = search.talent_search(db, rec, TalentSearchIn(query=query))
    assert [r.candidate.full_name for r in out.results] == ["Dev Eloper"], out
    assert out.results[0].evidence, "an exact mention must come with a quote"


def test_no_false_positive_for_substrings(db):
    rec = User(email="r2@x.com", password_hash="x", full_name="Rec", role="recruiter")
    cand = User(email="c2@x.com", password_hash="x", full_name="Js Dev", role="candidate")
    db.add_all([rec, cand]); db.flush()
    job = Job(recruiter_id=rec.id, title="FE", description="d" * 20)
    db.add(job); db.flush()
    db.add(Application(job_id=job.id, candidate_id=cand.id))
    db.add(Resume(candidate_id=cand.id, filename="a.pdf", sha256="s2", size=1, parse_status="parsed", is_current=True,
                  text="Frontend developer using JavaScript and the internet."))
    db.commit()
    assert search.talent_search(db, rec, TalentSearchIn(query="java")).results == []
    assert search.talent_search(db, rec, TalentSearchIn(query=".net")).results == []
