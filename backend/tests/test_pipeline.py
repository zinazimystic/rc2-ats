"""End-to-end AI pipeline on SQLite with fake embeddings and no LLM (rules extraction), driven through the real functions."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Application, Assessment, CandidateSkill, DuplicateFlag, Job, Resume
from app.services import pipeline, tasks
from tests.ai_helpers import mk_app, mk_job, mk_resume, mk_user


def _setup(db, demo_pdfs, names=("strong", "partial", "weak")):
    rec = mk_user(db, "rec@example.com", "Rita Recruiter", "recruiter")
    job = mk_job(db, rec)
    people = {"strong": ("aisha.rahman.acct@example.org", "Aisha Rahman"), "partial": ("omar.acct@example.org", "Omar Siddiqui"),
              "weak": ("sana.acct@example.org", "Sana Malik"), "duplicate": ("dup.acct@example.org", "Aisha R."),
              "scanned": ("scan.acct@example.org", "Scan Ned"), "injection": ("inj.acct@example.org", "Ivy Jection")}
    out = {}
    for n in names:
        email, name = people[n]
        u = mk_user(db, email, name)
        r = mk_resume(db, u, demo_pdfs[n])
        a = mk_app(db, job, u, r)
        out[n] = (u, r.id, a.id)
    return rec, job, out


def _run(db, out):
    for n, (u, rid, aid) in out.items():
        pipeline.enqueue_resume(rid)
    db.expire_all()


def test_demo_ranking_and_evidence(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs)
    _run(db, out)
    scores = {}
    for n, (_, rid, aid) in out.items():
        a = db.get(Application, aid)
        assert a.processing_state == "done", (n, a.processing_error)
        assert a.status == "ai_assessed"
        scores[n] = db.scalars(select(Assessment).where(Assessment.application_id == aid)).one()
    assert scores["strong"].total_score > scores["partial"].total_score > scores["weak"].total_score
    assert scores["strong"].total_score >= 80
    assert scores["weak"].total_score <= 40

    # partial candidate: Docker is MISSING EVIDENCE (not absent), Django only via related Flask
    reqs = {r["skill"]: r for r in scores["partial"].requirements}
    assert reqs["Docker"]["status"] == "missing_evidence" and reqs["Docker"]["credit"] == 0
    assert reqs["Django"]["match_type"] == "related" and 0 < reqs["Django"]["credit"] <= 0.7
    assert reqs["Python"]["status"] == "evidenced"
    assert any("Docker" in g for g in scores["partial"].gaps)
    assert any(s["skill"] == "Docker" for s in scores["partial"].learning_suggestions)

    # every evidenced requirement quotes the resume verbatim, with offsets that index into resume.text
    strong_resume = db.scalars(select(Resume).where(Resume.id == out["strong"][1])).one()
    text = strong_resume.text
    for r in scores["strong"].requirements:
        if r["status"] == "evidenced":
            ev = r["evidence"][0]
            assert text[ev["start"]:ev["end"]] == ev["quote"].strip() or ev["quote"].strip() in text
    assert scores["strong"].semantic_available is True
    assert scores["strong"].summary_method == "template"
    assert strong_resume.extraction_method == "rules"
    assert strong_resume.parse_status == "parsed" and strong_resume.page_count == 1
    assert {s.name for s in strong_resume.skills} >= {"Python", "Django", "PostgreSQL", "Docker"}
    assert len(strong_resume.chunks) >= 2 and all(c.embedding for c in strong_resume.chunks)
    assert strong_resume.doc_embedding


def test_scoring_is_deterministic(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    aid = out["strong"][2]
    first = db.scalars(select(Assessment).where(Assessment.application_id == aid)).one().total_score
    pipeline.enqueue_assessment(aid)
    db.expire_all()
    assert db.scalars(select(Assessment).where(Assessment.application_id == aid)).one().total_score == first


def test_override_survives_reassessment(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("weak",))
    _run(db, out)
    aid = out["weak"][2]
    a = db.scalars(select(Assessment).where(Assessment.application_id == aid)).one()
    a.override_score, a.override_reason = 90.0, "great portfolio"
    db.commit()
    pipeline.enqueue_assessment(aid)
    db.expire_all()
    a = db.scalars(select(Assessment).where(Assessment.application_id == aid)).one()
    assert a.override_score == 90.0 and a.effective_score == 90.0


def test_scanned_pdf_fails_cleanly(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("scanned",))
    _run(db, out)
    u, rid, aid = out["scanned"]
    r = db.get(Resume, rid)
    assert r.parse_status == "failed" and "scanned" in r.parse_error.lower()
    a = db.get(Application, aid)
    assert a.processing_state == "failed" and a.status == "submitted" and a.processing_error


def test_garbage_and_encrypted_files_fail_cleanly(db, demo_pdfs):
    import pymupdf

    rec = mk_user(db, "r2@example.com", "R Two", "recruiter")
    u = mk_user(db, "c2@example.com", "Cee Two")
    bad = mk_resume(db, u, b"%PDF-1.4 this is not really a pdf")
    pipeline.enqueue_resume(bad.id)
    db.expire_all()
    assert db.get(Resume, bad.id).parse_status == "failed"
    doc = pymupdf.open(stream=demo_pdfs["strong"], filetype="pdf")
    enc = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    r2 = mk_resume(db, u, enc)
    pipeline.enqueue_resume(r2.id)
    db.expire_all()
    r = db.get(Resume, r2.id)
    assert r.parse_status == "failed" and "password" in r.parse_error.lower()


def test_hidden_text_and_injection_are_flagged_and_ignored(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("injection", "weak"))
    _run(db, out)
    r = db.get(Resume, out["injection"][1])
    kinds = {f["type"] for f in r.integrity_flags}
    assert "hidden_text" in kinds and "prompt_injection" in kinds
    assert "Kubernetes" not in (r.text or "") and "Ignore all previous" not in r.text
    a_inj = db.scalars(select(Assessment).where(Assessment.application_id == out["injection"][2])).one()
    a_weak = db.scalars(select(Assessment).where(Assessment.application_id == out["weak"][2])).one()
    assert a_inj.total_score == a_weak.total_score  # the hidden instructions changed nothing
    assert any(f["type"] == "hidden_text" for f in a_inj.flags)


def test_candidate_removed_skill_is_not_resurrected_on_reprocess(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    rid = out["strong"][1]
    sk = db.scalars(select(CandidateSkill).where(CandidateSkill.resume_id == rid, CandidateSkill.name == "Docker")).one()
    sk.presence, sk.source = "absent", "candidate"
    db.commit()
    pipeline.enqueue_resume(rid)
    db.expire_all()
    sk = db.scalars(select(CandidateSkill).where(CandidateSkill.resume_id == rid, CandidateSkill.name == "Docker")).one()
    assert sk.presence == "absent"
    a = db.scalars(select(Assessment).where(Assessment.application_id == out["strong"][2])).one()
    docker = next(r for r in a.requirements if r["skill"] == "Docker")
    assert docker["status"] == "confirmed_absent"


def test_semantic_unavailable_degrades_to_keywords(db, demo_pdfs, monkeypatch):
    from app.services.ai import embeddings

    monkeypatch.setattr(embeddings, "embeddings_available", lambda: False)
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    a = db.scalars(select(Assessment).where(Assessment.application_id == out["strong"][2])).one()
    assert a.semantic_available is False and a.total_score >= 70
    assert any(f["type"] == "semantic_unavailable" for f in a.flags)
    assert any("Semantic" in w for w in db.get(Resume, out["strong"][1]).warnings)


def test_embedding_outage_mid_pipeline_is_tolerated(db, demo_pdfs, monkeypatch):
    from app.services.ai import embeddings

    def boom(texts):
        raise embeddings.EmbeddingUnavailable("token expired")

    monkeypatch.setattr(embeddings, "embed_texts", boom)
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    _run(db, out)
    assert db.get(Application, out["strong"][2]).processing_state == "done"


def test_duplicate_detection_flags_pair_without_merging(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong", "duplicate"))
    _run(db, out)
    flags = db.scalars(select(DuplicateFlag)).all()
    assert len(flags) == 1
    f = flags[0]
    assert f.status == "pending"
    assert any("email" in r.lower() or "phone" in r.lower() for r in f.reasons)
    assert str(f.candidate_a_id) < str(f.candidate_b_id)
    assert db.get(Application, out["duplicate"][2]).is_duplicate is True
    from app.models import User
    from app.services import duplicates

    actor = db.get(User, rec.id)
    duplicates.merge(db, f, actor)
    db.commit()
    db.expire_all()
    assert db.get(DuplicateFlag, f.id).status == "confirmed"
    dup_user = db.get(User, out["duplicate"][0].id)
    assert dup_user.profile.merged_into_id == out["strong"][0].id
    assert db.get(Resume, out["duplicate"][1]) is not None  # nothing deleted


def test_job_requirement_change_triggers_requeue_and_rescore(db, demo_pdfs):
    from app.models import JobRequirement

    rec, job, out = _setup(db, demo_pdfs, ("partial",))
    _run(db, out)
    aid = out["partial"][2]
    before = db.scalars(select(Assessment).where(Assessment.application_id == aid)).one().total_score
    db.add(JobRequirement(job_id=job.id, skill="Flask", kind="required", importance=5, position=9))
    db.get(Job, job.id).version = 2
    db.commit()
    pipeline.enqueue_assessment(aid)
    db.expire_all()
    a = db.scalars(select(Assessment).where(Assessment.application_id == aid)).one()
    assert a.job_version == 2 and a.total_score > before
    assert any(r["skill"] == "Flask" and r["status"] == "evidenced" for r in a.requirements)


def test_recover_stuck_requeues_work(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("strong",))
    # nothing was processed: resume is 'pending', application 'queued' (as after a crash)
    n = tasks.recover_stuck()
    assert n >= 2
    db.expire_all()
    assert db.get(Application, out["strong"][2]).processing_state == "done"


def test_withdrawn_application_is_not_assessed(db, demo_pdfs):
    rec, job, out = _setup(db, demo_pdfs, ("weak",))
    a = db.get(Application, out["weak"][2])
    a.status = "withdrawn"
    db.commit()
    _run(db, out)
    db.expire_all()
    assert db.get(Application, out["weak"][2]).status == "withdrawn"
    assert db.scalars(select(Assessment).where(Assessment.application_id == out["weak"][2])).first() is None
