#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chk.py — independent point-in-time certificate verifier (C5 Definition 5.6, V0–V6c).

Spec (frozen, read-only):
  /Volumes/SSD 1/explore_opportunity_cc/theory/C5_pointintime_certificates.md  (Def 5.1–5.7, Thm 5.9/5.10)
  /Volumes/SSD 1/explore_opportunity_cc/theory/C3_bitemporal_semantics.md      (Def 3.1–3.16, guard order D2)
  /Volumes/SSD 1/explore_opportunity_cc/theory/C4_maximal_legal_rewrite.md     (dec=REWRITE mapping, CT slice-major)

Input signature is strictly (certificate, q, G_v, D):
  - certificate : the JSON artifact (C5 §6.2 envelope or bare certificate object);
  - q           : the structured question (questions.json row, possibly with the
                  structured-intent extensions of C3 Def 3.6: num_window/den_window/
                  delta_windows/windows/params/sku/binding_id/anchor_override);
  - G_v         : resolved from certificate.graph_pin against the gov_* tables in the
                  warehouse (the same duckdb file also carries D);
  - D           : the warehouse fact tables (read-only duckdb connection).

Verdict: ACCEPT iff every check in {V0,V1,V2,V3,V4,V5,V6a,V6b,V6c} passes.
Reporting: every check is attempted; `rejected_by` is the first FAIL in canonical order.

Anti-certification-loop red lines (C5 Req 5.8, 梁老师意见3):
  * zero imports from any compiler module (impl/asof_compiler/**, pilot/domains/*/compiler.py);
  * window arithmetic, date handling, coverage computation, guard predicates and the
    symmetric-difference audit are all implemented here from the spec text alone;
  * certificate fields are treated as *claims*: every governance fact is re-queried from
    (G_v, D); probes are re-executed against D, never trusted from the transcript.

Window provenance (independence boundary, see impl/INDEPENDENCE_REPORT.md):
  the role window ω_r is derived FIRST from the domain's as-of convention over
  (G_v, D, q's non-window fields: domain/metric/as_of/params).  The window
  coordinate presented by the question (q['windows'], and rma's legacy
  num_window/den_window/delta_windows) is a *declared* input: it is consulted
  only when the convention cannot fix ω_r, or when it contradicts the
  convention (a rigid window commitment, C4 Def 4.6), and either case is
  reported per role as window_source ∈ {declared, declared-override} instead of
  being silently absorbed.  `--no-declared-windows` refuses the fallback
  outright, so the ACCEPT count under that flag is the honest measure of how
  much of the corpus the verifier can certify without reading any
  question-supplied window coordinate.

Only python3 stdlib + duckdb are used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys

import duckdb

DAY = dt.timedelta(days=1)

CHECK_ORDER = ["V0", "V1", "V2", "V3", "V4", "V5", "V6a", "V6b", "V6c"]
GUARD_ORDER = ["OOV", "AM", "MC"]  # frozen report order (D2 / C3 note 3.18')

REASONS = {"missing-caliber": "MC", "anchor-mismatch": "AM",
           "out-of-validity": "OOV", "disclosure-blocked": "DB"}

ADM_MODES = ("trivial_true", "symdiff_audit", "interval_containment",
             # pilot2 cross-anchor svw ratios: clause (iv) audits the two anchors'
             # WINDOW-RESTRICTED realisation day sets (hull anchor -> calendar days
             # inside its hull; strict_member anchor -> marker days), never the
             # unwindowed full sets — C3 Def 3.8(iv) evaluated on the request pair.
             "window_realization_symdiff")
# C3 Def 3.3 fixes cm_a ∈ {hull, strict_member}. The two半开 envelope modes are an
# implementation extension forced by the frozen gold (DEVIATION-1, see the
# integration report): a *right-open* envelope [min, +inf) is what makes
# EMAIL-ASOF-06 (2026-05 window past the label coverage top) an MC(ii) rather
# than an OOV, and a *left-open* envelope (-inf, max] is what makes AIBUY-Q6
# (as-of before the first recorded signal) an MC(ii) rather than an OOV — both
# classifications are pinned by C4 §4.4 标签归一注记 / G-10. Each mode is a
# per-anchor versioned attribute declared in G_v (D3/G4 `coverage_mode` column),
# never inventable by a certificate alone when G_v declares one.
COVERAGE_MODES = ("hull", "strict_member", "hull_right_open", "hull_left_open")

_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|ATTACH|DETACH|COPY|EXPORT|PRAGMA|INSTALL|LOAD|CALL|SET)\b",
    re.I)


# =========================================================================
# A. independent window arithmetic (C3 Def 3.1/3.2; W = half-open intervals
#    and finite date sets, normalised to a sorted union of half-open
#    day-granule intervals [(lo, hi), ...]; lo=None => -inf, hi=None => +inf)
# =========================================================================

def _parse_day(s):
    return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def month_first(y, m):
    return dt.date(y, m, 1)


def month_next(y, m):
    return dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)


def parse_asof(raw):
    """Classify an as-of string. Returns (kind, payload) where kind in
    {'day','month','year'} or ('unparseable', raw). Independent implementation
    (A5: unparseable is an explicit sentinel, not an exception path)."""
    s = (raw or "").strip() if isinstance(raw, str) else ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return ("day", _parse_day(s))
        except ValueError:
            return ("unparseable", raw)
    if re.fullmatch(r"\d{4}-\d{2}", s):
        y, m = int(s[:4]), int(s[5:7])
        if 1 <= m <= 12:
            return ("month", (y, m))
        return ("unparseable", raw)
    if re.fullmatch(r"\d{4}", s):
        return ("year", int(s))
    return ("unparseable", raw)


def w_norm(ivs):
    """Normalise a list of (lo, hi) half-open intervals (dates or None)."""
    ivs = [(lo, hi) for (lo, hi) in ivs
           if not (lo is not None and hi is not None and lo >= hi)]
    ivs.sort(key=lambda p: (p[0] is not None, p[0] or dt.date.min))
    out = []
    for lo, hi in ivs:
        if out:
            plo, phi = out[-1]
            if phi is None or (lo is not None and phi is not None and lo <= phi):
                nhi = None if (phi is None or hi is None) else max(phi, hi)
                out[-1] = (plo, nhi)
                continue
        out.append((lo, hi))
    return tuple(out)


def w_empty(w):
    return len(w) == 0


def w_eq(a, b):
    return w_norm(a) == w_norm(b)


def w_intersect(a, b):
    out = []
    for lo1, hi1 in a:
        for lo2, hi2 in b:
            lo = lo1 if lo2 is None else (lo2 if lo1 is None else max(lo1, lo2))
            hi = hi1 if hi2 is None else (hi2 if hi1 is None else min(hi1, hi2))
            if lo is None or hi is None or lo < hi:
                out.append((lo, hi))
    return w_norm(out)


def w_subset(a, b):
    """a ⊆ b for normalised unions of half-open intervals."""
    a, b = w_norm(a), w_norm(b)
    for lo, hi in a:
        covered = False
        for blo, bhi in b:
            lo_ok = (blo is None) or (lo is not None and blo <= lo)
            hi_ok = (bhi is None) or (hi is not None and hi <= bhi)
            if lo_ok and hi_ok:
                covered = True
                break
        if not covered:
            return False
    return True


def w_hull(w):
    """Order convex hull [min, max) of a finite union (C3 Def 3.3 hull mode)."""
    w = w_norm(w)
    if not w:
        return tuple()
    lo = w[0][0]
    hi = w[-1][1]
    return ((lo, hi),)


def w_from_dates(dates):
    return w_norm([(d, d + DAY) for d in dates])


def w_month(y, m):
    return ((month_first(y, m), month_next(y, m)),)


def w_str(w):
    if w is None:
        return "<none>"
    if w_empty(w):
        return "{}"
    return " ∪ ".join("[%s, %s)" % (lo.isoformat() if lo else "-inf",
                                    hi.isoformat() if hi else "+inf")
                      for lo, hi in w)


def parse_window_obj(obj):
    """Parse a certificate window object into the internal representation.
    Accepted forms (C5 §6.2 and natural variants):
      "YYYY-MM"                                  -> month window
      "YYYY-MM-DD"                               -> single-day point window
      {"kind":"month","lo":...,"hi_excl":...}    -> [lo, hi_excl)
      {"kind":"day"/"point","date": d}           -> {d}
      {"kind":"dateset","dates":[...]}           -> finite date set
      {"kind":"cumulative","hi_incl": d}         -> (-inf, d]
      {"lo":...,"hi_excl":...} (any kind label)  -> [lo, hi_excl)
    Returns window tuple or None if unparseable."""
    if obj is None:
        return None
    if isinstance(obj, str):
        kind, payload = parse_asof(obj)
        if kind == "month":
            return w_month(*payload)
        if kind == "day":
            return ((payload, payload + DAY),)
        if kind == "year":
            return ((dt.date(payload, 1, 1), dt.date(payload + 1, 1, 1)),)
        return None
    if not isinstance(obj, dict):
        return None
    try:
        # C5 §6.2 canonical form: {"kind":..., "intervals":[{"lo","hi_excl"},...]}
        # (an empty-window certificate carries kind="empty" and/or no intervals)
        if "intervals" in obj or obj.get("kind") == "empty":
            ivs = obj.get("intervals") or []
            if not ivs:
                return () if obj.get("kind") == "empty" else None
            parsed = []
            for iv in ivs:
                lo = _parse_day(iv["lo"]) if iv.get("lo") else None
                hi = _parse_day(iv["hi_excl"]) if iv.get("hi_excl") else None
                if lo is None and hi is None:
                    return None
                parsed.append((lo, hi))
            return w_norm(parsed)
        if "dates" in obj:
            return w_from_dates([_parse_day(x) for x in obj["dates"]])
        if "date" in obj:
            d = _parse_day(obj["date"])
            return ((d, d + DAY),)
        # pilot2 structured window spellings (question-side / gold-side objects):
        if obj.get("kind") in ("day", "member_day", "point_in_effect") and "day" in obj:
            d = _parse_day(obj["day"])
            return ((d, d + DAY),)
        if obj.get("kind") == "week" and obj.get("lo"):
            lo = _parse_day(obj["lo"])
            hi = _parse_day(obj["hi_excl"]) if obj.get("hi_excl") else lo + 7 * DAY
            return w_norm([(lo, hi)])
        if obj.get("kind") == "month_token" and obj.get("token"):
            return token_day_window(str(obj["token"]))
        if obj.get("kind") == "academic_year_token" and obj.get("token"):
            return token_day_window(str(obj["token"]))
        if obj.get("kind") == "month_token_range" and obj.get("lo") and obj.get("hi"):
            wlo = token_day_window(str(obj["lo"]))
            whi = token_day_window(str(obj["hi"]))
            if wlo is None or whi is None:
                return None
            return w_norm([(wlo[0][0], whi[-1][1])])
        if "hi_incl" in obj:
            hi = _parse_day(obj["hi_incl"]) + DAY
            lo = _parse_day(obj["lo"]) if obj.get("lo") else None
            return w_norm([(lo, hi)])
        if "lo" in obj or "hi_excl" in obj:
            lo = _parse_day(obj["lo"]) if obj.get("lo") else None
            hi = _parse_day(obj["hi_excl"]) if obj.get("hi_excl") else None
            return w_norm([(lo, hi)])
    except (ValueError, KeyError, TypeError):
        return None
    return None


def token_day_window(tok):
    """Day-space denotation of a calendar token (C3 Def 3.2 granule embedding):
      'YYYYMM' / 'YYYY-MM'      -> that month's half-open window
      'YYYY-YYYY' academic year -> [YYYY-07-01, (YYYY+1)-07-01)
    Returns a window tuple or None when the token names no known granule."""
    s = str(tok).strip()
    if re.fullmatch(r"\d{6}", s):
        y, m = int(s[:4]), int(s[4:6])
        return w_month(y, m) if 1 <= m <= 12 else None
    if re.fullmatch(r"\d{4}-\d{2}", s):
        y, m = int(s[:4]), int(s[5:7])
        return w_month(y, m) if 1 <= m <= 12 else None
    if re.fullmatch(r"\d{4}-\d{4}", s):
        y = int(s[:4])
        return ((dt.date(y, 7, 1), dt.date(y + 1, 7, 1)),)
    return None


def month_granule_aligned(w, gran):
    """Clause (iii) helper: is every maximal interval of w aligned to granule
    boundaries of `gran` in {'day','month','year'}? (C3 Def 3.2)."""
    if gran == "day" or gran is None:
        return True, None
    for lo, hi in w_norm(w):
        for edge in (lo, hi):
            if edge is None:
                continue
            if gran == "month" and edge.day != 1:
                return False, edge
            if gran == "year" and not (edge.day == 1 and edge.month == 1):
                return False, edge
    return True, None


# =========================================================================
# B. G_v accessor (governance graph at the pinned version) + D access
# =========================================================================

class Gv:
    """Read-side accessor for the governance semantic graph at version pin.
    All reads are straight duckdb queries over gov_* tables; version/domain
    filtered where those columns exist. Table absence is reported (C5 G7:
    absent-vs-empty is an open adjudication; this verifier treats an absent
    table as an absent relation and lets checks that need cited rows fail)."""

    def __init__(self, con, domain, version):
        self.con = con
        self.domain = domain
        self.version = version
        self.notes = []
        self._tables = {}
        for (sch, name) in con.execute(
                "SELECT table_schema, table_name FROM information_schema.tables").fetchall():
            self._tables.setdefault(name, []).append(sch)
        # pilot2 ten-table seed schema (gov_metric / gov_measure_def / per-leg
        # gov_temporal_binding rows, versions spelled graph_version): normalise
        # to the accessor shapes the checks consume. Detection is structural.
        self.is_p2 = "gov_metric" in self._tables

    def has_table(self, name):
        return name in self._tables

    def qualify(self, name):
        """Map a bare object name to a queryable qualified table name."""
        if name is None:
            return None
        base = name.split(".")[-1].strip('"')
        schemas = self._tables.get(base)
        if not schemas:
            return None
        sch = sorted(schemas)[0]
        if sch in ("main",):
            return base
        return '%s.%s' % (sch, base)

    def rows(self, table):
        """All rows of a gov table as dicts, filtered to (domain, version pin)
        where such columns exist. If the version column exists but no row
        carries the pinned version, falls back to the single distinct version
        present (recorded as a tolerance note; seed wart e.g. email anchors
        'v2026.06.23+asof' vs graph version 'v2026.06.23')."""
        if not self.has_table(table):
            return None
        cur = self.con.execute("SELECT * FROM main.%s" % table)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        if cols == ["placeholder"]:
            return []
        if "domain" in cols:
            rows = [r for r in rows if r.get("domain") == self.domain]
        if "graph_version" in cols:
            # p2 spelling of the version pin column; JSON-encoded list/object
            # columns are decoded here so every consumer sees one shape.
            rows = [r for r in rows if r.get("graph_version") == self.version]
            for r in rows:
                for k, v in list(r.items()):
                    if isinstance(v, str) and (v.startswith("[") or v.startswith("{")):
                        try:
                            r[k] = json.loads(v)
                        except ValueError:
                            pass
            return rows
        if "version" in cols and rows:
            pinned = [r for r in rows if r.get("version") == self.version]
            if pinned:
                rows = pinned
            else:
                versions = sorted({r.get("version") for r in rows})
                if len(versions) == 1:
                    self.notes.append(
                        "tolerance: %s rows carry version %r != pin %r (single-version seed)"
                        % (table, versions[0], self.version))
                else:
                    rows = pinned  # multiple versions, none matching: empty
        return rows

    # ---- specific relations -------------------------------------------

    def version_rows(self):
        if not self.has_table("gov_semantic_graph_version"):
            return None
        cur = self.con.execute("SELECT * FROM main.gov_semantic_graph_version")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        rows = [r for r in rows if r.get("domain") == self.domain]
        for r in rows:
            if "version" not in r and r.get("graph_version") is not None:
                r["version"] = r["graph_version"]
            # p2 commit ids are the committed_at timestamps themselves
        return rows

    def node_table(self, node_id):
        for r in (self.rows("gov_semantic_node") or []):
            if r.get("node_id") == node_id:
                return r.get("physical_table")
        return None

    def node_row(self, node_id):
        for r in (self.rows("gov_semantic_node") or []):
            if r.get("node_id") == node_id:
                return r
        return None

    def metric_row(self, metric_id):
        for r in (self.rows("gov_metric") or []):
            if r.get("metric_id") == metric_id:
                return r
        return None

    def measures(self, metric_id, leg=None):
        out = [r for r in (self.rows("gov_measure_def") or [])
               if r.get("metric_id") == metric_id and
               (leg is None or r.get("leg") == leg)]
        return sorted(out, key=lambda r: r.get("measure_id") or "")

    def gran_edges(self):
        return self.rows("gov_granularity_edge") or []

    def aliases_map(self):
        return {r.get("alias_text"): r.get("metric_id")
                for r in (self.rows("gov_metric_alias") or [])}

    def anchors(self):
        rows = self.rows("gov_valid_time_anchor")
        if rows is None or not self.is_p2:
            return rows
        out = []
        for r in rows:
            out.append({
                "anchor_id": r.get("anchor_id"),
                "semantic_object": self.node_table(r.get("node_id")),
                "node_id": r.get("node_id"),
                "anchor_type": r.get("anchor_type"),
                "coverage_mode": r.get("coverage_mode"),
                "effective_date": r.get("effective_col"),
                "granularity": r.get("granularity"),
                "valid_from_col": r.get("vf_col"),
                "valid_to_col": r.get("vtc_col"),
            })
        return out

    def anchor(self, anchor_id):
        rows = self.anchors() or []
        for r in rows:
            if r.get("anchor_id") == anchor_id:
                return r
        return self.anchor_family(anchor_id)

    def anchor_family(self, obj):
        """Object-level anchor of a *registry-shaped* seed (public pilot):
        C3 Def 3.3 makes the anchor an attribute of its semantic object o_a,
        with V_v(a) the registered valid-time markers; a registry seed spells
        those markers as one row per versioned snapshot ([valid_from, valid_to]
        + snapshot_table). The object-level anchor is then the family itself —
        V_v(a) = ⋃ registered intervals — and the per-T row is only the physical
        realisation. Returns a synthesised row, or None when `obj` does not name
        such a family (≥2 registered markers)."""
        if not isinstance(obj, str) or not obj:
            return None
        kin = [r for r in (self.anchors() or [])
               if (r.get("semantic_object") or "") == obj
               and not r.get("effective_date")
               and (r.get("valid_from") or r.get("valid_to"))]
        if len(kin) < 2:
            return None
        return {"anchor_id": obj, "semantic_object": obj,
                "anchor_type": "snapshot_registry_family",
                "coverage_mode": "strict_member",
                "family_rows": kin, "synthesised_family": True}

    def bindings(self):
        rows = self.rows("gov_temporal_binding")
        if rows is None or not self.is_p2:
            return rows
        # p2 spells β_v per leg (one row per (metric, leg)); the combined view a
        # binding cite names is "num-row-id|den-row-id" (ratio) or the atom row id.
        by_metric = {}
        for r in rows:
            by_metric.setdefault(r.get("metric_id"), {})[r.get("leg")] = r
        out = []
        for mid, legs in sorted(by_metric.items()):
            num, den, atom = legs.get("num"), legs.get("den"), legs.get("atom")
            rule = (num or den or atom or {}).get("rule_id")
            if num and den:
                bid = "%s|%s" % (num["binding_id"], den["binding_id"])
                out.append({"binding_id": bid, "metric": mid, "rule": rule,
                            "numerator_anchor": num.get("anchor_id"),
                            "denominator_anchor": den.get("anchor_id"),
                            "window_gran": {"num": num.get("window_gran"),
                                            "den": den.get("window_gran")},
                            "leg_ids": [num["binding_id"], den["binding_id"]]})
            elif atom:
                out.append({"binding_id": atom["binding_id"], "metric": mid,
                            "rule": rule, "atom_anchor": atom.get("anchor_id"),
                            "window_gran": {"atom": atom.get("window_gran")},
                            "leg_ids": [atom["binding_id"]]})
        return out

    def binding_by_id(self, binding_id):
        for r in (self.bindings() or []):
            if r.get("binding_id") == binding_id:
                return r
            if self.is_p2 and binding_id and \
                    set(str(binding_id).split("|")) == set(r.get("leg_ids") or []):
                return r
        return None

    def routings(self):
        rows = self.rows("gov_caliber_routing")
        if rows is None or not self.is_p2:
            return rows
        out = []
        for r in rows:
            out.append({
                "caliber_key": r.get("routing_id"),
                "metric": r.get("metric_id"),
                "leg": r.get("leg"),
                "hop_seq": r.get("hop_seq"),
                "src_node": r.get("src_node"),
                "dst_node": r.get("dst_node"),
                "via_table": self.node_table(r.get("dst_node")),
                "src_caliber": None,
                "dst_caliber": r.get("dst_caliber"),
                "join_keys": [list(p) for p in (r.get("join_on") or [])],
            })
        return out

    def routing(self, caliber_key):
        for r in (self.routings() or []):
            if r.get("caliber_key") == caliber_key:
                return r
        return None

    def metric_routings(self, metric_id, legs=("num", "den", "atom", "scope", "entity")):
        return [r for r in (self.routings() or [])
                if r.get("metric") == metric_id and r.get("leg") in legs]

    def policies(self):
        return self.rows("gov_disclosure_policy")

    def edges(self, types):
        rows = self.rows("gov_semantic_edge") or []
        return [r for r in rows if r.get("edge_type") in types]

    # ---- derived structures -------------------------------------------

    def inherit_closure(self, obj):
        """Forward closure of `obj` along normalize_of/aggregate_of edges
        (dws _1d/_1w families inherit the dwd anchor's valid-time column;
        C5 V6a). Names are compared on their last dotted component."""
        base = obj.split(".")[-1]
        adj = {}
        for e in self.edges({"normalize_of", "aggregate_of"}):
            s = (e.get("src") or "").split(".")[-1]
            d = (e.get("dst") or "").split(".")[-1]
            adj.setdefault(s, set()).add(d)
        seen, todo = {base}, [base]
        while todo:
            n = todo.pop()
            for m in adj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        return seen

    def metric_objects(self, metric, role_edge):
        """Objects cited as numerator_of/denominator_of for `metric`."""
        out = []
        for e in self.edges({role_edge}):
            if e.get("metric") == metric:
                out.append((e.get("src") or "").split(".")[-1])
        return out

    # ---- commit map / ver(T) (C3 Def 3.5) -----------------------------

    def commit_map(self):
        """Returns (mode, entries). mode 'timestamps': entries = [(t_i, v_i)]
        strictly increasing; mode 'trivial': single version, committed_at is a
        label (pilot seed) => ver(T) is the trivial total map (C3: 'pilot 单版本
        时 ver 平凡'); mode 'unavailable': multi-version without a parseable
        strictly-monotone commit map (fail-closed downstream)."""
        rows = self.version_rows() or []
        ents = []
        for r in rows:
            ca = r.get("committed_at")
            t = None
            if isinstance(ca, (dt.date, dt.datetime)):
                t = ca if isinstance(ca, dt.date) and not isinstance(ca, dt.datetime) else ca.date()
            elif isinstance(ca, str):
                k, payload = parse_asof(ca.strip())
                if k == "day":
                    t = payload
            ents.append((t, r.get("version")))
        if len(ents) == 1 and ents[0][0] is None:
            return ("trivial", [ents[0]])
        if all(t is not None for t, _ in ents) and ents:
            ents.sort(key=lambda p: p[0])
            if all(ents[i][0] < ents[i + 1][0] for i in range(len(ents) - 1)):
                return ("timestamps", ents)
            return ("unavailable", ents)
        if len(ents) == 1:
            return ("trivial", ents)
        return ("unavailable", ents)

    def ver_of(self, t_point):
        """ver(T): in-place version at T. Returns (version|None, mode)."""
        mode, ents = self.commit_map()
        if mode == "trivial":
            return (ents[0][1], mode)
        if mode == "timestamps":
            cur = None
            for t, v in ents:
                if t_point is not None and t_point >= t:
                    cur = v
                else:
                    break
            return (cur, mode)  # None => ver(T)↑ (T before t_1)
        return (None, mode)


