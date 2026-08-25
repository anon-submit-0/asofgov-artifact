#!/usr/bin/env python3
"""OPP-ASOF-GOV · B-gate pilot runner (pre-registered, frozen 2026-07-31 01:2x
BEFORE any result was observed).

Systems
-------
  baseline_claude   claude-opus-4-6 (tuzi, identity-verified)  — plain NL2SQL
  baseline_qwen     qwen3-coder-next (gateway, open-source SOTA family) — plain
  trivial_claude    claude-opus-4-6 + one-line version/anchor note (平凡基线)
  mechanism         deterministic temporal-binding compiler (per-dir compiler.py)

Pre-registered criteria (spec 02_投稿准备计划 §三; ambiguity resolutions frozen
here, pre-hoc):
  A  (frontier fails)   PASS iff min(error_rate of the two PLAIN baselines) >= 0.30
  B/C                    reference baseline := baseline_claude (plain)
                         PASS iff mechanism eliminates >= 0.80 of reference's
                         temporal errors AND trivial_claude eliminates < 0.40
  Deviations log         gateway claude-opus-4.8 unavailable tonight (HTTP 400
                         invalid model, probed 01:1x) -> substituted by
                         claude-opus-4-6; "GPT-5.x" leg dropped (tuzi gpt-5.5
                         not identity-verified); open-source leg = qwen3-coder-next.

Scoring
-------
  value   correct iff relative error <= 0.5% (or absolute <= 1e-9 when gold==0)
  refusal correct iff the system output starts with REFUSE (reason match not
          required for LLM systems; required for mechanism)
  taxonomy: correct | wrong_value | execution_error | answered_should_refuse |
            refused_should_answer | no_sql

All systems receive the SAME instruction, including the refusal affordance —
plain baselines are not denied the option to refuse (fairness).
Responses cached under runs/<system>/<qid>.json for resume.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent
RUNS = ROOT / "runs"
LLMHUB = pathlib.Path.home() / ".claude/skills/llmhub/bin/llmhub.py"
KEYS = pathlib.Path.home() / ".config/loctek_llm_keys.env"

SYSTEMS = ["baseline_claude", "baseline_qwen", "trivial_claude", "mechanism"]
# --- v2 expansion (2026-07-31, post-gate; for paper claims C1/C2, NOT re-gating:
#     the pre-registered A/B/C adjudication above stays computed on the original
#     four systems. Protocol addendum frozen before any v2 result was observed:
#     C1 breadth = two more model families (deepseek-3.2 gateway, kimi-k2.6 moonshot 欠费停用, 2026-07-31 12:0x 替换为 minimax-m2.5 gateway); C2 ablation = two more prompt variants of the trivial baseline
#     (v2 explicit-join guidance, v3 one generic worked example); bootstrap =
#     cluster bootstrap over the 6 source clusters (5 domains + public), B=2000,
#     seed=20260731; coverage reported alongside every conditional rate. ---
SYSTEMS_V2 = ["baseline_deepseek", "baseline_minimax", "trivial_v2", "trivial_v3"]
MODEL = {"baseline_claude": "claude-opus-4-6", "baseline_qwen": "qwen3-coder-next",
         "trivial_claude": "claude-opus-4-6",
         "baseline_deepseek": "deepseek-3.2", "baseline_minimax": "minimax-m2.5",
         "trivial_v2": "claude-opus-4-6", "trivial_v3": "claude-opus-4-6"}
REL_TOL = 0.005
RAW_CAP = 2000  # chars of the model response persisted in runs/<system>/<qid>.json

TRIVIAL_V2_NOTE = ("\n## 注意\n本库为版本化治理仓：gov_valid_time_anchor 表给出每个语义对象的"
                   "有效时间锚（effective_date/valid_from/valid_to），gov_temporal_binding 表给出"
                   "指标分子分母必须同 valid-time 窗对齐等绑定规则。回答问题时：先在锚表中查到"
                   "涉及指标的锚，再依绑定规则把 as-of 时点落到正确的窗口/版本快照上，"
                   "分子分母窗口必须一致；若同窗数据不存在应输出 REFUSE。\n")
TRIVIAL_V3_NOTE = ("\n## 示例（通用，非本库）\n问题：截至 2026-03，某指标 rate=分子/分母。"
                   "正确做法：SELECT SUM(num)/SUM(den) FROM fact WHERE strftime('%Y-%m', dt)='2026-03'"
                   "——分子分母都取 2026-03 同窗；错误做法：分子取 3 月、分母取全期或最新快照。"
                   "请对本题按同样纪律处理 as-of 时点。\n")

PROMPT = """你是一个 text-to-SQL 系统。给定 DuckDB 数据库 schema 与一个中文分析问题，输出**且仅输出**一条可执行的 DuckDB SQL（单值结果）。
如果你判断该问题在给定数据下无法被正确回答，输出且仅输出一行：REFUSE: <简短原因>。
不要输出解释、markdown 围栏之外的任何文字。

