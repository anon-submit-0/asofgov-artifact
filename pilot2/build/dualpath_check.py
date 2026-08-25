# -*- coding: utf-8 -*-
"""金标双人规则自检：路径 A（手写 gold_sql 直算，建库时已物化）
vs 路径 B（治理链推导，govchain_resolver 仅凭 G_v+D+题面可见字段独立复算）。

对每题比对：裁定类别 / 拒因+子型 / 数值（相对容差 1e-9）/ 改写描述 / 窗结构（双方都给出时）。
路径 B 输入被硬性投影到 VISIBLE_FIELDS —— 金标侧字段对其不可达（A2 泄漏纪律的运行时执行）。
同时收集路径 B 的种子触达行集 → ND-3 干扰行占比的分母/分子。
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import duckdb
import lib_build as L
from questions_def import VISIBLE_FIELDS
from govchain_resolver import Resolver


def close(a, b, tol=1e-9):
    if a is None or b is None:
        return a == b
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    a, b = float(a), float(b)
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def cmp_value(gold, got, kind):
    if gold is None and got is None:
        return True
    if isinstance(gold, list):
        if not isinstance(got, list) or len(gold) != len(got):
            return False
        return all(str(g[0]) == str(h[0]) and close(g[1], h[1]) for g, h in zip(gold, got))
    return close(gold, got)


def cmp_windows(gold, got):
    if gold is None or got is None:
        return None  # 一侧未物化（拒答早退等）→ 不计入硬比对
    return json.dumps(gold, sort_keys=True) == json.dumps(got, sort_keys=True)


def cmp_rewrite(gold, got):
    if gold is None and got is None:
        return True
    if (gold is None) != (got is None):
        return False
    if gold.get("kind") != got.get("kind"):
        return False
    if gold["kind"] == "granularity_rollup":
        return (gold.get("requested_level") == got.get("requested_level")
                and gold.get("effective_level") == got.get("effective_level"))
    if gold["kind"] == "hull_trim":
        return (json.dumps(gold.get("effective"), sort_keys=True)
                == json.dumps(got.get("effective"), sort_keys=True))
    if gold["kind"] == "mask":
        return gold.get("mask_class") == got.get("mask_class")
    return True


def main():
    results, mismatches = [], []
    touched_by_dom, seed_totals = {}, {}
    for domain in L.DOMAINS:
        d = L.dom_dir(domain)
        qs = json.load(open(os.path.join(d, "questions.json")))
        con = duckdb.connect(os.path.join(d, "warehouse.duckdb"), read_only=True)
        rz = Resolver(con)
        seed_totals[domain] = {tn: len(rz.gov.t[tn]) for tn in rz.gov.t}
        for q in qs:
            visible = {k: q.get(k) for k in VISIBLE_FIELDS}
            assert "gold_sql" not in visible and "gold_value" not in visible
            try:
                res = rz.resolve(visible)
                err = None
            except Exception as e:
                res = {"label": "ERROR", "value": None, "refusal_reason": None,
                       "refusal_subtype": None, "windows": None, "rewrite": None,
                       "offdiag": False}
                err = f"{type(e).__name__}: {e}"
            row = {"qid": q["qid"], "domain": domain,
                   "gold_kind": q["expected_kind"], "b_kind": res["label"],
                   "kind_ok": q["expected_kind"] == res["label"],
                   "reason_ok": (q["refusal_reason"] == res.get("refusal_reason")
                                 and q["refusal_subtype"] == res.get("refusal_subtype")),
                   "value_ok": cmp_value(q["gold_value"], res.get("value"), q["expected_kind"]),
                   "rewrite_ok": cmp_rewrite(q.get("rewrite"), res.get("rewrite")),
                   "windows_cmp": cmp_windows(q.get("windows"), res.get("windows")),
                   "b_value": res.get("value"), "gold_value": q["gold_value"],
                   "b_reason": res.get("refusal_reason"), "b_subtype": res.get("refusal_subtype"),
                   "offdiag": res.get("offdiag"), "error": err}
            row["ok"] = (row["kind_ok"] and row["reason_ok"] and row["value_ok"]
                         and row["rewrite_ok"] and row["windows_cmp"] is not False
                         and err is None)
            results.append(row)
            if not row["ok"]:
                mismatches.append(row)
        touched_by_dom[domain] = sorted(map(list, rz.touched))
        con.close()

    n_ok = sum(1 for r in results if r["ok"])
    rep = {"n": len(results), "agree": n_ok, "mismatch": len(results) - n_ok,
           "mismatches": mismatches, "results": results,
           "touched_by_domain": touched_by_dom,
           "seed_totals": seed_totals}
    L.jdump(rep, os.path.join(L.ROOT, "build", "dualpath_report.json"))
    print(f"[dualpath] {n_ok}/{len(results)} agree; mismatches={len(results)-n_ok}")
    for m in mismatches:
        print(" MISMATCH", m["qid"], "kind", m["gold_kind"], "->", m["b_kind"],
              "| reason_ok", m["reason_ok"], "| value", m["gold_value"], "->", m["b_value"],
              "| rw_ok", m["rewrite_ok"], "| win", m["windows_cmp"], "| err", m["error"])
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