# =========================================================================
# C. structured question access + independent alpha re-derivation (V0)
# =========================================================================

def base_metric(metric):
    """'stage_thread_share:订单确认' -> 'stage_thread_share';
    'price_pressure_rate@message_denominator' -> 'price_pressure_rate'."""
    if not isinstance(metric, str):
        return metric
    return re.split(r"[:@]", metric, 1)[0]


def q_params(q):
    p = q.get("params") or {}
    return p if isinstance(p, dict) else {}


def q_scope_literals(q):
    lits = []
    for key in ("sku",):
        v = q.get(key)
        if isinstance(v, str) and v:
            lits.append(v)
    for k, v in q_params(q).items():
        if k in ("numerator_anchor", "denominator_anchor", "anchor", "as_of_prev"):
            continue
        if isinstance(v, str) and v:
            lits.append(v)
    sc = q.get("scope")
    if isinstance(sc, dict):
        for v in sc.values():
            if isinstance(v, str) and v:
                lits.append(v)
    return lits


def resolve_binding_row(gv, q, cert_binding_id=None):
    """β_v(m) resolution (C3 Def 3.4/3.8: at most one positive row per metric).
    Machine-readable discrimination of negative example rows (is_negative /
    binding_role) is honoured when the seed carries such a column (C5 V3 种子
    扩列方案); otherwise: unique row wins; ambiguity is resolved only by an
    explicit structured declaration q['binding_id'] (gold questions carry it);
    else the resolution is reported as ambiguous (fail-closed at the caller)."""
    rows = gv.bindings()
    if rows is None:
        return (None, "table-absent")
    m = q.get("metric")
    bm = base_metric(m)
    cand = []
    for r in rows:
        rm = r.get("metric") or ""
        parts = [base_metric(x) for x in rm.split("|")]
        if m == rm or bm in parts:
            cand.append(r)
    neg_cols = [c for c in ("is_negative", "binding_role") if cand and c in cand[0]]
    if neg_cols:
        col = neg_cols[0]
        pos = [r for r in cand if not r.get(col) or str(r.get(col)).lower()
               in ("0", "false", "positive", "pos", "none", "")]
        if len(pos) == 1:
            return (pos[0], "column")
        cand = pos
    if len(cand) == 1:
        return (cand[0], "unique")
    if len(cand) == 0:
        return (None, "none")
    # NOTE: q['binding_id'] (questions.json) names the row the question
    # *exercises*, which for negative-example questions (QVOC-05) is the
    # negative row — it must NOT disambiguate β_v. Only an explicit
    # harness-level positive_binding_id declaration may.
    qbid = q.get("positive_binding_id")
    if qbid:
        for r in cand:
            if r.get("binding_id") == qbid:
                return (r, "declared-positive-id")
    return (None, "ambiguous:%s" % ",".join(sorted(r.get("binding_id", "?") for r in cand)))


def _anchor_metrics(arow):
    """Metrics an anchor row is registered as the prescribed anchor of (A_v's
    anchor assignment, C3 Def 3.4). Accepts a duckdb LIST, a JSON array string
    or a comma-separated string; absent column => no attribution."""
    raw = None
    for col in ("metrics", "metric"):
        if isinstance(arow, dict) and arow.get(col):
            raw = arow[col]
            break
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        return tuple(str(x) for x in raw)
    s = str(raw).strip()
    if s.startswith("["):
        try:
            v = json.loads(s)
            if isinstance(v, list):
                return tuple(str(x) for x in v)
        except ValueError:
            pass
    return tuple(p.strip() for p in s.split(",") if p.strip())


def _beta_prescribes(binding_row):
    """β_v(m)↓ ⇔ the binding row prescribes *both* legs (C3 Def 3.10(b2):
    "β_v(m) 有定义（两腿规定锚在册）"). A registry row that prescribes neither leg
    (atomic registry rows; the scoped-ratio 'no rate caliber' documentation rows)
    leaves β_v(m)↑ — for a ratio that is C3 Def 3.16(i)'s binding-missing mode
    (MC), never AM, because Def 3.15 conditions AM on β_v(m)↓."""
    if not binding_row:
        return False
    return bool(binding_row.get("numerator_anchor")) and \
        bool(binding_row.get("denominator_anchor"))


def resolve_atomic_anchor(gv, q):
    """Prescribed anchor a_m for an atomic metric: the registered anchor whose
    semantic object reaches the metric's numerator_of object along the
    inheritance closure (A_v anchor assignment, C3 Def 3.4). Explicit
    q['anchor']/params.anchor declaration wins (declared anchor)."""
    declared = q.get("anchor") or q_params(q).get("anchor")
    if declared:
        return (declared, "declared")
    anchors = gv.anchors() or []
    # A_v carries the anchor assignment for atomic metrics outright (C3 Def 3.4:
    # "A_v：锚集，并有锚指派把度量腿映到锚：原子型 m ↦ a_m"). A seed that spells
    # that assignment out (metrics/metric attribution column) is read first — it is
    # the registration itself, not a derivation from it. β_v stays the sole source
    # for ratio legs, so this never turns an atomic registry row into a ratio.
    attributed = [a.get("anchor_id") for a in anchors
                  if q.get("metric") in _anchor_metrics(a)]
    if len(attributed) == 1:
        return (attributed[0], "registered-assignment")
    if len(attributed) > 1:
        return (None, "ambiguous")
    objs = gv.metric_objects(q.get("metric"), "numerator_of")
    hits = []
    for a in anchors:
        clo = gv.inherit_closure(a.get("semantic_object") or "")
        if any(o in clo for o in objs):
            hits.append(a.get("anchor_id"))
    if len(hits) == 1:
        return (hits[0], "closure")
    if len(hits) > 1:
        return (None, "ambiguous")
    # Registry-shaped seeds (no semantic-node graph): the metric's registry row
    # names its semantic object directly, and that object may carry several
    # registered anchors whose validity intervals partition time. C3 Def 3.3/3.7:
    # the prescribed anchor at T is the registered anchor of that object whose
    # validity covers T; if none covers T there is no prescribed anchor and the
    # OOV path applies (that is the intended reading, not a heuristic).
    rows = gv.bindings() or []
    m, bm = q.get("metric"), base_metric(q.get("metric"))
    obj = None
    for r in rows:
        rm = r.get("metric") or ""
        if m == rm or bm in [base_metric(x) for x in rm.split("|")]:
            obj = r.get("semantic_object")
            break
    if not obj:
        return (None, "none")
    cands = [a for a in anchors if (a.get("semantic_object") or "") == obj]
    if len(cands) == 1:
        return (cands[0].get("anchor_id"), "registry-object")
    kind, payload = parse_asof(q.get("as_of"))
    t = None
    if kind == "day":
        t = payload
    elif kind == "month":
        t = dt.date(payload[0], payload[1], 1)
    elif kind == "year":
        t = dt.date(payload, 1, 1)
    if t is not None:
        def _as_day(x):
            # duckdb hands back datetime.date/datetime objects, seeds may carry
            # ISO strings — both are the same calendar value.
            if x is None or x == "":
                return None
            if isinstance(x, dt.datetime):
                return x.date()
            if isinstance(x, dt.date):
                return x
            return _parse_day(x)

        covering = []
        for a in cands:
            try:
                lo = _as_day(a.get("valid_from"))
                hi = _as_day(a.get("valid_to"))
            except (ValueError, TypeError):
                continue
            if (lo is None or lo <= t) and (hi is None or t <= hi):
                covering.append(a.get("anchor_id"))
        if len(covering) == 1:
            return (covering[0], "registry-validity")
        if len(covering) > 1:
            return (None, "ambiguous")
        # No registered marker realises the object at T. The metric's prescribed
        # anchor is still the object's own anchor (C3 Def 3.3: a = (o_a, …) is an
        # attribute of the object, not of one marker); what is empty at T is its
        # *coverage*, and that is exactly the OOV branch of Def 3.14 — which is
        # the frozen classification for the PUB-*-05 family (out-of-validity).
        # Reading the missing marker as "no prescribed anchor" instead would send
        # the family through the 真空约定 into MC(i), contradicting the gold.
        fam = gv.anchor_family(obj)
        if fam is not None:
            return (fam["anchor_id"], "registry-object-family")
    return (None, "none")


def declared_overrides(q):
    """Structured re-anchor declarations ā (C3 Def 3.6): returns dict
    role -> declared anchor reference (may be unregistered)."""
    out = {}
    p = q_params(q)
    if p.get("numerator_anchor"):
        out["numerator"] = p["numerator_anchor"]
    if p.get("denominator_anchor"):
        out["denominator"] = p["denominator_anchor"]
    ov = q.get("anchor_override")
    if isinstance(ov, dict):
        for role, ref in ov.items():
            if role in ("numerator", "denominator", "atom", "atomic") and isinstance(ref, str):
                out["atom" if role == "atomic" else role] = ref
    return out


# -- registered request-window rules ---------------------------------------
# A metric's registry row may register the *shape* of the as-of request window
# (C3 Def 3.2: the domain convention that maps an as-of point T to ω_r).  The
# pilot's gov_temporal_binding carries no machine-readable column for it, so the
# lookup order is: machine-readable column (if a seed ever grows one) → the
# `rule` value → a whitelisted token in the row's registered prose `note`.  The
# prose step is a *registration gap*, recorded as source 'registry-note' on
# every role it decides, not a silent convenience (see INDEPENDENCE_REPORT.md).
_WINDOW_RULE_COLS = ("window_rule", "window_kind", "request_window")
_WINDOW_RULE_VALUES = {"point": "point", "day": "point", "single_day": "point",
                       "cumulative": "cumulative", "cumulative_asof": "cumulative",
                       "asof_cumulative": "cumulative"}
_WINDOW_RULE_TOKENS = (("single-day window", "point"),
                       ("single_day_window", "point"),
                       ("单日窗", "point"),
                       ("cumulative as-of window", "cumulative"),
                       ("cumulative_asof_window", "cumulative"),
                       ("累积窗", "cumulative"))


def registry_window_rule(binding_row, default):
    """Registered request-window shape for the metric's registry row.
    Returns (rule|None, source): rule ∈ {'point','cumulative'}; source names
    where the answer came from so the caller can report it."""
    if not binding_row:
        return (default, "domain-default(no registry row)")
    for col in _WINDOW_RULE_COLS:
        v = binding_row.get(col)
        if isinstance(v, str) and v.strip():
            key = v.strip().lower()
            if key in _WINDOW_RULE_VALUES:
                return (_WINDOW_RULE_VALUES[key], "registry-column:%s" % col)
            return (None, "registry-column:%s=%r not a known window rule" % (col, v))
    hay = " ".join(str(binding_row.get(c) or "") for c in ("rule", "note")).lower()
    hits = {rule for tok, rule in _WINDOW_RULE_TOKENS if tok.lower() in hay}
    if len(hits) == 1:
        return (hits.pop(), "registry-note")
    if len(hits) > 1:
        return (None, "registry-note:ambiguous(%s)" % ",".join(sorted(hits)))
    return (default, "domain-default")


def _periods_equal(a, b):
    """Structural equality of two role→window period lists."""
    if a is None or b is None or len(a) != len(b):
        return False
    for pa, pb in zip(a, b):
        if set(pa) != set(pb):
            return False
        for k in pa:
            if not w_eq(pa[k], pb[k]):
                return False
    return True


def declared_window_periods(q, roles):
    """The window coordinate *presented by the question* (C3 Def 3.6 ω⃗ / A5).
    This is a declared input, never an independent derivation — the caller marks
    every role it decides with window_source ∈ {declared, declared-override}.
    Covers q['windows'] (a role→window map, or a list of them for the declared
    period order) and rma's legacy num_window/den_window/delta_windows spelling,
    which carry window coordinates just as literally.
    Returns (periods|None, detail)."""
    explicit = q.get("windows")
    if explicit and isinstance(explicit, (dict, list)):
        pers = explicit if isinstance(explicit, list) else [explicit]
        out = []
        parsed_all = True
        for i, src_map in enumerate(pers):
            if not isinstance(src_map, dict):
                parsed_all = False
                break
            pw = {}
            for role in roles:
                raw = src_map.get(role)
                if raw is None and role == "atom":
                    raw = src_map.get("atomic")
                if raw is None:   # p2 spelling: num/den role keys
                    raw = src_map.get({"numerator": "num", "denominator": "den"}
                                      .get(role, role))
                if raw is None:
                    raw = src_map.get("*")
                w = parse_window_obj(raw)
                if w is None:
                    parsed_all = False
                    break
                pw[role] = w
            if not parsed_all:
                break
            out.append(pw)
        if parsed_all and out:
            return (out, "q['windows']")
        # fall through: q['windows'] does not present a per-role coordinate
        # (p2 gold spells hull-trim REWRITEs as requested/effective, deltas as
        # p1/p2) — the question-side coordinate is then window_request /
        # cross_window below.

    # p2 structured spellings ------------------------------------------------
    cw = q.get("cross_window")
    if isinstance(cw, dict) and cw:
        per = {}
        ok = True
        for role in roles:
            key = {"numerator": "num", "denominator": "den"}.get(role, role)
            w = parse_window_obj(cw.get(key)) or token_day_window(cw.get(key) or "")
            if w is None:
                ok = False
                break
            per[role] = w
        if ok:
            return ([per], "q['cross_window']")
    wreq = q.get("window_request")
    if isinstance(wreq, dict) and wreq:
        w = parse_window_obj(wreq)
        if w is not None:
            return ([{r: w for r in roles}], "q['window_request']")
        return (None, "q['window_request'] unparseable: %r" % (wreq,))

    def month_win_of(s):
        k, p = parse_asof(s)
        if k == "month":
            return w_month(*p)
        if k == "day":
            return w_month(p.year, p.month)
        return None

    if isinstance(q.get("delta_windows"), list) and q["delta_windows"]:
        out = []
        for wm in q["delta_windows"]:
            w = month_win_of(wm)
            if w is None:
                return (None, "declared delta window %r unparseable" % (wm,))
            out.append({r: w for r in roles})
        return (out, "q['delta_windows']")
    if q.get("num_window") or q.get("den_window"):
        per = {}
        for role in roles:
            key = {"numerator": "num_window", "denominator": "den_window"}.get(role)
            w = month_win_of(q.get(key) if key and q.get(key) else q.get("as_of"))
            if w is None:
                return (None, "declared window for role %r unparseable" % role)
            per[role] = w
        return ([per], "q['num_window'/'den_window']")
    return (None, "question presents no window coordinate")


def _p2_anchor_hull_days(gv, arow):
    """min/max effective day of a day-granule anchor, re-queried from D."""
    tab = gv.qualify(arow.get("semantic_object"))
    col = arow.get("effective_date")
    if tab is None or not col:
        return (None, None)
    mn, mx = gv.con.execute(
        'SELECT MIN(substr(CAST("%s" AS VARCHAR),1,10)), '
        'MAX(substr(CAST("%s" AS VARCHAR),1,10)) FROM %s WHERE "%s" IS NOT NULL'
        % (col, col, tab, col)).fetchone()
    return (mn, mx)


def p2_window_periods(gv, q, roles, prescribed, overrides, binding_row):
    """pilot2 registered as-of window convention: G_v's per-leg window_gran
    (gov_temporal_binding) + the anchor's registered granularity decide ω_r from
    the NON-window fields (as_of / declared periods list). range_request rows
    register 'the window is the one the question presents' — that is a declared
    coordinate by construction and is NOT derived here (window_source honesty).
    Returns (periods|None, source, detail)."""
    metric = q.get("metric")
    mrow = gv.metric_row(metric) if metric else None
    if mrow is not None and mrow.get("kind") == "attribute":
        # atemporal attribute read: no registered leg window exists at all
        return ([{r: None for r in roles}], "domain-convention:p2-atemporal",
                "attribute metric carries no valid-time leg")
    if binding_row is None:
        return (None, None, "no registered binding row for metric %r" % (metric,))
    wg = binding_row.get("window_gran") or {}
    kind, payload = parse_asof(q.get("as_of"))

    def leg_window(role, as_of_kind, as_of_payload):
        legkey = {"numerator": "num", "denominator": "den"}.get(role, "atom")
        gran = wg.get(legkey) or wg.get("atom")
        aid = prescribed.get(role)
        arow = gv.anchor(aid) if isinstance(aid, str) else None
        agran = (arow or {}).get("granularity") or "day"
        if gran == "range_request":
            return ("declared", None)
        if binding_row.get("rule") == "point_in_effect" or gran == "day" \
                or gran == "member_day":
            if as_of_kind != "day":
                return ("err", "as_of %r is not a day coordinate" % (q.get("as_of"),))
            return ("ok", ((as_of_payload, as_of_payload + DAY),))
        if gran == "month_token":
            if as_of_kind == "day":
                return ("ok", w_month(as_of_payload.year, as_of_payload.month))
            if as_of_kind == "month":
                return ("ok", w_month(*as_of_payload))
            return ("err", "as_of %r not a month coordinate" % (q.get("as_of"),))
        if gran == "academic_year_token":
            if as_of_kind != "day":
                return ("err", "as_of %r not a day coordinate" % (q.get("as_of"),))
            y, m = as_of_payload.year, as_of_payload.month
            base = y if m >= 7 else y - 1
            return ("ok", ((dt.date(base, 7, 1), dt.date(base + 1, 7, 1)),))
        if gran == "cum_day":
            if as_of_kind != "day":
                return ("err", "as_of %r not a day coordinate" % (q.get("as_of"),))
            mn, mx = _p2_anchor_hull_days(gv, arow or {})
            if mn is None:
                return ("err", "anchor hull unavailable for the cum_day convention")
            hi = min(as_of_payload.isoformat(), mx)
            if as_of_payload.isoformat() < mn:
                return ("ok", ((as_of_payload, as_of_payload + DAY),))
            return ("ok", ((_parse_day(mn), _parse_day(hi) + DAY),))
        if gran == "month":
            if as_of_kind == "day":
                return ("ok", w_month(as_of_payload.year, as_of_payload.month))
            if as_of_kind == "month":
                return ("ok", w_month(*as_of_payload))
            return ("err", "as_of %r not a month coordinate" % (q.get("as_of"),))
        if gran == "year":
            y = (as_of_payload.year if as_of_kind == "day"
                 else as_of_payload[0] if as_of_kind == "month"
                 else as_of_payload if as_of_kind == "year" else None)
            if y is None:
                return ("err", "as_of %r has no year coordinate" % (q.get("as_of"),))
            return ("ok", ((dt.date(y, 1, 1), dt.date(y + 1, 1, 1)),))
        return ("err", "unknown registered window_gran %r" % (gran,))

    # delta questions: the declared period list is a list of as-of coordinates
    pers_decl = q.get("periods")
    if isinstance(pers_decl, list) and pers_decl and \
            (gv.metric_row(metric) or {}).get("kind") == "delta":
        out = []
        for py in pers_decl:
            pk, pp = parse_asof("%s-07-01" % py) if re.fullmatch(r"\d{4}", str(py)) \
                else parse_asof(str(py))
            per = {}
            for role in ("atom",):
                st, w = leg_window(role, pk, pp)
                if st != "ok":
                    return (None, None, "period %r underivable: %s" % (py, w))
                per[role] = w
            out.append(per)
        return (out, "domain-convention:p2-%s" % (binding_row.get("window_gran") or {}),
                "delta period list read as as-of coordinates")

    per = {}
    for role in roles:
        st, w = leg_window(role, kind, payload)
        if st == "declared":
            return (None, None, "window_gran=range_request registers the presented "
                                "window as the coordinate (declared input)")
        if st == "err":
            return (None, None, w)
        per[role] = w
    return ([per], "domain-convention:p2-window-gran", "")


