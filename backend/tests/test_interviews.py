from tests.api_helpers import fake_pipeline, future, world  # noqa: F401


def shortlist(w, *names):
    for n in names:
        r = w.rec.post(f"/api/applications/{w.apps[n]['id']}/transition", json={"to_status": "shortlisted"})
        assert r.status_code == 200, r.text


def book(w, name, start, **over):
    body = {"interviewer_name": "Ivy Interviewer", "interviewer_email": "ivy@corp.com", "start_at": start, "duration_minutes": 60, **over}
    return w.rec.post(f"/api/applications/{w.apps[name]['id']}/interviews", json=body)


def test_schedule_moves_to_interview_and_notifies(world):
    w = world
    shortlist(w, "alice")
    r = book(w, "alice", future(48), location="Room 4")
    assert r.status_code == 201, r.text
    iv = r.json()
    assert iv["status"] == "scheduled" and iv["has_conflict"] is False and iv["candidate_name"] == "Alice Tester"
    assert iv["job_title"] == "Backend Developer" and iv["end_at"] > iv["start_at"]
    assert w.rec.get(f"/api/applications/{w.apps['alice']['id']}").json()["status"] == "interview"
    cand = w.cands["alice"].get("/api/applications/me").json()[0]
    assert cand["status_label"] == "Interview scheduled" and cand["interviews"][0]["location"] == "Room 4"
    assert "feedback" not in w.cands["alice"].get("/api/applications/me").text
    titles = [n["title"] for n in w.cands["alice"].get("/api/notifications").json()]
    assert any(t.startswith("Interview scheduled") for t in titles)
    outbox = w.rec.get("/api/notifications/outbox").json()
    assert {o["recipient_email"] for o in outbox} >= {"alice@example.com", "ivy@corp.com"}
    assert w.cands["alice"].get("/api/notifications/outbox").status_code == 403


def test_scheduling_preconditions(world):
    w = world
    r = book(w, "alice", future(24))  # not shortlisted yet
    assert r.status_code == 422 and r.json()["code"] == "illegal_state"
    shortlist(w, "alice")
    assert book(w, "alice", future(-3)).json()["code"] == "past_time"
    assert w.rec.post(f"/api/applications/{w.apps['alice']['id']}/interviews",
                      json={"interviewer_name": "X", "start_at": future(24), "duration_minutes": 5}).status_code == 422
    assert w.rec2.post(f"/api/applications/{w.apps['alice']['id']}/interviews",
                       json={"interviewer_name": "X", "start_at": future(24)}).status_code == 404
    assert w.cands["alice"].post(f"/api/applications/{w.apps['alice']['id']}/interviews",
                                 json={"interviewer_name": "X", "start_at": future(24)}).status_code == 403
    w.cands["alice"].post(f"/api/applications/{w.apps['alice']['id']}/withdraw")
    assert book(w, "alice", future(24)).json()["code"] == "illegal_state"


def test_interviewer_conflict_409_force_and_back_to_back(world):
    w = world
    shortlist(w, "alice", "bob")
    start = future(48)
    assert book(w, "alice", start).status_code == 201
    r = book(w, "bob", start)  # same interviewer, same slot
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "schedule_conflict" and body["conflicts"][0]["kind"] == "interviewer"
    assert body["conflicts"][0]["with_whom"] == "Alice Tester" and body["conflicts"][0]["interview_id"]
    # partial overlap also conflicts, but case-insensitive email match matters
    assert book(w, "bob", future(48, 30), interviewer_email="IVY@corp.com").status_code == 409
    # different interviewer is fine
    assert book(w, "bob", start, interviewer_name="Other Person", interviewer_email="other@corp.com").status_code == 201


