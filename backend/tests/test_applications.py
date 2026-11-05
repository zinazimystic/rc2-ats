import json

from tests.api_helpers import PDF, apply_to, fake_pipeline, make_job, upload, world  # noqa: F401


def test_upload_validation(make_client, fake_pipeline):
    c = make_client("candidate", "alice@example.com", "Alice Tester")
    assert upload(c, "cv.txt", b"hello").json()["code"] == "unsupported_file_type"
    assert upload(c, "cv.pdf", b"").json()["code"] == "empty_file"
    assert upload(c, "cv.pdf", b"not really a pdf").json()["code"] == "invalid_file"
    assert upload(c, "cv.docx", b"%PDF-1.4").json()["code"] == "invalid_file"
    from app.core.config import settings

    big = b"%PDF-" + b"0" * (settings.max_upload_bytes + 10)
    r = upload(c, "big.pdf", big)
    assert r.status_code == 400 and r.json()["code"] == "file_too_large"
    assert c.post("/api/candidates/me/resumes").status_code == 422  # no file part
    r = upload(c, "../../etc/passwd.pdf")
    assert r.status_code == 201 and r.json()["filename"] == "passwd.pdf"


def test_upload_parse_and_file_download(make_client, fake_pipeline):
    c = make_client("candidate", "alice@example.com", "Alice Tester")
    r = upload(c)
    assert r.status_code == 201 and r.json()["parse_status"] == "parsed"
    rid = r.json()["id"]
    detail = c.get(f"/api/resumes/{rid}").json()
    assert detail["text"] and {s["name"] for s in detail["skills"]} == {"Python", "Django", "Docker"}
    f = c.get(f"/api/resumes/{rid}/file")
    assert f.status_code == 200 and f.content == PDF and f.headers["content-type"] == "application/pdf"
    assert f.headers["x-content-type-options"] == "nosniff"
    # a second upload becomes the current one
    r2 = upload(c, "second.pdf").json()
    lst = c.get("/api/candidates/me/resumes").json()
    assert [x["is_current"] for x in lst] == [True, False] and lst[0]["id"] == r2["id"]


def test_resume_pipeline_failure_marks_failed(make_client, monkeypatch):
    from app.services import pipeline

    def boom(rid):
        raise RuntimeError("no worker")

    monkeypatch.setattr(pipeline, "enqueue_resume", boom)
    c = make_client("candidate", "alice@example.com", "Alice Tester")
    r = upload(c)
    assert r.status_code == 201 and r.json()["parse_status"] == "failed" and "Reprocess" in r.json()["parse_error"]


def test_resume_access_control(world):
    w = world
    rid = w.apps["alice"]["resume_id"]
    assert w.cands["alice"].get(f"/api/resumes/{rid}").status_code == 200
    assert w.cands["bob"].get(f"/api/resumes/{rid}").status_code == 404
    assert w.cands["bob"].get(f"/api/resumes/{rid}/file").status_code == 404
    assert w.rec.get(f"/api/resumes/{rid}").status_code == 200  # applied to their job
    assert w.rec2.get(f"/api/resumes/{rid}").status_code == 404
    # talent pool opt-in opens the resume to other recruiters
    w.cands["alice"].patch("/api/candidates/me/profile", json={"talent_pool_opt_in": True})
    assert w.rec2.get(f"/api/resumes/{rid}").status_code == 200


def test_apply_edge_cases(make_client, fake_pipeline):
    rec = make_client("recruiter", "r@example.com")
    job = make_job(rec)
    c = make_client("candidate", "alice@example.com", "Alice Tester")
    r = apply_to(c, job["id"])
    assert r.status_code == 422 and r.json()["code"] == "no_resume"
    upload(c)
    assert apply_to(c, "00000000-0000-0000-0000-000000000000").status_code == 404
    assert c.post("/api/applications", json={"job_id": "nope"}).status_code == 422
    r = apply_to(c, job["id"])
    assert r.status_code == 201
    assert r.json()["status"] == "submitted" or r.json()["status_label"] in ("Submitted", "Under review")
    assert apply_to(c, job["id"]).json()["code"] == "already_applied"
    assert rec.post("/api/applications", json={"job_id": job["id"]}).status_code == 403


