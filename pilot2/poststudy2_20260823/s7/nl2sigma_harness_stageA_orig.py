#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nl2sigma_harness.py — S7 NL→σ 臂（PREREG_poststudy2_20260823.md §S7 的执行体）。

prereg sha256: 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669

架构：question_zh --(claude-opus-4-6 抽取)--> σ --(冻结 Pilot2Adapter+MLR 编译器)-->
outcome (answer/rewrite/typed refusal) --(冻结 acceptance_pilot2 关1 规则)--> verdict。

纪律（逐条对应 prereg §S7 + 母任务）：
  * 臂路径纯净：`load_questions_arm()` 在装载时即把每题裁剪为
    {qid, domain, question_zh} 三键；抽取函数断言入参恰为这三键。
    金标侧字段（gold_sql/gold_value/expected_kind/refusal_*/rewrite/windows*/
    notes/metric）与全部 σ 字段（as_of/declared_at/metric_alias/scope/
    pinned_version/cross_window/anchor_override/window_request/
    requested_granularity/requested_time_gran/presentation/ctx_role/periods）
    对臂路径结构性不可见；审计对照读取走独立函数 `audit_load_full()`，只被
    评分/σ-准确率函数调用。
  * 抽取调用：claude-opus-4-6（llmhub，首中渠道断言 == tuzi），单样本，
    非法 JSON 恰一次格式重试（附纠错行），仍非法 → extraction_error（计 error）。
  * 编译桥：抽取 σ + {qid, domain} 组装为题面 dict，喂冻结
    impl/asof_compiler.compile_question（对 pilot2/domains 冻结仓 read_only）。
  * 评分（冻结规则）：acceptance_pilot2 关1 `_gold_match`（value 1e-9 相对误差 /
    refusal reason token+subtype 全等 / rewrite 决策+kind+值）。另记
    lenient_refusal_ok（拒答题不问 reason 的 LLM 臂口径）为附注，不改主判。
  * 缓存只写不删：s7/runs_nl2sigma/<qid>.json 一经写入即终局，断点续跑只补缺。
  * 全部产出 append-only 落 s7/；冻结证据零写入（duckdb read_only）。

用法：
  python3 nl2sigma_harness.py --dry            # 断言 + 提示装配，零 LLM 调用
  python3 nl2sigma_harness.py --smoke          # 3 题冒烟（CARD-Q1/FIN-Q8/FIN-Q6）
  python3 nl2sigma_harness.py                  # 全 60 题（Stage B；冒烟核准后）
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent          # .../poststudy2_20260823/s7
POST2 = HERE.parent
P2 = POST2.parent                                       # pilot2/
PACK = P2 / "prompt_pack"
IMPL = P2.parent / "impl"
RUNS = HERE / "runs_nl2sigma"
LLMHUB = pathlib.Path.home() / ".claude/skills/llmhub/bin/llmhub.py"
KEYS = pathlib.Path.home() / ".config/loctek_llm_keys.env"

PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"
MODEL = "claude-opus-4-6"
EXPECT_CHANNEL = "tuzi"
RAW_CAP = 4000
MAX_TOKENS = 1024
SMOKE_QIDS = ["CARD-Q1", "FIN-Q8", "FIN-Q6"]

sys.path.insert(0, str(IMPL))
from asof_compiler import compile_question  # noqa: E402  冻结编译器（只读 import）

# 冻结评分模块（acceptance_pilot2 关1；import 即复用，不复制）
_spec = importlib.util.spec_from_file_location(
    "acceptance_pilot2", IMPL / "asof_compiler" / "acceptance_pilot2.py")
AP2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AP2)

# ---------------------------------------------------------------------------
# (1) σ 格式规范：编译器实际消费的题面意图字段（adapters_pilot2.py 纪律行 +
#     certificate.py 落字面）。qid/domain 为题目身份，由 harness 提供，不抽取。
# ---------------------------------------------------------------------------
SIGMA_FIELDS = [
    "as_of", "declared_at", "metric_alias", "scope", "pinned_version",
    "cross_window", "anchor_override", "window_request",
    "requested_granularity", "requested_time_gran", "presentation",
    "ctx_role", "periods",
]

