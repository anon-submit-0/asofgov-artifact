#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 — Subset robustness of the frozen score matrix (deterministic, zero LLM).

Governing prereg: PREREG_poststudy_20260820.md
  sha256 f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24

Inputs (READ-ONLY, frozen):
  * pilot2/pilot2_arms_summary.json  -> per_question_verdicts (60 qid x 9 arms)
  * pilot2/domains/*/questions.json  -> qid -> database (cluster) mapping
  * sandbox-regenerated copy of pilot2_arms_summary.json (byte-equality asserted,
    i.e. the matrix used here is exactly the one the frozen scorer reproduces)

Computations (PREREG S1):
  (a) LOCO: leave-one-database-out, 9 folds, error rates for all 9 arms;
  (b) database-level bootstrap, B=2000, seed 20260820 (consistency restatement
      of the frozen cluster bootstrap; algorithm byte-mirrors
      make_pilot2_summary.bootstrap(): fresh random.Random(seed) per arm,
      9 sorted cluster names resampled with replacement, ci95 = [rates[49],
      rates[1949]] over the sorted B=2000 rates);
  (c) question-level jackknife on baseline_claude and governance_informed.

Predictions judged exactly as written:
  S1-P1: in every LOCO fold, every plain-baseline family error >= 0.40.
  S1-P2: in every LOCO fold, governance_informed error < every plain-baseline
         error, and mechanism = 0 errors.
  S1-P3: in every LOCO fold, governance_informed error >= 0.35.

Outputs (append-only, under poststudy_20260820/s1/):
  loco_report.json, S1_REPORT.md
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import random
import sys

PREREG_SHA = "f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24"

FROZEN_ROOT = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2")
SANDBOX_ROOT = pathlib.Path(
    "/private/tmp/claude-502/-Volumes-SSD-1-vldb-asof/"
    "831806d7-8bc6-464b-9baf-a933f760e40d/scratchpad/poststudy-sandbox/pilot2")
OUT_DIR = FROZEN_ROOT / "poststudy_20260820" / "s1"

ARMS = ["baseline_claude", "baseline_qwen", "baseline_deepseek", "baseline_minimax",
        "trivial_claude", "trivial_v2", "trivial_v3", "governance_informed",
        "mechanism"]
PLAIN = ARMS[:4]

BOOT_B = 2000
BOOT_SEED = 20260820  # PREREG S1(b); frozen main-study bootstrap used 20260731


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_matrix():
    """Return (per_question_verdicts, qid->domain, frozen summary dict)."""
    frozen = FROZEN_ROOT / "pilot2_arms_summary.json"
    sandbox = SANDBOX_ROOT / "pilot2_arms_summary.json"
    fb, sb = frozen.read_bytes(), sandbox.read_bytes()
    assert fb == sb, ("sandbox-regenerated pilot2_arms_summary.json is NOT "
                      "byte-identical to the frozen committed copy — abort")
    summary = json.loads(fb.decode("utf-8"))
    pq = summary["per_question_verdicts"]
    assert len(pq) == 60
    for qid, row in pq.items():
        assert sorted(row) == sorted(ARMS), (qid, sorted(row))

    dom_of = {}
    for d in sorted((FROZEN_ROOT / "domains").iterdir()):
        qj = d / "questions.json"
        if not qj.is_file():
            continue
        qs = json.loads(qj.read_text(encoding="utf-8"))
        qlist = qs if isinstance(qs, list) else qs["questions"]
        for q in qlist:
            dom_of[q["qid"]] = d.name
    assert set(dom_of) == set(pq), "qid sets differ between questions.json and matrix"
    doms = sorted(set(dom_of.values()))
    assert len(doms) == 9, doms
    return pq, dom_of, summary, {"frozen_sha256": sha256(frozen),
                                 "sandbox_sha256": sha256(sandbox)}


def err_indicator(pq, arm):
    return {qid: (0 if pq[qid][arm] == "correct" else 1) for qid in pq}


def loco(pq, dom_of):
    doms = sorted(set(dom_of.values()))
    folds = {}
    for left_out in doms:
        keep = [qid for qid in pq if dom_of[qid] != left_out]
        n = len(keep)
        fold = {"left_out_db": left_out,
                "n_questions_left_out": 60 - n,
                "n_questions_kept": n,
                "error_rate": {}, "error_count": {}}
        for arm in ARMS:
            e = sum(1 for qid in keep if pq[qid][arm] != "correct")
            fold["error_count"][arm] = e
            fold["error_rate"][arm] = e / n
        folds[left_out] = fold
    return folds


def bootstrap(pq, dom_of, arm, seed=BOOT_SEED, b=BOOT_B):
    """Byte-mirror of make_pilot2_summary.bootstrap(), seed parameterised."""
    clusters = {}
    for qid in pq:
        clusters.setdefault(dom_of[qid], []).append(qid)
    names = sorted(clusters)
    assert len(names) == 9
    ind = err_indicator(pq, arm)
    rng = random.Random(seed)
    rates = []
    for _ in range(b):
        picked = [rng.choice(names) for _ in names]
        qids = [qid for c in picked for qid in clusters[c]]
        rates.append(sum(ind[qid] for qid in qids) / len(qids))
    rates.sort()
    return [rates[49], rates[1949]]


def jackknife(pq, dom_of, arm):
    """Question-level (leave-one-question-out) jackknife, n=60."""
    qids = sorted(pq)
    n = len(qids)
    ind = err_indicator(pq, arm)
    total = sum(ind.values())
    theta_hat = total / n
    thetas = [(total - ind[qid]) / (n - 1) for qid in qids]
    theta_bar = sum(thetas) / n
    var = (n - 1) / n * sum((t - theta_bar) ** 2 for t in thetas)
    se = math.sqrt(var)
    return {"arm": arm, "n": n, "point_error_rate": theta_hat,
            "error_count": total,
            "jackknife_mean_of_leave_one_out": theta_bar,
            "jackknife_se": se,
            "ci95_normal_approx": [theta_hat - 1.959963984540054 * se,
                                   theta_hat + 1.959963984540054 * se],
            "leave_one_out_min": min(thetas),
            "leave_one_out_max": max(thetas),
            "per_fold": {qid: (total - ind[qid]) / (n - 1) for qid in qids}}


def main() -> int:
    prereg = FROZEN_ROOT / "poststudy_20260820" / "PREREG_poststudy_20260820.md"
    assert sha256(prereg) == PREREG_SHA, "prereg sha drift — abort"

    pq, dom_of, summary, matrix_hashes = load_matrix()

    # ---- (a) LOCO --------------------------------------------------------
    folds = loco(pq, dom_of)

    # ---- (b) bootstrap restatement, seed 20260820 ------------------------
    boot = {}
    for arm in ARMS:
        ind = err_indicator(pq, arm)
        boot[arm] = {"err": sum(ind.values()) / 60,
                     "ci95_seed20260820": bootstrap(pq, dom_of, arm),
                     "ci95_frozen_seed20260731":
                         summary["cluster_bootstrap"][arm]["ci95"]
                         if arm in summary["cluster_bootstrap"] else None,
                     "B": BOOT_B, "seed": BOOT_SEED,
                     "cluster_unit": "domain (9 public DBs)"}
        assert boot[arm]["err"] == summary["error_rate"][arm], arm

    # ---- (c) question-level jackknife, two headline arms -----------------
    jack = {arm: jackknife(pq, dom_of, arm)
            for arm in ("baseline_claude", "governance_informed")}

    # ---- predictions, exactly as written ---------------------------------
    # S1-P1: in every LOCO fold, every plain-baseline family error >= 0.40
    p1_viol = [(f, arm, folds[f]["error_rate"][arm])
               for f in sorted(folds) for arm in PLAIN
               if not folds[f]["error_rate"][arm] >= 0.40]
    # S1-P2: in every LOCO fold, governance_informed < every plain-baseline
    #        error, and mechanism = 0 errors
    p2_viol_gov = [(f, arm, folds[f]["error_rate"]["governance_informed"],
                    folds[f]["error_rate"][arm])
                   for f in sorted(folds) for arm in PLAIN
                   if not (folds[f]["error_rate"]["governance_informed"]
                           < folds[f]["error_rate"][arm])]
    p2_viol_mech = [(f, folds[f]["error_count"]["mechanism"])
                    for f in sorted(folds)
                    if folds[f]["error_count"]["mechanism"] != 0]
    # S1-P3: in every LOCO fold, governance_informed error >= 0.35
    p3_viol = [(f, folds[f]["error_rate"]["governance_informed"])
               for f in sorted(folds)
               if not folds[f]["error_rate"]["governance_informed"] >= 0.35]

    predictions = {
        "S1-P1": {"statement": "in every LOCO fold, every plain-baseline family "
                               "error >= 0.40",
                  "verdict": "MET" if not p1_viol else "MISSED",
                  "violations": [{"fold": f, "arm": a, "error_rate": e}
                                 for f, a, e in p1_viol]},
        "S1-P2": {"statement": "in every LOCO fold, governance_informed error < "
                               "every plain-baseline error, and mechanism = 0 "
                               "errors",
                  "verdict": "MET" if not (p2_viol_gov or p2_viol_mech)
                             else "MISSED",
                  "violations_gov_vs_plain":
                      [{"fold": f, "plain_arm": a, "gov_error": g,
                        "plain_error": p} for f, a, g, p in p2_viol_gov],
                  "violations_mechanism_nonzero":
                      [{"fold": f, "mechanism_errors": e}
                       for f, e in p2_viol_mech]},
        "S1-P3": {"statement": "in every LOCO fold, governance_informed error "
                               ">= 0.35",
                  "verdict": "MET" if not p3_viol else "MISSED",
                  "violations": [{"fold": f, "error_rate": e}
                                 for f, e in p3_viol]},
    }

    report = {
        "study": "S1 — Subset robustness of the frozen score matrix "
                 "(deterministic, zero LLM)",
        "prereg": "PREREG_poststudy_20260820.md",
        "prereg_sha256": PREREG_SHA,
        "matrix_source": {
            "file": "pilot2/pilot2_arms_summary.json -> per_question_verdicts",
            "sha256": matrix_hashes,
            "sandbox_byte_identical_to_frozen": True,
            "reproduction": "reproduce_all.sh light in isolated sandbox: "
                            "PASS=20 FAIL=0 incl. byte-identical "
                            "pilot2_summary.json / pilot2_arms_summary.json / "
                            "fig_data_pilot2.json / tables",
        },
        "n_questions": 60,
        "arms": ARMS,
        "plain_baseline_family": PLAIN,
        "full_sample_error_rate": summary["error_rate"],
        "loco_folds": folds,
        "bootstrap_restatement": boot,
        "question_jackknife": jack,
        "predictions": predictions,
    }
    (OUT_DIR / "loco_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({
        "loco_gov_range": [min(f["error_rate"]["governance_informed"]
                               for f in folds.values()),
                           max(f["error_rate"]["governance_informed"]
                               for f in folds.values())],
        "loco_plain_min": min(f["error_rate"][a]
                              for f in folds.values() for a in PLAIN),
        "predictions": {k: v["verdict"] for k, v in predictions.items()},
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
