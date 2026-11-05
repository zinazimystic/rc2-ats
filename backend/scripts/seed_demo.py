"""Seed the demo scenario through the PUBLIC API (so it exercises the real pipeline).

    python scripts/seed_demo.py [--base-url http://localhost:8000/api] [--invite-code ...]

Demo logins (password for all: Demo1234!):
    recruiter  recruiter@demo.rc3.dev
    candidates alice.khan@demo.rc3.dev, bilal.ahmed@demo.rc3.dev, carla.meyer@demo.rc3.dev
Idempotent: existing accounts are signed in instead of re-created; an existing job with the same title is reused.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

PASSWORD = "Demo1234!"
RECRUITER = ("recruiter@demo.rc3.dev", "Rita Recruiter")
JOB_TITLE = "Backend Developer"
JOB = {
    "title": JOB_TITLE,
    "department": "Engineering",
    "location": "Remote",
    "work_mode": "remote",
    "description": (
        "We are looking for a Backend Developer to build and maintain our APIs. You will design services in Python and "
        "Django, model data in PostgreSQL, and ship them in Docker containers. 3+ years of experience and a bachelor's "
        "degree in Computer Science or a related field are preferred. REST API design and Git are expected; AWS is a plus."
    ),
    "min_experience_years": 3,
    "education_level": "bachelor",
    "qualifications": ["Bachelor's degree in Computer Science or related field"],
    "requirements": [
        {"skill": "Python", "kind": "required", "importance": 5},
        {"skill": "Django", "kind": "required", "importance": 5},
        {"skill": "PostgreSQL", "kind": "required", "importance": 4},
        {"skill": "Docker", "kind": "required", "importance": 4},
        {"skill": "REST API", "kind": "preferred", "importance": 3},
        {"skill": "AWS", "kind": "preferred", "importance": 2},
    ],
}

RESUMES = {
    "alice.khan@demo.rc3.dev": (
        "Alice Khan",
        """Alice Khan
Senior Backend Engineer | Lahore, Pakistan | alice.khan@demo.rc3.dev

SUMMARY
Backend engineer with 6 years of experience building Python and Django services on PostgreSQL.

EXPERIENCE
Senior Backend Engineer, Nimbus Labs (2021-03 - Present)
- Built REST APIs with Django REST Framework serving 2M requests per day.
- Designed PostgreSQL schemas, indexes and migrations; cut report query time by 70 percent.
- Containerised services with Docker and deployed them on AWS ECS.

Backend Developer, Orbit Soft (2018-06 - 2021-02)
- Developed Python microservices, wrote unit tests with pytest and used Git for code review.

PROJECTS
Inventory API - Django, PostgreSQL, Docker. Multi-tenant inventory service with role-based access.

EDUCATION
BS Computer Science, FAST University (2014 - 2018)

SKILLS
Python, Django, PostgreSQL, Docker, REST API, AWS, Git, pytest
""",
    ),
    "bilal.ahmed@demo.rc3.dev": (
        "Bilal Ahmed",
        """Bilal Ahmed
Software Developer | Karachi, Pakistan | bilal.ahmed@demo.rc3.dev

SUMMARY
Developer with 2 years of experience in Python web development.

EXPERIENCE
Software Developer, Pixel Works (2023-01 - Present)
- Built internal tools in Python and Flask backed by MySQL.
- Wrote REST endpoints and used Git daily.

PROJECTS
Expense Tracker - Python, Flask, SQLite. Personal finance web app.

EDUCATION
BS Software Engineering, NED University (2018 - 2022)

SKILLS
Python, Flask, MySQL, Git, REST API
""",
    ),
    "carla.meyer@demo.rc3.dev": (
        "Carla Meyer",
        """Carla Meyer
Frontend Engineer | Berlin, Germany | carla.meyer@demo.rc3.dev

SUMMARY
Frontend engineer with 4 years of experience building React applications.

EXPERIENCE
Frontend Engineer, Bluepeak (2021-09 - Present)
- Built React and TypeScript dashboards with design-system components.
- Collaborated with backend teams and consumed REST APIs.

EDUCATION
BA Information Design, HfG Berlin (2016 - 2020)

