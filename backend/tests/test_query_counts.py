"""N+1 guard: every list/detail endpoint must issue a SMALL, CONSTANT number of SQL statements, independent of data volume.

The world is seeded small, every endpoint is measured, the world is grown ~4x (more candidates, applications, assessments, notes,
interviews, notifications, jobs, resumes) and every endpoint is measured again. Counts must be identical (and under the cap)."""
from __future__ import annotations

import pytest

from tests.query_counter import count_queries
from tests.volume_seed import grow, seed_base

SMALL, LARGE = 12, 48


def _hdr(user):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


class Ctx:
    """Resolved ids used to build request paths."""


def _endpoints(c: Ctx):
    """(name, role, method, path, json, cap) -- cap is the maximum statement count allowed (user row is a cache hit or +1)."""
    J, A, R = c.job_id, c.app_id, c.resume_id
    return [
        ("GET /jobs (recruiter)", "rec", "GET", "/api/jobs", None, 3),
        ("GET /jobs?q&status (recruiter)", "rec", "GET", "/api/jobs?q=backend&status=open", None, 3),
        ("GET /jobs/{id} (recruiter)", "rec", "GET", f"/api/jobs/{J}", None, 3),
        ("GET /jobs/{id}/applications", "rec", "GET", f"/api/jobs/{J}/applications", None, 5),
        ("GET /jobs/{id}/applications sort=name", "rec", "GET", f"/api/jobs/{J}/applications?sort=name", None, 5),
        ("GET /jobs/{id}/applications sort=date", "rec", "GET", f"/api/jobs/{J}/applications?sort=date", None, 5),
        ("GET /jobs/{id}/applications filters", "rec", "GET", f"/api/jobs/{J}/applications?min_score=30&skill=python&q=cand&status=submitted,parsed,ai_assessed", None, 5),
        ("GET /jobs/{id}/compare", "rec", "GET", f"/api/jobs/{J}/compare?ids={','.join(c.compare_ids)}", None, 7),
        ("GET /jobs/{id}/talent-pool", "rec", "GET", f"/api/jobs/{J}/talent-pool", None, 10),
        ("GET /applications/{id}", "rec", "GET", f"/api/applications/{A}", None, 9),
        ("GET /applications/{id}/history", "rec", "GET", f"/api/applications/{A}/history", None, 5),
        ("GET /applications/{id}/notes", "rec", "GET", f"/api/applications/{A}/notes", None, 5),
        ("GET /applications/{id}/questions", "rec", "GET", f"/api/applications/{A}/questions", None, 5),
        ("GET /applications/{id}/interviews", "rec", "GET", f"/api/applications/{A}/interviews", None, 6),
        ("GET /interviews", "rec", "GET", "/api/interviews", None, 6),
        ("GET /interviews?from&to&status", "rec", "GET", "/api/interviews?from=2020-01-01T00:00:00Z&to=2099-01-01T00:00:00Z&status=scheduled", None, 6),
        ("GET /analytics/overview", "rec", "GET", "/api/analytics/overview", None, 8),
        ("GET /analytics/overview?job_id", "rec", "GET", f"/api/analytics/overview?job_id={J}", None, 8),
        ("GET /duplicates", "rec", "GET", "/api/duplicates", None, 6),
        ("GET /notifications (recruiter)", "rec", "GET", "/api/notifications", None, 3),
        ("GET /notifications/outbox", "rec", "GET", "/api/notifications/outbox", None, 3),
        ("POST /search/talent", "rec", "POST", "/api/search/talent", {"query": "python django postgresql backend", "limit": 50}, 8),
        ("GET /resumes/{id} (recruiter)", "rec", "GET", f"/api/resumes/{R}", None, 4),
        ("GET /jobs (candidate)", "cand", "GET", "/api/jobs", None, 3),
        ("GET /jobs/{id} (candidate)", "cand", "GET", f"/api/jobs/{J}", None, 4),
        ("GET /applications/me", "cand", "GET", "/api/applications/me", None, 5),
        ("GET /candidates/me/dashboard", "cand", "GET", "/api/candidates/me/dashboard", None, 10),
        ("GET /candidates/me/resumes", "cand", "GET", "/api/candidates/me/resumes", None, 3),
        ("GET /candidates/me/recommendations", "cand", "GET", "/api/candidates/me/recommendations", None, 6),
        ("GET /candidates/me/profile", "cand", "GET", "/api/candidates/me/profile", None, 4),
        ("GET /resumes/{id} (candidate)", "cand", "GET", f"/api/resumes/{c.cand_resume_id}", None, 3),
        ("GET /jobs/{id}/my-match", "cand", "GET", f"/api/jobs/{J}/my-match", None, 8),
        ("GET /notifications (candidate)", "cand", "GET", "/api/notifications", None, 3),
    ]


