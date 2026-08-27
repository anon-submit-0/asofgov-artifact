#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v6aplus.py — V6a+ structural template-membership check (post-registration
hardening, PREREG_poststudy3_20260826.md sha256
426017ddfd8af8608e452b44175e2158c620c2e8cebe3a17572ee3fe15d7a192).

Trigger: the 2026-08-26 external review (Codex) demonstrated that V6a's
containment-only scan accepts semantically wrong mutations of a genuine
certificate (COUNT(DISTINCT …) numerator, swapped legs, constant multi-row
SELECT, narrowed-in-window predicate).  V6a+ closes that class by parsing the
answer SQL with DuckDB's own parser (json_serialize_sql — no new dependency)
and validating the parse tree, fail-closed, against the independently loaded
governance seeds (gov_metric / gov_measure_def / gov_caliber_routing /
gov_valid_time_anchor / gov_semantic_node, all re-queried from G_v at the
pinned version — never trusted from the certificate).

The five check families of the prereg:
  1. template membership, fail-closed  — anything unparseable, non-scalar for
     a scalar metric kind, constant-only, or outside the registered template
     class of the metric's kind (single aggregate per leg; ratio = leg/leg;
     delta = leg−leg; report = (cell,val) group-by-1 or the scalar atom form;
     attribute = registered-value projection) is REJECT;
  2. measure implementation           — each leg's aggregate function and
     argument must implement that leg's registered gov_measure_def measure
     (count → COUNT(*); count_distinct:<key> → COUNT(DISTINCT key);
     sum:<col> / avg:<col> → SUM/AVG of the registered column — the
     registered form, not a lookalike);
  3. leg-role binding                 — the numerator position must be
     computed from the numerator leg's registered node/table/column and the
     denominator position from the denominator leg's (swapped legs REJECT;
     the delta minuend is the later certified period, the subtrahend the
     earlier one);
  4. registered predicates            — every predicate registered for the
     binding (the time window on the anchor column, with the certified
     constants, plus the non-temporal registered measure predicates) must
     appear; the window denotation must EQUAL the certified role window
     (narrowing or widening REJECT); every extra predicate must be a
     registered question-scope predicate (gov_semantic_node.scope_keys with
     the question's own value) — anything else REJECTs;
  5. join keys                        — multi-table legs must join exactly on
     the registered routing keys (INNER equality joins on
     gov_caliber_routing.join_on pairs only).

Reason codes (machine-readable; the FAIL detail is
"<CODE>: text[; <CODE>: text …]" with the primary code first):

  V6P_PARSE      SQL does not parse to exactly one plain SELECT statement
                 (parser error, multi-statement, serializer failure) —
                 fail-closed.
  V6P_KIND       the metric's kind cannot be resolved from gov_metric at the
                 pinned version, or the kind admits no SQL answer template.
  V6P_SHAPE      statement shape outside the registered template class
                 (set operation, CTE, DISTINCT/LIMIT/sample modifiers,
                 HAVING/QUALIFY, derived tables, wrong select-list arity,
                 constant-only or non-scalar output, missing scalar-subquery
                 leg wrap, unresolvable column reference).
  V6P_MEASURE    a leg's aggregate does not implement the leg's registered
                 measure (wrong function, wrong argument column, DISTINCT
                 flag not registered, FILTER clause, or a multi-row/weighted
                 measure family no single aggregate can implement).
  V6P_LEG_ROLE   a leg is not computed from its role's registered node/table
                 (leg swap, wrong base relation, wrong delta period order).
  V6P_PREDICATE  a registered predicate is missing or carries wrong
                 constants, or the SQL carries an extra predicate that is
                 neither registered nor justified by the question's own
                 scope (gov_semantic_node.scope_keys).
  V6P_WINDOW     the leg's time-predicate denotation does not equal the
                 certified role window (narrowed, widened, shifted, missing,
                 wrong anchor column/alias, or wrong in-effect form).
  V6P_JOIN       a join is not a registered routing equality for this
                 metric's legs (wrong keys, wrong tables, or a non-INNER /
                 non-equality join).
  V6P_TABLE      a FROM relation lies outside the leg's registered closure.
  V6P_ARITY      (PREREG_poststudy4_20260827, fix 2) the executed answer SQL
                 does not have the certified row/column arity — exactly one
                 row and one column for a scalar (atomic/ratio/delta) or an
                 attribute metric, or the (cell,val) report arity (>=1 row x 2
                 columns, or the 1x1 scalar-atom spelling). This is the ONLY
                 code raised by the appended execution-shape check (check id
                 V6a+x), which is the first V6a+-family site to EXECUTE the
                 answer SQL (read-only, via the same connection the V6b/V6c
                 probes use); all structural checks above remain parse-only.

Round-2 hardening (PREREG_poststudy4_20260827.md sha256
a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75): a second
external review (Codex 2026-08-27) showed the round-1 V6a+ still ACCEPTed a
genuine ratio/delta certificate whose outer SELECT carried a top-level WHERE
filtering the scalar answer to zero rows (WHERE 1=0, WHERE 'a'='b'), because
_check_ratio/_check_delta did not reject an outer where_clause and nothing
executed the answer to check its shape. Fix 1 closes the structure
(_plain_node rejects a non-null outer WHERE by default -> V6P_SHAPE); fix 2
adds the execution-shape backstop (V6P_ARITY). The genuine certificates carry
no outer WHERE and keep their 1x1 (or certified report/attribute) arity, so
both remain invariant on the genuine corpus.