def domain_window_periods(gv, q, roles, prescribed, overrides, binding_row):
    """The domain's registered as-of window convention (C3 Def 3.2), evaluated
    from (G_v, D, q's NON-window fields: domain / metric / as_of / params).
    q['windows'] (and the num_window/den_window/delta_windows spelling) is NOT
    read here — that is what makes the result independent of the coordinate the
    certificate asserts. Returns (periods|None, source, detail)."""
    domain = q.get("domain") or ""
    metric = q.get("metric")
    if gv.is_p2:
        return p2_window_periods(gv, q, roles, prescribed, overrides, binding_row)
    kind, payload = parse_asof(q.get("as_of"))

    if domain == "rma":
        # C3 Def 3.2: rma request windows are the as-of month window [m01, next m01),
        # the same window on every role (β_v's registered rule is
        # same_valid_time_window; a differing per-leg window is a *declared* rigid
        # commitment, not a convention — C4 Def 4.6).
        if kind == "month":
            w = w_month(*payload)
        elif kind == "day":
            w = w_month(payload.year, payload.month)
        else:
            return (None, None, "as_of %r is not an rma month coordinate" % (q.get("as_of"),))
        return ([{r: w for r in roles}], "domain-convention:rma-month", "")

    if domain == "domestic_newprod":
        # C3 Def 3.2 / D7: snapshot metrics take the cumulative window (-inf, d]
        # with d = as-of month end (month form) or the as-of day; SCD-2 legs take
        # the point window {d} (vf<=d<vtc semantics). The SCD-2 discrimination is
        # read off the anchor row's registered anchor_type.
        if kind == "month":
            y, m = payload
            d = month_next(y, m) - DAY
        elif kind == "day":
            d = payload
        else:
            return (None, None, "as_of %r unparseable for the domestic_newprod "
                    "cumulative convention" % (q.get("as_of"),))
        per = {}
        for role in roles:
            aid = overrides.get(role, prescribed.get(role))
            arow = gv.anchor(aid) if isinstance(aid, str) else None
            if arow and arow.get("anchor_type") == "scd_type2":
                per[role] = ((d, d + DAY),)
            else:
                per[role] = ((None, d + DAY),)
        return ([per], "domain-convention:domestic_newprod-cumulative", "")

    if domain == "quality_voc":
        if base_metric(metric) == "avg_handle_hours":
            if kind == "month":
                w = w_month(*payload)
            elif kind == "day":
                w = w_month(payload.year, payload.month)
            else:
                return (None, None, "as_of %r unparseable for the quality_voc "
                        "month convention" % (q.get("as_of"),))
            return ([{r: w for r in roles}], "domain-convention:quality_voc-month", "")
        day = payload if kind == "day" else (
            month_first(*payload) if kind == "month" else None)
        if day is None:
            return (None, None, "as_of %r underivable for the quality_voc day-set "
                    "convention" % (q.get("as_of"),))
        periods = [{r: ((day, day + DAY),) for r in roles}]
        prev = q_params(q).get("as_of_prev")   # a prior as-of *point*, not a window
        if prev:
            pk, pp = parse_asof(prev)
            pday = pp if pk == "day" else (month_first(*pp) if pk == "month" else None)
            if pday is None:
                return (None, None, "params.as_of_prev %r unparseable" % (prev,))
            periods.append({r: ((pday, pday + DAY),) for r in roles})
        return (periods, "domain-convention:quality_voc-daypoint", "")

    if domain == "email":
        # email registers its legs on event-time anchors (anchor_type
        # snapshot_effective_date + effective_date column) whose coverage_mode is a
        # half-open envelope, and its ratio rows register rule=same_valid_time_window
        # (both legs share ONE window).  The as-of envelope convention is therefore:
        #   as_of = day d      -> the point-in-time cumulative envelope (-inf, d]
        #   as_of = month/year -> that granule's half-open valid-time window
        # A binding row registering a different rule is not covered by the
        # convention and falls through to the declared coordinate (fail-open to
        # 'declared', never to a guessed window).
        if binding_row is not None and binding_row.get("rule") not in \
                (None, "", "same_valid_time_window"):
            return (None, None, "email binding rule %r is not same_valid_time_window; "
                    "the shared-window convention does not apply"
                    % (binding_row.get("rule"),))
        if kind == "day":
            w = ((None, payload + DAY),)
        elif kind == "month":
            w = w_month(*payload)
        elif kind == "year":
            w = ((dt.date(payload, 1, 1), dt.date(payload + 1, 1, 1)),)
        else:
            return (None, None, "as_of %r unparseable for the email envelope "
                    "convention" % (q.get("as_of"),))
        return ([{r: w for r in roles}], "domain-convention:email-asof-envelope", "")

    if domain == "aibuy":
        # aibuy registers atomic/ratio rows against day-granular event-time anchors
        # (snapshot_effective_date). The convention is the as-of cumulative window
        # (-inf, d]; a registry row may register a single-granule day window
        # instead, which is what registry_window_rule() looks up.
        if kind != "day":
            return (None, None, "as_of %r is not a day coordinate; aibuy's anchors "
                    "are day-granular event streams" % (q.get("as_of"),))
        rule, src = registry_window_rule(binding_row, "cumulative")
        if rule is None:
            return (None, None, "registered window rule for metric %r is not "
                    "resolvable (%s)" % (metric, src))
        w = ((payload, payload + DAY),) if rule == "point" else ((None, payload + DAY),)
        return ([{r: w for r in roles}],
                "domain-convention:aibuy-asof-%s[%s]" % (rule, src), "")

    if domain == "public" or domain.startswith("public:"):
        # The public pack registers its anchors as *interval* snapshots: one row
        # per versioned snapshot table carrying [valid_from, valid_to] and no
        # effective-date column, and gov_temporal_binding registers as-of snapshot
        # selection over those intervals.  An interval-registered snapshot anchor
        # admits exactly the point-in-time reading: the request window is the
        # as-of point {d}; which snapshot realises it is the coverage question
        # (V2/OOV), not the window question.
        anchors = gv.anchors() or []
        interval_rows = [a for a in anchors
                         if not a.get("effective_date")
                         and (a.get("valid_from") or a.get("valid_to"))]
        if not interval_rows:
            return (None, None, "no interval-registered snapshot anchor in "
                    "gov_valid_time_anchor; the as-of point convention does not apply")
        if kind != "day":
            return (None, None, "as_of %r is not a day coordinate; the public "
                    "snapshot registry is indexed by day-valued validity intervals"
                    % (q.get("as_of"),))
        w = ((payload, payload + DAY),)
        return ([{r: w for r in roles}], "domain-convention:public-asof-point", "")

    return (None, None, "no registered as-of window convention for domain %r" % (domain,))


def derive_expected_alpha(gv, q, allow_declared=True):
    """Independently re-derive the candidate anchor assignment α_{q,v}
    (C3 Def 3.7) from (q, G_v): prescribed anchors via β_v / A(G_v) lookup,
    declared overrides from the structured question, role windows via the
    domain's registered as-of convention (declared ω⃗ only as a marked
    fallback). Returns dict:
      { 'status': 'ok'|'unparseable'|'underivable', 'detail': str,
        'roles': {role_key: {'anchor': id|('REF',name)|None,
                             'declared': bool, 'window': win|None,
                             'window_source': 'derived'|'declared'|
                                              'declared-override'}},
        'ratio': bool, 'arity_source': str, 'binding_row': row|None,
        'periods': int, 'window_source': str, 'window_source_detail': str }
    Role keys: 'numerator'/'denominator'/'atom', suffixed '#<i>' for
    period-expanded (delta) questions beyond period 0.
    allow_declared=False refuses the declared fallback outright (the
    --no-declared-windows audit mode)."""
    metric = q.get("metric")
    binding_row, how = resolve_binding_row(gv, q)
    if how and how.startswith("ambiguous"):
        return {"status": "underivable",
                "detail": "β_v underdetermined for metric %r (%s); seed lacks "
                          "is_negative/binding_role column and q carries no binding_id"
                          % (metric, how), "roles": {}, "ratio": None,
                "arity_source": "ambiguous", "binding_row": None, "periods": 0,
                "window_source": None, "window_source_detail": ""}
    overrides = declared_overrides(q)

    # -- R(q): the role set is read off the *registry*, never off the presented
    # ω⃗ (reading the presented role keys would let the question — and, when the
    # question's coordinates were back-filled from the artifact, the certificate
    # itself — choose the arity the verifier checks against).
    # C3 Def 3.4: β_v(m) yields (a*_num, a*_den, rule); a registry row that
    # prescribes at least one leg registers the metric as a ratio. A row that
    # prescribes neither (atomic registry rows; the scoped-ratio rows with no
    # registered rate caliber) leaves the arity UNREGISTERED — C3 Def 3.10(b2)
    # reads that as MC(i), and the honest consequence is that for such a metric
    # the verifier cannot independently certify the arity coordinate at all
    # (check_V0 handles the MC(i) certificates elastically and reports it).
    ratio = binding_row is not None and bool(
        binding_row.get("numerator_anchor") or binding_row.get("denominator_anchor"))
    if ratio:
        arity_source = "beta_v(binding row prescribes legs)"
    elif binding_row is not None:
        arity_source = "registry-row-prescribes-no-leg(arity unregistered; read as atomic)"
    else:
        arity_source = "no-registry-row(arity unregistered; read as atomic)"

    # -- prescribed anchors per role
    if ratio:
        prescribed = {"numerator": binding_row.get("numerator_anchor"),
                      "denominator": binding_row.get("denominator_anchor")}
    elif gv.is_p2 and binding_row is not None and binding_row.get("atom_anchor"):
        # p2 registers the atomic leg's anchor outright on its binding row
        prescribed = {"atom": binding_row.get("atom_anchor")}
        arity_source = "registered-binding(atom leg)"
    else:
        a_m, _src = resolve_atomic_anchor(gv, q)
        # C3 Def 3.7 names the single non-ratio role "atom" (R(q) ⊆ {num,den} ∨
        # {atom}); certificates and question specs use that spelling, so the
        # verifier must too. ("atomic" is accepted as an alias on input only.)
        prescribed = {"atom": a_m}
    roles = list(prescribed.keys())
    if gv.is_p2 and isinstance(q.get("anchor_override"), str) and q["anchor_override"]:
        # p2 structured re-anchor declaration ā: a bare reference applies to the
        # metric's primary leg (numerator of a ratio, atom otherwise) — the same
        # deterministic convention the producer uses; a reference naming a
        # registered anchor/effective column is the no-op spelling.
        ref = q["anchor_override"]
        registered = any(a.get("anchor_id") == ref or a.get("effective_date") == ref
                         for a in (gv.anchors() or []))
        if not registered:
            overrides = dict(overrides)
            overrides["numerator" if ratio else "atom"] = ref

    kind, _payload = parse_asof(q.get("as_of"))
    conv, conv_src, conv_err = domain_window_periods(
        gv, q, roles, prescribed, overrides, binding_row)
    decl, decl_note = (None, "declared window input disabled (--no-declared-windows)")
    if allow_declared:
        decl, decl_note = declared_window_periods(q, roles)

    if conv is not None and decl is not None and not _periods_equal(conv, decl):
        # The question pins a window coordinate the domain convention does not
        # produce (C4 Def 4.6 rigid window commitment: a delta period pair, a
        # deliberately misaligned denominator leg, …). It is honoured — that IS
        # the request being certified — but it is a declared input, so say so.
        periods, wsrc = decl, "declared-override"
        wdetail = ("%s derives %s; the question presents %s (%s) — honoured as a "
                   "declared window commitment" %
                   (conv_src, " | ".join(w_str(p[roles[0]]) for p in conv),
                    " | ".join(w_str(p[roles[0]]) for p in decl), decl_note))
    elif conv is not None:
        periods, wsrc = conv, "derived"
        wdetail = conv_src + ("" if decl is None else "; agrees with the presented ω⃗")
    elif decl is not None:
        periods, wsrc = decl, "declared"
        wdetail = ("no independent derivation (%s); fell back to the presented "
                   "window coordinate (%s)" % (conv_err, decl_note))
    else:
        if kind == "unparseable":
            return {"status": "unparseable",
                    "detail": "as_of %r unparseable (A5 sentinel)" % (q.get("as_of"),),
                    "roles": {}, "ratio": ratio, "arity_source": arity_source,
                    "binding_row": binding_row, "periods": 0,
                    "window_source": None, "window_source_detail": conv_err}
        return {"status": "underivable",
                "detail": "ω_r not independently derivable: %s; and no usable "
                          "declared coordinate (%s)" % (conv_err, decl_note),
                "roles": {}, "ratio": ratio, "arity_source": arity_source,
                "binding_row": binding_row, "periods": 0,
                "window_source": None, "window_source_detail": conv_err}

    role_map = {}
    for i, per in enumerate(periods):
        for role, w in per.items():
            key = role if i == 0 else "%s#%d" % (role, i)
            aid = overrides.get(role, prescribed.get(role))
            entry = {"declared": role in overrides, "window": w,
                     "prescribed": prescribed.get(role), "window_source": wsrc,
                     # a *re-anchor* is a declaration that differs from the prescribed
                     # anchor; declaring the prescribed anchor again is not one
                     "reanchored": role in overrides and overrides[role] != prescribed.get(role)}
            if aid is None:
                entry["anchor"] = None
            elif gv.anchor(aid) is not None:
                entry["anchor"] = aid
            else:
                entry["anchor"] = ("REF", aid)  # unregistered anchor reference (D8)
            role_map[key] = entry
    return {"status": "ok", "detail": "", "roles": role_map, "ratio": ratio,
            "arity_source": arity_source, "binding_row": binding_row,
            "periods": len(periods), "window_source": wsrc,
            "window_source_detail": wdetail, "conv_windows": conv}


# =========================================================================
# D. certificate access helpers
# =========================================================================

def load_cert(obj):
    """Accept either the §6.2 envelope {"sql"/"refusal", "certificate": {...}}
    or a bare certificate object; returns (cert, out_sql, env_refusal)."""
    if not isinstance(obj, dict):
        return (None, None, None)
    if "certificate" in obj and isinstance(obj["certificate"], dict):
        cert = obj["certificate"]
        return (cert, obj.get("sql") or cert.get("sql"), obj.get("refusal"))
    return (obj, obj.get("sql"), None)


def cert_decision(cert):
    d = (cert.get("disclosure") or {}) if isinstance(cert, dict) else {}
    return d.get("decision")


def cert_alpha(cert):
    """Certificate anchors[] -> {role_key: {'anchor': .., 'window': win|None,
    'declared_override': .., raw}}. role key gets '#<period>' suffix for
    period > 0 entries."""
    out = {}
    for ent in (cert.get("anchors") or []):
        if not isinstance(ent, dict):
            continue
        role = ent.get("role")
        if role in ("num", "n"):
            role = "numerator"
        if role in ("den", "d"):
            role = "denominator"
        per = ent.get("period") or 0
        key = role if not per else "%s#%d" % (role, per)
        w = parse_window_obj(ent.get("window"))
        aid = ent.get("anchor_id")
        if aid is None and ent.get("anchor_ref"):
            aid = ("REF", ent.get("anchor_ref"))
        elif isinstance(aid, str) and ent.get("unregistered_reference"):
            # C3 Def 3.7 RefA_v: the certificate names an anchor reference it
            # declares unregistered. Either spelling is machine-readable; V2
            # re-checks the claim against A_v (a false claim is REJECTed there).
            aid = ("REF", aid)
        out[key] = {"anchor": aid, "window": w, "raw": ent,
                    "declared_override": bool(ent.get("declared_override"))}
    return out


def canonical_ctx_hash(ctx):
    blob = json.dumps(ctx if ctx is not None else {}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def same_ctx_hash(got, want):
    """Compare a certificate-carried context hash against a locally computed one.
    An optional algorithm prefix ("sha256:") is presentation, not content — C5
    Def 5.1 fixes the digest, not its spelling; both spellings are accepted."""
    if got in (None, ""):
        return True
    g = str(got).split(":", 1)[-1].strip().lower()
    return g == str(want).split(":", 1)[-1].strip().lower()


EMPTY_CTX_HASH = canonical_ctx_hash({})


# =========================================================================
# E. SQL scanning (V6a and probe validation) — syntactic, template-class
# =========================================================================

_CTE_RE = re.compile(r"(?:\bWITH\b|,)\s*([A-Za-z_]\w*)\s+AS\s*\(", re.I)
_TAB_RE = re.compile(r"\b(?:FROM|JOIN)\s+(\"[^\"]+\"|[A-Za-z_][\w\.\"]*)", re.I)
_CMP_RE = re.compile(
    r"([A-Za-z_][\w\.]*)\s*(>=|<=|<>|!=|<|>|=)\s*(?:DATE|TIMESTAMP)\s*'(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2}))?'",
    re.I)
_BETWEEN_RE = re.compile(
    r"([A-Za-z_][\w\.]*)\s+BETWEEN\s+DATE\s*'(\d{4}-\d{2}-\d{2})'\s+AND\s+DATE\s*'(\d{4}-\d{2}-\d{2})'",
    re.I)
_TRUNC_RE = re.compile(
    r"date_trunc\s*\(\s*'month'\s*,\s*([A-Za-z_][\w\.]*)\s*\)\s*=\s*DATE\s*'(\d{4}-\d{2}-\d{2})'",
    re.I)
_CAST_RE = re.compile(r"CAST\s*\(\s*([A-Za-z_][\w\.]*)\s+AS\s+DATE\s*\)", re.I)
_AGG_RATE_RE = re.compile(r"\b(?:SUM|AVG)\s*\(\s*[^()]*\b\w*(?:rate|share|ratio)\w*\b",
                          re.I)


def cte_names(sql):
    return {m.group(1).lower() for m in _CTE_RE.finditer(sql)}


_SQL_KEYWORDS = {
    "as", "on", "and", "or", "not", "where", "group", "order", "having", "limit",
    "union", "except", "intersect", "join", "inner", "left", "right", "full",
    "cross", "then", "else", "end", "when", "case", "select", "from", "using",
    "is", "in", "between", "like", "ilike", "offset", "window", "qualify",
}


def subquery_aliases(sql):
    """Correlation names of derived tables — `FROM (SELECT …) n`. They are not
    relations of G_v and must never be counted as touched objects (V6a). The
    innermost-out block decomposition blanks the parenthesised SELECT, which
    would otherwise leave the bare alias directly after FROM/JOIN and make it
    look like a table name (rma_q3's `… ) n, ( … ) d` delta template)."""
    out = set()
    pat = re.compile(r"\(\s*SELECT\b", re.I)
    for m in pat.finditer(sql):
        depth = 0
        for i in range(m.start(), len(sql)):
            if sql[i] == "(":
                depth += 1
            elif sql[i] == ")":
                depth -= 1
                if depth == 0:
                    tail = re.match(r"\s*(?:AS\s+)?([A-Za-z_]\w*)", sql[i + 1:], re.I)
                    if tail and tail.group(1).lower() not in _SQL_KEYWORDS:
                        out.add(tail.group(1).lower())
                    break
    return out


def sql_tables(sql, extra_ctes=frozenset()):
    """Referenced tables (last dotted component, lowercased), CTE names excluded.
    `extra_ctes`: CTE names computed on the full statement — needed when scanning
    a block whose defining WITH-clause parentheses lie outside the block."""
    ctes = cte_names(sql) | set(extra_ctes)
    tabs = []
    for m in _TAB_RE.finditer(sql):
        t = m.group(1).rstrip(",")
        base = t.split(".")[-1].strip('"').lower()
        if base and base not in ctes:
            tabs.append(base)
    return tabs


def _col_base(col):
    return col.split(".")[-1].strip('"').lower()


# pilot2 predicate spellings: the canonical day expression over heterogeneous
# storage types is substr(CAST(col AS VARCHAR),1,10); calendar-token anchors
# (YYYYMM / YYYY-MM / academic YYYY-YYYY) compare CAST(col AS VARCHAR) against
# token literals whose day-space denotation is the token's granule window.
_QCOL = r"(?:[A-Za-z_]\w*\.)?\"[^\"]+\"|[A-Za-z_][\w\.]*"
_SUBSTR_CMP_RE = re.compile(
    r"substr\s*\(\s*CAST\s*\(\s*(" + _QCOL + r")\s+AS\s+VARCHAR\s*\)\s*,\s*1\s*,\s*10\s*\)"
    r"\s*(>=|<=|<>|!=|<|>|=)\s*'(\d{4}-\d{2}-\d{2})'", re.I)
_TOKCAST_CMP_RE = re.compile(
    r"CAST\s*\(\s*(" + _QCOL + r")\s+AS\s+VARCHAR\s*\)"
    r"\s*(>=|<=|<>|!=|<|>|=)\s*'(\d{6}|\d{4}-\d{2}|\d{4}-\d{4})'", re.I)
_PLAIN_STR_CMP_RE = re.compile(
    r"(" + _QCOL + r")\s*(>=|<=|<>|!=|<|>|=)\s*'(\d{4}-\d{2}-\d{2}|\d{6}|\d{4}-\d{2}|\d{4}-\d{4})'")


def _token_atoms(col, op, tok):
    """Expand a calendar-token comparison into day-space atoms."""
    w = token_day_window(tok)
    if w is None:
        return []
    lo, hi = w[0][0], w[-1][1]
    cb = _col_base(col)
    if op == "=":
        return [(cb, ">=", lo, False), (cb, "<", hi, False)]
    if op == ">=":
        return [(cb, ">=", lo, False)]
    if op == "<=":
        return [(cb, "<", hi, False)]
    if op == ">":
        return [(cb, ">=", hi, False)]
    if op == "<":
        return [(cb, "<", lo, False)]
    return []


def sql_date_atoms(sql):
    """[(colbase, op, date, has_time)] date-comparison atoms; BETWEEN and
    date_trunc month equality expanded; CAST(col AS DATE) folded to col;
    substr-day and calendar-token comparison forms recognised (pilot2)."""
    atoms = []
    work = sql

    def _blank(m):
        return " " * (m.end() - m.start())

    for m in _SUBSTR_CMP_RE.finditer(work):
        col, op, d = m.group(1), m.group(2), m.group(3)
        if op in ("<>", "!="):
            continue
        atoms.append((_col_base(col), op, _parse_day(d), False))
    work = _SUBSTR_CMP_RE.sub(_blank, work)
    for m in _TOKCAST_CMP_RE.finditer(work):
        atoms.extend(_token_atoms(m.group(1), m.group(2), m.group(3)))
    work = _TOKCAST_CMP_RE.sub(_blank, work)

    s = _CAST_RE.sub(lambda m: m.group(1), work)
    for m in _CMP_RE.finditer(s):
        col, op, d, tm = m.group(1), m.group(2), _parse_day(m.group(3)), m.group(4)
        atoms.append((_col_base(col), op, d, bool(tm and tm != "00:00:00")))
    s = _CMP_RE.sub(_blank, s)
    for m in _BETWEEN_RE.finditer(s):
        col, d1, d2 = m.group(1), _parse_day(m.group(2)), _parse_day(m.group(3))
        atoms.append((_col_base(col), ">=", d1, False))
        atoms.append((_col_base(col), "<=", d2, False))
    s = _BETWEEN_RE.sub(_blank, s)
    for m in _TRUNC_RE.finditer(s):
        col, d = m.group(1), _parse_day(m.group(2))
        atoms.append((_col_base(col), ">=", dt.date(d.year, d.month, 1), False))
        atoms.append((_col_base(col), "<", month_next(d.year, d.month), False))
    s = _TRUNC_RE.sub(_blank, s)
    for m in _PLAIN_STR_CMP_RE.finditer(s):
        col, op, lit = m.group(1), m.group(2), m.group(3)
        if op in ("<>", "!="):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lit):
            atoms.append((_col_base(col), op, _parse_day(lit), False))
        else:
            atoms.extend(_token_atoms(col, op, lit))
    return atoms


