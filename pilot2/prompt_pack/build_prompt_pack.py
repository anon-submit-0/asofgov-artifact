#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pilot2 · LLM 臂提示物料打包器（PREREG_pilot2_arms.md §2/§3 的执行体；冻结件）。

产出（全部落 pilot2/prompt_pack/，不触碰 pilot2/domains|build|ci 与旧 pilot/ 任何字节）：
  <db>.schema.txt   —— 9 库 schema 包：main 全部表（业务表 + gov_* 登记表）的 CREATE DDL
                       + 行数注记；表按名字典序、列按物理序；标识符一律双引号。
  <db>.gov.txt      —— 9 库治理包：gov_seed/*.jsonl 十表全量重序列化
                       （json.dumps sort_keys ensure_ascii=False，行按文本字典序），
                       块按 P0→P9 固定序；GOV_CAP=32000 确定性截断（预期不触发）。
  MANIFEST.json     —— 尺寸/哈希/块数/截断标记 + 8 臂逐库提示长度 min–max 与总长。

确定性：重跑本脚本产出逐字节一致（已验证）。本脚本零 LLM 调用、只读 domains/。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import duckdb

P2 = pathlib.Path(__file__).resolve().parent.parent          # pilot2/
OUT = P2 / "prompt_pack"
sys.path.insert(0, str(P2.parent / "pilot"))
import run_pilot as RP  # noqa: E402  冻结 runner：只取 PROMPT / TRIVIAL_* 常量，不改不抄

GOV_CAP = 32000
# 块序 = 校验器/编译器解析链顺序（DESIGN_SPEC §3.3 步骤 1→5）；截断丢块从 P9 反向开始
PRIORITY = [
    "gov_semantic_graph_version",   # P0 版本轴 T→ver(T)
    "gov_metric_alias",             # P1 表面词→metric（随版本变）
    "gov_metric",                   # P2 指标登记
    "gov_measure_def",              # P3 度量/谓词原子（口径）
    "gov_caliber_routing",          # P4 口径路由
    "gov_valid_time_anchor",        # P5 有效时间锚（列名指针，无覆盖区间）
    "gov_temporal_binding",         # P6 绑定规则
    "gov_semantic_node",            # P7 节点→物理表
    "gov_granularity_edge",         # P8 粒度格
    "gov_disclosure_policy",        # P9 披露策略（非治域 rows=0 如实呈现）
]
ARM_EXTRA = {
    "baseline_claude": "", "baseline_qwen": "", "baseline_deepseek": "", "baseline_minimax": "",
    "trivial_claude": RP.TRIVIAL_NOTE, "trivial_v2": RP.TRIVIAL_V2_NOTE,
    "trivial_v3": RP.TRIVIAL_V3_NOTE, "governance_informed": None,  # V2_NOTE + gov 块，见下
}


def schema_pack(db: str, dir_: pathlib.Path) -> str:
    conn = duckdb.connect(str(dir_ / "warehouse.duckdb"), read_only=True)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name='main' "
            "ORDER BY table_name").fetchall()]
        lines = [
            f"-- {db} 域 pilot2 warehouse.duckdb schema（源: BIRD/Spider dev 公开数据集，"
            "抽取与 real/authored 行数见 provenance.json）",
            "-- schema: main = 业务事实/维表 + gov_* 治理登记表"
            "（十表 schema 法, DESIGN_SPEC §3.1）", ""]
        for t in tables:
            cols = conn.execute(
                "SELECT column_name, data_type FROM duckdb_columns() "
                "WHERE schema_name='main' AND table_name=? ORDER BY column_index",
                [t]).fetchall()
            n = conn.execute(f'SELECT COUNT(*) FROM main."{t}"').fetchone()[0]
            coldef = ", ".join(f'"{c}" {ty}' for c, ty in cols)
            lines.append(f'CREATE TABLE main."{t}"({coldef});')
            lines.append(f'-- rowcount main."{t}" = {n}')
            lines.append("")
        return "\n".join(lines)
    finally:
        conn.close()


def gov_blocks(db: str, dir_: pathlib.Path) -> list[tuple[str, list[str]]]:
    out = []
    for t in PRIORITY:
        p = dir_ / "gov_seed" / f"{t}.jsonl"
        rows = []
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            obj = json.loads(ln)
            dom = obj.get("domain")
            if dom is not None and dom != db:            # 域越界守卫（结构性断言）
                raise SystemExit(f"[ABORT] {db}/{t}: 越界 domain={dom}")
            rows.append(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str))
        out.append((t, sorted(rows)))
    return out


def render_gov(db: str, blocks: list[tuple[str, list[str]]]) -> tuple[str, list[str], int]:
    header = ("\n## 治理元数据（本库 gov_* 登记表全量导出；与具体问题无关，"
              "同库所有问题看到的内容完全相同）\n"
              f"-- 来源：{db}/gov_seed/*.jsonl（DESIGN_SPEC §3.1 十表 schema 法）；"
              "版本轴见 gov_semantic_graph_version\n"
              "-- 每个块 = 一张登记表，一行一个 JSON 对象，行按文本字典序排列\n")

    def emit(bs):
        s = header
        for t, rows in bs:
            s += f"\n-- TABLE {t}  (rows={len(rows)})\n"
            if rows:
                s += "\n".join(rows) + "\n"
        return s

    kept = list(blocks)
    dropped: list[str] = []
    while len(emit(kept)) > GOV_CAP and len(kept) > 1:   # 整块从最低优先级丢
        t, _ = kept.pop()                                # PRIORITY 尾 = P9
        dropped.append(t)
    kept_lines = -1
    if len(emit(kept)) > GOV_CAP:                        # 只剩一块仍超限：行级截断
        t, rows = kept[0]
        budget = GOV_CAP - len(header) - 300
        acc, used = [], 0
        for r in rows:
            if used + len(r) + 1 > budget:
                break
            acc.append(r)
            used += len(r) + 1
        kept_lines = len(acc)
        kept = [(t, acc)]
    s = emit(kept)
    if dropped or kept_lines >= 0:
        s += (f"\n-- [TRUNCATED@GOV_CAP={GOV_CAP}] dropped_blocks={dropped}; "
              f"kept_lines_in_last_block={kept_lines}\n")
    return s, dropped, kept_lines


def main() -> int:
    dirs = sorted([p for p in (P2 / "domains").iterdir()
                   if p.is_dir() and (p / "questions.json").is_file()])
    assert len(dirs) == 9, dirs
    manifest = {"llm_calls_at_generation_time": 0, "GOV_CAP": GOV_CAP,
                "priority": PRIORITY, "domains": {}, "prompt_totals": {},
                "prompt_len_range": {}}
    packs = {}
    for d in dirs:
        db = d.name
        sch = schema_pack(db, d)
        gov, dropped, kept_lines = render_gov(db, gov_blocks(db, d))
        (OUT / f"{db}.schema.txt").write_text(sch, encoding="utf-8")
        (OUT / f"{db}.gov.txt").write_text(gov, encoding="utf-8")
        qs = json.loads((d / "questions.json").read_text(encoding="utf-8"))
        packs[db] = (sch, gov, qs)
        manifest["domains"][db] = {
            "schema_chars": len(sch),
            "schema_sha256": hashlib.sha256(sch.encode()).hexdigest(),
            "gov_chars": len(gov), "gov_sha256": hashlib.sha256(gov.encode()).hexdigest(),
            "gov_blocks": len(PRIORITY) - len(dropped),
            "truncated": bool(dropped or kept_lines >= 0), "dropped_blocks": dropped,
            "n_questions": len(qs),
        }
    arms = list(ARM_EXTRA)
    for arm in arms:
        total = 0
        rng = {}
        for db, (sch, gov, qs) in sorted(packs.items()):
            extra = ARM_EXTRA[arm]
            if extra is None:
                extra = RP.TRIVIAL_V2_NOTE + gov
            lens = [len(RP.PROMPT.format(schema=sch, extra=extra, question=q["question_zh"]))
                    for q in qs]
            rng[db] = [min(lens), max(lens)]
            total += sum(lens)
        manifest["prompt_totals"][arm] = total
        manifest["prompt_len_range"][arm] = rng
    (OUT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("prompt_totals",)}, indent=1))
    for db, m in manifest["domains"].items():
        print(f"  {db:24} schema={m['schema_chars']:6}  gov={m['gov_chars']:6} "
              f"blocks={m['gov_blocks']} truncated={m['truncated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