def test_candidate_never_sees_scores_or_notes(world):
    w = world
    aid = w.apps["alice"]["id"]
    w.rec.post(f"/api/applications/{aid}/notes", json={"body": "very secret note"})
    w.rec.post(f"/api/applications/{aid}/transition", json={"to_status": "shortlisted"})
    r = w.cands["alice"].get("/api/applications/me")
    body = r.text.lower()
    assert r.status_code == 200
    for forbidden in ("score", "secret", "assessment", "rank", "strengths", "gaps"):
        assert forbidden not in body, forbidden
    row = r.json()[0]
    assert row["status_label"] == "Shortlisted"
    assert [t["label"] for t in row["timeline"]] == ["Submitted", "Under review", "Shortlisted"]
    # candidates cannot use recruiter endpoints on their own application
    assert w.cands["alice"].get(f"/api/applications/{aid}").status_code == 403
    assert w.cands["alice"].get(f"/api/applications/{aid}/history").status_code == 403
    # notifications don't leak scores either
    notes = w.cands["alice"].get("/api/notifications").json()
    assert any("Shortlisted" in n["title"] for n in notes) and "score" not in json.dumps(notes).lower()


def test_ranked_applicants_and_filters(world):
    w = world
    jid = w.job["id"]
    data = w.rec.get(f"/api/jobs/{jid}/applications").json()
    assert [r["candidate"]["full_name"] for r in data["items"]][0] == "Alice Tester"
    scores = [r["effective_score"] for r in data["items"]]
    assert scores == sorted(scores, reverse=True) and data["total"] == 3
    assert data["status_counts"]["ai_assessed"] == 3
    assert [r["candidate"]["full_name"] for r in w.rec.get(f"/api/jobs/{jid}/applications?sort=name").json()["items"]] == \
        ["Alice Tester", "Bob Tester", "Carol Tester"]
    assert len(w.rec.get(f"/api/jobs/{jid}/applications?min_score=60").json()["items"]) == 1
    assert len(w.rec.get(f"/api/jobs/{jid}/applications?skill=django").json()["items"]) == 1
    assert len(w.rec.get(f"/api/jobs/{jid}/applications?q=BOB").json()["items"]) == 1
    assert w.rec.get(f"/api/jobs/{jid}/applications?sort=bogus").status_code == 422
    assert w.rec.get(f"/api/jobs/{jid}/applications?min_score=500").status_code == 422
    top = data["items"][0]
    assert "Python" in top["matched_skills"] and data["items"][2]["missing_skills"] == ["Python", "Django"]


def test_workflow_transitions(world):
    w = world
    aid = w.apps["alice"]["id"]
    url = f"/api/applications/{aid}/transition"
    d = w.rec.get(f"/api/applications/{aid}").json()
    assert d["status"] == "ai_assessed" and "shortlisted" in d["allowed_transitions"]
    # illegal jumps
    for bad in ("interview", "selected", "parsed", "withdrawn"):
        r = w.rec.post(url, json={"to_status": bad})
        assert r.status_code == 422 and r.json()["code"] == "illegal_transition", bad
    assert w.rec.post(url, json={"to_status": "bogus"}).status_code == 422
    # reject needs a reason
    r = w.rec.post(url, json={"to_status": "rejected"})
    assert r.status_code == 422 and r.json()["code"] == "reason_required"
    r = w.rec.post(url, json={"to_status": "rejected", "reason": "Missing core skills"})
    assert r.json()["status"] == "rejected"
    # reconsider needs a reason too
    assert w.rec.post(url, json={"to_status": "recruiter_review"}).json()["code"] == "reason_required"
    assert w.rec.post(url, json={"to_status": "recruiter_review", "reason": "Second look"}).json()["status"] == "recruiter_review"
    assert w.rec.post(url, json={"to_status": "shortlisted"}).json()["status"] == "shortlisted"
    # history is an audit trail with actors
    hist = w.rec.get(f"/api/applications/{aid}/history").json()
    changes = [(h["from_value"], h["to_value"]) for h in hist if h["action"] == "status_change"]
    assert changes[0] == ("submitted", "parsed") and changes[-1] == ("recruiter_review", "shortlisted")
    assert hist[0]["actor_role"] == "candidate" and hist[1]["actor_role"] == "system" and hist[-1]["actor_name"] == "Rita Recruiter"
    # rejected candidate is told "Not selected"
    bob = w.apps["bob"]["id"]
    w.rec.post(f"/api/applications/{bob}/transition", json={"to_status": "rejected", "reason": "no"})
    assert w.cands["bob"].get("/api/applications/me").json()[0]["status_label"] == "Not selected"


