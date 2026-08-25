#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adapters_pilot2.py — pilot2 九公开库（BIRD dev ×8 + Spider world_1）的通用装配层。

与 adapters.py 的五生产域适配器同职责、不同素材面：pilot2 的治理状态 G_v 是十表
全量种子（gov_semantic_graph_version / gov_semantic_node / gov_metric /
gov_measure_def / gov_metric_alias / gov_caliber_routing / gov_valid_time_anchor /
gov_temporal_binding / gov_granularity_edge / gov_disclosure_policy），每域两提交
版本并存（committed_at 真时间戳全序 → ver(T) 非平凡，C3 定义 3.5 首次以
timestamps 模式实例化）。

装配链（DESIGN_SPEC §3.3 的编译器侧承接；判定全在 core.mlr_compile）：
  T=declared_at → ver(T)（含显式钉 → off_diagonal 承诺，行 2a）
  → metric_alias→metric_id（映射随版本变）
  → 度量/腿装配（gov_measure_def 谓词原子 + gov_caliber_routing hop → 程序化拼 SQL）
  → 腿→锚→窗现算（覆盖域不物化：hull=min/max、strict_member=distinct 集，全部对 D 探针）
  → 守卫材料注入（AM(i) 改锚 / AM(ii) 跨窗 / AM(iii) 窗-粒度 g^cmp / AM(iv)
    window_realization_symdiff 审计 / MC(i) dst_caliber='none' / MC(ii) μ_den 探针）
  → 披露装配（C4 行 12–14 首次非退化触发：粒度爬升链 Γ=lattice_levels、
    SUPPMIN_π(ℓ) 逐级探针、掩码闭包 μ*、名录刚性 S-M2 封顶 → DB）。

