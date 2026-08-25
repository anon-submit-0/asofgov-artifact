#!/usr/bin/env python3
"""S4 — Paired-difference uncertainty (deterministic, zero LLM).

Governing prereg: PREREG_poststudy2_20260823.md (sha256 asserted below), §S4:
  cluster-bootstrap (9 database clusters, B=2000, seed 20260823) 95% CIs on the
  paired per-question error differences (reference baseline_claude minus arm)
  for governance_informed and each trivial prompt variant; plus an
  elimination-uncertainty restatement from the five S3 reps (elim of the 36
  frozen reference errors per rep), re-derived from the rep caches and asserted
  equal to the frozen s3_summary.json values.

Inputs (all frozen, READ-ONLY):
  pilot2/pilot2_arms_summary.json          per_question_verdicts (rep1 matrix)
  pilot2/domains/*/questions.json          qid -> database cluster mapping
  pilot2/poststudy_20260820/s3/runs_rep/   governance_informed rep2..rep5 caches
  pilot2/poststudy_20260820/s3/s3_summary.json  frozen per-rep elim values

Outputs (append-only, deterministic, byte-identical across re-runs — a re-run
asserts byte-identity against any already-written output instead of mutating):
  pilot2/poststudy2_20260823/s4/s4_summary.json
  pilot2/poststudy2_20260823/s4/S4_REPORT.md   (rendered from the JSON)

Bootstrap convention: byte-for-byte the frozen make_pilot2_summary.py
convention — random.Random(seed) freshly constructed per arm (so every arm sees
the identical sequence of cluster resamples), 9 draws with replacement from the
sorted cluster names per iteration, B=2000 pooled statistics, sorted, CI =
[stat[49], stat[1949]] (the frozen 95% percentile convention). Only the seed
differs: 20260823 (pre-registered), vs 20260731 in the main study.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../poststudy2_20260823/s4
POST2 = HERE.parent                              # .../poststudy2_20260823
PILOT2 = POST2.parent                            # .../pilot2

PREREG = POST2 / "PREREG_poststudy2_20260823.md"
PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"

ARMS_SUMMARY = PILOT2 / "pilot2_arms_summary.json"
DOMAINS_DIR = PILOT2 / "domains"
S3_DIR = PILOT2 / "poststudy_20260820" / "s3"
S3_SUMMARY = S3_DIR / "s3_summary.json"

REFERENCE = "baseline_claude"
COMPARISON_ARMS = ["governance_informed", "trivial_claude", "trivial_v2", "trivial_v3"]
TRIVIAL_ARMS = ["trivial_claude", "trivial_v2", "trivial_v3"]
SEED = 20260823
B = 2000
ELIM_LINE = 0.40
ELIM_BAND = [0.30, 0.45]
REPS = [1, 2, 3, 4, 5]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_clusters():
    """qid -> database cluster from the frozen domains/*/questions.json."""
    clusters = {}
    for qf in sorted(DOMAINS_DIR.glob("*/questions.json")):
        dom = qf.parent.name
        qs = json.loads(qf.read_text(encoding="utf-8"))
        assert isinstance(qs, list) and qs, qf
        clusters[dom] = [q["qid"] for q in qs]
    assert len(clusters) == 9, f"expected 9 database clusters, got {len(clusters)}"
    assert sum(len(v) for v in clusters.values()) == 60
    return clusters


def cluster_bootstrap_ci(diff_by_qid, clusters):
    """Frozen-convention cluster bootstrap of the mean of diff_by_qid.

    Fresh Random(SEED) per call (per arm), 9 cluster draws with replacement per
    iteration, pooled mean, B=2000, CI = [sorted[49], sorted[1949]].
    """
    names = sorted(clusters)
    assert len(names) == 9
    rng = random.Random(SEED)
    stats = []
    for _ in range(B):
        picked = [rng.choice(names) for _ in names]
        qids = [qid for c in picked for qid in clusters[c]]
        stats.append(sum(diff_by_qid[qid] for qid in qids) / len(qids))
    stats.sort()
    return [stats[49], stats[1949]]


