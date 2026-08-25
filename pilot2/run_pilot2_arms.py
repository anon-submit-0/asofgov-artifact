#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pilot2 · 8 LLM 臂运行器（PREREG_pilot2_arms.md 的执行体；§7 产出物）。

设计约束（逐条对应 PREREG §1.2 / §4 / §7）：
  * **import `run_pilot`，不复制其任何函数**（A5）：llm / extract_sql / is_refusal /
    run_sql / score / PROMPT / TRIVIAL_* / REL_TOL / RAW_CAP 全部复用。
    本文件只提供：pilot2 路径装配、§4.2 扩展评分分派（6 道非数值金标）、runs/ 写入。
  * 写入路径只有 `pilot2/runs/<arm>/<qid>.json`（A6）；prompt_pack/domains/ 只读。
  * 缓存只写不删（§6.2）：已存在的 <qid>.json 一律终局，断点续跑只补从未写入的 qid。
  * 跑前断言 A0–A4/A7 全过才发第一次调用；`--dry` 只跑断言（零调用）。

用法：
  python3 run_pilot2_arms.py --dry                    # 断言 + A3 逐字节重建校验，零调用
  python3 run_pilot2_arms.py <arm> [<arm> ...]        # 逐臂串行运行（臂内 4 并发）
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

import duckdb

P2 = pathlib.Path(__file__).resolve().parent                 # pilot2/
PACK = P2 / "prompt_pack"
RUNS = P2 / "runs"
sys.path.insert(0, str(P2.parent / "pilot"))
import run_pilot as RP  # noqa: E402  冻结 runner：唯一的调用/评分来源，不复制

MODEL = {"baseline_claude": "claude-opus-4-6", "baseline_qwen": "qwen3-coder-next",
         "baseline_deepseek": "deepseek-3.2", "baseline_minimax": "minimax-m2.5",
         "trivial_claude": "claude-opus-4-6", "trivial_v2": "claude-opus-4-6",
         "trivial_v3": "claude-opus-4-6", "governance_informed": "claude-opus-4-6"}
EXTRA = {"baseline_claude": "", "baseline_qwen": "", "baseline_deepseek": "",
         "baseline_minimax": "", "trivial_claude": RP.TRIVIAL_NOTE,
         "trivial_v2": RP.TRIVIAL_V2_NOTE, "trivial_v3": RP.TRIVIAL_V3_NOTE,
         "governance_informed": None}                        # None → V2_NOTE + <db>.gov.txt
EXPECT_CHANNEL = {"claude-opus-4-6": "tuzi", "qwen3-coder-next": "gateway",
                  "deepseek-3.2": "gateway", "minimax-m2.5": "gateway"}

# §4.2 金标形态分派（60 题逐题冻结，运行期不得改派）
ROWSET_QIDS = {"CA-Q5", "CODE-Q4", "DEB-Q5", "TH-Q3"}
STRING_QIDS = {"CODE-Q6", "TH-Q4"}


# ---------------------------------------------------------------- 装配
def domains() -> list[pathlib.Path]:
    return sorted(p for p in (P2 / "domains").iterdir()
                  if p.is_dir() and not p.name.startswith("._")
                  and (p / "questions.json").is_file())


def questions() -> list[tuple[dict, pathlib.Path]]:
    out = []
    for d in domains():
        for q in json.loads((d / "questions.json").read_text(encoding="utf-8")):
            out.append((q, d))
    return out


def build_prompt(arm: str, d: pathlib.Path, question_zh: str) -> str:
    """入参只有 (臂, 目录, 题干文本)——结构性地不可能读到金标侧字段。"""
    schema = (PACK / f"{d.name}.schema.txt").read_text(encoding="utf-8")
    extra = EXTRA[arm]
    if extra is None:
        extra = RP.TRIVIAL_V2_NOTE + (PACK / f"{d.name}.gov.txt").read_text(encoding="utf-8")
    return RP.PROMPT.format(schema=schema, extra=extra, question=question_zh)