def atoms_denotation(atoms, col):
    """Denotation window of the conjunction of atoms over column `col`
    (⊤ when no atom mentions it). Equality/inequality on a timestamp with a
    non-midnight time part is conservatively widened to its day."""
    w = ((None, None),)
    for cb, op, d, has_time in atoms:
        if cb != col.lower():
            continue
        if op == ">=":
            aw = ((d, None),)
        elif op == ">":
            aw = ((d + DAY, None),)
        elif op == "<":
            aw = ((None, d if not has_time else d + DAY),)
        elif op == "<=":
            aw = ((None, d + DAY),)
        elif op == "=":
            aw = ((d, d + DAY),)
        else:  # <> / != carry no upper/lower information for containment
            continue
        w = w_intersect(w, aw)
    return w


def scd2_point_predicate(atoms, vf_col, vt_col, win):
    """C3 Def 3.3 interval anchor + D7 point-window semantics: the SQL realises
    `vf <= d < vtc` for the certified point window {d}. Returns (ok, why).
    The predicate is the *in-effect* test, not a containment of a marker column,
    so it is checked structurally rather than by denotation."""
    days = [lo for (lo, hi) in (win or ()) if lo is not None and hi is not None
            and (hi - lo) == DAY]
    if not win or len(days) != len(win) or len(days) != 1:
        return (False, "certified window %s is not a D7 point window {d}" % w_str(win))
    d = days[0]
    vf, vt = (vf_col or "").lower(), (vt_col or "").lower()
    if not vf or not vt:
        return (False, "anchor row declares no (valid_from_col, valid_to_col) pair")
    lower_ok = any(cb == vf and op in ("<=", "<", "=") and
                   (a_d == d or (op == "<" and a_d == d + DAY))
                   for cb, op, a_d, _ in atoms)
    upper_ok = any(cb == vt and op in (">", ">=") and
                   (a_d == d or (op == ">=" and a_d == d + DAY))
                   for cb, op, a_d, _ in atoms)
    if not lower_ok:
        return (False, "missing `%s <= DATE '%s'`" % (vf, d.isoformat()))
    if not upper_ok:
        return (False, "missing `%s > DATE '%s'`" % (vt, d.isoformat()))
    return (True, "vf<=d<vtc replayed at d=%s" % d.isoformat())


def split_select_blocks(sql):
    """Innermost-out decomposition into scoped SELECT blocks for the template
    query class Q_tmpl (single-block aggregates; C5 Thm 5.10(b) scope).
    Returns list of block strings (innermost parenthesised SELECTs first, the
    residual top level last)."""
    blocks = []
    s = sql
    pat = re.compile(r"\(\s*SELECT\b", re.I)
    for _ in range(64):
        found = None
        for m in pat.finditer(s):
            start = m.start()
            depth = 0
            for i in range(start, len(s)):
                if s[i] == "(":
                    depth += 1
                elif s[i] == ")":
                    depth -= 1
                    if depth == 0:
                        inner = s[start + 1:i]
                        if not pat.search(inner):
                            found = (start, i, inner)
                        break
            if found:
                break
        if not found:
            break
        start, end, inner = found
        blocks.append(inner)
        s = s[:start] + " " * (end - start + 1) + s[end + 1:]
    blocks.append(s)
    return blocks


def _win_pred(col, w):
    """SQL predicate for a normalised window (verifier-side, for re-queries)."""
    parts = []
    for lo, hi in w:
        seg = []
        if lo is not None:
            seg.append("%s >= DATE '%s'" % (col, lo.isoformat()))
        if hi is not None:
            seg.append("%s < DATE '%s'" % (col, hi.isoformat()))
        parts.append("(" + (" AND ".join(seg) if seg else "TRUE") + ")")
    return " OR ".join(parts) if parts else "FALSE"


def _same_marker_rows(gv, tabs, eff_col, den, expect_win):
    """Do the probe's own window and the certified window select the same marker
    rows of the probed object? Re-queried from D, never inferred."""
    for t in sorted(tabs):
        tab = gv.qualify(t)
        if tab is None:
            return (False, "probed object %r not resolvable for the marker re-query" % t)
        try:
            a = gv.con.execute("SELECT count(*), count(DISTINCT %s) FROM %s WHERE %s"
                               % (eff_col, tab, _win_pred(eff_col, den))).fetchone()
            b = gv.con.execute("SELECT count(*), count(DISTINCT %s) FROM %s WHERE %s"
                               % (eff_col, tab, _win_pred(eff_col, expect_win))).fetchone()
        except Exception as e:  # noqa: BLE001 — surfaced as a probe-validation failure
            return (False, "marker re-query failed on %r: %s" % (t, e))
        if a != b:
            return (False, "marker rows of %r differ: probe window %r vs certified %r"
                    % (t, a, b))
    return (True, "same marker rows on D")


def validate_probe_sql(gv, sql, allowed_tables, eff_col, expect_win, scope_literals):
    """A probe must be a single-scan SELECT aggregate over an allowed object,
    whose time-predicate denotation over the anchor's valid-time column equals
    the certified window, carrying the question's scope literals (§3.2(2): the
    verifier re-executes it; here we first pin what it may read)."""
    if not isinstance(sql, str) or not sql.strip():
        return "probe sql missing"
    body = sql.strip().rstrip(";")
    if ";" in body:
        return "probe must be a single statement"
    if not re.match(r"^\s*SELECT\b", body, re.I):
        return "probe must be a SELECT"
    if _FORBIDDEN_SQL.search(body):
        return "probe contains forbidden statement keyword"
    tabs = set(sql_tables(body, subquery_aliases(body)))
    if not tabs:
        return "probe reads no table"
    bad = tabs - {t.lower() for t in allowed_tables}
    if bad:
        return "probe reads outside the certified object closure: %s" % ",".join(sorted(bad))
    atoms = sql_date_atoms(body)
    den = atoms_denotation(atoms, eff_col)
    if expect_win is not None and not w_eq(den, expect_win):
        # The probe must range over exactly the certified window. Denotation
        # equality is the *syntactic* proxy for that; it is too strong on
        # coarser-grain objects, where one marker value denotes a whole granule
        # (C3 Def 3.3: vt_a(r)=gr_{g_a}(r.eff) — a `_1m` roll-up carries the month
        # start as the marker of its month granule, so `dt = DATE '2026-05-01'`
        # *is* the May window on that object). Fall back to the semantic test the
        # syntax stands for, re-queried from D (§3.2(2) licenses re-querying, and
        # a marker-set identity is strictly stronger evidence than the syntax):
        # no leakage outside the window, and the same marker rows selected.
        if not w_subset(den, expect_win):
            return ("probe window denotation %s ⊄ certified window %s (probe reads "
                    "outside the certified window)" % (w_str(den), w_str(expect_win)))
        same, why = _same_marker_rows(gv, tabs, eff_col, den, expect_win)
        if not same:
            return ("probe window denotation %s != certified window %s (%s)"
                    % (w_str(den), w_str(expect_win), why))
    for lit in scope_literals:
        if lit not in body:
            return "probe misses the question scope literal %r" % lit
    return None


def exec_scalar(con, sql):
    """Execute a validated probe, returning ('empty'|'null'|'value', v)."""
    body = sql.strip().rstrip(";")
    row = con.execute(body).fetchone()
    if row is None:
        return ("empty", None)
    v = row[0]
    if v is None:
        return ("null", None)
    return ("value", v)


def in_Z(kind, v):
    """MC(ii) refusal set 𝒵 = {∅, NULL} ∪ {z: z<=0} (D4 widened form)."""
    if kind in ("empty", "null"):
        return True
    try:
        return float(v) <= 0
    except (TypeError, ValueError):
        return False


# =========================================================================
# F. coverage / guard replays (C3 Def 3.14–3.16 on the guard chain)
# =========================================================================

def anchor_coverage(gv, arow, declared_mode=None):
    """Cov_v(a) per the anchor's coverage_mode (D3: versioned per-anchor
    attribute; resolution order: G_v column > certificate declaration >
    spec default by anchor type: snapshot_effective_date -> hull,
    scd_type2 -> strict_member). Returns (window, mode, err)."""
    if arow is None:
        return (None, None, "anchor row missing")
    mode = None
    if "coverage_mode" in arow and arow.get("coverage_mode"):
        mode = arow.get("coverage_mode")
        if declared_mode and declared_mode != mode:
            return (None, mode, "certificate coverage_mode %r contradicts G_v declaration %r"
                    % (declared_mode, mode))
    elif declared_mode:
        if declared_mode not in COVERAGE_MODES:
            return (None, None, "invalid coverage_mode %r" % (declared_mode,))
        mode = declared_mode
    else:
        mode = "strict_member" if arow.get("anchor_type") == "scd_type2" else "hull"
    def _d(x):
        if x is None or x == "":
            return None
        if isinstance(x, dt.datetime):
            return x.date()
        return x if isinstance(x, dt.date) else _parse_day(x)

    if arow.get("family_rows") is not None:
        # object-level registry family: V_v(a) = ⋃ registered marker intervals
        ivs = []
        for r in arow["family_rows"]:
            lo, hi = _d(r.get("valid_from")), _d(r.get("valid_to"))
            ivs.append((lo, (hi + DAY) if hi is not None else None))
        cov = w_norm(ivs)
    elif arow.get("anchor_type") == "scd_type2":
        tab = gv.qualify(arow.get("semantic_object"))
        if tab is None:
            return (None, mode, "anchor object %r not found" % arow.get("semantic_object"))
        vf, vt = arow.get("valid_from_col"), arow.get("valid_to_col")
        rows = gv.con.execute(
            'SELECT "%s", "%s" FROM %s' % (vf, vt, tab)).fetchall()
        ivs = []
        for a, b in rows:
            if a is None:
                continue
            a = a.date() if isinstance(a, dt.datetime) else a
            b = b.date() if isinstance(b, dt.datetime) else b
            if b is None:
                ivs.append((a, None))   # open in-effect row: [vf, +inf) (D7)
            elif a < b:  # zero-length rows contribute ∅ (C3 良构注记)
                ivs.append((a, b))
        cov = w_norm(ivs)
    elif not arow.get("effective_date") and (arow.get("valid_from") or arow.get("valid_to")):
        # Declared-validity anchor (C3 Def 3.3): the row states the anchor's
        # validity interval outright instead of exposing an effective-date column
        # to scan — typical of snapshot-table anchors, where the snapshot IS the
        # anchored state over [valid_from, valid_to]. Coverage is that interval.
        lo, hi = _d(arow.get("valid_from")), _d(arow.get("valid_to"))
        cov = w_norm([(lo, (hi + DAY) if hi is not None else None)])
    else:
        tab = gv.qualify(arow.get("semantic_object"))
        if tab is None:
            return (None, mode, "anchor object %r not found" % arow.get("semantic_object"))
        col = arow.get("effective_date")
        rows = gv.con.execute('SELECT DISTINCT "%s" FROM %s WHERE "%s" IS NOT NULL'
                              % (col, tab, col)).fetchall()
        gran = arow.get("granularity") or "day"
        if gran.startswith("month_token") or gran == "academic_year_token":
            # calendar-token markers: each token denotes its granule's day window
            ivs = []
            for (v,) in rows:
                w = token_day_window(str(v))
                if w is not None:
                    ivs.extend(w)
            cov = w_norm(ivs)
        else:
            days = []
            for (d,) in rows:
                if isinstance(d, dt.datetime):
                    days.append(d.date())
                elif isinstance(d, dt.date):
                    days.append(d)
                else:
                    try:
                        days.append(_parse_day(str(d)[:10]))
                    except ValueError:
                        continue
            cov = w_from_dates(days)
    if mode in ("hull", "hull_right_open", "hull_left_open"):
        h = w_hull(cov)
        if not h:
            cov = tuple()
        elif mode == "hull":
            cov = h
        elif mode == "hull_right_open":
            cov = ((h[0][0], None),)      # [min, +inf)
        else:
            cov = ((None, h[0][1]),)      # (-inf, max]
    return (cov, mode, None)


def anchor_valid_dates(gv, arow):
    """V(a): the anchor's effective marker date set (snapshot anchors)."""
    tab = gv.qualify(arow.get("semantic_object"))
    col = arow.get("effective_date")
    rows = gv.con.execute("SELECT DISTINCT %s FROM %s WHERE %s IS NOT NULL"
                          % (col, tab, col)).fetchall()
    return {(d.date() if isinstance(d, dt.datetime) else d) for (d,) in rows}


def p2_realization_days(gv, arow, win):
    """Window-restricted realisation day set of an anchor (window_realization_symdiff
    audit, C3 Def 3.8(iv) on the request pair): hull-mode anchors realise every
    calendar day of the window inside their hull; strict_member anchors realise
    exactly their marker days inside the window. Token-granule anchors do not
    take part in day-set audits (None)."""
    if (arow.get("granularity") or "day") != "day":
        return None
    if win is None or w_empty(win):
        return set()
    lo, hi = win[0][0], win[-1][1]
    if lo is None or hi is None or (hi - lo).days > 400:
        return None
    tab = gv.qualify(arow.get("semantic_object"))
    col = arow.get("effective_date")
    if tab is None or not col:
        return None
    if arow.get("coverage_mode") == "strict_member":
        rows = gv.con.execute(
            'SELECT DISTINCT substr(CAST("%s" AS VARCHAR),1,10) FROM %s '
            'WHERE "%s" IS NOT NULL AND substr(CAST("%s" AS VARCHAR),1,10) >= \'%s\' '
            "AND substr(CAST(\"%s\" AS VARCHAR),1,10) < '%s'"
            % (col, tab, col, col, lo.isoformat(), col, hi.isoformat())).fetchall()
        return {r[0] for r in rows}
    mn, mx = gv.con.execute(
        'SELECT MIN(substr(CAST("%s" AS VARCHAR),1,10)), '
        'MAX(substr(CAST("%s" AS VARCHAR),1,10)) FROM %s WHERE "%s" IS NOT NULL'
        % (col, col, tab, col)).fetchone()
    out = set()
    d = lo
    while d < hi:
        s = d.isoformat()
        if mn is not None and mn <= s <= mx:
            out.add(s)
        d += DAY
    return out


def replay_oov(gv, roles):
    """OOV original condition over the role map (version-axis branch handled
    in V1): some ω_r(T)↑, or some registered-anchor role with
    W_r ∩ Cov_v(a_r) = ∅. Unregistered REF roles do not participate
    (C3 Def 3.14 vacuity convention). Roles marked pair=True belong to a
    cross-anchor svw pair under the window-realization audit: their coverage
    emptiness is adjudicated at PAIR level — the pair-level audit precedes
    single-leg coverage, so OOV holds only when EVERY pair role is empty
    (a mixed pair is the audit's (iv) failure, not OOV).
    Returns (bool|None, detail)."""
    pair_state = []
    for key, ent in roles.items():
        a = ent.get("anchor")
        w = ent.get("window")
        if ent.get("unparseable"):
            return (True, "role %s: window unparseable" % key)
        if a is None or (isinstance(a, tuple) and a[0] == "REF"):
            continue
        arow = gv.anchor(a)
        if arow is None:
            continue  # vacuity (object not nameable here; guarded elsewhere)
        cov, mode, err = anchor_coverage(gv, arow, ent.get("coverage_mode"))
        if err:
            return (None, "role %s: %s" % (key, err))
        if w is None:
            continue
        empty = w_empty(w_intersect(w, cov))
        if ent.get("pair"):
            pair_state.append((key, a, mode, empty, w, cov))
            continue
        if empty:
            return (True, "role %s: W ∩ Cov_v(%s)[%s] = ∅ (W=%s, Cov=%s)"
                    % (key, a, mode, w_str(w), w_str(cov)))
    if pair_state and all(e for _, _, _, e, _, _ in pair_state):
        k, a, mode, _, w, cov = pair_state[0]
        return (True, "pair roles all empty: W ∩ Cov = ∅ on both legs (e.g. role "
                      "%s anchor %s[%s], W=%s, Cov=%s)"
                % (k, a, mode, w_str(w), w_str(cov)))
    return (False, "all role windows intersect their anchor coverage"
                   + ("" if not pair_state else
                      " (pair-level: %d/%d legs empty — audit territory, not OOV)"
                      % (sum(1 for s in pair_state if s[3]), len(pair_state))))


# The comparison-granule lattice clause (iii) tests against is {day, month,
# year}; β_v registers a per-leg *window* granularity, which maps onto it.
# `range_request` registers "the coordinate is the window the request presents"
# and therefore registers no granule at all.
# `academic_year_token` maps to `month`, NOT to `year`: its registered window is
# [Jul 1, Jul 1), month-aligned but never calendar-year-aligned, so `year` is
# the wrong join in this three-point lattice and would reject the school-year
# bindings on their own registered convention.
CMP_GRAN_OF_WINDOW_GRAN = {
    "month": "month", "month_token": "month", "academic_year_token": "month",
    "year": "year",
    "day": "day", "member_day": "day", "cum_day": "day",
    "range_request": None,
}


def resolve_cmp_granularity(brow):
    """g^cmp resolved from G_v ALONE (C3 Def 3.8(iii)): the binding row's own
    `cmp_granularity` column where a seed spells one, else re-derived from that
    row's registered `window_gran`.  The certificate's `g_cmp` is never
    consulted — clause (iii) is a coordinate the verifier must re-derive, not
    one it may inherit.  Returns None when β_v registers no granule (a
    `range_request` row, an unknown token, or legs that disagree): clause (iii)
    then has no granule lattice to test against, and the AM(iii) witness replay
    fails closed on it."""
    if not brow:
        return None
    if brow.get("cmp_granularity"):
        return brow.get("cmp_granularity")
    wg = brow.get("window_gran")
    if isinstance(wg, str):
        wg = {"atom": wg}
    if not isinstance(wg, dict):
        return None
    got = set()
    for v in wg.values():
        if v is None:
            continue
        if v not in CMP_GRAN_OF_WINDOW_GRAN:
            return None                      # unregistered token: not derivable
        got.add(CMP_GRAN_OF_WINDOW_GRAN[v])
    if len(got) != 1:
        return None                          # nothing registered, or legs disagree
    return got.pop()


def replay_svw(gv, roles, binding_row, adm_mode, g_cmp=None):
    """P_svw clause replay on the candidate assignment (C3 Def 3.8).
    Returns (passed, first_fail_clause, details) over clauses (i)-(iv).
    Multi-period questions replay the single-period restriction per period
    (C3 Cor 3.17'); the first failing period reports."""
    details = []
    prescribed = {"numerator": binding_row.get("numerator_anchor"),
                  "denominator": binding_row.get("denominator_anchor")}
    periods = sorted({k.split("#")[1] if "#" in k else "0" for k in roles})
    for per in periods:
        suffix = "" if per == "0" else "#" + per
        rn = roles.get("numerator" + suffix)
        rd = roles.get("denominator" + suffix)
        if rn is None or rd is None:
            continue
        # (i) anchor fidelity — unregistered references violate by construction
        for role_name, ent in (("numerator", rn), ("denominator", rd)):
            a = ent.get("anchor")
            star = prescribed[role_name]
            if isinstance(a, tuple) and a[0] == "REF":
                return (False, "(i)", "clause (i): declared anchor %r unregistered in A_v "
                                      "(≠ prescribed %r)" % (a[1], star))
            if a != star:
                return (False, "(i)", "clause (i): %s anchor %r ≠ prescribed %r"
                        % (role_name, a, star))
        details.append("clause (i) ok")
        # (ii) same window
        wn, wd = rn.get("window"), rd.get("window")
        if wn is None or wd is None or not w_eq(wn, wd):
            return (False, "(ii)", "clause (ii): W_n=%s ≠ W_d=%s"
                    % (w_str(wn), w_str(wd)))
        details.append("clause (ii) ok")
        # (iii) window-granularity expressibility at the binding's comparison
        # granularity g^cmp, re-derived from β_v's own registered window_gran
        # (C3 Def 3.8(iii)) — never read off the certificate.  A row registering
        # no granule (range_request) leaves the granule lattice unconstrained,
        # which month_granule_aligned treats as the 'day' bottom.
        gcmp = resolve_cmp_granularity(binding_row) or g_cmp
        ok, edge = month_granule_aligned(wn, gcmp)
        if not ok:
            return (False, "(iii)", "clause (iii): W ∉ W_{%s}; misaligned boundary %s"
                    % (gcmp, edge))
        details.append("clause (iii) ok")
        # (iv) anchor-pair admissibility per declared adm_check_mode.
        # First, the C3 §2 well-formedness invariant as a VERIFIER obligation:
        # a binding row whose two prescribed anchors differ carries a real
        # admissibility obligation and may not discharge it with the trivial
        # member.  Both anchors come from β_v, so this is re-derived from G_v,
        # not inherited from the coordinate the certificate asserts.
        if prescribed["numerator"] != prescribed["denominator"] \
                and adm_mode in (None, "trivial_true"):
            return (None, "(iv)", "distinct-anchor binding row may not replay the "
                                  "trivial clause-(iv) member (C3 §2 invariant, "
                                  "re-derived from β_v)")
        if adm_mode is None:
            return (None, "(iv)", "adm_check_mode undeclared: replay mode undecidable "
                                  "(C5 V3: 机器可读列缺失即不可判)")
        if adm_mode == "trivial_true":
            details.append("clause (iv) trivial_true")
        elif adm_mode == "symdiff_audit":
            an = gv.anchor(prescribed["numerator"])
            ad = gv.anchor(prescribed["denominator"])
            if an is None or ad is None:
                return (None, "(iv)", "anchor rows missing for symdiff audit")
            sd = anchor_valid_dates(gv, an) ^ anchor_valid_dates(gv, ad)
            if sd:
                return (False, "(iv)", "clause (iv): symdiff audit |V(a_n)△V(a_d)|=%d ≠ 0"
                        % len(sd))
            details.append("clause (iv) symdiff empty")
        elif adm_mode == "interval_containment":
            ad = gv.anchor(prescribed["denominator"])
            if ad is None or ad.get("anchor_type") != "scd_type2":
                return (None, "(iv)", "interval_containment needs an SCD-2 denominator anchor")
            covd, _, err = anchor_coverage(gv, ad, "strict_member")
            if err:
                return (None, "(iv)", err)
            days = [lo for (lo, hi) in wn if lo is not None and hi is not None
                    and (hi - lo) == DAY]
            if len(days) != len(wn) or not days:
                return (None, "(iv)", "interval_containment needs a finite point/day "
                                      "numerator window, got %s" % w_str(wn))
            for d in days:
                if w_empty(w_intersect(((d, d + DAY),), covd)):
                    return (False, "(iv)", "clause (iv): numerator granule %s outside "
                                           "denominator in-effect intervals" % d)
            details.append("clause (iv) containment ok")
        elif adm_mode == "window_realization_symdiff":
            an = gv.anchor(prescribed["numerator"])
            ad = gv.anchor(prescribed["denominator"])
            if an is None or ad is None:
                return (None, "(iv)", "anchor rows missing for the realization audit")
            rn = p2_realization_days(gv, an, wn)
            rd = p2_realization_days(gv, ad, wd)
            if rn is None or rd is None:
                # R4-TC-R4-3b (2026-08-07): this used to fall through to PASS.
                # A declared clause-(iv) obligation the verifier cannot replay
                # is UNDECIDABLE, not discharged -- the same treatment
                # interval_containment already gets above, and the only reading
                # consistent with the C3 §2 invariant enforced at the head of
                # this clause.  Callers are fail-closed on a None verdict.
                return (None, "(iv)", "realization audit not applicable: "
                                      "window/granularity outside the audit's "
                                      "domain")
            if rn != rd:
                return (False, "(iv)", "clause (iv): window-realization symdiff "
                                       "|Δ|=%d (num %d day(s), den %d day(s))"
                        % (len(rn ^ rd), len(rn), len(rd)))
            else:
                details.append("clause (iv) window-realization sets equal")
        else:
            return (None, "(iv)", "unknown adm_check_mode %r" % (adm_mode,))
    return (True, None, "; ".join(details))


