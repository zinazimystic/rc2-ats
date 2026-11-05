"""Pure scorer/matcher behaviour: no DB, no network."""
from __future__ import annotations

import pytest

from app.services.matching import matcher, scorer
from app.services.matching.explain import explain
from app.services.matching.specs import (
    CandidateSpec, ChunkSpec, EduSpec, ExpSpec, JobSpec, ProjSpec, ReqSpec, Semantics, SkillSpec,
)

REQS = (ReqSpec("Python", "required", 5), ReqSpec("Django", "required", 5), ReqSpec("Docker", "required", 3), ReqSpec("Redis", "preferred", 2))
JOB = JobSpec("Backend Developer", "backend apis", REQS, min_experience_years=3, education_level="bachelor")


def sk(name, ver="verified", presence="present", raw=None):
    return SkillSpec(name, raw or name, presence, ver, f"I used {name}", 0, 10)


def run(job, cand, sem=Semantics(False)):
    res = matcher.match_requirements(job, cand, sem)
    return res, scorer.score(job, cand, res, sem)


def test_exact_alias_related_unverified_absent_missing():
    cand = CandidateSpec(skills=(sk("Python", raw="python3"), sk("Flask"), sk("Docker", "unverified"), sk("Redis", presence="absent")))
    res, _ = run(JOB, cand)
    by = {r.skill: r for r in res}
    assert by["Python"].status == "evidenced" and by["Python"].credit == 1 and by["Python"].match_type == "exact"
    alias_job = JobSpec("x", "", (ReqSpec("k8s"),))
    assert matcher.match_requirements(alias_job, CandidateSpec(skills=(sk("Kubernetes"),)), Semantics(False))[0].match_type == "alias"
    assert by["Django"].status == "partial" and by["Django"].match_type == "related" and by["Django"].credit == pytest.approx(0.65)
    assert by["Docker"].status == "partial" and by["Docker"].credit == 0.5 and by["Docker"].match_type == "self_reported"
    assert by["Redis"].status == "confirmed_absent" and by["Redis"].credit == 0
    res2, _ = run(JOB, CandidateSpec(skills=(sk("Python"),)))
    assert {r.skill: r.status for r in res2}["Docker"] == "missing_evidence"  # missing evidence != confirmed absent


def test_declared_absent_beats_semantic_guess():
    cand = CandidateSpec(skills=(sk("Docker", presence="absent"),), chunks=(ChunkSpec("containers everywhere", 0, 20),))
    sem = Semantics(True, {2: (0.9, 0)})
    res, _ = run(JOB, cand, sem)
    assert res[2].status == "confirmed_absent"


def test_semantic_thresholds(monkeypatch):
    from app.core.config import settings

    cand = CandidateSpec(chunks=(ChunkSpec("We shipped services in containers", 5, 40, "experience"),))
    for sim, credit in ((0.9, 0.7), (settings.sem_strong, 0.7), (0.45, 0.35), (0.2, 0.0)):
        res = matcher.match_requirements(JOB, cand, Semantics(True, {2: (sim, 0)}))
        assert res[2].credit == credit
        if credit:
            assert res[2].match_type == "semantic" and res[2].evidence[0].similarity == round(sim, 3)


def test_weights_importance_and_required_vs_preferred():
    only_pref = CandidateSpec(skills=(sk("Redis"),))
    only_req = CandidateSpec(skills=(sk("Python"),))
    _, a = run(JOB, only_pref)
    _, b = run(JOB, only_req)
    assert b.components["skills"].score > a.components["skills"].score  # importance 5 required >> preferred 2
    # preferred weight is half of importance: Redis (2*0.5=1) of total (5+5+3+1=14)
    assert a.components["skills"].score == pytest.approx(100 / 14, abs=0.1)