def test_back_to_back_is_not_a_conflict_and_force_flags_it(world):
    w = world
    shortlist(w, "alice", "bob", "carol")
    assert book(w, "alice", future(48)).status_code == 201
    assert book(w, "bob", future(49)).status_code == 201  # starts exactly when the first ends
    r = book(w, "carol", future(48, 15), force=True)
    assert r.status_code == 201 and r.json()["has_conflict"] is True and r.json()["conflict_details"][0]["kind"] == "interviewer"
    listed = w.rec.get("/api/interviews").json()
    assert len(listed) == 3 and [i["start_at"] for i in listed] == sorted(i["start_at"] for i in listed)


def test_candidate_double_booking_conflict(world):
    w = world
    shortlist(w, "alice")
    assert book(w, "alice", future(48)).status_code == 201
    r = book(w, "alice", future(48, 30), interviewer_name="Someone Else", interviewer_email="s@corp.com")
    assert r.status_code == 409 and r.json()["conflicts"][0]["kind"] == "candidate"


def test_reschedule_cancel_and_closed_interviews(world):
    w = world
    shortlist(w, "alice", "bob")
    a = book(w, "alice", future(48)).json()
    b = book(w, "bob", future(72)).json()
    # moving bob onto alice's slot conflicts; force allows it; excluding itself means no self-conflict
    assert w.rec.patch(f"/api/interviews/{b['id']}", json={"start_at": a["start_at"]}).status_code == 409
    assert w.rec.patch(f"/api/interviews/{a['id']}", json={"duration_minutes": 90}).status_code == 200
    r = w.rec.patch(f"/api/interviews/{b['id']}", json={"start_at": a["start_at"], "force": True})
    assert r.status_code == 200 and r.json()["has_conflict"] is True
    assert w.rec.patch(f"/api/interviews/{a['id']}", json={}).status_code == 422
    # cancelling frees the slot and clears the conflict flag
    r = w.rec.patch(f"/api/interviews/{a['id']}", json={"status": "cancelled"})
    assert r.json()["status"] == "cancelled"
    assert w.rec.patch(f"/api/interviews/{a['id']}", json={"start_at": future(100)}).status_code == 409  # closed
    assert w.cands["alice"].get("/api/applications/me").json()[0]["interviews"] == []
    assert any(n["title"].startswith("Interview cancelled") for n in w.cands["alice"].get("/api/notifications").json())
    assert w.rec2.patch(f"/api/interviews/{b['id']}", json={"notes": "x"}).status_code == 404
    assert len(w.rec.get("/api/interviews?status=cancelled").json()) == 1
    assert len(w.rec.get("/api/interviews", params={"from": future(40), "to": future(60), "status": "scheduled"}).json()) == 1
    assert w.rec2.get("/api/interviews").json() == []


def test_feedback_flow(world):
    w = world
    shortlist(w, "alice")
    iv = book(w, "alice", future(48)).json()
    fb = {"ratings": {"technical": 5, "communication": 4, "problem_solving": 4, "culture_fit": 5}, "recommendation": "strong_yes", "comments": "Great"}
    r = w.rec.post(f"/api/interviews/{iv['id']}/feedback", json=fb)
    assert r.status_code == 200 and r.json()["status"] == "completed" and r.json()["feedback"][0]["author_name"] == "Rita Recruiter"
    fb["recommendation"] = "yes"
    r = w.rec.post(f"/api/interviews/{iv['id']}/feedback", json=fb)  # same author updates, not duplicates
    assert len(r.json()["feedback"]) == 1 and r.json()["feedback"][0]["recommendation"] == "yes"
    bad = {**fb, "ratings": {**fb["ratings"], "technical": 9}}
    assert w.rec.post(f"/api/interviews/{iv['id']}/feedback", json=bad).status_code == 422
    assert w.rec2.post(f"/api/interviews/{iv['id']}/feedback", json=fb).status_code == 404
    assert w.rec.get(f"/api/applications/{w.apps['alice']['id']}/interviews").json()[0]["feedback"]
    # decision after interview
    r = w.rec.post(f"/api/applications/{w.apps['alice']['id']}/transition", json={"to_status": "selected"})
    assert r.json()["status"] == "selected"
    assert w.cands["alice"].get("/api/applications/me").json()[0]["status_label"] == "Selected"
