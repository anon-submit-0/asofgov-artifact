# -*- coding: utf-8 -*-
"""路径 B：治理链独立推导器（金标双人规则的第二条路径）。

只读输入：warehouse.duckdb 的 gov_* 十表（G_v）+ 业务数据表（D）+ 题面评测可见字段
（qid/domain/question_zh/as_of/declared_at/metric_alias/scope/pinned_version/cross_window/
anchor_override/window_request/requested_granularity/requested_time_gran/presentation/periods）。
金标侧字段对本模块不可达：dualpath_check 只传可见投影并在运行时断言；ci/leak_check 静态复核。

解析链（§3.3 机理，≥2 步符号间接）：
  T→ver(T)（committed_at+commit_seq 全序，显式钉版本→offdiag 标记）
  → 别名→metric（映射随版本变）→ 度量/腿/口径装配（谓词原子+路由 hop → 程序化拼 SQL，无一处可粘贴）
  → 腿→锚→窗现算（覆盖域不物化：hull=min/max、strict_member=distinct 集，全部对 D 探针）
  → 守卫：AM(i)改锚 / AM(ii)跨窗 / AM(iii)窗-粒度 / OOV覆盖判空(+hull裁剪REWRITE)
        / AM(iv)锚对实现集审计 / MC(i)路由none / MC(ii)分母质量探针 / 披露(掩码/粒度格/k小胞/名录刚性)
  → 值装配执行。
"""
import json, datetime


# ---------------------------------------------------------------- gov loading
GOV_TABLES = ["gov_semantic_graph_version", "gov_semantic_node", "gov_metric",
              "gov_measure_def", "gov_metric_alias", "gov_caliber_routing",
              "gov_valid_time_anchor", "gov_temporal_binding",
              "gov_granularity_edge", "gov_disclosure_policy"]

JSON_FIELDS = {"scope_keys", "preds", "join_on", "lattice_levels", "carry",
               "band_bounds", "group_cols", "derived", "cols"}

ID_FIELD = {"gov_semantic_graph_version": "graph_version", "gov_semantic_node": "node_id",
            "gov_metric": "metric_id", "gov_measure_def": "measure_id",
            "gov_metric_alias": "alias_id", "gov_caliber_routing": "routing_id",
            "gov_valid_time_anchor": "anchor_id", "gov_temporal_binding": "binding_id",
            "gov_granularity_edge": "edge_id", "gov_disclosure_policy": "policy_id"}


class Gov:
    def __init__(self, con):
        self.con = con
        self.t = {}
        for tn in GOV_TABLES:
            try:
                cols = [d[0] for d in con.execute(f'DESCRIBE "{tn}"').fetchall()]
            except Exception:
                self.t[tn] = []
                continue
            if cols == ["placeholder"]:
                self.t[tn] = []
                continue
            rows = con.execute(f'SELECT * FROM "{tn}"').fetchall()
            out = []
            for r in rows:
                d = dict(zip(cols, r))
                for k, v in list(d.items()):
                    if k in JSON_FIELDS and isinstance(v, str):
                        try:
                            d[k] = json.loads(v)
                        except Exception:
                            pass
                    elif isinstance(v, str) and v.lstrip("-").replace(".", "", 1).isdigit():
                        d[k] = float(v) if "." in v else int(v)
                out.append(d)
            self.t[tn] = out

    def rows(self, tn, gv=None, **filt):
        out = []
        for r in self.t[tn]:
            if gv is not None and r.get("graph_version") != gv:
                continue
            if all(r.get(k) == v for k, v in filt.items()):
                out.append(r)
        return out


# ---------------------------------------------------------------- helpers
def _next_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    m += 1
    if m == 13:
        y, m = y + 1, 1
    return f"{y:04d}-{m:02d}"

def _next_day(d):
    dt = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    return dt.isoformat()

def _days(lo, hi_excl):
    out, d = [], datetime.date.fromisoformat(lo)
    end = datetime.date.fromisoformat(hi_excl)
    while d < end:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out

def _lit(v):
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"

def day_expr(alias, col):
    return f'substr(CAST({alias}."{col}" AS VARCHAR),1,10)'

def tok_expr(alias, col):
    return f'CAST({alias}."{col}" AS VARCHAR)'


class Refuse(Exception):
    def __init__(self, reason, subtype=None, windows=None):
        self.reason, self.subtype, self.windows = reason, subtype, windows