# ---------------------------------------------------------------- §4.2 扩展评分
def _num(x):
    try:
        return float(str(x))
    except (TypeError, ValueError):
        return None


def _num_eq(got: float, gold: float) -> bool:
    if gold == 0:
        return abs(got) <= 1e-9
    return abs(got - gold) / abs(gold) <= RP.REL_TOL


def _cell_eq(got, gold) -> bool:
    fg, fd = _num(got), _num(gold)
    if fg is not None and fd is not None:
        return _num_eq(fg, fd)
    return str(got).strip() == str(gold).strip()


def _rowset_correct(gold_rows: list, rows: list) -> bool:
    # 宽赦条款：金标恰 1 行且恰 1 个数值格时，1×1 标量命中该数值亦判对
    if len(gold_rows) == 1:
        gnums = [c for c in gold_rows[0] if _num(c) is not None]
        if len(gnums) == 1 and len(rows) == 1 and len(rows[0]) == 1:
            g = _num(rows[0][0])
            if g is not None and _num_eq(g, _num(gnums[0])):
                return True
    if len(rows) != len(gold_rows):
        return False
    for perm in itertools.permutations(range(len(rows))):
        ok = True
        for gi, ri in enumerate(perm):
            g, r = gold_rows[gi], rows[ri]
            if len(g) != len(r) or not all(_cell_eq(a, b) for a, b in zip(r, g)):
                ok = False
                break
        if ok:
            return True
    return False


def _jsonable(rows):
    return [[c if isinstance(c, (int, float, str, bool)) or c is None else str(c)
             for c in r] for r in rows]


def fetch_and_score(q: dict, sql, db: str):
    """返回 (kind, value, verdict)。数值金标走 RP.run_sql/RP.score 原文；6 道扩展题按 §4.2。"""
    qid = q["qid"]
    if sql == "REFUSE":
        kind, value = "refuse", None
        if q["expected_kind"] == "refusal":
            return kind, value, "correct"
        return kind, value, "refused_should_answer"
    if not sql:
        kind = "no_sql"
        return kind, None, ("answered_should_refuse" if q["expected_kind"] == "refusal"
                            else "no_sql")
    if qid in ROWSET_QIDS:
        try:
            conn = duckdb.connect(db, read_only=True)
            try:
                rows = conn.execute(sql).fetchall()
            finally:
                conn.close()
        except Exception:
            rows = None
        if not rows:                                          # 取数异常/空行集 → error
            kind, value = "error", None
        else:
            kind, value = "value", _jsonable(rows)
        if q["expected_kind"] == "refusal":
            return kind, value, "answered_should_refuse"
        if kind == "error":
            return kind, value, "execution_error"
        return kind, value, ("correct" if _rowset_correct(q["gold_value"], rows)
                             else "wrong_value")
    if qid in STRING_QIDS:
        try:
            conn = duckdb.connect(db, read_only=True)
            try:
                rows = conn.execute(sql).fetchall()
            finally:
                conn.close()
        except Exception:
            rows = None
        if not rows or rows[0][0] is None:
            kind, value = "error", None
        else:
            v = rows[0][0]
            kind = "value"
            value = v if isinstance(v, (int, float, str, bool)) else str(v)
        if q["expected_kind"] == "refusal":
            return kind, value, "answered_should_refuse"
        if kind == "error":
            return kind, value, "execution_error"
        return kind, value, ("correct" if _cell_eq(value, q["gold_value"])
                             else "wrong_value")
    # 数值金标（39 题 + 全部 refusal 题的作答路径）：run_pilot 原文
    kind, value = "no_sql", None
    try:
        value = RP.run_sql(db, sql)
        kind = "value" if value is not None else "error"
    except Exception:
        kind = "error"
    return kind, value, RP.score(q, kind, value)


