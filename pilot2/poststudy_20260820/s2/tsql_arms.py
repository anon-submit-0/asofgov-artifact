#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S2 — Governance-blind temporal-SQL arms (deterministic, zero LLM).

Prereg: PREREG_poststudy_20260820.md §S2
  sha256 f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24
Two hand-built arms operationalising "temporal-SQL machinery without the
governance axis":

  TSQL-W  same-window, latest-version, guard-free: applies the question's
          requested window to both legs on their latest-committed-version
          anchors; always answers; never refuses / rewrites / checks
          version-in-effect, coverage, admissibility or disclosure.
  TSQL-H  all-history at T: each leg aggregated over all valid rows dated
          <= as_of (classic time-travel dashboard reading); no as_of ->
          no time predicate at all.

Independence red line (mirrors the verifier's import-disjointness assertion):
imports NOTHING from impl/asof_compiler or impl/asof_verifier — asserted at
startup over sys.modules after all imports are done.

Inputs per question (prereg exclusion list enforced IN CODE by the loader):
the structured fields of questions.json EXCLUDING gold_sql, gold_value,
expected_kind, refusal_* (refusal_reason, refusal_subtype), rewrite,
pinned_version; plus the LATEST committed version's metric/leg/anchor/route
rows from gov_seed/*.jsonl; plus the warehouse. The arm-builder additionally
never reads question_zh / notes / windows_note / windows — the requested
window is re-derived from the non-gold structured fields + latest-version
binding rows, then cross-checked against the `windows` field OUTSIDE the
builder (recorded in the ledger; the builder never sees it).

Scoring: byte-identical frozen rules — imports run_pilot (frozen sha
asserted) and run_pilot2_arms.fetch_and_score from the sandbox copy
(0.5% relative tolerance, rowset/string dispatch, refusal scoring).
Edge rule: the arm emits the raw SQL evaluation result; a bare NULL is
recorded as "NULL"; the arm never emits a refusal declaration. Because the
frozen scorer's treatment of a bare NULL on a refusal-gold question is
interpretable two ways, BOTH readings are computed per question:
  reading A (frozen-literal): NULL -> kind "error" -> answered_should_refuse
  reading B (NULL-as-implicit-refusal-credit): refusal-gold + bare NULL ->
  correct (all other verdicts unchanged)

Outputs (all under poststudy_20260820/s2/): tsql_ledger.json, tsql_summary.json.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import pathlib
import sys

SANDBOX = pathlib.Path(os.environ.get(
    "TSQL_BASE",
    "/private/tmp/claude-502/-Volumes-SSD-1-vldb-asof/"
    "831806d7-8bc6-464b-9baf-a933f760e40d/scratchpad/poststudy-sandbox"))
OUT = pathlib.Path(os.environ.get(
    "TSQL_OUT", str(pathlib.Path(__file__).resolve().parent)))
PREREG = pathlib.Path(__file__).resolve().parent.parent / "PREREG_poststudy_20260820.md"
PREREG_SHA = "f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24"
FROZEN_RUN_PILOT_SHA = "fecda681ccce203fa08e1a8b28a8ff722093a50ce656c62e86d921b5949309ef"

import duckdb  # noqa: E402

sys.path.insert(0, str(SANDBOX / "pilot"))
sys.path.insert(0, str(SANDBOX / "pilot2"))
import run_pilot as RP          # noqa: E402  frozen scorer core (sha asserted below)
import run_pilot2_arms as R2    # noqa: E402  frozen §4.2 dispatch (fetch_and_score)

ARMS = ("TSQL-W", "TSQL-H")
EXCLUDE_FIELDS = {"gold_sql", "gold_value", "expected_kind", "rewrite",
                  "pinned_version"}  # + every key starting with "refusal_"
# the builder must additionally never read these (gold-side / free-text):
BUILDER_BLIND = {"windows", "windows_note", "notes", "question_zh"}

VERSION_FLIP_PAIRS = [("CA-Q1", "CA-Q2"), ("FIN-Q1", "FIN-Q2"),
                      ("F1-Q1", "F1-Q2"), ("W1-Q1", "W1-Q2")]

_DAY = datetime.timedelta(days=1)


# ---------------------------------------------------------------- red line
def assert_import_disjointness() -> str:
    bad = []
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None) or ""
        if "asof_compiler" in f or "asof_verifier" in f:
            bad.append((name, f))
        if f and (os.sep + "impl" + os.sep) in f:
            bad.append((name, f))
    assert not bad, f"IMPORT-DISJOINTNESS VIOLATION: {bad}"
    msg = (f"IMPORT-DISJOINTNESS OK: {len(sys.modules)} loaded modules scanned; "
           "none originate from impl/asof_compiler, impl/asof_verifier or impl/")
    return msg


def assert_frozen_scorer() -> str:
    got = hashlib.sha256((SANDBOX / "pilot" / "run_pilot.py").read_bytes()).hexdigest()
    assert got == FROZEN_RUN_PILOT_SHA, f"run_pilot.py sha drift: {got}"
    if PREREG.is_file():
        psha = hashlib.sha256(PREREG.read_bytes()).hexdigest()
        assert psha == PREREG_SHA, f"prereg sha drift: {psha}"
    return f"frozen scorer sha OK ({got[:12]}…), prereg sha OK ({PREREG_SHA[:12]}…)"


# ---------------------------------------------------------------- loading
def domains():
    return sorted(p for p in (SANDBOX / "pilot2" / "domains").iterdir()
                  if p.is_dir() and not p.name.startswith("._")
                  and (p / "questions.json").is_file())


def load_questions():
    out = []
    for d in domains():
        for q in json.loads((d / "questions.json").read_text(encoding="utf-8")):
            out.append((q, d))
    assert len(out) == 60 and len({q["qid"] for q, _ in out}) == 60
    return out


def strip_for_arm(q: dict) -> dict:
    """Prereg §S2 exclusion list, enforced in code."""
    qa = copy.deepcopy(q)
    for k in list(qa):
        if k in EXCLUDE_FIELDS or k.startswith("refusal_"):
            del qa[k]
    for k in EXCLUDE_FIELDS:
        assert k not in qa
    assert not any(k.startswith("refusal_") for k in qa)
    return qa


def load_gov(d: pathlib.Path) -> dict:
    g = {}
    for f in sorted((d / "gov_seed").glob("gov_*.jsonl")):
        rows = []
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        g[f.stem] = rows
    return g


def latest_version(gov: dict) -> dict:
    vs = sorted(gov["gov_semantic_graph_version"],
                key=lambda r: (str(r["committed_at"]), r.get("commit_seq") or 0))
    assert vs, "no committed versions"
    return vs[-1]


def ver_in_effect(gov: dict, declared_at: str):
    vs = sorted(gov["gov_semantic_graph_version"],
                key=lambda r: (str(r["committed_at"]), r.get("commit_seq") or 0))
    elig = [v for v in vs if str(v["committed_at"]) <= str(declared_at)]
    return elig[-1]["graph_version"] if elig else None


def grows(gov, table, gv=None, **filt):
    out = []
    for r in gov[table]:
        if gv is not None and r.get("graph_version") != gv:
            continue
        if all(r.get(k) == v for k, v in filt.items()):
            out.append(r)
    return out


# ---------------------------------------------------------------- SQL helpers
def _lit(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _day_expr(alias, col):
    return f'substr(CAST({alias}."{col}" AS VARCHAR),1,10)'


def _tok_expr(alias, col):
    return f'CAST({alias}."{col}" AS VARCHAR)'


def _month_lo_hi(ym: str):
    y, m = int(ym[:4]), int(ym[5:7])
    lo = datetime.date(y, m, 1)
    hi = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
    return lo.isoformat(), hi.isoformat()


def _ay_token(day: str) -> str:
    y, m = int(day[:4]), int(day[5:7])
    return f"{y}-{y + 1}" if m >= 7 else f"{y - 1}-{y}"


def _fmt_month_token(ym: str, gran: str) -> str:
    """'YYYY-MM' -> anchor-native month token."""
    return ym.replace("-", "") if gran == "month_token_yyyymm" else ym


# ---------------------------------------------------------------- leg assembly
class LegAsm:
    """One leg's FROM/JOIN tree + predicate atoms + scope, from latest-version
    gov rows only. Guard-free: dst_caliber is IGNORED (never refuses)."""

    def __init__(self, gov, gv, metric_id, leg, measures, scope):
        self.gov, self.gv = gov, gv
        self.metric_id, self.leg = metric_id, leg
        self.measures = measures
        self.scope = dict(scope or {})
        self.base_node = measures[0]["node_id"]
        self.aliases = {self.base_node: "t0"}
        self.joins = []
        self.notes = []
        self._ai = 0
        for legname in (leg, "scope", "entity"):
            hops = sorted(grows(gov, "gov_caliber_routing", gv=gv,
                                metric_id=metric_id, leg=legname),
                          key=lambda r: (r.get("hop_seq") or 0, r["routing_id"]))
            for h in hops:
                if h.get("dst_caliber") == "none":
                    self.notes.append(
                        f"route {h['routing_id']} dst_caliber='none' IGNORED (guard-free)")
                self._hop(h)

    def node_table(self, node_id):
        r = grows(self.gov, "gov_semantic_node", gv=self.gv, node_id=node_id)
        if not r:
            r = grows(self.gov, "gov_semantic_node", node_id=node_id)
        assert r, f"node {node_id!r} unregistered"
        return r[0]["physical_table"]

    def node_scope_keys(self, node_id):
        r = grows(self.gov, "gov_semantic_node", gv=self.gv, node_id=node_id)
        return (r[0].get("scope_keys") or {}) if r else {}

    def entity_key(self, node_id):
        r = grows(self.gov, "gov_semantic_node", gv=self.gv, node_id=node_id)
        return r[0].get("entity_key") if r else None

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

    def pred_parts(self):
        parts = []
        for m in self.measures:
            for p in (m.get("preds") or []):
                node = p.get("node") or m["node_id"]
                if node not in self.aliases:
                    self.notes.append(f"pred on unjoined node {node} skipped")
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
            hit = None
            for node, a in self.aliases.items():
                sk = self.node_scope_keys(node)
                if k in sk:
                    hit = (a, sk[k])
                    break
            assert hit is not None, \
                f"scope key {k!r} unresolved on {self.metric_id}/{self.leg}"
            parts.append(f'{hit[0]}."{hit[1]}" = {_lit(v)}')
        return parts

    # -- window realization on the leg's anchor ------------------------------
    def window_pred(self, anchor, wspec):
        """wspec: abstract requested window -> predicate strings on the anchor,
        realized in the anchor's native granule. Returns list of predicates.
        If the anchor's node is not joined into this leg, the window is
        unappliable: guard-free arm aggregates unfiltered (note recorded)."""
        if wspec is None:
            return []
        node = anchor["node_id"]
        if node not in self.aliases:
            self.notes.append(
                f"anchor node {node} not joined for leg {self.leg}: "
                "window unappliable, aggregating unfiltered (guard-free)")
            return []
        a = self.aliases[node]
        gran = anchor.get("granularity") or "day"
        typ = wspec["type"]

        if anchor.get("anchor_type") == "scd_type2":
            vf, vtc = anchor["vf_col"], anchor["vtc_col"]
            evf, evtc = _day_expr(a, vf), _day_expr(a, vtc)
            if typ == "pie":
                d = wspec["day"]
                return [f"{evf} <= '{d}'",
                        f'({a}."{vtc}" IS NULL OR {evtc} > \'{d}\')']
            if typ == "cum":  # all-history: ever-arrived by T (vtc ignored)
                return [f"{evf} <= '{wspec['hi_incl']}'"]
            raise RuntimeError(f"wspec {typ} on scd_type2")

        if gran.startswith("month_token"):
            e = _tok_expr(a, anchor["effective_col"])
            if typ == "months":
                lo = _fmt_month_token(wspec["lo_month"], gran)
                hi = _fmt_month_token(wspec["hi_month"], gran)
                return [f"{e} = '{lo}'"] if lo == hi else \
                    [f"{e} >= '{lo}'", f"{e} <= '{hi}'"]
            if typ == "range":
                lo_m = wspec["lo"][:7]
                hi_m = (datetime.date.fromisoformat(wspec["hi_excl"]) - _DAY
                        ).isoformat()[:7]
                lo = _fmt_month_token(lo_m, gran)
                hi = _fmt_month_token(hi_m, gran)
                self.notes.append(
                    f"day window realized at anchor granule month: [{lo},{hi}]")
                return [f"{e} = '{lo}'"] if lo == hi else \
                    [f"{e} >= '{lo}'", f"{e} <= '{hi}'"]
            if typ == "point":
                tok = _fmt_month_token(wspec["day"][:7], gran)
                return [f"{e} = '{tok}'"]
            if typ == "cum":
                tok = _fmt_month_token(wspec["hi_incl"][:7], gran)
                return [f"{e} <= '{tok}'"]
            raise RuntimeError(f"wspec {typ} on {gran}")

        if gran == "academic_year_token":
            e = _tok_expr(a, anchor["effective_col"])
            if typ == "ay":
                return [f"{e} = '{wspec['token']}'"]
            if typ == "cum":
                return [f"{e} <= '{_ay_token(wspec['hi_incl'])}'"]
            if typ in ("range", "months", "point"):
                # realize at AY granule
                d = wspec.get("lo") or wspec.get("lo_month", "") + "-01" \
                    or wspec.get("day")
                return [f"{e} = '{_ay_token(d)}'"]
            raise RuntimeError(f"wspec {typ} on academic_year_token")

        # day-granule anchors (snapshot_effective_date / date_set)
        e = _day_expr(a, anchor["effective_col"])
        if typ == "point":
            return [f"{e} = '{wspec['day']}'"]
        if typ == "range":
            return [f"{e} >= '{wspec['lo']}'", f"{e} < '{wspec['hi_excl']}'"]
        if typ == "months":
            lo, _ = _month_lo_hi(wspec["lo_month"])
            _, hi = _month_lo_hi(wspec["hi_month"])
            return [f"{e} >= '{lo}'", f"{e} < '{hi}'"]
        if typ == "cum":
            return [f"{e} <= '{wspec['hi_incl']}'"]
        raise RuntimeError(f"wspec {typ} on day anchor")

    # -- select/aggregate ----------------------------------------------------
    def _alias_for_col(self, col):
        alias = self.aliases[self.base_node]
        if "." in col:
            tab, c = col.split(".", 1)
            for r in grows(self.gov, "gov_semantic_node", gv=self.gv):
                if r.get("physical_table") == tab and r["node_id"] in self.aliases:
                    return self.aliases[r["node_id"]], c
        return alias, col

    def agg_select(self, mrow):
        m = mrow["measure"]
        if m == "count":
            return "COUNT(*)"
        for pref in ("sum", "avg", "count_distinct"):
            if m.startswith(pref + ":"):
                col = m.split(":", 1)[1]
                alias, col = self._alias_for_col(col)
                fn = {"sum": "SUM", "avg": "AVG", "count_distinct": "COUNT"}[pref]
                inner = (f'DISTINCT {alias}."{col}"' if pref == "count_distinct"
                         else f'{alias}."{col}"')
                return f"{fn}({inner})"
        raise RuntimeError(f"measure {m!r}")

    def body_sql(self, select, anchor=None, wspec=None, group=False):
        s = f'SELECT {select} FROM "{self.node_table(self.base_node)}" t0'
        for a, tab, on in self.joins:
            s += f' INNER JOIN "{tab}" {a} ON {on}'
        parts = self.pred_parts()
        if anchor is not None:
            parts += self.window_pred(anchor, wspec)
        if parts:
            s += " WHERE " + " AND ".join(parts)
        if group:
            s += " GROUP BY 1 ORDER BY 1"
        return s

    def scalar_sql(self, anchor, wspec):
        terms = []
        for mrow in self.measures:
            keep = self.measures
            self.measures = [mrow]
            try:
                body = self.body_sql(self.agg_select(mrow), anchor, wspec)
            finally:
                self.measures = keep
            w = mrow.get("weight")
            if w is None or float(w) == 1.0:
                terms.append(f"({body})")
            else:
                terms.append(f"({body}) * {float(w)}")
        return " + ".join(terms)


# ---------------------------------------------------------------- window derivation
def derive_window_W(qa: dict, binding: dict, leg_key: str):
    """TSQL-W requested window per leg, from NON-GOLD question fields only +
    the latest-version binding row. Returns abstract wspec or None."""
    cw = qa.get("cross_window") or {}
    wreq = qa.get("window_request")
    as_of = qa.get("as_of")
    gran = binding["window_gran"]
    rule = binding["rule_id"]

    if cw and leg_key in cw:
        m = cw[leg_key]  # 'YYYY-MM'
        return {"type": "months", "lo_month": m, "hi_month": m}
    if rule == "point_in_effect":
        return {"type": "pie", "day": as_of}
    if wreq is not None:
        k = wreq.get("kind")
        if k == "day_range":
            return {"type": "range", "lo": wreq["lo"], "hi_excl": wreq["hi_excl"]}
        if k == "week":
            lo = wreq["lo"]
            hi = wreq.get("hi_excl") or (datetime.date.fromisoformat(lo)
                                         + 7 * _DAY).isoformat()
            return {"type": "range", "lo": lo, "hi_excl": hi}
        if k == "month_token_range":
            return {"type": "months", "lo_month": wreq["lo"], "hi_month": wreq["hi"]}
        raise RuntimeError(f"window_request kind {k!r}")
    if as_of is None:
        return None
    if gran == "month_token":
        m = as_of[:7]
        return {"type": "months", "lo_month": m, "hi_month": m}
    if gran == "month":
        lo, hi = _month_lo_hi(as_of[:7])
        return {"type": "range", "lo": lo, "hi_excl": hi}
    if gran == "year":
        y = int(as_of[:4])
        return {"type": "range", "lo": f"{y}-01-01", "hi_excl": f"{y + 1}-01-01"}
    if gran == "academic_year_token":
        return {"type": "ay", "token": _ay_token(as_of)}
    if gran in ("member_day", "day"):
        return {"type": "point", "day": as_of}
    if gran == "cum_day":
        return {"type": "cum", "hi_incl": as_of}
    if gran == "range_request":
        return None  # no requested range on the question face
    raise RuntimeError(f"window_gran {gran!r}")


def derive_window_H(qa: dict):
    """TSQL-H: all valid rows dated <= as_of; no as_of -> no time predicate."""
    as_of = qa.get("as_of")
    if as_of is None:
        return None
    return {"type": "cum", "hi_incl": as_of}


# ---------------------------------------------------------------- arm builder
def build_sql(arm: str, qa: dict, gov: dict, gv: str):
    """Returns (sql, meta) — meta records derived windows + assembly notes."""
    meta = {"graph_version": gv, "windows_derived": {}, "notes": []}
    alias_rows = [a for a in grows(gov, "gov_metric_alias", gv=gv)
                  if a.get("alias_text") == qa.get("metric_alias")]
    assert alias_rows, f"alias {qa.get('metric_alias')!r} unresolved at {gv}"
    metric_id = alias_rows[0]["metric_id"]
    meta["metric_id"] = metric_id
    mrow = grows(gov, "gov_metric", gv=gv, metric_id=metric_id)[0]
    kind = mrow["kind"]
    meta["metric_kind"] = kind

    def binding(leg, mid=metric_id):
        return grows(gov, "gov_temporal_binding", gv=gv, metric_id=mid, leg=leg)[0]

    def anchor_of(brow):
        return grows(gov, "gov_valid_time_anchor", gv=gv,
                     anchor_id=brow["anchor_id"])[0]

    def measures(leg, mid=metric_id):
        ms = sorted(grows(gov, "gov_measure_def", gv=gv, metric_id=mid, leg=leg),
                    key=lambda r: r["measure_id"])
        assert ms, f"no {leg} measures for {mid}@{gv}"
        return ms

    def wspec_for(leg_key, brow):
        if arm == "TSQL-W":
            w = derive_window_W(qa, brow, leg_key)
        else:
            w = derive_window_H(qa)
        meta["windows_derived"][leg_key] = w
        return w

    if kind == "attribute":
        m = measures("atom")[0]
        col = m["measure"].split(":", 1)[1]
        asm = LegAsm(gov, gv, metric_id, "atom", [m], qa.get("scope"))
        a = asm.aliases[m["node_id"]]
        sql = asm.body_sql(f'CAST({a}."{col}" AS VARCHAR)')
        meta["windows_derived"]["atom"] = None
        meta["notes"] += asm.notes + ["attribute: atemporal, no window either arm; "
                                      "raw column value (no disclosure mask)"]
        return sql, meta

    if kind == "delta":
        base_id = mrow["base_metric_id"]
        brow = binding("atom")
        anc = anchor_of(brow)
        ms = measures("atom", base_id)
        periods = qa.get("periods") or []
        assert len(periods) == 2, "delta expects two periods"
        terms = []
        for i, py in enumerate(periods):
            qq = dict(qa, as_of=f"{py}-07-01")
            if arm == "TSQL-W":
                w = derive_window_W(qq, brow, "atom")
            else:
                w = derive_window_H(qa)  # H uses the question's own as_of (None)
            meta["windows_derived"][f"p{i + 1}"] = w
            asm = LegAsm(gov, gv, base_id, "atom", ms, qa.get("scope"))
            terms.append(asm.scalar_sql(anc, w))
            meta["notes"] += asm.notes
        if arm == "TSQL-H" and qa.get("as_of") is None:
            meta["notes"].append("H: no as_of -> both period terms unwindowed "
                                 "(identical); delta degenerates")
        return f"SELECT ({terms[1]}) - ({terms[0]})", meta

    if kind in ("report", "roster"):
        ent = mrow.get("entity_node")
        ms = measures("atom")
        brow = binding("atom")
        anc = anchor_of(brow)
        asm = LegAsm(gov, gv, metric_id, "atom", ms, qa.get("scope"))
        w = wspec_for("atom", brow)
        if mrow.get("report_axis") == "time":
            gran_req = qa.get("requested_time_gran") or "month"
            a = asm.aliases[anc["node_id"]]
            e = _day_expr(a, anc["effective_col"])
            cell = e if gran_req == "day" else f"substr({e},1,7)"
            meta["notes"].append(f"time-axis report at requested granularity "
                                 f"{gran_req!r} (no time-floor check)")
        else:
            req = qa.get("requested_granularity")
            cell = None
            for node, a in asm.aliases.items():
                sk = asm.node_scope_keys(node)
                if req in sk:
                    cell = f'{a}."{sk[req]}"'
                    meta["notes"].append(
                        f"entity report cell = scope-key column for {req!r}")
                    break
            if cell is None:
                ekey = asm.entity_key(ent)
                assert ent in asm.aliases and ekey, \
                    f"entity node {ent} not joined / no key"
                cell = f'{asm.aliases[ent]}."{ekey}"'
                meta["notes"].append(
                    f"entity report cell = entity key {ekey!r} of {ent} "
                    f"(requested level {req!r}; no k-anonymity rollup)")
        m0 = ms[0]
        if m0["measure"] == "ratio_of_base":
            base = grows(gov, "gov_metric", gv=gv,
                         metric_id=mrow["base_metric_id"])[0]
            bnum = measures("num", base["metric_id"])[0]
            bden = measures("den", base["metric_id"])[0]
            assert bnum["node_id"] == bden["node_id"] and \
                not bnum.get("preds") and not bden.get("preds")
            a = asm.aliases[bnum["node_id"]]
            ncol = bnum["measure"].split(":", 1)[1]
            dcol = bden["measure"].split(":", 1)[1]
            sel = (f'{cell} AS cell, SUM({a}."{ncol}") * 1.0 / '
                   f'SUM({a}."{dcol}") AS val')
        else:
            sel = f"{cell} AS cell, {asm.agg_select(m0)} AS val"
        sql = asm.body_sql(sel, anc, w, group=True)
        meta["notes"] += asm.notes
        return sql, meta

    # atomic / ratio scalars
    legnames = ["num", "den"] if kind == "ratio" else ["atom"]
    leg_sql = {}
    for ln in legnames:
        brow = binding(ln)
        anc = anchor_of(brow)
        asm = LegAsm(gov, gv, metric_id, ln, measures(ln), qa.get("scope"))
        w = wspec_for(ln, brow)
        leg_sql[ln] = asm.scalar_sql(anc, w)
        meta["notes"] += [f"[{ln}] {n}" for n in asm.notes]
    if kind == "ratio":
        sql = (f"SELECT ({leg_sql['num']}) * 1.0 / "
               f"NULLIF(({leg_sql['den']}), 0)")
    else:
        sql = f"SELECT ({leg_sql['atom']})"
    return sql, meta


# ---------------------------------------------------------------- window cross-check
def windows_field_to_abstract(w: dict):
    k = w.get("kind")
    if k == "range":
        return {"type": "range", "lo": w["lo"], "hi_excl": w["hi_excl"]}
    if k == "academic_year_token":
        return {"type": "ay", "token": w["token"]}
    if k == "point_in_effect":
        return {"type": "pie", "day": w["day"]}
    if k == "cum":
        return {"type": "cum", "hi_incl": w["hi_incl"], "lo": w.get("lo")}
    if k == "month_token":
        t = w["token"]
        m = f"{t[:4]}-{t[4:6]}" if "-" not in t else t
        return {"type": "months", "lo_month": m, "hi_month": m}
    if k in ("member_day", "day"):
        return {"type": "point", "day": w["day"]}
    if k == "week":
        lo = w["lo"]
        hi = w.get("hi_excl") or (datetime.date.fromisoformat(lo) + 7 * _DAY
                                  ).isoformat()
        return {"type": "range", "lo": lo, "hi_excl": hi}
    if k == "month_token_range":
        return {"type": "months", "lo_month": w["lo"], "hi_month": w["hi"]}
    raise RuntimeError(f"windows field kind {k!r}")


def _canon_wspec(w):
    """Canonical day-interval form for comparison: months -> range."""
    if w and w.get("type") == "months":
        lo, _ = _month_lo_hi(w["lo_month"])
        _, hi = _month_lo_hi(w["hi_month"])
        return {"type": "range", "lo": lo, "hi_excl": hi}
    return w


def crosscheck_windows(q_full: dict, derived: dict) -> dict:
    """Compare TSQL-W derived windows against the question's `windows` field
    (done OUTSIDE the builder; both sides canonicalised months->range).
    Returns {leg: 'ok'|'ok_cum_lo_omitted'|'mismatch(...)'|'skipped'}."""
    wf = q_full.get("windows")
    out = {}
    if not wf:
        return {"_": "skipped (windows field null)"}
    keymap = {}
    if "requested" in wf:
        for leg in derived:
            keymap[leg] = "requested"
    else:
        for leg in derived:
            keymap[leg] = leg
    for leg, wkey in keymap.items():
        if wkey not in wf:
            out[leg] = f"skipped (no {wkey!r} in windows field)"
            continue
        want = _canon_wspec(windows_field_to_abstract(wf[wkey]))
        got = _canon_wspec(derived.get(leg))
        if got is None:
            out[leg] = "mismatch (derived None)"
            continue
        w2 = dict(want)
        g2 = dict(got)
        if want["type"] == "cum" and got["type"] == "cum":
            if want.get("hi_incl") == got.get("hi_incl"):
                out[leg] = ("ok_cum_lo_omitted (guard-free arm has no hull lo; "
                            f"field lo={want.get('lo')})")
                continue
        w2.pop("lo", None) if w2.get("type") == "cum" else None
        out[leg] = "ok" if g2 == {k: v for k, v in w2.items()} else \
            f"mismatch (derived {got} vs field {want})"
    return out


# ---------------------------------------------------------------- execution + scoring
def execute_raw(db: str, sql: str, cap_rows: int = 20):
    try:
        conn = duckdb.connect(db, read_only=True)
        try:
            rows = conn.execute(sql).fetchall()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        return {"exec_ok": False, "error": f"{type(e).__name__}: {e}",
                "n_rows": None, "rows": None, "raw_output": "EXEC_ERROR",
                "bare_null": False}
    jrows = R2._jsonable(rows)
    bare_null = (not rows) or (rows[0][0] is None)
    if len(rows) == 1 and len(rows[0]) == 1:
        v = jrows[0][0]
        raw = "NULL" if v is None else str(v)
    else:
        raw = f"ROWSET({len(rows)} rows)"
    return {"exec_ok": True, "error": None, "n_rows": len(rows),
            "rows": jrows[:cap_rows], "rows_truncated": len(rows) > cap_rows,
            "raw_output": raw, "bare_null": bare_null}


def score_both(q_full: dict, sql: str, db: str, bare_null: bool):
    kind, value, verdict = R2.fetch_and_score(q_full, sql, db)
    v_frozen = verdict
    if q_full["expected_kind"] == "refusal" and bare_null:
        v_null = "correct"
    else:
        v_null = verdict
    return kind, value, v_frozen, v_null


# ---------------------------------------------------------------- main
def main() -> int:
    lines = [assert_frozen_scorer(), assert_import_disjointness()]
    for ln in lines:
        print(ln)

    qs = load_questions()
    ek = {}
    for q, _ in qs:
        ek[q["expected_kind"]] = ek.get(q["expected_kind"], 0) + 1
    assert ek == {"value": 33, "rewrite": 12, "refusal": 15}, ek

    gov_by_dom, gv_by_dom = {}, {}
    for d in domains():
        gov_by_dom[d.name] = load_gov(d)
        lv = latest_version(gov_by_dom[d.name])
        gv_by_dom[d.name] = lv
        print(f"  latest committed version {d.name}: {lv['graph_version']} "
              f"(commit_seq {lv['commit_seq']}, committed_at {lv['committed_at']})")

    ledger = []
    for q, d in qs:
        qa = strip_for_arm(q)
        gov = gov_by_dom[d.name]
        gv = gv_by_dom[d.name]["graph_version"]
        db = str(d / "warehouse.duckdb")
        entry = {
            "qid": q["qid"], "domain": d.name,
            "expected_kind": q["expected_kind"],
            "refusal_reason": q.get("refusal_reason"),
            "metric": q.get("metric"),
            "gold_value": q.get("gold_value"),
            "ver_in_effect": ver_in_effect(gov, q["declared_at"]),
            "latest_version_used": gv,
            "arms": {},
        }
        for arm in ARMS:
            try:
                sql, meta = build_sql(arm, qa, gov, gv)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"builder failed {arm} {q['qid']}: {e}") from e
            ex = execute_raw(db, sql)
            kind, value, v_frozen, v_null = score_both(
                q, sql, db, ex["bare_null"])
            rec = {"sql": sql, **meta, **ex,
                   "scored_kind": kind,
                   "scored_value": value,
                   "verdict_frozen_null_as_error": v_frozen,
                   "verdict_null_as_refusal_credit": v_null}
            if arm == "TSQL-W":
                rec["window_crosscheck"] = crosscheck_windows(
                    q, meta["windows_derived"])
            entry["arms"][arm] = rec
        ledger.append(entry)
        print(f"  {q['qid']:9} W:{entry['arms']['TSQL-W']['verdict_frozen_null_as_error']:>22} "
              f"H:{entry['arms']['TSQL-H']['verdict_frozen_null_as_error']:>22}"
              f"{'  [W NULL]' if entry['arms']['TSQL-W']['bare_null'] else ''}")

    # ---------------- aggregation ----------------
    READINGS = {"null_as_error": "verdict_frozen_null_as_error",
                "null_as_refusal_credit": "verdict_null_as_refusal_credit"}
    by_qid = {e["qid"]: e for e in ledger}
    forms = {"value": 33, "rewrite": 12, "refusal": 15}

    def agg(arm, vkey):
        errs = [e["qid"] for e in ledger
                if e["arms"][arm][vkey] != "correct"]
        byf = {f: {"n": n, "errors": sum(
            1 for e in ledger if e["expected_kind"] == f
            and e["arms"][arm][vkey] != "correct")} for f, n in forms.items()}
        byreason = {}
        for e in ledger:
            if e["expected_kind"] == "refusal":
                r = e["refusal_reason"]
                byreason.setdefault(r, {"n": 0, "errors": 0})
                byreason[r]["n"] += 1
                if e["arms"][arm][vkey] != "correct":
                    byreason[r]["errors"] += 1
        bydom = {}
        for e in ledger:
            bydom.setdefault(e["domain"], {"n": 0, "errors": 0})
            bydom[e["domain"]]["n"] += 1
            if e["arms"][arm][vkey] != "correct":
                bydom[e["domain"]]["errors"] += 1
        tax = {}
        for e in ledger:
            v = e["arms"][arm][vkey]
            tax[v] = tax.get(v, 0) + 1
        return {"error_count": len(errs), "error_rate": len(errs) / 60,
                "error_qids": sorted(errs), "by_form": byf,
                "by_refusal_reason": byreason, "by_domain": bydom,
                "taxonomy": tax}

    summary_arms = {}
    for arm in ARMS:
        nulls_on_refusal = sorted(
            e["qid"] for e in ledger if e["expected_kind"] == "refusal"
            and e["arms"][arm]["bare_null"])
        nulls_total = sorted(e["qid"] for e in ledger
                             if e["arms"][arm]["bare_null"])
        refuse_declared = sum(1 for e in ledger
                              if e["arms"][arm]["scored_kind"] == "refuse")
        summary_arms[arm] = {
            "answered_60_of_60_no_refusal_declaration": refuse_declared == 0,
            "refusal_declarations": refuse_declared,
            "bare_null_qids": nulls_total,
            "bare_null_on_refusal_gold_qids": nulls_on_refusal,
            "readings": {rn: agg(arm, vk) for rn, vk in READINGS.items()},
        }

    # ---------------- version-flip pair table ----------------
    flip_table = []
    for q1, q2 in VERSION_FLIP_PAIRS:
        e1, e2 = by_qid[q1], by_qid[q2]
        rows = []
        for e in (e1, e2):
            w = e["arms"]["TSQL-W"]
            gold = e["gold_value"]
            got = w["scored_value"]
            rel = None
            try:
                if gold not in (None, 0) and isinstance(got, (int, float)):
                    rel = abs(got - float(gold)) / abs(float(gold))
            except (TypeError, ValueError):
                rel = None
            rows.append({
                "qid": e["qid"], "ver_in_effect": e["ver_in_effect"],
                "latest_used": e["latest_version_used"],
                "off_version_side": e["ver_in_effect"] != e["latest_version_used"],
                "gold": gold, "tsql_w_value": got,
                "rel_diff": rel, "within_tol": (rel is not None
                                                and rel <= RP.REL_TOL),
                "tsql_w_verdict": w["verdict_frozen_null_as_error"]})
        flip_table.append({"pair": [q1, q2], "sides": rows})
    off_sides = [s for p in flip_table for s in p["sides"] if s["off_version_side"]]
    off_errs = [s["qid"] for s in off_sides if s["tsql_w_verdict"] != "correct"]
    tol_credit = [s["qid"] for s in off_sides
                  if s["tsql_w_verdict"] == "correct" and s["within_tol"]]

    # ---------------- window cross-check roll-up ----------------
    wc_bad = {}
    for e in ledger:
        wc = e["arms"]["TSQL-W"].get("window_crosscheck") or {}
        bad = {k: v for k, v in wc.items() if v.startswith("mismatch")}
        if bad:
            wc_bad[e["qid"]] = bad

    # ---------------- predictions ----------------
    frozen = json.loads((SANDBOX / "pilot2" / "pilot2_arms_summary.json")
                        .read_text(encoding="utf-8"))
    plain = ["baseline_claude", "baseline_qwen", "baseline_deepseek",
             "baseline_minimax"]
    plain_value = {a: frozen["slices"]["per_gold_form"][a]["value"]["errors"]
                   for a in plain}
    best_plain_value = min(plain_value.values())

    preds = {}
    for rn, vk in READINGS.items():
        w = summary_arms["TSQL-W"]["readings"][rn]
        h = summary_arms["TSQL-H"]["readings"][rn]
        ref_correct_w = 15 - w["by_form"]["refusal"]["errors"]
        ref_correct_h = 15 - h["by_form"]["refusal"]["errors"]
        p1 = (summary_arms["TSQL-W"]["answered_60_of_60_no_refusal_declaration"]
              and summary_arms["TSQL-H"]["answered_60_of_60_no_refusal_declaration"]
              and ref_correct_w == 0 and ref_correct_h == 0)
        p2 = (0.35 <= w["error_rate"] <= 0.60
              and h["error_rate"] >= w["error_rate"])
        p3 = len(off_errs) >= 2
        wv = w["by_form"]["value"]["errors"]
        p4 = wv <= best_plain_value
        preds[rn] = {
            "S2-P1": {"met": p1,
                      "detail": {"refusal_declarations":
                                 {a: summary_arms[a]["refusal_declarations"]
                                  for a in ARMS},
                                 "refusal_correct_W": f"{ref_correct_w}/15",
                                 "refusal_correct_H": f"{ref_correct_h}/15"}},
            "S2-P2": {"met": p2,
                      "detail": {"TSQL-W_error": w["error_rate"],
                                 "TSQL-H_error": h["error_rate"],
                                 "band": [0.35, 0.60]}},
            "S2-P3": {"met": p3,
                      "detail": {"off_version_side_errors": off_errs,
                                 "n_off_sides": len(off_sides),
                                 "within_tolerance_credited": tol_credit}},
            "S2-P4": {"met": p4,
                      "detail": {"TSQL-W_value_errors": f"{wv}/33",
                                 "plain_baseline_value_errors": plain_value,
                                 "best_plain_value_errors":
                                     f"{best_plain_value}/33"}},
        }

    summary = {
        "study": "S2 governance-blind temporal-SQL arms (deterministic, zero LLM)",
        "prereg": {"path": str(PREREG), "sha256": PREREG_SHA},
        "run_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "sandbox_base": str(SANDBOX),
        "import_disjointness": lines[1],
        "frozen_scorer": {"run_pilot_sha256": FROZEN_RUN_PILOT_SHA,
                          "REL_TOL": RP.REL_TOL,
                          "dispatch": "R2.fetch_and_score (frozen §4.2): rowset "
                                      "{CA-Q5,CODE-Q4,DEB-Q5,TH-Q3}, string "
                                      "{CODE-Q6,TH-Q4}, numeric otherwise"},
        "latest_versions": {d: {"graph_version": v["graph_version"],
                                "commit_seq": v["commit_seq"],
                                "committed_at": str(v["committed_at"])}
                            for d, v in gv_by_dom.items()},
        "exclusion_list_enforced": sorted(EXCLUDE_FIELDS) + ["refusal_*"],
        "null_edge_rule": "raw SQL result emitted; bare NULL recorded as 'NULL'; "
                          "no refusal declaration ever; both scoring readings "
                          "computed (frozen-literal NULL-as-error AND "
                          "NULL-as-implicit-refusal-credit)",
        "arms": summary_arms,
        "version_flip_pairs": flip_table,
        "off_version_sides_errors_TSQL_W": off_errs,
        "window_crosscheck_mismatches": wc_bad,
        "predictions": preds,
        "notes": [
            "TSQL-W realizes every requested window in the anchor's native "
            "granule (day windows on token anchors become covering token "
            "ranges); DEB-Q7's week request therefore lands on month token "
            "201303 and yields a number (answered_should_refuse under both "
            "readings). The alternative literal day-string comparison on the "
            "token column would yield NULL and flip DEB-Q7 to correct only "
            "under the null-credit reading.",
            "CARD-Q6 (collector_premium): the legs' anchor node card.sets is "
            "not reachable from the latest-version route rows for those legs "
            "(the den route is dst_caliber='none' with no join); the guard-"
            "free arm aggregates unfiltered — verdict unaffected "
            "(refusal-gold, answers a number).",
        ],
    }

    (OUT / "tsql_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "tsql_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"arms": {a: {rn: summary_arms[a]["readings"][rn]["error_count"]
                                   for rn in READINGS}
                               for a in ARMS},
                      "predictions": {rn: {k: v["met"] for k, v in preds[rn].items()}
                                      for rn in preds},
                      "off_version_errors": off_errs,
                      "window_crosscheck_mismatches": list(wc_bad)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
