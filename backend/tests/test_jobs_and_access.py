from tests.api_helpers import JOB_BODY, apply_to, fake_pipeline, make_job, upload, world  # noqa: F401


def test_job_crud_and_validation(make_client):
    rec = make_client("recruiter", "r@example.com")
    job = make_job(rec)
    assert job["version"] == 1 and job["weights"]["skills"] == 50 and len(job["requirements"]) == 3
    assert rec.post("/api/jobs", json={**JOB_BODY, "title": "x"}).status_code == 422
    bad = {**JOB_BODY, "weights": {"skills": 60, "experience": 30, "projects": 15, "qualifications": 10}}
    assert rec.post("/api/jobs", json=bad).status_code == 422
    assert rec.post("/api/jobs", json={**JOB_BODY, "salary_min": 10, "salary_max": 5}).status_code == 422
    # duplicate skills collapse to one requirement
    dup = {**JOB_BODY, "requirements": [{"skill": "Python"}, {"skill": "python", "importance": 5}]}
    assert len(rec.post("/api/jobs", json=dup).json()["requirements"]) == 1
    listing = rec.get("/api/jobs").json()
    assert len(listing) == 2 and listing[0]["required_skills"]


def test_update_bumps_version_only_for_scoring_fields(make_client):
    rec = make_client("recruiter", "r@example.com")
    job = make_job(rec)
    r = rec.patch(f"/api/jobs/{job['id']}", json={"title": "Senior Backend Developer", "location": "Remote"})
    assert r.json()["version"] == 1 and r.json()["title"] == "Senior Backend Developer"
    r = rec.patch(f"/api/jobs/{job['id']}", json={"min_experience_years": 5})
    assert r.json()["version"] == 2
    reqs = [{"skill": "Python", "kind": "required", "importance": 5}, {"skill": "FastAPI", "kind": "required", "importance": 3}]
    r = rec.patch(f"/api/jobs/{job['id']}", json={"requirements": reqs})
    assert r.json()["version"] == 3 and [x["skill"] for x in r.json()["requirements"]] == ["Python", "FastAPI"]
    # same requirements again: no bump; Python row keeps its id
    r2 = rec.patch(f"/api/jobs/{job['id']}", json={"requirements": reqs})
    assert r2.json()["version"] == 3
    assert r2.json()["requirements"][0]["id"] == r.json()["requirements"][0]["id"]
    assert rec.patch(f"/api/jobs/{job['id']}", json={}).status_code == 200


def test_job_update_requeues_assessments_and_marks_stale(world):
    w = world
    before = w.rec.get(f"/api/applications/{w.apps['alice']['id']}").json()["assessment"]
    assert before["stale"] is False
    w.rec.patch(f"/api/jobs/{w.job['id']}", json={"min_experience_years": 9})
    after = w.rec.get(f"/api/applications/{w.apps['alice']['id']}").json()["assessment"]
    assert after["job_version"] == 2 and after["stale"] is False  # eager re-scoring ran


def test_other_recruiter_gets_404_everywhere(world):
    w, aid, jid = world, world.apps["alice"]["id"], world.job["id"]
    for method, path in [
        ("get", f"/api/jobs/{jid}"), ("get", f"/api/jobs/{jid}/applications"), ("get", f"/api/applications/{aid}"),
        ("get", f"/api/applications/{aid}/history"), ("get", f"/api/applications/{aid}/notes"),
        ("get", f"/api/applications/{aid}/questions"), ("get", f"/api/applications/{aid}/interviews"),
        ("get", f"/api/jobs/{jid}/talent-pool"), ("get", f"/api/analytics/overview?job_id={jid}"),
    ]:
        r = getattr(w.rec2, method)(path)
        assert r.status_code == 404, (path, r.status_code)
    assert w.rec2.patch(f"/api/jobs/{jid}", json={"title": "Hacked title"}).status_code == 404
    assert w.rec2.post(f"/api/jobs/{jid}/close").status_code == 404
    assert w.rec2.post(f"/api/applications/{aid}/transition", json={"to_status": "recruiter_review"}).status_code == 404
    assert w.rec2.post(f"/api/applications/{aid}/override", json={"score": 99, "reason": "because"}).status_code == 404
    assert w.rec2.get("/api/jobs").json() == []
    assert w.rec2.get(f"/api/jobs/{jid}/compare?ids={aid},{w.apps['bob']['id']}").status_code == 404


def test_candidate_job_visibility(world, make_client):
    w = world
    newbie = make_client("candidate", "new@example.com", "New Person")
    r = newbie.get("/api/jobs").json()
    assert len(r) == 1 and r[0]["has_applied"] is False and r[0]["applicant_count"] == 0
    assert w.cands["alice"].get("/api/jobs").json()[0]["has_applied"] is True
    detail = newbie.get(f"/api/jobs/{w.job['id']}").json()
    assert detail["applicant_count"] == 0 and detail["has_applied"] is False
    assert newbie.post(f"/api/jobs/{w.job['id']}/close").status_code == 403
    w.rec.post(f"/api/jobs/{w.job['id']}/close")
    assert newbie.get("/api/jobs").json() == []
    assert newbie.get(f"/api/jobs/{w.job['id']}").status_code == 404
    assert w.cands["alice"].get(f"/api/jobs/{w.job['id']}").status_code == 200  # applicants keep access


def test_close_reopen_and_apply_to_closed(world, make_client):
    w = world
    assert w.rec.post(f"/api/jobs/{w.job['id']}/close").json()["status"] == "closed"
    assert w.rec.post(f"/api/jobs/{w.job['id']}/close").status_code == 409
    newbie = make_client("candidate", "n2@example.com", "Bob Second")
    upload(newbie)
    r = apply_to(newbie, w.job["id"])
    assert r.status_code == 409 and r.json()["code"] == "job_closed"
    assert w.rec.post(f"/api/jobs/{w.job['id']}/reopen").json()["status"] == "open"
    assert apply_to(newbie, w.job["id"]).status_code == 201


def test_job_list_counts_and_filter(world):
    w = world
    row = w.rec.get("/api/jobs").json()[0]
    assert row["applicant_count"] == 3 and row["pending_review_count"] == 3 and row["shortlisted_count"] == 0
    assert w.rec.get("/api/jobs?status=closed").json() == []
    assert len(w.rec.get("/api/jobs?q=backend").json()) == 1
    assert w.rec.get("/api/jobs?q=zzz").json() == []


def test_extract_requirements_uses_ai_module(make_client, monkeypatch):
    from app.schemas.job import ExtractedSkill, JobExtractOut
    from app.services import jobs_ai
    from app.services.ai import llm

    rec = make_client("recruiter", "r@example.com")
    monkeypatch.setattr(jobs_ai, "extract_job_requirements",
                        lambda t, d: JobExtractOut(required_skills=[ExtractedSkill(skill="Python")], method="rules"))
    body = {"description": "We need someone who knows Python very well for this role."}
    r = rec.post("/api/jobs/extract-requirements", json=body)
    assert r.status_code == 200 and r.json()["required_skills"][0]["skill"] == "Python"

    def boom(t, d):
        raise llm.LLMUnavailable("no key")

    monkeypatch.setattr(jobs_ai, "extract_job_requirements", boom)
    r = rec.post("/api/jobs/extract-requirements", json=body)
    assert r.status_code == 503 and r.json()["code"] == "llm_unavailable"
    assert rec.post("/api/jobs/extract-requirements", json={"description": "short"}).status_code == 422