SIGMA_SCHEMA = {
    "$comment": "σ：结构化查询意图（Definition 2.3 投影到 pilot2 题面字段）。"
                "所有字段必须出现；题面未声明的字段取 null（scope 取 {}）。",
    "type": "object",
    "additionalProperties": False,
    "required": SIGMA_FIELDS,
    "properties": {
        "as_of": {"type": ["string", "null"],
                  "description": "有效时间时点 'YYYY-MM-DD'（题面 as-of；月窗题为窗内代表日，"
                                 "题面通常写作 as-of X 所在月/年窗）。未声明→null"},
        "declared_at": {"type": ["string", "null"],
                        "description": "声明时点（事务时间轴 T）'YYYY-MM-DD'，决定 ver(T)"},
        "metric_alias": {"type": ["string", "null"],
                         "description": "指标业务别名，逐字取 gov_metric_alias.alias_text "
                                        "登记面里与题面指标称谓一致的字符串"},
        "scope": {"type": "object",
                  "description": "范围过滤 {scope_key: value}，键取治理登记 scope_keys 的键名"
                                 "（如 currency/segment/driver/county/patient_id…）；"
                                 "数值型 id 用数字。无范围限定→{}"},
        "pinned_version": {"type": ["string", "null"],
                           "description": "题面显式钉定的治理图版本号（如 'v1'）；未钉→null"},
        "cross_window": {"type": ["object", "null"],
                         "description": "跨窗祈使：题面强令分子/分母各取不同月窗时 "
                                        "{'num':'YYYY-MM','den':'YYYY-MM'}；否则 null"},
        "anchor_override": {"type": ["string", "null"],
                            "description": "题面点名改用的时间锚（锚 id 或列名，逐字）；未点名→null"},
        "window_request": {
            "type": ["object", "null"],
            "description": "题面显式请求的时间窗（区间/周/月token区间），三形之一："
                           "{'kind':'day_range','lo':'YYYY-MM-DD','hi_excl':'YYYY-MM-DD'}"
                           "（闭始开端；题面『至 X』含端日时 hi_excl=X 次日）| "
                           "{'kind':'week','lo':'YYYY-MM-DD'}（lo 起 7 天）| "
                           "{'kind':'month_token_range','lo':'YYYY-MM','hi':'YYYY-MM'}"
                           "（月 token 闭区间）。题面只给 as-of 时点/月窗→null"},
        "requested_granularity": {"type": ["string", "null"],
                                  "description": "报表/名录题请求的实体粒度级名（逐字，如 "
                                                 "school/patient/user/Segment）；非报表题→null"},
        "requested_time_gran": {"type": ["string", "null"],
                                "description": "时间轴报表请求的时间粒度（如 'day'）；未请求→null"},
        "presentation": {"type": ["string", "null"],
                         "enum": ["aggregate", "raw_rows", "value", None],
                         "description": "呈现形态：聚合值→'aggregate'；要求逐行原值名录→"
                                        "'raw_rows'；单属性原值→'value'"},
        "ctx_role": {"type": ["string", "null"],
                     "description": "提问者角色语境；本题集一律 'external_analyst'"},
        "periods": {"type": ["array", "null"], "items": {"type": "string"},
                    "description": "双期差值题的两个期标签（如年份 ['2009','2010']，"
                                   "先前期后后期）；非差值题→null"},
    },
}

# 已解析示例：虚构题面（断言不属于 60 题），演示字段落法
SIGMA_EXAMPLE_QUESTION = ("以 1998-01-10 为声明时点，按 v1 版口径计算捷克克朗（CZK）账户"
                          "1997 年 11 月（as-of 1997-11-20 所在月窗）的当月交易笔数。")
SIGMA_EXAMPLE = {
    "as_of": "1997-11-20", "declared_at": "1998-01-10",
    "metric_alias": "当月交易笔数", "scope": {"currency": "CZK"},
    "pinned_version": "v1", "cross_window": None, "anchor_override": None,
    "window_request": None, "requested_granularity": None,
    "requested_time_gran": None, "presentation": "aggregate",
    "ctx_role": "external_analyst", "periods": None,
}

PROMPT = """你是一个结构化查询意图抽取器。给定 DuckDB 数据库 schema、治理元数据（gov_* 登记表全量）与一个中文分析问题，把问题解析为一个结构化意图对象 σ。**输出且仅输出一个合法 JSON 对象**（不要 markdown 围栏、不要解释文字）。σ 将被喂给一个确定性的绑定编译器，由它决定作答/改写/拒答——你只负责忠实抽取题面声明的意图，不判断可答性，不计算任何数值。

## Schema（含行数注记）
{schema}

## 治理元数据
{gov}

## σ 格式规范（JSON Schema）
{sigma_schema}

## 已解析示例（示例题，非本题）
问题：{example_q}
σ：{example_sigma}

## 问题
{question}

σ JSON:"""

RETRY_SUFFIX = "\n\n（上一次输出不是合法 JSON。请重新输出：且仅输出一个符合上述规范的合法 JSON 对象，无任何其他文字。）"