## Schema（含行数注记）
{schema}
{extra}
## 问题
{question}

SQL:"""

TRIVIAL_NOTE = ("\n## 注意\n数据库中存在版本化快照与有效时间锚表"
                "（gov_valid_time_anchor / gov_temporal_binding）。"
                "问题中声明的 as-of 时点必须被尊重：请依据锚表选择该时点有效的"
                "版本/窗口作答。\n")


def _env() -> dict:
    import os
    env = dict(os.environ)
    if KEYS.is_file():
        for line in KEYS.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.replace("export ", "").strip()] = v.strip().strip('"')
    return env


def llm(model: str, prompt: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        try:
            p = subprocess.run(
                ["python3", str(LLMHUB), "chat", "--model", model, "--prompt", prompt],
                capture_output=True, text=True, timeout=180, env=_env())
            out = p.stdout.strip()
            # llmhub prefixes a "[model | prompt=..]" line — drop bracketed header lines
            lines = [l for l in out.splitlines() if not re.match(r"^\[.*\]$", l.strip())]
            text = "\n".join(lines).strip()
            if text:
                return text
        except subprocess.TimeoutExpired:
            pass
    return ""


# --- refusal detection (fixed 2026-08-03) -----------------------------------
# BUG (pre-fix): the REFUSE test ran on the *un-stripped* text, so a refusal that
# the model wrapped in a ```sql fence ("```sql\nREFUSE: ...\n```") fell through to
# the SQL path, was executed, raised, and was scored `execution_error` — i.e. an
# abstention was silently recorded as an attempted answer. 12 of the 408 cached
# responses were masked this way. Fix: strip fences FIRST, then test, and tolerate
# the common surface variants (leading prose, markdown bullets/quotes, ASCII or
# full-width colon, arbitrary case, unterminated fence).
_FENCE_RE = re.compile(r"```[ \t]*[A-Za-z0-9_+.-]*[ \t]*\r?\n?(.*?)(?:```|\Z)", re.S)
_REFUSE_RE = re.compile(r"^REFUSE\s*[:：]?", re.I)
_SQL_HEAD_RE = re.compile(r"^(?:WITH|SELECT|\()", re.I)
_DECOR = ">*_`#-•· \t"
_PROSE_LOOKAHEAD = 6  # non-empty lines of preamble tolerated before a REFUSE line


def _refusal_bodies(t: str):
    """The raw text plus the content of every fenced block (fence stripped)."""
    yield t
    for m in _FENCE_RE.finditer(t):
        body = m.group(1).strip()
        if body:
            yield body


def is_refusal(text: str) -> bool:
    for body in _refusal_bodies(text):
        seen = 0
        for line in body.splitlines():
            s = line.strip().lstrip(_DECOR).strip()
            if not s:
                continue
            if _REFUSE_RE.match(s):
                return True
            if _SQL_HEAD_RE.match(s):
                break            # SQL starts here -> this block is an answer
            seen += 1
            if seen >= _PROSE_LOOKAHEAD:
                break            # too much preamble; treat as an answer attempt
    return False


def extract_sql(text: str) -> str | None:
    if not text:
        return None
    t = text.strip()
    if is_refusal(t):
        return "REFUSE"
    m = re.search(r"```(?:sql)?\s*(.+?)```", t, re.S | re.I)
    if m:
        t = m.group(1).strip()
    # keep first statement only
    t = t.split(";")[0].strip()
    return t or None


def run_sql(db_path: str, sql: str):
    conn = duckdb.connect(db_path, read_only=True)
    try:
        rows = conn.execute(sql).fetchall()
        if not rows or rows[0][0] is None:
            return None
        return float(rows[0][0])
    finally:
        conn.close()


def load_compiler(dir_: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"compiler_{dir_.name}", dir_ / "compiler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def score(q: dict, kind: str, value) -> str:
    if q["expected_kind"] == "refusal":
        return "correct" if kind == "refuse" else "answered_should_refuse"
    # value question
    if kind == "refuse":
        return "refused_should_answer"
    if kind == "error":
        return "execution_error"
    if kind == "no_sql":
        return "no_sql"
    gold = float(q["gold_value"])
    if gold == 0:
        return "correct" if abs(value) <= 1e-9 else "wrong_value"
    return "correct" if abs(value - gold) / abs(gold) <= REL_TOL else "wrong_value"


def rescore_cached(rec: dict, q: dict, dir_: pathlib.Path) -> dict:
    """Re-derive kind/value/verdict from the CACHED raw response. No LLM call.

    Scoring is a pure function of the stored raw text, so a scorer fix must never
    require re-querying a model. `mechanism` is returned untouched: its branch in
    eval_one() never calls extract_sql(), so the refusal-detection bug cannot
    reach it, and its cached record also carries the reason-match adjudication
    that is not recoverable from the raw string alone.
    """
    if rec.get("system") == "mechanism":
        return rec
    raw = rec.get("raw") or ""
    sql = extract_sql(raw)
    if len(raw) >= RAW_CAP and sql != "REFUSE" and rec.get("sql"):
        # raw was capped at write time; the cached sql was extracted from the
        # full response, so it is the more faithful artifact here.
        sql = rec["sql"]
    kind, value = "no_sql", None
    if sql == "REFUSE":
        kind = "refuse"
    elif sql:
        try:
            value = run_sql(str(dir_ / "warehouse.duckdb"), sql)
            kind = "value" if value is not None else "error"
        except Exception:
            kind = "error"
    out = dict(rec)
    out.update(kind=kind, value=value, verdict=score(q, kind, value), sql=sql)
    return out


def eval_one(system: str, q: dict, dir_: pathlib.Path) -> dict:
    cache = RUNS / system / f"{q['qid']}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.is_file():
        return rescore_cached(json.loads(cache.read_text()), q, dir_)
    db = str(dir_ / "warehouse.duckdb")
    raw, sql, kind, value = "", None, "no_sql", None
    if system == "mechanism":
        comp = load_compiler(dir_)
        out = comp.compile_question(q)
        if "refusal" in out:
            kind, raw = "refuse", f"REFUSE: {out['refusal']}"
            # mechanism must match the expected reason on refusal questions
            if q["expected_kind"] == "refusal" and q.get("refusal_reason") and \
               q["refusal_reason"] not in out["refusal"]:
                kind = "error"
        else:
            sql = out["sql"]
            raw = sql
            try:
                value = run_sql(db, sql)
                kind = "value" if value is not None else "error"
            except Exception:
                kind = "error"
    else:
        schema = (dir_ / "schema.txt").read_text()
        extra = {"trivial_claude": TRIVIAL_NOTE, "trivial_v2": TRIVIAL_V2_NOTE,
                 "trivial_v3": TRIVIAL_V3_NOTE}.get(system, "")
        raw = llm(MODEL[system], PROMPT.format(schema=schema, extra=extra,
                                               question=q["question_zh"]))
        sql = extract_sql(raw)
        if sql == "REFUSE":
            kind = "refuse"
        elif sql:
            try:
                value = run_sql(db, sql)
                kind = "value" if value is not None else "error"
            except Exception:
                kind = "error"
    rec = {"qid": q["qid"], "system": system, "kind": kind, "value": value,
           "verdict": score(q, kind, value), "raw": raw[:RAW_CAP], "sql": sql}
    cache.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


def main() -> int:
    from concurrent.futures import ThreadPoolExecutor

    want = sys.argv[1] if len(sys.argv) > 1 else "all"
    systems = SYSTEMS if want == "all" else (SYSTEMS_V2 if want == "v2" else [want])

    dirs = sorted([p for p in (ROOT / "domains").iterdir() if (p / "questions.json").is_file()]) \
        + ([ROOT / "public"] if (ROOT / "public/questions.json").is_file() else [])
    questions = []
    for d in dirs:
        for q in json.loads((d / "questions.json").read_text()):
            questions.append((q, d))
    print(f"loaded {len(questions)} questions from {len(dirs)} dirs; systems={systems}")

    results = {s: [] for s in systems}
    for system in systems:
        # LLM systems parallelized (4-way); mechanism is local and fast
        workers = 1 if system == "mechanism" else 4
        with ThreadPoolExecutor(max_workers=workers) as ex:
            recs = list(ex.map(lambda qd: eval_one(system, qd[0], qd[1]), questions))
        results[system] = recs
        for rec in recs:
            print(f"  {system:16} {rec['qid']:22} {rec['verdict']}")

    if want != "all":
        ok = sum(1 for r in results[want] if r["verdict"] == "correct")
        print(f"{want}: {ok}/{len(questions)} correct")
        return 0

    # ---- pre-registered metrics ----
    def err_rate(recs):
        return sum(1 for r in recs if r["verdict"] != "correct") / len(recs)

    m = {s: err_rate(results[s]) for s in SYSTEMS}
    ref = {r["qid"]: r for r in results["baseline_claude"]}
    ref_err_qids = [qid for qid, r in ref.items() if r["verdict"] != "correct"]

    def eliminated(system):
        recs = {r["qid"]: r for r in results[system]}
        fixed = sum(1 for qid in ref_err_qids if recs[qid]["verdict"] == "correct")
        return fixed / len(ref_err_qids) if ref_err_qids else 0.0

    A_pass = min(m["baseline_claude"], m["baseline_qwen"]) >= 0.30
    elim_mech, elim_triv = eliminated("mechanism"), eliminated("trivial_claude")
    B_pass = elim_mech >= 0.80
    C_pass = elim_triv < 0.40

    # v2 systems: include if fully cached (post-gate expansion; never re-gates)
    for s in SYSTEMS_V2:
        cache_dir = RUNS / s
        if cache_dir.is_dir() and len(list(cache_dir.glob("*.json"))) >= len(questions):
            recs = [rescore_cached(json.loads((cache_dir / f"{q['qid']}.json").read_text()), q, d)
                    for q, d in questions]
            results[s] = recs
            m[s] = err_rate(recs)

    # cluster bootstrap (6 source clusters, B=2000, seed frozen 20260731) + coverage
    import random
    clusters = {}
    for q, d in questions:
        clusters.setdefault(d.name, []).append(q["qid"])
    cluster_names = sorted(clusters)
    rng = random.Random(20260731)
    boot, coverage = {}, {}
    for s, recs in results.items():
        by_qid = {r["qid"]: r for r in recs}
        rates = []
        for _ in range(2000):
            picked = [rng.choice(cluster_names) for _ in cluster_names]
            qids = [qid for c in picked for qid in clusters[c]]
            rates.append(sum(1 for qid in qids if by_qid[qid]["verdict"] != "correct") / len(qids))
        rates.sort()
        boot[s] = {"err": m[s], "ci95": [rates[49], rates[1949]], "B": 2000,
                   "cluster_unit": "source (5 domains + public)"}
        n_ans = sum(1 for r in recs if r["kind"] in ("value", "error"))
        coverage[s] = {"answered": n_ans / len(recs),
                       "refused": sum(1 for r in recs if r["kind"] == "refuse") / len(recs)}

    # refusal sub-slice: the questions whose gold behaviour is an abstention
    refusal_qids = [q["qid"] for q, _ in questions if q["expected_kind"] == "refusal"]
    value_qids = [q["qid"] for q, _ in questions if q["expected_kind"] != "refusal"]
    refusal_stats = {}
    for s, recs in results.items():
        by_qid = {r["qid"]: r for r in recs}
        refusal_stats[s] = {
            "correct_refusals": sum(1 for qid in refusal_qids
                                    if by_qid[qid]["verdict"] == "correct"),
            "n_refusal_questions": len(refusal_qids),
            "over_refusals_on_value_questions": sum(
                1 for qid in value_qids if by_qid[qid]["verdict"] == "refused_should_answer"),
            "n_value_questions": len(value_qids),
        }

    summary = {
        "n_questions": len(questions),
        "error_rate": m,
        "cluster_bootstrap": boot,
        "coverage": coverage,
        "reference_baseline": "baseline_claude",
        "reference_errors": len(ref_err_qids),
        "eliminated_by_mechanism": elim_mech,
        "eliminated_by_trivial": elim_triv,
        "A_pass(min plain-baseline err>=0.30)": A_pass,
        "B_pass(mech eliminates>=0.80)": B_pass,
        "C_pass(trivial eliminates<0.40)": C_pass,
        "refusal_stats": refusal_stats,
        "taxonomy": {s: {v: sum(1 for r in recs if r["verdict"] == v)
                         for v in ("correct", "wrong_value", "execution_error",
                                   "answered_should_refuse", "refused_should_answer", "no_sql")
                         if sum(1 for r in recs if r["verdict"] == v)}
                     for s, recs in results.items()},
        "scorer": {"refusal_detection": "fence-stripped, variant-tolerant (fixed 2026-08-03)",
                   "rescored_from": "cached raw responses in runs/ — no new LLM calls"},
    }
    (ROOT / "pilot_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