Red lines kept: this module imports NOTHING from any compiler tree (stdlib
only; the DuckDB parser is reached through the verifier's own read-only
connection passed in via cx.con), and it never trusts a certificate field it
can re-derive: measures, routings, anchors, scope keys and node tables are
re-read from G_v; only the certified role WINDOWS (α) — the object V0
independently re-derives — and the question's own scope values are consumed.
Registered equivalences encoded (corpus-wide spellings, never
per-certificate): `x * 1.0 / NULLIF(y, 0)` ≡ `x * 1.0 / y` ≡ `x / y` for the
ratio combiner; IN-list order; conjunct order; alias names; the three
registered day/token comparison spellings (substr(CAST(c AS VARCHAR),1,10),
CAST(c AS VARCHAR) vs calendar token, plain string/DATE comparison).
"""
from __future__ import annotations

import json

REASON_CODES = ("V6P_PARSE", "V6P_KIND", "V6P_SHAPE", "V6P_MEASURE",
                "V6P_LEG_ROLE", "V6P_PREDICATE", "V6P_WINDOW", "V6P_JOIN",
                "V6P_TABLE", "V6P_ARITY")

_DATE_RE_FULL = None  # set lazily from helpers (re module use kept local)


# ---------------------------------------------------------------- utilities

def _const_value(e):
    """Decode a VALUE_CONSTANT AST node to a python value; None if not one."""
    if not isinstance(e, dict) or e.get("class") != "CONSTANT":
        return None
    v = e.get("value") or {}
    if v.get("is_null"):
        return ("NULL",)
    tid = ((v.get("type") or {}).get("id") or "").upper()
    raw = v.get("value")
    if tid in ("INTEGER", "BIGINT", "SMALLINT", "TINYINT", "UINTEGER",
               "UBIGINT", "HUGEINT"):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    if tid == "DECIMAL":
        ti = (v.get("type") or {}).get("type_info") or {}
        scale = ti.get("scale") or 0
        try:
            return int(raw) / (10 ** int(scale))
        except (TypeError, ValueError):
            return None
    if tid in ("FLOAT", "DOUBLE"):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    if tid == "VARCHAR":
        return str(raw)
    if tid == "DATE":
        return str(raw)
    return ("UNSUPPORTED", tid)


def _is_const(e, want):
    """Node `e` is a VALUE_CONSTANT equal to `want` (0 and 1.0 included —
    constants are compared via sentinel-free None checks, never truthiness)."""
    cv = _const_value(e)
    return cv is not None and not isinstance(cv, tuple) and _num_eq(cv, want)


def _num_eq(a, b):
    """Constant comparison across int/float/str spellings of numbers."""
    if isinstance(a, str) or isinstance(b, str):
        if isinstance(a, str) and isinstance(b, str):
            return a == b
        try:
            return float(a) == float(b)
        except (TypeError, ValueError):
            return False
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def _colref(e):
    """(qualifier|None, column) of a COLUMN_REF node, else None."""
    if not isinstance(e, dict) or e.get("class") != "COLUMN_REF":
        return None
    names = e.get("column_names") or []
    if len(names) == 1:
        return (None, names[0])
    if len(names) == 2:
        return (names[0], names[1])
    return None


def _strip_cast_varchar(e):
    """CAST(col AS VARCHAR) -> col node; else None."""
    if isinstance(e, dict) and e.get("class") == "CAST" and \
            ((e.get("cast_type") or {}).get("id") or "").upper() == "VARCHAR" and \
            not e.get("try_cast"):
        return e.get("child")
    return None


def _fn(e):
    return (e or {}).get("function_name") if isinstance(e, dict) and \
        e.get("class") == "FUNCTION" else None


def _substr_day_col(e):
    """substr(CAST(col AS VARCHAR), 1, 10) -> col node; else None."""
    if _fn(e) not in ("substr", "substring"):
        return None
    ch = e.get("children") or []
    if len(ch) != 3:
        return None
    inner = _strip_cast_varchar(ch[0])
    if inner is None:
        return None
    if _const_value(ch[1]) == 1 and _const_value(ch[2]) == 10:
        return inner
    return None


_CMP_OPS = {
    "COMPARE_EQUAL": "=", "COMPARE_GREATERTHAN": ">",
    "COMPARE_GREATERTHANOREQUALTO": ">=", "COMPARE_LESSTHAN": "<",
    "COMPARE_LESSTHANOREQUALTO": "<=",
}


def _flatten_and(e, out):
    if isinstance(e, dict) and e.get("type") == "CONJUNCTION_AND":
        for c in e.get("children") or []:
            _flatten_and(c, out)
    elif e is not None:
        out.append(e)
    return out


def _walk_classes(e):
    """All (class, type, function_name) triples in an expression subtree."""
    out = []
    if isinstance(e, dict):
        out.append((e.get("class"), e.get("type"), e.get("function_name")))
        for k in ("children", "child", "left", "right", "subquery",
                  "case_checks", "else_expr", "when_expr", "then_expr"):
            v = e.get(k)
            if isinstance(v, dict):
                out.extend(_walk_classes(v))
            elif isinstance(v, list):
                for c in v:
                    out.extend(_walk_classes(c))
    return out


def _colrefs_in(e):
    out = []
    if isinstance(e, dict):
        if e.get("class") == "COLUMN_REF":
            r = _colref(e)
            if r:
                out.append(r)
        for k in ("children", "child", "left", "right",
                  "case_checks", "else_expr", "when_expr", "then_expr"):
            v = e.get(k)
            if isinstance(v, dict):
                out.extend(_colrefs_in(v))
            elif isinstance(v, list):
                for c in v:
                    out.extend(_colrefs_in(c))
    return out


_AGG_FUNCS = {"count_star", "count", "sum", "avg", "min", "max"}


def _has_agg_or_subquery(e):
    for cls, typ, fn in _walk_classes(e):
        if cls == "SUBQUERY":
            return True
        if cls == "FUNCTION" and (fn or "").lower() in _AGG_FUNCS:
            return True
        if cls == "WINDOW":
            return True
    return False


# ---------------------------------------------------------------- FROM shape

class LegFrom:
    """Decomposed FROM tree of one leg: base tables and inner-join equalities."""

    def __init__(self):
        self.aliases = {}      # alias(lower) -> table name (lower, unquoted)
        self.tables = []       # table names in FROM order (lower)
        self.joins = []        # list of ON-condition conjuncts (AST nodes)
        self.bad = None        # first structural offence (msg) or None


def _from_tree(ft, out):
    if not isinstance(ft, dict):
        out.bad = out.bad or "FROM clause missing"
        return out
    t = ft.get("type")
    if t == "BASE_TABLE":
        tbl = (ft.get("table_name") or "").strip('"').lower()
        alias = (ft.get("alias") or ft.get("table_name") or "").strip('"').lower()
        if not tbl:
            out.bad = out.bad or "unnamed base table"
            return out
        if alias in out.aliases:
            out.bad = out.bad or "duplicate correlation name %r" % alias
            return out
        out.aliases[alias] = tbl
        out.tables.append(tbl)
        return out
    if t == "JOIN":
        if ft.get("join_type") != "INNER" or ft.get("ref_type") != "REGULAR":
            out.bad = out.bad or ("non-INNER or non-regular join (%s/%s)"
                                  % (ft.get("join_type"), ft.get("ref_type")))
            return out
        _from_tree(ft.get("left"), out)
        _from_tree(ft.get("right"), out)
        conds = _flatten_and(ft.get("condition"), [])
        if not conds:
            out.bad = out.bad or "join without ON condition"
        out.joins.extend(conds)
        return out
    out.bad = out.bad or "FROM relation of unsupported type %r" % t
    return out


# ---------------------------------------------------------------- main check

class _Reject(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _measure_split(measure):
    """Registered measure string -> (kind, arg|None).
    kinds: count / count_distinct / sum / avg / value / ratio_of_base."""
    m = str(measure or "")
    if m == "count":
        return ("count", None)
    if m == "ratio_of_base":
        return ("ratio_of_base", None)
    for k in ("count_distinct", "sum", "avg", "value"):
        if m.startswith(k + ":"):
            return (k, m[len(k) + 1:])
    return (None, m)


class V6aPlus:
    """One certificate's structural validation. `cx` is chk's Ctx (duck-typed:
    only gv/q/alpha/sql/con/dec are touched); `H` carries chk's frozen window
    arithmetic (single source of truth — no re-implementation here)."""

    def __init__(self, cx, H):
        self.cx = cx
        self.H = H
        self.gv = cx.gv
        self.metric = H["base_metric"](cx.q.get("metric"))
        self.problems = []

    # ---------------- seed access (re-queried from G_v) ----------------

    def _node_table(self, node_id):
        t = self.gv.node_table(node_id)
        return str(t).strip('"').lower() if t else None

    def _node_rows(self):
        return self.gv.rows("gov_semantic_node") or []

    def _anchor_row(self, anchor_id):
        return self.gv.anchor(anchor_id) if isinstance(anchor_id, str) else None

    def _measures(self, metric, leg):
        return self.gv.measures(metric, leg)

    def _hop_pairs(self, metrics):
        """Registered join equalities for the given metric ids, as a list of
        frozenset({(table, col), (table2, col2)}) with orientation kept
        alongside: (frozenset, (src_tbl, src_col), (dst_tbl, dst_col))."""
        out = []
        for m in metrics:
            for r in self.gv.metric_routings(m):
                st = self._node_table(r.get("src_node"))
                dt = self._node_table(r.get("dst_node"))
                for pair in (r.get("join_keys") or []):
                    if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
                        continue
                    sc, dc = str(pair[0]).lower(), str(pair[1]).lower()
                    if st and dt:
                        out.append((frozenset(((st, sc), (dt, dc))),
                                    (st, sc), (dt, dc)))
        return out

    def _leg_tables(self, metrics, extra_nodes=()):
        """Registered closure of tables a leg may read: measure nodes and
        their pred nodes, routing hop endpoints, plus explicit extra nodes."""
        tabs = set()
        for m in metrics:
            for leg in ("num", "den", "atom", "scope", "entity"):
                for r in self._measures(m, leg):
                    t = self._node_table(r.get("node_id"))
                    if t:
                        tabs.add(t)
                    for p in (r.get("preds") or []):
                        if p.get("node"):
                            t2 = self._node_table(p["node"])
                            if t2:
                                tabs.add(t2)
            for r in self.gv.metric_routings(m):
                for t in (self._node_table(r.get("src_node")),
                          self._node_table(r.get("dst_node"))):
                    if t:
                        tabs.add(t)
        for n in extra_nodes:
            t = self._node_table(n) if n and "." in str(n) else (
                str(n).strip('"').lower() if n else None)
            if t:
                tabs.add(t)
        return tabs

    # ---------------- constants / scope ----------------

    def _scope_values(self):
        """Question-declared scope values, exactly as declared (never widened
        by the certificate). {} when the question declares none."""
        sc = self.cx.q.get("scope")
        vals = {}
        if isinstance(sc, dict):
            for k, v in sc.items():
                vals[str(k)] = v
        p = self.cx.q.get("params")
        if isinstance(p, dict):
            for k, v in p.items():
                vals.setdefault(str(k), v)
        return vals

    def _scope_pred_ok(self, tbl, col, const):
        """Is (tbl.col = const) a REGISTERED scope predicate carrying the
        question's own value? gov_semantic_node.scope_keys is the registry.
        Returns the matched scope key, or None."""
        for r in self._node_rows():
            t = str(r.get("physical_table") or "").strip('"').lower()
            if t != tbl:
                continue
            sk = r.get("scope_keys")
            if isinstance(sk, str):
                try:
                    sk = json.loads(sk)
                except ValueError:
                    sk = None
            if not isinstance(sk, dict):
                continue
            for key, pcol in sk.items():
                if str(pcol).lower() != col:
                    continue
                qv = self._scope_values().get(str(key))
                if qv is not None and _num_eq(const, qv):
                    return str(key)
        return None

    def _required_scope_keys(self, leg_tables):
        """Question scope keys an ANSWER leg must implement: every declared
        scope key whose registered scope_keys mapping lands on a table inside
        this leg's registered closure. (REWRITE certificates may coarsen a
        scope axis away — that narrowing is V5's rollup/mask jurisdiction —
        so the requirement binds dec=ANSWER only.)"""
        req = {}
        sc = self.cx.q.get("scope")
        declared = {str(k): v for k, v in sc.items()
                    if v is not None} if isinstance(sc, dict) else {}
        if not declared:
            return req
        for r in self._node_rows():
            t = str(r.get("physical_table") or "").strip('"').lower()
            if t not in leg_tables:
                continue
            sk = r.get("scope_keys")
            if isinstance(sk, str):
                try:
                    sk = json.loads(sk)
                except ValueError:
                    sk = None
            if not isinstance(sk, dict):
                continue
            for key in sk:
                if str(key) in declared:
                    req.setdefault(str(key), []).append(
                        (t, str(sk[key]).lower()))
        return req

    def _entity_key(self, tbl):
        for r in self._node_rows():
            t = str(r.get("physical_table") or "").strip('"').lower()
            if t == tbl and r.get("entity_key"):
                return str(r["entity_key"]).lower()
        return None

    # ---------------- alias / column resolution ----------------

    def _resolve_col(self, lf, ref):
        """(alias|None, col) -> (alias, table, col) or _Reject V6P_SHAPE."""
        if ref is None:
            raise _Reject("V6P_SHAPE", "unsupported column reference")
        qual, col = ref
        col_l = str(col).strip('"').lower()
        if qual is not None:
            a = str(qual).strip('"').lower()
            if a not in lf.aliases:
                raise _Reject("V6P_SHAPE",
                              "column qualifier %r names no FROM relation" % qual)
            return (a, lf.aliases[a], col_l)
        if len(lf.aliases) == 1:
            a = next(iter(lf.aliases))
            return (a, lf.aliases[a], col_l)
        raise _Reject("V6P_SHAPE",
                      "unqualified column %r in a multi-relation leg" % col)

    def _role_alias(self, lf, role_tbl, hop_pairs):
        """Alias of the leg's measured (role) occurrence of role_tbl.
        Unique occurrence -> that alias; self-join -> the alias standing on
        the registered hop's src side; otherwise fail-closed."""
        hits = [a for a, t in lf.aliases.items() if t == role_tbl]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise _Reject("V6P_LEG_ROLE",
                          "registered role table %r absent from the leg's FROM"
                          % role_tbl)
        # self-join: find an ON equality matching a registered self-hop and
        # take the alias bound to the src column.
        for cond in lf.joins:
            if (cond or {}).get("type") != "COMPARE_EQUAL":
                continue
            lr = _colref(cond.get("left"))
            rr = _colref(cond.get("right"))
            if not lr or not rr:
                continue
            try:
                la, lt, lc = self._resolve_col(lf, lr)
                ra, rt, rc = self._resolve_col(lf, rr)
            except _Reject:
                continue
            for pairset, (st, sc), (dt, dc) in hop_pairs:
                if st == dt == role_tbl and \
                        frozenset(((lt, lc), (rt, rc))) == pairset:
                    if (lt, lc) == (st, sc):
                        return la
                    if (rt, rc) == (st, sc):
                        return ra
        raise _Reject("V6P_LEG_ROLE",
                      "cannot bind the measured occurrence of self-joined "
                      "table %r to the registered hop orientation" % role_tbl)

    # ---------------- joins ----------------

    def _check_joins(self, lf, hop_pairs):
        for cond in lf.joins:
            if (cond or {}).get("type") != "COMPARE_EQUAL":
                raise _Reject("V6P_JOIN", "join condition is not an equality")
            lr = _colref(cond.get("left"))
            rr = _colref(cond.get("right"))
            if not lr or not rr:
                raise _Reject("V6P_JOIN",
                              "join equality is not column = column")
            _, lt, lc = self._resolve_col(lf, lr)
            _, rt, rc = self._resolve_col(lf, rr)
            got = frozenset(((lt, lc), (rt, rc)))
            if not any(got == pairset for pairset, _s, _d in hop_pairs):
                raise _Reject("V6P_JOIN",
                              "join %s.%s = %s.%s is not a registered routing "
                              "key for this metric" % (lt, lc, rt, rc))

    # ---------------- time-window atoms ----------------

    def _time_atom(self, conj, lf):
        """Recognise one registered time-comparison conjunct. Returns
        (alias, table, col, op, literal) or None (not a time form)."""
        typ = (conj or {}).get("type")
        if typ not in _CMP_OPS:
            return None
        op = _CMP_OPS[typ]
        left, right = conj.get("left"), conj.get("right")
        # normalise: constant on the right
        cv = _const_value(right)
        if cv is None and _const_value(left) is not None:
            left, right = right, left
            cv = _const_value(right)
            op = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op)
        if not isinstance(cv, str):
            return None
        col_node = _substr_day_col(left)
        if col_node is None:
            col_node = _strip_cast_varchar(left)
        if col_node is None and isinstance(left, dict) and \
                left.get("class") == "COLUMN_REF":
            col_node = left
        if col_node is None:
            return None
        ref = _colref(col_node)
        if ref is None:
            return None
        lit = cv
        if not self._is_time_literal(lit):
            return None
        a, t, c = self._resolve_col(lf, ref)
        return (a, t, c, op, lit)

    def _is_time_literal(self, s):
        import re
        return bool(re.fullmatch(
            r"\d{4}-\d{2}-\d{2}|\d{6}|\d{4}-\d{2}|\d{4}-\d{4}", str(s)))

    def _lit_window(self, op, lit):
        """Day-space window of `col OP lit` (token literals expand to their
        granule window; frozen arithmetic from chk via H)."""
        H = self.H
        import re
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lit):
            d = H["parse_day"](lit)
            lo, hi = d, d + H["DAY"]
        else:
            w = H["token_day_window"](lit)
            if w is None:
                raise _Reject("V6P_WINDOW", "unknown calendar token %r" % lit)
            lo, hi = w[0][0], w[-1][1]
        if op == "=":
            return ((lo, hi),)
        if op == ">=":
            return ((lo, None),)
        if op == ">":
            return ((hi, None),)
        if op == "<":
            return ((None, lo),)
        if op == "<=":
            return ((None, hi),)
        raise _Reject("V6P_WINDOW", "unsupported time operator %r" % op)

    def _check_window(self, lf, atoms, alpha_ent, anchor_row, role_tbl,
                      hop_pairs, in_effect_parts, role_alias=None):
        """Family 4's temporal half: the atoms on the anchor binding must
        denote EXACTLY the certified role window."""
        H = self.H
        win = (alpha_ent or {}).get("window")
        arow = anchor_row
        if win is None:
            # atemporal role (attribute): no time predicate may exist
            if atoms or in_effect_parts:
                raise _Reject("V6P_WINDOW",
                              "time predicate present but the certified role "
                              "is atemporal")
            return
        if not arow:
            raise _Reject("V6P_WINDOW",
                          "certified window without a registered anchor row")
        vf = (arow.get("valid_from_col") or "").strip('"').lower()
        vt = (arow.get("valid_to_col") or "").strip('"').lower()
        eff = (arow.get("effective_date") or "").strip('"').lower()
        atbl = str(arow.get("semantic_object") or "").strip('"').lower()
        if vf and vt and not eff:
            # interval (in-effect) anchor over a D7 point window {d}
            days = [lo for (lo, hi) in win
                    if lo is not None and hi is not None and
                    (hi - lo) == H["DAY"]]
            if len(days) != 1 or len(win) != 1:
                raise _Reject("V6P_WINDOW",
                              "interval anchor with a non-point certified "
                              "window %s" % H["w_str"](win))
            d = days[0]
            alias = self._anchor_alias(lf, atbl, role_tbl, role_alias)
            lo_ok = any(a == alias and c == vf and op == "<=" and
                        H["parse_day"](lit) == d
                        for (a, t, c, op, lit) in atoms
                        if self._is_day_lit(lit))
            hi_ok = in_effect_parts.get((alias, vt)) == d
            extra = [x for x in atoms if not (x[0] == alias and x[2] == vf)]
            if not lo_ok:
                raise _Reject("V6P_WINDOW",
                              "in-effect lower bound `%s <= '%s'` not replayed"
                              % (vf, d.isoformat()))
            if not hi_ok:
                raise _Reject("V6P_WINDOW",
                              "in-effect upper form `(%s IS NULL OR %s > '%s')`"
                              " not replayed" % (vt, vt, d.isoformat()))
            if extra:
                raise _Reject("V6P_WINDOW",
                              "extra time predicate outside the registered "
                              "in-effect pair: %s" % sorted(
                                  "%s.%s" % (x[1], x[2]) for x in extra))
            return
        if not eff:
            raise _Reject("V6P_WINDOW",
                          "anchor registers no effective/valid columns")
        if in_effect_parts:
            raise _Reject("V6P_WINDOW",
                          "IS NULL/OR time form on an effective-date anchor")
        alias = self._anchor_alias(lf, atbl, role_tbl, role_alias)
        mine = [x for x in atoms if x[0] == alias and x[2] == eff]
        alien = [x for x in atoms if not (x[0] == alias and x[2] == eff)]
        if alien:
            raise _Reject("V6P_WINDOW",
                          "time predicate on a non-anchor column/alias: %s"
                          % sorted("%s.%s" % (x[1], x[2]) for x in alien))
        if not mine:
            raise _Reject("V6P_WINDOW",
                          "certified window %s has no time predicate on "
                          "anchor column %s.%s" % (H["w_str"](win), atbl, eff))
        den = ((None, None),)
        for (_a, _t, _c, op, lit) in mine:
            den = H["w_intersect"](den, self._lit_window(op, lit))
        if not H["w_eq"](den, win):
            raise _Reject("V6P_WINDOW",
                          "time predicate denotation %s != certified role "
                          "window %s" % (H["w_str"](den), H["w_str"](win)))

    def _is_day_lit(self, lit):
        import re
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(lit)))

    def _anchor_alias(self, lf, tbl, role_tbl=None, role_alias=None):
        """Alias carrying the anchor binding. Unique occurrence -> that
        alias. When the anchor's node coincides with the measured node (the
        registered coincidence, e.g. code.posts anchoring code.accepted_rate
        legs), the anchored occurrence IS the measured occurrence — the
        hop-src alias already bound by _role_alias. Anything else stays
        fail-closed."""
        hits = [a for a, t in lf.aliases.items() if t == tbl]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise _Reject("V6P_WINDOW",
                          "anchor table %r absent from the leg's FROM" % tbl)
        if role_alias is not None and tbl == role_tbl:
            return role_alias
        raise _Reject("V6P_WINDOW",
                      "anchor table %r occurs %d times and is not the "
                      "measured node; the anchor binding is ambiguous"
                      % (tbl, len(hits)))

    # ---------------- in-effect OR-form recognition ----------------

    def _in_effect_part(self, conj, lf):
        """`(vt IS NULL OR vt > 'd')` -> ((alias, col), day). None otherwise."""
        if (conj or {}).get("type") != "CONJUNCTION_OR":
            return None
        ch = conj.get("children") or []
        if len(ch) != 2:
            return None
        isnull, cmpn = None, None
        for c in ch:
            if c.get("type") == "OPERATOR_IS_NULL":
                isnull = c
            elif c.get("type") in _CMP_OPS:
                cmpn = c
        if isnull is None or cmpn is None:
            return None
        inner = (isnull.get("children") or [None])[0]
        ref0 = _colref(inner) or _colref(_strip_cast_varchar(inner) or
                                         _substr_day_col(inner) or {})
        atom = self._time_atom(cmpn, lf)
        if ref0 is None or atom is None:
            return None
        a0, t0, c0 = self._resolve_col(lf, ref0)
        a1, t1, c1, op, lit = atom
        if (a0, c0) != (a1, c1) or op != ">" or not self._is_day_lit(lit):
            return None
        return ((a1, c1), self.H["parse_day"](lit))

    # ---------------- measure predicates ----------------

    def _match_measure_pred(self, conj, lf, pred, role_tbl, role_alias):
        """Does `conj` implement the registered pred (on the pred's node table
        — the measured alias when the pred binds the role table itself)?"""
        ptbl = self._node_table(pred.get("node")) if pred.get("node") else role_tbl
        pcol = str(pred.get("col") or "").strip('"').lower()
        op = pred.get("op")
        val = pred.get("value")

        def _bind_ok(a, t, c):
            if t != ptbl or c != pcol:
                return False
            if t == role_tbl and a != role_alias:
                return False
            if t != role_tbl:
                # non-role table: require the unique occurrence
                hits = [x for x, tt in lf.aliases.items() if tt == t]
                return len(hits) == 1 and a == hits[0]
            return True

        typ = (conj or {}).get("type")
        if op == "=":
            if typ != "COMPARE_EQUAL":
                return False
            for l, r in ((conj.get("left"), conj.get("right")),
                         (conj.get("right"), conj.get("left"))):
                ref = _colref(l)
                cv = _const_value(r)
                if ref is None or cv is None or isinstance(cv, tuple):
                    continue
                a, t, c = self._resolve_col(lf, ref)
                if _bind_ok(a, t, c) and _num_eq(cv, val):
                    return True
            return False
        if op == "in":
            if typ != "COMPARE_IN":
                return False
            ch = conj.get("children") or []
            if not ch:
                return False
            ref = _colref(ch[0])
            if ref is None:
                return False
            a, t, c = self._resolve_col(lf, ref)
            if not _bind_ok(a, t, c):
                return False
            consts = [_const_value(x) for x in ch[1:]]
            if any(v is None or isinstance(v, tuple) for v in consts):
                return False
            want = list(val if isinstance(val, (list, tuple)) else [val])
            if len(consts) != len(want):
                return False
            unmatched = list(want)
            for cv in consts:
                hit = next((i for i, w in enumerate(unmatched)
                            if _num_eq(cv, w)), None)
                if hit is None:
                    return False
                unmatched.pop(hit)
            return not unmatched
        if op in (">=", ">", "<=", "<"):
            if _CMP_OPS.get(typ) != op:
                # allow the mirrored spelling const OP col
                pass
            for l, r, o in ((conj.get("left"), conj.get("right"),
                             _CMP_OPS.get(typ)),
                            (conj.get("right"), conj.get("left"),
                             {"<": ">", ">": "<", "<=": ">=",
                              ">=": "<="}.get(_CMP_OPS.get(typ)))):
                ref = _colref(l)
                cv = _const_value(r)
                if ref is None or cv is None or isinstance(cv, tuple) or o != op:
                    continue
                a, t, c = self._resolve_col(lf, ref)
                if _bind_ok(a, t, c) and _num_eq(cv, val):
                    return True
            return False
        if op == "is_null":
            if typ != "OPERATOR_IS_NULL":
                return False
            ref = _colref((conj.get("children") or [None])[0])
            if ref is None:
                return False
            a, t, c = self._resolve_col(lf, ref)
            return _bind_ok(a, t, c)
        if op == "not_null":
            if typ != "OPERATOR_IS_NOT_NULL":
                return False
            ref = _colref((conj.get("children") or [None])[0])
            if ref is None:
                return False
            a, t, c = self._resolve_col(lf, ref)
            return _bind_ok(a, t, c)
        if op in (">col", "=col", "<col", ">=col", "<=col"):
            want_op = {"=col": "=", ">col": ">", "<col": "<",
                       ">=col": ">=", "<=col": "<="}[op]
            if _CMP_OPS.get(typ) not in (want_op,
                                         {"<": ">", ">": "<", "<=": ">=",
                                          ">=": "<=", "=": "="}[want_op]):
                return False
            lr = _colref(conj.get("left"))
            rr = _colref(conj.get("right"))
            if not lr or not rr:
                return False
            la, lt, lc = self._resolve_col(lf, lr)
            ra, rt, rc = self._resolve_col(lf, rr)
            ocol = str(val or "").strip('"').lower()
            if _CMP_OPS.get(typ) == want_op:
                return _bind_ok(la, lt, lc) and (rt, rc) == (ptbl, ocol)
            return _bind_ok(ra, rt, rc) and (lt, lc) == (ptbl, ocol)
        return False

    # ---------------- scope conjunct ----------------

    def _scope_conjunct_ok(self, conj, lf):
        """Matched registered scope key of a `col = const` conjunct carrying
        the question's own value, else None."""
        if (conj or {}).get("type") != "COMPARE_EQUAL":
            return None
        for l, r in ((conj.get("left"), conj.get("right")),
                     (conj.get("right"), conj.get("left"))):
            ref = _colref(l)
            cv = _const_value(r)
            if ref is None or cv is None or isinstance(cv, tuple):
                continue
            try:
                a, t, c = self._resolve_col(lf, ref)
            except _Reject:
                return None
            key = self._scope_pred_ok(t, c, cv)
            if key is not None:
                return key
        return None

    def _check_scope_complete(self, leg_tables, matched_keys, where):
        """ANSWER legs must implement every applicable question scope key
        (at least one registered mapping per key)."""
        if self.cx.dec != "ANSWER":
            return
        req = self._required_scope_keys(leg_tables)
        missing = sorted(k for k in req if k not in matched_keys)
        if missing:
            raise _Reject("V6P_PREDICATE",
                          "%s does not implement the question's declared "
                          "scope key(s) %s (registered via "
                          "gov_semantic_node.scope_keys on this leg's "
                          "closure)" % (where, missing))

    # ---------------- aggregate vs measure ----------------

    def _expected_arg(self, arg_spec, role_tbl, leg_tables):
        """Registered aggregate-argument spec -> (table, col). A dotted spec
        whose prefix names a registered leg table is table-qualified;
        otherwise the whole spec is a column of the role table."""
        s = str(arg_spec)
        if "." in s:
            pre, post = s.split(".", 1)
            if pre.strip('"').lower() in leg_tables:
                return (pre.strip('"').lower(), post.strip('"').lower())
        return (role_tbl, s.strip('"').lower())

    def _check_aggregate(self, agg, mrow, lf, role_tbl, role_alias, leg_tables):
        """select-list aggregate vs the single registered measure row."""
        kind, arg = _measure_split(mrow.get("measure"))
        if kind is None:
            raise _Reject("V6P_MEASURE",
                          "registered measure %r has no implementable form"
                          % mrow.get("measure"))
        if not isinstance(agg, dict) or agg.get("class") != "FUNCTION":
            raise _Reject("V6P_MEASURE",
                          "leg output is not an aggregate function")
        fn = (agg.get("function_name") or "").lower()
        if agg.get("filter"):
            raise _Reject("V6P_MEASURE", "FILTER clause is not a registered form")
        distinct = bool(agg.get("distinct"))
        ch = agg.get("children") or []
        if kind == "count":
            if fn != "count_star" or distinct or ch:
                raise _Reject("V6P_MEASURE",
                              "leg must implement registered measure count as "
                              "COUNT(*); got %s%s" %
                              (fn, "(DISTINCT …)" if distinct else ""))
            return
        if kind == "count_distinct":
            if fn != "count" or not distinct or len(ch) != 1:
                raise _Reject("V6P_MEASURE",
                              "leg must implement count_distinct:%s as "
                              "COUNT(DISTINCT %s)" % (arg, arg))
            a, t, c = self._resolve_col(lf, _colref(ch[0]))
            et, ec = self._expected_arg(arg, role_tbl, leg_tables)
            if (t, c) != (et, ec) or (t == role_tbl and a != role_alias):
                raise _Reject("V6P_MEASURE",
                              "COUNT(DISTINCT %s.%s) does not implement the "
                              "registered key %s.%s" % (t, c, et, ec))
            return
        if kind in ("sum", "avg"):
            if fn != kind or distinct or len(ch) != 1:
                raise _Reject("V6P_MEASURE",
                              "leg must implement %s:%s as %s(%s)"
                              % (kind, arg, kind.upper(), arg))
            ref = _colref(ch[0])
            if ref is None:
                raise _Reject("V6P_MEASURE",
                              "%s over a non-column expression is not the "
                              "registered form" % kind.upper())
            a, t, c = self._resolve_col(lf, ref)
            et, ec = self._expected_arg(arg, role_tbl, leg_tables)
            if (t, c) != (et.lower(), ec.lower()) or \
                    (t == role_tbl and a != role_alias):
                raise _Reject("V6P_MEASURE",
                              "%s(%s.%s) does not implement the registered "
                              "argument %s.%s" % (kind.upper(), t, c, et, ec))
            return
        raise _Reject("V6P_MEASURE",
                      "measure kind %r is not scalar-implementable here" % kind)

    def _single_measure(self, metric, leg):
        rows = self._measures(metric, leg)
        if not rows:
            raise _Reject("V6P_MEASURE",
                          "no registered gov_measure_def row for (%s, %s) at "
                          "the pinned version" % (metric, leg))
        if len(rows) > 1:
            raise _Reject("V6P_MEASURE",
                          "leg (%s, %s) registers %d measure rows (a weighted "
                          "family); no single aggregate implements it — "
                          "fail-closed" % (metric, leg, len(rows)))
        r = rows[0]
        w = r.get("weight")
        if w is not None and not _num_eq(w, 1):
            raise _Reject("V6P_MEASURE",
                          "leg (%s, %s) registers weight %r; no single "
                          "aggregate implements it — fail-closed"
                          % (metric, leg, w))
        return r

    # ---------------- one leg ----------------

    def _check_leg(self, node, metric, leg, alpha_ent, extra_metrics=()):
        """Validate one leg SELECT node against its registered role facts."""
        # A leg carries a real FROM and its own predicate WHERE (walked below):
        # allow_outer_where=True keeps that read as before.
        self._plain_node(node, allow_from=True, allow_outer_where=True)
        sel = node.get("select_list") or []
        if len(sel) != 1:
            raise _Reject("V6P_SHAPE",
                          "leg select-list arity %d != 1" % len(sel))
        mrow = self._single_measure(metric, leg)
        role_tbl = self._node_table(mrow.get("node_id"))
        if not role_tbl:
            raise _Reject("V6P_LEG_ROLE",
                          "registered node %r has no physical table"
                          % mrow.get("node_id"))
        metrics = (metric,) + tuple(extra_metrics)
        anchor_row = self._anchor_row((alpha_ent or {}).get("anchor"))
        anchor_tbl = str((anchor_row or {}).get("semantic_object") or "")\
            .strip('"').lower() or None
        leg_tables = self._leg_tables(metrics,
                                      extra_nodes=(anchor_tbl,) if anchor_tbl
                                      else ())
        lf = _from_tree(node.get("from_table"), LegFrom())
        if lf.bad:
            raise _Reject("V6P_SHAPE", lf.bad)
        if not lf.tables:
            raise _Reject("V6P_SHAPE", "leg reads no relation")
        for t in lf.tables:
            if t not in leg_tables:
                raise _Reject("V6P_TABLE",
                              "leg reads %r outside its registered closure" % t)
        hop_pairs = self._hop_pairs(metrics)
        role_alias = self._role_alias(lf, role_tbl, hop_pairs)
        self._check_joins(lf, hop_pairs)
        self._check_aggregate(sel[0], mrow, lf, role_tbl, role_alias,
                              leg_tables)
        # predicates
        conjs = _flatten_and(node.get("where_clause"), [])
        atoms = []
        in_effect = {}
        matched_keys = set()
        preds = list(mrow.get("preds") or [])
        matched = [False] * len(preds)
        for conj in conjs:
            ie = self._in_effect_part(conj, lf)
            if ie is not None:
                in_effect[ie[0]] = ie[1]
                continue
            ta = self._time_atom(conj, lf)
            if ta is not None:
                atoms.append(ta)
                continue
            hit = None
            for i, p in enumerate(preds):
                if not matched[i] and \
                        self._match_measure_pred(conj, lf, p, role_tbl,
                                                 role_alias):
                    hit = i
                    break
            if hit is not None:
                matched[hit] = True
                continue
            skey = self._scope_conjunct_ok(conj, lf)
            if skey is not None:
                matched_keys.add(skey)
                continue
            raise _Reject("V6P_PREDICATE",
                          "predicate of type %r is neither a registered "
                          "measure predicate, a registered question-scope "
                          "predicate, nor the anchor time form"
                          % (conj or {}).get("type"))
        missing = [p for i, p in enumerate(preds) if not matched[i]]
        if missing:
            raise _Reject("V6P_PREDICATE",
                          "registered predicate(s) missing from the leg: %s"
                          % json.dumps(missing, ensure_ascii=False,
                                       sort_keys=True))
        self._check_scope_complete(leg_tables, matched_keys,
                                   "leg (%s, %s)" % (metric, leg))
        self._check_window(lf, atoms, alpha_ent, anchor_row, role_tbl,
                           hop_pairs, in_effect, role_alias=role_alias)
        return lf

    # ---------------- node shape ----------------

    def _plain_node(self, node, allow_from, allow_order=False,
                    allow_group1=False, allow_outer_where=False):
        if not isinstance(node, dict) or node.get("type") != "SELECT_NODE":
            raise _Reject("V6P_SHAPE",
                          "not a plain SELECT node (%r)"
                          % (node or {}).get("type"))
        cte = ((node.get("cte_map") or {}).get("map")) or []
        if cte:
            raise _Reject("V6P_SHAPE", "CTEs are outside the template class")
        for m in node.get("modifiers") or []:
            mt = (m or {}).get("type")
            if mt == "ORDER_MODIFIER" and allow_order:
                continue
            raise _Reject("V6P_SHAPE",
                          "modifier %r is outside the template class" % mt)
        if node.get("having") or node.get("qualify"):
            raise _Reject("V6P_SHAPE", "HAVING/QUALIFY outside the template")
        if (node.get("sample") or None) is not None:
            raise _Reject("V6P_SHAPE", "SAMPLE outside the template")
        if node.get("aggregate_handling") not in (None, "STANDARD_HANDLING"):
            raise _Reject("V6P_SHAPE",
                          "aggregate handling %r outside the template"
                          % node.get("aggregate_handling"))
        groups = node.get("group_expressions") or []
        if groups and not allow_group1:
            raise _Reject("V6P_SHAPE", "GROUP BY outside the template")
        if allow_group1:
            if len(groups) != 1 or _const_value(groups[0]) != 1:
                raise _Reject("V6P_SHAPE",
                              "report template requires exactly GROUP BY 1")
        if not allow_from and (node.get("from_table") or {}).get("type") != "EMPTY":
            raise _Reject("V6P_SHAPE",
                          "scalar template requires an empty outer FROM")
        # Outer-filter closure (PREREG_poststudy4_20260827, fix 1): a non-null
        # outer WHERE on a template node is outside the class and is rejected by
        # DEFAULT. The scalar OUTER nodes of atomic/ratio/delta carry no WHERE
        # (they route through here with allow_outer_where=False); the FROM-
        # carrying leg / report / attribute predicate walkers pass
        # allow_outer_where=True and read their own where_clause as before.
        if not allow_outer_where and node.get("where_clause") is not None:
            raise _Reject("V6P_SHAPE", "outer WHERE outside the template")

    # ---------------- scalar wrappers ----------------

    def _scalar_subquery_node(self, e):
        if not (isinstance(e, dict) and e.get("class") == "SUBQUERY" and
                e.get("subquery_type") == "SCALAR"):
            raise _Reject("V6P_SHAPE",
                          "expected a scalar-subquery leg, got %r"
                          % (e or {}).get("class"))
        sub = ((e.get("subquery") or {}).get("node"))
        if not isinstance(sub, dict):
            raise _Reject("V6P_SHAPE", "scalar subquery without a SELECT node")
        return sub

    def _num_side(self, e):
        """`SUBQ * 1.0` or bare SUBQ -> subquery node."""
        if _fn(e) == "*":
            ch = e.get("children") or []
            if len(ch) == 2 and _is_const(ch[1], 1.0):
                return self._scalar_subquery_node(ch[0])
            if len(ch) == 2 and _is_const(ch[0], 1.0):
                return self._scalar_subquery_node(ch[1])
            raise _Reject("V6P_SHAPE",
                          "numerator combiner is not `leg * 1.0`")
        return self._scalar_subquery_node(e)

    def _den_side(self, e):
        """`NULLIF(SUBQ, 0)` or bare SUBQ -> subquery node."""
        if _fn(e) == "nullif":
            ch = e.get("children") or []
            if len(ch) == 2 and _is_const(ch[1], 0):
                return self._scalar_subquery_node(ch[0])
            raise _Reject("V6P_SHAPE",
                          "denominator guard is not `NULLIF(leg, 0)`")
        return self._scalar_subquery_node(e)

    # ---------------- report val: ratio_of_base ----------------

    def _agg_side(self, e):
        """`AGG * 1.0` / `NULLIF(AGG, 0)` / bare AGG -> aggregate node."""
        if _fn(e) == "*":
            ch = e.get("children") or []
            if len(ch) == 2 and _is_const(ch[1], 1.0):
                return self._agg_side(ch[0])
            if len(ch) == 2 and _is_const(ch[0], 1.0):
                return self._agg_side(ch[1])
            raise _Reject("V6P_SHAPE", "val combiner is not `agg * 1.0`")
        if _fn(e) == "nullif":
            ch = e.get("children") or []
            if len(ch) == 2 and _is_const(ch[1], 0):
                return ch[0]
            raise _Reject("V6P_SHAPE", "val guard is not `NULLIF(agg, 0)`")
        return e

    # ---------------- kinds ----------------

    def check(self):
        cx, H = self.cx, self.H
        sql = cx.sql
        rel = cx.con.execute("SELECT json_serialize_sql(?::VARCHAR)",
                             [sql]).fetchone()[0]
        doc = json.loads(rel)
        if doc.get("error"):
            raise _Reject("V6P_PARSE",
                          "DuckDB cannot parse the answer SQL (%s: %s)"
                          % (doc.get("error_type"),
                             str(doc.get("error_message"))[:120]))
        stmts = doc.get("statements") or []
        if len(stmts) != 1:
            raise _Reject("V6P_PARSE",
                          "%d statements; the template is one SELECT"
                          % len(stmts))
        node = (stmts[0] or {}).get("node")
        mrow = self.gv.metric_row(self.metric)
        if not mrow:
            raise _Reject("V6P_KIND",
                          "metric %r has no gov_metric row at the pinned "
                          "version" % self.metric)
        kind = mrow.get("kind")
        if kind == "atomic":
            self._check_atomic(node, self.metric)
        elif kind == "ratio":
            self._check_ratio(node, self.metric)
        elif kind == "delta":
            self._check_delta(node, mrow)
        elif kind == "report":
            self._check_report(node, mrow)
        elif kind == "attribute":
            self._check_attribute(node, self.metric)
        else:
            raise _Reject("V6P_KIND",
                          "metric kind %r admits no registered SQL answer "
                          "template (fail-closed)" % kind)
        return ("PASS",
                "AST lies in the registered %s template: measures, leg-role "
                "binding, registered predicates, window equality and routing "
                "joins all replayed from G_v" % kind)

    def _alpha(self, key):
        ent = self.cx.alpha.get(key)
        if key == "atom" and ent is None:
            ent = self.cx.alpha.get("atomic")
        return ent

    def _check_atomic(self, node, metric, leg="atom", alpha_key="atom"):
        # Fix 1: the outer WHERE rejection now lives in _plain_node's default
        # (allow_outer_where=False), so atomic/ratio/delta share one closure.
        self._plain_node(node, allow_from=False)
        sel = node.get("select_list") or []
        if len(sel) != 1:
            raise _Reject("V6P_SHAPE",
                          "scalar template requires one output column, got %d"
                          % len(sel))
        sub = self._scalar_subquery_node(sel[0])
        self._check_leg(sub, metric, leg, self._alpha(alpha_key))

    def _check_ratio(self, node, metric):
        self._plain_node(node, allow_from=False)
        sel = node.get("select_list") or []
        if len(sel) != 1:
            raise _Reject("V6P_SHAPE",
                          "scalar template requires one output column, got %d"
                          % len(sel))
        top = sel[0]
        if _fn(top) != "/":
            raise _Reject("V6P_SHAPE",
                          "ratio template requires `num / den` at the top")
        ch = top.get("children") or []
        if len(ch) != 2:
            raise _Reject("V6P_SHAPE", "ratio division arity != 2")
        num_node = self._num_side(ch[0])
        den_node = self._den_side(ch[1])
        self._check_leg(num_node, metric, "num", self._alpha("numerator"))
        self._check_leg(den_node, metric, "den", self._alpha("denominator"))

    def _check_delta(self, node, mrow):
        base = mrow.get("base_metric_id")
        if not base:
            raise _Reject("V6P_KIND",
                          "delta metric registers no base_metric_id")
        self._plain_node(node, allow_from=False)
        sel = node.get("select_list") or []
        if len(sel) != 1:
            raise _Reject("V6P_SHAPE", "delta template outputs one column")
        top = sel[0]
        if _fn(top) != "-":
            raise _Reject("V6P_SHAPE",
                          "delta template requires `leg - leg` at the top")
        ch = top.get("children") or []
        if len(ch) != 2:
            raise _Reject("V6P_SHAPE", "delta subtraction arity != 2")
        ents = [(k, v) for k, v in sorted(self.cx.alpha.items())
                if k == "atom" or k.startswith("atom#")]
        wins = [(k, v) for k, v in ents if v.get("window")]
        if len(wins) != 2:
            raise _Reject("V6P_LEG_ROLE",
                          "delta certificate must certify exactly 2 atom "
                          "period windows, found %d" % len(wins))
        H = self.H

        def _lo(went):
            w = went[1]["window"]
            return (w[0][0] is not None, w[0][0])
        wins.sort(key=_lo)
        earlier, later = wins[0][1], wins[1][1]
        if H["w_eq"](earlier.get("window"), later.get("window")):
            raise _Reject("V6P_LEG_ROLE",
                          "delta periods certify identical windows")
        minuend = self._scalar_subquery_node(ch[0])
        subtrahend = self._scalar_subquery_node(ch[1])
        # registered orientation: Δ = value(later period) − value(earlier)
        self._check_leg(minuend, base, "atom", later,
                        extra_metrics=(self.metric,))
        self._check_leg(subtrahend, base, "atom", earlier,
                        extra_metrics=(self.metric,))

    def _check_report(self, node, mrow):
        # scalar-atom spelling (time-axis reports rewritten to one cell)
        sel = (node.get("select_list") or []) if isinstance(node, dict) else []
        if len(sel) == 1 and isinstance(node, dict) and \
                ((node.get("from_table") or {}).get("type") == "EMPTY"):
            self._check_atomic(node, self.metric)
            return
        # (cell, val) spelling — a FROM-carrying node whose WHERE is the
        # report predicate walker's (read below): allow_outer_where=True.
        self._plain_node(node, allow_from=True, allow_order=True,
                         allow_group1=True, allow_outer_where=True)
        if len(sel) != 2:
            raise _Reject("V6P_SHAPE",
                          "report template outputs (cell, val), got %d columns"
                          % len(sel))
        aliases = [(e or {}).get("alias") or "" for e in sel]
        if aliases != ["cell", "val"]:
            raise _Reject("V6P_SHAPE",
                          "report output aliases %s != ['cell', 'val']"
                          % aliases)
        cell, val = sel[0], sel[1]
        if _has_agg_or_subquery(cell):
            raise _Reject("V6P_SHAPE",
                          "report cell expression must be aggregate- and "
                          "subquery-free")
        mrow_leg = self._single_measure(self.metric, "atom")
        kindm, _arg = _measure_split(mrow_leg.get("measure"))
        metrics = (self.metric,)
        if mrow.get("base_metric_id"):
            metrics = metrics + (mrow["base_metric_id"],)
        role_tbl = self._node_table(mrow_leg.get("node_id"))
        anchor_row = self._anchor_row((self._alpha("atom") or {}).get("anchor"))
        anchor_tbl = str((anchor_row or {}).get("semantic_object") or "")\
            .strip('"').lower() or None
        leg_tables = self._leg_tables(metrics,
                                      extra_nodes=(anchor_tbl,) if anchor_tbl
                                      else ())
        lf = _from_tree(node.get("from_table"), LegFrom())
        if lf.bad:
            raise _Reject("V6P_SHAPE", lf.bad)
        for t in lf.tables:
            if t not in leg_tables:
                raise _Reject("V6P_TABLE",
                              "report reads %r outside its registered closure"
                              % t)
        hop_pairs = self._hop_pairs(metrics)
        role_alias = self._role_alias(lf, role_tbl, hop_pairs)
        self._check_joins(lf, hop_pairs)
        # cell columns must resolve inside the leg's FROM
        for ref in _colrefs_in(cell):
            self._resolve_col(lf, ref)
        # val: atom measure or ratio_of_base over the base metric's legs
        if kindm == "ratio_of_base":
            base = mrow.get("base_metric_id")
            if not base:
                raise _Reject("V6P_KIND",
                              "ratio_of_base without base_metric_id")
            if _fn(val) != "/":
                raise _Reject("V6P_SHAPE",
                              "ratio_of_base val must be `num / den`")
            ch = val.get("children") or []
            if len(ch) != 2:
                raise _Reject("V6P_SHAPE", "val division arity != 2")
            bn = self._single_measure(base, "num")
            bd = self._single_measure(base, "den")
            self._check_aggregate(self._agg_side(ch[0]), bn, lf,
                                  self._node_table(bn.get("node_id")),
                                  role_alias, leg_tables)
            self._check_aggregate(self._agg_side(ch[1]), bd, lf,
                                  self._node_table(bd.get("node_id")),
                                  role_alias, leg_tables)
        else:
            self._check_aggregate(val, mrow_leg, lf, role_tbl, role_alias,
                                  leg_tables)
        # predicates + window on the report node itself
        conjs = _flatten_and(node.get("where_clause"), [])
        atoms = []
        in_effect = {}
        matched_keys = set()
        preds = list(mrow_leg.get("preds") or [])
        matched = [False] * len(preds)
        for conj in conjs:
            ie = self._in_effect_part(conj, lf)
            if ie is not None:
                in_effect[ie[0]] = ie[1]
                continue
            ta = self._time_atom(conj, lf)
            if ta is not None:
                atoms.append(ta)
                continue
            hit = None
            for i, p in enumerate(preds):
                if not matched[i] and self._match_measure_pred(
                        conj, lf, p, role_tbl, role_alias):
                    hit = i
                    break
            if hit is not None:
                matched[hit] = True
                continue
            skey = self._scope_conjunct_ok(conj, lf)
            if skey is not None:
                matched_keys.add(skey)
                continue
            raise _Reject("V6P_PREDICATE",
                          "report predicate of type %r is neither registered "
                          "nor question-scope-justified"
                          % (conj or {}).get("type"))
        missing = [p for i, p in enumerate(preds) if not matched[i]]
        if missing:
            raise _Reject("V6P_PREDICATE",
                          "registered predicate(s) missing from the report: %s"
                          % json.dumps(missing, ensure_ascii=False,
                                       sort_keys=True))
        self._check_scope_complete(leg_tables, matched_keys, "report")
        self._check_window(lf, atoms, self._alpha("atom"), anchor_row,
                           role_tbl, hop_pairs, in_effect,
                           role_alias=role_alias)

    def _check_attribute(self, node, metric):
        # A FROM-carrying node whose WHERE is the attribute predicate walker's
        # (read below): allow_outer_where=True.
        self._plain_node(node, allow_from=True, allow_outer_where=True)
        sel = node.get("select_list") or []
        if len(sel) != 1:
            raise _Reject("V6P_SHAPE",
                          "attribute template outputs one column, got %d"
                          % len(sel))
        expr = sel[0]
        if _has_agg_or_subquery(expr):
            raise _Reject("V6P_SHAPE",
                          "attribute projection must be aggregate- and "
                          "subquery-free")
        mrow = self._single_measure(metric, "atom")
        kindm, arg = _measure_split(mrow.get("measure"))
        if kindm != "value":
            raise _Reject("V6P_MEASURE",
                          "attribute metric registers %r, not a value:<col> "
                          "measure" % mrow.get("measure"))
        role_tbl = self._node_table(mrow.get("node_id"))
        leg_tables = self._leg_tables((metric,))
        lf = _from_tree(node.get("from_table"), LegFrom())
        if lf.bad:
            raise _Reject("V6P_SHAPE", lf.bad)
        for t in lf.tables:
            if t not in leg_tables:
                raise _Reject("V6P_TABLE",
                              "attribute reads %r outside its registered "
                              "closure" % t)
        hop_pairs = self._hop_pairs((metric,))
        role_alias = self._role_alias(lf, role_tbl, hop_pairs)
        self._check_joins(lf, hop_pairs)
        refs = _colrefs_in(expr)
        if not refs:
            raise _Reject("V6P_SHAPE",
                          "attribute projection is constant-only")
        et, ec = self._expected_arg(arg, role_tbl, leg_tables)
        for ref in refs:
            a, t, c = self._resolve_col(lf, ref)
            if (t, c) != (et, ec) or (t == role_tbl and a != role_alias):
                raise _Reject("V6P_MEASURE",
                              "attribute projection reads %s.%s; the "
                              "registered value column is %s.%s"
                              % (t, c, et, ec))
        # predicates: every conjunct must be scope-justified or registered;
        # at least one equality on the node's registered entity/scope key.
        conjs = _flatten_and(node.get("where_clause"), [])
        preds = list(mrow.get("preds") or [])
        matched = [False] * len(preds)
        matched_keys = set()
        keyed = False
        for conj in conjs:
            if self._time_atom(conj, lf) is not None or \
                    self._in_effect_part(conj, lf) is not None:
                raise _Reject("V6P_WINDOW",
                              "time predicate on an atemporal attribute")
            hit = None
            for i, p in enumerate(preds):
                if not matched[i] and self._match_measure_pred(
                        conj, lf, p, role_tbl, role_alias):
                    hit = i
                    break
            if hit is not None:
                matched[hit] = True
                continue
            skey = self._scope_conjunct_ok(conj, lf)
            if skey is not None:
                matched_keys.add(skey)
                keyed = True
                continue
            raise _Reject("V6P_PREDICATE",
                          "attribute predicate of type %r is neither "
                          "registered nor question-scope-justified"
                          % (conj or {}).get("type"))
        missing = [p for i, p in enumerate(preds) if not matched[i]]
        if missing:
            raise _Reject("V6P_PREDICATE",
                          "registered predicate(s) missing: %s"
                          % json.dumps(missing, ensure_ascii=False,
                                       sort_keys=True))
        if not keyed:
            raise _Reject("V6P_PREDICATE",
                          "attribute template requires the question's own "
                          "entity/scope key equality; none found")
        self._check_scope_complete(leg_tables, matched_keys, "attribute")
        ent = self._alpha("atom") or {}
        if ent.get("window") is not None:
            raise _Reject("V6P_WINDOW",
                          "attribute certificate certifies a window the "
                          "template cannot bind")