# ---------------------------------------------------------------------------
# 装载：臂路径（三键裁剪）与审计路径（全量）严格分离
# ---------------------------------------------------------------------------
ARM_KEYS = ("qid", "domain", "question_zh")


def _domains():
    return sorted(p for p in (P2 / "domains").iterdir()
                  if p.is_dir() and not p.name.startswith("._")
                  and (p / "questions.json").is_file())


def load_questions_arm() -> list:
    """臂路径唯一装载器：装载即裁剪为 {qid, domain, question_zh}。"""
    out = []
    for d in _domains():
        for q in json.loads((d / "questions.json").read_text(encoding="utf-8")):
            out.append({k: q[k] for k in ARM_KEYS})
    return out


def audit_load_full() -> dict:
    """审计路径装载器（金标 + 冻结 σ）：只允许评分/σ-准确率/预检断言调用。"""
    out = {}
    for d in _domains():
        for q in json.loads((d / "questions.json").read_text(encoding="utf-8")):
            out[q["qid"]] = (q, d)
    return out


# ---------------------------------------------------------------------------
# 抽取（LLM）
# ---------------------------------------------------------------------------
def build_prompt(arm_q: dict) -> str:
    """入参必须是三键裁剪题面——结构性地不可能读到金标/σ 字段。"""
    assert set(arm_q.keys()) == set(ARM_KEYS), f"arm purity violated: {set(arm_q)}"
    schema = (PACK / f"{arm_q['domain']}.schema.txt").read_text(encoding="utf-8")
    gov = (PACK / f"{arm_q['domain']}.gov.txt").read_text(encoding="utf-8")
    return PROMPT.format(
        schema=schema, gov=gov,
        sigma_schema=json.dumps(SIGMA_SCHEMA, ensure_ascii=False, indent=1),
        example_q=SIGMA_EXAMPLE_QUESTION,
        example_sigma=json.dumps(SIGMA_EXAMPLE, ensure_ascii=False),
        question=arm_q["question_zh"])


def _env() -> dict:
    env = dict(os.environ)
    if KEYS.is_file():
        for line in KEYS.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.replace("export ", "").strip()] = v.strip().strip('"')
    return env


def llm_once(prompt: str) -> str:
    p = subprocess.run(
        ["python3", str(LLMHUB), "chat", "--model", MODEL,
         "--max-tokens", str(MAX_TOKENS), "--prompt", prompt],
        capture_output=True, text=True, timeout=240, env=_env())
    out = p.stdout.strip()
    lines = [l for l in out.splitlines() if not re.match(r"^\[.*\]$", l.strip())]
    return "\n".join(lines).strip()