SKILLS
JavaScript, TypeScript, React, CSS, Figma, Git
""",
    ),
}


def make_pdf(text: str) -> bytes:
    """Render plain text to a real, text-selectable PDF (PyMuPDF)."""
    import pymupdf

    doc = pymupdf.open()
    lines = text.splitlines()
    per_page = 52
    for i in range(0, len(lines), per_page):
        page = doc.new_page()
        page.insert_text((50, 60), "\n".join(lines[i : i + per_page]), fontsize=10, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def signed_in_client(base: str, email: str, name: str, role: str, invite: str | None) -> httpx.Client:
    c = httpx.Client(base_url=base, timeout=120.0)
    body = {"email": email, "password": PASSWORD, "full_name": name, "role": role}
    if role == "recruiter" and invite:
        body["invite_code"] = invite
    r = c.post("/auth/register", json=body)
    if r.status_code == 409:
        r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code not in (200, 201):
        die(f"auth failed for {email}: {r.status_code} {r.text}")
    print(f"  signed in {role}: {email}")
    return c


def wait_assessed(rec: httpx.Client, app_id: str, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = rec.get(f"/applications/{app_id}").json()
        if d["processing_state"] in ("done", "failed"):
            return d
        time.sleep(2)
    die(f"application {app_id} was not processed within {timeout:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000/api")
    ap.add_argument("--invite-code", default=None, help="RECRUITER_INVITE_CODE if the server requires one")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    health = httpx.get(f"{base}/health", timeout=15)
    if health.status_code != 200:
        die(f"API not reachable at {base}")
    print("Health:", {k: v for k, v in health.json().items() if k in ("status", "database_backend")}, "llm_ok=", health.json()["llm"]["ok"])

    print("Recruiter")
    rec = signed_in_client(base, RECRUITER[0], RECRUITER[1], "recruiter", args.invite_code)
    existing = [j for j in rec.get("/jobs").json() if j["title"] == JOB_TITLE]
    if existing:
        job_id = existing[0]["id"]
        print(f"  reusing job {job_id}")
    else:
        r = rec.post("/jobs", json=JOB)
        if r.status_code != 201:
            die(f"create job: {r.status_code} {r.text}")
        job_id = r.json()["id"]
        print(f"  created job {job_id}")

    print("Candidates")
    app_ids: dict[str, str] = {}
    for email, (name, text) in RESUMES.items():
        c = signed_in_client(base, email, name, "candidate", None)
        mine = c.get("/applications/me").json()
        found = next((a for a in mine if a["job"]["id"] == job_id and a["status"] != "withdrawn"), None)
        if found:
            app_ids[email] = found["id"]
            print(f"  {name}: already applied")
            continue
        up = c.post("/candidates/me/resumes", files={"file": (f"{name.replace(' ', '_')}_CV.pdf", make_pdf(text), "application/pdf")})
        if up.status_code != 201:
            die(f"upload for {name}: {up.status_code} {up.text}")
        rid = up.json()["id"]
        for _ in range(90):  # poll until parsed
            st = c.get(f"/resumes/{rid}").json()
            if st["parse_status"] in ("parsed", "failed"):
                break
            time.sleep(2)
        print(f"  {name}: resume {st['parse_status']} ({st.get('extraction_method')})")
        r = c.post("/applications", json={"job_id": job_id, "cover_note": f"Hello, I'm {name} and I'd love to join the team."})
        if r.status_code != 201:
            die(f"apply for {name}: {r.status_code} {r.text}")
        app_ids[email] = r.json()["id"]

    print("Waiting for AI assessments")
    ranked = []
    for email, aid in app_ids.items():
        d = wait_assessed(rec, aid)
        score = d["assessment"]["effective_score"] if d.get("assessment") else None
        print(f"  {d['candidate']['full_name']}: {d['status']} score={score}")
        ranked.append((score or -1, aid, d))
    ranked.sort(key=lambda t: t[0], reverse=True)

    best_score, best_id, best = ranked[0]
    if best["status"] in ("ai_assessed", "recruiter_review") and best_score >= 0:
        r = rec.post(f"/applications/{best_id}/transition", json={"to_status": "shortlisted"})
        print("Shortlisted top candidate:", r.status_code)
    if best["status"] in ("ai_assessed", "recruiter_review", "shortlisted") or best["status"] == "interview":
        q = rec.post(f"/applications/{best_id}/questions/generate", json={})
        print("Interview questions:", q.status_code, f"({len(q.json())} generated)" if q.status_code == 200 else q.json().get("detail"))
        start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        r = rec.post(
            f"/applications/{best_id}/interviews",
            json={"interviewer_name": "Sam Interviewer", "interviewer_email": "sam@demo.rc3.dev", "interview_type": "technical",
                  "start_at": start.isoformat(), "duration_minutes": 60, "location": "https://meet.example.com/demo"},
        )
        print("Interview scheduled:", r.status_code, "" if r.status_code == 201 else r.json().get("detail"))

    kpis = rec.get("/analytics/overview").json()["kpis"]
    print("Dashboard KPIs:", kpis)
    print(f"\nDone. Sign in as {RECRUITER[0]} / {PASSWORD}")


if __name__ == "__main__":
    main()