def registered_rule(brow):
    """Rule name of a binding row. Enterprise seeds spell the column `rule`;
    the public registry seed spells it `binding_rule` — same content, and C3
    Def 3.8 fixes the rule's meaning, not the column's spelling."""
    if not brow:
        return None
    return brow.get("rule") or brow.get("binding_rule")


def _registers_coverage_mode(arow):
    """True iff G_v itself registers this anchor's coverage mode (the D3/G4
    per-anchor `coverage_mode` column). A synthesised registry *family* row
    carries no such registration — its strict_member reading is this
    verifier's own construction (Gv.anchor_family), not a governance
    declaration — so it counts as unregistered here."""
    return bool(arow) and not arow.get("synthesised_family") \
        and bool(arow.get("coverage_mode"))


def derive_adm_mode(gv, binding_row):
    """The clause-(iv) replay variant RE-DERIVED from β_v alone.

    (R5-M2, 2026-08-10) This used to be inherited: no seed spells an
    `adm_check_mode` column, so the G_v branch of resolve_adm_mode was dead and
    every certificate picked its own clause-(iv) variant — the exact coordinate
    the certificate section declares must never be inherited.  The variant is
    a *function of β_v*, and both implementations already hard-code that
    function; the verifier now computes it from the two governance facts it
    can re-query — the binding row's prescribed anchor PAIR and the two
    anchors' registered coverage declarations:

      * no prescribed pair                    -> not derivable (no obligation
        is nameable here; β_v(m)↑ is adjudicated by the callers)
      * a_n = a_d                             -> `trivial_true`: one anchor has
        nothing to align against, so the obligation discharges by identity
      * SCD-2 denominator, non-SCD-2 numerator -> `interval_containment`: an
        in-effect interval anchor exposes no marker set to difference, so the
        clause tests granule containment in its in-effect intervals (D7)
      * both anchors register a coverage mode -> `window_realization_symdiff`:
        the registered mode is precisely what fixes each anchor's realisation
        (hull → calendar days inside the hull, strict_member → marker days),
        so the audit is the WINDOW-RESTRICTED realisation comparison
      * neither registers one                 -> `symdiff_audit`: with no
        registered realisation semantics the clause degenerates to the
        unwindowed marker-set symmetric difference V(a_n) △ V(a_d)
      * exactly one registers one             -> not derivable (fail closed:
        the pair has no common realisation semantics to audit under)

    Returns (mode|None, provenance-note). A None mode means "β_v does not fix
    a variant here", which callers treat as an UNDECLARED replay mode and fail
    closed on — never as a licence to read the mode off the certificate."""
    if not _beta_prescribes(binding_row):
        return (None, "β_v prescribes no anchor pair")
    na = binding_row.get("numerator_anchor")
    da = binding_row.get("denominator_anchor")
    if na == da:
        return ("trivial_true", "β_v pairs one anchor %r with itself" % (na,))
    an, ad = gv.anchor(na), gv.anchor(da)
    if an is None or ad is None:
        return (None, "prescribed anchors %r/%r not both registered in A_v" % (na, da))
    if ad.get("anchor_type") == "scd_type2" and an.get("anchor_type") != "scd_type2":
        return ("interval_containment",
                "β_v pairs a point anchor with the SCD-2 denominator %r" % (da,))
    cn, cd = _registers_coverage_mode(an), _registers_coverage_mode(ad)
    if cn and cd:
        return ("window_realization_symdiff",
                "A_v registers both coverage modes (%s[%s], %s[%s])"
                % (na, an.get("coverage_mode"), da, ad.get("coverage_mode")))
    if not cn and not cd:
        return ("symdiff_audit",
                "A_v registers no coverage mode for either of %r/%r" % (na, da))
    return (None, "only one of %r/%r registers a coverage mode" % (na, da))


def resolve_adm_mode(gv, binding_row, cert_binding):
    """adm variant resolution WITHOUT inheritance (C5 Def 5.3 read against the
    no-inherited-coordinate rule): G_v's machine-readable column where a seed
    spells one, else the variant re-derived from β_v by derive_adm_mode.  The
    certificate's own `adm_check_mode` is a *claim*: it is checked against the
    re-derived variant and a contradiction is an error, but it is never the
    source of the mode.  Returns (mode|None, err|None); a (None, None) result
    means β_v fixes no variant here and the callers fail closed."""
    gcol = None
    if binding_row and binding_row.get("adm_check_mode"):
        gcol = binding_row.get("adm_check_mode")
    cdecl = (cert_binding or {}).get("adm_check_mode")
    if cdecl is not None and cdecl not in ADM_MODES:
        return (None, "invalid adm_check_mode %r" % (cdecl,))
    if gcol:
        mode, why = gcol, "G_v machine-readable column"
    else:
        mode, why = derive_adm_mode(gv, binding_row)
    if mode is None:
        return (None, None)
    if cdecl and cdecl != mode:
        return (None, "certificate adm_check_mode %r contradicts the clause-(iv) "
                      "variant re-derived from G_v: %r (%s)" % (cdecl, mode, why))
    return (mode, None)


# =========================================================================
# G. the checks V0..V6c
# =========================================================================

class Ctx:
    """Shared per-verification state (computed once, used by several checks)."""

    def __init__(self, cert, out_sql, env_refusal, q, con, ctx, allow_declared=True):
        self.cert = cert
        self.sql = out_sql
        self.env_refusal = env_refusal
        self.q = q
        self.con = con
        self.audit_ctx = ctx
        self.allow_declared = allow_declared
        pin = (cert.get("graph_pin") or {}) if isinstance(cert, dict) else {}
        self.domain = pin.get("domain") or q.get("domain")
        self.version = pin.get("graph_version")
        self.gv = Gv(con, self.domain, self.version)
        self.dec = cert_decision(cert) if isinstance(cert, dict) else None
        self.alpha = cert_alpha(cert) if isinstance(cert, dict) else {}
        self.expected = derive_expected_alpha(self.gv, q, allow_declared=allow_declared)
        self.refusal = (cert.get("refusal") or {}) if isinstance(cert, dict) else {}
        self.reason = self.refusal.get("reason")
        self.witness = self.refusal.get("witness") or {}
        self.probes = cert.get("probes") or []
        self.binding = cert.get("binding") or {}
        self.routing = cert.get("routing") or []
        self.disclosure = cert.get("disclosure") or {}

    # roles for guard replay: certificate alpha entries enriched with any
    # per-entry coverage_mode declarations
    def guard_roles(self):
        roles = {}
        pair = self._pair_roles()
        for k, ent in self.alpha.items():
            roles[k] = {"anchor": ent.get("anchor"), "window": ent.get("window"),
                        "coverage_mode": (ent.get("raw") or {}).get("coverage_mode"),
                        "pair": str(k).split("#")[0] in pair}
        return roles

    def _pair_roles(self):
        """Roles governed by the cross-anchor window-realization audit
        (pair-level adjudication precedes single-leg coverage). Derived from
        G_v's registered binding, never from the certificate."""
        if not self.gv.is_p2:
            return set()
        brow = self.expected.get("binding_row") or {}
        na, da = brow.get("numerator_anchor"), brow.get("denominator_anchor")
        if na and da and na != da and \
                (brow.get("rule") == "same_valid_time_window"):
            return {"numerator", "denominator"}
        return set()

    def alpha_objects(self):
        """α's certified semantic objects, closed under the registered
        normalize_of/aggregate_of inheritance edges (C5 V6a)."""
        objs = set()
        for ent in self.alpha.values():
            a = ent.get("anchor")
            if isinstance(a, str):
                arow = self.gv.anchor(a)
                if arow:
                    objs |= {t.lower() for t in
                             self.gv.inherit_closure(arow.get("semantic_object") or "")}
        return objs

    def publication_objects(self, objs):
        """The object at which q's metric is *published* — the head of the
        registered numerator_of/denominator_of edges leaving a certified object
        for this metric. C3 Def 3.4 puts m ∈ M_v at that node, so reading the
        precomputed metric there is reading the anchored object one registered
        aggregation step on, not a foreign table (the time-predicate containment
        below still applies to it under the same role window)."""
        out = set()
        bm = base_metric(self.q.get("metric"))
        for e in self.gv.edges({"numerator_of", "denominator_of"}):
            em = base_metric(e.get("metric") or "")
            if em and bm and em == bm and \
                    (e.get("src") or "").split(".")[-1].lower() in objs:
                out.add((e.get("dst") or "").split(".")[-1].lower())
        return out

    def dimension_objects(self, objs):
        """Conformed dimensions registered in G_v as `dimension_of` edges into a
        certified object: the scope selector s of C3 Def 3.6 resolves its
        predicates through them (rma_q4's lvl1_name='Quality'). Registration in
        G_v is what makes them certified rather than free-floating joins."""
        out = set()
        for e in self.gv.edges({"dimension_of"}):
            if (e.get("dst") or "").split(".")[-1].lower() in objs:
                out.add((e.get("src") or "").split(".")[-1].lower())
        return out

    def allowed_tables(self):
        """Certified object closure for V6a / probe validation: anchor objects
        (their inheritance closure) + the metric's publication node + registered
        conformed dimensions + routing via tables. In the p2 seed schema the
        metric's REGISTERED measure/pred nodes and routing hops (re-queried from
        G_v, never trusted from the certificate) are certified objects too —
        C3 Def 3.4 registers m at those nodes."""
        objs = self.alpha_objects()
        allowed = set(objs)
        for ent in self.alpha.values():
            a = ent.get("anchor")
            arow = self.gv.anchor(a) if isinstance(a, str) else None
            # An anchor's own physical binding (the snapshot table it pins at
            # that valid time) is part of α's certified closure, not a foreign
            # table: reading it IS reading the anchored object at T.
            snap = arow.get("snapshot_table") if arow else None
            if snap:
                allowed.add(str(snap).split(".")[-1].lower())
        allowed |= self.publication_objects(objs)
        allowed |= self.dimension_objects(objs)
        for e in self.routing:
            r = self.gv.routing(e.get("caliber_key")) if isinstance(e, dict) else None
            if r and r.get("via_table"):
                allowed.add(str(r.get("via_table")).split(".")[-1].lower())
        if self.gv.is_p2:
            allowed |= self.p2_metric_tables()
        return allowed

    def p2_metric_tables(self):
        """G_v-registered physical tables of the metric's measures (their nodes
        and pred nodes) and of its routing hops (src and dst)."""
        out = set()
        m = self.q.get("metric")
        if not m:
            return out
        base = gv_base = None
        for r in self.gv.measures(m):
            t = self.gv.node_table(r.get("node_id"))
            if t:
                out.add(t.lower())
            for p in (r.get("preds") or []):
                if p.get("node"):
                    t2 = self.gv.node_table(p["node"])
                    if t2:
                        out.add(t2.lower())
        mrow = self.gv.metric_row(m)
        if mrow and mrow.get("kind") == "delta" and mrow.get("base_metric_id"):
            for r in self.gv.measures(mrow["base_metric_id"]):
                t = self.gv.node_table(r.get("node_id"))
                if t:
                    out.add(t.lower())
                for p in (r.get("preds") or []):
                    if p.get("node"):
                        t2 = self.gv.node_table(p["node"])
                        if t2:
                            out.add(t2.lower())
            for e in self.gv.metric_routings(mrow["base_metric_id"]):
                for t in (self.gv.node_table(e.get("src_node")),
                          self.gv.node_table(e.get("dst_node"))):
                    if t:
                        out.add(t.lower())
        if mrow and mrow.get("kind") == "report" and mrow.get("base_metric_id"):
            for r in self.gv.measures(mrow["base_metric_id"]):
                t = self.gv.node_table(r.get("node_id"))
                if t:
                    out.add(t.lower())
        for e in self.gv.metric_routings(m):
            for t in (self.gv.node_table(e.get("src_node")),
                      self.gv.node_table(e.get("dst_node"))):
                if t:
                    out.add(t.lower())
        return out

    def den_closure(self, suffix=""):
        ent = (self.alpha.get("denominator" + suffix) or self.alpha.get("atom")
               or self.alpha.get("atomic"))
        if not ent or not isinstance(ent.get("anchor"), str):
            return (set(), None, None)
        arow = self.gv.anchor(ent["anchor"])
        if not arow:
            return (set(), None, None)
        clo = {t.lower() for t in self.gv.inherit_closure(arow.get("semantic_object") or "")}
        if self.gv.is_p2:
            # the den probe legally reads the den leg's registered hop tables
            # (scope/entity joins included) — G_v-derived, per-metric
            m = self.q.get("metric")
            for e in self.gv.metric_routings(m, legs=("den", "scope", "entity")):
                for t in (self.gv.node_table(e.get("src_node")),
                          self.gv.node_table(e.get("dst_node"))):
                    if t:
                        clo.add(t.lower())
            for r in self.gv.measures(m, "den"):
                t = self.gv.node_table(r.get("node_id"))
                if t:
                    clo.add(t.lower())
                for p in (r.get("preds") or []):
                    if p.get("node"):
                        t2 = self.gv.node_table(p["node"])
                        if t2:
                            clo.add(t2.lower())
        return (clo, arow.get("effective_date"), ent.get("window"))


def check_V0(cx):
    """Question↔certificate correspondence: independent re-derivation of
    α_{q,v} and per-role comparison; dec=REWRITE narrowing mapping (C4 Def
    4.10); qid/as_of echo; exemptions only via machine-readable records."""
    cert, q = cx.cert, cx.q
    cq = cert.get("question") or {}
    if q.get("qid") and cq.get("qid") and q["qid"] != cq["qid"]:
        return ("FAIL", "certificate question.qid %r ≠ q.qid %r" % (cq.get("qid"), q.get("qid")))
    if q.get("as_of") is not None and cq.get("as_of") is not None \
            and str(q["as_of"]) != str(cq["as_of"]):
        return ("FAIL", "certificate question.as_of %r ≠ q.as_of %r"
                % (cq.get("as_of"), q.get("as_of")))
    if cx.gv.is_p2 and q.get("metric_alias"):
        # p2 alias resolution replay: the metric coordinate the certificate pins
        # must be the one the registered alias map (at the pinned version) yields
        # — metric substitution across the alias layer is a V0 reject.
        amap = cx.gv.aliases_map()
        want = amap.get(q["metric_alias"])
        got_m = cq.get("metric")
        if want is None:
            if cx.dec == "REFUSE" and cx.reason == "missing-caliber":
                pass  # unregistered alias: the MC(i) certificate is the legal shape
            else:
                return ("FAIL", "alias %r resolves to no metric@%s yet the "
                                "certificate answers" % (q["metric_alias"], cx.version))
        elif got_m is not None and got_m != want:
            return ("FAIL", "certificate metric %r ≠ alias resolution %r (alias %r@%s)"
                    % (got_m, want, q["metric_alias"], cx.version))
        if q.get("metric") is not None and want is not None and q["metric"] != want:
            return ("FAIL", "q.metric %r ≠ alias resolution %r (harness/gold skew)"
                    % (q.get("metric"), want))
    exp = cx.expected
    if exp["status"] == "underivable":
        return ("FAIL", "α_{q,v} not independently derivable: %s" % exp["detail"])
    if exp["status"] == "unparseable":
        # I2'(b): only an OOV refusal with the unparseable-as_of witness variant
        # may stand; its roles may be windowless.
        if cx.dec == "REFUSE" and cx.reason == "out-of-validity" and \
                (cx.witness.get("type") in ("unparseable-asof", "asof-unparseable")):
            if str(cx.witness.get("raw_as_of")) != str(q.get("as_of")):
                return ("FAIL", "I2'(b) witness raw_as_of %r ≠ q.as_of %r"
                        % (cx.witness.get("raw_as_of"), q.get("as_of")))
            return ("PASS", "as_of unparseable; I2'(b) OOV degenerate variant matches")
        return ("FAIL", "as_of %r unparseable but certificate is not the I2'(b) "
                        "OOV degenerate variant" % (q.get("as_of"),))

    got = cx.alpha
    problems = []
    mc1 = (cx.dec == "REFUSE" and cx.reason == "missing-caliber"
           and (cx.witness.get("type") == "routing-lookup"))
    for key, ent in exp["roles"].items():
        gent = got.get(key)
        if gent is None:
            if mc1:
                continue  # I2'(a) explicit empty assignment permitted for MC(i)
            problems.append("role %s missing from certificate α" % key)
            continue
        ea, ga = ent["anchor"], gent.get("anchor")
        if isinstance(ea, tuple):
            # expected: an unregistered anchor reference (D8). Accept either the
            # explicit anchor_ref encoding or a bare anchor_id that indeed has
            # no row in A_v (V2 re-confirms unregisteredness).
            if isinstance(ga, tuple):
                ga_t = ga
            elif isinstance(ga, str):
                ga_t = ("REF", ga) if cx.gv.anchor(ga) is None else ga
            else:
                ref = (gent.get("raw") or {}).get("anchor_ref")
                ga_t = ("REF", ref) if ref else None
            if ga_t != ea:
                problems.append("role %s: expected unregistered reference %r, certificate "
                                "carries %r" % (key, ea, ga))
        elif ea is None:
            if ga is not None and not mc1:
                problems.append("role %s: no prescribed anchor derivable yet certificate "
                                "pins %r" % (key, ga))
        elif ga != ea:
            problems.append("role %s: anchor %r ≠ derived %r%s"
                            % (key, ga, ea,
                               "" if gent.get("declared_override") or ent["declared"]
                               else " (no machine-readable override record — AM(i) handling)"))
        if ent.get("reanchored") and not gent.get("declared_override"):
            # V0 "豁免仅凭证书记录": a re-anchor declaration ā carried by q is only
            # honoured when the certificate records it machine-readably; otherwise the
            # deviation from the prescribed anchor is AM(i) material, not an exemption.
            problems.append("role %s: q declares a re-anchor (ā) but the certificate "
                            "carries no machine-readable declared_override record" % key)
        ew, gw = ent["window"], gent.get("window")
        if ew is None:
            # atemporal role (p2 attribute metrics): no registered leg window —
            # nothing to hold the certificate's coordinate against.
            pass
        elif gw is None:
            if not mc1:
                problems.append("role %s: certificate window missing/unparseable" % key)
        elif cx.dec in ("ANSWER", "REFUSE", None):
            if not w_eq(gw, ew):
                problems.append("role %s: window %s ≠ derived %s"
                                % (key, w_str(gw), w_str(ew)))
        elif cx.dec == "REWRITE":
            if not w_subset(gw, ew):
                problems.append("role %s: REWRITE window %s ⊄ requested %s"
                                % (key, w_str(gw), w_str(ew)))
    # I2'(a) elastic arity: when β_v(m)↑ the metric's *arity* is not registered
    # in G_v (no row, or a row prescribing neither leg), so the verifier derives
    # the single role 'atom' by convention while an MC(i) certificate may
    # legitimately present the {num,den} spelling with explicit empty
    # assignments. For those certificates the role NAMES are not independently
    # checkable — but the window coordinate still is, and it is: every presented
    # role is held to the window the domain convention derives for its period.
    def _period_of(key):
        tail = str(key).split("#", 1)
        if len(tail) == 1:
            return 0
        try:
            return int(tail[1])
        except ValueError:      # a forged, non-numeric period suffix
            return -1

    elastic = mc1 and not exp["ratio"]
    extra = set(got) - set(exp["roles"])
    for key in sorted(extra, key=str):
        base = str(key).split("#", 1)[0]
        if elastic and base in ("numerator", "denominator", "atom", "atomic"):
            wins = [e["window"] for k, e in exp["roles"].items()
                    if _period_of(k) == _period_of(key)]
            gw = (got.get(key) or {}).get("window")
            if not wins:
                problems.append("certificate α carries role %s in a period the "
                                "derivation does not reach" % key)
            elif gw is None:
                problems.append("role %s: certificate window missing/unparseable" % key)
            elif not w_eq(gw, wins[0]):
                problems.append("role %s: window %s ≠ derived %s"
                                % (key, w_str(gw), w_str(wins[0])))
            continue
        problems.append("certificate α carries role %s absent from q's role set" % key)
    # dec=REWRITE mapping (C4 Def 4.10): ANSWER must not narrow; REWRITE must
    # narrow along SOME request coordinate — window (w* ⊊ w0), grain (g ≠ g0:
    # entity/time roll-up under a k/time-floor clause), or presentation (μ* ≠ id:
    # mask closure) — and must carry the cut trace.
    if cx.dec == "REWRITE":
        rw = cert.get("rewrite") or {}
        if not rw.get("cut_trace"):
            problems.append("dec=REWRITE without cut_trace (silent narrowing is the "
                            "disclosure-laundering surface, C5 Prop 5.12)")
        narrowed = any(
            got.get(k) and exp["roles"][k]["window"] and got[k].get("window")
            and not w_eq(got[k]["window"], exp["roles"][k]["window"])
            for k in exp["roles"])
        d = cert.get("disclosure") or {}
        g_req = q.get("requested_granularity") or q.get("requested_time_gran")
        grain_coarsened = bool(g_req) and d.get("granularity") not in (None, g_req)
        masked = bool(d.get("mask_closure"))
        if not (narrowed or grain_coarsened or masked):
            problems.append("dec=REWRITE but every coordinate equals the request "
                            "(no window narrowing, no grain coarsening, no mask "
                            "closure — mapping requires dec=ANSWER)")
    if problems:
        return ("FAIL", "; ".join(problems))
    tag = {"derived": "windows independently derived",
           "declared": "windows DECLARED (no independent derivation)",
           "declared-override": "windows DECLARED-OVERRIDE (question pins a "
                                "coordinate the convention does not produce)"}
    note = tag.get(exp.get("window_source"), "window provenance unrecorded")
    if elastic:
        note += "; arity NOT independently checked (β_v(m)↑, I2'(a) elastic role set)"
    return ("PASS", "α matches the independently re-derived α_{q,v} "
                    "(%d role(s), %d period(s); %s — %s)"
            % (len(exp["roles"]), exp["periods"], note,
               exp.get("window_source_detail") or ""))