class LegPlan:
    """一条腿的装配面：基表、hop、谓词、锚、窗。SQL 由原子程序化拼出。"""
    def __init__(self, rz, gv, metric_id, leg, measures, binding, anchor, scope):
        self.rz, self.gv = rz, gv
        self.metric_id, self.leg = metric_id, leg
        self.measures, self.binding, self.anchor = measures, binding, anchor
        self.scope = dict(scope or {})
        self.window = None          # 结构化窗对象
        self.aliases = {}           # node_id -> alias
        self.joins = []             # (alias, table, on_sql)
        base_node = measures[0]["node_id"]
        self.base_node = base_node
        self.aliases[base_node] = "t0"
        self._ai = 0
        # 腿 hop + scope/entity hop 全部预挂（确定性）
        for legname in (leg, "scope", "entity"):
            for h in sorted(rz.gov.rows("gov_caliber_routing", gv=gv, metric_id=metric_id, leg=legname),
                            key=lambda r: (r.get("hop_seq") or 0, r["routing_id"])):
                rz.touch("gov_caliber_routing", h)
                if h.get("dst_caliber") == "none":
                    raise Refuse("missing-caliber", "mc_i")
                self._add_hop(h)

    def _add_hop(self, h):
        src, dst = h["src_node"], h["dst_node"]
        if not h.get("join_on"):
            return
        if src not in self.aliases:
            return
        if dst in self.aliases and dst != src:
            return  # 已挂
        self._ai += 1
        a = f"t{self._ai}"
        tab = self.rz.node_table(dst)
        on = " AND ".join(
            f'{self.aliases[src]}."{sc}" = {a}."{dc}"' for sc, dc in h["join_on"])
        if dst == src:
            # 自连接（如 采纳判定 posts a ⋈ posts qq ON qq.AcceptedAnswerId=a.Id）：
            # 新别名只承载连接语义，节点名仍指向基别名（锚/谓词落基表）
            self.joins.append((a, tab, on))
        else:
            self.aliases[dst] = a
            self.joins.append((a, tab, on))

    def where_parts(self, drop_scope_keys=()):
        parts = []
        for m in self.measures:
            for p in m.get("preds") or []:
                node = p.get("node") or m["node_id"]
                if node not in self.aliases:
                    continue  # 谓词节点未挂（不发生于金标路径）
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
        # scope
        for k, v in self.scope.items():
            if k in drop_scope_keys:
                continue
            hit = None
            for node, a in self.aliases.items():
                sk = self.rz.node_scope_keys(node)
                if k in sk:
                    hit = (a, sk[k])
                    break
            if hit is None:
                raise RuntimeError(f"scope key {k} unresolved on legs of {self.metric_id}")
            parts.append(f'{hit[0]}."{hit[1]}" = {_lit(v)}')
        # window（锚节点上）
        w = self.window
        if w is not None:
            an = self.anchor
            node = an["node_id"]
            if node not in self.aliases:
                raise RuntimeError(f"anchor node {node} not joined for {self.metric_id}/{self.leg}")
            a = self.aliases[node]
            k = w["kind"]
            if k in ("range", "day_range"):
                e = day_expr(a, an["effective_col"])
                parts.append(f"{e} >= '{w['lo']}' AND {e} < '{w['hi_excl']}'")
            elif k == "day":
                e = day_expr(a, an["effective_col"])
                parts.append(f"{e} = '{w['day']}'")
            elif k == "member_day":
                e = day_expr(a, an["effective_col"])
                parts.append(f"{e} = '{w['day']}'")
            elif k == "month_token":
                e = tok_expr(a, an["effective_col"])
                parts.append(f"{e} = '{w['token']}'")
            elif k == "academic_year_token":
                e = tok_expr(a, an["effective_col"])
                parts.append(f"{e} = '{w['token']}'")
            elif k == "cum":
                e = day_expr(a, an["effective_col"])
                parts.append(f"{e} >= '{w['lo']}' AND {e} <= '{w['hi_incl']}'")
            elif k == "month_token_range":
                e = tok_expr(a, an["effective_col"])
                parts.append(f"{e} >= '{w['lo']}' AND {e} <= '{w['hi']}'")
            elif k == "point_in_effect":
                vf, vtc, d = an["vf_col"], an["vtc_col"], w["day"]
                evf, evtc = day_expr(a, vf), day_expr(a, vtc)
                parts.append(f"{evf} <= '{d}' AND ({a}.\"{vtc}\" IS NULL OR {evtc} > '{d}')")
            else:
                raise RuntimeError(f"window kind {k}")
        return parts

    def sql(self, select, drop_scope_keys=(), group=False):
        s = f'SELECT {select} FROM "{self.rz.node_table(self.base_node)}" t0'
        for a, tab, on in self.joins:
            s += f' INNER JOIN "{tab}" {a} ON {on}'
        wp = self.where_parts(drop_scope_keys)
        if wp:
            s += " WHERE " + " AND ".join(wp)
        if group:
            s += " GROUP BY 1 ORDER BY 1"
        return s

    def agg_select(self, measure_row):
        m = measure_row["measure"]
        if m == "count":
            return "COUNT(*)"
        for pref in ("sum", "avg", "count_distinct"):
            if m.startswith(pref + ":"):
                col = m.split(":", 1)[1]
                alias = self.aliases[self.base_node]
                if "." in col:
                    tab, c = col.split(".", 1)
                    node = self.rz.node_by_table(tab)
                    if node and node in self.aliases:
                        alias, col = self.aliases[node], c
                fn = {"sum": "SUM", "avg": "AVG", "count_distinct": "COUNT"}[pref]
                inner = f'DISTINCT {alias}."{col}"' if pref == "count_distinct" else f'{alias}."{col}"'
                return f"{fn}({inner})"
        raise RuntimeError(f"measure {m}")

    def eval_scalar(self, drop_scope_keys=()):
        """加权多行度量：Σ weight×agg。"""
        total, seen = 0.0, False
        for mrow in self.measures:
            keep = self.measures
            self.measures = [mrow]
            try:
                v = self.rz.con.execute(self.sql(self.agg_select(mrow), drop_scope_keys)).fetchone()[0]
            finally:
                self.measures = keep
            if v is None:
                continue
            seen = True
            w = mrow.get("weight")
            total += float(v) * (float(w) if w is not None else 1.0)
        return total if seen else None


