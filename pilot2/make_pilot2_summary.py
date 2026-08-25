#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pilot2 · 统一评分与汇总（consolidation 阶段；评分 = 缓存 raw 的纯函数，零 LLM 调用）。

来源纪律：
  * 判定链 import 冻结 `pilot/run_pilot.py`（sha256 断言后 import，不复制任何函数）;
  * §4.2 三形态分派 import `pilot2/run_pilot2_arms.py` 的 `fetch_and_score`（与跑臂时
    逐字节同一实现，评分对所有臂统一）;
  * mechanism = certs2 冻结验收锚点（金标 60/60 → 0/60 错），本轮零调用零重评;
  * 簇自助逐字复刻 run_pilot.py 主流程算法：9 簇整簇有放回，B=2000，
    每臂各自新建 random.Random(20260731)（公共随机数）。

输出（不覆盖任何冻结件）：
  pilot2/pilot2_arms_summary.json   （PREREG §4.4 指名汇总：逐题表+三张分片表+账目）
  pilot2/pilot2_summary.json        （结构对齐旧 pilot/pilot_summary.json，论文工具链用）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import sys

P2 = pathlib.Path(__file__).resolve().parent
RUNS = P2 / "runs"

FROZEN_RUN_PILOT_SHA = "fecda681ccce203fa08e1a8b28a8ff722093a50ce656c62e86d921b5949309ef"
rp_path = P2.parent / "pilot" / "run_pilot.py"
got = hashlib.sha256(rp_path.read_bytes()).hexdigest()
assert got == FROZEN_RUN_PILOT_SHA, f"run_pilot.py sha drift: {got}"

sys.path.insert(0, str(P2.parent / "pilot"))
sys.path.insert(0, str(P2))
import run_pilot as RP            # noqa: E402  冻结判定链
import run_pilot2_arms as R2      # noqa: E402  §4.2 分派（跑臂同一实现）

ARMS = ["baseline_claude", "baseline_qwen", "baseline_deepseek", "baseline_minimax",
        "trivial_claude", "trivial_v2", "trivial_v3", "governance_informed"]
PLAIN = ARMS[:4]
TRIVIAL = ARMS[4:7]
VERDICTS = ("correct", "wrong_value", "execution_error",
            "answered_should_refuse", "refused_should_answer", "no_sql")

# PREREG §5.2 冻结题集（决定性探针 7 题 / 元数据可判 5 题）
PROBE7 = ["FIN-Q7", "F1-Q7", "DEB-Q6", "EF2-Q5", "CARD-Q7", "F1-Q8", "EF2-Q6"]
MD5 = ["CA-Q6", "FIN-Q8", "W1-Q5", "DEB-Q7", "CARD-Q6"]

REASON_SHORT = {"out-of-validity": "OOV", "anchor-mismatch": "AM",
                "missing-caliber": "MC", "disclosure-blocked": "DB"}


def load_questions():
    qs = R2.questions()
    assert len(qs) == 60 and len({q["qid"] for q, _ in qs}) == 60
    ek = {}
    for q, _ in qs:
        ek[q["expected_kind"]] = ek.get(q["expected_kind"], 0) + 1
    assert ek == {"value": 33, "rewrite": 12, "refusal": 15}, ek
    return qs


def rescore_arm(arm: str, qs) -> list[dict]:
    """镜像 run_pilot2_arms.eval_one 的缓存分支：从缓存 raw 纯函数重评。"""
    recs = []
    for q, d in qs:
        f = RUNS / arm / f"{q['qid']}.json"
        assert f.is_file(), f"missing cache {arm}/{q['qid']}"
        rec = json.loads(f.read_text(encoding="utf-8"))
        raw = rec.get("raw") or ""
        sql = RP.extract_sql(raw)
        if len(raw) >= RP.RAW_CAP and sql != "REFUSE" and rec.get("sql"):
            sql = rec["sql"]
        kind, value, verdict = R2.fetch_and_score(q, sql, str(d / "warehouse.duckdb"))
        out = dict(rec)
        out.update(kind=kind, value=value, verdict=verdict, sql=sql)
        recs.append(out)
    return recs