# ---------------------------------------------------------------- 跑前断言
def preflight(qs: list, arms_to_run: list[str]) -> None:
    man = json.loads((PACK / "MANIFEST.json").read_text(encoding="utf-8"))

    # A0 冻结哈希（132 文件 + 聚合）
    fz = json.loads((P2 / "FREEZE_pilot2_arms.json").read_text(encoding="utf-8"))
    bad = []
    for rel, want in fz["files"].items():
        p = (pathlib.Path(os.path.expanduser(rel)) if rel.startswith("~")
             else (P2 / rel).resolve())
        got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
        if got != want:
            bad.append(rel)
    assert not bad, f"A0 FAIL: {bad}"
    agg_files = sorted(str(x) for x in
                       list(P2.glob("domains/*/questions.json"))
                       + list(P2.glob("domains/*/gov_seed/*.jsonl"))
                       if "/._" not in str(x))
    h = hashlib.sha256()
    for f in agg_files:
        h.update(pathlib.Path(f).read_bytes())
    assert h.hexdigest() == fz["aggregate"]["sha256"], "A0 FAIL: aggregate"
    print(f"  A0  OK ({len(fz['files'])} files + aggregate {len(agg_files)} parts)")

    # A1 渠道解析（只断言本次要跑的臂涉及的模型）
    reg = json.loads(pathlib.Path(os.path.expanduser(
        "~/.claude/skills/llmhub/channels.json")).read_text())
    for arm in arms_to_run:
        mdl = MODEL[arm]
        homes = [c["name"] for c in reg["channels"] if mdl in c["models"]]
        assert homes and homes[0] == EXPECT_CHANNEL[mdl], f"A1 FAIL {mdl}: {homes}"
    print("  A1  OK (channel first-hit as frozen)")

    # A2 泄漏断言：最大超集提示（governance_informed 完整装配）× 7 金标侧字段
    skipped = []
    for q, d in qs:
        p = build_prompt("governance_informed", d, q["question_zh"])
        fields = {"gold_sql": q.get("gold_sql"),
                  "windows": None if q.get("windows") is None
                  else json.dumps(q["windows"], ensure_ascii=False),
                  "windows_note": q.get("windows_note"), "notes": q.get("notes"),
                  "rewrite": None if q.get("rewrite") is None
                  else json.dumps(q["rewrite"], ensure_ascii=False),
                  "refusal_reason": q.get("refusal_reason"),
                  "gold_value": None if q.get("gold_value") is None
                  else str(q["gold_value"])}
        for k, v in fields.items():
            if v is None:
                continue
            s = v.strip() if isinstance(v, str) else str(v)
            if len(s) < 8:
                skipped.append(f"{q['qid']}.{k}")
                continue
            assert s not in p, f"A2 FAIL: {q['qid']} leaks {k}"
    print(f"  A2  OK (60×7 比对；过短跳过 {len(skipped)} 项)")

    # A3 prompt_pack 逐字节重建校验（内存重建，不写盘）
    import importlib.util
    spec = importlib.util.spec_from_file_location("bpp", PACK / "build_prompt_pack.py")
    bpp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bpp)
    for d in domains():
        db = d.name
        sch = bpp.schema_pack(db, d)
        gov, _, _ = bpp.render_gov(db, bpp.gov_blocks(db, d))
        assert sch == (PACK / f"{db}.schema.txt").read_text(encoding="utf-8"), \
            f"A3 FAIL: {db}.schema.txt"
        assert gov == (PACK / f"{db}.gov.txt").read_text(encoding="utf-8"), \
            f"A3 FAIL: {db}.gov.txt"
        assert hashlib.sha256(sch.encode()).hexdigest() == \
            man["domains"][db]["schema_sha256"], f"A3 FAIL sha: {db}.schema"
        assert hashlib.sha256(gov.encode()).hexdigest() == \
            man["domains"][db]["gov_sha256"], f"A3 FAIL sha: {db}.gov"
    print("  A3  OK (18 packs rebuilt byte-identical, sha256 == MANIFEST)")

    # A4 逐臂提示总长与逐库 min–max == MANIFEST（8 臂全查，装配即本运行器的 build_prompt）
    for arm in MODEL:
        total, rng = 0, {}
        for d in domains():
            lens = [len(build_prompt(arm, d, q["question_zh"]))
                    for q, dd in qs if dd == d]
            rng[d.name] = [min(lens), max(lens)]
            total += sum(lens)
        assert total == man["prompt_totals"][arm], \
            f"A4 FAIL {arm}: total={total} vs {man['prompt_totals'][arm]}"
        assert rng == man["prompt_len_range"][arm], f"A4 FAIL {arm}: ranges"
    print(f"  A4  OK (8 arms totals: {man['prompt_totals']})")

    # A7 题集结构
    assert len(qs) == 60 and len({q['qid'] for q, _ in qs}) == 60, "A7 FAIL: n/dup"
    ek = {}
    rr = {}
    for q, _ in qs:
        ek[q["expected_kind"]] = ek.get(q["expected_kind"], 0) + 1
        if q["expected_kind"] == "refusal":
            rr[q["refusal_reason"]] = rr.get(q["refusal_reason"], 0) + 1
    assert ek == {"value": 33, "rewrite": 12, "refusal": 15}, f"A7 FAIL: {ek}"
    assert sorted(rr.values(), reverse=True) == [5, 4, 3, 3], f"A7 FAIL: {rr}"
    assert len(domains()) == 9, "A7 FAIL: dirs"
    print(f"  A7  OK (60 题; {ek}; refusal_reasons {rr})")