# ---------------------------------------------------------------- resolver
class Resolver:
    def __init__(self, con):
        self.con = con
        self.gov = Gov(con)
        self.touched = set()

    def touch(self, tn, row):
        self.touched.add((tn, row.get(ID_FIELD[tn]), row.get("graph_version")))

    # ---- gov 访问
    def node_table(self, node_id):
        for gv in ("v1", "v2"):
            r = self.gov.rows("gov_semantic_node", gv=gv, node_id=node_id)
            if r:
                return r[0]["physical_table"]
        raise RuntimeError(node_id)

    def node_by_table(self, table):
        for r in self.gov.t["gov_semantic_node"]:
            if r["physical_table"] == table:
                return r["node_id"]
        return None

    def node_scope_keys(self, node_id):
        r = self.gov.rows("gov_semantic_node", node_id=node_id)
        return (r[0].get("scope_keys") or {}) if r else {}

    def node_entity_key(self, node_id):
        r = self.gov.rows("gov_semantic_node", node_id=node_id)
        return r[0].get("entity_key") if r else None

    # ---- 版本解析
    def ver_of(self, T, pinned=None):
        vs = sorted(self.gov.t["gov_semantic_graph_version"],
                    key=lambda r: (str(r["committed_at"]), r.get("commit_seq") or 0))
        eligible = [v for v in vs if str(v["committed_at"]) <= T]
        if not eligible:
            raise Refuse("out-of-validity", "pre_governance")
        cur = eligible[-1]["graph_version"]
        for v in eligible:
            self.touch("gov_semantic_graph_version", v)
        if pinned:
            if pinned not in [v["graph_version"] for v in eligible]:
                raise Refuse("out-of-validity", "pinned_version_uncommitted")
            return pinned, (pinned != cur)
        return cur, False

    # ---- 覆盖探针（对 D 现算；覆盖域不物化公理）
    def anchor_day_hull(self, anchor):
        tab = self.node_table(anchor["node_id"])
        col = anchor["effective_col"]
        e = day_expr("t", col)
        r = self.con.execute(
            f'SELECT MIN({e}), MAX({e}) FROM "{tab}" t WHERE t."{col}" IS NOT NULL').fetchone()
        return r[0], r[1]

    def anchor_token_set(self, anchor):
        tab = self.node_table(anchor["node_id"])
        col = anchor["effective_col"]
        e = tok_expr("t", col)
        rows = self.con.execute(
            f'SELECT DISTINCT {e} FROM "{tab}" t WHERE t."{col}" IS NOT NULL').fetchall()
        return set(r[0] for r in rows)

    def anchor_member_days(self, anchor, lo=None, hi_excl=None):
        tab = self.node_table(anchor["node_id"])
        col = anchor["effective_col"]
        e = day_expr("t", col)
        cond = f' WHERE t."{col}" IS NOT NULL'
        if lo:
            cond += f" AND {e} >= '{lo}' AND {e} < '{hi_excl}'"
        rows = self.con.execute(f'SELECT DISTINCT {e} FROM "{tab}" t{cond}').fetchall()
        return set(r[0] for r in rows)

    def scd2_cov(self, anchor, d):
        tab = self.node_table(anchor["node_id"])
        vf, vtc = anchor["vf_col"], anchor["vtc_col"]
        evf = day_expr("t", vf)
        r = self.con.execute(
            f'SELECT MIN({evf}), MAX({day_expr("t", vtc)}), '
            f'SUM(CASE WHEN t."{vtc}" IS NULL THEN 1 ELSE 0 END) FROM "{tab}" t '
            f'WHERE t."{vf}" IS NOT NULL').fetchone()
        mn, mx_vtc, open_cnt = r
        return (mn is not None and d >= mn and ((open_cnt or 0) > 0 or (mx_vtc and d <= mx_vtc)))

    # ---- 窗推导 + 覆盖裁定；返回 (window, rewrite_or_None)
    # check_cover=False：只做结构推导（跨锚比率先过 AM(iv) 审计，再回头做覆盖裁定）
    def derive_window(self, q, binding, anchor, check_cover=True):
        gran = binding["window_gran"]
        as_of = q.get("as_of")
        wreq = q.get("window_request")
        cov = anchor["coverage_mode"]
        agran = anchor["granularity"]

        # AM(iii) 前置：周窗请求落在非日粒锚上即不可表达（W∉W_g^cmp），先于一切覆盖判定
        if wreq is not None and wreq.get("kind") == "week":
            if agran != "day":
                raise Refuse("anchor-mismatch", "am_iii")

        if binding["rule_id"] == "point_in_effect":
            w = {"kind": "point_in_effect", "day": as_of}
            if check_cover and not self.scd2_cov(anchor, as_of):
                raise Refuse("out-of-validity", None, windows={"atom": w})
            return w, None

        if gran == "range_request":
            if wreq is None:
                raise RuntimeError("range_request 无题面窗")
            if wreq["kind"] == "week":
                if agran.startswith("month_token") or cov == "strict_member" and agran != "day":
                    raise Refuse("anchor-mismatch", "am_iii")
                lo = wreq["lo"]
                wreq = {"kind": "day_range", "lo": lo,
                        "hi_excl": (datetime.date.fromisoformat(lo) + datetime.timedelta(days=7)).isoformat()}
            if wreq["kind"] == "day_range":
                if agran.startswith("month_token"):
                    raise Refuse("anchor-mismatch", "am_iii")
                hmin, hmax = self.anchor_day_hull(anchor)
                lo, hi = wreq["lo"], wreq["hi_excl"]
                elo, ehi = max(lo, hmin), min(hi, _next_day(hmax))
                if elo >= ehi:
                    raise Refuse("out-of-validity")
                w = {"kind": "range", "lo": elo, "hi_excl": ehi}
                if (elo, ehi) != (lo, hi):
                    return w, {"kind": "hull_trim",
                               "requested": {"kind": "range", "lo": lo, "hi_excl": hi},
                               "effective": w}
                return w, None
            if wreq["kind"] == "month_token_range":
                toks = sorted(self.anchor_token_set(anchor))
                tmin, tmax = toks[0], toks[-1]
                lo, hi = wreq["lo"], wreq["hi"]
                elo, ehi = max(lo, tmin), min(hi, tmax)
                if elo > ehi:
                    raise Refuse("out-of-validity")
                w = {"kind": "month_token_range", "lo": elo, "hi": ehi}
                if (elo, ehi) != (lo, hi):
                    return w, {"kind": "hull_trim",
                               "requested": {"kind": "month_token_range", "lo": lo, "hi": hi},
                               "effective": w}
                return w, None
            raise RuntimeError(wreq["kind"])

        if gran == "month_token":
            if agran == "month_token_yyyymm":
                token = as_of[:4] + as_of[5:7]
            else:
                token = as_of[:7]
            w = {"kind": "month_token", "token": token}
            if check_cover:
                if cov == "strict_member":
                    if token not in self.anchor_token_set(anchor):
                        raise Refuse("out-of-validity", None, windows={"atom": w})
                else:
                    toks = sorted(self.anchor_token_set(anchor))
                    if not toks or token < toks[0] or token > toks[-1]:
                        raise Refuse("out-of-validity", None, windows={"atom": w})
            return w, None

        if gran == "academic_year_token":
            y, m = int(as_of[:4]), int(as_of[5:7])
            token = f"{y}-{y+1}" if m >= 7 else f"{y-1}-{y}"
            w = {"kind": "academic_year_token", "token": token}
            if check_cover and cov == "strict_member" and token not in self.anchor_token_set(anchor):
                raise Refuse("out-of-validity", None, windows={"atom": w})
            return w, None

        if gran == "member_day":
            w = {"kind": "member_day", "day": as_of}
            if check_cover and as_of not in self.anchor_member_days(anchor):
                raise Refuse("out-of-validity", None, windows={"atom": w})
            return w, None

        if gran == "cum_day":
            hmin, hmax = self.anchor_day_hull(anchor)
            if as_of < hmin:
                raise Refuse("out-of-validity")
            hi = min(as_of, hmax)
            w = {"kind": "cum", "lo": hmin, "hi_incl": as_of if as_of <= hmax else hmax}
            return w, None

        # day / month / year 日历窗
        if gran == "day":
            lo, hi = as_of, _next_day(as_of)
        elif gran == "month":
            lo = as_of[:7] + "-01"
            hi = _next_month(as_of[:7]) + "-01"
        elif gran == "year":
            lo, hi = as_of[:4] + "-01-01", f"{int(as_of[:4])+1}-01-01"
        else:
            raise RuntimeError(gran)
        w = {"kind": "range", "lo": lo, "hi_excl": hi}
        if gran == "day":
            w = {"kind": "day", "day": lo}
        if not check_cover:
            return w, None
        if cov == "strict_member":
            days = self.anchor_member_days(anchor, lo, hi)
            if not days:
                raise Refuse("out-of-validity", None, windows={"atom": w})
            return w, None
        hmin, hmax = self.anchor_day_hull(anchor)
        elo, ehi = max(lo, hmin), min(hi, _next_day(hmax))
        if elo >= ehi:
            raise Refuse("out-of-validity", None, windows={"atom": w})
        if (elo, ehi) != (lo, hi):
            eff = {"kind": "range", "lo": elo, "hi_excl": ehi}
            return eff, {"kind": "hull_trim", "requested": w, "effective": eff}
        return w, None

    # ---- 锚对实现集（AM(iv) 审计）
    def realization_days(self, anchor, w):
        if w["kind"] in ("day", "member_day"):
            days = [w["day"]]
        elif w["kind"] == "range":
            days = _days(w["lo"], w["hi_excl"])
        else:
            return None  # token 类窗不参与日集审计
        if anchor["coverage_mode"] == "strict_member":
            mem = self.anchor_member_days(anchor)
            return set(d for d in days if d in mem)
        hmin, hmax = self.anchor_day_hull(anchor)
        return set(d for d in days if hmin <= d <= hmax)

    # ---- 报表格
    def lattice_chain(self, policy):
        return list(policy.get("lattice_levels") or [])

    def level_expr(self, gv, domain, level, plan, entity_node):
        if level == "all":
            return "'all'"
        edges = self.gov.rows("gov_granularity_edge", gv=gv, domain=domain)
        # 实体基级：entity key
        to_edges = [e for e in edges if e.get("axis") == "entity" and e.get("to_level") == level]
        if not to_edges:
            key = self.node_entity_key(entity_node)
            a = plan.aliases[entity_node]
            return f'{a}."{key}"'
        e = to_edges[0]
        self.touch("gov_granularity_edge", e)
        node = e.get("node_id") or entity_node
        a = plan.aliases[node]
        parts = []
        if e.get("band_col"):
            bs = e["band_bounds"]
            case = "CASE"
            for i in range(len(bs) - 1, 0, -1):
                lab = f"[{bs[i]},inf)" if i == len(bs) - 1 else f"[{bs[i]},{bs[i+1]})"
                case += f' WHEN {a}."{e["band_col"]}" >= {bs[i]} THEN \'{lab}\''
            case += f" ELSE '[{bs[0]},{bs[1]})' END"
            parts.append(case)
        for c in e.get("group_cols") or []:
            parts.append(f'{a}."{c}"')
        for dv in e.get("derived") or []:
            if dv["fn"] == "decade":
                parts.append(f'substr(CAST({a}."{dv["col"]}" AS VARCHAR),1,3) || \'0s\'')
        if not parts:
            key = self.node_entity_key(node)
            parts = [f'{a}."{key}"']
        return " || '/' || ".join(parts) if len(parts) > 1 else parts[0]

    def scope_keys_at_or_below(self, gv, domain, level_chain, upto_level):
        """卷到 upto_level 之上时应丢弃的 scope 键（其列被格边吸收）。"""
        drop = set()
        idx = level_chain.index(upto_level)
        edges = self.gov.rows("gov_granularity_edge", gv=gv, domain=domain)
        for lvl in level_chain[:idx]:
            for e in edges:
                if e.get("to_level") == lvl:
                    for c in e.get("group_cols") or []:
                        for node in self.gov.rows("gov_semantic_node", gv=gv):
                            for sk, col in (node.get("scope_keys") or {}).items():
                                if col == c:
                                    drop.add(sk)
        return drop

    # ---- 主入口
    def resolve(self, q):
        self.touched_q = set()
        try:
            return self._resolve(q)
        except Refuse as r:
            return {"label": "refusal", "refusal_reason": r.reason,
                    "refusal_subtype": r.subtype, "value": None,
                    "windows": r.windows, "rewrite": None, "offdiag": False}

    def _legs(self, gv, metric, q, scope):
        legs = {}
        for legname in (["num", "den"] if metric["kind"] == "ratio" else ["atom"]):
            measures = sorted(self.gov.rows("gov_measure_def", gv=gv,
                                            metric_id=metric["metric_id"], leg=legname),
                              key=lambda r: r["measure_id"])
            if not measures:
                raise Refuse("missing-caliber", "mc_i")
            for m in measures:
                self.touch("gov_measure_def", m)
            bindings = self.gov.rows("gov_temporal_binding", gv=gv,
                                     metric_id=metric["metric_id"], leg=legname)
            binding = bindings[0] if bindings else None
            anchor = None
            if binding:
                self.touch("gov_temporal_binding", binding)
                anchor = self.gov.rows("gov_valid_time_anchor", gv=gv,
                                       anchor_id=binding["anchor_id"])[0]
                self.touch("gov_valid_time_anchor", anchor)
            legs[legname] = LegPlan(self, gv, metric["metric_id"], legname,
                                    measures, binding, anchor, scope)
        return legs

    def _resolve(self, q):
        T = q["declared_at"]
        gv, offdiag = self.ver_of(T, q.get("pinned_version"))
        domain = q["domain"]

        # 别名 → metric（随版本变）
        al = [a for a in self.gov.rows("gov_metric_alias", gv=gv)
              if a["alias_text"] == q["metric_alias"]]
        if not al:
            raise Refuse("missing-caliber", "mc_i")
        self.touch("gov_metric_alias", al[0])
        metric = self.gov.rows("gov_metric", gv=gv, metric_id=al[0]["metric_id"])[0]
        self.touch("gov_metric", metric)
        for n in self.gov.rows("gov_semantic_node", gv=gv, domain=domain):
            if n["node_id"] in (metric.get("num_node"), metric.get("den_node"),
                                metric.get("entity_node")):
                self.touch("gov_semantic_node", n)

        # AM(i)：题面点名改锚 → 注册表查无
        if q.get("anchor_override"):
            reg = self.gov.rows("gov_valid_time_anchor", gv=gv)
            hit = [a for a in reg if a["anchor_id"] == q["anchor_override"]
                   or a.get("effective_col") == q["anchor_override"]]
            for a in reg:
                self.touch("gov_valid_time_anchor", a)
            if not hit:
                raise Refuse("anchor-mismatch", "am_i")

        # AM(ii)：跨窗祈使 vs same_valid_time_window 绑定
        if q.get("cross_window"):
            bs = self.gov.rows("gov_temporal_binding", gv=gv, metric_id=metric["metric_id"])
            for b in bs:
                self.touch("gov_temporal_binding", b)
            if any(b["rule_id"] == "same_valid_time_window" for b in bs):
                raise Refuse("anchor-mismatch", "am_ii")

        policies = self.gov.rows("gov_disclosure_policy", gv=gv, domain=domain)

        # 名录/原值行呈现 → 披露闸
        if metric["kind"] == "roster" or q.get("presentation") == "raw_rows":
            ent = metric.get("entity_node")
            masks = [p for p in policies if p["kind"] == "mask" and p["node_id"] == ent]
            klat = [p for p in policies if p["kind"] == "k_threshold" and p["node_id"] == ent]
            for p in masks + klat:
                self.touch("gov_disclosure_policy", p)
            if masks or klat:
                raise Refuse("disclosure-blocked")

        # 属性值 → 掩码呈现降级
        if metric["kind"] == "attribute":
            m = self.gov.rows("gov_measure_def", gv=gv, metric_id=metric["metric_id"])[0]
            self.touch("gov_measure_def", m)
            col = m["measure"].split(":", 1)[1]
            node = m["node_id"]
            tab = self.node_table(node)
            sk = self.node_scope_keys(node)
            conds = []
            for k, v in (q.get("scope") or {}).items():
                conds.append(f'"{sk[k]}" = {_lit(v)}')
            raw = self.con.execute(
                f'SELECT "{col}" FROM "{tab}" WHERE ' + " AND ".join(conds)).fetchone()
            raw = raw[0] if raw else None
            mp = [p for p in policies if p["kind"] == "mask" and p["node_id"] == node
                  and col in (p.get("cols") or [])]
            if mp:
                self.touch("gov_disclosure_policy", mp[0])
                mc = mp[0]["mask_class"]
                s = str(raw)
                if mc == "year_only":
                    val = s[:4]
                elif mc == "year_month":
                    val = s[:7]
                elif mc == "generalize_last_component":
                    val = s.split(",")[-1].strip()
                else:
                    val = s
                return {"label": "rewrite", "refusal_reason": None, "refusal_subtype": None,
                        "value": val, "windows": None,
                        "rewrite": {"kind": "mask", "mask_class": mc, "col": col},
                        "offdiag": offdiag}
            return {"label": "value", "value": str(raw), "windows": None,
                    "refusal_reason": None, "refusal_subtype": None, "rewrite": None,
                    "offdiag": offdiag}

        # delta：双期同版本
        if metric["kind"] == "delta":
            base = self.gov.rows("gov_metric", gv=gv, metric_id=metric["base_metric_id"])[0]
            self.touch("gov_metric", base)
            vals, wins = [], {}
            for i, py in enumerate(q["periods"]):
                legs = self._legs(gv, base, dict(q, as_of=f"{py}-07-01"), q.get("scope"))
                plan = legs["atom"]
                w, rw = self.derive_window(dict(q, as_of=f"{py}-07-01"),
                                           plan.binding, plan.anchor)
                if rw:
                    raise Refuse("out-of-validity")
                plan.window = w
                vals.append(plan.eval_scalar())
                wins[f"p{i+1}"] = w
            value = (vals[1] or 0) - (vals[0] or 0)
            return {"label": "value", "value": value, "windows": wins,
                    "refusal_reason": None, "refusal_subtype": None, "rewrite": None,
                    "offdiag": offdiag}

        # 报表（实体/时间轴 + 粒度格 + k）
        if metric["kind"] == "report":
            return self._resolve_report(q, gv, metric, policies, offdiag)

        # 常规 atomic / ratio
        legs = self._legs(gv, metric, q, q.get("scope"))

        # AM(iv)：跨锚比率先做锚对实现集审计（同窗规则要求两锚窗实现一致；
        # 审计先于逐腿覆盖裁定——锚对不相容是"对子"的失配，不化归为单腿 OOV）
        if metric["kind"] == "ratio":
            pn, pd = legs["num"], legs["den"]
            if pn.anchor["anchor_id"] != pd.anchor["anchor_id"] and \
               pn.binding["rule_id"] == "same_valid_time_window" == pd.binding["rule_id"]:
                wn, _ = self.derive_window(q, pn.binding, pn.anchor, check_cover=False)
                wd, _ = self.derive_window(q, pd.binding, pd.anchor, check_cover=False)
                rn = self.realization_days(pn.anchor, wn)
                rd = self.realization_days(pd.anchor, wd)
                if rn is not None and rd is not None and rn != rd:
                    raise Refuse("anchor-mismatch", "am_iv", windows={"num": wn, "den": wd})

        rewrite = None
        windows = {}
        for legname, plan in legs.items():
            w, rw = self.derive_window(q, plan.binding, plan.anchor)
            plan.window = w
            if rw:
                rewrite = rw
                windows["requested"] = rw["requested"]
                windows["effective"] = rw["effective"]
            else:
                windows[legname] = w

        # MC(ii)：分母质量探针（μ_den≤0）
        if metric["kind"] == "ratio":
            den = legs["den"].eval_scalar()
            if den is None or den <= 0:
                raise Refuse("missing-caliber", "mc_ii",
                             windows={"num": legs["num"].window, "den": legs["den"].window})
            num = legs["num"].eval_scalar()
            value = (num or 0.0) / den
        else:
            value = legs["atom"].eval_scalar()

        return {"label": ("rewrite" if rewrite else "value"), "value": value,
                "windows": windows, "rewrite": rewrite,
                "refusal_reason": None, "refusal_subtype": None, "offdiag": offdiag}

    def _resolve_report(self, q, gv, metric, policies, offdiag):
        domain = q["domain"]
        # 时间轴报表：时间粒度下限
        if metric.get("report_axis") == "time":
            tf = [p for p in policies if p["kind"] == "time_floor"]
            legs = self._legs(gv, metric, q, q.get("scope"))
            plan = legs["atom"]
            w, rw = self.derive_window(q, plan.binding, plan.anchor)
            plan.window = w
            req = q.get("requested_time_gran")
            if tf and req == "day" and tf[0]["time_floor_gran"] == "month":
                self.touch("gov_disclosure_policy", tf[0])
                val = plan.eval_scalar()
                return {"label": "rewrite", "value": val, "windows": {"atom": w},
                        "rewrite": {"kind": "granularity_rollup", "axis": "time",
                                    "requested_level": req, "effective_level": "month"},
                        "refusal_reason": None, "refusal_subtype": None, "offdiag": offdiag}
            val = plan.eval_scalar()
            return {"label": "value", "value": val, "windows": {"atom": w},
                    "rewrite": None, "refusal_reason": None, "refusal_subtype": None,
                    "offdiag": offdiag}

        # 实体轴报表
        ent = metric["entity_node"]
        kpol = [p for p in policies if p["kind"] == "k_threshold" and p["node_id"] == ent]
        legs = self._legs(gv, metric, q, q.get("scope"))
        plan = legs["atom"]
        w, rw = self.derive_window(q, plan.binding, plan.anchor)
        plan.window = w
        chain_all = self.lattice_chain(kpol[0]) if kpol else [q.get("requested_granularity")]
        if kpol:
            self.touch("gov_disclosure_policy", kpol[0])
        k = kpol[0]["k"] if kpol else None
        req = q.get("requested_granularity")
        chain = chain_all[chain_all.index(req):] if req in chain_all else [req]
        ekey = self.node_entity_key(ent)
        final = None
        for lvl in chain:
            if lvl == "all" and (not kpol or kpol[0].get("k_exempt_top")):
                final = lvl
                break
            expr = self.level_expr(gv, domain, lvl, plan, ent)
            drop = self.scope_keys_at_or_below(gv, domain, chain_all, lvl) if lvl != chain_all[0] else set()
            cells = self.con.execute(
                plan.sql(f'{expr} AS cell, COUNT(DISTINCT {plan.aliases[ent]}."{ekey}") AS n',
                         drop_scope_keys=drop, group=True)).fetchall()
            if cells and all((c[1] or 0) >= k for c in cells):
                final = lvl
                break
        if final is None:
            raise Refuse("disclosure-blocked")
        drop = self.scope_keys_at_or_below(gv, domain, chain_all, final) if final != chain_all[0] else set()
        # 值装配：ratio_of_base 或普通聚合
        m0 = plan.measures[0]
        if m0["measure"] == "ratio_of_base":
            base = self.gov.rows("gov_metric", gv=gv, metric_id=metric["base_metric_id"])[0]
            self.touch("gov_metric", base)
            blegs = self._legs(gv, base, q, q.get("scope"))
            out = {}
            for legname in ("num", "den"):
                bp = blegs[legname]
                bw, _ = self.derive_window(q, bp.binding, bp.anchor)
                bp.window = bw
                expr = self.level_expr(gv, domain, final, bp, ent) if final != "all" else "'all'"
                sel = f"{expr} AS cell, {bp.agg_select(bp.measures[0])} AS val"
                for cell, v in self.con.execute(bp.sql(sel, drop_scope_keys=drop, group=True)).fetchall():
                    out.setdefault(cell, {})[legname] = float(v)
            cells = sorted((c, d["num"] / d["den"]) for c, d in out.items() if d.get("den"))
        else:
            expr = self.level_expr(gv, domain, final, plan, ent) if final != "all" else "'all'"
            sel = f"{expr} AS cell, {plan.agg_select(m0)} AS val"
            cells = [(c, float(v)) for c, v in
                     self.con.execute(plan.sql(sel, drop_scope_keys=drop, group=True)).fetchall()]
            cells.sort()
        rwv = None if final == req else {"kind": "granularity_rollup", "axis": "entity",
                                         "requested_level": req, "effective_level": final}
        return {"label": ("rewrite" if rwv else "value"), "value": [[c, v] for c, v in cells],
                "windows": {"atom": w}, "rewrite": rwv,
                "refusal_reason": None, "refusal_subtype": None, "offdiag": offdiag}