纪律：只读题面评测可见字段（qid/domain/as_of/declared_at/metric_alias/scope/
pinned_version/cross_window/anchor_override/window_request/requested_granularity/
requested_time_gran/presentation/periods）；金标侧字段（metric/expected_kind/
gold_*/windows/rewrite/refusal_*/notes）一律不触。不 import 校验器侧代码，不
import pilot2/build 路径 B（govchain_resolver）——本文件是双人规则之外的第三次
独立实现，语义以 theory/C3–C5 与 gov_* 登记为准。纯 python3 + duckdb。
"""
from __future__ import annotations

import datetime
import json
import pathlib
from typing import Optional

from .core import (
    CovResult, Disclosure, Intent, Leg, Period, RuleAudit, Window,
)

_DAY = datetime.timedelta(days=1)

P2_DOMAINS = {
    "financial", "card_games", "codebase_community", "debit_card_specializing",
    "european_football_2", "california_schools", "thrombosis_prediction",
    "formula_1", "world_1",
}

_GOV_TABLES = (
    "gov_semantic_graph_version", "gov_semantic_node", "gov_metric",
    "gov_measure_def", "gov_metric_alias", "gov_caliber_routing",
    "gov_valid_time_anchor", "gov_temporal_binding", "gov_granularity_edge",
    "gov_disclosure_policy",
)
_JSON_COLS = {"scope_keys", "preds", "join_on", "lattice_levels", "carry",
              "band_bounds", "group_cols", "derived", "cols"}


def _jload(v):
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("[") or s.startswith("{"):
            try:
                return json.loads(s)
            except ValueError:
                return v
    return v


def _lit(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _day_expr(alias, col):
    """有效日列的日粒规范表达（DATE/TIMESTAMP/VARCHAR 'YYYY-MM-DD*' 统一）。"""
    return f'substr(CAST({alias}."{col}" AS VARCHAR),1,10)'


def _tok_expr(alias, col):
    return f'CAST({alias}."{col}" AS VARCHAR)'


def _next_day(d: str) -> str:
    return (datetime.date.fromisoformat(d) + _DAY).isoformat()


def _month_lo_hi(ym: str):
    y, m = int(ym[:4]), int(ym[5:7])
    lo = datetime.date(y, m, 1)
    hi = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
    return lo, hi


def _ym_of(day: datetime.date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


class _Refuse(Exception):
    """装配期即判定成立的守卫（版本轴 OOV 等）；核心守卫仍走 mlr_compile。"""

    def __init__(self, payload_field: str, payload: dict):
        self.payload_field = payload_field
        self.payload = payload


class P2Gov:
    """warehouse 内 gov_* 十表的只读装载（G_v；JSON 列解码，逐版本过滤查询）。"""

    def __init__(self, con):
        self.t = {}
        for tn in _GOV_TABLES:
            try:
                cur = con.execute(f'SELECT * FROM "{tn}"')
            except Exception:
                self.t[tn] = []
                continue
            cols = [d[0] for d in cur.description]
            if cols == ["placeholder"]:
                self.t[tn] = []
                continue
            rows = []
            for r in cur.fetchall():
                d = dict(zip(cols, r))
                for k in list(d):
                    if k in _JSON_COLS:
                        d[k] = _jload(d[k])
                rows.append(d)
            self.t[tn] = rows

    def rows(self, tn, gv=None, **filt):
        out = []
        for r in self.t[tn]:
            if gv is not None and r.get("graph_version") != gv:
                continue
            if all(r.get(k) == v for k, v in filt.items()):
                out.append(r)
        return out


class _LegAsm:
    """一条腿的 SQL 装配面：基表 + 治理 hop 树 + 谓词原子 + scope + 窗谓词。

    与路径 B 的 LegPlan 同构不同源：hop 顺序 (hop_seq, routing_id) 字典序确定性，
    自连接（src==dst）只承载连接语义（锚/谓词仍落基别名）。"""

    def __init__(self, gov: P2Gov, gv: str, metric_id: str, leg: str,
                 measures: list, node_table, scope: dict):
        self.gov, self.gv = gov, gv
        self.metric_id, self.leg = metric_id, leg
        self.measures = measures
        self.node_table = node_table
        self.scope = dict(scope or {})
        self.aliases = {measures[0]["node_id"]: "t0"}
        self.base_node = measures[0]["node_id"]
        self.joins = []
        self.route_rows = []
        self._ai = 0
        for legname in (leg, "scope", "entity"):
            hops = sorted(gov.rows("gov_caliber_routing", gv=gv,
                                   metric_id=metric_id, leg=legname),
                          key=lambda r: (r.get("hop_seq") or 0, r["routing_id"]))
            for h in hops:
                self.route_rows.append(h)
                if h.get("dst_caliber") == "none":
                    raise _Refuse("mc_missing", {
                        "metric": metric_id, "caliber_key": h["routing_id"],
                        "dst_caliber": "none",
                        "assertion": "R_v 路由 dst_caliber='none'（reference-only，"
                                     "不可重算）→ MC(i)",
                        "probe": {"kind": "ROUTE_LOOKUP",
                                  "sql": ("SELECT routing_id, dst_caliber FROM "
                                          "gov_caliber_routing WHERE routing_id = "
                                          f"'{h['routing_id']}' AND graph_version = '{gv}'"),
                                  "observed": [h["routing_id"], "none"]}})
                self._hop(h)

    def _hop(self, h):
        src, dst = h["src_node"], h["dst_node"]
        if not h.get("join_on"):
            return
        if src not in self.aliases:
            return
        if dst in self.aliases and dst != src:
            return
        self._ai += 1
        a = f"t{self._ai}"
        on = " AND ".join(f'{self.aliases[src]}."{sc}" = {a}."{dc}"'
                          for sc, dc in h["join_on"])
        self.joins.append((a, self.node_table(dst), on))
        if dst != src:
            self.aliases[dst] = a

    # -- where 部件 ----------------------------------------------------------
    def pred_parts(self, drop_scope_keys=()):
        parts = []
        for m in self.measures:
            for p in (m.get("preds") or []):
                node = p.get("node") or m["node_id"]
                if node not in self.aliases:
                    continue
                a = self.aliases[node]
                col, op, v = p["col"], p["op"], p.get("value")
                if op == "in":
                    parts.append(f'{a}."{col}" IN ({", ".join(_lit(x) for x in v)})')
                elif op == "is_null":
                    parts.append(f'{a}."{col}" IS NULL')
                elif op == "not_null":
                    parts.append(f'{a}."{col}" IS NOT NULL')
                elif op == ">col":
                    parts.append(f'{a}."{col}" > {a}."{v}"')
                elif op == "=col":
                    parts.append(f'{a}."{col}" = {a}."{v}"')
                else:
                    parts.append(f'{a}."{col}" {op} {_lit(v)}')
        for k, v in self.scope.items():
            if k in drop_scope_keys:
                continue
            hit = None
            for node, a in self.aliases.items():
                sk = self._node_scope_keys(node)
                if k in sk:
                    hit = (a, sk[k])
                    break
            if hit is None:
                raise RuntimeError(f"scope key {k!r} unresolved on {self.metric_id}/{self.leg}")
            parts.append(f'{hit[0]}."{hit[1]}" = {_lit(v)}')
        return parts

    def _node_scope_keys(self, node_id):
        r = self.gov.rows("gov_semantic_node", gv=self.gv, node_id=node_id)
        return (r[0].get("scope_keys") or {}) if r else {}

    def window_pred(self, anchor: dict, pinfo: Optional[tuple]) -> list:
        if pinfo is None:
            return []
        node = anchor["node_id"]
        if node not in self.aliases:
            raise RuntimeError(f"anchor node {node} not joined for {self.metric_id}/{self.leg}")
        a = self.aliases[node]
        kind = pinfo[0]
        if kind == "day_range":            # [lo, hi_excl)
            e = _day_expr(a, anchor["effective_col"])
            return [f"{e} >= '{pinfo[1]}'", f"{e} < '{pinfo[2]}'"]
        if kind == "day_le":               # cum [lo, hi_incl]
            e = _day_expr(a, anchor["effective_col"])
            return [f"{e} >= '{pinfo[1]}'", f"{e} <= '{pinfo[2]}'"]
        if kind == "day_eq":
            e = _day_expr(a, anchor["effective_col"])
            return [f"{e} = '{pinfo[1]}'"]
        if kind == "token_eq":
            e = _tok_expr(a, anchor["effective_col"])
            return [f"{e} = '{pinfo[1]}'"]
        if kind == "token_range":          # [lo, hi] inclusive tokens
            e = _tok_expr(a, anchor["effective_col"])
            return [f"{e} >= '{pinfo[1]}'", f"{e} <= '{pinfo[2]}'"]
        if kind == "point_in_effect":
            vf, vtc, d = anchor["vf_col"], anchor["vtc_col"], pinfo[1]
            evf, evtc = _day_expr(a, vf), _day_expr(a, vtc)
            return [f"{evf} <= '{d}'", f'({a}."{vtc}" IS NULL OR {evtc} > \'{d}\')']
        raise RuntimeError(f"window pred kind {kind}")

    def sql(self, select, anchor=None, pinfo=None, drop_scope_keys=(), group=False):
        s = f'SELECT {select} FROM "{self.node_table(self.base_node)}" t0'
        for a, tab, on in self.joins:
            s += f' INNER JOIN "{tab}" {a} ON {on}'
        parts = self.pred_parts(drop_scope_keys)
        if anchor is not None:
            parts += self.window_pred(anchor, pinfo)
        if parts:
            s += " WHERE " + " AND ".join(parts)
        if group:
            s += " GROUP BY 1 ORDER BY 1"
        return s

    def agg_select(self, mrow):
        m = mrow["measure"]
        if m == "count":
            return "COUNT(*)"
        for pref in ("sum", "avg", "count_distinct"):
            if m.startswith(pref + ":"):
                col = m.split(":", 1)[1]
                alias = self.aliases[self.base_node]
                if "." in col:
                    tab, c = col.split(".", 1)
                    node = self._node_by_table(tab)
                    if node and node in self.aliases:
                        alias, col = self.aliases[node], c
                fn = {"sum": "SUM", "avg": "AVG", "count_distinct": "COUNT"}[pref]
                inner = (f'DISTINCT {alias}."{col}"' if pref == "count_distinct"
                         else f'{alias}."{col}"')
                return f"{fn}({inner})"
        raise RuntimeError(f"measure {m!r}")

    def _node_by_table(self, table):
        for r in self.gov.rows("gov_semantic_node", gv=self.gv):
            if r.get("physical_table") == table:
                return r["node_id"]
        return None

    def scalar_sql(self, anchor, pinfo, drop_scope_keys=()):
        """腿标量：单度量直出；加权多度量（v1 平局计半胜）→ 标量子查询线性组合。"""
        terms = []
        for mrow in self.measures:
            keep = self.measures
            self.measures = [mrow]
            try:
                body = self.sql(self.agg_select(mrow), anchor, pinfo, drop_scope_keys)
            finally:
                self.measures = keep
            w = mrow.get("weight")
            if w is None or float(w) == 1.0:
                terms.append(f"({body})")
            else:
                terms.append(f"({body}) * {float(w)}")
        return " + ".join(terms)


class Pilot2Adapter:
    """gov_* 全量种子驱动的通用适配器（九库一份实现，无逐库字典）。"""

    def __init__(self, domain: str, dir_path: pathlib.Path):
        self.domain = domain
        self.db = str(pathlib.Path(dir_path) / "warehouse.duckdb")

    # ================= 版本轴 =================
    def _ver_of(self, gov: P2Gov, declared_at: str, pinned: Optional[str]):
        vs = sorted(gov.t["gov_semantic_graph_version"],
                    key=lambda r: (str(r["committed_at"]), r.get("commit_seq") or 0))
        eligible = [v for v in vs if str(v["committed_at"]) <= str(declared_at)]
        if not eligible:
            raise _Refuse("oov_scope", {
                "type": "version-axis-undefined",
                "declared_at": declared_at,
                "first_commit": str(vs[0]["committed_at"]) if vs else None,
                "assertion": "T 早于首个 typed-commit：ver(T)↑（I2'(c) 变体）"})
        cur = eligible[-1]
        if pinned:
            hit = [v for v in eligible if v["graph_version"] == pinned]
            if not hit:
                raise _Refuse("oov_scope", {
                    "type": "version-pin-uncommitted",
                    "pinned": pinned, "declared_at": declared_at,
                    "eligible": [v["graph_version"] for v in eligible],
                    "assertion": "钉定版本在 T 时未提交/不存在：版本承诺落在可解析版本集之外"})
            offdiag = None
            if pinned != cur["graph_version"]:
                offdiag = {"pinned": pinned, "ver_as_of": cur["graph_version"]}
            return hit[0], offdiag
        return cur, None

    # ================= 覆盖探针族（覆盖域不物化：现算 D） =================
    def _hull_days(self, con, table, col):
        e = _day_expr("t", col)
        sql = f'SELECT MIN({e}), MAX({e}) FROM "{table}" t WHERE t."{col}" IS NOT NULL'
        mn, mx = con.execute(sql).fetchone()
        return mn, mx, sql

    def _token_set(self, con, table, col):
        e = _tok_expr("t", col)
        sql = f'SELECT DISTINCT {e} FROM "{table}" t WHERE t."{col}" IS NOT NULL'
        return set(r[0] for r in con.execute(sql).fetchall()), sql

    def _member_days_in(self, con, table, col, lo, hi_excl):
        e = _day_expr("t", col)
        sql = (f'SELECT COUNT(DISTINCT {e}) FROM "{table}" t WHERE t."{col}" IS NOT NULL '
               f"AND {e} >= '{lo}' AND {e} < '{hi_excl}'")
        return con.execute(sql).fetchone()[0], sql

    def _member_day_set(self, con, table, col, lo, hi_excl):
        e = _day_expr("t", col)
        sql = (f'SELECT DISTINCT {e} FROM "{table}" t WHERE t."{col}" IS NOT NULL '
               f"AND {e} >= '{lo}' AND {e} < '{hi_excl}'")
        return set(r[0] for r in con.execute(sql).fetchall()), sql

    @staticmethod
    def _tok_to_iv(tok: str, gran: str):
        """token → 日历日区间 [lo, hi)（月 token 两拼法 + 学年 token）。"""
        if gran == "month_token_yyyymm":
            lo, hi = _month_lo_hi(f"{tok[:4]}-{tok[4:6]}")
        elif gran == "academic_year_token":
            y = int(tok[:4])
            lo, hi = datetime.date(y, 7, 1), datetime.date(y + 1, 7, 1)
        else:  # month_token_yyyy_mm
            lo, hi = _month_lo_hi(tok)
        return lo, hi

    def _coverage_for(self, con, anchor, node_table, window_kind_hint=None):
        """按锚的 (coverage_mode, granularity) 构造 core 覆盖闭包（行 8–9）。"""
        tab = node_table(anchor["node_id"])
        gran = anchor.get("granularity") or "day"
        mode = anchor.get("coverage_mode") or "hull"
        aid = anchor["anchor_id"]

        if anchor.get("anchor_type") == "scd_type2":
            vf, vtc = anchor["vf_col"], anchor["vtc_col"]

            def probe(leg: Leg) -> CovResult:
                d = leg.window.ivs[0][0].isoformat()
                evf = _day_expr("t", vf)
                sql = (f'SELECT COUNT(*) FROM "{tab}" t WHERE {evf} <= \'{d}\' AND '
                       f'(t."{vtc}" IS NULL OR {_day_expr("t", vtc)} > \'{d}\')')
                n = con.execute(sql).fetchone()[0]
                member = (n or 0) > 0
                # 证书按 G_v 声明的 coverage_mode 落字（D3 版本化属性；校验器对同一
                # 声明重演）；在效判定本身仍是 D7 的 vf<=d<vtc 成员探针。
                return CovResult(
                    mode=mode,
                    bound=leg.window if member else Window.empty(),
                    empty=not member, w0_subset_val=member,
                    env_brief=f"SCD-2 在效区间并 [{vf},{vtc}) of {tab}（D7: vf<=d<vtc, NULL vtc 开放）",
                    probe={"kind": "COVERAGE", "anchor_id": aid,
                           "coverage_mode": mode, "sql": sql, "observed": n})
            return probe

        if gran.startswith("month_token") or gran == "academic_year_token":
            def probe(leg: Leg) -> CovResult:
                toks, sql = self._token_set(con, tab, anchor["effective_col"])
                ivs = sorted(self._tok_to_iv(t, gran) for t in toks)
                if not ivs:
                    env = Window.empty()
                elif mode == "strict_member":
                    # token 区间并（相邻月经 intersect(⊤) 走规范化合并）
                    env = Window(tuple(ivs), "token-set").intersect(
                        Window(((None, None),)), kind="token-set")
                else:
                    env = Window.interval(ivs[0][0], ivs[-1][1], "token-hull")
                bound = leg.window.intersect(env, kind=leg.window.kind)
                return CovResult(
                    mode=mode, bound=bound, empty=bound.is_empty(),
                    w0_subset_val=leg.window.subset_of(env),
                    env_brief=env.brief(),
                    probe={"kind": "COVERAGE", "anchor_id": aid, "coverage_mode": mode,
                           "sql": sql, "observed": len(toks)})
            return probe

        # 日粒锚
        if mode == "strict_member":
            def probe(leg: Leg) -> CovResult:
                lo, hi = leg.window.ivs[0]
                n, sql = self._member_days_in(con, tab, anchor["effective_col"],
                                              lo.isoformat(), hi.isoformat())
                member = (n or 0) > 0
                return CovResult(
                    mode="strict_member",
                    bound=leg.window if member else Window.empty(),
                    empty=not member, w0_subset_val=member,
                    env_brief=f"strict_member 有效标记日集 of {tab}.{anchor['effective_col']}",
                    probe={"kind": "COVERAGE", "anchor_id": aid,
                           "coverage_mode": "strict_member", "sql": sql, "observed": n})
            return probe

        def probe(leg: Leg) -> CovResult:
            mn, mx, sql = self._hull_days(con, tab, anchor["effective_col"])
            if mn is None:
                env = Window.empty()
            else:
                env = Window.interval(mn, _next_day(mx), "hull")
            bound = leg.window.intersect(env, kind=leg.window.kind)
            return CovResult(
                mode="hull", bound=bound, empty=bound.is_empty(),
                w0_subset_val=leg.window.subset_of(env),
                env_brief=env.brief(),
                probe={"kind": "COVERAGE", "anchor_id": aid, "coverage_mode": "hull",
                       "sql": sql, "observed": [str(mn), str(mx)]})
        return probe

    # ================= 窗推导（G_v 登记的域约定；种子不存窗） =================
    def _derive_window(self, con, q, binding, anchor, node_table, leg_key=None):
        """返回 (Window, pred_info, g_cmp)。覆盖裁定交由 core 行 8–9 的覆盖闭包。"""
        gran = binding["window_gran"]
        as_of = q.get("as_of")
        wreq = q.get("window_request")
        agran = anchor.get("granularity") or "day"
        gcmp = "month" if agran.startswith("month_token") else "day"
        cw = q.get("cross_window") or {}

        def month_win(tok):
            lo, hi = _month_lo_hi(tok)
            return Window.interval(lo, hi, "month")

        # AM(ii) 跨窗祈使：题面逐腿钉窗（月 token）——腿窗随 leg_key 分裂
        if cw and leg_key in cw:
            tok = cw[leg_key]
            w = month_win(tok)
            if gran == "month_token":
                token = tok.replace("-", "") if agran == "month_token_yyyymm" else tok
                return w, ("token_eq", token), gcmp
            return w, ("day_range", w.ivs[0][0].isoformat(), w.ivs[0][1].isoformat()), gcmp

        # AM(iii) 前置（先于一切覆盖/粒元派发）：周窗请求落非日粒锚即不可表达
        # （W ∉ W_{g^cmp}，C3 定义 3.8(iii)）——构造周窗，g^cmp 取锚粒元，交 core 条款 (iii)
        if wreq is not None and wreq.get("kind") == "week" and agran != "day":
            lo = wreq["lo"]
            hi = wreq.get("hi_excl") or (datetime.date.fromisoformat(lo) + 7 * _DAY).isoformat()
            return (Window.interval(lo, hi, "week"), ("day_range", lo, hi), "month")

        if binding["rule_id"] == "point_in_effect":
            return Window.point(as_of), ("point_in_effect", as_of), "day"

        if gran == "range_request":
            if wreq is None:
                raise _Refuse("oov_parse", {"as_of": as_of,
                                            "note": "range_request 无题面窗"})
            if wreq.get("kind") == "week":
                if agran != "day":
                    # AM(iii)：周窗落非日粒锚（W ∉ W_{g^cmp}）——构造周窗交 core 条款 (iii)
                    lo = wreq["lo"]
                    hi = (datetime.date.fromisoformat(lo) + 7 * _DAY).isoformat()
                    return (Window.interval(lo, hi, "week"),
                            ("day_range", lo, hi), "month")
                lo = wreq["lo"]
                hi = (datetime.date.fromisoformat(lo) + 7 * _DAY).isoformat()
                return Window.interval(lo, hi, "week"), ("day_range", lo, hi), "day"
            if wreq.get("kind") == "day_range":
                if agran.startswith("month_token"):
                    return (Window.interval(wreq["lo"], wreq["hi_excl"], "range"),
                            ("day_range", wreq["lo"], wreq["hi_excl"]), "month")
                return (Window.interval(wreq["lo"], wreq["hi_excl"], "range"),
                        ("day_range", wreq["lo"], wreq["hi_excl"]), "day")
            if wreq.get("kind") == "month_token_range":
                lo, _ = _month_lo_hi(wreq["lo"])
                _, hi = _month_lo_hi(wreq["hi"])
                return (Window.interval(lo, hi, "month-token-range"),
                        ("token_range", wreq["lo"], wreq["hi"]), "month")
            raise _Refuse("oov_parse", {"as_of": as_of,
                                        "note": f"window_request kind {wreq.get('kind')!r}"})

        if gran == "month_token":
            token = (as_of[:4] + as_of[5:7]) if agran == "month_token_yyyymm" else as_of[:7]
            return month_win(as_of[:7]), ("token_eq", token), gcmp

        if gran == "academic_year_token":
            y, m = int(as_of[:4]), int(as_of[5:7])
            token = f"{y}-{y + 1}" if m >= 7 else f"{y - 1}-{y}"
            lo = datetime.date(int(token[:4]), 7, 1)
            hi = datetime.date(int(token[:4]) + 1, 7, 1)
            return (Window.interval(lo, hi, "academic-year"),
                    ("token_eq", token), "day")

        if gran == "member_day":
            return Window.point(as_of), ("day_eq", as_of), "day"

        if gran == "cum_day":
            tab = node_table(anchor["node_id"])
            mn, mx, _sql = self._hull_days(con, tab, anchor["effective_col"])
            if mn is None or as_of < mn:
                # 覆盖真空：构造空交窗（core 行 8–9 判 OOV）
                return Window.point(as_of), ("day_eq", as_of), "day"
            hi_incl = as_of if as_of <= mx else mx
            return (Window.interval(mn, _next_day(hi_incl), "cumulative"),
                    ("day_le", mn, hi_incl), "day")

        if gran == "day":
            return Window.point(as_of), ("day_eq", as_of), "day"
        if gran == "month":
            w = month_win(as_of[:7])
            return w, ("day_range", w.ivs[0][0].isoformat(), w.ivs[0][1].isoformat()), gcmp
        if gran == "year":
            y = int(as_of[:4])
            w = Window.year(str(y))
            return w, ("day_range", f"{y}-01-01", f"{y + 1}-01-01"), gcmp
        raise RuntimeError(f"window_gran {gran!r}")

    # ================= AM(iv) 审计（window_realization_symdiff） =================
    def _realization_days(self, con, anchor, node_table, w: Window):
        """锚在窗上的实现日集（hull → 日历日∩[hmin,hmax]；strict → 标记日∩窗；
        token 粒锚不参与日集审计 → None）。"""
        gran = anchor.get("granularity") or "day"
        if gran != "day":
            return None
        lo, hi = w.ivs[0]
        if lo is None or hi is None or (hi - lo).days > 400:
            return None
        tab = node_table(anchor["node_id"])
        if anchor.get("coverage_mode") == "strict_member":
            days, _sql = self._member_day_set(con, tab, anchor["effective_col"],
                                              lo.isoformat(), hi.isoformat())
            return days
        mn, mx, _sql = self._hull_days(con, tab, anchor["effective_col"])
        out = set()
        d = lo
        while d < hi:
            s = d.isoformat()
            if mn is not None and mn <= s <= mx:
                out.add(s)
            d += _DAY
        return out

    def _adm_audit(self, con, node_table, an, ad, wn: Window, wd: Window):
        def run():
            rn = self._realization_days(con, an, node_table, wn)
            rd = self._realization_days(con, ad, node_table, wd)
            if rn is None or rd is None:
                return {"ok": True, "num_anchor": an["anchor_id"],
                        "den_anchor": ad["anchor_id"],
                        "note": "token-granule window: day-set audit not applicable"}
            sym = rn ^ rd
            return {"ok": not sym,
                    "num_anchor": an["anchor_id"], "den_anchor": ad["anchor_id"],
                    "symdiff_count": len(sym),
                    "discriminant_date": min(sym) if sym else None,
                    "probe": {"kind": "ADM_WINDOW_REALIZATION", "anchors":
                              [an["anchor_id"], ad["anchor_id"]],
                              "observed": len(sym)}}
        return run

    # ================= 粒度格 / 披露装配 =================
    def _lattice_expr(self, gov, gv, domain, level, asm: _LegAsm, entity_node):
        if level == "all":
            return "'all'"
        edges = gov.rows("gov_granularity_edge", gv=gv, domain=domain)
        to_edges = [e for e in edges if e.get("axis") == "entity"
                    and e.get("to_level") == level]
        if not to_edges:
            key = self._entity_key(gov, gv, entity_node)
            return f'{asm.aliases[entity_node]}."{key}"'
        e = to_edges[0]
        node = e.get("node_id") or entity_node
        a = asm.aliases[node]
        parts = []
        if e.get("band_col"):
            bs = e["band_bounds"]
            case = "CASE"
            for i in range(len(bs) - 1, 0, -1):
                lab = f"[{bs[i]},inf)" if i == len(bs) - 1 else f"[{bs[i]},{bs[i + 1]})"
                case += f' WHEN {a}."{e["band_col"]}" >= {bs[i]} THEN \'{lab}\''
            case += f" ELSE '[{bs[0]},{bs[1]})' END"
            parts.append(case)
        for c in (e.get("group_cols") or []):
            parts.append(f'{a}."{c}"')
        for dv in (e.get("derived") or []):
            if dv["fn"] == "decade":
                parts.append(f'substr(CAST({a}."{dv["col"]}" AS VARCHAR),1,3) || \'0s\'')
        if not parts:
            key = self._entity_key(gov, gv, node)
            parts = [f'{a}."{key}"']
        return " || '/' || ".join(parts) if len(parts) > 1 else parts[0]

    @staticmethod
    def _entity_key(gov, gv, node_id):
        r = gov.rows("gov_semantic_node", gv=gv, node_id=node_id)
        return r[0].get("entity_key") if r else None

    def _drop_keys(self, gov, gv, domain, chain_all, upto):
        """卷至 upto 时被格边吸收的 scope 键（其列成为/曾是更细层分组列）。"""
        drop = set()
        if upto not in chain_all:
            return drop
        idx = chain_all.index(upto)
        edges = gov.rows("gov_granularity_edge", gv=gv, domain=domain)
        for lvl in chain_all[:idx]:
            for e in edges:
                if e.get("to_level") == lvl:
                    for c in (e.get("group_cols") or []):
                        for node in gov.rows("gov_semantic_node", gv=gv):
                            for sk, col in (node.get("scope_keys") or {}).items():
                                if col == c:
                                    drop.add(sk)
        return drop

    # ================= 主装配 =================
    def intent(self, q: dict, con) -> Intent:
        gov = P2Gov(con)
        try:
            return self._intent(q, con, gov)
        except _Refuse as r:
            graph = {"domain": self.domain, "graph_version": None, "commit_id": None}
            kw = {"qid": q["qid"], "domain": self.domain,
                  "metric": q.get("metric_alias"), "metric_kind": "atomic",
                  "graph": graph, "periods": [Period(0, "-", [])],
                  "binding": None, "route": [], "g0": "requested",
                  "disclosure": Disclosure(policy_table_present=False)}
            kw[r.payload_field] = r.payload
            return Intent(**kw)

    def _intent(self, q: dict, con, gov: P2Gov) -> Intent:
        domain = self.domain
        vrow, offdiag = self._ver_of(gov, q["declared_at"], q.get("pinned_version"))
        gv = vrow["graph_version"]
        graph = {"domain": domain, "graph_version": gv,
                 "commit_id": str(vrow["committed_at"])}

        def node_table(node_id):
            r = gov.rows("gov_semantic_node", gv=gv, node_id=node_id)
            if not r:
                r = gov.rows("gov_semantic_node", node_id=node_id)
            if not r:
                raise RuntimeError(f"node {node_id!r} unregistered")
            return r[0]["physical_table"]

        pols = gov.rows("gov_disclosure_policy", gv=gv, domain=domain)
        policy_table_present = bool(pols)

        # ---- 别名 → metric（映射随版本变；查无 → MC(i)）----
        alias = [a for a in gov.rows("gov_metric_alias", gv=gv)
                 if a.get("alias_text") == q.get("metric_alias")]
        if not alias:
            return Intent(
                qid=q["qid"], domain=domain, metric=q.get("metric_alias"),
                metric_kind="atomic", graph=graph, periods=[Period(0, "-", [])],
                binding=None, route=[], g0="requested",
                disclosure=Disclosure(policy_table_present=policy_table_present,
                                      policies=pols),
                off_diagonal=offdiag,
                mc_missing={"metric": q.get("metric_alias"), "caliber_key": None,
                            "assertion": "gov_metric_alias@v 查无该别名 → MC(i)"})
        metric_id = alias[0]["metric_id"]
        mrow = gov.rows("gov_metric", gv=gv, metric_id=metric_id)[0]
        kind = mrow["kind"]

        # ---- AM(i)：题面点名改锚 → A_v 查无（D8 未注册锚引用）----
        override_ref = None
        if q.get("anchor_override"):
            reg = gov.rows("gov_valid_time_anchor", gv=gv)
            hit = [a for a in reg if a["anchor_id"] == q["anchor_override"]
                   or a.get("effective_col") == q["anchor_override"]]
            if not hit:
                override_ref = q["anchor_override"]

        # ---- 度量分派 ----
        if kind == "attribute":
            return self._attribute_intent(q, con, gov, gv, graph, metric_id, mrow,
                                          pols, node_table, offdiag,
                                          policy_table_present)
        if kind == "delta":
            return self._delta_intent(q, con, gov, gv, graph, metric_id, mrow,
                                      pols, node_table, offdiag, policy_table_present)
        if kind in ("report", "roster"):
            return self._report_intent(q, con, gov, gv, graph, metric_id, mrow,
                                       pols, node_table, offdiag,
                                       policy_table_present, kind, override_ref)
        return self._scalar_intent(q, con, gov, gv, graph, metric_id, mrow, pols,
                                   node_table, offdiag, policy_table_present, kind,
                                   override_ref)

    # ---- 常规 atomic / ratio ----
    def _scalar_intent(self, q, con, gov, gv, graph, metric_id, mrow, pols,
                       node_table, offdiag, ptp, kind, override_ref):
        legnames = ["num", "den"] if kind == "ratio" else ["atom"]
        role_of = {"num": "numerator", "den": "denominator", "atom": "atom"}
        asms, anchors, bindings, windows, pinfos, gcmps = {}, {}, {}, {}, {}, {}
        measures_of = {}
        for ln in legnames:
            measures = sorted(gov.rows("gov_measure_def", gv=gv,
                                       metric_id=metric_id, leg=ln),
                              key=lambda r: r["measure_id"])
            if not measures:
                return Intent(
                    qid=q["qid"], domain=self.domain, metric=metric_id,
                    metric_kind=kind, graph=graph, periods=[Period(0, "-", [])],
                    binding=None, route=[], g0="requested",
                    disclosure=Disclosure(policy_table_present=ptp, policies=pols),
                    off_diagonal=offdiag,
                    mc_missing={"metric": metric_id, "caliber_key": None,
                                "assertion": f"gov_measure_def@{gv} 无 {ln} 腿度量 → MC(i)"})
            measures_of[ln] = measures
            brow = gov.rows("gov_temporal_binding", gv=gv,
                            metric_id=metric_id, leg=ln)[0]
            bindings[ln] = brow
            anchors[ln] = gov.rows("gov_valid_time_anchor", gv=gv,
                                   anchor_id=brow["anchor_id"])[0]
            windows[ln], pinfos[ln], gcmps[ln] = self._derive_window(
                con, q, brow, anchors[ln], node_table, leg_key=ln)

        binding_id = "|".join(bindings[ln]["binding_id"] for ln in legnames)
        rule = bindings[legnames[0]]["rule_id"]

        def mk_legs():
            out = []
            for ln in legnames:
                a = anchors[ln]
                ref = override_ref if (override_ref and ln == legnames[0]) else None
                out.append(Leg(
                    role=role_of[ln],
                    anchor_id=(ref if ref else a["anchor_id"]),
                    registered=(False if ref else True),
                    required_anchor_id=a["anchor_id"],
                    window=windows[ln],
                    granule=a.get("granularity") or "day",
                    declared_override=bool(ref),
                    coverage=(None if ref else
                              self._coverage_for(con, a, node_table))))
            return out

        # ---- 腿装配（治理 hop 树）；dst_caliber='none' 即 MC(i)——α 仍携腿与窗 ----
        try:
            for ln in legnames:
                asms[ln] = _LegAsm(gov, gv, metric_id, ln, measures_of[ln],
                                   node_table, q.get("scope"))
        except _Refuse as r:
            if r.payload_field != "mc_missing":
                raise
            return Intent(
                qid=q["qid"], domain=self.domain, metric=metric_id,
                metric_kind=kind, graph=graph,
                periods=[Period(0, str(q.get("as_of")), mk_legs())],
                binding={"binding_id": binding_id, "rule": rule,
                         "numerator_anchor": (anchors.get("num") or {}).get("anchor_id"),
                         "denominator_anchor": (anchors.get("den") or {}).get("anchor_id"),
                         "adm_check_mode": "trivial_true"},
                route=[], g0="scope×window",
                disclosure=Disclosure(policy_table_present=ptp, policies=pols),
                off_diagonal=offdiag, mc_missing=r.payload)

        # AM(ii) 跨窗祈使检查材料在 core 条款 (ii)（双腿窗不等即违 same_valid_time_window）
        adm_mode = "trivial_true"
        adm_audit = None
        am_precheck = None
        if kind == "ratio" and anchors["num"]["anchor_id"] != anchors["den"]["anchor_id"] \
                and all(bindings[ln]["rule_id"] == "same_valid_time_window"
                        for ln in legnames):
            adm_mode = "window_realization_symdiff"
            adm_audit = self._adm_audit(con, node_table, anchors["num"],
                                        anchors["den"], windows["num"], windows["den"])
            if windows["num"] == windows["den"]:
                # 对子级审计前置（同窗时）：实现集失配先于逐腿覆盖裁定；
                # 两集同空 → 审计通过，回落逐腿覆盖 OOV（core 行 8–9）。
                a = adm_audit()
                if not a.get("ok"):
                    am_precheck = {"adm_check_mode": adm_mode,
                                   **{k: v for k, v in a.items() if k != "ok"},
                                   "num_window": windows["num"].to_json(),
                                   "den_window": windows["den"].to_json(),
                                   "assertion": "锚对实现集对称差非空（same_valid_time_window"
                                                " 双锚窗实现不一致，条款 (iv) 审计失败）"}

        legs = mk_legs()

        den_probe = None
        if kind == "ratio":
            def den_probe(bound_windows, _ln="den"):
                # μ_den 探针在 w*（行 8 裁剪后窗）上求值（引理 4.12）；出码谓词与
                # 认证窗指称一致（C5 V6c 按 α(den) 的窗重演）。
                w = bound_windows.get("denominator")
                pi = pinfos[_ln]
                if w is not None and not w.is_empty() and w != windows[_ln]:
                    pi = self._pinfo_from_window(w, pinfos[_ln], anchors[_ln])
                stmt = f"SELECT {asms[_ln].scalar_sql(anchors[_ln], pi)}"
                v = con.execute(stmt).fetchone()[0]
                return {"sql": stmt, "observed": None if v is None else float(v),
                        "mu_den": None if v is None else float(v)}

        def emit(bound):
            per = (bound or {}).get(0) or {}
            eff_pinfos = dict(pinfos)
            for ln in legnames:
                leg = per.get(role_of[ln])
                if leg is not None and leg.w_star is not None and \
                        leg.w_star != leg.window and not leg.w_star.is_empty():
                    eff_pinfos[ln] = self._pinfo_from_window(
                        leg.w_star, pinfos[ln], anchors[ln])
            if kind == "ratio":
                num = asms["num"].scalar_sql(anchors["num"], eff_pinfos["num"])
                den = asms["den"].scalar_sql(anchors["den"], eff_pinfos["den"])
                return f"SELECT {num} * 1.0 / NULLIF({den}, 0)"
            atom = asms["atom"].scalar_sql(anchors["atom"], eff_pinfos["atom"])
            return f"SELECT {atom}"

        seen = {}
        for ln in legnames:
            for h in asms[ln].route_rows:
                seen.setdefault(h["routing_id"], h)
        route = [self._route_entry(h, node_table) for h in seen.values()]
        g0 = "scope×window"
        return Intent(
            qid=q["qid"], domain=self.domain, metric=metric_id, metric_kind=kind,
            graph=graph,
            periods=[Period(0, str(q.get("as_of")), legs, den_probe=den_probe)],
            binding={"binding_id": binding_id, "rule": rule,
                     "numerator_anchor": (anchors.get("num") or {}).get("anchor_id"),
                     "denominator_anchor": (anchors.get("den") or {}).get("anchor_id"),
                     "adm_check_mode": adm_mode},
            rule_audit=RuleAudit(binding_id=binding_id, rule=rule,
                                 adm_check_mode=adm_mode,
                                 g_cmp=max(gcmps.values(), key=lambda g: g == "month"),
                                 adm_audit=adm_audit),
            route=route, g0=g0,
            disclosure=Disclosure(policy_table_present=ptp, policies=pols),
            off_diagonal=offdiag, am_precheck=am_precheck, emit_sql=emit)

    @staticmethod
    def _pinfo_from_window(w: Window, orig_pinfo, anchor):
        """覆盖裁剪后（w* ⊊ w0）把认证窗回落为出码谓词（C5 V6a：谓词指称集=认证窗）。"""
        lo, hi = w.ivs[0]
        kind = orig_pinfo[0]
        gran = anchor.get("granularity") or "day"
        if kind == "token_range" or gran.startswith("month_token"):
            return ("token_range",
                    (lo.isoformat()[:7].replace("-", "") if gran == "month_token_yyyymm"
                     else _ym_of(lo)),
                    ((hi - _DAY).isoformat()[:7].replace("-", "")
                     if gran == "month_token_yyyymm" else _ym_of(hi - _DAY)))
        if kind == "day_le":
            return ("day_le", lo.isoformat(), (hi - _DAY).isoformat())
        return ("day_range", lo.isoformat(), hi.isoformat())

    @staticmethod
    def _route_entry(h, node_table):
        return {"caliber_key": h["routing_id"], "metric": h.get("metric_id"),
                "leg": h.get("leg"), "hop_seq": h.get("hop_seq"),
                "src_node": h.get("src_node"), "dst_node": h.get("dst_node"),
                "via_table": node_table(h["dst_node"]),
                "dst_caliber": h.get("dst_caliber"),
                "join_keys": [list(p) for p in (h.get("join_on") or [])]}

    # ---- attribute（非时态属性值：掩码呈现降级 μ*）----
    def _attribute_intent(self, q, con, gov, gv, graph, metric_id, mrow, pols,
                          node_table, offdiag, ptp):
        m = gov.rows("gov_measure_def", gv=gv, metric_id=metric_id)[0]
        col = m["measure"].split(":", 1)[1]
        node = m["node_id"]
        asm = _LegAsm(gov, gv, metric_id, "atom", [m], node_table, q.get("scope"))
        masks = [p for p in pols if p.get("kind") == "mask" and p.get("node_id") == node
                 and col in (p.get("cols") or [])]
        mask_ob = [{"attributes": [col], "mask": p["mask_class"],
                    "policy_id": p["policy_id"]} for p in masks]

        def emit(bound):
            a = asm.aliases[node]
            if masks:
                mc = masks[0]["mask_class"]
                if mc == "year_only":
                    sel = f'substr(CAST({a}."{col}" AS VARCHAR),1,4)'
                elif mc == "year_month":
                    sel = f'substr(CAST({a}."{col}" AS VARCHAR),1,7)'
                elif mc == "generalize_last_component":
                    sel = f'trim(regexp_extract({a}."{col}", \'([^,]+)$\', 1))'
                else:
                    sel = f'CAST({a}."{col}" AS VARCHAR)'
            else:
                sel = f'CAST({a}."{col}" AS VARCHAR)'
            return asm.sql(sel)

        leg = Leg(role="atom", anchor_id=None, registered=False,
                  required_anchor_id=None, window=Window(((None, None),), "atemporal"),
                  granule="atemporal", coverage=None)
        # I2'(a) 空指派 + 无窗记录以证书内容物呈现（certificate 层按 anchor_id=None 落）
        leg.w_star = leg.window
        return Intent(
            qid=q["qid"], domain=self.domain, metric=metric_id, metric_kind="attribute",
            graph=graph, periods=[Period(0, "-", [leg])],
            binding=None, rule_audit=None, route=[], g0="value",
            disclosure=Disclosure(policy_table_present=ptp, policies=pols,
                                  touched=[p["policy_id"] for p in masks],
                                  mask_obligations=mask_ob),
            off_diagonal=offdiag, emit_sql=emit,
            notes=["attribute 度量非时态：α 记显式空指派（I2'(a)），无锚窗可评"])

    # ---- delta（推论 3.17′ 双期）----
    def _delta_intent(self, q, con, gov, gv, graph, metric_id, mrow, pols,
                      node_table, offdiag, ptp):
        base_id = mrow["base_metric_id"]
        periods_decl = q.get("periods") or []
        brow = gov.rows("gov_temporal_binding", gv=gv, metric_id=metric_id,
                        leg="atom")[0]
        anchor = gov.rows("gov_valid_time_anchor", gv=gv,
                          anchor_id=brow["anchor_id"])[0]
        measures = sorted(gov.rows("gov_measure_def", gv=gv, metric_id=base_id,
                                   leg="atom"), key=lambda r: r["measure_id"])
        periods = []
        pinfos = []
        asms = []
        for i, py in enumerate(periods_decl):
            qq = dict(q, as_of=f"{py}-07-01")
            asm = _LegAsm(gov, gv, base_id, "atom", measures, node_table,
                          q.get("scope"))
            w, pinfo, _g = self._derive_window(con, qq, brow, anchor, node_table)
            leg = Leg(role="atom", anchor_id=anchor["anchor_id"], registered=True,
                      required_anchor_id=anchor["anchor_id"], window=w,
                      granule=anchor.get("granularity") or "day",
                      coverage=self._coverage_for(con, anchor, node_table))
            periods.append(Period(i, str(py), [leg]))
            pinfos.append(pinfo)
            asms.append(asm)

        def emit(bound):
            terms = [asms[i].scalar_sql(anchor, pinfos[i]) for i in range(len(asms))]
            return f"SELECT {terms[1]} - {terms[0]}"

        route = [self._route_entry(h, node_table) for h in
                 (asms[0].route_rows if asms else [])]
        return Intent(
            qid=q["qid"], domain=self.domain, metric=metric_id, metric_kind="delta",
            graph=graph, periods=periods, combine="delta",
            binding={"binding_id": brow["binding_id"], "rule": brow["rule_id"],
                     "adm_check_mode": "trivial_true"},
            rule_audit=RuleAudit(binding_id=brow["binding_id"], rule=brow["rule_id"],
                                 adm_check_mode="trivial_true", g_cmp="day"),
            route=route, g0="scope×period",
            disclosure=Disclosure(policy_table_present=ptp, policies=pols),
            off_diagonal=offdiag, emit_sql=emit)

    # ---- report / roster（披露门：粒度爬升 Γ、k 小胞、时间下限、名录封顶）----
    def _report_intent(self, q, con, gov, gv, graph, metric_id, mrow, pols,
                       node_table, offdiag, ptp, kind, override_ref):
        domain = self.domain
        ent = mrow.get("entity_node")
        measures = sorted(gov.rows("gov_measure_def", gv=gv, metric_id=metric_id,
                                   leg="atom"), key=lambda r: r["measure_id"])
        asm = _LegAsm(gov, gv, metric_id, "atom", measures, node_table,
                      q.get("scope"))
        brow = gov.rows("gov_temporal_binding", gv=gv, metric_id=metric_id,
                        leg="atom")[0]
        anchor = gov.rows("gov_valid_time_anchor", gv=gv,
                          anchor_id=brow["anchor_id"])[0]
        w, pinfo, gcmp = self._derive_window(con, q, brow, anchor, node_table)

        ref = override_ref
        leg = Leg(role="atom",
                  anchor_id=(ref if ref else anchor["anchor_id"]),
                  registered=(False if ref else True),
                  required_anchor_id=anchor["anchor_id"], window=w,
                  granule=anchor.get("granularity") or "day",
                  declared_override=bool(ref),
                  coverage=(None if ref else self._coverage_for(con, anchor, node_table)))

        kpols = [p for p in pols if p.get("kind") == "k_threshold"
                 and p.get("node_id") == ent]
        maskpols = [p for p in pols if p.get("kind") == "mask"
                    and p.get("node_id") == ent]
        tfpols = [p for p in pols if p.get("kind") == "time_floor"]
        route = [self._route_entry(h, node_table) for h in asm.route_rows]

        # ---- roster / raw_rows：刚性呈现封顶 → DB（S-M2）----
        if kind == "roster" or q.get("presentation") == "raw_rows":
            touched = [p["policy_id"] for p in (maskpols + kpols)]
            block = None
            if maskpols or kpols:
                transcript = []
                ekey = self._entity_key(gov, gv, ent)
                if kpols and ent in asm.aliases:
                    lvl = (kpols[0].get("lattice_levels") or ["entity"])[0]
                    expr = self._lattice_expr(gov, gv, domain, lvl, asm, ent)
                    inner = asm.sql(
                        f'{expr} AS cell, COUNT(DISTINCT {asm.aliases[ent]}."{ekey}") AS n',
                        anchor, pinfo, group=True)
                    sql = f"SELECT MIN(n) FROM ({inner})"
                    obs = con.execute(sql).fetchone()[0]
                    transcript.append({"kind": "SUPPMIN",
                                       "policy_id": kpols[0]["policy_id"],
                                       "level": lvl, "sql": sql,
                                       "observed": None if obs is None else int(obs),
                                       "threshold": kpols[0].get("k")})
                block = {
                    "type": "empty-legal-rewrite",
                    "blocked_slices": [f"({gv},{metric_id})"],
                    "blocking_policy_ids": touched,
                    "probe_transcript": transcript,
                    "u_min_empty": True,
                    "assertion": ("名录/原值行呈现刚性（S-M2 ⊤_M）：掩码列原值 + 实体级"
                                  "行呈现不可合法化，掩码/小胞条款联合封顶 U_min=∅"),
                }
            return Intent(
                qid=q["qid"], domain=domain, metric=metric_id, metric_kind=kind,
                graph=graph, periods=[Period(0, str(q.get("as_of")), [leg])],
                binding={"binding_id": brow["binding_id"], "rule": brow["rule_id"],
                         "adm_check_mode": "trivial_true"},
                rule_audit=RuleAudit(binding_id=brow["binding_id"],
                                     rule=brow["rule_id"],
                                     adm_check_mode="trivial_true", g_cmp=gcmp),
                route=route, g0=q.get("requested_granularity") or "entity",
                disclosure=Disclosure(policy_table_present=ptp, policies=pols,
                                      touched=touched, block=block),
                off_diagonal=offdiag,
                emit_sql=lambda bound: None)

        # ---- 时间轴报表（time_floor）----
        if mrow.get("report_axis") == "time":
            req = q.get("requested_time_gran")
            touched = []
            lattice = None
            legal = None
            g0 = req or "month"
            if tfpols and req == "day" and tfpols[0].get("time_floor_gran") == "month":
                touched = [tfpols[0]["policy_id"]]
                lattice = ["day", "month"]

                def legal(level, _pid=tfpols[0]["policy_id"]):
                    if level == "day":
                        return {"ok": False, "probe": None}
                    return {"ok": True, "probe": None}

            def emit(bound):
                per = (bound or {}).get(0) or {}
                lg = per.get("atom")
                pi = pinfo
                if lg is not None and lg.w_star is not None and \
                        lg.w_star != lg.window and not lg.w_star.is_empty():
                    pi = self._pinfo_from_window(lg.w_star, pinfo, anchor)
                return f"SELECT {asm.scalar_sql(anchor, pi)}"

            return Intent(
                qid=q["qid"], domain=domain, metric=metric_id, metric_kind=kind,
                graph=graph, periods=[Period(0, str(q.get("as_of")), [leg])],
                binding={"binding_id": brow["binding_id"], "rule": brow["rule_id"],
                         "adm_check_mode": "trivial_true"},
                rule_audit=RuleAudit(binding_id=brow["binding_id"],
                                     rule=brow["rule_id"],
                                     adm_check_mode="trivial_true", g_cmp=gcmp),
                route=route, g0=g0,
                disclosure=Disclosure(policy_table_present=ptp, policies=pols,
                                      touched=touched, lattice=lattice,
                                      legal_at=legal),
                off_diagonal=offdiag, emit_sql=emit)

        # ---- 实体轴报表：Γ = lattice_levels 从请求级起，逐级 SUPPMIN 审计 ----
        req = q.get("requested_granularity")
        chain_all = (kpols[0].get("lattice_levels") if kpols else None) or [req]
        chain = chain_all[chain_all.index(req):] if req in chain_all else [req]
        k = kpols[0].get("k") if kpols else None
        ekey = self._entity_key(gov, gv, ent)
        touched = [p["policy_id"] for p in kpols]

        def legal(level):
            if level == "all" and (not kpols or kpols[0].get("k_exempt_top")):
                return {"ok": True, "exempt": True, "probe": None}
            drop = self._drop_keys(gov, gv, domain, chain_all, level) \
                if level != chain_all[0] else set()
            expr = self._lattice_expr(gov, gv, domain, level, asm, ent)
            inner = asm.sql(
                f'{expr} AS cell, COUNT(DISTINCT {asm.aliases[ent]}."{ekey}") AS n',
                anchor, pinfo, drop_scope_keys=drop, group=True)
            sql = f"SELECT MIN(n) FROM ({inner})"
            obs = con.execute(sql).fetchone()[0]
            ok = obs is not None and k is not None and int(obs) >= int(k)
            return {"ok": ok,
                    "probe": {"kind": "SUPPMIN", "policy_id": kpols[0]["policy_id"],
                              "level": level, "sql": sql,
                              "observed": None if obs is None else int(obs),
                              "threshold": k}}

        intent_holder = {}

        def emit(bound):
            it = intent_holder["intent"]
            final = getattr(it, "chosen_grain", req)
            drop = self._drop_keys(gov, gv, domain, chain_all, final) \
                if final != chain_all[0] else set()
            m0 = measures[0]
            if m0["measure"] == "ratio_of_base":
                base = gov.rows("gov_metric", gv=gv,
                                metric_id=mrow["base_metric_id"])[0]
                bnum = gov.rows("gov_measure_def", gv=gv,
                                metric_id=base["metric_id"], leg="num")[0]
                bden = gov.rows("gov_measure_def", gv=gv,
                                metric_id=base["metric_id"], leg="den")[0]
                if bnum["node_id"] != bden["node_id"] or bnum.get("preds") or \
                        bden.get("preds"):
                    raise RuntimeError("ratio_of_base 装配面超出同节点无谓词单趟形")
                bnum_col = bnum["measure"].split(":", 1)[1]
                bden_col = bden["measure"].split(":", 1)[1]
                a = asm.aliases[bnum["node_id"]]
                expr = (self._lattice_expr(gov, gv, domain, final, asm, ent)
                        if final != "all" else "'all'")
                sel = (f'{expr} AS cell, SUM({a}."{bnum_col}") * 1.0 / '
                       f'SUM({a}."{bden_col}") AS val')
                return asm.sql(sel, anchor, pinfo, drop_scope_keys=drop, group=True)
            expr = (self._lattice_expr(gov, gv, domain, final, asm, ent)
                    if final != "all" else "'all'")
            sel = f"{expr} AS cell, {asm.agg_select(m0)} AS val"
            return asm.sql(sel, anchor, pinfo, drop_scope_keys=drop, group=True)

        it = Intent(
            qid=q["qid"], domain=domain, metric=metric_id, metric_kind=kind,
            graph=graph, periods=[Period(0, str(q.get("as_of")), [leg])],
            binding={"binding_id": brow["binding_id"], "rule": brow["rule_id"],
                     "adm_check_mode": "trivial_true"},
            rule_audit=RuleAudit(binding_id=brow["binding_id"], rule=brow["rule_id"],
                                 adm_check_mode="trivial_true", g_cmp=gcmp),
            route=route, g0=req,
            disclosure=Disclosure(policy_table_present=ptp, policies=pols,
                                  touched=touched, lattice=chain, legal_at=legal),
            off_diagonal=offdiag, emit_sql=emit)
        intent_holder["intent"] = it
        return it
