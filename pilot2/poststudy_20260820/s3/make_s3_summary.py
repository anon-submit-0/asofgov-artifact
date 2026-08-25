#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3 repetition-study summary + report generator (PREREG §S3).

Deterministic, zero LLM calls, pure reader of frozen evidence:
  * rep1        := frozen main-study caches  pilot2/runs/{arm}/{qid}.json
  * reps 2..5   := poststudy caches          s3/runs_rep/{arm}/rep{k}/{qid}.json
  * call log    := s3/call_log.jsonl (side log written by rep_harness.py)
  * frozen ref  := pilot2/pilot2_arms_summary.json (reference_error_qids etc.)

Outputs (both under s3/, nothing frozen is touched):
  * s3_summary.json — every computed number (machine-readable twin)
  * S3_REPORT.md    — rendered FROM the reloaded JSON (no hand-typed result
                      numbers; prereg constants are quoted as protocol text)

Integrity gates (all hard assertions):
  * PREREG sha256 recomputed from disk == the frozen registration sha
  * rep1 cache verdicts == frozen pilot2_arms_summary per_question_verdicts
  * every rep2..5 cache prompt_sha256+chars == its frozen rep1 record
    (byte-identity of prompts across all five reps)
  * call log: 480 unique (arm,rep,qid) == 2 arms x 4 reps x 60 qids; every
    line carries the prereg sha; every logged verdict == its cache verdict
  * driver.log ran to completion, no circuit-breaker line; per-rep empty
    counts in driver.log == recount from caches

Determinism: fixed iteration orders, no wall-clock in outputs; re-running
must produce byte-identical files.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

S3 = pathlib.Path(__file__).resolve().parent
POSTSTUDY = S3.parent
P2 = POSTSTUDY.parent
PREREG = POSTSTUDY / "PREREG_poststudy_20260820.md"
PREREG_SHA = "f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24"

ARMS = ("baseline_claude", "governance_informed")
REPS = (1, 2, 3, 4, 5)               # rep1 = frozen main-study run (reused)
NEW_REPS = (2, 3, 4, 5)
VERDICTS = ("correct", "wrong_value", "execution_error",
            "answered_should_refuse", "refused_should_answer", "no_sql")
