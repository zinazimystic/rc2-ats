"""Offline keyword FAQ used when the language model is not configured or disabled."""
from __future__ import annotations

import re

_FAQ: list[tuple[tuple[str, ...], str]] = [
    (("privacy", "data", "gdpr", "delete my"),
     "**Privacy:** your resume and profile are only used to match you with jobs and are visible to recruiters when you apply. Chats with this assistant are not stored."),
    (("fair", "bias", "discriminat"),
     "**Fairness:** candidates are scored on evidence in their resume (skills, experience, projects) against the job requirements. Protected attributes such as age, gender or ethnicity are not used."),
    (("scor", "match", "rank"),
     "**Scoring:** each application is compared with the job's requirements and gets an evidence-based match score with the reasons behind it, so recruiters can see why someone ranks where they do."),
    (("verify", "verification", "code", "otp"),
     "**Email verification:** open your profile or account page and choose Verify email. We send a 6-digit code that is valid for 15 minutes; you can ask for a new one after a minute."),
    (("resume", "cv", "upload"),
     "**Resumes:** upload a PDF (up to 5 MB) from your candidate dashboard. We extract your skills and experience automatically; you can re-parse or delete a resume at any time."),
    (("apply", "application"),
     "**Applying:** browse open roles at /candidate/jobs, pick one, and apply with one of your uploaded resumes. You can track the status of each application from your dashboard."),
    (("interview", "schedule"),
     "**Interviews:** recruiters can propose interview times for shortlisted candidates, and candidates are notified in the app and can confirm."),
    (("job", "post", "hire", "recruiter"),
     "**For recruiters:** create a job at /recruiter/jobs, then review ranked applicants with evidence-based scores, shortlist and schedule interviews."),
    (("what", "platform", "do", "about", "hello", "hi", "help"),
     "**RC3 Talent Intelligence** helps candidates find and apply for jobs and helps recruiters screen applicants fairly with evidence-based scoring and interview scheduling."),
]
_DEFAULT = ("I'm running in basic mode right now, so I can only answer a few common questions about the platform: "
            "what it does, applying, resumes, scoring, fairness, email verification, interviews and privacy. Which would you like to know about?")


def answer(text: str) -> str:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    low = text.lower()
    for keys, reply in _FAQ[:-1]:
        if any((k in low) if len(k) > 3 else (k in words) for k in keys):
            return reply
    last_keys, last = _FAQ[-1]
    return last if words & set(last_keys) and len(words) <= 4 else _DEFAULT
