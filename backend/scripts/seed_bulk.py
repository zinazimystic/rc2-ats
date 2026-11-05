"""Bulk-load realistic data through the PUBLIC API and (optionally) exercise every feature at scale.

    python scripts/seed_bulk.py [--stage load|actions|checks|all] [--base-url http://localhost:8000/api]

Stages (all idempotent; accounts are logged into when they already exist, jobs reused by title):
    reprocess re-parse + re-assess every resume (after backend matching/taxonomy changes; see reembed_jobs.py)
    load     10 recruiters + 10 jobs, 50 candidates + resumes (10 edge documents), ~114 applications, wait for AI assessments
    actions  recruiter workflow per job (shortlist/reject/reconsider/questions/interviews/feedback/select), compare, fairness,
             override, talent search, talent pool, duplicates, recommendations, notifications, analytics, withdraw, close job
    checks   negative + security checks (403/404/401, oversize upload, injection text, login rate limit)
Results go to scripts/.bulk_out/*.json; `python scripts/bulk_report.py` prints the model-quality report.
Tip: start the server with REGISTER_RATE_LIMIT_PER_HOUR=2000 so sign-ups are not throttled.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import bulk_data as bd  # noqa: E402

OUT = Path(__file__).parent / ".bulk_out"
OUT.mkdir(exist_ok=True)
PASSWORD = bd.PASSWORD
_print_lock = threading.Lock()


def log(*a):
    with _print_lock:
        print(*a, flush=True)


class Api:
    """httpx client wrapper that honours 429 Retry-After."""

    def __init__(self, base: str, email: str | None = None):
        self.base = base.rstrip("/")
        self.c = httpx.Client(base_url=self.base, timeout=180.0)
        self.email = email

    def req(self, method: str, url: str, **kw) -> httpx.Response:
        for _ in range(6):
            r = self.c.request(method, url, **kw)
            if r.status_code == 429:
                time.sleep(min(int(r.headers.get("Retry-After", "2")) + 1, 30))
                continue
            return r
        return r

    def get(self, url, **kw):
        return self.req("GET", url, **kw)

    def post(self, url, **kw):
        return self.req("POST", url, **kw)

    def patch(self, url, **kw):
        return self.req("PATCH", url, **kw)

    def delete(self, url, **kw):
        return self.req("DELETE", url, **kw)

    def sign_in(self, email: str, name: str, role: str) -> "Api":
        r = self.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": name, "role": role})
        if r.status_code == 409:
            r = self.post("/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code not in (200, 201):
            raise SystemExit(f"auth failed for {email}: {r.status_code} {r.text[:200]}")
        self.email = email
        return self


def rec_email(handle: str) -> str:
    return f"{handle}@bulk.rc3.dev"


def get_ctx(base: str) -> dict:
    """Sign in all recruiters, locate their jobs; candidates are signed in lazily by callers."""
    recs = {}
    for (name, handle), track in zip(bd.RECRUITERS, bd.TRACK_ORDER):
        api = Api(base).sign_in(rec_email(handle), name, "recruiter")
        title = bd.TRACKS[track]["title"]
        jobs = [j for j in api.get("/jobs").json() if j["title"] == title]
        recs[track] = {"api": api, "name": name, "handle": handle, "job_id": jobs[0]["id"] if jobs else None}
    return recs


def stage_load(base: str) -> None:
    t0 = time.time()
    results: dict = {"extraction": {}, "uploads": {}, "applies": [], "timing": {}}
    h = httpx.get(f"{base}/health", timeout=20).json()
    log("health:", h["status"], "llm", h["llm"]["ok"], "emb", h["embeddings"]["ok"])

    # ---- recruiters + jobs
    log("== recruiters + jobs")
    recs: dict = {}
    for (name, handle), track in zip(bd.RECRUITERS, bd.TRACK_ORDER):
        api = Api(base).sign_in(rec_email(handle), name, "recruiter")
        payload = bd.job_payload(track)
        existing = [j for j in api.get("/jobs").json() if j["title"] == payload["title"]]
        if existing:
            jid = existing[0]["id"]
        else:
            r = api.post("/jobs", json=payload)
            if r.status_code != 201:
                raise SystemExit(f"create job {track}: {r.status_code} {r.text[:300]}")
            jid = r.json()["id"]
        recs[track] = {"api": api, "job_id": jid}
        log(f"  {name:16s} {payload['title']:28s} {jid[:8]}")
    (OUT / "jobs.json").write_text(json.dumps({t: r["job_id"] for t, r in recs.items()}, indent=1))

    # ---- requirement extraction accuracy (3 jobs)
    log("== extract-requirements accuracy")
    for track in ("backend_py", "devops", "data_sci"):
        t = bd.TRACKS[track]
        s = time.time()
        r = recs[track]["api"].post("/jobs/extract-requirements", json={"title": t["title"], "description": bd.job_description(track)})
        if r.status_code != 200:
            log(f"  {track}: HTTP {r.status_code} {r.text[:200]}")
            continue
        d = r.json()
        got = {x["skill"].lower() for x in d["required_skills"]}
        want = {x.lower() for x in t["core"]}
        tp = len(got & want)
        prec = tp / len(got) if got else 0
        rec = tp / len(want)
        results["extraction"][track] = {"precision": prec, "recall": rec, "got": sorted(got), "want": sorted(want), "method": d["method"], "secs": round(time.time() - s, 1),
                                        "preferred": [x["skill"] for x in d["preferred_skills"]], "min_years": d["min_experience_years"], "edu": d["education_level"]}
        log(f"  {track}: precision={prec:.2f} recall={rec:.2f} method={d['method']} got={sorted(got)} ({time.time()-s:.1f}s)")

    # ---- candidates: register, profile, upload, poll
    log("== candidates")
    people = bd.build_people()
    by_idx = {p.idx: p for p in people}
    cand_api: dict[int, Api] = {}

    def onboard(p: bd.Person) -> dict:
        info: dict = {"idx": p.idx, "email": p.email, "kind": p.kind, "track": p.track, "level": p.level}
        api = Api(base).sign_in(p.email, p.name, "candidate")
        cand_api[p.idx] = api
        retention = (datetime.now(timezone.utc) + timedelta(days=365 if p.idx % 3 else 180)).isoformat()
        r = api.patch("/candidates/me/profile", json={"headline": f"{bd.TRACKS[p.track]['titles'][0]} based in {p.city}", "location": p.city,
                                                       "phone": p.phone, "talent_pool_opt_in": p.open_to_pool, "retention_until": retention})
        info["profile_status"] = r.status_code
        fname, data, ctype = bd.build_file(p)
        s = time.time()
        up = api.post("/candidates/me/resumes", files={"file": (fname, data, ctype)})
        info["upload_status"] = up.status_code
        if up.status_code != 201:
            info["upload_error"] = up.json().get("detail") if up.headers.get("content-type", "").startswith("application/json") else up.text[:200]
            return info
        rid = up.json()["id"]
        info["resume_id"] = rid
        st = {}
        for _ in range(180):
            st = api.get(f"/resumes/{rid}").json()
            if st["parse_status"] in ("parsed", "failed"):
                break
            time.sleep(2)
        info["parse_secs"] = round(time.time() - s, 1)
        info["parse_status"] = st.get("parse_status")
        info["parse_error"] = st.get("parse_error")
        info["extraction_method"] = st.get("extraction_method")
        info["integrity_flags"] = [f["type"] for f in st.get("integrity_flags", [])]
        info["warnings"] = st.get("warnings", [])
        info["n_skills"] = len(st.get("skills", []))
        log(f"  [{p.idx:2d}] {p.name:20s} {p.kind:10s} upload={up.status_code} parse={info['parse_status']} {info['parse_secs']}s flags={info['integrity_flags']} err={info['parse_error']}")
        return info

    with ThreadPoolExecutor(6) as ex:
        for info in ex.map(onboard, people):
            results["uploads"][str(info["idx"])] = info
    results["timing"]["onboard_secs"] = round(time.time() - t0, 1)

    # ---- applications
    log("== applications")
    app_ids: dict[tuple[int, str], str] = {}

    def apply_all(p: bd.Person) -> list[dict]:
        api = cand_api[p.idx]
        out = []
        for track in p.apply_tracks:
            jid = recs[track]["job_id"]
            r = api.post("/applications", json={"job_id": jid, "cover_note": f"Hello, I am {p.name} and I would like to join as {bd.TRACKS[track]['title']}."})
            row = {"idx": p.idx, "track": track, "status_code": r.status_code, "kind": p.kind}
            if r.status_code == 201:
                row["app_id"] = r.json()["id"]
            elif r.status_code == 409:
                mine = api.get("/applications/me").json()
                f = next((a for a in mine if a["job"]["id"] == jid and a["status"] != "withdrawn"), None)
                row["app_id"] = f["id"] if f else None
                row["note"] = "already applied"
            else:
                try:
                    row["error"] = r.json()
                except Exception:
                    row["error"] = r.text[:200]
            out.append(row)
        return out

    with ThreadPoolExecutor(6) as ex:
        for rows in ex.map(apply_all, people):
            results["applies"].extend(rows)
    ok = sum(1 for r in results["applies"] if r.get("app_id"))
    bad = [r for r in results["applies"] if not r.get("app_id")]
    log(f"  applications created/found: {ok}; rejected at submit: {len(bad)}")
    for r in bad:
        log(f"    idx={r['idx']} kind={r['kind']} -> {r['status_code']} {r['error'].get('detail') if isinstance(r.get('error'), dict) else r.get('error')}")
    # duplicate apply must 409
    first = next(r for r in results["applies"] if r.get("app_id") and r["status_code"] == 201)
    r = cand_api[first["idx"]].post("/applications", json={"job_id": recs[first["track"]]["job_id"]})
    log(f"  double apply -> {r.status_code} (expect 409)")
    results["double_apply_status"] = r.status_code
    (OUT / "load.json").write_text(json.dumps(results, indent=1, default=str))

    # ---- wait for assessments
    log("== waiting for AI assessments")
    deadline = time.time() + 40 * 60
    t1 = time.time()
    while time.time() < deadline:
        pending = 0
        total = 0
        failed = 0
        for track, r in recs.items():
            d = r["api"].get(f"/jobs/{r['job_id']}/applications").json()
            for it in d["items"]:
                total += 1
                if it["processing_state"] in ("queued", "processing"):
                    pending += 1
                elif it["processing_state"] == "failed":
                    failed += 1
        log(f"  t+{int(time.time()-t1)}s total={total} pending={pending} failed={failed}")
        if pending == 0:
            break
        time.sleep(15)
    results["timing"]["assess_wait_secs"] = round(time.time() - t1, 1)
    results["timing"]["total_secs"] = round(time.time() - t0, 1)
    (OUT / "load.json").write_text(json.dumps(results, indent=1, default=str))
    log("load stage done in", results["timing"])


def stage_reprocess(base: str) -> None:
    """Re-run parsing + assessment for every loaded resume (after a taxonomy / matching change). LLM extraction is cached."""
    people = bd.build_people()
    recs = get_ctx(base)
    n = 0
    for p in people:
        try:
            api = Api(base).sign_in(p.email, p.name, "candidate")
        except SystemExit:
            continue
        for r in api.get("/candidates/me/resumes").json():
            if r["parse_status"] == "parsed" and api.post(f"/resumes/{r['id']}/reprocess").status_code == 202:
                n += 1
    log(f"re-queued {n} resumes; waiting for assessments")
    deadline = time.time() + 40 * 60
    while time.time() < deadline:
        time.sleep(15)
        pend = sum(1 for r in recs.values() for it in r["api"].get(f"/jobs/{r['job_id']}/applications").json()["items"]
                   if it["processing_state"] in ("queued", "processing"))
        log(f"  pending={pend}")
        if pend == 0:
            break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000/api")
    ap.add_argument("--stage", default="all", choices=["load", "reprocess", "actions", "checks", "all"])
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    if args.stage in ("load", "all"):
        stage_load(base)
    if args.stage == "reprocess":
        stage_reprocess(base)
    if args.stage in ("actions", "checks", "all"):
        import seed_bulk_actions as sa

        if args.stage in ("actions", "all"):
            sa.stage_actions(base)
        if args.stage in ("checks", "all"):
            sa.stage_checks(base)


if __name__ == "__main__":
    main()
