#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adapters.py — 五生产域 + public 的 metric/锚/绑定/路由装配层。

职责（C4 §4.4 探针接口注记：机制细节降格为实现）：
  * 从各仓 gov_* 表读取治理状态 G_v（gov_semantic_graph_version / gov_valid_time_anchor /
    gov_temporal_binding / gov_caliber_routing / gov_disclosure_policy）；
  * 把 questions.json 的问题装配为 core.Intent（窗解析 ω_r、锚指派 α_{q,v}、承诺 κ、
    覆盖/审计/μ_den 探针闭包、C3 出码模板）；
  * aibuy 缺 A 原语表（无 gov_valid_time_anchor / gov_temporal_binding，实查）：按其
    compiler.py 现行等价物（BINDINGS 常量）装配，spec_deviations 逐条记录；
  * 现役 pilot/domains/*/compiler.py 仅为对照基线（只读），本库不 import 之；
    亦不 import 任何校验器侧代码（C5 要求 5.8 红线）。

坐标：SQL 模板与现役编译器逐字节一致（等价性回归的最强保证）；探针 SQL 按规范
在 w*（行 8 裁剪后窗）上求值（μ_den(α,v,w*,σ)，引理 4.12）。
"""
from __future__ import annotations

import calendar
import datetime
import pathlib
import re
from typing import Optional

import duckdb

from .core import (
    CovResult, Disclosure, Intent, Leg, Period, RuleAudit, Window,
)

_DAY = datetime.timedelta(days=1)


# ---------------------------------------------------------------------------
# 公用小件
# ---------------------------------------------------------------------------
def _date(x) -> Optional[datetime.date]:
    if x is None:
        return None
    if isinstance(x, datetime.datetime):
        return x.date()
    if isinstance(x, datetime.date):
        return x
    return datetime.date.fromisoformat(str(x)[:10])


def _month_bounds(ym: str):
    y, m = int(ym[:4]), int(ym[5:7])
    nx = f"{y + 1}-01-01" if m == 12 else f"{y}-{m + 1:02d}-01"
    return f"{y}-{m:02d}-01", nx


def _iv_pred(col: str, w: Window) -> str:
    """把 w*（单区间窗）落为日期谓词（探针用；A4.4(ii) 有限区间并，pilot 单区间）。"""
    assert len(w.ivs) == 1, "pilot windows are single-interval"
    lo, hi = w.ivs[0]
    parts = []
    if lo is not None:
        parts.append(f"{col} >= DATE '{lo.isoformat()}'")
    if hi is not None:
        parts.append(f"{col} < DATE '{hi.isoformat()}'")
    return " AND ".join(parts) if parts else "TRUE"


def _bound_pred(bound, period, role, col, legacy_pred, w0=None):
    """出码谓词：w* == w0（未被裁剪）时保留现役模板逐字节形态；w* ⊊ w0（覆盖 hull 边
    裁剪 → dec=REWRITE）时落 **w* 的显式上下界**——认证窗与产出 SQL 的时间谓词指称集
    必须一致（C5 V6a：s 的每个时间谓词指称集 ⊆ 认证窗；只写上界会让证书主张的下界
    在语法上不可核验，是 F1c 型"窗挪移"伪造的落点）。"""
    per = (bound or {}).get(period) or {}
    leg = per.get(role)
    if leg is None or leg.w_star is None:
        return legacy_pred
    if w0 is not None and leg.w_star == w0:
        return legacy_pred
    if leg.w_star == leg.window:
        return legacy_pred
    return _iv_pred(col, leg.w_star)


def _graph_pin(con, domain: str) -> dict:
    try:
        row = con.execute(
            "SELECT version, committed_at FROM gov_semantic_graph_version LIMIT 1"
        ).fetchone()
    except duckdb.Error:
        return {"domain": domain, "graph_version": None, "commit_id": None,
                "table_absent": True}
    if row is None:
        return {"domain": domain, "graph_version": None, "commit_id": None,
                "table_absent": True}
    return {"domain": domain, "graph_version": row[0], "commit_id": row[1]}


def _listify(x):
    """join_keys 等 G_v 列的规范化：duckdb LIST 直取；JSON 数组字符串（domestic_newprod
    种子存法 '["dt"]'）解码为真列表——先前把 JSON 文本原样装单元素列表，与 V4 按
    json.loads 重查的注册值失配（证书构造缺陷，已修）。"""
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("["):
            try:
                import json as _json
                v = _json.loads(s)
                if isinstance(v, list):
                    return [str(e) for e in v]
            except ValueError:
                pass
    return [str(x)]


def _route_row(con, caliber_key: str) -> Optional[dict]:
    try:
        row = con.execute(
            "SELECT caliber_key, src_caliber, dst_caliber, via_table, join_keys, "
            "attribution_alignment FROM gov_caliber_routing WHERE caliber_key = ?",
            [caliber_key]).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return {"caliber_key": row[0], "src_caliber": row[1], "dst_caliber": row[2],
            "via_table": row[3], "join_keys": _listify(row[4]),
            "attribution_alignment": row[5]}


def _policies(con) -> list:
    try:
        rows = con.execute(
            "SELECT policy_id, role_scope_predicate, mask_class, min_grain, k_threshold, "
            "applied_columns, applied_tables, join_right_table, join_carry "
            "FROM gov_disclosure_policy").fetchall()
    except duckdb.Error:
        return []
    out = []
    for r in rows:
        out.append({"policy_id": r[0], "role_scope_predicate": r[1], "mask_class": r[2],
                    "min_grain": r[3], "k_threshold": r[4],
                    "applied_columns": _listify(r[5]), "applied_tables": _listify(r[6]),
                    "join_right_table": r[7], "join_carry": _listify(r[8])})
    return out


def _touched(policies: list, read_set: set) -> list:
    """π ∈ touched(q) ⇔ P̄_π ∩ R(q) ≠ ∅（定义 4.5；P̄ 为 carry 闭包，引理 4.4）。"""
    out = []
    for p in policies:
        cols = {(t, c) for t in p["applied_tables"] for c in p["applied_columns"]}
        if p.get("join_right_table"):
            for c in p.get("join_carry", []):
                cols.add((p["join_right_table"], c))  # 保联结携出（worklist 一步即闭包，pilot 单边）
        if cols & read_set:
            out.append(p["policy_id"])
    return out


# ---- 覆盖探针族（行 8–9；逐锚 coverage_mode，D3）----------------------------
def _hull_cov(con, anchor_id, table, col, lo_only=False, deviation=None, mode=None):
    """按 G_v 声明的 coverage_mode 求 Cov_v(a)（D3：mode 是锚的版本化属性）：
      hull            [min, max]        （C3 定义 3.3 缺省快照锚读法）
      hull_right_open [min, +inf)       （email 事件流锚的 G_v 声明值；兑现冻结金标
                                         EMAIL-ASOF-06=MC(ii)）
      hull_left_open  (-inf, max]       （aibuy 画像信号锚的 G_v 声明值；兑现冻结金标
                                         AIBUY-Q6=MC(ii)，C4 §4.4 标签归一注记）
    两个半开 mode 是对 C3 定义 3.3 cm_a∈{hull,strict_member} 的实现扩展（DEVIATION-1）。
    证书/探针笔录按 G_v 声明的 mode 落字，校验器对同一声明重演。"""
    mode = mode or ("hull_right_open" if lo_only else "hull")

    def probe(leg: Leg) -> CovResult:
        sql = f"SELECT min({col}), max({col}) FROM {table}"
        mn, mx = con.execute(sql).fetchone()
        mn, mx = _date(mn), _date(mx)
        if mn is None:
            env = Window.empty()
        elif mode == "hull_right_open":
            env = Window.interval(mn, None, "hull-right-open")
        elif mode == "hull_left_open":
            env = Window.interval(None, mx + _DAY, "hull-left-open")
        else:
            env = Window.interval(mn, mx + _DAY, "hull")
        bound = leg.window.intersect(env, kind=leg.window.kind)
        return CovResult(
            mode=mode, bound=bound, empty=bound.is_empty(),
            w0_subset_val=leg.window.subset_of(env),
            env_brief=env.brief(),
            probe={"kind": "COVERAGE", "anchor_id": anchor_id, "coverage_mode": mode,
                   "sql": sql, "observed": [str(mn), str(mx)]},
            deviation=deviation)
    return probe


def _member_day_cov(con, anchor_id, table, col, day: str):
    def probe(leg: Leg) -> CovResult:
        sql = f"SELECT count(*) FROM {table} WHERE {col} = DATE '{day}'"
        n = con.execute(sql).fetchone()[0]
        member = n > 0
        bound = leg.window if member else Window.empty()
        return CovResult(
            mode="strict_member", bound=bound, empty=not member,
            w0_subset_val=member,
            env_brief=f"strict_member 有效标记日集 of {table}.{col}",
            probe={"kind": "COVERAGE", "anchor_id": anchor_id,
                   "coverage_mode": "strict_member", "sql": sql, "observed": n})
    return probe


def _member_month_cov(con, anchor_id, table, col, month_start: str):
    def probe(leg: Leg) -> CovResult:
        sql = (f"SELECT count(*) FROM {table} "
               f"WHERE date_trunc('month', {col}) = DATE '{month_start}'")
        n = con.execute(sql).fetchone()[0]
        member = n > 0
        bound = leg.window if member else Window.empty()
        return CovResult(
            mode="strict_member", bound=bound, empty=not member,
            w0_subset_val=member,
            env_brief=f"strict_member 月粒标记集 of {table}.{col}",
            probe={"kind": "COVERAGE", "anchor_id": anchor_id,
                   "coverage_mode": "strict_member", "sql": sql, "observed": n})
    return probe


def _scd_point_cov(con, anchor_id, table, vf_col, vt_col, day: str):
    def probe(leg: Leg) -> CovResult:
        sql = (f"SELECT count(*) FROM {table} WHERE {vf_col} <= DATE '{day}' "
               f"AND {vt_col} > DATE '{day}'")
        n = con.execute(sql).fetchone()[0]
        member = n > 0
        bound = leg.window if member else Window.empty()
        return CovResult(
            mode="strict_member", bound=bound, empty=not member,
            w0_subset_val=member,
            env_brief=f"SCD-2 点窗有效区间并 [{vf_col},{vt_col}) of {table}（D7: vf<=d<vtc）",
            probe={"kind": "COVERAGE", "anchor_id": anchor_id,
                   "coverage_mode": "strict_member", "sql": sql, "observed": n})
    return probe


def _symdiff_material(con, table_a, col_a, table_b, col_b, anchor_a, anchor_b):
    """条款 (iv) symdiff_audit / AM(i) 判别元：两锚有效日期集对称差 + 判别日。"""
    def run() -> dict:
        sql = (f"SELECT (SELECT count(*) FROM (SELECT DISTINCT {col_a} AS d FROM {table_a}) n"
               f" WHERE n.d NOT IN (SELECT DISTINCT {col_b} FROM {table_b}))"
               f" + (SELECT count(*) FROM (SELECT DISTINCT {col_b} AS d FROM {table_b}) r"
               f" WHERE r.d NOT IN (SELECT DISTINCT {col_a} FROM {table_a}))")
        n = con.execute(sql).fetchone()[0]
        disc = None
        if n > 0:
            disc = con.execute(
                f"SELECT d FROM ((SELECT DISTINCT {col_a} AS d FROM {table_a} "
                f"WHERE {col_a} NOT IN (SELECT DISTINCT {col_b} FROM {table_b})) UNION ALL "
                f"(SELECT DISTINCT {col_b} AS d FROM {table_b} "
                f"WHERE {col_b} NOT IN (SELECT DISTINCT {col_a} FROM {table_a}))) "
                f"ORDER BY d LIMIT 1").fetchone()[0]
        return {"ok": n == 0, "num_anchor": anchor_a, "den_anchor": anchor_b,
                "symdiff_count": n,
                "discriminant_date": str(disc) if disc is not None else None,
                "probe": {"kind": "ADM_SYMDIFF", "sql": sql, "observed": n,
                          "anchors": [anchor_a, anchor_b]}}
    return run


def _interval_containment_audit(con, num_table, num_col, den_table, vf_col, vt_col,
                                anchor_n, anchor_d):
    """条款 (iv) interval_containment：分子粒元须落入分母 SCD 在效区间（C3 定义 3.8(iv)）。"""
    def run() -> dict:
        sql = (f"SELECT count(*) FROM (SELECT DISTINCT {num_col} AS d FROM {num_table}) x "
               f"WHERE NOT EXISTS (SELECT 1 FROM {den_table} p "
               f"WHERE p.{vf_col} <= x.d AND p.{vt_col} > x.d)")
        n = con.execute(sql).fetchone()[0]
        return {"ok": n == 0, "num_anchor": anchor_n, "den_anchor": anchor_d,
                "uncovered_granules": n,
                "probe": {"kind": "ADM_INTERVAL_CONTAINMENT", "sql": sql, "observed": n,
                          "anchors": [anchor_n, anchor_d]}}
    return run


# ===========================================================================
# rma
# ===========================================================================
class RmaAdapter:
    domain = "rma"
    NUM_TABLE = "flexispot_rma.dws_rma_sku_problem_1d"
    DEN_TABLE = "flexispot_rma.dws_sales_sku_1d"
    PT_TABLE = "flexispot_rma.dws_rma_problemtype_1d"
    DIM_PT = "flexispot_rma.dim_problem_type"
    MEASURES = {"problem_rate": ("problem_qty", "sales_qty"),
                "refund_rate": ("refund_amount", "sales_amount")}
    # 结构化参数（与现役编译器 QSPEC 同源：出题时从 question_zh 固化；κ 的退化解析，缺口 G-2）
    QSPEC = {
        "rma_q1": {"metric": "problem_rate", "sku": "E7-WHT"},
        "rma_q2": {"metric": "refund_rate", "sku": "EG8-BLK"},
        "rma_q3": {"metric": "problem_rate", "sku": "EC1-BLK",
                   "delta_windows": ["2026-03", "2026-05"]},
        "rma_q4": {"metric": "problem_qty", "kind": "atomic", "lvl1": "Quality"},
        "rma_q5": {"metric": "problem_rate", "sku": "SKU536-EOL"},
        "rma_q6": {"metric": "refund_rate", "sku": "EG8-BLK",
                   "num_window": "2026-05", "den_window": "2026-04"},
    }

    def __init__(self, dir_path: pathlib.Path):
        self.db = str(dir_path / "warehouse.duckdb")

    # -- 现役模板逐字节镜像（等价性回归锚点）--------------------------------
    def _rate_sql(self, metric, sku, window):
        nm, dm = self.MEASURES[metric]
        lo, hi = _month_bounds(window)
        return (
            f"WITH num AS (SELECT CAST(SUM({nm}) AS DOUBLE) AS v FROM {self.NUM_TABLE} "
            f"WHERE product_sku = '{sku}' AND dt >= DATE '{lo}' AND dt < DATE '{hi}'),\n"
            f"     den AS (SELECT CAST(SUM({dm}) AS DOUBLE) AS v FROM {self.DEN_TABLE} "
            f"WHERE product_sku = '{sku}' AND dt >= DATE '{lo}' AND dt < DATE '{hi}')\n"
            f"SELECT ROUND(num.v / NULLIF(den.v, 0), 6) AS {metric} FROM num, den"
        )

    def _rate_delta_sql(self, metric, sku, w1, w2):
        nm, dm = self.MEASURES[metric]
        lo1, hi1 = _month_bounds(w1)
        lo2, hi2 = _month_bounds(w2)

        def rate(lo, hi):
            return (
                f"(SELECT CAST(SUM(n.v) AS DOUBLE) / NULLIF(CAST(SUM(d.v) AS DOUBLE), 0) FROM "
                f"(SELECT SUM({nm}) AS v FROM {self.NUM_TABLE} WHERE product_sku = '{sku}' "
                f"AND dt >= DATE '{lo}' AND dt < DATE '{hi}') n, "
                f"(SELECT SUM({dm}) AS v FROM {self.DEN_TABLE} WHERE product_sku = '{sku}' "
                f"AND dt >= DATE '{lo}' AND dt < DATE '{hi}') d)"
            )
        return f"SELECT ROUND({rate(lo2, hi2)} - {rate(lo1, hi1)}, 6) AS {metric}_delta"

    def _atomic_sql(self, lvl1, window):
        lo, hi = _month_bounds(window)
        return (
            f"SELECT CAST(SUM(s.problem_qty) AS BIGINT) AS problem_qty FROM {self.PT_TABLE} s "
            f"JOIN {self.DIM_PT} p ON s.problem_type_id = p.problem_type_id "
            f"WHERE p.lvl1_name = '{lvl1}' AND s.dt >= DATE '{lo}' AND s.dt < DATE '{hi}'"
        )

    def _phys(self, semantic_object: str) -> str:
        return f"flexispot_rma.{semantic_object}"

    def intent(self, q: dict, con) -> Intent:
        spec = self.QSPEC[q["qid"]]
        metric = spec["metric"]
        as_of = q.get("as_of")
        graph = _graph_pin(con, "rma")
        anchors = {r[0]: {"semantic_object": r[1], "col": r[2]} for r in con.execute(
            "SELECT anchor_id, semantic_object, effective_date FROM gov_valid_time_anchor"
        ).fetchall()}
        # ≺_det 注册序：缺省钉 binding_id 字典序（定义 4.11；现役 rma compiler 同款 ORDER BY）
        brow = con.execute(
            "SELECT binding_id, rule, numerator_anchor, denominator_anchor "
            "FROM gov_temporal_binding WHERE domain='rma' AND metric=? ORDER BY binding_id",
            [metric]).fetchone()

        if brow is None:
            # 原子型（rma_q4）：β 可缺省（C3 定义 3.4），单锚 rma_event_time，月窗
            a = "rma_event_time"
            tab, col = self._phys(anchors[a]["semantic_object"]), anchors[a]["col"]
            leg = Leg(role="atom", anchor_id=a, registered=True, required_anchor_id=a,
                      window=Window.month(as_of), granule="day",
                      coverage=_hull_cov(con, a, tab, col))
            return Intent(
                qid=q["qid"], domain="rma", metric=metric, metric_kind="atomic",
                graph=graph, periods=[Period(0, as_of, [leg])],
                binding=None, rule_audit=None, route=[],
                g0="problem_type_lvl1×month",
                disclosure=Disclosure(policy_table_present=False),
                emit_sql=lambda bound: self._atomic_sql(spec["lvl1"], as_of))

        binding_id, rule, num_a, den_a = brow
        route = _route_row(con, "rma_problem_to_sales")
        nm, dm = self.MEASURES[metric]
        sku = spec["sku"]

        def mk_leg(role, anchor_id, window, rigid):
            info = anchors[anchor_id]
            return Leg(role=role, anchor_id=anchor_id, registered=True,
                       required_anchor_id=anchor_id, window=window, rigid_window=rigid,
                       granule="day",
                       coverage=_hull_cov(con, anchor_id, self._phys(info["semantic_object"]),
                                          info["col"]))

        periods = []
        if "delta_windows" in spec:
            for i, w in enumerate(spec["delta_windows"]):
                periods.append(self._ratio_period(con, i, w, w, num_a, den_a, dm, sku, mk_leg))
        else:
            nw = spec.get("num_window", as_of)
            dw = spec.get("den_window", as_of)
            rigid = "num_window" in spec  # q6 题面显式双窗承诺 → 窗坐标刚性（定义 4.6 实例）
            periods.append(self._ratio_period(con, 0, nw, dw, num_a, den_a, dm, sku,
                                              mk_leg, rigid=rigid))

        def emit(bound):
            if "delta_windows" in spec:
                return self._rate_delta_sql(metric, sku, *spec["delta_windows"])
            return self._rate_sql(metric, sku, spec.get("num_window", as_of))

        notes = []
        if metric == "refund_rate":
            notes.append(
                "μ_den 探针按分母测度 sales_amount（C4 §4.4 探针形态对账：现役 rma 编译器对 "
                "refund_rate 探 sales_qty 属潜在实现偏差；本仓无 qty>0∧amount<=0 分歧行，两读同值）")
        return Intent(
            qid=q["qid"], domain="rma", metric=metric, metric_kind="ratio",
            graph=graph, periods=periods,
            combine="delta" if "delta_windows" in spec else "single",
            binding={"binding_id": binding_id, "rule": rule,
                     "numerator_anchor": num_a, "denominator_anchor": den_a,
                     "adm_check_mode": "trivial_true"},
            rule_audit=RuleAudit(binding_id=binding_id, rule=rule,
                                 adm_check_mode="trivial_true", g_cmp="day"),
            route=[route] if route else [],
            g0="product_sku×month",
            disclosure=Disclosure(policy_table_present=False),
            emit_sql=emit, notes=notes)

    def _ratio_period(self, con, idx, nw, dw, num_a, den_a, den_measure, sku, mk_leg,
                      rigid=False):
        legs = [mk_leg("numerator", num_a, Window.month(nw), rigid),
                mk_leg("denominator", den_a, Window.month(dw), rigid)]

        def den_probe(bound_windows):
            w = bound_windows["denominator"]
            sql = (f"SELECT SUM({den_measure}) FROM {self.DEN_TABLE} "
                   f"WHERE product_sku = '{sku}' AND {_iv_pred('dt', w)}")
            v = con.execute(sql).fetchone()[0]
            return {"sql": sql, "observed": None if v is None else float(v),
                    "mu_den": None if v is None else float(v)}
        return Period(idx, f"{nw}|{dw}", legs, den_probe=den_probe)


# ===========================================================================
# quality_voc
# ===========================================================================
class QualityVocAdapter:
    domain = "quality_voc"
    METRIC_CALIBER = {"defect_rate": "quality_complaint_to_sales",
                      "avg_handle_hours": "reissue_sla_self",
                      "complaint_rate_global_recompute": "complaint_rate_pivot_reference"}

    def __init__(self, dir_path: pathlib.Path):
        self.db = str(dir_path / "warehouse.duckdb")

    @staticmethod
    def _q(s):
        return s.replace("'", "''")

    def _anchor(self, con, anchor_id):
        row = con.execute(
            "SELECT semantic_object, effective_date FROM gov_valid_time_anchor "
            "WHERE anchor_id = ?", [anchor_id]).fetchone()
        if row is None:
            return None
        return {"semantic_object": row[0], "col": row[1]}

    def intent(self, q: dict, con) -> Intent:
        metric = q["metric"]
        as_of = q["as_of"]
        params = q.get("params") or {}
        graph = _graph_pin(con, "quality_voc")
        dis = Disclosure(policy_table_present=False)

        if metric == "defect_rate":
            return self._defect_rate(q, con, graph, dis, as_of, params)
        if metric == "avg_handle_hours":
            return self._avg_handle(q, con, graph, dis, as_of, params)

        # 其余 metric：无锚/绑定可评（OOV/AM 真空约定），落口径闸 → MC(i)
        caliber = self.METRIC_CALIBER.get(metric)
        if caliber is not None:
            sql = ("SELECT caliber_key, dst_caliber FROM gov_caliber_routing "
                   f"WHERE caliber_key = '{caliber}'")
            row = con.execute(sql).fetchone()
            mc = {"metric": metric, "caliber_key": caliber,
                  "dst_caliber": row[1] if row else None,
                  "assertion": "reference-only 路由（dst_caliber='none'）不可重算 → MC(i)",
                  "probe": {"kind": "ROUTE_LOOKUP", "sql": sql,
                            "observed": list(row) if row else None}}
        else:
            mc = {"metric": metric, "caliber_key": None,
                  "assertion": "metric 无注册口径路由/绑定可依 → MC(i)"}
        legs = [Leg("numerator", None, False, None, Window.point(f"{as_of}-01" if len(as_of) == 7 else as_of)),
                Leg("denominator", None, False, None, Window.point(f"{as_of}-01" if len(as_of) == 7 else as_of))]
        return Intent(
            qid=q["qid"], domain="quality_voc", metric=metric, metric_kind="ratio",
            graph=graph, periods=[Period(0, as_of, legs)],
            binding=None, route=[], g0="category×week", disclosure=dis,
            mc_missing=mc,
            notes=["I2'(a)：涉事度量 reference-only，无可指派 (a,W)——α 记显式空指派"])

    # -- defect_rate ---------------------------------------------------------
    def _defect_rate(self, q, con, graph, dis, as_of, params):
        num_anchor = params.get("numerator_anchor", "complaint_submit_date")
        den_anchor = params.get("denominator_anchor", "sales_event_date")
        as_of_day = f"{as_of}-01" if len(as_of) == 7 else as_of
        as_of_prev = params.get("as_of_prev")
        model = params.get("company_model")
        route = _route_row(con, self.METRIC_CALIBER["defect_rate"])

        # β_v(defect_rate)：正例行选取（(domain,metric) 非函数键——负例行不入 β，C3 原型对照；
        # 机器可读 is_negative 列缺席（C5 V3 种子扩列待办）→ 以路由相容性消歧：
        # 取分母锚 semantic_object == 路由 via_table 的行（I3 路由衔接的装配面）。
        brows = con.execute(
            "SELECT binding_id, rule, numerator_anchor, denominator_anchor "
            "FROM gov_temporal_binding WHERE domain='quality_voc' AND metric='defect_rate' "
            "ORDER BY binding_id").fetchall()
        pos = None
        for b in brows:
            a = self._anchor(con, b[3])
            if a and route and a["semantic_object"] == route["via_table"]:
                pos = b
                break
        binding_id, rule, req_num, req_den = pos

        def mk_leg(role, anchor_id, required, day):
            info = self._anchor(con, anchor_id)
            registered = info is not None
            return Leg(role=role, anchor_id=anchor_id, registered=registered,
                       required_anchor_id=required, window=Window.point(day),
                       granule="week",
                       declared_override=(anchor_id != required),
                       coverage=(_member_day_cov(con, anchor_id, info["semantic_object"],
                                                 info["col"], day) if registered else None))

        periods = []
        days = [as_of_day] + ([as_of_prev] if as_of_prev else [])
        for i, day in enumerate(days):
            legs = [mk_leg("numerator", num_anchor, req_num, day),
                    mk_leg("denominator", den_anchor, req_den, day)]

            def den_probe(bound_windows, _day=day):
                scope = f" AND company_model = '{self._q(model)}'" if model else ""
                sql = (f"SELECT SUM(sales_qty) FROM dws_quality_defect_model_1w "
                       f"WHERE dt = DATE '{_day}'{scope}")
                v = con.execute(sql).fetchone()[0]
                return {"sql": sql, "observed": None if v is None else float(v),
                        "mu_den": None if v is None else float(v)}
            periods.append(Period(i, day, legs, den_probe=den_probe))

        # 条款 (iv) 审计（symdiff_audit，对规定锚对）与 AM(i) 判别元（对声明锚对）
        na, da = self._anchor(con, req_num), self._anchor(con, req_den)
        adm = _symdiff_material(con, na["semantic_object"], na["col"],
                                da["semantic_object"], da["col"], req_num, req_den)
        mism = None
        dna, dda = self._anchor(con, num_anchor), self._anchor(con, den_anchor)
        if dna and dda:
            mism = _symdiff_material(con, dna["semantic_object"], dna["col"],
                                     dda["semantic_object"], dda["col"],
                                     num_anchor, den_anchor)

        def emit(bound):
            if as_of_prev:
                return ("SELECT ROUND(a.defect_rate - b.defect_rate, 6) "
                        "FROM ads_quality_defect_rank_1w a "
                        "JOIN ads_quality_defect_rank_1w b ON a.company_model = b.company_model "
                        f"WHERE a.company_model = '{self._q(model)}' "
                        f"AND a.dt = DATE '{as_of}' AND b.dt = DATE '{as_of_prev}'")
            if model:
                return ("SELECT defect_rate FROM ads_quality_defect_rank_1w "
                        f"WHERE company_model = '{self._q(model)}' AND dt = DATE '{as_of}'")
            return ("SELECT ROUND(SUM(complaint_qty) * 1.0 / SUM(sales_qty), 6) "
                    f"FROM dws_quality_defect_model_1w WHERE dt = DATE '{as_of}'")

        return Intent(
            qid=q["qid"], domain="quality_voc", metric="defect_rate", metric_kind="ratio",
            graph=graph, periods=periods,
            combine="delta" if as_of_prev else "single",
            binding={"binding_id": binding_id, "rule": rule,
                     "numerator_anchor": req_num, "denominator_anchor": req_den,
                     "adm_check_mode": "symdiff_audit"},
            rule_audit=RuleAudit(binding_id=binding_id, rule=rule,
                                 adm_check_mode="symdiff_audit", g_cmp="week",
                                 adm_audit=adm, mismatch_material=mism),
            route=[route] if route else [],
            g0=("company_model×week" if model else "all_models×week"),
            disclosure=dis, emit_sql=emit,
            notes=["β 正例行经路由相容性消歧（负例行 complaint_vs_rma_anchor_mismatch 不入 β；"
                   "is_negative 机器可读列为 C5 V3 种子扩列待办）"])

    # -- avg_handle_hours ----------------------------------------------------
    def _avg_handle(self, q, con, graph, dis, as_of, params):
        month_start = f"{as_of}-01" if len(as_of) == 7 else as_of
        anchor_id = params.get("anchor", "rma_create_date")
        info = self._anchor(con, anchor_id)
        cat = params.get("category")
        route = _route_row(con, self.METRIC_CALIBER["avg_handle_hours"])

        brow = con.execute(
            "SELECT binding_id, rule, numerator_anchor, denominator_anchor "
            "FROM gov_temporal_binding WHERE domain='quality_voc' "
            "AND metric='avg_handle_hours' ORDER BY binding_id").fetchone()
        binding_id, rule, req_num, req_den = brow if brow else (None, None, None, None)

        def mk(role):
            required = {"numerator": req_num, "denominator": req_den}.get(role, anchor_id)
            return Leg(role=role, anchor_id=anchor_id, registered=True,
                       required_anchor_id=required or anchor_id,
                       window=Window.month(as_of), granule="month",
                       declared_override=(required is not None and anchor_id != required),
                       coverage=_member_month_cov(con, anchor_id, info["semantic_object"],
                                                  info["col"], month_start))

        def den_probe(bound_windows):
            sql = (f"SELECT SUM(ticket_cnt) FROM dws_reissue_category_1m "
                   f"WHERE category = '{self._q(cat)}' AND dt = DATE '{month_start}'")
            v = con.execute(sql).fetchone()[0]
            return {"sql": sql, "observed": None if v is None else float(v),
                    "mu_den": None if v is None else float(v)}

        return Intent(
            qid=q["qid"], domain="quality_voc", metric="avg_handle_hours",
            metric_kind="ratio", graph=graph,
            periods=[Period(0, as_of, [mk("numerator"), mk("denominator")],
                            den_probe=den_probe)],
            binding=({"binding_id": binding_id, "rule": rule,
                      "numerator_anchor": req_num, "denominator_anchor": req_den,
                      "adm_check_mode": "trivial_true"} if binding_id else None),
            rule_audit=(RuleAudit(binding_id=binding_id, rule=rule,
                                  adm_check_mode="trivial_true", g_cmp="day")
                        if binding_id else None),
            route=[route] if route else [],
            g0="category×month", disclosure=dis,
            emit_sql=lambda bound: ("SELECT avg_handle_hours FROM ads_reissue_sla_1m "
                                    f"WHERE category = '{self._q(cat)}' AND dt = DATE '{month_start}'"),
            notes=["β_v(avg_handle_hours)=avg_handle_hours_align（两腿同锚 rma_create_date、"
                   "同窗、adm 平凡真）：该绑定原只活在 gov_caliber_routing['reissue_sla_self']"
                   ".note 的散文里，集成期落为登记行；先前实现以 spec_deviation 跳过"
                   "「比率型 β↑ → MC(i)」的字面读法，该偏离随登记消解"])


# ===========================================================================
# domestic_newprod
# ===========================================================================
class DomesticNewprodAdapter:
    domain = "domestic_newprod"
    TEMPLATES = {
        "launch_online_rate": {
            "kind": "ratio",
            "sql": ("SELECT CAST(sum(biz_online) AS DOUBLE)/count(*) "
                    "FROM dwd_product_launch_di WHERE {pred}"),
            "den_table": "dwd_product_launch_di", "den_expr": "count(*)",
            "caliber": "launch_online_to_prodtask", "window": "cumulative"},
        "mkt_reach_rate": {
            "kind": "ratio",
            "sql": ("SELECT CAST(sum(mkt_reached) AS DOUBLE)/count(*) "
                    "FROM dwd_product_launch_di WHERE {pred}"),
            "den_table": "dwd_product_launch_di", "den_expr": "count(*)",
            "caliber": "launch_mkt_to_prodtask", "window": "cumulative"},
        "online_share": {
            "kind": "ratio",
            "sql": ("SELECT CAST(sum(online_qty) AS DOUBLE)/sum(order_total_qty) "
                    "FROM dwd_preorder_confirm_di WHERE {pred}"),
            "den_table": "dwd_preorder_confirm_di",
            "den_expr": "COALESCE(sum(order_total_qty),0)",
            "caliber": "preorder_online_to_total", "window": "cumulative"},
        "offline_share": {
            "kind": "ratio",
            "sql": ("SELECT CAST(sum(offline_qty) AS DOUBLE)/sum(order_total_qty) "
                    "FROM dwd_preorder_confirm_di WHERE {pred}"),
            "den_table": "dwd_preorder_confirm_di",
            "den_expr": "COALESCE(sum(order_total_qty),0)",
            "caliber": "preorder_offline_to_total", "window": "cumulative"},
        "product_versions_valid_asof": {
            "kind": "atomic",
            "sql": ("SELECT CAST(count(*) AS DOUBLE) FROM dim_product "
                    "WHERE dw_start_date <= DATE '{d}' AND dw_end_date > DATE '{d}'"),
            "caliber": None, "window": "point", "anchor": "domestic_newprod_scd2_dim_product",
            "binding_ref": "model_mismatch_rate_align"},
        "model_mismatch_rate": {
            "kind": "ratio",
            "sql": ("SELECT CAST(sum(CASE WHEN sales_model <> company_model THEN 1 ELSE 0 END) "
                    "AS DOUBLE)/count(*) FROM dim_product "
                    "WHERE dw_start_date <= DATE '{d}' AND dw_end_date > DATE '{d}'"),
            "den_table": "dim_product", "den_expr": "count(*)",
            "caliber": "sku_to_company_model_bridge", "window": "point"},
        "online_group_order_cnt": {
            "kind": "atomic",
            "sql": ("SELECT CAST(count(*) AS DOUBLE) FROM ("
                    "SELECT DISTINCT o.prod_order_id FROM dwd_prod_order_di o, "
                    "unnest(string_split(o.channel, ',')) AS u(ch) "
                    "JOIN dim_channel cm ON trim(u.ch) = cm.channel "
                    "WHERE cm.channel_group = '线上' AND {pred})"),
            "caliber": "channel_to_group_bridge", "window": "cumulative",
            "anchor": "prodorder_order_date"},
        "offline_group_order_cnt": {
            "kind": "atomic",
            "sql": ("SELECT CAST(count(*) AS DOUBLE) FROM ("
                    "SELECT DISTINCT o.prod_order_id FROM dwd_prod_order_di o, "
                    "unnest(string_split(o.channel, ',')) AS u(ch) "
                    "JOIN dim_channel cm ON trim(u.ch) = cm.channel "
                    "WHERE cm.channel_group = '线下' AND {pred})"),
            "caliber": "channel_to_group_bridge", "window": "cumulative",
            "anchor": "prodorder_order_date"},
    }
    # ā 改锚声明的语用判定（κ 的退化 NL 解析，C5 §6.1 如实声明；缺口 G-2）：
    # 命中即声明改锚到治理图查无此锚的时间列 → D8 未注册锚 → AM(i)
    ANCHOR_OVERRIDE = {
        "launch_order_date": (re.compile(r"(以|按|取)[^。；]{0,12}上线(日期|时间|时点)"),
                              "numerator", "业务部上线日期(biz_dept_online_date)"),
        "preorder_finish_date": (re.compile(r"(以|按|取)[^。；]{0,12}发起(时间|时点)"),
                                 "numerator", "产前下单发起时间(preorder_initiate_date)"),
        "domestic_newprod_scd2_dim_product": (re.compile(r"(以|按|用)[^。；]{0,10}(最新|当前)版本"),
                                              "denominator", "最新版本读(latest_version_pin)"),
    }

    def __init__(self, dir_path: pathlib.Path):
        self.db = str(dir_path / "warehouse.duckdb")

    @staticmethod
    def _as_of_end(as_of: str) -> str:
        as_of = (as_of or "").strip()
        m = re.match(r"^(\d{4})-(\d{2})$", as_of)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
            return f"{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", as_of):
            return as_of
        raise ValueError(f"unparseable as_of: {as_of!r}")

    def intent(self, q: dict, con) -> Intent:
        metric = q.get("metric")
        text = q.get("question_zh", "") or ""
        graph = _graph_pin(con, "domestic_newprod")
        dis = Disclosure(policy_table_present=False)
        if metric not in self.TEMPLATES:
            return Intent(qid=q["qid"], domain=self.domain, metric=metric,
                          metric_kind="ratio", graph=graph,
                          periods=[Period(0, "-", [Leg("numerator", None, False, None,
                                                       Window.empty()),
                                                   Leg("denominator", None, False, None,
                                                       Window.empty())])],
                          binding=None, route=[], g0="requested", disclosure=dis,
                          mc_missing={"metric": metric, "caliber_key": None,
                                      "assertion": "指标无治理模板/口径定义 → MC(i)"})
        tpl = self.TEMPLATES[metric]
        try:
            d = self._as_of_end(q.get("as_of", ""))
        except ValueError:
            return Intent(qid=q["qid"], domain=self.domain, metric=metric,
                          metric_kind=tpl["kind"], graph=graph,
                          periods=[Period(0, "-", [])], binding=None, route=[],
                          g0="requested", disclosure=dis,
                          oov_parse={"as_of": q.get("as_of")})

        anchors = {r[0]: {"semantic_object": r[1], "anchor_type": r[2],
                          "col": r[3], "vf": r[4], "vt": r[5]}
                   for r in con.execute(
                       "SELECT anchor_id, semantic_object, anchor_type, effective_date, "
                       "valid_from_col, valid_to_col FROM gov_valid_time_anchor").fetchall()}
        brow = con.execute(
            "SELECT binding_id, rule, numerator_anchor, denominator_anchor "
            "FROM gov_temporal_binding WHERE metric = ? ORDER BY binding_id",
            [metric]).fetchone()

        window = Window.cumulative_to(d) if tpl["window"] == "cumulative" else Window.point(d)

        def cov_for(anchor_id):
            a = anchors[anchor_id]
            if a["anchor_type"] == "scd_type2":
                return _scd_point_cov(con, anchor_id, a["semantic_object"], a["vf"], a["vt"], d)
            return _hull_cov(con, anchor_id, a["semantic_object"], a["col"])

        route = _route_row(con, tpl["caliber"]) if tpl.get("caliber") else None

        if brow is not None and tpl["kind"] == "ratio":
            binding_id, rule, num_a, den_a = brow
        elif tpl.get("binding_ref"):
            b2 = con.execute(
                "SELECT binding_id, rule, numerator_anchor, denominator_anchor "
                "FROM gov_temporal_binding WHERE binding_id = ?",
                [tpl["binding_ref"]]).fetchone()
            binding_id, rule, num_a, den_a = b2
        else:
            binding_id = rule = num_a = den_a = None

        # ---- 装配 legs ----
        legs = []
        if tpl["kind"] == "atomic" and metric != "product_versions_valid_asof" or \
                (tpl["kind"] == "atomic" and metric == "product_versions_valid_asof"):
            anchor_id = tpl.get("anchor") or den_a
            a = anchors[anchor_id]
            gran = "itv" if a["anchor_type"] == "scd_type2" else "day"
            legs.append(Leg(role="atom", anchor_id=anchor_id, registered=True,
                            required_anchor_id=anchor_id, window=window, granule=gran,
                            coverage=cov_for(anchor_id)))
        else:
            for role, aid in (("numerator", num_a), ("denominator", den_a)):
                a = anchors[aid]
                gran = "itv" if a["anchor_type"] == "scd_type2" else "day"
                legs.append(Leg(role=role, anchor_id=aid, registered=True,
                                required_anchor_id=aid, window=window, granule=gran,
                                coverage=cov_for(aid)))

        # ---- ā 改锚声明（题面正则命中 → 未注册锚引用，D8 → AM(i)）----
        for bound_anchor, (pat, role, ref_name) in self.ANCHOR_OVERRIDE.items():
            if bound_anchor in {num_a, den_a, tpl.get("anchor")} and pat.search(text):
                for leg in legs:
                    if leg.role == role or (leg.role == "atom" and role == "numerator"):
                        leg.anchor_id = ref_name
                        leg.registered = False       # A_v 查无此锚（C3 定义 3.7 RefA_v）
                        leg.declared_override = True
                        leg.coverage = None          # 未注册锚不参与 Cov/OOV 求值
                        break
                break

        den_probe = None
        if tpl["kind"] == "ratio":
            def den_probe(bound_windows, _tpl=tpl):
                w = bound_windows["denominator"]
                if _tpl["den_table"] == "dim_product":
                    sql = (f"SELECT {_tpl['den_expr']} FROM dim_product "
                           f"WHERE dw_start_date <= DATE '{d}' AND dw_end_date > DATE '{d}'")
                else:
                    sql = (f"SELECT {_tpl['den_expr']} FROM {_tpl['den_table']} "
                           f"WHERE {_iv_pred('dt', w)}")
                v = con.execute(sql).fetchone()[0]
                return {"sql": sql, "observed": None if v is None else float(v),
                        "mu_den": None if v is None else float(v)}

        audit = None
        if binding_id == "model_mismatch_rate_align" and tpl["kind"] == "ratio":
            na, da_ = anchors[num_a], anchors[den_a]
            audit = _interval_containment_audit(
                con, na["semantic_object"], na["col"],
                da_["semantic_object"], da_["vf"], da_["vt"], num_a, den_a)

        rule_audit = None
        binding_info = None
        if binding_id is not None and tpl["kind"] == "ratio":
            mode = ("interval_containment" if binding_id == "model_mismatch_rate_align"
                    else "trivial_true")
            binding_info = {"binding_id": binding_id, "rule": rule,
                            "numerator_anchor": num_a, "denominator_anchor": den_a,
                            "adm_check_mode": mode}
            rule_audit = RuleAudit(binding_id=binding_id, rule=rule,
                                   adm_check_mode=mode, g_cmp="day", adm_audit=audit)
        # 原子型不引绑定行：β_v 对原子型可缺省（C3 定义 3.4），而 binding_ref 指向的
        # 是**另一个 metric**（model_mismatch_rate）的绑定行——把它写进证书 binding
        # 段等于宣称 β_v(product_versions_valid_asof)↓ 且规则可审，V3 逐 id 查键即
        # 判"该行治理的不是本题 metric"。锚来源改由 A_v 的锚指派登记（metrics 列）承担。

        def emit(bound):
            if "{pred}" not in tpl["sql"]:
                return tpl["sql"].format(d=d)
            role = "atom" if tpl["kind"] == "atomic" else "numerator"
            col = "o.dt" if "unnest(" in tpl["sql"] else "dt"
            legacy = f"{col} <= DATE '{d}'"
            return tpl["sql"].format(
                d=d, pred=_bound_pred(bound, 0, role, col, legacy))

        return Intent(
            qid=q["qid"], domain=self.domain, metric=metric, metric_kind=tpl["kind"],
            graph=graph,
            periods=[Period(0, d, legs, den_probe=den_probe)],
            binding=binding_info, rule_audit=rule_audit,
            route=[route] if route else [],
            g0={"product_versions_valid_asof": "product_version×asof_point",
                "online_group_order_cnt": "channel_group×asof",
                "offline_group_order_cnt": "channel_group×asof"}.get(metric, "task_set×asof"),
            disclosure=dis,
            emit_sql=emit)


# ===========================================================================
# aibuy（A 原语缺席：按 compiler.py 现行等价物装配，逐条记 spec_deviations）
# ===========================================================================
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

_DEV_AIBUY_A = ("aibuy 的 A 原语（gov_valid_time_anchor / gov_temporal_binding）为集成期"
                "按 domain_config DWD date_field + 现役 compiler.py BINDINGS 等价物**补登记**"
                "的行（v2026.06.23 源 gov_seed 无 A 文件，与 email 同型）：锚/绑定/覆盖方式"
                "自此读自治理表而非编译器字典，但登记行本身是 agent-authored，非上游生产"
                "产出——provenance 见 INTEGRATION_REPORT。user_profile_signal.recorded_at 的"
                "coverage_mode='hull_left_open' 是对 C3 定义 3.3 cm_a∈{hull,strict_member} 的"
                "实现扩展（DEVIATION-1 族，与 email 的 hull_right_open 同型），兑现 C4 §4.4"
                "标签归一注记钉定的金标 AIBUY-Q6=missing-caliber(MC(ii))")


class AibuyAdapter:
    domain = "aibuy"
    BINDINGS = {
        "reco_snapshot_cnt_asof": {"binding_id": "B-AIBUY-RECO-ASOF-CUM",
                                   "anchor": "recommendation_snapshots.created_at",
                                   "window": "cumulative", "kind": "atomic"},
        "reco_with_evidence_cnt_asof": {"binding_id": "B-AIBUY-RECO-ASOF-CUM",
                                        "anchor": "recommendation_snapshots.created_at (FK carry via snapshot_id)",
                                        "window": "cumulative", "kind": "atomic"},
        "reco_top1_cnt_day": {"binding_id": "B-AIBUY-RECO-DAY",
                              "anchor": "recommendation_snapshots.created_at (FK carry via snapshot_id)",
                              "window": "day", "kind": "atomic"},
        "reco_items_per_snapshot_asof": {"binding_id": "B-AIBUY-RECO-RATIO-SAMEWIN",
                                         "anchor": "recommendation_snapshots.created_at",
                                         "window": "cumulative", "kind": "same_window_ratio"},
        "reco_grounding_coverage_rate": {"binding_id": "B-AIBUY-GROUNDING-RATE-NOCALIBER",
                                         "anchor": "recommendation_snapshots.created_at",
                                         "window": "cumulative", "kind": "scoped_ratio"},
        "profile_high_sensitivity_share_asof": {"binding_id": "B-AIBUY-PROFILE-ASOF",
                                                "anchor": "user_profile_signal.recorded_at",
                                                "window": "cumulative", "kind": "scoped_ratio"},
    }

    def __init__(self, dir_path: pathlib.Path):
        self.db = str(dir_path / "warehouse.duckdb")

    def intent(self, q: dict, con) -> Intent:
        metric = q.get("metric")
        graph = _graph_pin(con, "aibuy")
        pols = _policies(con)
        as_of = q.get("as_of", "")
        if metric not in self.BINDINGS:
            return Intent(qid=q["qid"], domain="aibuy", metric=metric, metric_kind="ratio",
                          graph=graph, periods=[Period(0, "-", [])], binding=None, route=[],
                          g0="requested",
                          disclosure=Disclosure(True, pols, []),
                          mc_missing={"metric": metric, "caliber_key": None,
                                      "assertion": "未注册指标：无绑定可依 → MC(i)"},
                          deviations=[_DEV_AIBUY_A])
        b = self.BINDINGS[metric]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            return Intent(qid=q["qid"], domain="aibuy", metric=metric,
                          metric_kind="atomic", graph=graph, periods=[Period(0, "-", [])],
                          binding=None, route=[], g0="requested",
                          disclosure=Disclosure(True, pols, []),
                          oov_parse={"as_of": as_of}, deviations=[_DEV_AIBUY_A])
        window = (Window.cumulative_to(as_of) if b["window"] == "cumulative"
                  else Window.point(as_of))

        # A 原语读自治理表（集成期补登记；见 _DEV_AIBUY_A）：锚对象/有效时间列/
        # coverage_mode 逐锚查键，覆盖检查按声明 mode 重演（D3）
        anchors = {r[0]: {"semantic_object": r[1], "col": r[2], "coverage_mode": r[3]}
                   for r in con.execute(
                       "SELECT anchor_id, semantic_object, effective_date, coverage_mode "
                       "FROM gov_valid_time_anchor WHERE domain='aibuy'").fetchall()}

        def cov_for(anchor_id):
            a = anchors.get(anchor_id)
            if not a:
                return None
            return _hull_cov(con, anchor_id, a["semantic_object"], a["col"],
                             mode=a.get("coverage_mode"))

        def leg(role, anchor=None):
            aid = anchor or b["anchor"]
            return Leg(role=role, anchor_id=aid, registered=aid in anchors,
                       required_anchor_id=aid, window=window,
                       granule="day", coverage=cov_for(aid))

        mk = {"qid": q["qid"], "domain": "aibuy", "metric": metric, "graph": graph,
              "deviations": [_DEV_AIBUY_A]}

        if metric == "reco_snapshot_cnt_asof":
            legacy = f"CAST(created_at AS DATE) <= DATE '{as_of}'"

            def sql(bound):
                return ("SELECT COUNT(*) AS v FROM ods_pg_recommendation_snapshots WHERE "
                        + _bound_pred(bound, 0, "atom", "CAST(created_at AS DATE)", legacy))
            return Intent(**mk, metric_kind="atomic",
                          periods=[Period(0, as_of, [leg("atom")])],
                          binding={"binding_id": b["binding_id"], "rule": None,
                                   "adm_check_mode": "trivial_true"},
                          route=[], g0="snapshot_set×asof",
                          disclosure=Disclosure(True, pols, _touched(
                              pols, {("ods_pg_recommendation_snapshots", "created_at")})),
                          emit_sql=sql)
        if metric == "reco_with_evidence_cnt_asof":
            legacy = f"dt <= DATE '{as_of}'"

            def sql(bound):
                return ("SELECT SUM(has_evidence) AS v FROM dwd_aibuy_reco_item_di WHERE "
                        + _bound_pred(bound, 0, "atom", "dt", legacy))
            return Intent(**mk, metric_kind="atomic",
                          periods=[Period(0, as_of, [leg("atom")])],
                          binding={"binding_id": b["binding_id"], "rule": None,
                                   "adm_check_mode": "trivial_true"},
                          route=[], g0="reco_item_set×asof",
                          disclosure=Disclosure(True, pols, _touched(
                              pols, {("dwd_aibuy_reco_item_di", "has_evidence"),
                                     ("dwd_aibuy_reco_item_di", "dt")})),
                          emit_sql=sql)
        if metric == "reco_top1_cnt_day":
            legacy = f"dt = DATE '{as_of}'"

            def sql(bound):
                return ("SELECT SUM(is_top1) AS v FROM dwd_aibuy_reco_item_di WHERE "
                        + _bound_pred(bound, 0, "atom", "dt", legacy))
            return Intent(**mk, metric_kind="atomic",
                          periods=[Period(0, as_of, [leg("atom")])],
                          binding={"binding_id": b["binding_id"], "rule": None,
                                   "adm_check_mode": "trivial_true"},
                          route=[], g0="reco_item_set×day",
                          disclosure=Disclosure(True, pols, _touched(
                              pols, {("dwd_aibuy_reco_item_di", "is_top1"),
                                     ("dwd_aibuy_reco_item_di", "dt")})),
                          emit_sql=sql)
        if metric == "reco_items_per_snapshot_asof":
            den_legacy = f"CAST(created_at AS DATE) <= DATE '{as_of}'"
            num_legacy = f"dt <= DATE '{as_of}'"

            def den_probe(bound_windows, _b={}):
                w = bound_windows.get("denominator")
                pred = _iv_pred("CAST(created_at AS DATE)", w) if w else den_legacy
                sql = ("SELECT COUNT(*) FROM ods_pg_recommendation_snapshots "
                       f"WHERE {pred}")
                v = con.execute(sql).fetchone()[0]
                return {"sql": sql, "observed": v, "mu_den": float(v or 0)}

            def sql(bound):
                return ("SELECT ROUND("
                        "(SELECT COUNT(*) FROM dwd_aibuy_reco_item_di WHERE "
                        + _bound_pred(bound, 0, "numerator", "dt", num_legacy) +
                        ") / NULLIF((SELECT COUNT(*) FROM ods_pg_recommendation_snapshots "
                        "WHERE "
                        + _bound_pred(bound, 0, "denominator",
                                      "CAST(created_at AS DATE)", den_legacy) +
                        "), 0), 6) AS v")
            legs = [leg("numerator",
                        "recommendation_snapshots.created_at (FK carry via snapshot_id)"),
                    leg("denominator", "recommendation_snapshots.created_at")]
            # ρ：FK 恒等路由（reco_item --snapshot_id--> reco_snapshot），R_v 的机器可读
            # 归属见 gov_caliber_routing.metric（集成期补登记）。比率型必须携可重算路由
            # （C3 定义 3.10(b2)）——先前以 spec_deviation 免除该要求，偏离随登记消解。
            route = _route_row(con, "reco_item_to_snapshot")
            return Intent(**mk, metric_kind="ratio",
                          periods=[Period(0, as_of, legs, den_probe=den_probe)],
                          binding={"binding_id": b["binding_id"],
                                   "rule": "same_valid_time_window",
                                   "adm_check_mode": "trivial_true"},
                          rule_audit=RuleAudit(binding_id=b["binding_id"],
                                               rule="same_valid_time_window",
                                               adm_check_mode="trivial_true", g_cmp="day"),
                          route=[route] if route else [],
                          g0="reco_item_per_snapshot×asof",
                          disclosure=Disclosure(True, pols, _touched(
                              pols, {("dwd_aibuy_reco_item_di", "dt"),
                                     ("ods_pg_recommendation_snapshots", "created_at")})),
                          emit_sql=sql)
        if metric == "reco_grounding_coverage_rate":
            # MC(i) 见证探针 = R_v(m) 查键（C3 定义 3.16(i)）：按 metric 归属列查
            # 该度量自己的率值口径路由。原 '%reco%' 模糊匹配是"全域无 reco 字样路由"
            # 的近似，随 R_v 归属列落地后改为精确查键（同域存在结构性 FK 恒等路由
            # reco_item_to_snapshot 并不使本度量获得率值分母口径）。
            probe_sql = ("SELECT COUNT(*) FROM gov_caliber_routing "
                         "WHERE domain='aibuy' AND metric='reco_grounding_coverage_rate'")
            n = con.execute(probe_sql).fetchone()[0]
            legs = [Leg("numerator", b["anchor"], True, b["anchor"], window, granule="day"),
                    Leg("denominator", None, False, None, window, granule="day")]
            return Intent(**mk, metric_kind="scoped_ratio",
                          periods=[Period(0, as_of, legs)],
                          binding={"binding_id": b["binding_id"], "rule": None,
                                   "adm_check_mode": "trivial_true"},
                          route=[], g0="reco_item_set×asof",
                          disclosure=Disclosure(True, pols, []),
                          mc_missing={"metric": metric, "caliber_key": None,
                                      "assertion": "R_v(reco_grounding_coverage_rate)↑：治理图未"
                                                   "登记该度量的率值口径路由（domain_config ADS: "
                                                   "reco grounding 仅 atomic，无分母人口口径）"
                                                   " → MC(i)；分母角色记 I2'(a) 显式空指派",
                                      "probe": {"kind": "ROUTE_LOOKUP", "sql": probe_sql,
                                                "observed": n}})
        # profile_high_sensitivity_share_asof
        m = _UUID_RE.search(q.get("question_zh", ""))
        if not m:
            return Intent(**mk, metric_kind="scoped_ratio",
                          periods=[Period(0, as_of, [])], binding=None, route=[],
                          g0="session_id×asof", disclosure=Disclosure(True, pols, []),
                          oov_scope={"anchor_id": b["anchor"], "coverage_mode": None,
                                     "requested": Window.cumulative_to(as_of).to_json(),
                                     "assertion": "无法定位会话主体：请求窗无法落在任何有效锚域"
                                                  "（现行等价物 OOV 分支）"})
        sid = m.group(0)
        caliber_probe_sql = ("SELECT COUNT(*) FROM gov_caliber_routing "
                             "WHERE domain='aibuy' AND caliber_key='profile_sensitive_to_session'")
        n_caliber = con.execute(caliber_probe_sql).fetchone()[0]
        route = _route_row(con, "profile_sensitive_to_session")
        legs = [leg("numerator"), leg("denominator")]
        mc = None
        if n_caliber == 0:
            mc = {"metric": metric, "caliber_key": "profile_sensitive_to_session",
                  "assertion": "caliber 未注册 → MC(i)",
                  "probe": {"kind": "ROUTE_LOOKUP", "sql": caliber_probe_sql, "observed": 0}}

        def den_probe(bound_windows):
            # 探针窗必须是**认证窗本身**的字面谓词（C5 V6c：校验器按 α(den) 的窗重演；
            # 先前 `recorded_at < (DATE 'd' + INTERVAL 1 DAY)` 的算术上界在语法层不可解，
            # 指称集读作 ⊤，等于把探针窗留白）
            w = bound_windows.get("denominator") or window
            sql = ("SELECT COUNT(*) FROM ods_pg_user_profile_signal "
                   f"WHERE session_id = '{sid}' AND {_iv_pred('recorded_at', w)}")
            v = con.execute(sql).fetchone()[0]
            return {"sql": sql, "observed": v, "mu_den": float(v or 0)}

        def emit_sql_fn(bound):
            pred = _bound_pred(bound, 0, "numerator", "recorded_at",
                               _iv_pred("recorded_at", window))
            return ("SELECT ROUND(SUM(CASE WHEN sensitivity_level='sensitive' THEN 1 ELSE 0 END) "
                    "/ NULLIF(COUNT(*), 0), 6) AS v "
                    "FROM ods_pg_user_profile_signal "
                    f"WHERE session_id = '{sid}' AND {pred}")
        return Intent(**mk, metric_kind="scoped_ratio",
                      periods=[Period(0, as_of, legs, den_probe=den_probe)],
                      binding={"binding_id": b["binding_id"],
                               "rule": "same_valid_time_window",
                               "adm_check_mode": "trivial_true"},
                      rule_audit=RuleAudit(binding_id=b["binding_id"],
                                           rule="same_valid_time_window",
                                           adm_check_mode="trivial_true", g_cmp="day"),
                      route=[route] if route else [],
                      g0="session_id×asof",
                      disclosure=Disclosure(True, pols, _touched(
                          pols, {("ods_pg_user_profile_signal", "sensitivity_level"),
                                 ("ods_pg_user_profile_signal", "session_id"),
                                 ("ods_pg_user_profile_signal", "recorded_at")})),
                      mc_missing=mc,
                      emit_sql=emit_sql_fn,
                      notes=["probes 段 ROUTE_LOOKUP：caliber 注册探针 observed="
                             f"{n_caliber}"])


# ===========================================================================
# email（gov A 表在仓内实存（agent-authored 版式补齐）；按表装配）
# ===========================================================================
_DEV_EMAIL_COV = ("email 锚覆盖按右开包络 [min_dt, +inf) 实施（上端不设 OOV 闸）：C3 定义 3.3 "
                  "hull=[min,max] 的字面读法会把 EMAIL-ASOF-06（2026-05 月窗 > 金标覆盖上端 "
                  "2026-04-14）判 OOV，与冻结裁决（C4 §4.4 标签归一注记/C5 G2/D1：该题=missing-"
                  "caliber MC(ii) 同窗分母质量空）冲突；按冻结金标语义取事件流锚右开覆盖读法，"
                  "记为对 hull 字面语义的实现偏离")


class EmailAdapter:
    domain = "email"
    _LABEL_ANCHOR = "email_label_sent_time"
    _MESSAGE_ANCHOR = "email_message_mail_time"
    _METRICS = {
        "price_pressure_rate": ("email_redline_rate_temporal_align", "thread",
                                "hit_price_pressure=1"),
        "quality_risk_rate": ("email_redline_rate_temporal_align", "thread",
                              "hit_quality_risk=1"),
        "churn_risk_rate": ("email_redline_rate_temporal_align", "thread",
                            "hit_churn_risk=1"),
        "stage_thread_share": ("email_funnel_share_temporal_align", "thread",
                               "business_stage='{param}'"),
        "needs_review_rate": ("email_label_quality_temporal_align", "label", None),
        "avg_confidence": ("email_label_quality_temporal_align", "label", None),
    }
    _CALIBER_KEY = {"thread": "funnel_email_to_thread", "label": "label_email_grain"}

    def __init__(self, dir_path: pathlib.Path):
        self.db = str(dir_path / "warehouse.duckdb")

    @staticmethod
    def _window(as_of: str):
        as_of = str(as_of).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            return Window.cumulative_to(as_of), f"dt <= DATE '{as_of}'"
        if re.fullmatch(r"\d{4}-\d{2}", as_of):
            y, m = int(as_of[:4]), int(as_of[5:7])
            last = calendar.monthrange(y, m)[1]
            return (Window.month(as_of),
                    f"dt BETWEEN DATE '{y:04d}-{m:02d}-01' AND DATE '{y:04d}-{m:02d}-{last:02d}'")
        if re.fullmatch(r"\d{4}", as_of):
            return (Window.year(as_of),
                    f"dt BETWEEN DATE '{as_of}-01-01' AND DATE '{as_of}-12-31'")
        raise ValueError(f"unparseable as_of: {as_of!r}")

    def intent(self, q: dict, con) -> Intent:
        metric_spec = q["metric"]
        as_of = q["as_of"]
        graph = _graph_pin(con, "email")
        pols = _policies(con)
        dis = Disclosure(True, pols, [])  # 六题均只读 dwd_email_*，策略表列不被触及

        requested_den = self._LABEL_ANCHOR
        base = metric_spec
        if "@" in base:
            base, override = base.split("@", 1)
            if override == "message_denominator":
                requested_den = self._MESSAGE_ANCHOR
            else:
                raise ValueError(f"unknown denominator override: {override!r}")
        param = None
        if ":" in base:
            base, param = base.split(":", 1)
        if base not in self._METRICS:
            return Intent(qid=q["qid"], domain="email", metric=metric_spec,
                          metric_kind="ratio", graph=graph, periods=[Period(0, "-", [])],
                          binding=None, route=[], g0="requested", disclosure=dis,
                          mc_missing={"metric": metric_spec, "caliber_key": None,
                                      "assertion": "unknown metric → MC(i)"})
        binding_id, caliber, num_case = self._METRICS[base]
        try:
            w0, pred = self._window(as_of)
        except ValueError:
            return Intent(qid=q["qid"], domain="email", metric=base, metric_kind="ratio",
                          graph=graph, periods=[Period(0, "-", [])], binding=None,
                          route=[], g0="requested", disclosure=dis,
                          oov_parse={"as_of": as_of})

        brow = con.execute(
            "SELECT numerator_anchor, denominator_anchor, rule FROM gov_temporal_binding "
            "WHERE binding_id = ?", [binding_id]).fetchone()
        if brow is None:
            return Intent(qid=q["qid"], domain="email", metric=base, metric_kind="ratio",
                          graph=graph, periods=[Period(0, "-", [])], binding=None,
                          route=[], g0="requested", disclosure=dis,
                          mc_missing={"metric": base, "caliber_key": None,
                                      "assertion": "治理图无该指标时态绑定 → MC(i)"})
        req_num, req_den, rule = brow
        anchors = {r[0]: {"semantic_object": r[1], "col": r[2]} for r in con.execute(
            "SELECT anchor_id, semantic_object, effective_date FROM gov_valid_time_anchor"
        ).fetchall()}

        def mk_leg(role, anchor_id, required):
            a = anchors[anchor_id]
            return Leg(role=role, anchor_id=anchor_id, registered=True,
                       required_anchor_id=required, window=w0, granule="day",
                       declared_override=(anchor_id != required),
                       coverage=_hull_cov(con, anchor_id, a["semantic_object"], a["col"],
                                          lo_only=True, deviation=_DEV_EMAIL_COV))

        legs = [mk_leg("numerator", self._LABEL_ANCHOR, req_num),
                mk_leg("denominator", requested_den, req_den)]

        def den_probe(bound_windows):
            w = bound_windows["denominator"]
            if caliber == "thread":
                sql = (f"SELECT COUNT(DISTINCT thread_id) FROM dwd_email_label_di "
                       f"WHERE {_iv_pred('dt', w)}")
            else:
                sql = (f"SELECT COUNT(email_id) FROM dwd_email_label_di "
                       f"WHERE {_iv_pred('dt', w)}")
            v = con.execute(sql).fetchone()[0]
            return {"sql": sql, "observed": v, "mu_den": float(v or 0)}

        route = _route_row(con, self._CALIBER_KEY[caliber])

        def emit(bound):
            # 认证窗 w*（覆盖 hull 边裁剪后）落谓词；未裁剪时保留现役模板形态
            p = _bound_pred(bound, 0, "numerator", "dt", pred, w0=w0)
            if base in ("price_pressure_rate", "quality_risk_rate", "churn_risk_rate",
                        "stage_thread_share"):
                case = num_case.format(param=param) if param is not None else num_case
                return (
                    "SELECT ROUND(COUNT(DISTINCT CASE WHEN {case} THEN thread_id END) * 1.0 "
                    "/ NULLIF(COUNT(DISTINCT thread_id),0), 6) AS {name} "
                    "FROM dwd_email_label_di WHERE {pred}"
                ).format(case=case, name=base, pred=p)
            if base == "needs_review_rate":
                return ("SELECT ROUND(SUM(needs_review) * 1.0 / NULLIF(COUNT(email_id),0), 6) "
                        f"AS needs_review_rate FROM dwd_email_label_di WHERE {p}")
            return ("SELECT ROUND(SUM(confidence) * 1.0 / NULLIF(COUNT(email_id),0), 6) "
                    f"AS avg_confidence FROM dwd_email_label_di WHERE {p}")

        return Intent(
            qid=q["qid"], domain="email", metric=base, metric_kind="ratio",
            graph=graph, periods=[Period(0, as_of, legs, den_probe=den_probe)],
            binding={"binding_id": binding_id, "rule": rule,
                     "numerator_anchor": req_num, "denominator_anchor": req_den,
                     "adm_check_mode": "trivial_true"},
            rule_audit=RuleAudit(binding_id=binding_id, rule=rule,
                                 adm_check_mode="trivial_true", g_cmp="day"),
            route=[route] if route else [],
            g0=("thread×window" if caliber == "thread" else "email×window"),
            disclosure=dis, emit_sql=emit)


# ===========================================================================
# public（扰动库：快照区间锚；无 gov_semantic_graph_version / 路由 / 披露表）
# ===========================================================================
_DEV_PUBLIC = ("public 仓无 gov_semantic_graph_version / gov_caliber_routing / "
               "gov_disclosure_policy 表：graph_pin 记 version_table_absent（C5 缺口 G7 "
               "缺席语义），版本轴取单一合成在位版本；binding 行无 rule 列，规则记 "
               "asof-snapshot-selection（快照区间选择），锚型按区间锚 strict_member 读")


class PublicAdapter:
    domain = "public"

    def __init__(self, dir_path: pathlib.Path):
        self.db = str(dir_path / "warehouse.duckdb")

    @staticmethod
    def _normalize_as_of(as_of: str) -> str:
        as_of = str(as_of).strip()
        if len(as_of) == 7:
            as_of = as_of + "-01"
        datetime.date.fromisoformat(as_of)
        return as_of

    def intent(self, q: dict, con) -> Intent:
        graph = _graph_pin(con, q.get("domain", "public"))
        dis = Disclosure(policy_table_present=False)
        try:
            day = self._normalize_as_of(q["as_of"])
        except ValueError:
            return Intent(qid=q["qid"], domain=q.get("domain", "public"),
                          metric=q.get("metric"), metric_kind="atomic", graph=graph,
                          periods=[Period(0, "-", [])], binding=None, route=[],
                          g0="requested", disclosure=dis,
                          oov_parse={"as_of": q.get("as_of")},
                          deviations=[_DEV_PUBLIC])

        if q.get("binding_id"):
            row = con.execute(
                "SELECT binding_id, semantic_object, select_expr, where_expr "
                "FROM gov_temporal_binding WHERE binding_id = ?", [q["binding_id"]]).fetchone()
        else:
            row = con.execute(
                "SELECT binding_id, semantic_object, select_expr, where_expr "
                "FROM gov_temporal_binding WHERE metric = ?", [q["metric"]]).fetchone()
        if row is None:
            return Intent(qid=q["qid"], domain=q.get("domain", "public"),
                          metric=q.get("metric"), metric_kind="atomic", graph=graph,
                          periods=[Period(0, "-", [])], binding=None, route=[],
                          g0="requested", disclosure=dis,
                          mc_missing={"metric": q.get("metric"), "caliber_key": None,
                                      "assertion": "gov_temporal_binding 查无该 metric/binding"
                                                   " → MC(i)"},
                          deviations=[_DEV_PUBLIC])
        binding_id, semantic_object, select_expr, where_expr = row
        holder = {}

        def coverage(leg: Leg) -> CovResult:
            sql = ("SELECT anchor_id, snapshot_table, valid_from, valid_to "
                   "FROM gov_valid_time_anchor WHERE semantic_object = "
                   f"'{semantic_object}' AND valid_from <= CAST('{day}' AS DATE) "
                   f"AND valid_to >= CAST('{day}' AS DATE) ORDER BY valid_from DESC")
            rows = con.execute(sql).fetchall()
            all_rows = con.execute(
                "SELECT anchor_id, valid_from, valid_to FROM gov_valid_time_anchor "
                "WHERE semantic_object = ? ORDER BY valid_from", [semantic_object]).fetchall()
            env_brief = "; ".join(f"{r[0]}:[{r[1]},{r[2]}]" for r in all_rows)
            if rows:
                holder["anchor_id"], holder["snapshot_table"] = rows[0][0], rows[0][1]
                leg.anchor_id = rows[0][0]  # 覆盖命中的锚行（≺_det: valid_from 最新者先）
                return CovResult("strict_member", leg.window, False, True, env_brief,
                                 probe={"kind": "COVERAGE", "anchor_id": rows[0][0],
                                        "coverage_mode": "strict_member", "sql": sql,
                                        "observed": len(rows)})
            return CovResult("strict_member", Window.empty(), True, False, env_brief,
                             probe={"kind": "COVERAGE", "anchor_id": semantic_object,
                                    "coverage_mode": "strict_member", "sql": sql,
                                    "observed": 0})

        leg = Leg(role="atom", anchor_id=semantic_object, registered=True,
                  required_anchor_id=semantic_object, window=Window.point(day),
                  granule="itv", coverage=coverage)

        def emit(bound):
            sql = "SELECT %s FROM %s" % (select_expr, holder["snapshot_table"])
            if where_expr:
                sql += " WHERE %s" % where_expr
            return sql

        return Intent(
            qid=q["qid"], domain=q.get("domain", "public"), metric=q.get("metric"),
            metric_kind="atomic", graph=graph,
            periods=[Period(0, day, [leg])],
            binding={"binding_id": binding_id, "rule": "asof-snapshot-selection",
                     "adm_check_mode": "trivial_true",
                     "note": "取 valid_from<=as_of<=valid_to 的快照表；无命中拒答 out-of-validity"},
            route=[], g0="snapshot_table×asof_point", disclosure=dis,
            emit_sql=emit, deviations=[_DEV_PUBLIC])


# ===========================================================================
# 注册表与驱动
# ===========================================================================
ADAPTERS = {
    "rma": RmaAdapter,
    "quality_voc": QualityVocAdapter,
    "domestic_newprod": DomesticNewprodAdapter,
    "aibuy": AibuyAdapter,
    "email": EmailAdapter,
    "public": PublicAdapter,
}


def adapter_for(domain: str, dir_path) -> object:
    # pilot2 九公开库走通用 gov_* 种子适配器（adapters_pilot2；域名即键）
    from .adapters_pilot2 import P2_DOMAINS, Pilot2Adapter
    if domain in P2_DOMAINS:
        return Pilot2Adapter(domain, pathlib.Path(dir_path))
    key = "public" if str(domain).startswith("public") else domain
    return ADAPTERS[key](pathlib.Path(dir_path))
