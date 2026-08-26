#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forge_v6aplus.py — forgery families F6–F10 (V6a+ hardening battery,
PREREG_poststudy3_20260826.md sha256
426017ddfd8af8608e452b44175e2158c620c2e8cebe3a17572ee3fe15d7a192).

Every base is a REAL compiler-emitted certificate the hardened verifier
ACCEPTs unmutated; each forgery is a systematic SQL-text mutation (exact
substring replacement, asserted to apply) that leaves every certificate
FIELD intact — precisely the surface the external review (Codex 2026-08-26)
showed V6a alone could not police. Families, per the prereg:

  F6  wrong-aggregate      — the leg's aggregate is replaced by a lookalike
                             (COUNT(DISTINCT …), AVG for SUM, COUNT(col),
                             wrong registered column, raw column instead of
                             the routed one).
  F7  leg-swap             — numerator and denominator leg subqueries are
                             exchanged inside the intact ratio frame.
  F8  wrong/absent registered predicate — a registered measure predicate is
                             dropped, its constant changed, or a scope
                             constant replaced against the question.
  F9  narrowed-or-widened window predicate — the leg's time predicate is
                             narrowed inside the certified window (invisible
                             to V6a's containment scan), widened, shifted,
                             or the in-effect bound is moved.
  F10 constant/multi-row output — constant projections, multi-row and
                             multi-column outputs, set operations, and
                             non-aggregate scalar subqueries.

Expectation model: every forgery must REJECT, and "V6a+" must be among the
failing checks. `rejected_by` (first FAIL in the frozen canonical order) is
asserted exactly: it is "V6a+" wherever the pre-hardening verifier accepted
the mutation class, and the earlier frozen gate (V6a) where the mutation
also escapes the certified window containment — those cases are the
regression face V6a always policed; V6a+ must fail on them TOO.

Verifier-side file: imports chk only. Certificates and questions are
consumed as data; nothing is imported from any compiler.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chk  # the verifier under test (same side of the red line)

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL = os.path.dirname(HERE)
ROOT = os.path.dirname(IMPL)
CERTS2 = os.path.join(IMPL, "certs2")

BASE_QIDS = {
    "CARD-Q1": "card_games", "CARD-Q2": "card_games", "CARD-Q4": "card_games",
    "CA-Q1": "california_schools", "CA-Q3": "california_schools",
    "CODE-Q1": "codebase_community", "CODE-Q2": "codebase_community",
    "CODE-Q3": "codebase_community",
    "DEB-Q1": "debit_card_specializing", "DEB-Q3": "debit_card_specializing",
    "EF2-Q1": "european_football_2", "EF2-Q2": "european_football_2",
    "FIN-Q1": "financial", "FIN-Q3": "financial", "FIN-Q4": "financial",
    "FIN-Q5": "financial",
    "F1-Q1": "formula_1",
    "TH-Q1": "thrombosis_prediction", "TH-Q2": "thrombosis_prediction",
    "W1-Q1": "world_1", "W1-Q2": "world_1", "W1-Q3": "world_1",
}

_RATIO_FRAME = re.compile(
    r"^SELECT\s+\((?P<num>SELECT .*)\)\s*\*\s*1\.0\s*/\s*"
    r"NULLIF\(\((?P<den>SELECT .*)\),\s*0\)\s*$", re.S)


def _sub(sql, old, new):
    """Exact-substring mutation; refuses to no-op (systematic, fail-fast)."""
    if old not in sql:
        raise AssertionError("mutation substring not found: %r" % old[:80])
    return sql.replace(old, new)


def _swap_ratio_legs(sql):
    m = _RATIO_FRAME.match(sql.strip())
    if not m:
        raise AssertionError("ratio frame not matched for leg swap")
    return ("SELECT (%s) * 1.0 / NULLIF((%s), 0)"
            % (m.group("den"), m.group("num")))


def _sql_mut(fn):
    def g(env, con):
        f = copy.deepcopy(env)
        f["sql"] = fn(f["sql"])
        return f
    return g


def forgeries():
    """Yields (name, base_qid, mutate(env, con) -> env, expected_rejected_by,
    note). "V6a+" must additionally be among the FAILs of every row."""
    out = []

    # ---------------- F6: wrong aggregate ----------------
    out.append(("F6a_count_distinct_num", "CARD-Q2", _sql_mut(
        lambda s: _sub(s, 'SELECT COUNT(*) FROM "rulings" t0',
                       'SELECT COUNT(DISTINCT t0."date") FROM "rulings" t0')),
        "V6a+", "numerator count re-implemented as COUNT(DISTINCT rulings."
                "date): same table, same window, wrong registered measure"))
    out.append(("F6b_avg_for_sum", "CA-Q1", _sql_mut(
        lambda s: _sub(s, 'SUM(t0."Free Meal Count (K-12)")',
                       'AVG(t0."Free Meal Count (K-12)")')),
        "V6a+", "numerator sum:<col> replaced by AVG over the same "
                "registered column"))
    out.append(("F6c_count_for_sum", "DEB-Q3", _sql_mut(
        lambda s: _sub(s, 'SUM(t0."Consumption")', 'COUNT(*)')),
        "V6a+", "sum:Consumption replaced by COUNT(*): a plausible atomic "
                "lookalike inside the certified closure"))
    out.append(("F6d_wrong_sum_column", "W1-Q1", _sql_mut(
        lambda s: _sub(s, 'SUM(t0."population")',
                       'SUM(t0."population_resident")')),
        "V6a+", "sum:population replaced by the sibling registered column "
                "population_resident (W1-Q2's caliber, not W1-Q1's)"))
    out.append(("F6e_raw_points_column", "F1-Q1", _sql_mut(
        lambda s: _sub(s, 'SUM(t2."points")', 'SUM(t0."points")')),
        "V6a+", "sum:points_scheme.points replaced by the raw results.points "
                "column — the exact registered-form-not-lookalike case"))
    out.append(("F6f_count_col_for_count", "TH-Q1", _sql_mut(
        lambda s: _sub(s, 'SELECT COUNT(*) FROM "Laboratory" t0 WHERE '
                          't0."GOT" >= 60',
                       'SELECT COUNT(t0."GOT") FROM "Laboratory" t0 WHERE '
                       't0."GOT" >= 60')),
        "V6a+", "count implemented as COUNT(col): NULL-skipping lookalike of "
                "the registered COUNT(*)"))

    # ---------------- F7: leg swap ----------------
    for tag, qid in (("a", "CODE-Q1"), ("b", "FIN-Q1"), ("c", "W1-Q3"),
                     ("d", "CA-Q1"), ("e", "EF2-Q2")):
        out.append(("F7%s_leg_swap_%s" % (tag, qid.replace("-", "").lower()),
                    qid, _sql_mut(_swap_ratio_legs), "V6a+",
                    "numerator and denominator legs exchanged inside the "
                    "intact `num * 1.0 / NULLIF(den, 0)` frame"))

    # ---------------- F8: wrong/absent registered predicate ----------------
    out.append(("F8a_drop_status_pred", "FIN-Q1", _sql_mut(
        lambda s: _sub(s, "t0.\"status\" IN ('B', 'D') AND ", "")),
        "V6a+", "registered numerator predicate status IN ('B','D') deleted: "
                "num silently becomes den"))
    out.append(("F8b_wrong_ksymbol", "FIN-Q3", _sql_mut(
        lambda s: _sub(s, "'SANKC. UROK'", "'SLUZBY'")),
        "V6a+", "registered k_symbol constant replaced by another real "
                "k_symbol value"))
    out.append(("F8c_weakened_threshold", "TH-Q1", _sql_mut(
        lambda s: _sub(s, 't0."GOT" >= 60', 't0."GOT" >= 6')),
        "V6a+", "registered GOT >= 60 threshold weakened to 6"))
    out.append(("F8d_wrong_posttype", "CODE-Q1", _sql_mut(
        lambda s: _sub(s, 't0."PostTypeId" = 2', 't0."PostTypeId" = 3')),
        "V6a+", "registered PostTypeId = 2 numerator predicate re-pointed at "
                "wiki posts"))
    out.append(("F8e_drop_isnull_pred", "CODE-Q2", _sql_mut(
        lambda s: _sub(s, 't0."CommunityOwnedDate" IS NULL AND ', "")),
        "V6a+", "v2-registered denominator predicate CommunityOwnedDate IS "
                "NULL deleted"))
    out.append(("F8f_wrong_scope_const", "CARD-Q4", _sql_mut(
        lambda s: _sub(s, "t1.\"setCode\" = 'ORI'", "t1.\"setCode\" = 'KTK'")),
        "V6a+", "scope constant contradicts the question's own set_code "
                "declaration (q says ORI)"))
    out.append(("F8g_drop_scope_join_pred", "F1-Q1", _sql_mut(
        lambda s: _sub(_sub(s, ' INNER JOIN "drivers" t3 ON t0."driverId" = '
                               't3."driverId"', ""),
                       "t3.\"driverRef\" = 'button' AND ", "")),
        "V6a+", "the question's driver scope (join + predicate) silently "
                "dropped from an ANSWER: computes every driver's points "
                "(hole found and closed during hardening — the declared "
                "scope keys are registered predicates of the binding)"))
    out.append(("F8h_drop_scope_pred_both_legs", "CA-Q1", _sql_mut(
        lambda s: s.replace("t0.\"County Name\" = 'Alameda' AND ", "")),
        "V6a+", "the question's county scope dropped from both ratio legs "
                "of an ANSWER: state-wide rate presented as Alameda's"))

    # ---------------- F9: narrowed-or-widened window ----------------
    out.append(("F9a_narrow_month", "CARD-Q1", _sql_mut(
        lambda s: _sub(_sub(s, "'2017-02-01'", "'2017-02-10'"),
                       "'2017-03-01'", "'2017-02-20'")),
        "V6a+", "month window narrowed to [02-10, 02-20): still inside the "
                "certified window, invisible to V6a's containment scan"))
    out.append(("F9b_widen_to_year", "FIN-Q4", _sql_mut(
        lambda s: _sub(_sub(s, "'1997-05-01'", "'1997-01-01'"),
                       "'1997-06-01'", "'1998-01-01'")),
        "V6a", "month window widened to the whole year: escapes containment "
               "(V6a, frozen attribution) and fails window equality (V6a+)"))
    out.append(("F9c_shift_token", "W1-Q1", _sql_mut(
        lambda s: _sub(s, "'2026-05'", "'2026-04'")),
        "V6a", "month token shifted to 2026-04: outside the certified month "
               "(V6a) and unequal to it (V6a+)"))
    out.append(("F9d_narrow_num_leg", "EF2-Q2", _sql_mut(
        lambda s: s.replace("'2016-05-26'", "'2016-05-01'", 1)),
        "V6a+", "numerator leg's upper bound pulled to 05-01 while the "
                "denominator keeps the certified range: in-window narrowing "
                "of one ratio leg"))
    out.append(("F9e_extra_day_bound", "DEB-Q1", _sql_mut(
        lambda s: _sub(s, "CAST(t0.\"Date\" AS VARCHAR) = '201308')",
                       "CAST(t0.\"Date\" AS VARCHAR) = '201308' AND "
                       "substr(CAST(t0.\"Date\" AS VARCHAR),1,10) >= "
                       "'2013-08-10')")),
        "V6a+", "an extra lower day-bound conjoined onto the certified "
                "month-token equality narrows the leg inside the window"))
    out.append(("F9f_move_ineffect_bound", "CA-Q3", _sql_mut(
        lambda s: _sub(s, "substr(CAST(t0.\"OpenDate\" AS VARCHAR),1,10) <= "
                          "'2015-01-01'",
                       "substr(CAST(t0.\"OpenDate\" AS VARCHAR),1,10) <= "
                       "'2014-12-31'")),
        "V6a", "the in-effect lower bound is moved off the certified point "
               "day (V6a's SCD-2 replay catches it first; V6a+ must too)"))

    # ---------------- F10: constant / multi-row output ----------------
    out.append(("F10a_constant_multirow", "CARD-Q1", _sql_mut(
        lambda s: 'SELECT 999 FROM "rulings" t0 WHERE '
                  "substr(CAST(t0.\"date\" AS VARCHAR),1,10) >= '2017-02-01' "
                  "AND substr(CAST(t0.\"date\" AS VARCHAR),1,10) < "
                  "'2017-03-01'"),
        "V6a+", "constant multi-row projection over the certified table and "
                "window (the Codex mutation class, on a fresh base)"))
    out.append(("F10b_constant_scalar", "FIN-Q5", _sql_mut(
        lambda s: "SELECT (SELECT 42)"),
        "V6a+", "constant-only scalar subquery: reads no relation at all"))
    out.append(("F10c_union_extra_row", "TH-Q2", _sql_mut(
        lambda s: s + " UNION ALL SELECT 0"),
        "V6a+", "UNION ALL appends a second output row to a scalar template"))
    out.append(("F10d_two_columns", "CODE-Q3", _sql_mut(
        lambda s: s + ", 1"),
        "V6a+", "a second output column appended to the scalar template"))
    out.append(("F10e_nonaggregate_subquery", "W1-Q2", _sql_mut(
        lambda s: _sub(s, 'SELECT SUM(t0."population_resident") FROM',
                       'SELECT t0."population_resident" FROM')),
        "V6a+", "aggregate dropped: the leg subquery projects a raw column "
                "(multi-row scalar subquery)"))
    out.append(("F10f_bare_constant", "EF2-Q1", _sql_mut(
        lambda s: "SELECT 0.5"),
        "V6a+", "the whole answer replaced by a bare constant"))

    return out


PINNED = [
    # (file stem, expected primary V6P reason code) — the five preserved
    # reproduction mutations of CARD-Q2 (Codex 2026-08-26 / m1-repro), all
    # of which the pre-hardening verifier ACCEPTed. See
    # pinned_regressions/README.md for provenance hashes.
    ("cert_mut_a_count_distinct_date", "V6P_MEASURE"),
    ("cert_mut_b_leg_swap", "V6P_PARSE"),
    ("cert_mut_b2_leg_swap_valid", "V6P_LEG_ROLE"),
    ("cert_mut_c_constant_999", "V6P_SHAPE"),
    ("cert_mut_d_narrowed_predicate", "V6P_WINDOW"),
]


def run_pinned(p2_root, pinned_dir, rows):
    """Replay the five pinned regression certificates: all must REJECT with
    V6a+ among the FAILs and the pinned primary reason code."""
    ok = True
    qp = os.path.join(pinned_dir, "q_CARD-Q2.json")
    with open(qp, encoding="utf-8") as fh:
        q = json.load(fh)
    db = os.path.join(p2_root, "card_games", "warehouse.duckdb")
    for stem, want_code in PINNED:
        with open(os.path.join(pinned_dir, stem + ".json"),
                  encoding="utf-8") as fh:
            env = json.load(fh)
        con = duckdb.connect(db, read_only=True)
        try:
            rep = chk.verify(env, q, con)
        finally:
            con.close()
        fails = [c for c in rep["checks"] if c["status"] == "FAIL"]
        failed_ids = [c["check"] for c in fails]
        v6p = next((c for c in rep["checks"] if c["check"] == "V6a+"), None)
        m = re.match(r"(V6P_[A-Z_]+)",
                     (v6p or {}).get("detail") or "") if v6p else None
        code = m.group(1) if m else None
        good = (rep["verdict"] == "REJECT" and "V6a+" in failed_ids and
                code == want_code)
        ok &= good
        rows.append({"name": "PINNED_" + stem, "base": "CARD-Q2",
                     "expected": "REJECT(%s)" % want_code,
                     "actual": "%s by %s" % (rep["verdict"],
                                             rep.get("rejected_by")),
                     "ok": good, "failed_checks": failed_ids,
                     "v6aplus_reason_code": code,
                     "first_fail_detail": (fails[0]["detail"][:220]
                                           if fails else ""),
                     "note": "pinned reproduction mutation (m1-repro; must "
                             "REJECT forever)"})
    return ok


def load_base(qid, p2_root):
    dom = BASE_QIDS[qid]
    with open(os.path.join(p2_root, dom, "questions.json"),
              encoding="utf-8") as fh:
        q = next(x for x in json.load(fh) if x["qid"] == qid)
    with open(os.path.join(CERTS2, qid + ".json"), encoding="utf-8") as fh:
        env = json.load(fh)
    return q, env, os.path.join(p2_root, dom, "warehouse.duckdb")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="V6a+ forgery families (F6-F10) runner")
    ap.add_argument("--out", default=os.path.join(HERE, "forge_v6aplus_out"))
    ap.add_argument("--p2", default=os.path.join(ROOT, "pilot2", "domains"),
                    help="pilot2 domains root carrying questions.json and "
                         "warehouse.duckdb per domain")
    ap.add_argument("--pinned",
                    default=os.path.join(HERE, "pinned_regressions"),
                    help="directory with the five pinned reproduction "
                         "mutations + q_CARD-Q2.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    loaded = {qid: load_base(qid, args.p2) for qid in BASE_QIDS}
    rows = []
    ok = True

    # pinned reproduction regressions first (mandatory, prereg P2)
    if os.path.isdir(args.pinned):
        ok &= run_pinned(args.p2, args.pinned, rows)
    else:
        ok = False
        rows.append({"name": "PINNED_MISSING", "expected": "dir present",
                     "actual": "absent: %s" % args.pinned, "ok": False,
                     "note": "pinned_regressions directory is mandatory"})

    # harness sanity: every base certificate must ACCEPT unmutated under the
    # HARDENED verifier (V6a+ included in the conjunction)
    for qid, (q, env, db) in sorted(loaded.items()):
        con = duckdb.connect(db, read_only=True)
        try:
            rep = chk.verify(copy.deepcopy(env), q, con)
        finally:
            con.close()
        good = rep["verdict"] == "ACCEPT"
        ok &= good
        rows.append({"name": "BASE_" + qid, "expected": "ACCEPT",
                     "actual": rep["verdict"], "ok": good,
                     "first_fail_detail": "" if good else next(
                         c["detail"] for c in rep["checks"]
                         if c["status"] == "FAIL")[:200],
                     "note": "real compiler-emitted certificate (must ACCEPT "
                             "under the hardened verifier)"})

    fam_counts = {}
    for name, qid, mut, expected, note in forgeries():
        q, env, db = loaded[qid]
        con = duckdb.connect(db, read_only=True)
        try:
            f = mut(copy.deepcopy(env), con)
            rep = chk.verify(f, q, con)
        finally:
            con.close()
        fails = [c for c in rep["checks"] if c["status"] == "FAIL"]
        failed_ids = [c["check"] for c in fails]
        v6p = next((c for c in rep["checks"] if c["check"] == "V6a+"), None)
        code = None
        if v6p and v6p["status"] == "FAIL":
            m = re.match(r"(V6P_[A-Z_]+)", v6p["detail"])
            code = m.group(1) if m else None
        good = (rep["verdict"] == "REJECT" and
                rep["rejected_by"] == expected and
                "V6a+" in failed_ids)
        ok &= good
        fam = name.split("_")[0][:-1] if name[2].isalpha() else name[:3]
        fam = re.match(r"(F\d+)", name).group(1)
        fam_counts.setdefault(fam, {"total": 0, "rejected": 0,
                                    "bases": set()})
        fam_counts[fam]["total"] += 1
        fam_counts[fam]["rejected"] += 1 if rep["verdict"] == "REJECT" else 0
        fam_counts[fam]["bases"].add(qid)
        rows.append({"name": name, "base": qid, "expected": expected,
                     "actual": "%s by %s" % (rep["verdict"],
                                             rep.get("rejected_by")),
                     "ok": good, "failed_checks": failed_ids,
                     "v6aplus_reason_code": code,
                     "first_fail_detail": (fails[0]["detail"][:220]
                                           if fails else ""),
                     "note": note})
        with open(os.path.join(args.out, name + ".json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"base_qid": qid, "expected_reject_by": expected,
                       "envelope": f, "report": rep}, fh,
                      ensure_ascii=False, indent=1, default=str)

    for fam in fam_counts.values():
        fam["bases"] = sorted(fam["bases"])
    n_base = sum(1 for r in rows if r["name"].startswith("BASE_"))
    n_pin = sum(1 for r in rows if r["name"].startswith("PINNED_"))
    payload = {"ok": ok, "families": fam_counts, "rows": rows,
               "n_bases": n_base, "n_pinned": n_pin,
               "n_forgeries": len(rows) - n_base - n_pin}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        wid = max(len(r["name"]) for r in rows)
        for r in rows:
            print("%-*s  expect=%-7s  got=%-16s  %s"
                  % (wid, r["name"], r["expected"], r["actual"],
                     "OK" if r["ok"] else "** MISMATCH **"))
            if not r["ok"]:
                print("%*s  └─ %s" % (wid, "",
                                      r["first_fail_detail"] or "(accepted)"))
        print("\nFORGE-V6A+: %s (%d bases, %d pinned regressions, "
              "%d forgeries)" % ("PASS" if ok else "FAIL", n_base, n_pin,
                                 len(rows) - n_base - n_pin))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