def check_V1(cx):
    """Version pin resolution + diagonality ver(T) (C3 Def 3.5; C5 Def 5.1
    offdiag; Axiom 5.0 uniqueness)."""
    cert, q = cx.cert, cx.q
    pin = cert.get("graph_pin")
    # I2'(c) degenerate variant: ver(T)↑ certificate carries the probe assertion
    if not pin:
        if cx.dec == "REFUSE" and cx.reason == "out-of-validity" and \
                cx.witness.get("type") == "version-axis-undefined":
            gv = Gv(cx.con, q.get("domain"), None)
            kind, payload = parse_asof(q.get("declared_at") or q.get("as_of"))
            t = _asof_point(kind, payload)
            ver, mode = gv.ver_of(t)
            if mode == "trivial":
                return ("FAIL", "I2'(c) claim ver(T)↑ but the commit map is the trivial "
                                "single-version total map (ver(T) defined)")
            if mode == "unavailable":
                return ("FAIL", "commit map unavailable (multi-version, unparseable "
                                "committed_at): cannot verify ver(T)↑")
            if ver is not None:
                return ("FAIL", "I2'(c) claim ver(T)↑ but ver(T)=%r" % ver)
            return ("PASS", "ver(T)↑ verified on the version axis (T before t_1)")
        return ("FAIL", "graph_pin (ν) missing: certificate has no version coordinate "
                        "(version-swap surface, C5 Prop 5.12)")
    dom, ver = pin.get("domain"), pin.get("graph_version")
    if not dom or not ver:
        return ("FAIL", "graph_pin incomplete: domain=%r graph_version=%r" % (dom, ver))
    if q.get("domain") and dom != q.get("domain"):
        return ("FAIL", "graph_pin.domain %r ≠ q.domain %r" % (dom, q.get("domain")))
    vrows = cx.gv.version_rows()
    if vrows is None:
        return ("FAIL", "gov_semantic_graph_version table absent: ν unresolvable")
    hits = [r for r in vrows if r.get("version") == ver]
    if len(hits) != 1:
        return ("FAIL", "ν does not resolve to a unique typed-commit: version %r has %d "
                        "row(s) in gov_semantic_graph_version@%s" % (ver, len(hits), dom))
    row = hits[0]
    cid = pin.get("commit_id")
    if cid is not None and row.get("committed_at") is not None and \
            str(cid) != str(row.get("committed_at")):
        return ("FAIL", "commit_id %r ≠ registered committed_at %r" % (cid, row.get("committed_at")))
    # diagonality: T is the DECLARATION time when the question carries one
    # (pilot2 declared_at, the transaction-time coordinate ver() ranges over);
    # legacy questions declare only as_of, which then serves as T.
    kind, payload = parse_asof(q.get("declared_at") or q.get("as_of"))
    t = _asof_point(kind, payload)
    ver_t, mode = cx.gv.ver_of(t)
    if mode == "unavailable":
        return ("FAIL", "commit map unavailable (multi-version, unparseable committed_at): "
                        "diagonality unverifiable (fail-closed)")
    offdiag = pin.get("off_diagonal")
    if ver_t == ver:
        if offdiag:
            return ("FAIL", "off_diagonal marker present but ν.v = ver(T) = %r" % ver)
        return ("PASS", "ν resolves uniquely; diagonal read ν.v = ver(T) = %r (%s commit map)"
                % (ver, mode))
    # off-diagonal: explicit commitment marker required (GOLD-1 mirror)
    if not offdiag:
        return ("FAIL", "ν.v=%r ≠ ver(T)=%r without the explicit off_diagonal commitment "
                        "marker (zero-trace off-diagonal certificate REJECT)" % (ver, ver_t))
    if not (isinstance(offdiag, dict) and offdiag.get("pinned") == ver
            and str(offdiag.get("ver_as_of")) == str(ver_t)):
        return ("FAIL", "off_diagonal marker %r inconsistent with (pinned=%r, ver_as_of=%r)"
                % (offdiag, ver, ver_t))
    return ("PASS", "off-diagonal read explicitly committed: pinned %r, ver(T)=%r" % (ver, ver_t))


def _asof_point(kind, payload):
    """Representative day of the as-of declaration for ver(T) (end of period;
    only discriminates on multi-version commit maps)."""
    if kind == "day":
        return payload
    if kind == "month":
        return month_next(*payload) - DAY
    if kind == "year":
        return dt.date(payload, 12, 31)
    return None


def check_V2(cx):
    """Anchor existence + window well-formedness/type compatibility."""
    problems = []
    anchors_table = cx.gv.anchors()
    for key, ent in cx.alpha.items():
        a = ent.get("anchor")
        w = ent.get("window")
        raw = ent.get("raw") or {}
        if isinstance(a, tuple) and a[0] == "REF":
            if anchors_table is None:
                problems.append("role %s: REF claim unverifiable, anchor table absent" % key)
            elif cx.gv.anchor(a[1]) is not None:
                problems.append("role %s: claimed-unregistered anchor %r actually resolves "
                                "in A_v" % (key, a[1]))
            continue
        if a is None:
            # I2'(a): explicit empty assignment must record role + metric id
            if not (raw.get("empty_assignment") and raw.get("metric")):
                problems.append("role %s: empty assignment without the I2'(a) record "
                                "(role+metric id)" % key)
            continue
        if anchors_table is None:
            problems.append("role %s: gov_valid_time_anchor absent, %r unverifiable" % (key, a))
            continue
        arow = cx.gv.anchor(a)
        if arow is None:
            problems.append("role %s: anchor %r ∉ gov_valid_time_anchor@%s"
                            % (key, a, cx.version))
            continue
        if w is None:
            if raw.get("window") is not None:
                problems.append("role %s: window %r not well-typed in 𝒲" % (key, raw.get("window")))
            elif not (cx.dec == "REFUSE" and cx.reason in ("out-of-validity", "missing-caliber")):
                problems.append("role %s: window missing outside the I2' degenerate variants" % key)
            continue
        if arow.get("anchor_type") == "scd_type2":
            days = [(lo, hi) for lo, hi in w if lo is not None and hi is not None]
            if not (len(w) == len(days) and all((hi - lo) == DAY for lo, hi in days)):
                problems.append("role %s: SCD-2 anchor requires the D7 point window {d}, got %s"
                                % (key, w_str(w)))
    if problems:
        return ("FAIL", "; ".join(problems))
    return ("PASS", "%d α entr(ies) exist@%s with well-typed windows"
            % (len(cx.alpha), cx.version))


def check_V3(cx):
    """Binding rule replay under the three-value consistency table."""
    if cx.dec == "REFUSE" and cx.reason in ("missing-caliber", "out-of-validity",
                                            "disclosure-blocked"):
        return ("SKIP", "V3 exempt for REFUSE(%s); guard negation replays in V6b(0)" % cx.reason)
    bid = cx.binding.get("binding_id")
    brow = None
    if bid:
        brow = cx.gv.binding_by_id(bid)
        if brow is None:
            return ("FAIL", "binding_id %r ∉ gov_temporal_binding@%s" % (bid, cx.version))
        m, bm = cx.q.get("metric"), base_metric(cx.q.get("metric"))
        parts = [base_metric(x) for x in (brow.get("metric") or "").split("|")]
        if not (brow.get("metric") == m or bm in parts):
            return ("FAIL", "binding row %r governs metric %r, not q.metric %r"
                    % (bid, brow.get("metric"), m))
        # C3 Def 3.8 rules constrain the two legs of a ratio binding. An atomic
        # metric has no legs to align: citing its registry row is provenance, and
        # the svw replay is vacuous. (Registry-shaped seeds also carry prose in
        # the rule column, which is not a rule token by design.)
        if not cx.expected.get("ratio"):
            return ("PASS", "atomic metric: cited registry row %r governs the metric; "
                            "svw replay vacuous (no two legs)" % bid)
        if cx.binding.get("rule") and cx.binding["rule"] != registered_rule(brow):
            return ("FAIL", "certificate rule %r ≠ registered rule %r"
                    % (cx.binding.get("rule"), registered_rule(brow)))
    else:
        brow = cx.expected.get("binding_row")
        if brow is None:
            return ("SKIP", "β_v undefined for metric (atomic / no binding row): "
                            "V3 vacuously passes")
        return ("FAIL", "β_v(m) is defined (binding %r) but the certificate cites no "
                        "binding_id" % brow.get("binding_id"))
    mode, err = resolve_adm_mode(cx.gv, brow, cx.binding)
    if err:
        return ("FAIL", err)
    if registered_rule(brow) != "same_valid_time_window":
        return ("FAIL", "unknown binding rule %r: replay undefined" % registered_rule(brow))
    passed, clause, detail = replay_svw(cx.gv, cx.guard_roles(), brow, mode)
    if cx.dec in ("ANSWER", "REWRITE"):
        if passed is True:
            return ("PASS", "rule replay passes (%s)" % detail)
        return ("FAIL", "dec=%s but rule replay does not pass: %s" % (cx.dec, detail))
    if cx.dec == "REFUSE" and cx.reason == "anchor-mismatch":
        if passed is True:
            return ("FAIL", "REFUSE(AM) but rule replay passes on α")
        if passed is None:
            return ("FAIL", "REFUSE(AM) replay undecidable: %s" % detail)
        wc = cx.witness.get("clause")
        if wc and wc != clause:
            return ("FAIL", "replayed failing clause %s ≠ witness clause %s" % (clause, wc))
        return ("PASS", "rule replay fails at clause %s, consistent with witness (%s)"
                % (clause, detail))
    # dec missing/invalid: an I4/δ defect — V5 fails it; the consistency table
    # is inapplicable here.
    return ("SKIP", "δ.decision %r: V3 consistency table inapplicable (I4 defect "
                    "surfaces in V5)" % (cx.dec,))


def check_V4(cx):
    """Routing replay: every cited edge exists@v and matches field-by-field;
    I3 adjacency; ratio-type answers must cite a recomputable route."""
    problems = []
    prev_dst = None
    cx._v4_nodes = {}
    routings = cx.gv.routings()
    for i, e in enumerate(cx.routing):
        if not isinstance(e, dict):
            problems.append("routing[%d] not an object" % i)
            continue
        key = e.get("caliber_key")
        if routings is None:
            problems.append("gov_caliber_routing absent: %r unverifiable" % key)
            continue
        row = cx.gv.routing(key)
        if row is None:
            problems.append("routing edge %r ∉ gov_caliber_routing@%s" % (key, cx.version))
            continue
        jk_cert = e.get("join_keys")
        jk_gv = row.get("join_keys")
        if isinstance(jk_gv, str):
            try:
                jk_gv = json.loads(jk_gv)
            except ValueError:
                jk_gv = [jk_gv]
        if jk_cert is not None and list(jk_cert) != list(jk_gv or []):
            problems.append("edge %r join_keys %r ≠ registered %r" % (key, jk_cert, jk_gv))
        if e.get("attribution_alignment") is not None and \
                e.get("attribution_alignment") != row.get("attribution_alignment"):
            problems.append("edge %r attribution_alignment %r ≠ registered %r"
                            % (key, e.get("attribution_alignment"),
                               row.get("attribution_alignment")))
        for fld in ("src_caliber", "dst_caliber", "via_table", "metric", "leg",
                    "hop_seq", "src_node", "dst_node"):
            if e.get(fld) is not None and e.get(fld) != row.get(fld):
                problems.append("edge %r %s %r ≠ registered %r"
                                % (key, fld, e.get(fld), row.get(fld)))
        if row.get("src_node") is not None:
            # p2 hop rows: I3 adjacency is per-leg node reachability — every
            # hop's src node must be the leg's base node or the dst of an
            # earlier hop of the same leg (hop trees rooted at the base node).
            leg = row.get("leg")
            legroots = cx._v4_nodes.setdefault(leg, set())
            if not legroots:
                legroots.add(row.get("src_node"))
            if row.get("src_node") not in legroots:
                problems.append("I3 adjacency broken at %r: src node %r not reached "
                                "by leg %r's earlier hops" % (key, row.get("src_node"), leg))
            legroots.add(row.get("dst_node"))
        else:
            if prev_dst is not None and row.get("src_caliber") != prev_dst:
                problems.append("I3 adjacency broken at %r: src %r ≠ previous dst %r"
                                % (key, row.get("src_caliber"), prev_dst))
            prev_dst = row.get("dst_caliber")
    if cx.dec in ("ANSWER", "REWRITE") and cx.expected.get("ratio"):
        if not cx.routing:
            problems.append("ratio-type metric answered without a caliber routing path ρ "
                            "(caliber-blind substitution surface, C5 Prop 5.12)")
        else:
            for e in cx.routing:
                row = cx.gv.routing(e.get("caliber_key")) if isinstance(e, dict) else None
                if row and row.get("dst_caliber") == "none":
                    problems.append("cited route %r is reference-only (dst_caliber='none'): "
                                    "not recomputable" % e.get("caliber_key"))
            # R_v is a metric→routing map (C3 Def 3.4). Where the seed spells that
            # attribution out, the cited head edge must be the metric's own route —
            # citing some other metric's registered route is exactly the caliber
            # substitution V4 exists to close.
            head = cx.routing[0] if isinstance(cx.routing[0], dict) else {}
            hrow = cx.gv.routing(head.get("caliber_key")) or {}
            if "metric" in hrow and hrow.get("metric"):
                if base_metric(hrow["metric"]) != base_metric(cx.q.get("metric")):
                    problems.append("cited route %r is registered for metric %r, not "
                                    "q.metric %r (R_v attribution mismatch)"
                                    % (head.get("caliber_key"), hrow.get("metric"),
                                       cx.q.get("metric")))
    if problems:
        return ("FAIL", "; ".join(problems))
    return ("PASS", "ρ (%d edge(s)) replayed against gov_caliber_routing@%s"
            % (len(cx.routing), cx.version))


def _p2_effective_metric(cx):
    m = cx.q.get("metric")
    if m:
        return m
    return cx.gv.aliases_map().get(cx.q.get("metric_alias"))


def _p2_touched_policies(cx, pols):
    """Effective policy set Π replay for the p2 schema (C4 Def 4.5 applicability
    computed from G_v + q's presentation coordinates, independent of the
    certificate): mask policies touch when their protected columns are surfaced
    (attribute value reads; raw-row rosters); k policies touch entity-grain
    presentations of their node (entity-axis reports, rosters); time-floor
    policies touch time-axis reports presenting a finer-than-floor granule."""
    m = _p2_effective_metric(cx)
    mrow = cx.gv.metric_row(m) if m else None
    kind = (mrow or {}).get("kind")
    ent = (mrow or {}).get("entity_node")
    raw_rows = (kind == "roster" or cx.q.get("presentation") == "raw_rows")
    val_cols = set()
    val_node = None
    for r in cx.gv.measures(m or ""):
        if str(r.get("measure") or "").startswith("value:"):
            val_cols.add(str(r["measure"]).split(":", 1)[1])
            val_node = r.get("node_id")
    out = []
    for p in pols:
        pk = p.get("kind")
        if pk in ("mask", "present_only"):
            if kind == "attribute" and p.get("node_id") == val_node and \
                    val_cols & set(p.get("cols") or []):
                out.append(p)
            elif raw_rows and pk == "mask" and p.get("node_id") == ent:
                # raw-row roster presentations touch the node's mask policies
                # (protected raw columns are surfaced by construction);
                # present_only rows govern single-attribute presentations and
                # follow the registered blocking set (build adjudication).
                out.append(p)
        elif pk == "k_threshold":
            if p.get("node_id") == ent and (
                    kind == "roster" or
                    (kind == "report" and (mrow or {}).get("report_axis") == "entity")):
                out.append(p)
        elif pk == "time_floor":
            if kind == "report" and (mrow or {}).get("report_axis") == "time" \
                    and cx.q.get("requested_time_gran"):
                out.append(p)
    return out


def _p2_level_expr(cx, level, aliases, ent):
    """Grouping expression of a lattice level from gov_granularity_edge
    (band CASE / group columns / derived decade / entity key)."""
    if level == "all":
        return "'all'"
    edges = [e for e in cx.gv.gran_edges() if e.get("axis") == "entity"
             and e.get("to_level") == level]
    if not edges:
        key = (cx.gv.node_row(ent) or {}).get("entity_key")
        return '%s."%s"' % (aliases[ent], key)
    e = edges[0]
    node = e.get("node_id") or ent
    a = aliases.get(node)
    if a is None:
        return None
    parts = []
    if e.get("band_col"):
        bs = e["band_bounds"]
        case = "CASE"
        for i in range(len(bs) - 1, 0, -1):
            lab = "[%s,inf)" % bs[i] if i == len(bs) - 1 else "[%s,%s)" % (bs[i], bs[i + 1])
            case += ' WHEN %s."%s" >= %s THEN \'%s\'' % (a, e["band_col"], bs[i], lab)
        case += " ELSE '[%s,%s)' END" % (bs[0], bs[1])
        parts.append(case)
    for c in (e.get("group_cols") or []):
        parts.append('%s."%s"' % (a, c))
    for dv in (e.get("derived") or []):
        if dv.get("fn") == "decade":
            parts.append('substr(CAST(%s."%s" AS VARCHAR),1,3) || \'0s\'' % (a, dv["col"]))
    if not parts:
        key = (cx.gv.node_row(node) or {}).get("entity_key")
        parts = ['%s."%s"' % (a, key)]
    return " || '/' || ".join(parts) if len(parts) > 1 else parts[0]


def _p2_drop_keys(cx, chain_all, upto):
    drop = set()
    if upto not in chain_all:
        return drop
    idx = chain_all.index(upto)
    for lvl in chain_all[:idx]:
        for e in cx.gv.gran_edges():
            if e.get("to_level") == lvl:
                for c in (e.get("group_cols") or []):
                    for node in (cx.gv.rows("gov_semantic_node") or []):
                        for sk, col in (node.get("scope_keys") or {}).items():
                            if col == c:
                                drop.add(sk)
    return drop


def _p2_min_cell(cx, level, chain_all):
    """Independent SUPPMIN_π(level) re-computation from (G_v, D): grouped
    distinct-entity counts of the metric's atom leg at `level`, over the
    derived role window and q's scope (minus lattice-absorbed keys).
    Returns (min_cell|None, err)."""
    m = _p2_effective_metric(cx)
    mrow = cx.gv.metric_row(m) or {}
    ent = mrow.get("entity_node")
    measures = cx.gv.measures(m, "atom")
    if not measures or ent is None:
        return (None, "metric %r has no atom measures/entity node" % m)
    base = measures[0]["node_id"]
    aliases = {base: "t0"}
    joins = []
    order = {"atom": 0, "scope": 1, "entity": 2}
    hops = sorted(cx.gv.metric_routings(m, legs=("atom", "scope", "entity")),
                  key=lambda r: (order.get(r.get("leg"), 9),
                                 r.get("hop_seq") or 0, r.get("caliber_key") or ""))
    ai = 0
    for h in hops:
        src, dst = h.get("src_node"), h.get("dst_node")
        if not h.get("join_keys") or src not in aliases or \
                (dst in aliases and dst != src):
            continue
        ai += 1
        a = "t%d" % ai
        on = " AND ".join('%s."%s" = %s."%s"' % (aliases[src], sc, a, dc)
                          for sc, dc in h["join_keys"])
        joins.append((a, cx.gv.node_table(dst), on))
        if dst != src:
            aliases[dst] = a
    if ent not in aliases:
        return (None, "entity node %r not reachable via registered hops" % ent)
    where = []
    for r in measures:
        for p in (r.get("preds") or []):
            node = p.get("node") or r["node_id"]
            a = aliases.get(node)
            if a is None:
                continue
            col, op, v = p.get("col"), p.get("op"), p.get("value")
            if op == "in":
                where.append('%s."%s" IN (%s)' % (a, col, ", ".join(
                    ("'%s'" % str(x).replace("'", "''")) if isinstance(x, str)
                    else str(x) for x in v)))
            elif op == "is_null":
                where.append('%s."%s" IS NULL' % (a, col))
            elif op == "not_null":
                where.append('%s."%s" IS NOT NULL' % (a, col))
            elif op == ">col":
                where.append('%s."%s" > %s."%s"' % (a, col, a, v))
            elif op == "=col":
                where.append('%s."%s" = %s."%s"' % (a, col, a, v))
            else:
                lit = ("'%s'" % str(v).replace("'", "''")) if isinstance(v, str) else str(v)
                where.append('%s."%s" %s %s' % (a, col, op, lit))
    drop = _p2_drop_keys(cx, chain_all, level) if level != chain_all[0] else set()
    for k, v in (cx.q.get("scope") or {}).items():
        if k in drop:
            continue
        hit = None
        for node, a in aliases.items():
            sk = (cx.gv.node_row(node) or {}).get("scope_keys") or {}
            if k in sk:
                hit = (a, sk[k])
                break
        if hit is None:
            return (None, "scope key %r unresolved on registered hops" % k)
        lit = ("'%s'" % str(v).replace("'", "''")) if isinstance(v, str) else str(v)
        where.append('%s."%s" = %s' % (hit[0], hit[1], lit))
    # role window over the atom anchor (derived coordinates, C3 Def 3.2)
    ent_w = (cx.expected.get("roles") or {}).get("atom") or {}
    win = ent_w.get("window")
    brow = cx.expected.get("binding_row") or {}
    aid = brow.get("atom_anchor")
    arow = cx.gv.anchor(aid) if aid else None
    if arow is not None and win is not None:
        col = arow.get("effective_date")
        gran = arow.get("granularity") or "day"
        a = aliases.get(arow.get("node_id"))
        if a is None:
            return (None, "anchor node %r not reachable" % arow.get("node_id"))
        lo, hi = win[0][0], win[-1][1]
        if gran == "academic_year_token":
            tok = "%d-%d" % (lo.year, lo.year + 1)
            where.append('CAST(%s."%s" AS VARCHAR) = \'%s\'' % (a, col, tok))
        elif gran.startswith("month_token"):
            toks = []
            d = dt.date(lo.year, lo.month, 1)
            while d < hi:
                toks.append("%04d%02d" % (d.year, d.month) if gran == "month_token_yyyymm"
                            else "%04d-%02d" % (d.year, d.month))
                d = month_next(d.year, d.month)
            where.append('CAST(%s."%s" AS VARCHAR) IN (%s)'
                         % (a, col, ", ".join("'%s'" % t for t in toks)))
        else:
            e = 'substr(CAST(%s."%s" AS VARCHAR),1,10)' % (a, col)
            if lo is not None:
                where.append("%s >= '%s'" % (e, lo.isoformat()))
            if hi is not None:
                where.append("%s < '%s'" % (e, hi.isoformat()))
    expr = _p2_level_expr(cx, level, aliases, ent)
    if expr is None:
        return (None, "level %r grouping expression underivable" % level)
    ekey = (cx.gv.node_row(ent) or {}).get("entity_key")
    sql = 'SELECT %s AS cell, COUNT(DISTINCT %s."%s") AS n FROM %s t0' % (
        expr, aliases[ent], ekey, cx.gv.qualify(cx.gv.node_table(base)))
    for a, tab, on in joins:
        sql += ' INNER JOIN %s %s ON %s' % (cx.gv.qualify(tab), a, on)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY 1"
    try:
        rows = cx.gv.con.execute("SELECT MIN(n) FROM (%s)" % sql).fetchone()
    except Exception as e:  # noqa: BLE001
        return (None, "cell re-count failed: %s" % e)
    return (rows[0], None)