def test_withdraw_and_reapply(world):
    w = world
    aid = w.apps["carol"]["id"]
    assert w.cands["bob"].post(f"/api/applications/{aid}/withdraw").status_code == 404
    r = w.cands["carol"].post(f"/api/applications/{aid}/withdraw")
    assert r.status_code == 200 and r.json()["status"] == "withdrawn" and r.json()["can_withdraw"] is False
    assert w.cands["carol"].post(f"/api/applications/{aid}/withdraw").status_code == 422
    assert w.rec.post(f"/api/applications/{aid}/transition", json={"to_status": "shortlisted"}).status_code == 422
    # hidden from the default ranked list, but counted
    data = w.rec.get(f"/api/jobs/{w.job['id']}/applications").json()
    assert data["total"] == 2 and data["status_counts"]["withdrawn"] == 1
    assert w.rec.get("/api/jobs").json()[0]["applicant_count"] == 2
    # re-applying reactivates the same application
    r = apply_to(w.cands["carol"], w.job["id"])
    assert r.status_code == 201 and r.json()["id"] == aid and r.json()["status"] in ("submitted", "ai_assessed")
    assert w.rec.get(f"/api/jobs/{w.job['id']}/applications").json()["total"] == 3
    # recruiter was notified
    titles = [n["title"] for n in w.rec.get("/api/notifications").json()]
    assert any("withdrawn" in t.lower() for t in titles) and any("New application" in t for t in titles)


def test_override_notes_and_reprocess(world):
    w = world
    aid = w.apps["bob"]["id"]
    r = w.rec.post(f"/api/applications/{aid}/override", json={"score": 88.46, "reason": "Strong portfolio"})
    assert r.status_code == 200 and r.json()["override_score"] == 88.5 and r.json()["effective_score"] == 88.5
    assert r.json()["total_score"] == 50.0
    assert w.rec.post(f"/api/applications/{aid}/override", json={"score": 101, "reason": "abc"}).status_code == 422
    assert w.rec.post(f"/api/applications/{aid}/override", json={"score": 50, "reason": ""}).status_code == 422
    rows = w.rec.get(f"/api/jobs/{w.job['id']}/applications").json()["items"]
    assert [r["candidate"]["full_name"] for r in rows] == ["Alice Tester", "Bob Tester", "Carol Tester"] and rows[1]["effective_score"] == 88.5
    hist = w.rec.get(f"/api/applications/{aid}/history").json()
    assert any(h["action"] == "override" and h["to_value"] == "88.5" and h["note"] == "Strong portfolio" for h in hist)
    n = w.rec.post(f"/api/applications/{aid}/notes", json={"body": "  call back  "})
    assert n.status_code == 201 and n.json()["body"] == "call back" and n.json()["author_name"] == "Rita Recruiter"
    assert w.rec.post(f"/api/applications/{aid}/notes", json={"body": "   "}).status_code == 422
    assert len(w.rec.get(f"/api/applications/{aid}/notes").json()) == 1
    assert w.rec.get(f"/api/applications/{aid}").json()["notes_count"] == 1
    assert w.rec2.delete(f"/api/notes/{n.json()['id']}").status_code == 404
    assert w.rec.delete(f"/api/notes/{n.json()['id']}").status_code == 200
    assert w.rec.post(f"/api/applications/{aid}/reprocess").status_code == 202


