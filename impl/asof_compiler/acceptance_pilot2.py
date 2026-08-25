#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""acceptance_pilot2.py — pilot2 六十题的编译器侧验收（对照 pilot2 冻结金标）。

三关（与 acceptance.py 的老 51 题三关同构；无"现役编译器"对照——pilot2 没有
legacy compiler，金标由建仓期双路径复核锁定）：
  关 1（金标逐题一致）：value 题执行 SQL 与 gold_value 数值等（标量相对误差 1e-9；
        字符串金标全等；报表列表金标逐胞 (cell, val) 等）；refusal 题 reason token
        全等且见证子型与 refusal_subtype 对齐（mc_i/mc_ii/am_i..iv 经见证类型/条款映射）；
        rewrite 题另比 rewrite.kind（hull_trim / granularity_rollup / mask）。
  关 2（证书落盘）：每题 §6.2 信封写 impl/certs2/<qid>.json。
  关 3（良构自检）：wellformed_errors 零错误（producer 自检，非独立校验）。

用法：python3 acceptance_pilot2.py [--pilot2 <dir>] [--certs <out>]
退出码 0 = 全过。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import duckdb

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from asof_compiler import compile_question, wellformed_errors  # noqa: E402

REL_TOL = 1e-9

DOMAINS = ["california_schools", "card_games", "codebase_community",
           "debit_card_specializing", "european_football_2", "financial",
           "formula_1", "thrombosis_prediction", "world_1"]


def _num_eq(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    a, b = float(a), float(b)
    if b == 0:
        return abs(a) <= 1e-9
    return abs(a - b) / abs(b) <= REL_TOL


def _subtype_of(cert) -> str:
    """由见证形制回推拒因子型（C5 定义 5.3 的机器可读投影）。"""
    r = cert.get("refusal") or {}
    reason = r.get("reason")
    w = r.get("witness") or {}
    if reason == "missing-caliber":
        return "mc_i" if w.get("type") == "routing-lookup" else "mc_ii"
    if reason == "anchor-mismatch":
        c = (w.get("clause") or "").strip("()")
        return {"i": "am_i", "ii": "am_ii", "iii": "am_iii", "iv": "am_iv"}.get(c, "am_?")
    return ""


def _rewrite_kind(cert) -> set:
    kinds = set()
    for c in (cert.get("rewrite") or {}).get("cut_trace") or []:
        if c.get("kind") == "granularity_rollup":
            kinds.add("granularity_rollup")
        elif c.get("kind") == "mask_presentation":
            kinds.add("mask")
        elif "cut" in c:
            kinds.add("hull_trim")
    return kinds


def _gold_match(q, env, cert, db) -> tuple:
    dec = cert["disclosure"]["decision"]
    if q["expected_kind"] == "refusal":
        if "refusal" not in env:
            return False, f"expected refusal, got {dec}"
        if env["refusal"] != q["refusal_reason"]:
            return False, f"reason {env['refusal']} != {q['refusal_reason']}"
        sub = q.get("refusal_subtype")
        if sub and _subtype_of(cert) != sub:
            return False, f"subtype {_subtype_of(cert)} != {sub}"
        return True, ""
    if "sql" not in env:
        return False, f"expected {q['expected_kind']}, got refusal {env.get('refusal')}"
    if q["expected_kind"] == "rewrite":
        if dec != "REWRITE":
            return False, f"expected REWRITE, dec={dec}"
        want = (q.get("rewrite") or {}).get("kind")
        if want and want not in _rewrite_kind(cert):
            return False, f"rewrite kind {sorted(_rewrite_kind(cert))} !∋ {want}"
    elif dec != "ANSWER":
        return False, f"expected ANSWER, dec={dec}"

    con = duckdb.connect(db, read_only=True)
    try:
        rows = con.execute(env["sql"]).fetchall()
    except Exception as e:  # noqa: BLE001
        return False, f"sql failed: {e}"
    finally:
        con.close()
    gold = q.get("gold_value")
    if isinstance(gold, list):
        got = [[r[0], None if r[1] is None else float(r[1])] for r in rows]
        if len(got) != len(gold):
            return False, f"cells {len(got)} != {len(gold)}"
        for (gc, gvv), (wc, wv) in zip(got, gold):
            if str(gc) != str(wc) or not _num_eq(gvv, wv):
                return False, f"cell ({gc},{gvv}) != ({wc},{wv})"
        return True, ""
    v = rows[0][0] if rows else None
    if isinstance(gold, str):
        return (str(v) == gold), ("" if str(v) == gold else f"{v!r} != {gold!r}")
    ok = v is not None and _num_eq(v, gold)
    return ok, ("" if ok else f"{v!r} != {gold!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot2", default=str(_HERE.parent.parent / "pilot2"))
    ap.add_argument("--certs", default=str(_HERE.parent / "certs2"))
    args = ap.parse_args()
    root = pathlib.Path(args.pilot2)
    certs_dir = pathlib.Path(args.certs)
    certs_dir.mkdir(parents=True, exist_ok=True)

    n = 0
    fails, wf_fails = [], []
    rows = []
    for dom in DOMAINS:
        d = root / "domains" / dom
        questions = json.loads((d / "questions.json").read_text(encoding="utf-8"))
        db = str(d / "warehouse.duckdb")
        for q in questions:
            n += 1
            env = compile_question(q, d)
            cert = env["certificate"]
            (certs_dir / f"{q['qid']}.json").write_text(
                json.dumps(env, ensure_ascii=False, indent=1, default=str),
                encoding="utf-8")
            errs = wellformed_errors(cert, env)
            if errs:
                wf_fails.append((q["qid"], errs))
            ok, why = _gold_match(q, env, cert, db)
            if not ok:
                fails.append((q["qid"], why))
            rows.append((q["qid"], cert["disclosure"]["decision"],
                         env.get("refusal", "value"),
                         "gold:OK" if ok else f"gold:FAIL {why}"))

    for r in rows:
        print(f"  {r[0]:10} dec={r[1]:8} out={r[2]:18} {r[3]}")
    print(f"\nquestions={n}")
    print(f"gold_match={n - len(fails)}/{n}")
    print(f"certificates_written={n} -> {certs_dir}")
    print(f"wellformed_selfcheck_errors={sum(len(e) for _, e in wf_fails)}")
    if fails:
        print("GOLD FAILURES:")
        for f in fails:
            print("  ", f)
    if wf_fails:
        print("WELLFORMEDNESS ERRORS:")
        for f in wf_fails:
            print("  ", f)
    ok = not fails and not wf_fails
    print("ACCEPTANCE-P2:", "ALL OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
