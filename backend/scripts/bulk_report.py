"""Model-quality report for the bulk load: scores by ground-truth level per job, cross-track averages, stealth/injection/hidden checks.

    python scripts/bulk_report.py [--base-url http://localhost:8000/api] [--verbose]
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bulk_data as bd  # noqa: E402
from seed_bulk import OUT, Api, get_ctx  # noqa: E402

LEVELS = ["strong", "stealth", "medium", "weak"]


def norm(s: str) -> str:
    return " ".join(s.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000/api")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    people = bd.build_people()
    by_email = {p.email: p for p in people}
    recs = get_ctx(args.base_url)

    own: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))  # track -> level -> scores
    cross: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []
    states: dict[str, int] = defaultdict(int)
    problems: list[str] = []
    stealth_rows: list[str] = []
    inj_rows: list[str] = []
    ev_checked = ev_bad = 0
    no_evidence_explanations = 0
    reqs_total = 0
    assess_secs: list[float] = []

    for track, r in recs.items():
        api: Api = r["api"]
        items = api.get(f"/jobs/{r['job_id']}/applications").json()["items"]
        t = bd.TRACKS[track]
        for it in items:
            states[it["processing_state"]] += 1
            p = by_email.get(it["candidate"]["email"])
            if it["processing_state"] == "failed":
                problems.append(f"{track}: {it['candidate']['full_name']} FAILED: {it.get('processing_error')}")
            if p is None or it["total_score"] is None:
                continue
            sc = it["total_score"]  # AI score (ignores recruiter overrides)
            all_scores.append(sc)
            if p.kind in ("injection", "hidden", "duplicate", "docx", "scanned", "encrypted", "empty", "corrupt", "nonresume", "wrongtype"):
                tag = f"{p.kind}:{p.track}"
                if p.track == track:
                    d = api.get(f"/applications/{it['id']}").json()
                    flags = [f["type"] for f in (d.get("assessment") or {}).get("flags", [])] + [f["type"] for f in (d.get("resume") or {}).get("integrity_flags", [])]
                    inj_rows.append(f"  {tag:22s} {p.name:18s} score={sc:5.1f} level={p.level:6s} flags={sorted(set(flags))} matched={it['matched_skills']} missing={it['missing_skills']}")
                continue
            if p.track == track:
                own[track][p.level].append(sc)
                d = api.get(f"/applications/{it['id']}").json()
                a = d.get("assessment") or {}
                txt = (d.get("resume") or {}).get("text") or ""
                for rq in a.get("requirements", []):
                    reqs_total += 1
                    if rq["status"] in ("present", "partial", "inferred", "related") and not rq["evidence"]:
                        no_evidence_explanations += 1
                    for ev in rq["evidence"]:
                        ev_checked += 1
                        if norm(ev["quote"]) not in norm(txt):
                            ev_bad += 1
                if p.level == "stealth":
                    plain = set(t["plain"])
                    for rq in a.get("requirements", []):
                        if rq["skill"] in plain:
                            stealth_rows.append(f"  {track:10s} {p.name:16s} {rq['skill']:18s} status={rq['status']:9s} credit={rq['credit']:.2f} match={rq['match_type']:9s} via={rq.get('matched_as')}")
                if args.verbose:
                    print(f"  [{track}/{p.level}] {p.name}: {sc} matched={it['matched_skills']} missing={it['missing_skills']} flags={[f['type'] for f in it['flags']]}")
            else:
                cross[track].append(sc)

    avg = lambda xs: f"{st.mean(xs):5.1f}" if xs else "  -  "  # noqa: E731
    print("\n=== Average AI score per job by ground-truth level (own-track candidates) ===")
    print(f"{'job':12s} " + " ".join(f"{lv:>8s}" for lv in LEVELS) + f" {'other-trk':>10s}   ordering")
    ok_orders = 0
    cols = {lv: [] for lv in LEVELS}
    cr_all: list[float] = []
    for track in bd.TRACK_ORDER:
        row = {lv: own[track].get(lv, []) for lv in LEVELS}
        m = {lv: (st.mean(v) if v else None) for lv, v in row.items()}
        for lv in LEVELS:
            if row[lv]:
                cols[lv].extend(row[lv])
        cr = cross.get(track, [])
        cr_all.extend(cr)
        chain = [m["strong"], m["stealth"], m["medium"], m["weak"], st.mean(cr) if cr else None]
        vals = [x for x in chain if x is not None]
        good = all(a >= b - 0.01 for a, b in zip(vals, vals[1:]))
        ok_orders += good
        print(f"{track:12s} " + " ".join(f"{avg(row[lv]):>8s}" for lv in LEVELS) + f" {avg(cr):>10s}   {'OK' if good else 'VIOLATION'}")
    print(f"{'ALL':12s} " + " ".join(f"{avg(cols[lv]):>8s}" for lv in LEVELS) + f" {avg(cr_all):>10s}   {ok_orders}/10 jobs ordered strong>=stealth>=medium>=weak>=other")
    if all_scores:
        print(f"\nScore distribution: min={min(all_scores):.1f} p25={st.quantiles(all_scores, n=4)[0]:.1f} median={st.median(all_scores):.1f} p75={st.quantiles(all_scores, n=4)[2]:.1f} max={max(all_scores):.1f}  (n={len(all_scores)})")
    print(f"Processing states: {dict(states)}")

    print("\n=== Stealth candidates: plain-worded core skills must not be 'missing' ===")
    print("\n".join(stealth_rows) or "  (none)")
    miss = [s for s in stealth_rows if "status=missing" in s]
    print(f"  -> {len(stealth_rows) - len(miss)}/{len(stealth_rows)} credited")

    print("\n=== Edge documents (own job) ===")
    print("\n".join(inj_rows) or "  (none)")

    print(f"\nEvidence: {ev_checked} quotes checked, {ev_bad} not verbatim in resume text; claims with no evidence: {no_evidence_explanations}/{reqs_total} requirement rows")
    if problems:
        print("\nFailed applications:")
        print("\n".join("  " + x for x in problems))

    f = OUT / "load.json"
    if f.exists():
        res = json.loads(f.read_text())
        ps = [u["parse_secs"] for u in res["uploads"].values() if u.get("parse_secs")]
        if ps:
            print(f"\nParse time (upload->parsed, concurrent x6): mean={st.mean(ps):.1f}s max={max(ps):.1f}s n={len(ps)}")
        print("Timing:", res.get("timing"))
        print("Extraction accuracy:", {k: (round(v['precision'], 2), round(v['recall'], 2)) for k, v in res.get("extraction", {}).items()})
        print("Upload outcomes:")
        for u in res["uploads"].values():
            if u["kind"] != "normal":
                print(f"  {u['kind']:10s} upload={u['upload_status']} parse={u.get('parse_status')} err={u.get('parse_error') or u.get('upload_error')} flags={u.get('integrity_flags')}")


if __name__ == "__main__":
    main()
