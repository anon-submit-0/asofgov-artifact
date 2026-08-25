#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6 summary builder — deterministic, zero LLM calls (PREREG §S6;
sha256 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669).

Reads ONLY:
  * s6/runs_en/<arm>/<qid>.json      (Stage B caches, this study)
  * pilot2/pilot2_arms_summary.json  (frozen ZH per-question verdict matrix)
  * pilot2/make_pilot2_summary.py    (frozen PROBE7 list, PREREG_pilot2_arms §5.2)
  * pilot2/domains/*/questions.json  (frozen gold-side metadata, via R2.questions)
  * s6/FREEZE_questions_en.sha256 + s6/questions_en.json (freeze re-check)

Writes ONLY (append-only; refuses overwrite):
  * s6/s6_summary.json

Adjudicates S6-P1..P4 exactly as pre-registered:
  P1  EN backbone error within 0.600 +/- 0.10
  P2  EN governance-informed error within 0.467 +/- 0.10
  P3  EN backbone error > EN governance error
  P4  of the 7 probe-only refusal questions, EN governance arm errs >= 4

PROBE7 provenance: the frozen list in pilot2/make_pilot2_summary.py
(`PROBE7 = ["FIN-Q7","F1-Q7","DEB-Q6","EF2-Q5","CARD-Q7","F1-Q8","EF2-Q6"]`,
comment: PREREG §5.2 冻结题集 决定性探针 7 题), mirrored in
pilot2_arms_summary.json -> governance_informed_arm.probe7_metadata_undecidable
and in paper/figures/fig_data_pilot2.json -> gov_arm.probe7_errors (§7.3a).
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import re
import sys

P2 = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2").resolve()
S6 = P2 / "poststudy2_20260823" / "s6"
OUT = S6 / "s6_summary.json"
PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"
ARMS = ("baseline_claude", "governance_informed")


def probe7_from_frozen() -> list[str]:
    """Parse the frozen PROBE7 literal out of make_pilot2_summary.py (no import,
    no execution — pure text parse of the frozen file)."""
    src = (P2 / "make_pilot2_summary.py").read_text(encoding="utf-8")
    m = re.search(r"^PROBE7\s*=\s*(\[.*?\])", src, re.M | re.S)
    assert m, "PROBE7 literal not found in frozen make_pilot2_summary.py"
    lst = ast.literal_eval(m.group(1))
    assert len(lst) == 7 and len(set(lst)) == 7
    return lst


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"[REFUSE] overwrite existing summary: {OUT}")

    # freeze re-check on the EN question set
    want = (S6 / "FREEZE_questions_en.sha256").read_text(encoding="utf-8").split()[0]
    got = hashlib.sha256((S6 / "questions_en.json").read_bytes()).hexdigest()
    assert got == want, "questions_en.json freeze sha mismatch"

    # frozen ZH verdict matrix + frozen gold-side metadata
    zh = json.loads((P2 / "pilot2_arms_summary.json").read_text(encoding="utf-8"))
    zh_pq = zh["per_question_verdicts"]                     # qid -> arm -> verdict
    probe7 = probe7_from_frozen()
    zh_probe7 = zh["governance_informed_arm"]["probe7_metadata_undecidable"]
    assert set(zh_probe7) == set(probe7), "PROBE7 drift vs frozen summary"

    qmeta = {}                                              # qid -> (expected_kind, refusal_reason, cluster)
    for d in sorted((P2 / "domains").iterdir()):
        if not d.is_dir() or d.name.startswith("._") or not (d / "questions.json").is_file():
            continue
        for q in json.loads((d / "questions.json").read_text(encoding="utf-8")):
            qmeta[q["qid"]] = {"expected_kind": q["expected_kind"],
                               "refusal_reason": q.get("refusal_reason"),
                               "cluster": d.name}
    assert len(qmeta) == 60

    # Stage B caches
    en = {}                                                 # arm -> qid -> record
    for arm in ARMS:
        recs = {}
        for qid in qmeta:
            p = S6 / "runs_en" / arm / f"{qid}.json"
            assert p.is_file(), f"missing EN cache {arm}/{qid}"
            recs[qid] = json.loads(p.read_text(encoding="utf-8"))
        assert len(recs) == 60
        en[arm] = recs

    verdicts = ("correct", "wrong_value", "execution_error",
                "answered_should_refuse", "refused_should_answer", "no_sql")

    def err_count(recs):
        return sum(1 for r in recs.values() if r["verdict"] != "correct")

    err = {arm: err_count(en[arm]) for arm in ARMS}
    rate = {arm: err[arm] / 60 for arm in ARMS}
    taxonomy = {arm: {v: sum(1 for r in en[arm].values() if r["verdict"] == v)
                      for v in verdicts
                      if sum(1 for r in en[arm].values() if r["verdict"] == v)}
                for arm in ARMS}
    empty = {arm: sum(1 for r in en[arm].values() if r.get("empty_response"))
             for arm in ARMS}

    refusal_qids = sorted(q for q, m in qmeta.items() if m["expected_kind"] == "refusal")
    value_qids = sorted(q for q, m in qmeta.items() if m["expected_kind"] != "refusal")
    refusal_stats = {arm: {
        "correct_refusals": sum(1 for q in refusal_qids
                                if en[arm][q]["verdict"] == "correct"),
        "n_refusal_questions": len(refusal_qids),
        "over_refusals_on_answer_questions": sum(
            1 for q in value_qids
            if en[arm][q]["verdict"] == "refused_should_answer"),
        "n_answer_questions": len(value_qids)} for arm in ARMS}

    # per-question EN-vs-ZH flip table
    flips = {}
    flip_counts = {arm: {"both_correct": 0, "both_error": 0,
                         "zh_correct_en_error": 0, "zh_error_en_correct": 0}
                   for arm in ARMS}
    for qid in sorted(qmeta):
        row = {"cluster": qmeta[qid]["cluster"],
               "expected_kind": qmeta[qid]["expected_kind"]}
        for arm in ARMS:
            z, e = zh_pq[qid][arm], en[arm][qid]["verdict"]
            zc, ec = z == "correct", e == "correct"
            cat = ("both_correct" if zc and ec else
                   "both_error" if not zc and not ec else
                   "zh_correct_en_error" if zc else "zh_error_en_correct")
            flip_counts[arm][cat] += 1
            row[arm] = {"zh": z, "en": e, "flip": cat}
        flips[qid] = row

    # call-log accounting (side log; metadata only, never used for scoring)
    call_acct = {arm: {"n_logged_calls": 0, "retried_calls(attempts>1)": 0,
                       "total_latency_s": 0.0} for arm in ARMS}
    log_p = S6 / "call_log_en.jsonl"
    if log_p.is_file():
        for line in log_p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            a = r["arm"]
            call_acct[a]["n_logged_calls"] += 1
            call_acct[a]["total_latency_s"] = round(
                call_acct[a]["total_latency_s"] + r["latency_s"], 3)
            if r.get("attempts", 1) > 1:
                call_acct[a]["retried_calls(attempts>1)"] += 1

    # probe7 EN governance verdicts
    en_probe7 = {q: en["governance_informed"][q]["verdict"] for q in probe7}
    en_probe7_errors = sum(1 for v in en_probe7.values() if v != "correct")

    # frozen ZH anchors (exact, from the frozen matrix)
    zh_err = {arm: sum(1 for q in zh_pq if zh_pq[q][arm] != "correct") for arm in ARMS}
    assert zh_err["baseline_claude"] == 36 and zh_err["governance_informed"] == 28

    # --- pre-registered adjudication (literal prereg numbers 0.600 / 0.467) ---
    p1 = abs(rate["baseline_claude"] - 0.600) <= 0.10
    p2 = abs(rate["governance_informed"] - 0.467) <= 0.10
    p3 = rate["baseline_claude"] > rate["governance_informed"]
    p4 = en_probe7_errors >= 4

    summary = {
        "study": "S6 Stage B — English-question control (2 arms x 60)",
        "prereg_sha256": PREREG_SHA,
        "questions_en_sha256": got,
        "protocol": {
            "model": "claude-opus-4-6",
            "arms": list(ARMS),
            "sampling": "one sample, retry only on empty x3, 512-token cap, temperature unset",
            "single_delta": "question text = frozen question_en (all else byte-frozen R2/RP chain)",
            "scorer": "frozen R2.fetch_and_score (RP.score + §4.2 rowset/string dispatch)",
        },
        "n_questions": 60,
        "error_counts_en": err,
        "error_rate_en": rate,
        "empty_responses": empty,
        "taxonomy_en": taxonomy,
        "refusal_stats_en": refusal_stats,
        "zh_anchors_frozen": {
            "error_counts": zh_err,
            "error_rate": {a: zh_err[a] / 60 for a in ARMS},
            "source": "pilot2/pilot2_arms_summary.json per_question_verdicts (frozen 2026-08-04 main study)",
        },
        "probe7": {
            "qids": probe7,
            "provenance": ("frozen PROBE7 list in pilot2/make_pilot2_summary.py "
                           "(PREREG_pilot2_arms §5.2, 决定性探针 7 题); mirrored in "
                           "pilot2_arms_summary.json governance_informed_arm."
                           "probe7_metadata_undecidable and paper/figures/"
                           "fig_data_pilot2.json gov_arm.probe7_errors (§7.3a)"),
            "zh_governance_verdicts": zh_probe7,
            "zh_governance_errors": sum(1 for v in zh_probe7.values() if v != "correct"),
            "en_governance_verdicts": en_probe7,
            "en_governance_errors": en_probe7_errors,
        },
        "predictions": {
            "S6-P1": {"stated": "EN backbone error within 0.600 +/- 0.10",
                      "observed": rate["baseline_claude"],
                      "band": [0.500, 0.700], "met": p1},
            "S6-P2": {"stated": "EN governance-informed error within 0.467 +/- 0.10",
                      "observed": rate["governance_informed"],
                      "band": [0.367, 0.567], "met": p2},
            "S6-P3": {"stated": "backbone error > governance error in English",
                      "observed": [rate["baseline_claude"], rate["governance_informed"]],
                      "met": p3},
            "S6-P4": {"stated": "EN governance arm errs >= 4 of the 7 probe-only refusal questions",
                      "observed": en_probe7_errors, "met": p4},
        },
        "call_log_account": call_acct,
        "flip_counts": flip_counts,
        "per_question_flips": flips,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("error_counts_en", "error_rate_en", "flip_counts")},
                     ensure_ascii=False, indent=1))
    print(json.dumps(summary["predictions"], ensure_ascii=False, indent=1))
    print(f"WROTE {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