def check_v6a_plus(cx, helpers):
    """Entry point called by chk.check_V6a_plus. Returns (status, detail)."""
    if cx.dec not in ("ANSWER", "REWRITE"):
        return ("SKIP", "V6a+ applies to answer certificates only")
    if not getattr(cx.gv, "is_p2", False):
        return ("SKIP", "V6a+ validates against the pilot2 governance seed "
                        "schema (gov_metric absent in this graph)")
    s = cx.sql
    if not isinstance(s, str) or not s.strip():
        return ("FAIL", "V6P_PARSE: answer certificate without query text")
    try:
        return V6aPlus(cx, helpers).check()
    except _Reject as r:
        return ("FAIL", "%s: %s" % (r.code, r.msg))
    except Exception as e:  # noqa: BLE001 — fail-closed on any surprise
        return ("FAIL", "V6P_PARSE: structural validation crashed "
                        "(fail-closed): %s: %s" % (type(e).__name__, e))


# ---------------- execution-shape check (V6a+x; fix 2) ----------------

def _arity_ok(kind, ncols, nrows_cap):
    """Does an executed answer of `ncols` columns and `nrows_cap` rows
    (nrows_cap is min(actual_rows, 2): 0=empty, 1=exactly one, 2=two-or-more)
    have the certified arity for `kind`?  Scalar (atomic/ratio/delta) and
    attribute answers are exactly 1 row x 1 column; a report answer is the
    (cell,val) group-by-1 shape (>=1 row x 2 columns) or the scalar-atom
    spelling (1 row x 1 column).  Any other kind fails closed."""
    if kind in ("atomic", "ratio", "delta", "attribute"):
        return nrows_cap == 1 and ncols == 1
    if kind == "report":
        return (ncols == 2 and nrows_cap >= 1) or (ncols == 1 and nrows_cap == 1)
    return False