# ---------------------------------------------------------------- 单题（缓存只写不删）
def eval_one(arm: str, q: dict, d: pathlib.Path, stats: dict) -> dict:
    cache = RUNS / arm / f"{q['qid']}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    db = str(d / "warehouse.duckdb")
    if cache.is_file():                                       # 终局，不再调用
        rec = json.loads(cache.read_text(encoding="utf-8"))
        raw = rec.get("raw") or ""
        sql = RP.extract_sql(raw)
        if len(raw) >= RP.RAW_CAP and sql != "REFUSE" and rec.get("sql"):
            sql = rec["sql"]
        kind, value, verdict = fetch_and_score(q, sql, db)
        out = dict(rec)
        out.update(kind=kind, value=value, verdict=verdict, sql=sql)
        stats["cached"] += 1
        return out
    prompt = build_prompt(arm, d, q["question_zh"])
    raw = RP.llm(MODEL[arm], prompt)                          # retries=2 → 最多 3 次尝试
    sql = RP.extract_sql(raw)
    kind, value, verdict = fetch_and_score(q, sql, db)
    rec = {"qid": q["qid"], "system": arm, "kind": kind, "value": value,
           "verdict": verdict, "raw": raw[:RP.RAW_CAP], "sql": sql,
           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
           "prompt_chars": len(prompt), "empty_response": raw == ""}
    cache.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    stats["calls"] += 1
    if raw == "":
        stats["empty"] += 1
    return rec


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    qs = questions()
    arms = args or list(MODEL)
    for a in arms:
        assert a in MODEL, f"unknown arm {a}"
    preflight(qs, arms)
    if dry:
        print("DRY RUN — 零 LLM 调用。")
        return 0

    report = {}
    for arm in arms:                                          # 臂间串行
        stats = {"calls": 0, "cached": 0, "empty": 0}
        with ThreadPoolExecutor(max_workers=4) as ex:         # 臂内 4 并发
            recs = list(ex.map(lambda qd: eval_one(arm, qd[0], qd[1], stats), qs))
        n_ok = sum(1 for r in recs if r["verdict"] == "correct")
        for r in recs:
            print(f"  {arm:20} {r['qid']:10} {r['verdict']}")
        report[arm] = {**stats, "errors": len(recs) - n_ok, "correct": n_ok,
                       "voided(empty>=3)": stats["empty"] >= 3}
        print(f"[{arm}] calls={stats['calls']} cached={stats['cached']} "
              f"empty={stats['empty']} correct={n_ok}/60 errors={len(recs)-n_ok}")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