def test_compare(world):
    w = world
    ids = ",".join(w.apps[n]["id"] for n in ("alice", "bob"))
    r = w.rec.get(f"/api/jobs/{w.job['id']}/compare?ids={ids}")
    assert r.status_code == 200 and [c["candidate"]["full_name"] for c in r.json()["candidates"]] == ["Alice Tester", "Bob Tester"]
    assert r.json()["candidates"][0]["requirements"] and r.json()["candidates"][0]["missing_information"]
    assert w.rec.get(f"/api/jobs/{w.job['id']}/compare?ids={w.apps['alice']['id']}").status_code == 422
    assert w.rec.get(f"/api/jobs/{w.job['id']}/compare?ids=x,y").status_code == 422
    five = ",".join([w.apps["alice"]["id"], w.apps["bob"]["id"], w.apps["carol"]["id"]] * 2)
    assert w.rec.get(f"/api/jobs/{w.job['id']}/compare?ids={five}").status_code == 200  # de-duplicated to 3


def test_skill_edits_rescore_and_access(world):
    w = world
    rid = w.apps["bob"]["resume_id"]
    bob = w.cands["bob"]
    r = bob.post(f"/api/resumes/{rid}/skills", json={"name": "django"})
    assert r.status_code == 201 and r.json()["source"] == "candidate" and r.json()["verification"] == "self_reported"
    assert w.rec.get(f"/api/applications/{w.apps['bob']['id']}").json()["assessment"]["total_score"] == 100.0
    sid = r.json()["id"]
    assert w.cands["carol"].patch(f"/api/skills/{sid}", json={"removed": True}).status_code == 404
    assert bob.patch(f"/api/skills/{sid}", json={"name": "Python"}).status_code == 409
    assert bob.delete(f"/api/skills/{sid}").status_code == 200
    assert "Django" not in [s["name"] for s in bob.get(f"/api/resumes/{rid}").json()["skills"]]
    assert w.rec.get(f"/api/applications/{w.apps['bob']['id']}").json()["assessment"]["total_score"] == 50.0
    # recruiter may add verified skills; absent skills are supported
    r = w.rec.post(f"/api/resumes/{rid}/skills", json={"name": "Docker", "presence": "absent"})
    assert r.status_code == 201 and r.json()["source"] == "recruiter" and r.json()["presence"] == "absent"
    assert w.rec2.post(f"/api/resumes/{rid}/skills", json={"name": "X"}).status_code == 404


def test_parsed_patch_candidate_only(world):
    w = world
    rid = w.apps["alice"]["resume_id"]
    r = w.cands["alice"].patch(f"/api/resumes/{rid}/parsed", json={"summary": "Corrected summary", "certifications": ["AWS SAA"]})
    assert r.status_code == 200 and r.json()["parsed"]["summary"] == "Corrected summary"
    assert r.json()["parsed"]["contact"]["name"] == "Alice Tester"  # untouched sections preserved
    assert w.rec.patch(f"/api/resumes/{rid}/parsed", json={"summary": "x"}).status_code == 403
    assert w.cands["bob"].patch(f"/api/resumes/{rid}/parsed", json={"summary": "x"}).status_code == 404


def test_profile_and_notifications(make_client):
    c = make_client("candidate", "alice@example.com", "Alice Tester")
    p = c.get("/api/candidates/me/profile").json()
    assert p["email"] == "alice@example.com" and p["talent_pool_opt_in"] is False
    p = c.patch("/api/candidates/me/profile", json={"headline": " Dev ", "links": ["https://x.dev", " "], "talent_pool_opt_in": True}).json()
    assert p["headline"] == "Dev" and p["links"] == ["https://x.dev"] and p["talent_pool_opt_in"] is True
    assert c.get("/api/notifications").json() == []
    assert c.post("/api/notifications/read-all").status_code == 200
    assert c.post("/api/notifications/00000000-0000-0000-0000-000000000000/read").status_code == 404
