from tests.api_helpers import fake_pipeline, future, make_job, world  # noqa: F401


def test_empty_dashboard(make_client):
    rec = make_client("recruiter", "r@example.com")
    d = rec.get("/api/analytics/overview").json()
    assert d["kpis"]["total_jobs"] == 0 and d["shortlist_rate"] is None and d["avg_processing_seconds"] is None
    assert [b["count"] for b in d["score_distribution"]] == [0] * 5 and d["recent_activity"] == []


def test_dashboard_updates_with_pipeline(world):
    w = world
    d = w.rec.get("/api/analytics/overview").json()
    assert d["kpis"]["active_jobs"] == 1 and d["kpis"]["total_applications"] == 3 and d["kpis"]["pending_reviews"] == 3
    assert d["kpis"]["shortlisted"] == 0 and d["avg_processing_seconds"] is not None
    assert sum(b["count"] for b in d["score_distribution"]) == 3
    assert d["score_distribution"][4]["count"] == 1 and d["score_distribution"][0]["count"] == 1  # alice 100, carol 0
    gaps = {g["skill"]: g for g in d["top_skill_gaps"]}
    assert gaps["Python"]["count"] == 1 and gaps["Django"]["count"] == 2 and gaps["Django"]["percent"] == 66.7
    assert d["applications_by_job"][0]["by_stage"] == {"ai_assessed": 3}
    aid = w.apps["alice"]["id"]
    w.rec.post(f"/api/applications/{aid}/transition", json={"to_status": "shortlisted"})
    w.rec.post(f"/api/applications/{aid}/interviews",
               json={"interviewer_name": "Ivy", "start_at": future(48)})
    w.rec.post(f"/api/applications/{w.apps['carol']['id']}/transition", json={"to_status": "rejected", "reason": "gap"})
    d = w.rec.get("/api/analytics/overview").json()
    k = d["kpis"]
    assert (k["shortlisted"], k["interviews_scheduled"], k["rejected"], k["pending_reviews"]) == (1, 1, 1, 1)
    assert d["shortlist_rate"] == 0.333 and d["avg_time_to_decision_hours"] is not None
    assert {s["stage"]: s["count"] for s in d["stage_funnel"]}["interview"] == 1
    assert d["recent_activity"] and "Alice Tester" in " ".join(a["text"] for a in d["recent_activity"])
    # per-job filter and isolation
    assert w.rec.get(f"/api/analytics/overview?job_id={w.job['id']}").json()["job_filter"]["id"] == w.job["id"]
    assert w.rec2.get("/api/analytics/overview").json()["kpis"]["total_applications"] == 0
    assert w.cands["alice"].get("/api/analytics/overview").status_code == 403


def test_withdrawn_excluded_from_totals(world):
    w = world
    w.cands["bob"].post(f"/api/applications/{w.apps['bob']['id']}/withdraw")
    assert w.rec.get("/api/analytics/overview").json()["kpis"]["total_applications"] == 2


def test_duplicates_and_talent_endpoints_use_ai_module(world, monkeypatch):
    from app.models import DuplicateFlag, User
    from app.db.session import SessionLocal
    from app.schemas.search import TalentSearchOut
    from app.services import duplicates, search

    w = world
    with SessionLocal() as db:
        a = db.query(User).filter_by(email="alice@example.com").one()
        b = db.query(User).filter_by(email="bob@example.com").one()
        flag = DuplicateFlag(candidate_a_id=a.id, candidate_b_id=b.id, reasons=["same phone"], similarity=0.93)
        db.add(flag)
        db.commit()
        fid = str(flag.id)
    lst = w.rec.get("/api/duplicates").json()
    assert len(lst) == 1 and lst[0]["reasons"] == ["same phone"]
    assert w.rec2.get("/api/duplicates").json() == [] and w.rec2.post(f"/api/duplicates/{fid}/confirm").status_code == 404
    merged = []
    monkeypatch.setattr(duplicates, "merge", lambda db, flag, actor: merged.append(flag.id))
    assert w.rec.post(f"/api/duplicates/{fid}/confirm").json()["status"] == "confirmed" and merged
    assert w.rec.post(f"/api/duplicates/{fid}/dismiss").status_code == 409
    assert w.rec.get("/api/duplicates").json() == []
    assert len(w.rec.get("/api/duplicates?status=confirmed").json()) == 1

    monkeypatch.setattr(search, "talent_search", lambda db, u, req: TalentSearchOut(query=req.query, mode="keyword"))
    assert w.rec.post("/api/search/talent", json={"query": "python django"}).json()["mode"] == "keyword"
    assert w.rec.post("/api/search/talent", json={"query": "python", "job_id": w.job["id"]}).status_code == 200
    assert w.rec2.post("/api/search/talent", json={"query": "python", "job_id": w.job["id"]}).status_code == 404
    assert w.rec.post("/api/search/talent", json={"query": "p"}).status_code == 422
    assert w.cands["alice"].post("/api/search/talent", json={"query": "python"}).status_code == 403


def test_invite_from_talent_pool(world):
    w = world
    cid = w.cands["alice"].user["id"]
    job2 = w.rec.post("/api/jobs", json={"title": "Platform Engineer", "description": "Platform engineering with Docker and Kubernetes."}).json()
    assert w.rec.post(f"/api/jobs/{w.job['id']}/talent-pool/{cid}/invite").status_code == 409  # already applied
    r = w.rec.post(f"/api/jobs/{job2['id']}/talent-pool/{cid}/invite")
    assert r.status_code == 200 and r.json()["detail"] == "Invitation sent"
    assert w.rec.post(f"/api/jobs/{job2['id']}/talent-pool/{cid}/invite").json()["detail"] == "Candidate was already invited"
    assert any("invited" in n["title"] for n in w.cands["alice"].get("/api/notifications").json())
    assert w.rec2.post(f"/api/jobs/{job2['id']}/talent-pool/{cid}/invite").status_code == 404
    assert w.rec.post(f"/api/jobs/{job2['id']}/talent-pool/{w.rec.user['id']}/invite").status_code == 404