def test_weights_renormalise_when_component_not_applicable():
    job = JobSpec("X", "", (), 0, "none", ())  # no requirements, no education -> skills & qualifications dropped
    _, s = run(job, CandidateSpec(experience=(ExpSpec("Dev", ("Python",), "2020-01", "2023-12"),)))
    assert not s.components["skills"].applicable and not s.components["qualifications"].applicable
    assert sum(c.weight for c in s.components.values()) == pytest.approx(100, abs=0.01)
    assert s.components["experience"].weight == pytest.approx(62.5, abs=0.01)  # 25/(25+15)


def test_total_is_sum_of_points_and_bounded():
    cand = CandidateSpec(skills=tuple(sk(r.skill) for r in REQS), experience=(ExpSpec("Backend Developer", ("Python", "Django"), "2015-01", "2024-01"),),
                         education=(EduSpec("master", "Computer Science"),), projects=(ProjSpec("P", "Python Django Docker", ("Python", "Django", "Docker")),))
    _, s = run(JOB, cand)
    assert 0 <= s.total <= 100
    assert s.total == pytest.approx(sum(c.points for c in s.components.values()), abs=0.15)
    assert s.total >= 90


def test_scoring_is_deterministic_and_ignores_input_order():
    cand = CandidateSpec(skills=(sk("Python"), sk("Flask"), sk("Docker", "fuzzy")))
    cand2 = CandidateSpec(skills=tuple(reversed(cand.skills)))
    assert run(JOB, cand)[1].total == run(JOB, cand)[1].total == run(JOB, cand2)[1].total


def test_experience_relevant_vs_other_and_claim_fallback():
    rel = ExpSpec("Backend Developer", ("Python", "Django"), "2021-01", "2023-12")
    other = ExpSpec("Barista", (), "2018-01", "2020-12", description="made coffee")
    s, d = scorer.experience_component(JOB, CandidateSpec(experience=(rel, other)))
    assert d["relevant_years"] == pytest.approx(3.0, abs=0.01) and d["other_years"] == pytest.approx(3.0, abs=0.01) and s == 100
    s, d = scorer.experience_component(JOB, CandidateSpec(experience=(other,)))
    assert s == pytest.approx(100 * 0.25 * 3 / 3, abs=0.5) and d["relevant_years"] == 0
    s, d = scorer.experience_component(JOB, CandidateSpec(total_years_claimed=2))
    assert d["claim_only"] and s == pytest.approx(40, abs=0.5)
    s, d = scorer.experience_component(JOB, CandidateSpec())
    assert s == 0 and d["missing_evidence"]
    s0, _ = scorer.experience_component(JobSpec("x", "", (), 0), CandidateSpec())
    assert s0 == 50  # no required years, no experience evidence


def test_unverified_experience_gets_no_credit():
    s, d = scorer.experience_component(JOB, CandidateSpec(experience=(ExpSpec("Backend Developer", ("Python",), "2015-01", "2023-01", verification="unverified"),)))
    assert s == 0


def test_qualifications_levels_and_missing_evidence():
    s, d = scorer.qualifications_component(JOB, CandidateSpec(education=(EduSpec("diploma", "Information Technology"),)))
    assert 50 < s < 100 and d["candidate_level"] == "diploma"
    s, d = scorer.qualifications_component(JOB, CandidateSpec())
    assert s == 0 and d["missing_evidence"] is True  # not "has no degree"
    s, _ = scorer.qualifications_component(JobSpec("x"), CandidateSpec())
    assert s is None
    job = JobSpec("x", "", (), 0, "bachelor", ("AWS Certified Developer",))
    s_with, d = scorer.qualifications_component(job, CandidateSpec(education=(EduSpec("bachelor", "Computer Science"),), certifications=("AWS Certified Developer - Associate",)))
    s_without, _ = scorer.qualifications_component(job, CandidateSpec(education=(EduSpec("bachelor", "Computer Science"),)))
    assert s_with > s_without and d["certifications_matched"]