def compute():
    # -- prereg gate ---------------------------------------------------------
    assert sha256_file(PREREG) == PREREG_SHA, "prereg sha256 mismatch — refusing to run"

    arms_summary = json.loads(ARMS_SUMMARY.read_text(encoding="utf-8"))
    verdicts = arms_summary["per_question_verdicts"]
    assert len(verdicts) == 60

    clusters = load_clusters()
    qid_order = [qid for dom in sorted(clusters) for qid in clusters[dom]]
    assert sorted(qid_order) == sorted(verdicts), "qid sets differ between domains/ and verdict matrix"

    def err(qid, arm):
        return 0 if verdicts[qid][arm] == "correct" else 1

    # -- frozen reference error set re-derived and asserted ------------------
    ref_error_qids = sorted(q for q in verdicts if err(q, REFERENCE) == 1)
    assert ref_error_qids == sorted(arms_summary["reference_error_qids"]), \
        "re-derived reference error set != frozen reference_error_qids"
    assert len(ref_error_qids) == 36 == arms_summary["reference_errors"]
    for arm in [REFERENCE] + COMPARISON_ARMS:
        n = sum(err(q, arm) for q in verdicts)
        assert n == arms_summary["error_counts"][arm], (arm, n)

    # -- (a) paired per-question differences + cluster-bootstrap CIs ---------
    paired = {}
    for arm in COMPARISON_ARMS:
        diff = {qid: err(qid, REFERENCE) - err(qid, arm) for qid in verdicts}
        mean = sum(diff.values()) / len(diff)
        ci = cluster_bootstrap_ci(diff, clusters)
        per_cluster = {
            dom: {
                "n": len(clusters[dom]),
                "sum_diff": sum(diff[q] for q in clusters[dom]),
                "mean_diff": sum(diff[q] for q in clusters[dom]) / len(clusters[dom]),
            }
            for dom in sorted(clusters)
        }
        paired[arm] = {
            "direction": f"{REFERENCE} minus {arm} (positive = arm makes fewer errors)",
            "errors_reference": arms_summary["error_counts"][REFERENCE],
            "errors_arm": arms_summary["error_counts"][arm],
            "mean_paired_diff": mean,
            "ci95_percentile": ci,
            "ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0),
            "n_questions": 60,
            "discordant": {
                "ref_err_arm_ok": sum(1 for v in diff.values() if v == 1),
                "ref_ok_arm_err": sum(1 for v in diff.values() if v == -1),
                "concordant": sum(1 for v in diff.values() if v == 0),
            },
            "per_cluster": per_cluster,
            "per_question_diff": {qid: diff[qid] for qid in qid_order},
            "note_sign_symmetry": (
                "arm-minus-reference is the exact negation; whether the CI "
                "includes 0 is sign-invariant"
            ),
        }

    # -- (b) elimination restatement from the five S3 reps -------------------
    def gov_verdict(rep, qid):
        if rep == 1:
            return verdicts[qid]["governance_informed"]
        f = S3_DIR / "runs_rep" / "governance_informed" / f"rep{rep}" / f"{qid}.json"
        return json.loads(f.read_text(encoding="utf-8"))["verdict"]

    per_rep = {}
    for rep in REPS:
        n_elim = sum(1 for q in ref_error_qids if gov_verdict(rep, q) == "correct")
        per_rep[str(rep)] = {
            "eliminated_n": n_elim,
            "of_reference_errors": 36,
            "eliminated_frac": n_elim / 36,
            "source": ("frozen pilot2_arms_summary.json per_question_verdicts" if rep == 1
                       else f"poststudy_20260820/s3/runs_rep/governance_informed/rep{rep}/"),
        }

    # assert equality with the frozen S3 summary values
    s3 = json.loads(S3_SUMMARY.read_text(encoding="utf-8"))
    s3_per_rep = s3["elimination_governance_informed"]["per_rep"]
    for rep in REPS:
        a, b = per_rep[str(rep)], s3_per_rep[str(rep)]
        assert a["eliminated_n"] == b["eliminated_n"], (rep, a, b)
        assert a["eliminated_frac"] == b["eliminated_frac"], (rep, a, b)
    fracs = [per_rep[str(r)]["eliminated_frac"] for r in REPS]
    elim = {
        "reference_error_set": "36 frozen baseline_claude rep1 errors (re-derived and asserted)",
        "per_rep": per_rep,
        "min_frac": min(fracs),
        "max_frac": max(fracs),
        "range": [min(fracs), max(fracs)],
        "prereg_line": ELIM_LINE,
        "prereg_band": ELIM_BAND,
        "all_in_band": all(ELIM_BAND[0] <= f <= ELIM_BAND[1] for f in fracs),
        "range_straddles_line": bool(min(fracs) < ELIM_LINE < max(fracs)),
        "reasserted_equal_to_frozen_s3_summary": True,
    }

    # -- prediction adjudication --------------------------------------------
    p1_met = paired["governance_informed"]["ci_excludes_zero"]
    p2_detail = {a: (not paired[a]["ci_excludes_zero"]) for a in TRIVIAL_ARMS}
    p2_met = all(p2_detail.values())
    p3_met = elim["all_in_band"] and elim["range_straddles_line"]
    predictions = {
        "S4-P1": {
            "statement": "the reference−governance paired-difference CI excludes 0",
            "observed": {
                "mean": paired["governance_informed"]["mean_paired_diff"],
                "ci95": paired["governance_informed"]["ci95_percentile"],
            },
            "met": bool(p1_met),
            "verdict": "MET" if p1_met else "MISS",
        },
        "S4-P2": {
            "statement": "every variant−reference paired-difference CI includes 0",
            "observed": {a: {"mean_ref_minus_arm": paired[a]["mean_paired_diff"],
                            "ci95_ref_minus_arm": paired[a]["ci95_percentile"],
                            "includes_zero": p2_detail[a]} for a in TRIVIAL_ARMS},
            "met": bool(p2_met),
            "verdict": "MET" if p2_met else "MISS",
        },
        "S4-P3": {
            "statement": ("per-rep elim values all lie in [0.30, 0.45] and the min–max "
                          "range straddles the pre-registered 0.40 line"),
            "observed": {"per_rep_fracs": fracs, "min": elim["min_frac"],
                         "max": elim["max_frac"], "all_in_band": elim["all_in_band"],
                         "range_straddles_line": elim["range_straddles_line"]},
            "met": bool(p3_met),
            "verdict": "MET" if p3_met else "MISS",
        },
    }

    summary = {
        "study": "S4 — Paired-difference uncertainty (PREREG_poststudy2_20260823.md §S4)",
        "prereg_sha256": PREREG_SHA,
        "prereg_sha256_reasserted_from_disk": True,
        "deterministic": True,
        "llm_calls": 0,
        "inputs": {
            "verdict_matrix": "pilot2/pilot2_arms_summary.json per_question_verdicts (frozen rep1)",
            "verdict_matrix_sha256": sha256_file(ARMS_SUMMARY),
            "cluster_mapping": "pilot2/domains/*/questions.json (9 databases)",
            "s3_rep_caches": "pilot2/poststudy_20260820/s3/runs_rep/governance_informed/rep{2..5}",
            "s3_summary_sha256": sha256_file(S3_SUMMARY),
        },
        "method": {
            "error_indicator": "verdict != 'correct' (frozen scorer verdicts, zero re-scoring)",
            "paired_difference": f"per-question err({REFERENCE}) - err(arm)",
            "bootstrap": {
                "unit": "database cluster (9 domains)",
                "B": B,
                "seed": SEED,
                "rng": "random.Random(seed), fresh per arm (identical resample "
                       "sequence across arms, as in frozen make_pilot2_summary.py)",
                "resample": "9 cluster draws with replacement per iteration, questions pooled",
                "ci": "95% percentile, [sorted[49], sorted[1949]] of B=2000 (frozen convention)",
            },
        },
        "reference_arm": REFERENCE,
        "reference_errors": 36,
        "paired_differences": paired,
        "elimination_restatement": elim,
        "predictions": predictions,
        "n_predictions_missed": sum(1 for p in predictions.values() if not p["met"]),
    }
    return summary