# PREREG §S3 band: rate within frozen +/- 0.10; with n=60 that is exactly
# +/- 6 questions (0.10 * 60). Integer form avoids float-band edge effects.
BAND_QUESTIONS = 6
# PREREG §S3-P4: pooled flip rate < 0.15; with n=60, pass iff n_flip < 9.
FLIP_NUM, FLIP_DEN = 3, 20           # 0.15 == 3/20


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_json(p: pathlib.Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def is_err(verdict: str) -> bool:
    return verdict != "correct"


def pctl(sorted_vals, q):
    """Nearest-rank percentile on a pre-sorted list (deterministic)."""
    assert sorted_vals
    import math
    k = max(1, math.ceil(q * len(sorted_vals)))
    return sorted_vals[k - 1]


def main() -> int:
    # ---- gate: prereg registration hash --------------------------------------
    got_sha = sha256_file(PREREG)
    assert got_sha == PREREG_SHA, f"PREREG sha drift: {got_sha}"

    frozen = load_json(P2 / "pilot2_arms_summary.json")
    pq = frozen["per_question_verdicts"]
    qids = sorted(pq)
    assert len(qids) == 60 and frozen["n_questions"] == 60
    ref_err_qids = frozen["reference_error_qids"]
    assert frozen["reference_baseline"] == "baseline_claude"
    assert len(ref_err_qids) == frozen["reference_errors"]
    frozen_err_counts = {arm: frozen["error_counts"][arm] for arm in ARMS}
    frozen_err_rates = {arm: frozen["error_rate"][arm] for arm in ARMS}

    # ---- load all caches (rep1 frozen, reps 2..5 poststudy) ------------------
    recs: dict[str, dict[int, dict[str, dict]]] = {}
    sha_checked = 0
    for arm in ARMS:
        recs[arm] = {}
        rep1 = {}
        for qid in qids:
            r = load_json(P2 / "runs" / arm / f"{qid}.json")
            assert r["qid"] == qid and r["system"] == arm
            assert r["verdict"] in VERDICTS, (arm, qid, r["verdict"])
            assert r["verdict"] == pq[qid][arm], \
                f"rep1 cache/frozen-summary verdict drift: {arm}/{qid}"
            rep1[qid] = r
        recs[arm][1] = rep1
        for k in NEW_REPS:
            rk = {}
            for qid in qids:
                r = load_json(S3 / "runs_rep" / arm / f"rep{k}" / f"{qid}.json")
                assert r["qid"] == qid and r["system"] == arm
                assert r["verdict"] in VERDICTS, (arm, k, qid, r["verdict"])
                assert r["prompt_sha256"] == rep1[qid]["prompt_sha256"], \
                    f"prompt sha drift vs frozen: {arm}/rep{k}/{qid}"
                assert r["prompt_chars"] == rep1[qid]["prompt_chars"], \
                    f"prompt chars drift vs frozen: {arm}/rep{k}/{qid}"
                sha_checked += 1
                rk[qid] = r
            recs[arm][k] = rk
    assert sha_checked == len(ARMS) * len(NEW_REPS) * 60  # 480 prompt-identity checks

    # ---- per-arm per-rep stats, agreement, flips -----------------------------
    per_arm = {}
    for arm in ARMS:
        per_rep = {}
        for k in REPS:
            rk = recs[arm][k]
            errs = sum(1 for q in qids if is_err(rk[q]["verdict"]))
            per_rep[str(k)] = {
                "n": len(qids),
                "errors": errs,
                "error_rate": errs / 60,
                "empty_responses": sum(1 for q in qids if rk[q].get("empty_response")),
                "verdict_counts": {v: n for v in VERDICTS
                                   if (n := sum(1 for q in qids
                                                if rk[q]["verdict"] == v))},
                "source": ("frozen main-study run (pilot2/runs/, reused not re-run)"
                           if k == 1 else f"s3/runs_rep/{arm}/rep{k}/"),
            }
        assert per_rep["1"]["errors"] == frozen_err_counts[arm], \
            f"rep1 error recount != frozen error_counts for {arm}"
        assert per_rep["1"]["error_rate"] == frozen_err_rates[arm]

        v1 = {q: recs[arm][1][q]["verdict"] for q in qids}
        rep1_vs = {}
        for k in NEW_REPS:
            vk = {q: recs[arm][k][q]["verdict"] for q in qids}
            to_correct = sorted(q for q in qids
                                if is_err(v1[q]) and not is_err(vk[q]))
            to_wrong = sorted(q for q in qids
                              if not is_err(v1[q]) and is_err(vk[q]))
            agree = 60 - len(to_correct) - len(to_wrong)
            rep1_vs[str(k)] = {
                "correctness_agreement_n": agree,
                "correctness_agreement_rate": agree / 60,
                "verdict_agreement_n": sum(1 for q in qids if v1[q] == vk[q]),
                "flipped_to_correct": to_correct,
                "flipped_to_wrong": to_wrong,
            }
        flip_qids = sorted(
            q for q in qids
            if len({is_err(recs[arm][k][q]["verdict"]) for k in REPS}) > 1)
        pooled = {
            "definition": "question flips iff correctness is not constant "
                          "across all 5 reps (rep1 + reps 2..5)",
            "flip_qids": flip_qids,
            "n_flips": len(flip_qids),
            "flip_rate": len(flip_qids) / 60,
        }
        err_list = [per_rep[str(k)]["errors"] for k in REPS]
        per_arm[arm] = {
            "per_rep": per_rep,
            "rep1_vs_repk": rep1_vs,
            "pooled_flip": pooled,
            "errors_across_reps": {"per_rep_errors": err_list,
                                   "min": min(err_list), "max": max(err_list),
                                   "mean": sum(err_list) / len(err_list)},
        }

    # ---- ordering check per rep ----------------------------------------------
    ordering = {}
    for k in REPS:
        eb = per_arm["baseline_claude"]["per_rep"][str(k)]["errors"]
        eg = per_arm["governance_informed"]["per_rep"][str(k)]["errors"]
        ordering[str(k)] = {"baseline_claude_errors": eb,
                           "governance_informed_errors": eg,
                           "margin_questions": eb - eg,
                           "baseline_gt_governance": eb > eg}
    ordering_all = all(o["baseline_gt_governance"] for o in ordering.values())

    # ---- per-rep elimination of frozen reference-baseline errors (gov) -------
    elim_per_rep = {}
    for k in REPS:
        rk = recs["governance_informed"][k]
        elim_n = sum(1 for q in ref_err_qids if not is_err(rk[q]["verdict"]))
        elim_per_rep[str(k)] = {"eliminated_n": elim_n,
                                "of_reference_errors": len(ref_err_qids),
                                "eliminated_frac": elim_n / len(ref_err_qids)}
    assert elim_per_rep["1"]["eliminated_frac"] == \
        frozen["eliminated_by"]["governance_informed"], \
        "rep1 elimination recount != frozen eliminated_by"
    elimination = {
        "reference": "frozen baseline_claude rep1 error set "
                     "(pilot2_arms_summary.json reference_error_qids)",
        "n_reference_errors": len(ref_err_qids),
        "per_rep": elim_per_rep,
        "frozen_rep1_value_reasserted": True,
    }

    # ---- prediction adjudication (PREREG §S3, verbatim scope) ----------------
    def band_pred(arm):
        center_n = frozen_err_counts[arm]
        per = {str(k): per_arm[arm]["per_rep"][str(k)]["errors"] for k in REPS}
        viol = {k: e for k, e in per.items()
                if abs(e - center_n) > BAND_QUESTIONS}
        return {
            "band_center_error_rate": frozen_err_rates[arm],
            "band_half_width": "0.10 (== 6/60 questions; adjudicated in "
                               "integer questions, |errors - frozen| <= 6)",
            "band_questions": [center_n - BAND_QUESTIONS,
                               center_n + BAND_QUESTIONS],
            "per_rep_errors": per,
            "per_rep_error_rates": {k: e / 60 for k, e in per.items()},
            "violations": viol,
            "pass": not viol,
        }

    p1 = band_pred("baseline_claude")
    p2 = band_pred("governance_informed")
    p3 = {"per_rep": ordering, "pass": ordering_all}
    p4_rates = {arm: per_arm[arm]["pooled_flip"] for arm in ARMS}
    p4_pass = all(v["n_flips"] * FLIP_DEN < FLIP_NUM * 60   # n_flip/60 < 0.15
                  for v in p4_rates.values())
    p4 = {"threshold": "flip rate < 0.15 per arm (== n_flips < 9 of 60)",
          "per_arm": {arm: {"n_flips": v["n_flips"], "flip_rate": v["flip_rate"]}
                      for arm, v in p4_rates.items()},
          "pass": p4_pass}
    predictions = {
        "S3-P1": {"statement": "every baseline_claude rep error within "
                               "0.600 +/- 0.10", **p1},
        "S3-P2": {"statement": "every governance_informed rep error within "
                               "0.467 +/- 0.10", **p2},
        "S3-P3": {"statement": "baseline_claude error > governance_informed "
                               "error in every rep", **p3},
        "S3-P4": {"statement": "pooled per-question flip rate (per arm) "
                               "< 0.15", **p4},
    }
    n_missed = sum(1 for p in predictions.values() if not p["pass"])

    # ---- call log statistics -------------------------------------------------
    log_lines = [json.loads(l) for l in
                 (S3 / "call_log.jsonl").read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    assert len(log_lines) == len(ARMS) * len(NEW_REPS) * 60, len(log_lines)
    seen = set()
    for e in log_lines:
        key = (e["arm"], e["rep"], e["qid"])
        assert key not in seen, f"duplicate call-log entry {key}"
        seen.add(key)
        assert e["prereg_sha256"] == PREREG_SHA
        cache = recs[e["arm"]][e["rep"]][e["qid"]]
        assert e["verdict"] == cache["verdict"], f"log/cache verdict drift {key}"
        assert bool(e["empty_response"]) == bool(cache["empty_response"])
    assert seen == {(a, k, q) for a in ARMS for k in NEW_REPS for q in qids}

    by_ts = sorted(log_lines, key=lambda e: e["ts"])
    smoke = [e for e in log_lines if e["rep"] == 2 and e["qid"] == "CARD-Q1"]
    assert len(smoke) == 2 and \
        sorted(e["ts"] for e in smoke) == sorted(e["ts"] for e in by_ts[:2]), \
        "smoke calls (rep2/CARD-Q1 both arms) must be the 2 earliest log entries"
    smoke = sorted(smoke, key=lambda e: e["ts"])
    full = sorted((e for e in log_lines
                   if not (e["rep"] == 2 and e["qid"] == "CARD-Q1")),
                  key=lambda e: e["ts"])

    def lat_stats(entries):
        lats = sorted(e["latency_s"] for e in entries)
        att = [e["attempts"] for e in entries]
        return {
            "n_calls": len(entries),
            "latency_s": {"min": lats[0], "median": pctl(lats, 0.5),
                          "mean": round(sum(lats) / len(lats), 3),
                          "p95": pctl(lats, 0.95), "max": lats[-1]},
            "attempts": {"total": sum(att), "max": max(att),
                         "calls_with_retry": sum(1 for a in att if a > 1),
                         "histogram": {str(a): att.count(a)
                                       for a in sorted(set(att))}},
            "tokens": {"prompt_total": sum(e["prompt_tokens"] or 0
                                           for e in entries),
                       "completion_total": sum(e["completion_tokens"] or 0
                                               for e in entries)},
            "empty_response_logged": sum(1 for e in entries
                                         if e["empty_response"]),
        }

    call_log_stats = {
        "n_total_paid_calls": len(log_lines),
        "smoke_phase": {
            "note": "2 calls (rep2/CARD-Q1, both arms), chronologically first",
            "calls": [{"arm": e["arm"], "ts": e["ts"],
                       "latency_s": e["latency_s"], "attempts": e["attempts"],
                       "verdict": e["verdict"]} for e in smoke],
        },
        "full_run_phase": {
            "window": {"first_ts": full[0]["ts"], "last_ts": full[-1]["ts"]},
            "per_arm": {arm: lat_stats([e for e in full if e["arm"] == arm])
                        for arm in ARMS},
            "overall": lat_stats(full),
        },
    }

    # ---- operational: driver + circuit breaker + empties ---------------------
    driver_sh = (S3 / "s3_driver.sh").read_text(encoding="utf-8")
    m = re.search(r'"\$n_empty"\s+-gt\s+(\d+)', driver_sh)
    assert m, "cannot find circuit-breaker threshold in s3_driver.sh"
    breaker_threshold = int(m.group(1))
    driver_log = (S3 / "driver.log").read_text(encoding="utf-8")
    assert "S3 DRIVER COMPLETE" in driver_log
    assert "CIRCUIT BREAKER" not in driver_log
    logged_empties = {mm.group(1): int(mm.group(2)) for mm in re.finditer(
        r"governance rep(\d) empty_response count: (\d+)", driver_log)}
    cache_gov_empties = {str(k):
                         per_arm["governance_informed"]["per_rep"][str(k)]
                         ["empty_responses"] for k in NEW_REPS}
    assert logged_empties == cache_gov_empties, \
        f"driver.log empty counts {logged_empties} != cache recount {cache_gov_empties}"
    new_rep_empties = sum(per_arm[a]["per_rep"][str(k)]["empty_responses"]
                          for a in ARMS for k in NEW_REPS)
    rep1_empty_qids = {a: sorted(q for q in qids
                                 if recs[a][1][q].get("empty_response"))
                       for a in ARMS}
    for a in ARMS:   # rep1 empties must match the frozen summary's disclosure
        assert rep1_empty_qids[a] == frozen["empty_responses"][a], \
            f"rep1 empty set drift vs frozen empty_responses for {a}"
    operational = {
        "driver_completed": True,
        "circuit_breaker": {
            "rule": f"driver stops if a finished governance rep has "
                    f"> {breaker_threshold}/60 empty_response caches "
                    f"(threshold parsed from s3_driver.sh)",
            "threshold_empties": breaker_threshold,
            "tripped": False,
            "governance_empties_per_rep": cache_gov_empties,
        },
        "empty_responses_new_reps_total": new_rep_empties,
        "empty_responses_frozen_rep1": {
            "per_arm_qids": rep1_empty_qids,
            "note": "frozen main-study artifact, already disclosed in "
                    "pilot2_arms_summary.json empty_responses; asserted equal "
                    "to that frozen disclosure — not produced by this study",
        },
        "smoke_time_tuzi_slowness": {
            "source": "S3_SMOKE.md (operational warning) + smoke-phase log",
            "gov_smoke_latency_s": smoke[-1]["latency_s"]
            if smoke[-1]["arm"] == "governance_informed"
            else smoke[0]["latency_s"],
            "gov_smoke_attempts": smoke[-1]["attempts"]
            if smoke[-1]["arm"] == "governance_informed"
            else smoke[0]["attempts"],
            "gov_full_run_median_latency_s":
                call_log_stats["full_run_phase"]["per_arm"]
                ["governance_informed"]["latency_s"]["median"],
        },
        "prompt_byte_identity_checks":
            {"rep_caches_vs_frozen_rep1_sha256_and_chars": sha_checked,
             "all_equal": True},
    }

    # ---- is the frozen rep1 the worst governance rep? ------------------------
    rep1_position = {}
    for arm in ARMS:
        e1 = per_arm[arm]["per_rep"]["1"]["errors"]
        others = [per_arm[arm]["per_rep"][str(k)]["errors"] for k in NEW_REPS]
        rep1_position[arm] = {
            "rep1_errors": e1,
            "new_rep_errors_min": min(others),
            "new_rep_errors_max": max(others),
            "rep1_is_strict_worst": e1 > max(others),
            "rep1_is_strict_best": e1 < min(others),
        }

    summary = {
        "study": "S3 — repetition study (PREREG_poststudy_20260820.md §S3)",
        "prereg_sha256": got_sha,
        "prereg_sha256_reasserted_from_disk": True,
        "arms": list(ARMS),
        "reps": list(REPS),
        "rep1_source": "frozen main-study caches pilot2/runs/ (reused, not re-run)",
        "n_questions": 60,
        "model": "claude-opus-4-6 (frozen gateway channel; protocol byte-identical "
                 "to the frozen runs, see rep_harness.py)",
        "per_arm": per_arm,
        "ordering_check": {"per_rep": ordering, "all_reps_pass": ordering_all},
        "elimination_governance_informed": elimination,
        "predictions": predictions,
        "n_predictions_missed": n_missed,
        "call_log_stats": call_log_stats,
        "operational": operational,
        "rep1_position": rep1_position,
        "scorer": "frozen chain (R2.fetch_and_score at run time; verdicts read "
                  "from caches here, rep1 verdicts asserted equal to frozen "
                  "pilot2_arms_summary.json per_question_verdicts)",
    }
    out_json = S3 / "s3_summary.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    # ---- render the report FROM the reloaded JSON ----------------------------
    S = load_json(out_json)          # reload: report reads only the JSON
    render_report(S)

    print(json.dumps({
        "per_rep_errors": {a: S["per_arm"][a]["errors_across_reps"]
                           ["per_rep_errors"] for a in S["arms"]},
        "pooled_flips": {a: S["per_arm"][a]["pooled_flip"]["n_flips"]
                         for a in S["arms"]},
        "predictions_pass": {k: v["pass"] for k, v in S["predictions"].items()},
        "n_predictions_missed": S["n_predictions_missed"],
        "circuit_breaker_tripped":
            S["operational"]["circuit_breaker"]["tripped"],
        "new_rep_empties": S["operational"]["empty_responses_new_reps_total"],
        "frozen_rep1_empties": S["operational"]["empty_responses_frozen_rep1"]
            ["per_arm_qids"],
    }, ensure_ascii=False, indent=1))
    return 0


def render_report(S: dict) -> None:
    A, G = "baseline_claude", "governance_informed"
    L = []
    add = L.append

    def f4(x):
        return f"{x:.4f}"

    add("# S3 — Repetition study (LLM, paid; k=4 new reps per arm)")
    add("")
    add("- **Governing prereg**: `PREREG_poststudy_20260820.md`,")
    add(f"  sha256 `{S['prereg_sha256']}`")
    add("  (recomputed from disk by the generator before any analysis).")
    first_ts = S["call_log_stats"]["full_run_phase"]["window"]["first_ts"]
    last_ts = S["call_log_stats"]["full_run_phase"]["window"]["last_ts"]
    smoke_ts = S["call_log_stats"]["smoke_phase"]["calls"][0]["ts"]
    add(f"- **Study date**: {first_ts[:10]} (smoke {smoke_ts[11:16]}, full run "
        f"{first_ts[11:16]}–{last_ts[11:16]} local). "
        f"{S['call_log_stats']['n_total_paid_calls']} paid LLM calls total "
        f"({len(S['arms'])} arms × {len(S['reps']) - 1} new reps × "
        f"{S['n_questions']} questions; rep1 := the frozen main-study run, "
        "reused not re-run). All outputs append-only under "
        "`pilot2/poststudy_20260820/s3/`; no frozen file modified.")
    add("- **Machine-readable twin**: [`s3_summary.json`](s3_summary.json)")
    add("  (every number in this file). Generator:")
    add("  [`make_s3_summary.py`](make_s3_summary.py). Run harness:")
    add("  [`rep_harness.py`](rep_harness.py); side log:")
    add("  [`call_log.jsonl`](call_log.jsonl); smoke record:")
    add("  [`S3_SMOKE.md`](S3_SMOKE.md).")
    add(f"- **Protocol**: {S['model']}; scoring: {S['scorer']}")
    add(f"- **Prompt byte-identity**: all "
        f"{S['operational']['prompt_byte_identity_checks']['rep_caches_vs_frozen_rep1_sha256_and_chars']}"
        " rep2–5 cache records match their frozen rep1 record on "
        "`prompt_sha256` + `prompt_chars` (re-asserted by this generator; the "
        "harness additionally asserted it before every paid call).")
    add("")

    # -- prediction verdicts --
    add("## Prediction verdicts")
    add("")
    add("| Prediction | Statement (verbatim scope) | Verdict |")
    add("|---|---|---|")
    P = S["predictions"]
    p1 = P["S3-P1"]
    r1 = [p1["per_rep_errors"][str(k)] for k in S["reps"]]
    add(f"| **S3-P1** | {p1['statement']} | "
        f"{'**MET**' if p1['pass'] else '**MISSED**'} — per-rep errors "
        f"{'/'.join(str(e) for e in r1)} of 60 (rates "
        f"{', '.join(f4(p1['per_rep_error_rates'][str(k)]) for k in S['reps'])}), "
        f"all within {p1['band_questions'][0]}–{p1['band_questions'][1]} "
        f"questions (= {f4(p1['band_center_error_rate'])} ± 0.10) |")
    p2 = P["S3-P2"]
    r2 = [p2["per_rep_errors"][str(k)] for k in S["reps"]]
    add(f"| **S3-P2** | {p2['statement']} | "
        f"{'**MET**' if p2['pass'] else '**MISSED**'} — per-rep errors "
        f"{'/'.join(str(e) for e in r2)} of 60 (rates "
        f"{', '.join(f4(p2['per_rep_error_rates'][str(k)]) for k in S['reps'])}), "
        f"all within {p2['band_questions'][0]}–{p2['band_questions'][1]} "
        f"questions (= {f4(p2['band_center_error_rate'])} ± 0.10) |")
    p3 = P["S3-P3"]
    margins = [p3["per_rep"][str(k)]["margin_questions"] for k in S["reps"]]
    add(f"| **S3-P3** | {p3['statement']} | "
        f"{'**MET**' if p3['pass'] else '**MISSED**'} — margin "
        f"(baseline − governance) per rep: "
        f"{', '.join(f'+{m}' for m in margins)} questions; ordering holds in "
        f"{sum(1 for k in S['reps'] if p3['per_rep'][str(k)]['baseline_gt_governance'])}"
        f"/{len(S['reps'])} reps |")
    p4 = P["S3-P4"]
    add(f"| **S3-P4** | {p4['statement']} | "
        f"{'**MET**' if p4['pass'] else '**MISSED**'} — "
        f"`{A}` {p4['per_arm'][A]['n_flips']}/60 = "
        f"{f4(p4['per_arm'][A]['flip_rate'])}, `{G}` "
        f"{p4['per_arm'][G]['n_flips']}/60 = "
        f"{f4(p4['per_arm'][G]['flip_rate'])}, both < 0.15 |")
    add("")
    if S["n_predictions_missed"] == 0:
        add("No prediction miss. (Per the prereg publication rule, a miss would")
        add("have been reported as MISSED_PREDICTION; none occurred.)")
    else:
        add(f"**{S['n_predictions_missed']} prediction(s) MISSED** — reported "
            "as such per the prereg publication rule; see the rows above.")
    add("")

    # -- per-rep table --
    add("## Per-rep results")
    add("")
    add("Error = verdict ≠ `correct` (frozen scorer semantics). Verdict-class")
    add("key: wv = wrong_value, xe = execution_error, asr =")
    add("answered_should_refuse, rsa = refused_should_answer, ns = no_sql.")
    add("")
    for arm in S["arms"]:
        pa = S["per_arm"][arm]
        add(f"### `{arm}`")
        add("")
        add("| rep | errors/60 | error rate | empty | correct | wv | xe | asr | rsa | ns | vs rep1: agree (correctness) | flips vs rep1 (→correct / →wrong) |")
        add("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for k in S["reps"]:
            pr = pa["per_rep"][str(k)]
            vc = pr["verdict_counts"]
            if k == 1:
                agree, flips = "—(reference)", "—"
            else:
                rv = pa["rep1_vs_repk"][str(k)]
                agree = (f"{rv['correctness_agreement_n']}/60 = "
                         f"{f4(rv['correctness_agreement_rate'])}")
                flips = (f"{len(rv['flipped_to_correct'])} / "
                         f"{len(rv['flipped_to_wrong'])}")
            add(f"| {k}{'*' if k == 1 else ''} | {pr['errors']} | "
                f"{f4(pr['error_rate'])} | {pr['empty_responses']} | "
                f"{vc.get('correct', 0)} | {vc.get('wrong_value', 0)} | "
                f"{vc.get('execution_error', 0)} | "
                f"{vc.get('answered_should_refuse', 0)} | "
                f"{vc.get('refused_should_answer', 0)} | "
                f"{vc.get('no_sql', 0)} | {agree} | {flips} |")
        ea = pa["errors_across_reps"]
        add("")
        add(f"Errors across the 5 reps: min {ea['min']}, max {ea['max']}, "
            f"mean {ea['mean']:.1f}. (*rep1 = frozen main-study run.)")
        add("")

    # -- flip sets --
    add("## Stability: pooled per-question flip sets")
    add("")
    add("A question *flips* iff its correctness is not constant across all 5")
    add("reps (rep1 + reps 2–5) — the pooled definition adjudicated in S3-P4.")
    add("")
    add("| arm | flips | flip rate | flip qids |")
    add("|---|---|---|---|")
    for arm in S["arms"]:
        pf = S["per_arm"][arm]["pooled_flip"]
        add(f"| `{arm}` | {pf['n_flips']}/60 | {f4(pf['flip_rate'])} | "
            f"{', '.join(f'`{q}`' for q in pf['flip_qids'])} |")
    add("")
    add(f"{120 - S['per_arm'][A]['pooled_flip']['n_flips'] - S['per_arm'][G]['pooled_flip']['n_flips']}"
        " of the 120 (arm, question) cells are perfectly stable across all")
    add("five reps; correctness, not the verbatim verdict class, is the unit")
    add("(a cell that moves e.g. wrong_value → execution_error does not flip).")
    add("")

    # -- ordering + elimination --
    add("## Ordering and reference-error elimination per rep")
    add("")
    add("| rep | baseline errors | governance errors | margin | baseline > governance | governance eliminates of the frozen "
        f"{S['elimination_governance_informed']['n_reference_errors']} reference errors |")
    add("|---|---|---|---|---|---|")
    for k in S["reps"]:
        o = S["ordering_check"]["per_rep"][str(k)]
        e = S["elimination_governance_informed"]["per_rep"][str(k)]
        add(f"| {k}{'*' if k == 1 else ''} | {o['baseline_claude_errors']} | "
            f"{o['governance_informed_errors']} | +{o['margin_questions']} | "
            f"{'yes' if o['baseline_gt_governance'] else '**NO**'} | "
            f"{e['eliminated_n']}/{e['of_reference_errors']} = "
            f"{f4(e['eliminated_frac'])} |")
    add("")
    add("Reference set = the frozen `baseline_claude` rep1 error qids")
    add("(`pilot2_arms_summary.json` → `reference_error_qids`); the rep1 row")
    add("re-derives the frozen `eliminated_by.governance_informed` value and is")
    add("asserted equal to it. Elimination in reps 2–5 is computed against the")
    add("SAME frozen reference set (not against each rep's own baseline errors),")
    add("so it reads as: how much of the frozen headline's error mass does the")
    add("governance arm remove, under resampling of the governance arm alone.")
    add("")

    # -- latency / attempts --
    add("## Latency and attempts (from `call_log.jsonl`)")
    add("")
    cl = S["call_log_stats"]
    add("| phase / arm | calls | latency s (min / median / mean / p95 / max) | attempts (max, calls-with-retry) | prompt tok | completion tok | empty |")
    add("|---|---|---|---|---|---|---|")
    for arm in S["arms"]:
        st = cl["full_run_phase"]["per_arm"][arm]
        lat = st["latency_s"]
        at = st["attempts"]
        add(f"| full run `{arm}` | {st['n_calls']} | "
            f"{lat['min']} / {lat['median']} / {lat['mean']} / {lat['p95']} / "
            f"{lat['max']} | max {at['max']}, {at['calls_with_retry']} retried | "
            f"{st['tokens']['prompt_total']} | "
            f"{st['tokens']['completion_total']} | "
            f"{st['empty_response_logged']} |")
    ov = cl["full_run_phase"]["overall"]
    add(f"| full run overall | {ov['n_calls']} | {ov['latency_s']['min']} / "
        f"{ov['latency_s']['median']} / {ov['latency_s']['mean']} / "
        f"{ov['latency_s']['p95']} / {ov['latency_s']['max']} | "
        f"max {ov['attempts']['max']}, "
        f"{ov['attempts']['calls_with_retry']} retried | "
        f"{ov['tokens']['prompt_total']} | {ov['tokens']['completion_total']} | "
        f"{ov['empty_response_logged']} |")
    for c in cl["smoke_phase"]["calls"]:
        add(f"| smoke `{c['arm']}` ({c['ts'][11:16]}) | 1 | {c['latency_s']} | "
            f"{c['attempts']} attempt(s) | — | — | — |")
    add("")

    # -- operational note --
    op = S["operational"]
    add("## Operational note")
    add("")
    sl = op["smoke_time_tuzi_slowness"]
    add(f"- **Gateway slowness at smoke time, recovered by run time**: at the")
    add(f"  smoke check ({smoke_ts[11:16]}) the frozen `tuzi` channel was slow —")
    add(f"  the governance smoke call took {sl['gov_smoke_latency_s']} s and "
        f"{sl['gov_smoke_attempts']} attempts")
    add("  (first attempts empty/timeout; the protocol-internal empty-retry ×3")
    add(f"  absorbed it). In the full run the governance-arm median latency was")
    add(f"  {sl['gov_full_run_median_latency_s']} s, and "
        f"{cl['full_run_phase']['overall']['attempts']['calls_with_retry']} of "
        f"{cl['full_run_phase']['overall']['n_calls']} full-run calls needed "
        "any retry.")
    n_new_empty = op["empty_responses_new_reps_total"]
    add(f"- **{'Zero' if n_new_empty == 0 else n_new_empty} empty completions "
        f"in the full new run**: {n_new_empty} `empty_response`")
    add(f"  caches across all {len(S['reps']) - 1} new reps of both arms "
        f"({cl['n_total_paid_calls']} paid calls; per-rep counts in the")
    rep1_empty = {a: qs for a, qs in sorted(
        op["empty_responses_frozen_rep1"]["per_arm_qids"].items()) if qs}
    n_rep1_empty = sum(len(qs) for qs in rep1_empty.values())
    add(f"  tables above). The {n_rep1_empty} frozen-rep1 empty cache(s) ("
        + ", ".join(f"`{a}`: " + ", ".join(f"`{q}`" for q in qs)
                    for a, qs in rep1_empty.items())
        + ") are a main-study artifact already")
    add("  disclosed in the frozen `pilot2_arms_summary.json` "
        "`empty_responses`; this")
    add("  generator asserts the rep1 empty sets equal that frozen disclosure.")
    cb = op["circuit_breaker"]
    add(f"- **Circuit breaker never tripped**: the driver "
        f"([`s3_driver.sh`](s3_driver.sh)) stops if a")
    add(f"  finished governance rep exceeds {cb['threshold_empties']}/60 empty "
        f"responses; observed per-rep")
    add(f"  governance empties "
        f"{{{', '.join(f'rep{k}: {v}' for k, v in sorted(cb['governance_empties_per_rep'].items()))}}}"
        f" — driver ran to `S3 DRIVER COMPLETE`")
    add("  (asserted from `driver.log`, which contains no `CIRCUIT BREAKER` line;")
    add("  the per-rep counts logged by the driver are asserted equal to a fresh")
    add("  recount from the caches).")
    add("")

    # -- conservativeness observation (only if the numbers say so) --
    rp = S["rep1_position"]
    if rp[G]["rep1_is_strict_worst"]:
        add("## The frozen rep is governance_informed's worst rep")
        add("")
        add(f"The frozen main-study rep1 has {rp[G]['rep1_errors']} governance-"
            f"arm errors; every new rep has fewer "
            f"({rp[G]['new_rep_errors_min']}–{rp[G]['new_rep_errors_max']}). "
            f"The frozen `{A}` rep1 ({rp[A]['rep1_errors']} errors) sits inside "
            f"its new-rep range ({rp[A]['new_rep_errors_min']}–"
            f"{rp[A]['new_rep_errors_max']}).")
        m1 = S["ordering_check"]["per_rep"]["1"]["margin_questions"]
        new_margins = [S["ordering_check"]["per_rep"][str(k)]["margin_questions"]
                       for k in S["reps"] if k != 1]
        tail = ("every new rep also widens the baseline−governance margin "
                f"(+{m1} frozen vs +{min(new_margins)}–+{max(new_margins)} new), "
                "none narrows it."
                if min(new_margins) > m1 else
                "the governance arm's error count is strictly lower in every "
                "new rep.")
        add("The paper's frozen headline gap "
            f"({f4(S['per_arm'][A]['per_rep']['1']['error_rate'])} vs "
            f"{f4(S['per_arm'][G]['per_rep']['1']['error_rate'])}) is therefore "
            "**conservative** with respect to repetition variance: " + tail)
        add("")
    add("---")
    add("*Post-registration study. Generated deterministically by "
        "`make_s3_summary.py` from the frozen rep1 caches, the rep2–5 caches, "
        "`call_log.jsonl`, `driver.log`, `s3_driver.sh`, and "
        "`pilot2_arms_summary.json`; every number above is read from "
        "`s3_summary.json`.*")
    add("")
    (S3 / "S3_REPORT.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