def test_projects_missing_and_related():
    s, d = scorer.projects_component(JOB, CandidateSpec(), Semantics(False))
    assert s == 0 and d["missing_evidence"]
    full = CandidateSpec(projects=(ProjSpec("A", "x", ("Python", "Django", "Docker")),))
    rel = CandidateSpec(projects=(ProjSpec("B", "x", ("Flask",)),))
    none = CandidateSpec(projects=(ProjSpec("C", "x", ("React",)),))
    assert scorer.projects_component(JOB, full, Semantics(False))[0] > scorer.projects_component(JOB, rel, Semantics(False))[0] > scorer.projects_component(JOB, none, Semantics(False))[0]


def test_explanation_sections_and_learning_subset_of_gaps():
    cand = CandidateSpec(skills=(sk("Python"),))
    res, s = run(JOB, cand)
    ex = explain(JOB, cand, res, s.components, s.total, Semantics(False), [{"type": "hidden_text", "message": "m", "severity": "critical"}], use_llm=False)
    gaps = {r.skill for r in res if r.credit < 0.7}
    assert {l.skill for l in ex.learning} <= gaps and ex.learning
    assert any("Docker" in g for g in ex.gaps) and ex.summary_method == "template"
    types = {f.type for f in ex.flags}
    assert {"hidden_text", "no_projects", "semantic_unavailable"} <= types


def test_llm_narrative_cannot_invent_learning_skills(monkeypatch):
    from tests.fakes import install_fake_llm

    cand = CandidateSpec(skills=(sk("Python"),))
    res, s = run(JOB, cand)
    install_fake_llm(monkeypatch, lambda sys, user, m: {"summary": "A neutral summary.", "learning": [
        {"skill": "Docker", "suggestion": "Containerize an app."}, {"skill": "Quantum Basket Weaving", "suggestion": "invented"}]})
    ex = explain(JOB, cand, res, s.components, s.total, Semantics(False), [], use_llm=True)
    assert ex.summary_method == "llm" and ex.summary == "A neutral summary."
    assert [l.skill for l in ex.learning] == ["Docker"]


def test_llm_narrative_failure_falls_back_to_template(monkeypatch):
    from tests.fakes import install_fake_llm
    from app.services.ai import llm

    def boom(*a):
        raise llm.LLMError("bad")

    install_fake_llm(monkeypatch, boom)
    cand = CandidateSpec(skills=(sk("Python"),))
    res, s = run(JOB, cand)
    ex = explain(JOB, cand, res, s.components, s.total, Semantics(False), [], use_llm=True)
    assert ex.summary_method == "template" and "Scored" in ex.summary


def test_tools_are_not_aliases_of_umbrella_skills():
    """A candidate who lists only Selenium / Jenkins / dbt must not get full credit for Test Automation / CI/CD / Airflow."""
    from app.services.parsing.normalizer import taxonomy

    tax = taxonomy()
    for tool, umbrella in [("Selenium", "Test Automation"), ("Jenkins", "CI/CD"), ("dbt", "Data Engineering"), ("Hadoop", "Spark"),
                           ("JUnit", "Unit Testing"), ("Dart", "Flutter"), ("scikit-learn", "Machine Learning")]:
        assert tax.canonical(tool) == tool != tax.canonical(umbrella)
        assert tax.related(umbrella).get(tool, 0) >= 0.3 and tax.related(tool).get(umbrella, 0) >= 0.3
    assert tax.canonical("Apache Airflow") == "Airflow" and tax.canonical("ETL pipelines") == "ETL"
    for skill in ("MLOps", "Computer Vision", "Snowflake", "BigQuery", "Firebase", "Maven", "Cypress", "JMeter"):
        assert tax.known(skill), skill


def test_requirement_embedding_text_is_descriptive():
    from app.services.matching import builders

    assert "continuous integration" in builders.req_text("CI/CD").lower()
    assert builders.req_text("Some Unknown Tool") == "Experience with Some Unknown Tool"