_MASK_SIGNATURES = {
    "year_only": lambda col: [r"substr\s*\(\s*CAST\s*\(\s*(?:\w+\.)?\"?%s\"?\s+AS\s+VARCHAR\s*\)\s*,\s*1\s*,\s*4\s*\)" % re.escape(col)],
    "year_month": lambda col: [r"substr\s*\(\s*CAST\s*\(\s*(?:\w+\.)?\"?%s\"?\s+AS\s+VARCHAR\s*\)\s*,\s*1\s*,\s*7\s*\)" % re.escape(col)],
    "generalize_last_component": lambda col: [r"regexp_extract\s*\(\s*(?:\w+\.)?\"?%s\"?\s*,\s*'\(\[\^,\]\+\)\$'" % re.escape(col)],
}


def _check_V5_p2(cx, d, pols):
    """Complete C5 disclosure replay over the p2 policy schema (mask /
    k_threshold+lattice / time_floor / present_only): Π re-derivation, then the
    literal clause replay per effective policy — the k clause re-computes
    SUPPMIN at every lattice level from D (the certified grain must be the
    ≺-minimal legal level), the mask clause re-checks μ* and the masking
    transform on the emitted query, the time-floor clause re-checks the
    granule coordinate."""
    problems = []
    dec = d.get("decision")
    if d.get("ungoverned_disclosure"):
        problems.append("domain carries %d disclosure policies@%s yet the certificate "
                        "claims ungoverned-disclosure" % (len(pols), cx.version))
    ch = cx.cert.get("ctx_hash", d.get("ctx_hash"))
    if cx.audit_ctx is None:
        if not same_ctx_hash(ch, EMPTY_CTX_HASH):
            problems.append("governed domain: auditor context required to check ctx_hash")
    elif not same_ctx_hash(ch, canonical_ctx_hash(cx.audit_ctx)):
        problems.append("hash(ctx) ≠ δ.h_ctx")

    touched = _p2_touched_policies(cx, pols)
    exp_ids = sorted(p.get("policy_id") for p in touched)
    got_ids = sorted(d.get("policy_ids") or [])
    if exp_ids != got_ids:
        problems.append("effective policy set mismatch: expected %r, certificate Π=%r"
                        % (exp_ids, got_ids))
    if dec == "REFUSE":
        # DB clause replay happens on the witness (V6b: blocking policies,
        # SUPPMIN transcripts, U_min=∅); V5 pins Π + the annotations above.
        if problems:
            return ("FAIL", "; ".join(problems))
        return ("PASS", "governed disclosure (p2): Π=%r replayed; REFUSE clause "
                        "replay delegated to the witness (V6b)" % got_ids)

    sql_text = cx.sql or ""
    for p in touched:
        pid, pk = p.get("policy_id"), p.get("kind")
        if pk in ("mask", "present_only"):
            mu = d.get("mask_closure") or []
            mclasses = {e.get("mask") for e in mu if isinstance(e, dict)} | \
                       {e for e in mu if isinstance(e, str)}
            if p.get("mask_class") not in mclasses:
                problems.append("mask clause: μ* %r does not cover policy %r mask_class %r"
                                % (sorted(mclasses), pid, p.get("mask_class")))
                continue
            if dec != "REWRITE":
                problems.append("mask policy %r touched but dec=%s (presentation "
                                "downgrade requires REWRITE)" % (pid, dec))
            sigs = _MASK_SIGNATURES.get(p.get("mask_class"))
            cols = [c for c in (p.get("cols") or []) if c in sql_text]
            if sigs and cols:
                for c in cols:
                    if not any(re.search(s, sql_text, re.I) for s in sigs(c)):
                        problems.append("mask clause: query surfaces %r without the "
                                        "%r masking transform" % (c, p.get("mask_class")))
        elif pk == "k_threshold":
            chain_all = p.get("lattice_levels") or []
            req = cx.q.get("requested_granularity")
            g = d.get("granularity")
            if req not in chain_all:
                problems.append("requested granularity %r outside the registered "
                                "lattice %r" % (req, chain_all))
                continue
            chain = chain_all[chain_all.index(req):]
            if g not in chain:
                problems.append("certified grain %r not in the ↑%r lattice chain %r"
                                % (g, req, chain))
                continue
            k = p.get("k")
            for lvl in chain:
                if lvl == g:
                    break
                mn, err = _p2_min_cell(cx, lvl, chain_all)
                if err:
                    problems.append("SUPPMIN(%s) replay failed: %s" % (lvl, err))
                elif mn is not None and int(mn) >= int(k):
                    problems.append("grain minimality violated: finer level %r is "
                                    "already legal (min cell %s ≥ k=%s) yet the "
                                    "certificate coarsened to %r" % (lvl, mn, k, g))
            if g == "all" and p.get("k_exempt_top"):
                pass  # top-level exemption is registered in G_v
            else:
                mn, err = _p2_min_cell(cx, g, chain_all)
                if err:
                    problems.append("SUPPMIN(%s) replay failed: %s" % (g, err))
                elif mn is None or int(mn) < int(k):
                    problems.append("k clause fails at the certified grain %r: min "
                                    "cell %s < k=%s" % (g, mn, k))
            if g != req and dec != "REWRITE":
                problems.append("grain coarsened (%r→%r) but dec=%s" % (req, g, dec))
            if g == req and dec == "REWRITE" and not (d.get("mask_closure")):
                # window narrowing may still justify REWRITE; V0 already holds
                # the mapping — nothing to add here.
                pass
        elif pk == "time_floor":
            req = cx.q.get("requested_time_gran")
            floor = p.get("time_floor_gran")
            g = d.get("granularity")
            if req and floor and req != floor:
                if dec != "REWRITE":
                    problems.append("time floor %r touched on a %r request but dec=%s"
                                    % (floor, req, dec))
                if g != floor:
                    problems.append("time floor clause: δ.g=%r ≠ registered floor %r"
                                    % (g, floor))
    if problems:
        return ("FAIL", "; ".join(problems))
    return ("PASS", "governed disclosure (p2) replayed: Π=%r; k/lattice, mask and "
                    "time-floor clauses re-established from (G_v, D)" % got_ids)


def check_V5(cx):
    """Disclosure replay: governed domains replay the literal granularity and
    mask clauses per effective policy; ungoverned domains (D5) must carry the
    ungoverned-disclosure annotation with Π=∅ and no REWRITE/REFUSE(DB)."""
    d = cx.disclosure
    if not d:
        return ("FAIL", "disclosure section (δ) missing (disclosure-laundering surface, "
                        "C5 Prop 5.12)")
    dec = d.get("decision")
    if dec not in ("ANSWER", "REWRITE", "REFUSE"):
        return ("FAIL", "δ.decision %r invalid" % (dec,))
    # I4 decision-output matching
    if dec in ("ANSWER", "REWRITE") and not (isinstance(cx.sql, str) and cx.sql.strip()):
        return ("FAIL", "I4: dec=%s but no query text out" % dec)
    if dec == "REFUSE" and not cx.refusal:
        return ("FAIL", "I4: dec=REFUSE but no refusal section")
    if dec == "REFUSE" and cx.reason not in REASONS:
        return ("FAIL", "refusal.reason %r not in {missing-caliber, anchor-mismatch, "
                        "out-of-validity, disclosure-blocked}" % (cx.reason,))
    pols = cx.gv.policies()
    governed = bool(pols)
    pi = d.get("policy_ids")
    if not governed:
        # D5 absence rule
        problems = []
        if pi:
            problems.append("Π=%r must be empty in an ungoverned-disclosure domain" % (pi,))
        # D5 makes the *disclosure gate* unconstrained — it does not forbid
        # REWRITE as such. C4's dec mapping defines dec=REWRITE by narrowing of
        # the request coordinates (g≠g₀ ∨ some leg w*≠w₀, hull-edge cuts
        # included ∨ cross-boundary component narrowing) — a binding-layer
        # phenomenon that occurs in ungoverned domains too. Only a
        # disclosure-blocked refusal is impossible without policies.
        if dec == "REFUSE" and cx.reason == "disclosure-blocked":
            problems.append("dec=REFUSE(DB) impossible: absent policies mean "
                            "unconstrained disclosure (D5)")
        if not d.get("ungoverned_disclosure"):
            problems.append("ungoverned-disclosure annotation missing (absence ≠ checked; "
                            "D5: 缺标即 REJECT)")
        ch = cx.cert.get("ctx_hash", d.get("ctx_hash"))
        if not same_ctx_hash(ch, EMPTY_CTX_HASH):
            problems.append("ungoverned domain must carry the empty context hash, got %r" % ch)
        if problems:
            return ("FAIL", "; ".join(problems))
        return ("PASS", "ungoverned-disclosure domain: Π=∅, dec=%s, annotation present" % dec)
    if cx.gv.is_p2:
        return _check_V5_p2(cx, d, pols)
    # governed domain (aibuy/email seeds)
    problems = []
    if d.get("ungoverned_disclosure"):
        problems.append("domain carries %d disclosure policies@%s yet the certificate "
                        "claims ungoverned-disclosure" % (len(pols), cx.version))
    ch = cx.cert.get("ctx_hash", d.get("ctx_hash"))
    if cx.audit_ctx is None:
        if not same_ctx_hash(ch, EMPTY_CTX_HASH):
            problems.append("governed domain: auditor context required to check ctx_hash")
    elif not same_ctx_hash(ch, canonical_ctx_hash(cx.audit_ctx)):
        problems.append("hash(ctx) ≠ δ.h_ctx")
    # touched policies: applied tables/columns vs what the artifact reads
    read_text = " ".join(filter(None, [cx.sql or ""] +
                                [p.get("sql", "") for p in cx.probes if isinstance(p, dict)]))
    touched = []
    read_tabs = {x.lower() for x in sql_tables(read_text)}
    for p in pols:
        tabs = p.get("applied_tables") or []
        cols = p.get("applied_columns") or []
        if isinstance(tabs, str):
            tabs = [tabs]
        if isinstance(cols, str):
            cols = [cols]
        # touched(g) is C4 Def 4.5's per-policy applicability: the artifact must
        # read a table the policy governs AND surface one of the protected
        # attributes it governs (C4: S_raw(cl(g)) ∩ P̄_π ≠ ∅). A column-name-only
        # match across unrelated tables is not applicability — aggregating a
        # governed table without projecting any protected column touches nothing.
        tab_hit = any(str(t).split(".")[-1].lower() in read_tabs for t in tabs)
        col_hit = any(c in read_text for c in cols) if cols else True
        hit = (tab_hit and col_hit) if tabs else col_hit
        if hit:
            touched.append(p)
    exp_ids = sorted(p.get("policy_id") for p in touched)
    got_ids = sorted(pi or [])
    if exp_ids != got_ids:
        problems.append("effective policy set mismatch: expected %r, certificate Π=%r"
                        % (exp_ids, got_ids))
    for p in touched:
        pid = p.get("policy_id")
        if p.get("min_grain") is not None:
            g = d.get("granularity")
            if g is None:
                problems.append("policy %r requires the granularity clause but δ.g is absent"
                                % pid)
            elif g != p.get("min_grain"):
                # without a machine-readable coarsening lattice Γ_v the literal
                # replay accepts only γ_π itself; a declared coarser grain must be
                # provided by G_v to be accepted (fail-closed)
                problems.append("granularity clause γ_π ⪯ g unverifiable: δ.g=%r vs "
                                "min_grain=%r and no Γ_v lattice declared" % (g, p.get("min_grain")))
        if p.get("mask_class"):
            mu = d.get("mask_closure") or []
            if p.get("mask_class") not in mu:
                problems.append("mask clause: μ* %r does not cover policy %r mask_class %r"
                                % (mu, pid, p.get("mask_class")))
    if problems:
        return ("FAIL", "; ".join(problems))
    return ("PASS", "governed disclosure replayed: Π=%r, clauses hold" % got_ids)


def check_V6a(cx):
    """Answer syntactic containment: touched tables ⊆ certified closure;
    time-predicate denotations ⊆ certified windows; ratio recomputed from
    separately windowed aggregates (no sum(rate))."""
    if cx.dec not in ("ANSWER", "REWRITE"):
        return ("SKIP", "V6a applies to answer certificates only")
    s = cx.sql
    if not isinstance(s, str) or not s.strip():
        return ("FAIL", "answer certificate without query text (I4)")
    if _FORBIDDEN_SQL.search(s):
        return ("FAIL", "answer SQL contains a non-SELECT statement keyword")
    if _AGG_RATE_RE.search(s):
        return ("FAIL", "ratio structure violated: aggregate over a rate/share column "
                        "(sum(rate) form; C3 note 3.13 ratio-of-sums)")
    allowed = cx.allowed_tables()
    if not allowed:
        return ("FAIL", "no certified objects derivable from α/ρ to contain the SQL")
    alpha_objs = cx.alpha_objects()
    pub_objs = cx.publication_objects(alpha_objs)
    # window sets by table: role windows whose anchor closure contains the table
    table_windows = {}
    for key, ent in cx.alpha.items():
        a = ent.get("anchor")
        if not isinstance(a, str):
            continue
        arow = cx.gv.anchor(a)
        if not arow:
            continue
        clo = {t.lower() for t in cx.gv.inherit_closure(arow.get("semantic_object") or "")}
        snap = (str(arow["snapshot_table"]).split(".")[-1].lower()
                if arow.get("snapshot_table") else None)
        if snap:
            clo.add(snap)
        clo |= cx.publication_objects(clo) & pub_objs
        eff_col = arow.get("effective_date") or arow.get("valid_from_col")
        eff = (eff_col or "dt").lower()
        scd2 = arow.get("anchor_type") == "scd_type2"
        for t in clo:
            # C3 Def 3.3 snapshot anchor: when the anchor pins a whole snapshot
            # table and carries no effective-date column, the temporal restriction
            # is realised by SELECTING that table — an unrestricted read of it
            # denotes exactly the anchor's validity, so there is no predicate to
            # contain. Mark such (table, role) pairs exempt rather than demanding
            # a WHERE clause that cannot exist.
            exempt = bool(snap and t == snap and not eff_col)
            table_windows.setdefault(t, []).append(
                {"win": ent.get("window"), "eff": eff, "key": key, "exempt": exempt,
                 "scd2": scd2, "vf": (arow.get("valid_from_col") or "").lower(),
                 "vt": (arow.get("valid_to_col") or "").lower()})
    problems = []
    full_ctes = cte_names(s) | subquery_aliases(s)
    for block in split_select_blocks(s):
        tabs = sql_tables(block, full_ctes)
        if not tabs:
            continue
        atoms = sql_date_atoms(block)
        for t in tabs:
            if t not in allowed:
                problems.append("table %r outside the certified closure (α objects ∪ "
                                "inheritance ∪ 发布节点 ∪ 维度 ∪ ρ via)" % t)
                continue
            ents = table_windows.get(t, [])
            if not ents:
                continue  # certified but not anchor-restricted (dimension join)
            # A multi-period (delta) query reads the same object once per period;
            # the block must lie inside SOME certified role window for that table
            # (C3 Cor 3.17′: guards are evaluated per period, never across).
            if any(e["exempt"] or e["win"] is None for e in ents):
                continue
            fails = []
            ok = False
            for e in ents:
                if e["scd2"]:
                    good, why = scd2_point_predicate(atoms, e["vf"], e["vt"], e["win"])
                    if good:
                        ok = True
                        break
                    fails.append("block on %r: SCD-2 in-effect predicate not replayed "
                                 "(%s; role %s)" % (t, why, e["key"]))
                    continue
                den = atoms_denotation(atoms, e["eff"])
                if w_subset(den, e["win"]):
                    ok = True
                    break
                fails.append("block on %r: time predicate denotation %s ⊄ certified "
                             "window %s (role %s)"
                             % (t, w_str(den), w_str(e["win"]), e["key"]))
            if not ok:
                problems.extend(fails)
    if problems:
        return ("FAIL", "; ".join(sorted(set(problems))))
    return ("PASS", "SQL touches only certified objects; every time-predicate denotation "
                    "lies inside its certified window; ratio form legal")


def _replay_neg_oov(cx):
    ok, detail = replay_oov(cx.gv, cx.guard_roles())
    if ok is None:
        return (None, detail)
    return (not ok, detail)


# Witness forms that establish OOV through a disjunct other than coverage
# vacuity: an unparseable as-of (ω_r(T)=↑, replayed from the raw string) and an
# undefined version axis (replayed by V1). Neither has a pair-level reading.
_OOV_NON_COVERAGE_WITNESS = ("unparseable-asof", "asof-unparseable",
                             "version-axis-undefined")


def _replay_pos_oov(cx):
    """The OOV guard the certificate *claims*, replayed at the level the
    semantics adjudicates it (C3 Def 3.14 coverage disjunct).

    (R5-M1, 2026-08-10) The OOV witness is a single-anchor triple (a, W_T, π_V),
    and replaying it alone only re-establishes that ONE leg is vacuous.  Where
    β_v's rule pairs two legs the coverage disjunct is pair-level: OOV holds
    only when EVERY paired role is empty, and a MIXED pair is clause (iv)'s
    audit jurisdiction.  Without this call an entirely HONEST single-leg vacuum
    witness certifies ⊥_OOV on a mixed pair whose denotation is ⊥_AM(iv) — the
    reason-class substitution V6b(0) exists to stop, arriving through the one
    class V6b(0) never ran for.  Returns (True|False|None, detail)."""
    return replay_oov(cx.gv, cx.guard_roles())


def _replay_neg_am(cx):
    # D8 (C3 Def 3.7 boundary adjudication): a declared-but-unregistered anchor
    # reference is a first-order clause-(i) violation — AM(i) by construction —
    # for atomic and ratio metrics alike (β_v(m)↑ does not vacate it).
    for key, ent in cx.guard_roles().items():
        a = ent.get("anchor")
        if isinstance(a, tuple) and a[0] == "REF":
            return (False, "AM(i) by construction: unregistered anchor reference %r "
                           "(role %s; D8)" % (a[1], key))
        if isinstance(a, str) and cx.gv.anchors() is not None and cx.gv.anchor(a) is None:
            return (False, "AM(i) by construction: declared anchor %r has no row in "
                           "A_v (role %s; D8)" % (a, key))
    brow = cx.expected.get("binding_row")
    if not _beta_prescribes(brow):
        # C3 Def 3.15: AM ⟺ β_v(m)↓ ∧ ¬P_rule. With no prescribed anchor pair there
        # is no rule to violate — the state is Def 3.16(i)'s binding-missing mode,
        # which the guard order reaches at MC, not at AM.
        return (True, "β_v(m)↑ (%s): AM guard vacuously false (Def 3.15 conditions AM "
                      "on β_v(m)↓; no unregistered reference)"
                % ("no binding row" if brow is None else
                   "binding row %r prescribes no leg anchors" % brow.get("binding_id")))
    mode, err = resolve_adm_mode(cx.gv, brow, cx.binding)
    if err:
        return (None, err)
    passed, clause, detail = replay_svw(cx.gv, cx.guard_roles(), brow, mode)
    if passed is None:
        return (None, detail)
    return (passed, detail if passed else "AM holds at clause %s: %s" % (clause, detail))


def _find_den_probe(cx):
    for p in cx.probes:
        if isinstance(p, dict) and p.get("kind") == "DEN_POP":
            return p
    return None


def _replay_mu_den(cx, probe_sql, expect_win=None):
    """Validate + re-execute the denominator population probe against D."""
    clo, eff, win = cx.den_closure()
    if expect_win is not None:
        win = expect_win
    if not clo:
        return (None, None, "denominator anchor closure underivable for probe validation")
    err = validate_probe_sql(cx.gv, probe_sql, clo, eff or "dt", win,
                             q_scope_literals(cx.q))
    if err:
        return (None, None, err)
    try:
        kind, v = exec_scalar(cx.con, probe_sql)
    except Exception as e:  # noqa: BLE001 — surfaced as REJECT detail
        return (None, None, "probe execution failed: %s" % e)
    return (kind, v, None)


