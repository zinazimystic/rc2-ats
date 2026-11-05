"""Stages 'actions' and 'checks' of seed_bulk.py (recruiter workflow at scale + negative/security checks)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import bulk_data as bd
from seed_bulk import OUT, Api, PASSWORD, get_ctx, log

RESULTS: list[dict] = []


def chk(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    log(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    return bool(ok)


def j(r):
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:200]}


def ranked(api: Api, job_id: str) -> list[dict]:
    d = api.get(f"/jobs/{job_id}/applications").json()
    return [i for i in d["items"] if i["effective_score"] is not None]


def candidate_api(base: str, p: bd.Person) -> Api:
    return Api(base).sign_in(p.email, p.name, "candidate")


def stage_actions(base: str) -> None:
    people = bd.build_people()
    recs = get_ctx(base)
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    summary: dict = {"jobs": {}}
    log("== recruiter workflow per job")
    for n, (track, r) in enumerate(recs.items()):
        api, jid = r["api"], r["job_id"]
        title = bd.TRACKS[track]["title"]
        rows = ranked(api, jid)
        log(f"-- {title}: {len(rows)} assessed applicants")
        done = [x for x in rows if x["status"] in ("selected", "interview")]
        if done:  # re-run: the workflow was already applied; only complete what a previous run may have missed
            for x in done:
                if not api.get(f"/applications/{x['id']}/questions").json():
                    qs = api.post(f"/applications/{x['id']}/questions/generate", json={})
                    chk(f"{track}: (re-run) interview questions generated", qs.status_code == 200, str(qs.status_code))
                for iv in api.get(f"/applications/{x['id']}/interviews").json():
                    if not iv["feedback"]:
                        fb = api.post(f"/interviews/{iv['id']}/feedback", json={"ratings": {"technical": 4, "communication": 5, "problem_solving": 4, "culture_fit": 4},
                                                                              "recommendation": "yes", "comments": "Solid, clear communicator."})
                        chk(f"{track}: (re-run) submit feedback", fb.status_code in (200, 201), f"{fb.status_code} {j(fb).get('detail', '')}")
                if x["status"] == "interview":
                    sel = api.post(f"/applications/{x['id']}/transition", json={"to_status": "selected"})
                    chk(f"{track}: (re-run) select", sel.status_code == 200, str(sel.status_code))
            summary["jobs"].setdefault(track, {})["rerun"] = True
            continue
        rows = [x for x in rows if x["status"] in ("ai_assessed", "recruiter_review")]
        if len(rows) < 3:
            chk(f"{track}: >=3 assessed applicants", False, str(len(rows)))
            continue
        # ranking order check
        scores = [x["effective_score"] for x in rows]
        chk(f"{track}: list sorted by score desc", scores == sorted(scores, reverse=True))
        top, second, third = rows[0], rows[1], rows[2]
        bottom = rows[-1]
        # --- shortlist top 2 with a private note
        for x in (top, second):
            t = api.post(f"/applications/{x['id']}/transition", json={"to_status": "shortlisted"})
            chk(f"{track}: shortlist {x['candidate']['full_name']}", t.status_code == 200, f"{t.status_code} {j(t).get('detail', '')}")
            nt = api.post(f"/applications/{x['id']}/notes", json={"body": f"Strong match ({x['effective_score']}). Private: check salary expectations."})
            chk(f"{track}: add note", nt.status_code in (200, 201), str(nt.status_code))
        # --- illegal transition + missing reason
        bad = api.post(f"/applications/{third['id']}/transition", json={"to_status": "selected"})
        chk(f"{track}: illegal transition rejected", bad.status_code == 422, f"{bad.status_code} {j(bad).get('detail', '')}")
        nore = api.post(f"/applications/{bottom['id']}/transition", json={"to_status": "rejected"})
        chk(f"{track}: reject without reason -> 422", nore.status_code == 422, f"{nore.status_code} {j(nore).get('detail', '')}")
        rj = api.post(f"/applications/{bottom['id']}/transition", json={"to_status": "rejected", "reason": "Skills do not match the core requirements."})
        chk(f"{track}: reject bottom with reason", rj.status_code == 200, f"{rj.status_code} {j(rj).get('detail', '')}")
        if n == 0 or n % 2 == 0:
            noreason = api.post(f"/applications/{bottom['id']}/transition", json={"to_status": "recruiter_review"})
            if noreason.status_code == 200:  # contract: reason required for reconsider
                chk(f"{track}: reconsider without reason should be 422", False, "accepted without reason")
                api.post(f"/applications/{bottom['id']}/transition", json={"to_status": "rejected", "reason": "Re-reject for test"})
            else:
                chk(f"{track}: reconsider without reason -> 422", noreason.status_code == 422)
            rc = api.post(f"/applications/{bottom['id']}/transition", json={"to_status": "recruiter_review", "reason": "Second look after re-reading the resume."})
            chk(f"{track}: reconsider rejected", rc.status_code == 200, f"{rc.status_code} {j(rc).get('detail', '')}")
        # --- override audited (third)
        ov = api.post(f"/applications/{third['id']}/override", json={"score": 77.5, "reason": "Strong portfolio not captured by the resume."})
        ok = ov.status_code == 200 and j(ov).get("override_score") == 77.5
        chk(f"{track}: override score", ok, f"{ov.status_code}")
        hist = api.get(f"/applications/{third['id']}/history").json()
        chk(f"{track}: override in audit history", any(h["action"] == "override" for h in hist), str([h["action"] for h in hist]))
        # --- compare
        cp = api.get(f"/jobs/{jid}/compare", params={"ids": ",".join(x["id"] for x in rows[:3])})
        chk(f"{track}: compare 3", cp.status_code == 200 and len(j(cp).get("candidates", [])) == 3, str(cp.status_code))
        cp1 = api.get(f"/jobs/{jid}/compare", params={"ids": top["id"]})
        chk(f"{track}: compare with 1 id rejected", cp1.status_code in (400, 422), str(cp1.status_code))
        # --- fairness
        fc = api.post(f"/applications/{top['id']}/fairness-check")
        fj = j(fc)
        chk(f"{track}: fairness check", fc.status_code == 200 and fj.get("passed") is True, f"{fc.status_code} max_delta={fj.get('max_abs_delta')}")
        # --- questions (LLM) for top only on every job
        t0 = time.time()
        qs = api.post(f"/applications/{top['id']}/questions/generate", json={})
        ql = j(qs)
        chk(f"{track}: interview questions generated", qs.status_code == 200 and isinstance(ql, list) and len(ql) >= 4,
            f"{qs.status_code} n={len(ql) if isinstance(ql, list) else ql} {time.time()-t0:.0f}s")
        if isinstance(ql, list) and ql:
            verified = sum(1 for q in ql if q.get("source_verified"))
            summary["jobs"].setdefault(track, {})["questions"] = {"n": len(ql), "source_verified": verified, "sample": ql[0]["question"]}
        # --- interviews + double booking
        ib = {"interviewer_name": "Sam Interviewer", "interviewer_email": "sam@bulk.rc3.dev", "interview_type": "technical", "duration_minutes": 60,
              "location": "https://meet.example.com/bulk"}
        day = start + timedelta(days=n)
        i1 = api.post(f"/applications/{top['id']}/interviews", json={**ib, "start_at": day.isoformat()})
        chk(f"{track}: schedule interview 1", i1.status_code == 201, f"{i1.status_code} {j(i1).get('detail', '')}")
        i2 = api.post(f"/applications/{second['id']}/interviews", json={**ib, "start_at": (day + timedelta(minutes=30)).isoformat()})
        chk(f"{track}: interviewer double-booking -> 409 schedule_conflict", i2.status_code == 409 and j(i2).get("code") == "schedule_conflict", f"{i2.status_code}")
        i3 = api.post(f"/applications/{second['id']}/interviews", json={**ib, "start_at": (day + timedelta(minutes=30)).isoformat(), "force": True})
        chk(f"{track}: force=true schedules anyway", i3.status_code == 201 and j(i3).get("has_conflict") in (True, False), f"{i3.status_code}")
        if i1.status_code == 201:
            fb = api.post(f"/interviews/{j(i1)['id']}/feedback", json={"ratings": {"technical": 4, "communication": 5, "problem_solving": 4, "culture_fit": 4},
                                                                      "recommendation": "yes", "comments": "Solid, clear communicator."})
            chk(f"{track}: submit feedback", fb.status_code in (200, 201), f"{fb.status_code} {j(fb).get('detail', '')}")
        sel = api.post(f"/applications/{top['id']}/transition", json={"to_status": "selected"})
        chk(f"{track}: select top candidate", sel.status_code == 200, f"{sel.status_code} {j(sel).get('detail', '')}")
        # --- detail sanity: evidence is verbatim
        d = api.get(f"/applications/{third['id']}").json()
        txt = (d.get("resume") or {}).get("text") or ""
        miss = []
        for rq in (d.get("assessment") or {}).get("requirements", []):
            for ev in rq["evidence"]:
                if ev["quote"].strip() and ev["quote"].strip() not in txt and " ".join(ev["quote"].split()) not in " ".join(txt.split()):
                    miss.append((rq["skill"], ev["quote"][:60]))
        chk(f"{track}: evidence quotes verbatim in resume text", not miss, str(miss[:2]))
        summary["jobs"].setdefault(track, {})["top"] = {"name": top["candidate"]["full_name"], "score": top["effective_score"]}

    # ---- talent search
    log("== talent search")
    rita = recs["backend_py"]["api"]
    queries = ["Python developers with REST API experience", "someone who containerizes services and automates deployments",
               "machine learning engineer with PyTorch", "React and TypeScript frontend engineer", "Flutter mobile app developer with Firebase",
               "data pipelines with Spark and Airflow"]
    sr = {}
    for q in queries:
        t0 = time.time()
        r = rita.post("/search/talent", json={"query": q, "limit": 10})
        d = j(r)
        res = d.get("results", []) if r.status_code == 200 else []
        names = [f"{x['candidate']['full_name']}({x['score']:.0f})" for x in res[:5]]
        sr[q] = {"mode": d.get("mode"), "detected": d.get("detected_skills"), "top": names, "secs": round(time.time() - t0, 1)}
        chk(f"search '{q}'", r.status_code == 200 and len(res) > 0, f"mode={d.get('mode')} detected={d.get('detected_skills')} top={names[:3]}")
    # access filtering: recruiter of a job with applicants only sees candidates that applied to his jobs (or opted into the pool)
    omar = recs["frontend"]["api"]
    mine = {a["candidate"]["email"] for a in omar.get(f"/jobs/{recs['frontend']['job_id']}/applications").json()["items"]}
    r = omar.post("/search/talent", json={"query": "Python Django developer", "limit": 50})
    leaked = [x["candidate"]["email"] for x in j(r).get("results", []) if x["candidate"]["email"] not in mine and not x.get("in_talent_pool")]
    chk("search is access-filtered (only applicants or pool opt-ins)", not leaked, f"leaked={leaked[:3]}")
    summary["search"] = sr

    # ---- talent pool + invite
    log("== talent pool")
    for track in ("backend_py", "devops"):
        tp = recs[track]["api"].get(f"/jobs/{recs[track]['job_id']}/talent-pool")
        items = j(tp)
        chk(f"{track}: talent pool", tp.status_code == 200 and isinstance(items, list), f"{tp.status_code} n={len(items) if isinstance(items, list) else items}")
        if isinstance(items, list) and items:
            inv = recs[track]["api"].post(f"/jobs/{recs[track]['job_id']}/talent-pool/{items[0]['candidate']['id']}/invite")
            chk(f"{track}: invite from pool", inv.status_code == 200, f"{inv.status_code} {j(inv).get('detail', '')}")
            summary.setdefault("pool", {})[track] = [f"{x['candidate']['full_name']}({x['score']:.0f})" for x in items[:5]]

    # ---- duplicates
    log("== duplicates")
    d = rita.get("/duplicates", params={"status": "all"})
    dl = j(d)
    hz = [x for x in dl if "Hamza Qureshi" in (x["candidate_a"]["full_name"], x["candidate_b"]["full_name"])] if isinstance(dl, list) else []
    chk("duplicate of Hamza Qureshi flagged", bool(hz), f"flags={len(dl) if isinstance(dl, list) else dl} reasons={hz[0]['reasons'] if hz else ''}")
    if hz:
        c = rita.post(f"/duplicates/{hz[0]['id']}/confirm")
        chk("confirm duplicate (no deletion)", c.status_code == 200, f"{c.status_code} {j(c).get('detail', '')}")
        al = rita.get(f"/jobs/{recs['backend_py']['job_id']}/applications").json()["items"]
        still = [a for a in al if a["candidate"]["full_name"] == "Hamza Qureshi"]
        chk("both Hamza applications still present", len(still) >= 2, f"n={len(still)} is_duplicate={[a['is_duplicate'] for a in still]}")

    # ---- recommendations (candidate side)
    log("== recommendations + notifications")
    recs_out = {}
    for p in [people[0], people[5], people[12], people[22], people[33]]:
        ca = candidate_api(base, p)
        t0 = time.time()
        rr = ca.get("/candidates/me/recommendations")
        rl = j(rr)
        top3 = [f"{x['job']['title']}({x['score']:.0f})" for x in rl[:3]] if isinstance(rl, list) else rl
        recs_out[p.name] = top3
        want = bd.TRACKS[p.track]["title"]
        chk(f"recommendations for {p.name} [{p.track}/{p.level}]", rr.status_code == 200 and isinstance(rl, list) and len(rl) > 0,
            f"{top3} want~{want} {time.time()-t0:.1f}s")
        nt = ca.get("/notifications")
        chk(f"notifications for {p.name}", nt.status_code == 200, f"n={len(j(nt)) if nt.status_code == 200 else nt.text[:80]}")
    summary["recommendations"] = recs_out
    ob = rita.get("/notifications/outbox")
    chk("recruiter email outbox", ob.status_code == 200, f"n={len(j(ob)) if ob.status_code == 200 else ob.text[:80]}")

    # ---- analytics per recruiter
    log("== analytics")
    for track, r in recs.items():
        an = r["api"].get("/analytics/overview")
        k = j(an).get("kpis", {})
        chk(f"{track}: analytics overview", an.status_code == 200 and k.get("total_applications", 0) > 0,
            f"kpis={k} avg_proc={j(an).get('avg_processing_seconds')}")
        summary["jobs"].setdefault(track, {})["kpis"] = k

    # ---- withdraw + close job then apply
    log("== withdraw / close")
    wp = next(p for p in people if p.kind == "normal" and p.level == "weak" and p.apply_tracks[1:])
    wa = candidate_api(base, wp)
    mine_apps = wa.get("/applications/me").json()
    target = next((a for a in mine_apps if a["status"] not in ("withdrawn", "selected", "rejected")), None)
    if target:
        w = wa.post(f"/applications/{target['id']}/withdraw")
        chk("withdraw application", w.status_code == 200 and j(w).get("status") == "withdrawn", f"{w.status_code} {j(w).get('detail', '')}")
        w2 = wa.post(f"/applications/{target['id']}/withdraw")
        chk("withdraw twice is rejected", w2.status_code in (409, 422), str(w2.status_code))
    qa = recs["qa"]
    cl = qa["api"].post(f"/jobs/{qa['job_id']}/close")
    chk("close job", cl.status_code == 200, str(cl.status_code))
    other = next(p for p in people if p.kind == "normal" and "qa" not in p.apply_tracks)
    oc = candidate_api(base, other)
    ap = oc.post("/applications", json={"job_id": qa["job_id"]})
    chk("apply to closed job -> 409", ap.status_code == 409, f"{ap.status_code} {j(ap).get('detail', '')}")
    rp = qa["api"].post(f"/jobs/{qa['job_id']}/reopen")
    chk("reopen job", rp.status_code == 200, str(rp.status_code))

    (OUT / "actions.json").write_text(json.dumps({"checks": RESULTS, "summary": summary}, indent=1, default=str))
    fails = [x for x in RESULTS if not x["ok"]]
    log(f"actions done: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed; failures: {[f['check'] for f in fails]}")


def stage_checks(base: str) -> None:
    people = bd.build_people()
    recs = get_ctx(base)
    A, B = recs["backend_py"], recs["frontend"]
    log("== negative / security checks")
    cand = candidate_api(base, people[0])
    anon = Api(base)
    # candidate -> recruiter endpoints
    for method, url in [("GET", "/analytics/overview"), ("GET", f"/jobs/{A['job_id']}/applications"), ("GET", "/interviews"), ("GET", "/duplicates"),
                        ("GET", "/notifications/outbox")]:
        r = cand.req(method, url)
        chk(f"candidate {method} {url.split('?')[0][:40]} -> 403", r.status_code == 403, str(r.status_code))
    r = cand.post("/search/talent", json={"query": "python"})
    chk("candidate POST /search/talent -> 403", r.status_code == 403, str(r.status_code))
    r = cand.post("/jobs", json=bd.job_payload("backend_py"))
    chk("candidate POST /jobs -> 403", r.status_code == 403, str(r.status_code))
    r = A["api"].get("/applications/me")
    chk("recruiter GET /applications/me -> 403", r.status_code == 403, str(r.status_code))
    # recruiter B vs recruiter A
    rows = A["api"].get(f"/jobs/{A['job_id']}/applications").json()["items"]
    aid = rows[0]["id"]
    for method, url, kw in [("GET", f"/jobs/{A['job_id']}/applications", {}), ("GET", f"/applications/{aid}", {}), ("GET", f"/applications/{aid}/notes", {}),
                            ("PATCH", f"/jobs/{A['job_id']}", {"json": {"title": "Hacked"}}), ("POST", f"/jobs/{A['job_id']}/close", {}),
                            ("POST", f"/applications/{aid}/transition", {"json": {"to_status": "recruiter_review"}}),
                            ("POST", f"/applications/{aid}/questions/generate", {"json": {}}), ("GET", f"/jobs/{A['job_id']}/talent-pool", {})]:
        r = B["api"].req(method, url, **kw)
        chk(f"recruiter B {method} {url[:48]} -> 404", r.status_code == 404, str(r.status_code))
    # resume access: recruiter B cannot read a resume of a candidate who never applied to B's job
    ups = json.loads((OUT / "load.json").read_text())["uploads"]
    rid = ups["1"]["resume_id"]
    r = B["api"].get(f"/resumes/{rid}")
    chk("recruiter B GET resume of non-applicant -> 404", r.status_code == 404, str(r.status_code))
    other_c = candidate_api(base, people[1])
    r = other_c.get(f"/resumes/{rid}")
    chk("candidate GET another candidate's resume -> 404", r.status_code == 404, str(r.status_code))
    # candidate payload leaks
    mine = cand.get("/applications/me")
    body = mine.text.lower()
    bad = [k for k in ("total_score", "effective_score", "override", "\"rank\"", "\"score\"", "notes\":", "assessment", "missing_skills") if k in body]
    chk("candidate /applications/me has no score/notes/rank fields", mine.status_code == 200 and not bad, f"found={bad}")
    jb = cand.get("/jobs").text.lower()
    chk("candidate /jobs has no applicant data", "effective_score" not in jb and "applicant" not in jb)
    # unauthenticated
    for url in ["/auth/me", "/jobs", "/applications/me", "/candidates/me/profile", "/analytics/overview", "/notifications"]:
        r = anon.get(url)
        chk(f"unauthenticated GET {url} -> 401", r.status_code == 401, str(r.status_code))
    r = anon.get("/health")
    chk("health is public", r.status_code == 200)
    # oversize upload
    big = b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024)
    r = cand.post("/candidates/me/resumes", files={"file": ("big.pdf", big, "application/pdf")})
    chk("oversize upload rejected (4xx)", 400 <= r.status_code < 500, f"{r.status_code} {j(r).get('detail', '')}")
    # wrong extension / mime
    r = cand.post("/candidates/me/resumes", files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")})
    chk("executable upload rejected", 400 <= r.status_code < 500, f"{r.status_code} {j(r).get('detail', '')}")
    # SQL / HTML in text fields
    sqli = "Robert'); DROP TABLE users;--"
    xss = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    r = cand.patch("/candidates/me/profile", json={"headline": sqli, "location": xss})
    p = cand.get("/candidates/me/profile").json()
    chk("SQL/HTML in profile stored safely", r.status_code == 200 and p.get("headline") == sqli, f"{r.status_code}")
    chk("API still healthy after SQL text (users table intact)", A["api"].get("/auth/me").status_code == 200)
    r = A["api"].post(f"/applications/{aid}/notes", json={"body": xss})
    chk("HTML in note accepted as text (no 5xx)", r.status_code in (200, 201, 422), f"{r.status_code}")
    if r.status_code in (200, 201):
        A["api"].delete(f"/notes/{r.json()['id']}")
    r = A["api"].post("/search/talent", json={"query": "' OR 1=1; --"})
    chk("SQL-ish search query handled", r.status_code in (200, 422), str(r.status_code))
    r = Api(base).post("/auth/register", json={"email": "x@bulk.rc3.dev", "password": "short", "full_name": "X", "role": "candidate"})
    chk("weak password rejected", r.status_code == 422, f"{r.status_code} {j(r).get('detail', '')}")
    r = Api(base).post("/auth/register", json={"email": "admin@bulk.rc3.dev", "password": PASSWORD, "full_name": "Evil", "role": "admin"})
    chk("register with role=admin rejected", r.status_code == 422, str(r.status_code))
    r = A["api"].post("/jobs", json={**bd.job_payload("backend_py"), "title": "", "salary_min": 10, "salary_max": 5})
    chk("invalid job payload -> 422", r.status_code == 422, str(r.status_code))
    # login rate limit
    lim = Api(base)
    codes = []
    for _ in range(14):
        codes.append(lim.post("/auth/login", json={"email": "rita@bulk.rc3.dev", "password": "WrongPass1!"}).status_code)
    chk("login rate limit kicks in (429)", 429 in codes, f"codes={sorted(set(codes))}")
    # real user can still log in with other key? (limiter keyed per ip+email: the throttled email is rita; give it time)
    (OUT / "checks.json").write_text(json.dumps(RESULTS, indent=1))
    fails = [x for x in RESULTS if not x["ok"]]
    log(f"checks done: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed; failures: {[f['check'] for f in fails]}")