def _arity_want(kind):
    if kind in ("atomic", "ratio", "delta", "attribute"):
        return "exactly 1 row x 1 column"
    if kind == "report":
        return ("the (cell,val) report arity: >=1 row x 2 columns, or the 1 "
                "row x 1 column scalar-atom spelling")
    return "a metric kind with a registered executable answer template"


def check_exec_shape(cx, helpers):
    """Execution-shape check — check id `V6a+x` (PREREG_poststudy4_20260827
    fix 2).  This is the FIRST V6a+-family site to EXECUTE the answer SQL: it
    runs each ANSWER/REWRITE certificate's answer query read-only against the
    warehouse (`cx.con` — the same read-only DuckDB connection the V6b/V6c
    probes use; no new connection, no writes) and requires the executed result
    to carry the certified row/column arity, else REJECTs with the machine-
    readable code `V6P_ARITY`.  Appended LAST in the check order so every
    pre-existing first-FAIL attribution stays frozen; REFUSE certificates carry
    no answer SQL and are SKIPped exactly as V6a+ SKIPs them.  Returns
    (status, detail)."""
    if cx.dec not in ("ANSWER", "REWRITE"):
        return ("SKIP", "execution-shape check applies to answer certificates "
                        "only (REFUSE carries no answer SQL)")
    if not getattr(cx.gv, "is_p2", False):
        return ("SKIP", "execution-shape check validates the pilot2 governance "
                        "seed schema (gov_metric absent in this graph)")
    s = cx.sql
    if not isinstance(s, str) or not s.strip():
        return ("FAIL", "V6P_ARITY: answer certificate without query text")
    try:
        metric = helpers["base_metric"](cx.q.get("metric"))
        kind = (cx.gv.metric_row(metric) or {}).get("kind")
    except Exception as e:  # noqa: BLE001 — fail-closed
        return ("FAIL", "V6P_ARITY: metric kind unresolvable for the arity "
                        "contract (fail-closed): %s: %s" % (type(e).__name__, e))
    try:
        res = cx.con.execute(s)
        ncols = len(res.description) if res.description else 0
        head = res.fetchmany(2)          # cap: enough to tell 0 / 1 / >=2 rows
        nrows_cap = len(head)
    except Exception as e:  # noqa: BLE001 — an unexecutable answer is fail-closed
        return ("FAIL", "V6P_ARITY: answer SQL did not execute read-only "
                        "(fail-closed): %s: %s"
                        % (type(e).__name__, str(e)[:140]))
    if not _arity_ok(kind, ncols, nrows_cap):
        rowtxt = ">=2" if nrows_cap == 2 else str(nrows_cap)
        return ("FAIL", "V6P_ARITY: executed answer shape %s row(s) x %d "
                        "column(s) is not the certified arity for a %r metric "
                        "(expected %s)"
                        % (rowtxt, ncols, kind, _arity_want(kind)))
    rowtxt = ">=2" if nrows_cap == 2 else str(nrows_cap)
    return ("PASS", "executed answer shape %s row(s) x %d column(s) matches the "
                    "certified %r arity" % (rowtxt, ncols, kind))