def check_V6b(cx):
    """Refusal witness replay: (0) negation of the prior guards in the frozen
    order OOV→AM→MC, then (1) the witness's own finite decision."""
    if cx.dec != "REFUSE":
        return ("SKIP", "V6b applies to refusal certificates only")
    r = REASONS.get(cx.reason)
    if r is None:
        return ("FAIL", "unknown refusal reason %r" % (cx.reason,))
    if cx.env_refusal and cx.reason and not str(cx.env_refusal).startswith(cx.reason):
        return ("FAIL", "envelope refusal %r ≠ certificate reason %r"
                % (cx.env_refusal, cx.reason))
    w = cx.witness
    if not w:
        return ("FAIL", "refusal without witness (unfalsifiable refusal, C5 Prop 5.12)")
    # CT shape (slice-major, Def 5.2): when present, the first slice row's
    # reason must agree with r; non-first rows are unverified audit notes
    # (explicit non-goal) and are format-checked only.
    ct = cx.refusal.get("ct")
    if ct is not None:
        if not (isinstance(ct, list) and ct and isinstance(ct[0], dict)):
            return ("FAIL", "CT present but not a non-empty list of slice rows")
        fr = ct[0].get("reason")
        if REASONS.get(fr, fr) != r:
            return ("FAIL", "CT first slice reason %r ≠ certificate reason %r "
                            "(slice-major: r comes from the first failed slice)" % (fr, r))
    # (0) prior-guard negation
    steps = []
    if r in ("AM", "MC", "DB"):
        ok, detail = _replay_neg_oov(cx)
        if ok is None:
            return ("FAIL", "¬OOV replay undecidable: %s" % detail)
        if not ok:
            return ("FAIL", "guard order violated: OOV holds before %s (%s)" % (r, detail))
        steps.append("¬OOV ok")
    if r in ("MC", "DB"):
        ok, detail = _replay_neg_am(cx)
        if ok is None:
            return ("FAIL", "¬AM replay undecidable: %s" % detail)
        if not ok:
            return ("FAIL", "guard order violated: AM holds before %s (%s)" % (r, detail))
        steps.append("¬AM ok")
    if r == "DB":
        clo, eff, win = cx.den_closure()
        if cx.expected.get("ratio"):
            dp = _find_den_probe(cx)
            if dp is None:
                return ("FAIL", "REFUSE(DB) on a ratio metric without a DEN_POP transcript "
                                "to replay ¬MC")
            kind, v, err = _replay_mu_den(cx, dp.get("sql"))
            if err:
                return ("FAIL", "¬MC replay: %s" % err)
            if in_Z(kind, v):
                return ("FAIL", "guard order violated: MC(ii) holds before DB (μ_den=%r)" % (v,))
            steps.append("¬MC ok")
    if r == "OOV" and w.get("type") not in _OOV_NON_COVERAGE_WITNESS:
        # OOV has no predecessor to negate, but its coverage disjunct is
        # adjudicated pair-wise wherever β_v pairs the legs; the single-anchor
        # witness cannot carry that verdict on its own (R5-M1, see
        # _replay_pos_oov).
        ok, detail = _replay_pos_oov(cx)
        if ok is None:
            return ("FAIL", "OOV replay undecidable: %s" % detail)
        if not ok:
            return ("FAIL", "refusal class substitution: OOV does not hold on (G_v,D) "
                            "at the level its coverage disjunct is adjudicated (%s)" % detail)
        steps.append("OOV holds ok")
    # (1) witness replay by declared type
    wt = w.get("type")
    if r == "MC":
        if wt == "routing-lookup":
            key = w.get("caliber_key")
            routings = cx.gv.routings()
            if routings is None:
                return ("FAIL", "gov_caliber_routing absent: MC(i) lookup unverifiable")
            row = cx.gv.routing(key) if key else None
            if row is None and key:
                return ("PASS", "; ".join(steps + [
                    "MC(i): caliber_key %r absent from gov_caliber_routing@%s" % (key, cx.version)]))
            if row is not None and row.get("dst_caliber") == "none":
                if w.get("dst_caliber") not in (None, "none"):
                    return ("FAIL", "witness dst_caliber %r ≠ registered 'none'" % w.get("dst_caliber"))
                return ("PASS", "; ".join(steps + [
                    "MC(i): route %r is reference-only (dst_caliber='none')" % key]))
            if row is None:
                m = w.get("metric") or cx.q.get("metric")
                # R_v(m)↑ replay. Where the seed carries the machine-readable
                # metric attribution of R_v (C3 Def 3.4), the lookup is that key;
                # only a seed without it falls back to scanning the prose notes.
                attributed = [rr for rr in routings if "metric" in rr]
                if attributed:
                    hit = [rr for rr in attributed
                           if base_metric(rr.get("metric") or "") == base_metric(m or "")]
                else:
                    hit = [rr for rr in routings if m and m in (rr.get("note") or "")]
                if not hit:
                    return ("PASS", "; ".join(steps + [
                        "MC(i): no recomputable route registered for metric %r" % m]))
            return ("FAIL", "MC(i) witness does not replay: route %r exists and is "
                            "recomputable" % key)
        if wt == "empty-denominator-probe":
            kind, v, err = _replay_mu_den(cx, w.get("probe_sql"))
            if err:
                return ("FAIL", "MC(ii) probe: %s" % err)
            if not in_Z(kind, v):
                return ("FAIL", "MC(ii) does not replay: μ_den=%r ∉ 𝒵 (μ_den≤0 ∨ NULL ∨ ∅)" % (v,))
            wobs = w.get("observed", "___absent___")
            if wobs != "___absent___":
                same = (wobs is None and kind in ("null", "empty")) or \
                       (wobs is not None and kind == "value" and float(wobs) == float(v))
                if not same:
                    return ("FAIL", "recorded observed %r contradicts re-executed value %r "
                                    "(§3.2(2): certificate fields are claims)" % (wobs, v))
            return ("PASS", "; ".join(steps + ["MC(ii): μ_den re-executed ∈ 𝒵 (observed %s)"
                                               % ("NULL" if kind != "value" else v)]))
        return ("FAIL", "MC witness type %r unknown" % (wt,))
    if r == "AM":
        clause = w.get("clause")
        brow = None
        bid = cx.binding.get("binding_id") or w.get("binding_id")
        if bid:
            brow = cx.gv.binding_by_id(bid)
            if brow is None:
                return ("FAIL", "AM witness binding_id %r ∉ gov_temporal_binding@%s"
                        % (bid, cx.version))
        else:
            brow = cx.expected.get("binding_row")
        if wt in ("window-pair",) or clause == "(ii)":
            wn = parse_window_obj(w.get("num_window"))
            wd = parse_window_obj(w.get("den_window"))
            if wn is None or wd is None:
                return ("FAIL", "AM(ii) witness windows unparseable")
            en = (cx.expected["roles"].get("numerator") or {}).get("window")
            ed = (cx.expected["roles"].get("denominator") or {}).get("window")
            if en is None or ed is None or not (w_eq(wn, en) and w_eq(wd, ed)):
                return ("FAIL", "AM(ii) payload windows (%s, %s) are not q's request "
                                "window pair (%s, %s) — fake-pair replay rejected"
                        % (w_str(wn), w_str(wd), w_str(en), w_str(ed)))
            if w_eq(wn, wd):
                return ("FAIL", "AM(ii) does not replay: W_n = W_d")
            return ("PASS", "; ".join(steps + ["AM(ii): W_n ≠ W_d on q's own window pair"]))
        if wt in ("anchor-override",) or clause == "(i)":
            role = w.get("role")
            abar = w.get("declared_anchor") or w.get("anchor_ref")
            astar = w.get("prescribed_anchor")
            if abar is None:
                return ("FAIL", "AM(i) witness missing the declared anchor ā")
            if cx.gv.anchor(abar) is None:
                # unregistered reference (D8: atomic and ratio alike): the witness
                # is the reference name + the 'no such anchor in A_v' assertion
                return ("PASS", "; ".join(steps + [
                    "AM(i): declared anchor %r has no row in A_v@%s (unregistered "
                    "reference, role %s)" % (abar, cx.version, role)]))
            star_from_row = None
            if brow is not None:
                star_from_row = {"numerator": brow.get("numerator_anchor"),
                                 "denominator": brow.get("denominator_anchor")}.get(role)
            if astar is None:
                astar = star_from_row
            elif star_from_row is not None and astar != star_from_row:
                return ("FAIL", "AM(i) witness prescribed_anchor %r ≠ β_v row's %r "
                                "(certificate fields are claims)" % (astar, star_from_row))
            if astar is None:
                return ("FAIL", "AM(i) prescribed anchor underivable for role %r" % role)
            if abar == astar:
                return ("FAIL", "AM(i) does not replay: declared anchor equals the "
                                "prescribed anchor %r" % astar)
            return ("PASS", "; ".join(steps + ["AM(i): ā=%r ≠ a*=%r (role %s)"
                                               % (abar, astar, role)]))
        if clause == "(iii)":
            if brow is None:
                return ("FAIL", "AM(iii) needs the binding row for g^cmp")
            gcmp = resolve_cmp_granularity(brow)
            if not gcmp:
                return ("FAIL", "AM(iii) comparison granularity undeclared (must not fall "
                                "back to a single-anchor granule test, Def 5.3)")
            win = parse_window_obj(w.get("window")) or \
                (cx.expected["roles"].get("numerator") or {}).get("window")
            if win is None:
                return ("FAIL", "AM(iii) window unavailable")
            ok, edge = month_granule_aligned(win, gcmp)
            if ok:
                return ("FAIL", "AM(iii) does not replay: W ∈ 𝒲_{%s}" % gcmp)
            bp = w.get("boundary_point")
            if bp and _parse_day(bp) != edge:
                return ("FAIL", "AM(iii) boundary point %r ≠ replayed misaligned edge %s"
                        % (bp, edge))
            return ("PASS", "; ".join(steps + ["AM(iii): W ∉ 𝒲_{%s} at %s" % (gcmp, edge)]))
        if wt in ("validity-set-symdiff",) or clause == "(iv)":
            mode, err = resolve_adm_mode(cx.gv, brow, dict(cx.binding, **{
                "adm_check_mode": w.get("adm_check_mode") or cx.binding.get("adm_check_mode")}))
            if err:
                return ("FAIL", err)
            an = cx.gv.anchor(w.get("num_anchor"))
            ad = cx.gv.anchor(w.get("den_anchor"))
            if an is None or ad is None:
                return ("FAIL", "AM(iv) anchors %r/%r not both registered"
                        % (w.get("num_anchor"), w.get("den_anchor")))
            if mode == "window_realization_symdiff":
                # window-restricted realisation audit on q's own window pair
                en = (cx.expected["roles"].get("numerator") or {}).get("window")
                ed = (cx.expected["roles"].get("denominator") or {}).get("window")
                wn = parse_window_obj(w.get("num_window")) or en
                wd = parse_window_obj(w.get("den_window")) or ed
                if en is not None and wn is not None and not w_eq(wn, en):
                    return ("FAIL", "AM(iv) payload num window %s is not q's request "
                                    "window %s (fake-pair replay rejected)"
                            % (w_str(wn), w_str(en)))
                if ed is not None and wd is not None and not w_eq(wd, ed):
                    return ("FAIL", "AM(iv) payload den window %s is not q's request "
                                    "window %s (fake-pair replay rejected)"
                            % (w_str(wd), w_str(ed)))
                rn = p2_realization_days(cx.gv, an, wn)
                rd = p2_realization_days(cx.gv, ad, wd)
                if rn is None or rd is None:
                    return ("FAIL", "AM(iv) realization audit inapplicable "
                                    "(token-granule window): witness unverifiable")
                sd = rn ^ rd
                if not sd:
                    return ("FAIL", "AM(iv) does not replay: window-realization sets equal")
                disc = w.get("discriminant_date")
                if disc and str(disc) not in sd:
                    return ("FAIL", "discriminant %r ∉ replayed realization symdiff" % disc)
                cnt = w.get("symdiff_count")
                if cnt is not None and int(cnt) != len(sd):
                    return ("FAIL", "symdiff_count %r ≠ replayed |△| = %d" % (cnt, len(sd)))
                return ("PASS", "; ".join(steps + [
                    "AM(iv): window-realization |Δ|=%d re-established on D "
                    "(num %d day(s) vs den %d day(s))" % (len(sd), len(rn), len(rd))]))
            if mode != "symdiff_audit":
                return ("FAIL", "AM(iv) witness requires adm_check_mode=symdiff_audit "
                                "or window_realization_symdiff, got %r" % (mode,))
            sd = anchor_valid_dates(cx.gv, an) ^ anchor_valid_dates(cx.gv, ad)
            if not sd:
                return ("FAIL", "AM(iv) does not replay: symmetric difference empty")
            disc = w.get("discriminant_date")
            if disc:
                if _parse_day(disc) not in sd:
                    return ("FAIL", "discriminant %r ∉ replayed V(a_n)△V(a_d)" % disc)
            cnt = w.get("symdiff_count")
            if cnt is not None and int(cnt) != len(sd):
                return ("FAIL", "symdiff_count %r ≠ replayed |△| = %d" % (cnt, len(sd)))
            return ("PASS", "; ".join(steps + ["AM(iv): |V(a_n)△V(a_d)|=%d, discriminant "
                                               "verified" % len(sd)]))
        return ("FAIL", "AM witness clause %r / type %r unknown" % (clause, wt))
    if r == "OOV":
        if wt in ("unparseable-asof", "asof-unparseable"):
            kind, _ = parse_asof(str(w.get("raw_as_of")))
            if kind != "unparseable":
                return ("FAIL", "I2'(b) does not replay: as_of %r parses" % w.get("raw_as_of"))
            return ("PASS", "OOV I2'(b): as_of unparseable re-verified")
        if wt == "version-axis-undefined":
            return ("PASS", "OOV I2'(c) handled by V1's version-axis probe")
        aid = w.get("anchor_id")
        arow = cx.gv.anchor(aid) if aid else None
        if arow is None:
            return ("FAIL", "OOV witness anchor %r not registered@%s" % (aid, cx.version))
        cov, mode, err = anchor_coverage(cx.gv, arow, w.get("coverage_mode"))
        if err:
            return ("FAIL", "OOV coverage: %s" % err)
        # the requested window: the role window of the α entry carrying this anchor
        win = None
        for ent in cx.alpha.values():
            if ent.get("anchor") == aid and ent.get("window") is not None:
                win = ent["window"]
                break
        if win is None:
            win = parse_window_obj(w.get("requested"))
        if win is None:
            return ("FAIL", "OOV requested window unavailable")
        if not w_empty(w_intersect(win, cov)):
            return ("FAIL", "OOV does not replay: W ∩ Cov_v(%s)[%s] ≠ ∅ (W=%s, Cov=%s)"
                    % (aid, mode, w_str(win), w_str(cov)))
        return ("PASS", "; ".join(steps + ["OOV: W ∩ Cov_v(%s)[%s] = ∅ replayed"
                                           % (aid, mode)]))
    if r == "DB":
        pols = cx.gv.policies() or []
        ids = {p.get("policy_id") for p in pols}
        blk = w.get("blocking_policy_ids") or []
        missing = [b for b in blk if b not in ids]
        if missing:
            return ("FAIL", "DB blocking policies %r not registered@%s" % (missing, cx.version))
        if not blk:
            return ("FAIL", "DB witness cites no blocking policy")
        tr = w.get("probe_transcript") or []
        if not tr:
            return ("FAIL", "DB witness without SUPPMIN/POP probe transcript")
        for p in tr:
            sqlp = p.get("sql")
            if sqlp:
                if _FORBIDDEN_SQL.search(sqlp) or ";" in sqlp.strip().rstrip(";"):
                    return ("FAIL", "DB probe not a single SELECT")
                try:
                    kind, v = exec_scalar(cx.con, sqlp)
                except Exception as e:  # noqa: BLE001
                    return ("FAIL", "DB probe failed: %s" % e)
                thr = p.get("threshold")
                if thr is not None and kind == "value" and float(v) >= float(thr):
                    return ("FAIL", "DB does not replay: SUPPMIN %r ≥ threshold %r" % (v, thr))
        if not w.get("u_min_empty"):
            return ("FAIL", "DB witness must assert u_min_empty (S-M2)")
        return ("PASS", "; ".join(steps + ["DB: blocking policies registered, transcripts "
                                           "replayed under threshold, U_min=∅ asserted"]))
    return ("FAIL", "unhandled refusal reason %r" % (cx.reason,))


def check_V6c(cx):
    """Answer-side guard replay: ¬OOV ∧ ¬AM ∧ ¬MC re-established from (G_v, D)."""
    if cx.dec not in ("ANSWER", "REWRITE"):
        return ("SKIP", "V6c applies to answer certificates only")
    ok, detail = _replay_neg_oov(cx)
    if ok is None:
        return ("FAIL", "¬OOV replay undecidable: %s" % detail)
    if not ok:
        return ("FAIL", "OOV holds yet the certificate answers: %s" % detail)
    ok, detail = _replay_neg_am(cx)
    if ok is None:
        return ("FAIL", "¬AM replay undecidable: %s" % detail)
    if not ok:
        return ("FAIL", "AM holds yet the certificate answers: %s" % detail)
    if cx.expected.get("ratio"):
        # ¬MC(i): a recomputable route must be cited (V4 already field-checks it)
        if not cx.routing:
            return ("FAIL", "¬MC(i) not establishable: no routing cited for a ratio metric")
        for e in cx.routing:
            row = cx.gv.routing(e.get("caliber_key")) if isinstance(e, dict) else None
            if row is None or row.get("dst_caliber") == "none":
                return ("FAIL", "¬MC(i) fails: cited route %r missing or reference-only"
                        % (e.get("caliber_key") if isinstance(e, dict) else e,))
        # ¬MC(ii): μ_den > 0 re-executed from D (never trusted from the transcript)
        periods = sorted({k.split("#")[1] if "#" in k else "0" for k in cx.alpha})
        for per in periods:
            suffix = "" if per == "0" else "#" + per
            dp = None
            for p in cx.probes:
                if isinstance(p, dict) and p.get("kind") == "DEN_POP" and \
                        str(p.get("period") or 0) == (per if per != "0" else "0"):
                    dp = p
                    break
            if dp is None and per == "0":
                dp = _find_den_probe(cx)
            if dp is None:
                return ("FAIL", "ratio answer without a DEN_POP probe transcript for "
                                "period %s (F1b surface: empty-denominator ANSWER)" % per)
            clo, eff, win = cx.den_closure(suffix)
            kind, v, err = _replay_mu_den(cx, dp.get("sql"), expect_win=win)
            if err:
                return ("FAIL", "DEN_POP probe: %s" % err)
            if in_Z(kind, v):
                return ("FAIL", "MC(ii) holds yet the certificate answers: re-executed "
                                "μ_den=%r ∈ 𝒵 (empty/NULL/≤0)" % (v,))
            rec = dp.get("observed", "___absent___")
            if rec != "___absent___" and not (
                    rec is not None and kind == "value" and float(rec) == float(v)):
                return ("FAIL", "DEN_POP recorded observed %r contradicts re-executed %r" % (rec, v))
    return ("PASS", "¬OOV ∧ ¬AM ∧ ¬MC replayed on (G_v, D)")


# =========================================================================
# H. driver
# =========================================================================

def verify(cert_obj, q, con, ctx=None, allow_declared_windows=True):
    """Chk(C, G_v, D, ctx) -> report dict. Inputs are strictly the certificate,
    the structured question, the warehouse connection (G_v + D) and the
    auditor-held context.
    allow_declared_windows=False forbids reading any window coordinate off the
    question (q['windows'] / num_window / den_window / delta_windows): the role
    windows must then come from the domain's registered as-of convention alone."""
    cert, out_sql, env_refusal = load_cert(cert_obj)
    if cert is None or not isinstance(cert, dict):
        return {"verdict": "REJECT", "rejected_by": "V0",
                "checks": [{"check": "V0", "status": "FAIL",
                            "detail": "certificate is not an object"}]}
    cx = Ctx(cert, out_sql, env_refusal, q, con, ctx,
             allow_declared=allow_declared_windows)
    checks = []
    fns = {"V0": check_V0, "V1": check_V1, "V2": check_V2, "V3": check_V3,
           "V4": check_V4, "V5": check_V5, "V6a": check_V6a, "V6b": check_V6b,
           "V6c": check_V6c}
    for cid in CHECK_ORDER:
        try:
            status, detail = fns[cid](cx)
        except Exception as e:  # noqa: BLE001 — a crashing check is a failing check
            status, detail = "FAIL", "check crashed: %s: %s" % (type(e).__name__, e)
        checks.append({"check": cid, "status": status, "detail": detail})
    fails = [c for c in checks if c["status"] == "FAIL"]
    exp = cx.expected
    report = {
        "verdict": "REJECT" if fails else "ACCEPT",
        "rejected_by": fails[0]["check"] if fails else None,
        "checks": checks,
        "gv_notes": cx.gv.notes,
        # independence provenance of the re-derivation (never a check verdict —
        # a purely descriptive record of WHERE each coordinate came from)
        "independence": {
            "declared_windows_allowed": allow_declared_windows,
            "alpha_status": exp.get("status"),
            "window_source": exp.get("window_source"),
            "window_source_detail": exp.get("window_source_detail"),
            "arity_source": exp.get("arity_source"),
        },
    }
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="C5 independent certificate verifier (V0–V6c)")
    ap.add_argument("--cert", required=True, help="certificate JSON file")
    ap.add_argument("--question", help="structured question JSON file (single object)")
    ap.add_argument("--questions", help="questions.json file (array); requires --qid")
    ap.add_argument("--qid", help="qid to select from --questions")
    ap.add_argument("--db", required=True, help="warehouse.duckdb (G_v + D)")
    ap.add_argument("--ctx", help="auditor context JSON (governed disclosure domains)")
    ap.add_argument("--json", action="store_true", help="emit the full JSON report")
    ap.add_argument("--no-declared-windows", action="store_true",
                    help="refuse every window coordinate presented by the question "
                         "(q['windows'] / num_window / den_window / delta_windows); "
                         "role windows must come from the domain's registered as-of "
                         "convention over (G_v, D) alone")
    args = ap.parse_args(argv)
    with open(args.cert, encoding="utf-8") as fh:
        cert = json.load(fh)
    if args.question:
        with open(args.question, encoding="utf-8") as fh:
            q = json.load(fh)
    elif args.questions and args.qid:
        with open(args.questions, encoding="utf-8") as fh:
            qs = json.load(fh)
        q = next((x for x in qs if x.get("qid") == args.qid), None)
        if q is None:
            print("qid %r not found" % args.qid, file=sys.stderr)
            return 2
    else:
        print("pass --question or (--questions and --qid)", file=sys.stderr)
        return 2
    ctx = None
    if args.ctx:
        with open(args.ctx, encoding="utf-8") as fh:
            ctx = json.load(fh)
    con = duckdb.connect(args.db, read_only=True)
    try:
        rep = verify(cert, q, con, ctx,
                     allow_declared_windows=not args.no_declared_windows)
    finally:
        con.close()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("%s%s" % (rep["verdict"],
                        "" if not rep["rejected_by"] else " (rejected_by %s)" % rep["rejected_by"]))
        ind = rep.get("independence") or {}
        print("  window_source=%s  arity_source=%s"
              % (ind.get("window_source"), ind.get("arity_source")))
        for c in rep["checks"]:
            print("  %-4s %-4s %s" % (c["check"], c["status"], c["detail"]))
    return 0 if rep["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    sys.exit(main())