def mechanism_recs(qs) -> list[dict]:
    """certs2 冻结验收锚点：金标 60/60（拒因匹配已验）→ 全部 correct；零重评。"""
    out = []
    for q, _ in qs:
        assert (P2.parent / "impl" / "certs2" / f"{q['qid']}.json").is_file(), q["qid"]
        kind = "refuse" if q["expected_kind"] == "refusal" else "value"
        out.append({"qid": q["qid"], "system": "mechanism", "kind": kind,
                    "verdict": "correct", "empty_response": False})
    return out


def bootstrap(recs, qs):
    clusters = {}
    for q, d in qs:
        clusters.setdefault(d.name, []).append(q["qid"])
    names = sorted(clusters)
    assert len(names) == 9
    by_qid = {r["qid"]: r for r in recs}
    rng = random.Random(20260731)
    rates = []
    for _ in range(2000):
        picked = [rng.choice(names) for _ in names]
        qids = [qid for c in picked for qid in clusters[c]]
        rates.append(sum(1 for qid in qids if by_qid[qid]["verdict"] != "correct") / len(qids))
    rates.sort()
    return [rates[49], rates[1949]]


def main() -> int:
    qs = load_questions()
    by_dom, refusal_qids, value_qids = {}, [], []
    reason_of, form_of = {}, {}
    for q, d in qs:
        by_dom.setdefault(d.name, []).append(q["qid"])
        form_of[q["qid"]] = q["expected_kind"]
        if q["expected_kind"] == "refusal":
            refusal_qids.append(q["qid"])
            reason_of[q["qid"]] = q["refusal_reason"]
        else:
            value_qids.append(q["qid"])
    rc = {}
    for r in reason_of.values():
        rc[r] = rc.get(r, 0) + 1
    assert rc == {"out-of-validity": 4, "anchor-mismatch": 5,
                  "missing-caliber": 3, "disclosure-blocked": 3}, rc
    db3 = sorted(qid for qid, r in reason_of.items() if r == "disclosure-blocked")

    results = {arm: rescore_arm(arm, qs) for arm in ARMS}
    results["mechanism"] = mechanism_recs(qs)

    def err_n(recs):
        return sum(1 for r in recs if r["verdict"] != "correct")

    m = {s: err_n(r) / 60 for s, r in results.items()}
    ref = {r["qid"]: r for r in results["baseline_claude"]}
    ref_err = [qid for qid, r in ref.items() if r["verdict"] != "correct"]

    def elim(s):
        by = {r["qid"]: r for r in results[s]}
        return (sum(1 for qid in ref_err if by[qid]["verdict"] == "correct")
                / len(ref_err)) if ref_err else 0.0

    boot, coverage, refusal_stats, taxonomy = {}, {}, {}, {}
    slices_cluster, slices_form, slices_reason = {}, {}, {}
    for s, recs in results.items():
        by = {r["qid"]: r for r in recs}
        boot[s] = {"err": m[s], "ci95": bootstrap(recs, qs), "B": 2000,
                   "cluster_unit": "domain (9 public DBs)"}
        coverage[s] = {"answered": sum(1 for r in recs if r["kind"] in ("value", "error")) / 60,
                       "refused": sum(1 for r in recs if r["kind"] == "refuse") / 60}
        refusal_stats[s] = {
            "correct_refusals": sum(1 for qid in refusal_qids if by[qid]["verdict"] == "correct"),
            "n_refusal_questions": 15,
            "by_reason": {REASON_SHORT[k]: {
                "n": rc[k],
                "correct": sum(1 for qid in refusal_qids
                               if reason_of[qid] == k and by[qid]["verdict"] == "correct")}
                for k in rc},
            "over_refusals_on_answer_questions": sum(
                1 for qid in value_qids if by[qid]["verdict"] == "refused_should_answer"),
            "n_answer_questions": 45,
        }
        taxonomy[s] = {v: n for v in VERDICTS
                       if (n := sum(1 for r in recs if r["verdict"] == v))}
        slices_cluster[s] = {c: {"n": len(qids),
                                 "errors": sum(1 for qid in qids if by[qid]["verdict"] != "correct")}
                             for c, qids in sorted(by_dom.items())}
        slices_form[s] = {f: {"n": sum(1 for v in form_of.values() if v == f),
                              "errors": sum(1 for qid, v in form_of.items()
                                            if v == f and by[qid]["verdict"] != "correct")}
                          for f in ("value", "rewrite", "refusal")}
        slices_reason[s] = refusal_stats[s]["by_reason"]

    elims = {s: elim(s) for s in ARMS}
    elims["mechanism"] = 1.0  # 恒等：mechanism 0/60（certs2），修掉 reference 全部错题

    A_prime = min(m[s] for s in PLAIN) >= 0.30
    C_prime = max(elims[s] for s in TRIVIAL) < 0.40

    # ---- governance 臂专项 ----
    gov = {r["qid"]: r for r in results["governance_informed"]}
    tv2 = {r["qid"]: r for r in results["trivial_v2"]}
    E_gov = err_n(results["governance_informed"])
    gov_err_qids = sorted(qid for qid, r in gov.items() if r["verdict"] != "correct")
    if E_gov == 0:
        scenario = "ND-4 FAIL (E=0): base defect — new seeds still degenerate"
    elif E_gov <= 2:
        scenario = "(ii) near-degenerate (1<=E<=2): treat as defect, per-question postmortem"
    elif elims["governance_informed"] >= 0.40:
        scenario = "(i) significant-but-far-from-zero (E>=3 & elim>=0.40)"
    else:
        scenario = "(iii) no substantial improvement (E>=3 & elim<0.40)"

    def paired(a_by, b_by):
        b = sum(1 for q_, _ in qs if a_by[q_["qid"]]["verdict"] == "correct"
                and b_by[q_["qid"]]["verdict"] != "correct")
        c = sum(1 for q_, _ in qs if a_by[q_["qid"]]["verdict"] != "correct"
                and b_by[q_["qid"]]["verdict"] == "correct")
        tie_ok = sum(1 for q_, _ in qs if a_by[q_["qid"]]["verdict"] == "correct"
                     and b_by[q_["qid"]]["verdict"] == "correct")
        return {"b_other_correct_gov_wrong": b, "c_other_wrong_gov_correct": c,
                "tie_both_correct": tie_ok, "tie_both_wrong": 60 - b - c - tie_ok,
                "net": c - b}

    empty = {s: sorted(r["qid"] for r in results[s] if r.get("empty_response"))
             for s in ARMS}
    prompt_chars = {s: sum(r.get("prompt_chars") or 0 for r in results[s]) for s in ARMS}

    per_q = {q["qid"]: {s: {r["qid"]: r for r in results[s]}[q["qid"]]["verdict"]
                        for s in ARMS + ["mechanism"]} for q, _ in qs}

    summary = {
        "n_questions": 60,
        "base": "pilot2 (9 public BIRD-derived DBs, frozen 2026-08-04)",
        "error_rate": m,
        "error_counts": {s: err_n(r) for s, r in results.items()},
        "cluster_bootstrap": boot,
        "coverage": coverage,
        "reference_baseline": "baseline_claude",
        "reference_errors": len(ref_err),
        "reference_error_qids": sorted(ref_err),
        "eliminated_by": elims,
        "eliminated_by_mechanism": elims["mechanism"],
        "eliminated_by_trivial": elims["trivial_claude"],
        "A_prime_pass(min plain-baseline err>=0.30)": A_prime,
        "B_prime_pass(mechanism 0/60 & elim=1.0, from frozen certs2)": True,
        "C_prime_pass(max trivial-variant elim<0.40)": C_prime,
        "refusal_stats": refusal_stats,
        "taxonomy": taxonomy,
        "slices": {"per_cluster": slices_cluster, "per_gold_form": slices_form,
                   "per_refusal_reason": slices_reason},
        "per_question_verdicts": per_q,
        "empty_responses": empty,
        "prompt_char_account": {"observed_sum": prompt_chars,
                                "manifest_totals": json.loads(
                                    (P2 / "prompt_pack" / "MANIFEST.json")
                                    .read_text())["prompt_totals"]},
        "governance_informed_arm": {
            "prereg": "PREREG_pilot2_arms.md §3 (ND-4 remount of B6 protocol; FROZEN 2026-08-04, 0 LLM calls at freeze)",
            "E_gov": E_gov,
            "error_qids": gov_err_qids,
            "eliminated_by_governance": elims["governance_informed"],
            "nd4_nondegeneracy": "PASS" if E_gov > 0 else "FAIL",
            "prereg_case": scenario,
            "probe7_metadata_undecidable": {
                qid: gov[qid]["verdict"] for qid in PROBE7},
            "probe7_errors": sum(1 for qid in PROBE7 if gov[qid]["verdict"] != "correct"),
            "metadata_decidable_5": {qid: gov[qid]["verdict"] for qid in MD5},
            "md5_fixed": sum(1 for qid in MD5 if gov[qid]["verdict"] == "correct"),
            "disclosure_blocked_3": {qid: gov[qid]["verdict"] for qid in db3},
            "paired_vs_baseline_claude": paired(ref, gov),
            "paired_vs_trivial_v2": paired(tv2, gov),
            "per_cluster_vs_reference": {
                c: {"n": len(qids),
                    "errors": sum(1 for qid in qids if gov[qid]["verdict"] != "correct"),
                    "correct_refusals": sum(1 for qid in qids if qid in refusal_qids
                                            and gov[qid]["verdict"] == "correct"),
                    "n_refusal_questions": sum(1 for qid in qids if qid in refusal_qids),
                    "baseline_claude_errors": sum(1 for qid in qids
                                                  if ref[qid]["verdict"] != "correct")}
                for c, qids in sorted(by_dom.items())},
        },
        "mechanism": {"error_rate": 0.0, "source": "impl/certs2 frozen acceptance "
                      "(gold 60/60, verifier ACCEPT 60/60, strict 50/60, 30 forgeries rejected); "
                      "zero calls, zero re-evaluation this round"},
        "scorer": {"run_pilot_sha256": FROZEN_RUN_PILOT_SHA,
                   "REL_TOL": RP.REL_TOL, "RAW_CAP": RP.RAW_CAP,
                   "dispatch": "§4.2 frozen: rowset {CA-Q5,CODE-Q4,DEB-Q5,TH-Q3}, "
                               "string {CODE-Q6,TH-Q4}, numeric otherwise",
                   "rescored_from": "cached raw responses in pilot2/runs/ — no new LLM calls"},
    }
    (P2 / "pilot2_arms_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 旧 pilot_summary.json 结构对齐版（论文工具链） ----
    old_shape = {
        "n_questions": 60,
        "error_rate": m,
        "cluster_bootstrap": boot,
        "coverage": coverage,
        "reference_baseline": "baseline_claude",
        "reference_errors": len(ref_err),
        "eliminated_by_mechanism": elims["mechanism"],
        "eliminated_by_trivial": elims["trivial_claude"],
        "A_pass(min plain-baseline err>=0.30)": A_prime,
        "B_pass(mechanism err=0 & elim=1.0)": True,
        "C_pass(trivial eliminates<0.40)": C_prime,
        "criteria_note": "A'/B'/C' are the pilot2 descriptive criteria pre-registered in "
                         "PREREG_pilot2_arms.md §4.4 — NOT a re-run of the old A/B/C gates "
                         "(old adjudication frozen in pilot/pilot_summary.json; old numbers "
                         "51-question enterprise base, not comparable)",
        "refusal_stats": {s: {"correct_refusals": refusal_stats[s]["correct_refusals"],
                              "n_refusal_questions": 15,
                              "over_refusals_on_value_questions":
                                  refusal_stats[s]["over_refusals_on_answer_questions"],
                              "n_value_questions": 45} for s in results},
        "taxonomy": taxonomy,
        "scorer": summary["scorer"],
        "governance_informed_arm": summary["governance_informed_arm"],
        "slices": summary["slices"],
        "empty_responses": empty,
        "details": "pilot2_arms_summary.json (per-question verdicts, prompt char account)",
    }
    (P2 / "pilot2_summary.json").write_text(
        json.dumps(old_shape, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"error_counts": summary["error_counts"],
                      "elims": elims, "A_prime": A_prime, "C_prime": C_prime,
                      "E_gov": E_gov, "scenario": scenario,
                      "empty": {k: v for k, v in empty.items() if v}},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