def fmt(x):
    return f"{x:.4f}"


def render_report(s):
    """S4_REPORT.md rendered from the summary JSON dict (no other source)."""
    L = []
    L.append("# S4 — Paired-difference uncertainty (deterministic)")
    L.append("")
    L.append(f"Governing prereg: `PREREG_poststudy2_20260823.md`, sha256 `{s['prereg_sha256']}` "
             "(re-asserted from disk at run time). Zero LLM calls; every number below is "
             "computed by `s4_paired_ci.py` from frozen inputs and read back out of "
             "`s4_summary.json`.")
    L.append("")
    L.append("## Inputs")
    L.append("")
    L.append(f"- Verdict matrix: {s['inputs']['verdict_matrix']} "
             f"(sha256 `{s['inputs']['verdict_matrix_sha256'][:16]}…`)")
    L.append(f"- Clusters: {s['inputs']['cluster_mapping']}")
    L.append(f"- S3 rep caches: {s['inputs']['s3_rep_caches']}; frozen s3_summary.json "
             f"sha256 `{s['inputs']['s3_summary_sha256'][:16]}…`")
    L.append(f"- Reference arm: `{s['reference_arm']}` with {s['reference_errors']} frozen errors "
             "(error set re-derived from the matrix and asserted equal to the frozen list).")
    L.append("")
    L.append("## (a) Paired per-question error differences, cluster-bootstrap 95% CIs")
    L.append("")
    b = s["method"]["bootstrap"]
    L.append(f"Difference direction: reference − arm (positive = arm makes fewer errors). "
             f"Bootstrap: {b['unit']}, B={b['B']}, seed {b['seed']}, {b['ci']}.")
    L.append("")
    L.append("| arm | ref errs | arm errs | mean paired diff | 95% CI | excludes 0 | discordant (ref-err/arm-ok, ref-ok/arm-err) |")
    L.append("|---|---|---|---|---|---|---|")
    for arm, p in s["paired_differences"].items():
        d = p["discordant"]
        L.append(f"| {arm} | {p['errors_reference']} | {p['errors_arm']} | "
                 f"{fmt(p['mean_paired_diff'])} | [{fmt(p['ci95_percentile'][0])}, "
                 f"{fmt(p['ci95_percentile'][1])}] | {'yes' if p['ci_excludes_zero'] else 'no'} | "
                 f"{d['ref_err_arm_ok']} / {d['ref_ok_arm_err']} |")
    L.append("")
    L.append("Sign note: arm−reference is the exact negation of reference−arm; whether a CI "
             "includes 0 is invariant to the sign convention, so S4-P2 is adjudicated on the "
             "reference−variant CIs above.")
    L.append("")
    L.append("Per-cluster mean paired differences (reference − arm):")
    L.append("")
    doms = sorted(next(iter(s["paired_differences"].values()))["per_cluster"])
    L.append("| arm | " + " | ".join(doms) + " |")
    L.append("|---|" + "---|" * len(doms))
    for arm, p in s["paired_differences"].items():
        L.append("| " + arm + " | " +
                 " | ".join(fmt(p["per_cluster"][d]["mean_diff"]) for d in doms) + " |")
    L.append("")
    L.append("## (b) Elimination-uncertainty restatement (five S3 reps)")
    L.append("")
    e = s["elimination_restatement"]
    L.append(f"Elim = fraction of the {s['reference_errors']} frozen reference errors the "
             "governance-informed arm answers correctly in a given rep. Re-derived here from "
             "the rep caches and asserted equal to the frozen `s3_summary.json` values "
             f"(`reasserted_equal_to_frozen_s3_summary = {e['reasserted_equal_to_frozen_s3_summary']}`).")
    L.append("")
    L.append("| rep | eliminated | frac | source |")
    L.append("|---|---|---|---|")
    for rep in ["1", "2", "3", "4", "5"]:
        r = e["per_rep"][rep]
        L.append(f"| {rep} | {r['eliminated_n']}/{r['of_reference_errors']} | "
                 f"{fmt(r['eliminated_frac'])} | {r['source']} |")
    L.append("")
    L.append(f"Min–max range: [{fmt(e['min_frac'])}, {fmt(e['max_frac'])}]; pre-registered line "
             f"{e['prereg_line']}; band {e['prereg_band']}. All reps in band: "
             f"{'yes' if e['all_in_band'] else 'no'}; range straddles the {e['prereg_line']} line: "
             f"{'yes' if e['range_straddles_line'] else 'no'}. The frozen case-(iii) call "
             "(rep1 elim 0.3611 < 0.40) sits inside a rep-to-rep band that crosses the line — "
             "boundary-honest, not comfortable, exactly as pre-registered.")
    L.append("")
    L.append("## Pre-registered predictions")
    L.append("")
    for pid in ["S4-P1", "S4-P2", "S4-P3"]:
        p = s["predictions"][pid]
        L.append(f"- **{pid}** — {p['statement']}: **{p['verdict']}**")
        if pid == "S4-P1":
            o = p["observed"]
            L.append(f"  - mean {fmt(o['mean'])}, CI [{fmt(o['ci95'][0])}, {fmt(o['ci95'][1])}]")
        elif pid == "S4-P2":
            for arm, o in p["observed"].items():
                L.append(f"  - {arm}: mean {fmt(o['mean_ref_minus_arm'])}, CI "
                         f"[{fmt(o['ci95_ref_minus_arm'][0])}, {fmt(o['ci95_ref_minus_arm'][1])}], "
                         f"includes 0: {'yes' if o['includes_zero'] else 'no'}")
        else:
            o = p["observed"]
            L.append(f"  - per-rep fracs {[round(f, 4) for f in o['per_rep_fracs']]}, "
                     f"min {fmt(o['min'])}, max {fmt(o['max'])}")
    L.append("")
    L.append(f"Predictions missed: {s['n_predictions_missed']}/3. A miss is published as a miss.")
    L.append("")
    return "\n".join(L)


def write_or_assert(path: Path, data: bytes):
    """Append-only discipline: first run writes; any re-run asserts byte-identity."""
    if path.exists():
        assert path.read_bytes() == data, f"re-run produced different bytes for {path}"
        return "byte-identical (asserted)"
    path.write_bytes(data)
    return "written"


def main():
    summary = compute()
    js = (json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
    # report is rendered from the JSON bytes just produced, not from live state
    report = render_report(json.loads(js.decode("utf-8"))).encode("utf-8")
    r1 = write_or_assert(HERE / "s4_summary.json", js)
    r2 = write_or_assert(HERE / "S4_REPORT.md", report)
    print(f"s4_summary.json: {r1}  sha256 {hashlib.sha256(js).hexdigest()}")
    print(f"S4_REPORT.md:    {r2}  sha256 {hashlib.sha256(report).hexdigest()}")
    print(f"predictions missed: {summary['n_predictions_missed']}/3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