def _resolve(db, w) -> Ctx:
    from sqlalchemy import func, select

    from app.models import Application

    c = Ctx()
    counts = dict(db.execute(select(Application.job_id, func.count()).group_by(Application.job_id)).all())
    job = max(w.jobs, key=lambda j: counts.get(j.id, 0))
    apps = [a for a in w.apps if a.job_id == job.id]
    c.job_id, c.app_id, c.resume_id = str(job.id), str(apps[0].id), str(apps[0].resume_id)
    c.compare_ids = [str(a.id) for a in apps[:4]]
    c.cand_resume_id = str(w.resumes[0].id)
    return c


def _measure(client, db, w, c: Ctx):
    from app.core.deps import invalidate_user

    heads = {"rec": _hdr(w.recruiters[0]), "cand": _hdr(w.candidates[0])}
    out = {}
    for name, who, method, path, body, cap in _endpoints(c):
        invalidate_user()  # measure the cold path (user row fetched)
        with count_queries() as qc:
            r = client.request(method, path, headers=heads[who], json=body)
        assert r.status_code == 200, f"{name}: {r.status_code} {r.text[:300]}"
        out[name] = (qc.count, cap, qc)
    return out


def test_statement_counts_are_constant_and_small(client, db):
    w = seed_base(db)
    grow(db, w, SMALL)
    ctx = _resolve(db, w)
    small = _measure(client, db, w, ctx)
    grow(db, w, LARGE - SMALL, extra_jobs=3, extra_for_first=4)
    ctx2 = _resolve(db, w)
    ctx2.job_id, ctx2.app_id, ctx2.resume_id, ctx2.compare_ids = ctx.job_id, ctx.app_id, ctx.resume_id, ctx.compare_ids
    large = _measure(client, db, w, ctx2)

    import os

    only = os.environ.get("QC_VERBOSE")  # e.g. QC_VERBOSE="applications/{id}" prints the statements of matching endpoints
    if only:
        for name, (n, _cap, qc) in large.items():
            if only in name or only == "all":
                print(f"\n== {name}: {n}\n{qc.report(110)}")
    problems = []
    lines = [f"{'endpoint':<48}{'N small':>8}{'N large':>8}{'cap':>5}"]
    for name in small:
        s, cap, _ = small[name]
        l, _, qc = large[name]
        lines.append(f"{name:<48}{s:>8}{l:>8}{cap:>5}")
        if s != l:
            problems.append(f"{name}: {s} statements at N small vs {l} at N large (N+1)\n{qc.report()}")
        if l > cap:
            problems.append(f"{name}: {l} statements exceeds the cap of {cap}\n{qc.report()}")
    print("\n" + "\n".join(lines))
    assert not problems, "\n\n".join(problems)


def test_large_columns_are_not_loaded_by_lists(client, db):
    """file_bytes / text / embeddings must never be selected by list endpoints (they would travel over the 90 ms link)."""
    w = seed_base(db)
    grow(db, w, 6)
    ctx = _resolve(db, w)
    banned = ("resumes.file_bytes", "resumes.text", "resumes.doc_embedding", "jobs.embedding", "resume_chunks.embedding")
    from app.core.deps import invalidate_user

    heads = {"rec": _hdr(w.recruiters[0]), "cand": _hdr(w.candidates[0])}
    offenders = []
    allowed = {  # endpoints that legitimately need a column
        "GET /resumes/{id} (recruiter)": {"resumes.text"},
        "GET /resumes/{id} (candidate)": {"resumes.text"},
        "GET /applications/{id}": {"resumes.text"},  # the evidence view renders the resume text
        "POST /search/talent": {"resumes.text", "resume_chunks.embedding"},  # semantic search on SQLite loads chunk vectors
    }
    scoring = {"jobs.embedding", "resume_chunks.embedding"}  # endpoints that SCORE a resume against a job need the vectors
    for n in ("GET /candidates/me/dashboard", "GET /candidates/me/recommendations", "GET /jobs/{id}/my-match", "GET /jobs/{id}/talent-pool"):
        allowed[n] = scoring
    for name, who, method, path, body, _cap in _endpoints(ctx):
        invalidate_user()
        with count_queries() as qc:
            client.request(method, path, headers=heads[who], json=body)
        for s in qc.statements:
            sel = s.split(" FROM ")[0] if s.upper().startswith("SELECT") else ""
            for col in banned:
                if col in sel and col not in allowed.get(name, set()):
                    offenders.append(f"{name} loads {col}: {s[:200]}")
    assert not offenders, "\n".join(sorted(set(offenders)))