def parse_sigma(text: str):
    """剥围栏后取首个 '{' 到末个 '}' 的子串尝试解析；须为 object。失败 → None。"""
    if not text:
        return None
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S | re.I)
    if m:
        t = m.group(1).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        obj = json.loads(t[i:j + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def extract_one(arm_q: dict, stats: dict) -> dict:
    """单题抽取（缓存只写不删；单样本 + 恰一次格式重试）。"""
    cache = RUNS / f"{arm_q['qid']}.json"
    if cache.is_file():
        stats["cached"] += 1
        return json.loads(cache.read_text(encoding="utf-8"))
    prompt = build_prompt(arm_q)
    raws, sigma = [], None
    budget_hit = False
    for attempt in range(2):                      # 1 样本 + 1 格式重试
        if stats.get("budget") is not None and stats["calls"] >= stats["budget"]:
            budget_hit = True                     # 硬预算：宁记 error 不超付费上限
            break
        raw = llm_once(prompt if attempt == 0 else prompt + RETRY_SUFFIX)
        raws.append(raw)
        stats["calls"] += 1
        sigma = parse_sigma(raw)
        if sigma is not None:
            break
    if budget_hit and not raws:
        raise SystemExit(f"call budget {stats['budget']} exhausted before "
                         f"{arm_q['qid']} — stop, no cache written")
    rec = {"qid": arm_q["qid"], "domain": arm_q["domain"], "system": "nl2sigma",
           "model": MODEL, "sigma": sigma,
           "extraction_error": sigma is None,
           "attempts": len(raws),
           "raw": [r[:RAW_CAP] for r in raws],
           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
           "prompt_chars": len(prompt)}
    cache.write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    return rec


# ---------------------------------------------------------------------------
# 桥：σ → 冻结编译器 → outcome
# ---------------------------------------------------------------------------
def sigma_to_question(qid: str, domain: str, sigma: dict) -> dict:
    """抽取 σ + 题目身份 → 编译器题面 dict。字段全部来自模型输出（缺失补 null；
    scope 规范化为 dict；periods 元素规范化为 str）——绝不从 questions.json 取。"""
    q = {"qid": qid, "domain": domain}
    for f in SIGMA_FIELDS:
        v = sigma.get(f)
        if f == "scope":
            v = v if isinstance(v, dict) else {}
        if f == "periods" and isinstance(v, list):
            v = [str(x) for x in v]
        q[f] = v
    return q


def compile_sigma(q_sigma: dict):
    d = P2 / "domains" / q_sigma["domain"]
    try:
        env = compile_question(q_sigma, d)
        return env, None
    except Exception as e:  # noqa: BLE001  σ 畸形导致的装配期异常 → compile_error
        return None, f"{type(e).__name__}: {e}"


def outcome_of(env) -> dict:
    if env is None:
        return {"kind": "compile_error"}
    cert = env["certificate"]
    if "refusal" in env:
        r = cert.get("refusal") or {}
        return {"kind": "refusal", "reason": env["refusal"],
                "subtype": AP2._subtype_of(cert)}
    dec = cert["disclosure"]["decision"]
    return {"kind": "rewrite" if dec == "REWRITE" else "answer",
            "decision": dec,
            "rewrite_kinds": sorted(AP2._rewrite_kind(cert)) if dec == "REWRITE" else []}


# ---------------------------------------------------------------------------
# 审计：评分（冻结关1规则）与逐字段 σ-准确率（只在此处读金标/冻结 σ）
# ---------------------------------------------------------------------------
def _canon(v, field=None):
    if field == "scope" and (v is None or v == {}):
        return {}
    if field == "periods" and isinstance(v, list):
        v = [str(x) for x in v]
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        return {k: _canon(x) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return [_canon(x) for x in v]
    return v


def audit_sigma_accuracy(q_full: dict, sigma: dict) -> dict:
    """逐字段与冻结 σ 对照（审计函数：唯一允许读 questions.json σ 字段之处）。"""
    per = {}
    for f in SIGMA_FIELDS:
        got = _canon((sigma or {}).get(f), f)
        want = _canon(q_full.get(f), f)
        per[f] = {"match": got == want, "got": got, "gold": want}
    return {"fields": per, "exact_full_sigma": all(x["match"] for x in per.values())}


def audit_score(q_full: dict, env, cert, db: str, outc: dict):
    """冻结关1规则主判 + lenient 附注。"""
    if env is None:
        strict_ok, why = False, "compile_error"
    else:
        strict_ok, why = AP2._gold_match(q_full, env, cert, db)
    lenient_refusal_ok = (q_full["expected_kind"] == "refusal"
                          and outc["kind"] == "refusal")
    return {"verdict": "correct" if strict_ok else "error",
            "why": why, "lenient_refusal_ok": lenient_refusal_ok,
            "expected_kind": q_full["expected_kind"]}


# ---------------------------------------------------------------------------
# 预检（零调用）
# ---------------------------------------------------------------------------
# 与冻结 A2 同字段族（金标侧值字段；metric_id/expected_kind 等登记面/枚举 token
# 本就出现在与具体问题无关的共享 pack/规范里，不构成泄漏，A2 亦未列入）
GOLD_SIDE = ("gold_sql", "gold_value", "refusal_reason", "refusal_subtype",
             "rewrite", "windows", "windows_note", "notes")


def preflight(arm_qs: list) -> None:
    got = hashlib.sha256(
        (POST2 / "PREREG_poststudy2_20260823.md").read_bytes()).hexdigest()
    assert got == PREREG_SHA, f"P0 FAIL prereg sha: {got}"
    print(f"  P0 OK prereg sha256 == {PREREG_SHA[:16]}…")

    reg = json.loads(pathlib.Path(os.path.expanduser(
        "~/.claude/skills/llmhub/channels.json")).read_text())
    homes = [c["name"] for c in reg["channels"] if MODEL in c["models"]]
    assert homes and homes[0] == EXPECT_CHANNEL, f"P1 FAIL channel: {homes}"
    print(f"  P1 OK channel first-hit {MODEL} -> {homes[0]}")

    assert len(arm_qs) == 60 and len({q["qid"] for q in arm_qs}) == 60, "P2 FAIL n"
    assert all(set(q.keys()) == set(ARM_KEYS) for q in arm_qs), "P2 FAIL keys"
    texts = {q["question_zh"] for q in arm_qs}
    assert SIGMA_EXAMPLE_QUESTION not in texts, "P2 FAIL example ∈ 60 题"
    print("  P2 OK 60 题三键裁剪；σ 示例题不属于 60 题")

    # P3 泄漏断言（审计装载）：金标侧字段值不得出现在任何抽取提示里
    full = audit_load_full()
    skipped = 0
    for q in arm_qs:
        p = build_prompt(q)
        qf, _ = full[q["qid"]]
        for k in GOLD_SIDE:
            v = qf.get(k)
            if v is None:
                continue
            s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            s = s.strip()
            if len(s) < 8:
                skipped += 1
                continue
            assert s not in p, f"P3 FAIL: {q['qid']} leaks {k}"
    print(f"  P3 OK 60×{len(GOLD_SIDE)} 泄漏比对（过短跳过 {skipped}）")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run(qids, out_name: str, budget=None) -> dict:
    arm_qs = load_questions_arm()
    preflight(arm_qs)
    todo = [q for q in arm_qs if qids is None or q["qid"] in qids]
    stats = {"calls": 0, "cached": 0, "budget": budget}
    ledger = []
    full = None                                  # 审计装载延迟到评分时
    for aq in todo:
        rec = extract_one(aq, stats)
        sigma = rec.get("sigma")
        if sigma is None:
            env, cerr = None, "extraction_error"
            q_sigma = None
        else:
            q_sigma = sigma_to_question(aq["qid"], aq["domain"], sigma)
            env, cerr = compile_sigma(q_sigma)
        outc = outcome_of(env)
        if cerr:
            outc["error"] = cerr
        if full is None:
            full = audit_load_full()             # ---- 以下为审计侧 ----
        qf, d = full[aq["qid"]]
        db = str(d / "warehouse.duckdb")
        cert = env["certificate"] if env else None
        score = audit_score(qf, env, cert, db, outc)
        acc = audit_sigma_accuracy(qf, sigma or {})
        row = {"qid": aq["qid"], "domain": aq["domain"],
               "extraction_error": rec["extraction_error"],
               "attempts": rec["attempts"],
               "sigma_extracted": sigma, "outcome": outc, "score": score,
               "sigma_accuracy": {
                   "exact_full_sigma": acc["exact_full_sigma"],
                   "field_match": {f: acc["fields"][f]["match"]
                                   for f in SIGMA_FIELDS},
                   "mismatches": {f: {"got": acc["fields"][f]["got"],
                                      "gold": acc["fields"][f]["gold"]}
                                  for f in SIGMA_FIELDS
                                  if not acc["fields"][f]["match"]}}}
        ledger.append(row)
        print(f"  {row['qid']:10} outcome={outc['kind']:13} "
              f"verdict={score['verdict']:7} exact_sigma={acc['exact_full_sigma']}"
              f"{'  why=' + score['why'] if score['why'] else ''}")

    n = len(ledger)
    summary = {
        "prereg_sha256": PREREG_SHA, "model": MODEL, "n": n,
        "calls": stats["calls"], "cached": stats["cached"],
        "exact_full_sigma": sum(r["sigma_accuracy"]["exact_full_sigma"]
                                for r in ledger),
        "end_to_end_correct": sum(r["score"]["verdict"] == "correct"
                                  for r in ledger),
        "end_to_end_error": sum(r["score"]["verdict"] != "correct"
                                for r in ledger),
        "metric_alias_match": sum(
            r["sigma_accuracy"]["field_match"]["metric_alias"] for r in ledger),
        "per_field_match": {f: sum(r["sigma_accuracy"]["field_match"][f]
                                   for r in ledger) for f in SIGMA_FIELDS},
        "exact_sigma_and_wrong": [
            r["qid"] for r in ledger
            if r["sigma_accuracy"]["exact_full_sigma"]
            and r["score"]["verdict"] != "correct"],       # S7-P3 见证（应为空）
        "ledger": ledger,
    }
    out = HERE / out_name
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1,
                              default=str), encoding="utf-8")
    print(f"\nwrote {out}")
    print(json.dumps({k: v for k, v in summary.items() if k != "ledger"},
                     ensure_ascii=False, indent=1))
    return summary


def main() -> int:
    dry = "--dry" in sys.argv
    smoke = "--smoke" in sys.argv
    if dry:
        arm_qs = load_questions_arm()
        preflight(arm_qs)
        lens = [len(build_prompt(q)) for q in arm_qs]
        print(f"DRY RUN — 零调用。60 题提示长度 min={min(lens)} max={max(lens)}")
        return 0
    if smoke:
        run(set(SMOKE_QIDS), "smoke_nl2sigma.json", budget=3)
        return 0
    run(None, "s7_nl2sigma_full.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
