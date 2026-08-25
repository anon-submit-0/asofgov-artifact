#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s7_adjudicate.py — S7 Stage B adjudication (deterministic, zero LLM).

prereg sha256: 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669

Reads s7_nl2sigma_full.json (produced by nl2sigma_harness.py over all 60
questions), splits it into s7_summary.json + s7_ledger.json, and adjudicates
S7-P1..P4 exactly as pre-registered:

  S7-P1: exact full-σ recovery on >= 36/60 questions.
  S7-P2: end-to-end error <= 28/60 (the governance-informed arm's).
  S7-P3: on questions with exact σ recovery, end-to-end error = 0.
  S7-P4: metric-identity recovery >= 54/60 (>=90%); descriptive clause:
         failures concentrate in window/scope/version fields, not metric
         identity (reported as per-field mismatch counts + a concentration
         boolean: metric_alias mismatches <= mismatches summed over
         {window_request, cross_window, scope, pinned_version}).

Every number in S7_REPORT.md flows from the JSONs this script writes.
"""
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PREREG = HERE.parent / "PREREG_poststudy2_20260823.md"
PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"

SIGMA_FIELDS = [
    "as_of", "declared_at", "metric_alias", "scope", "pinned_version",
    "cross_window", "anchor_override", "window_request",
    "requested_granularity", "requested_time_gran", "presentation",
    "ctx_role", "periods",
]
WINDOW_SCOPE_VERSION = ["window_request", "cross_window", "scope",
                        "pinned_version"]


def main() -> int:
    got = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    assert got == PREREG_SHA, f"prereg sha mismatch: {got}"

    full = json.loads((HERE / "s7_nl2sigma_full.json").read_text(
        encoding="utf-8"))
    ledger = full["ledger"]
    n = len(ledger)
    assert n == 60, f"expected 60 ledger rows, got {n}"
    assert len({r["qid"] for r in ledger}) == 60, "duplicate qids"

    # ---- ledger file: per question σ, field-match vector, compile outcome,
    #      gold kind, verdict -------------------------------------------------
    ledger_rows = []
    for r in ledger:
        ledger_rows.append({
            "qid": r["qid"],
            "domain": r["domain"],
            "extraction_error": r["extraction_error"],
            "attempts": r["attempts"],
            "sigma_extracted": r["sigma_extracted"],
            "field_match": r["sigma_accuracy"]["field_match"],
            "exact_full_sigma": r["sigma_accuracy"]["exact_full_sigma"],
            "sigma_mismatches": r["sigma_accuracy"]["mismatches"],
            "compile_outcome": r["outcome"],
            "gold_kind": r["score"]["expected_kind"],
            "verdict": r["score"]["verdict"],
            "why": r["score"]["why"],
            "lenient_refusal_ok": r["score"]["lenient_refusal_ok"],
        })

    # ---- aggregates --------------------------------------------------------
    exact_full = sum(r["exact_full_sigma"] for r in ledger_rows)
    e2e_error = sum(r["verdict"] != "correct" for r in ledger_rows)
    e2e_correct = n - e2e_error
    per_field = {f: sum(r["field_match"][f] for r in ledger_rows)
                 for f in SIGMA_FIELDS}
    per_field_miss = {f: n - per_field[f] for f in SIGMA_FIELDS}
    metric_match = per_field["metric_alias"]
    exact_and_wrong = [r["qid"] for r in ledger_rows
                       if r["exact_full_sigma"] and r["verdict"] != "correct"]
    extraction_errors = [r["qid"] for r in ledger_rows if r["extraction_error"]]
    compile_errors = [r["qid"] for r in ledger_rows
                      if r["compile_outcome"]["kind"] == "compile_error"]
    retried = [r["qid"] for r in ledger_rows if r["attempts"] > 1]

    by_domain = {}
    for r in ledger_rows:
        d = by_domain.setdefault(r["domain"], {"n": 0, "exact_full_sigma": 0,
                                               "e2e_correct": 0, "e2e_error": 0})
        d["n"] += 1
        d["exact_full_sigma"] += int(r["exact_full_sigma"])
        d["e2e_correct"] += int(r["verdict"] == "correct")
        d["e2e_error"] += int(r["verdict"] != "correct")

    by_gold_kind = {}
    for r in ledger_rows:
        k = r["gold_kind"]
        g = by_gold_kind.setdefault(k, {"n": 0, "e2e_correct": 0, "e2e_error": 0,
                                        "exact_full_sigma": 0})
        g["n"] += 1
        g["e2e_correct"] += int(r["verdict"] == "correct")
        g["e2e_error"] += int(r["verdict"] != "correct")
        g["exact_full_sigma"] += int(r["exact_full_sigma"])

    # ---- prereg adjudication ----------------------------------------------
    wsv_miss = sum(per_field_miss[f] for f in WINDOW_SCOPE_VERSION)
    metric_miss = per_field_miss["metric_alias"]
    predictions = {
        "S7-P1": {
            "statement": "exact full-σ recovery on >= 36/60 questions",
            "observed": {"exact_full_sigma": exact_full, "n": n},
            "threshold": 36,
            "met": exact_full >= 36,
        },
        "S7-P2": {
            "statement": "end-to-end error <= 28/60 "
                         "(the governance-informed arm's)",
            "observed": {"end_to_end_error": e2e_error, "n": n},
            "threshold": 28,
            "met": e2e_error <= 28,
        },
        "S7-P3": {
            "statement": "on questions with exact σ recovery, "
                         "end-to-end error = 0 (compiler correctness transfers)",
            "observed": {"exact_sigma_questions": exact_full,
                         "errors_among_them": len(exact_and_wrong),
                         "witnesses": exact_and_wrong},
            "met": len(exact_and_wrong) == 0,
        },
        "S7-P4": {
            "statement": "metric-identity recovery >= 54/60 (>=90%); failures "
                         "concentrate in window/scope/version fields, "
                         "not metric identity",
            "observed": {
                "metric_alias_match": metric_match, "n": n,
                "metric_alias_mismatches": metric_miss,
                "window_scope_version_mismatches_total": wsv_miss,
                "window_scope_version_fields": WINDOW_SCOPE_VERSION,
                "concentration_ok": metric_miss <= wsv_miss,
                # descriptive only (not part of the gate): as_of is a
                # time-point field outside the window/scope/version family;
                # reported so the dominant mismatch field is not hidden.
                "as_of_mismatches_descriptive": per_field_miss["as_of"],
            },
            "threshold": 54,
            "met": (metric_match >= 54) and (metric_miss <= wsv_miss),
        },
    }
    predictions_met = sum(p["met"] for p in predictions.values())

    summary = {
        "study": "S7 NL->sigma arm (Stage B full run)",
        "prereg_sha256": PREREG_SHA,
        "model": full["model"],
        "n": n,
        "llm_calls_this_run": full["calls"],
        "cache_hits_this_run": full["cached"],
        "format_retried_qids": retried,
        "extraction_error_qids": extraction_errors,
        "compile_error_qids": compile_errors,
        "exact_full_sigma": exact_full,
        "end_to_end_correct": e2e_correct,
        "end_to_end_error": e2e_error,
        "per_field_match": per_field,
        "per_field_mismatch": per_field_miss,
        "exact_sigma_and_wrong": exact_and_wrong,
        "by_domain": by_domain,
        "by_gold_kind": by_gold_kind,
        "reference_points": {
            "governance_informed_error_frozen": 28,
            "backbone_error_frozen": 36,
        },
        "predictions": predictions,
        "predictions_met": f"{predictions_met}/4",
    }

    (HERE / "s7_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "s7_ledger.json").write_text(
        json.dumps({"prereg_sha256": PREREG_SHA, "n": n,
                    "ledger": ledger_rows},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("by_domain", "by_gold_kind")},
                     ensure_ascii=False, indent=1))
    print("\nwrote s7_summary.json + s7_ledger.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
