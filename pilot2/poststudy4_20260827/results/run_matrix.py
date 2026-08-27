#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_matrix.py — poststudy4_20260827 matrix runner (PREREG sha256
a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75).

Produces the run artifacts that the deterministic generator consumes:
  genuine60_verdicts.json  — all 60 pilot2 genuine certs under the round-2
                             verifier (verdict, per-check status incl. V6a+ and
                             V6a+x, executed answer arity).                (P1/P4)
  exploits_run.json        — the confirmed p0-repro outer-filter exploits
                             (V1,V1b,V1c,V2,V3,V4) replayed post-fix.        (P2)
  sweep_run.json           — the systematic corpus sweep: an outer WHERE 1=0
                             appended to every genuine cert's answer SQL.    (P3)

Read-only against the pilot2 domain warehouses (frozen EVIDENCE); mutates only
in-memory certificate copies. Deterministic: sorted iteration, fixed mutations.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys

VER = "/Volumes/SSD 1/explore_opportunity_cc/impl/asof_verifier"
# The confirmed-exploit base is the genuine CARD-Q2 ratio certificate; it is
# byte-identical to the frozen p0-repro base (verified). Read it from stable
# frozen evidence so this runner is self-contained (no session scratchpad).
CARD_Q2_CERT = os.path.join(
    os.path.dirname(os.path.dirname(VER)), "impl", "certs2", "CARD-Q2.json")
CARD_Q2_Q = os.path.join(VER, "pinned_regressions", "q_CARD-Q2.json")
sys.path.insert(0, VER)
import duckdb          # noqa: E402
import chk             # noqa: E402
import runall          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DOMAINS = "/Volumes/SSD 1/explore_opportunity_cc/pilot2/domains"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    with open(p, "rb") as fh:
        return sha256_bytes(fh.read())


def code_of(check):
    if not check or check["status"] != "FAIL":
        return None
    m = re.match(r"(V6P_[A-Z_]+)", check.get("detail") or "")
    return m.group(1) if m else None


def verify(cert, q, db):
    con = duckdb.connect(db, read_only=True)
    try:
        return chk.verify(cert, q, con)
    finally:
        con.close()


def kind_of(cert_obj, out_sql, env_ref, q, db):
    con = duckdb.connect(db, read_only=True)
    try:
        cx = chk.Ctx(cert_obj, out_sql, env_ref, q, con, None)
        try:
            return (cx.gv.metric_row(chk.base_metric(q.get("metric"))) or {}
                    ).get("kind"), cx.dec
        except Exception:
            return None, cx.dec
    finally:
        con.close()


def exec_shape(sql, db):
    if not (isinstance(sql, str) and sql.strip()):
        return None
    con = duckdb.connect(db, read_only=True)
    try:
        res = con.execute(sql)
        ncols = len(res.description) if res.description else 0
        data = res.fetchall()
        return [len(data), ncols]
    except Exception as e:
        return "EXECERR:%s" % str(e)[:80]
    finally:
        con.close()


# ---------------------------------------------------------------- genuine 60
def run_genuine60():
    rows = []
    for q, db, cert_path in runall.suite_p2():
        with open(cert_path, "rb") as fh:
            raw = fh.read()
        cert = json.loads(raw)
        cobj, out_sql, env_ref = chk.load_cert(cert)
        kind, dec = kind_of(cobj, out_sql, env_ref, q, db)
        rep = verify(cert, q, db)
        v6p = next((c for c in rep["checks"] if c["check"] == "V6a+"), None)
        v6px = next((c for c in rep["checks"] if c["check"] == "V6a+x"), None)
        shape = exec_shape(cert.get("sql"), db) if dec in ("ANSWER", "REWRITE") \
            else None
        rows.append({
            "qid": q["qid"], "domain": q.get("domain"),
            "metric": q.get("metric"), "metric_kind": kind, "decision": dec,
            "cert_sha256": sha256_bytes(raw), "verdict": rep["verdict"],
            "rejected_by": rep["rejected_by"],
            "v6aplus": {"status": (v6p or {}).get("status"),
                        "detail": (v6p or {}).get("detail")},
            "v6aplus_x": {"status": (v6px or {}).get("status"),
                          "detail": (v6px or {}).get("detail")},
            "executed_shape": shape,
            "checks": [{"check": c["check"], "status": c["status"]}
                       for c in rep["checks"]],
        })
    rows.sort(key=lambda r: r["qid"])
    from collections import Counter
    acc = sum(1 for r in rows if r["verdict"] == "ACCEPT")
    out = {
        "suite": "pilot2 genuine (certs2 x pilot2/domains)",
        "verifier": VER,
        "warehouse_root": DOMAINS,
        "n_total": len(rows), "n_accept": acc, "n_reject": len(rows) - acc,
        "v6aplus_status_counts": dict(sorted(
            Counter(r["v6aplus"]["status"] for r in rows).items())),
        "v6aplus_x_status_counts": dict(sorted(
            Counter(r["v6aplus_x"]["status"] for r in rows).items())),
        "rows": rows,
    }
    with open(os.path.join(HERE, "genuine60_verdicts.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


# ---------------------------------------------------------------- exploits
def run_exploits():
    gen = json.load(open(CARD_Q2_CERT, encoding="utf-8"))
    q = json.load(open(CARD_Q2_Q, encoding="utf-8"))
    db = os.path.join(DOMAINS, "card_games", "warehouse.duckdb")
    base = gen["sql"]
    variants = [
        ("V1_outer_where_1eq0", base + " WHERE 1=0", "confirmed exploit: "
         "outer WHERE filters the ratio to 0 rows (pre-fix ACCEPT)"),
        ("V1b_outer_where_1eq1_control", base + " WHERE 1=1", "denotation-"
         "preserving control: TRUE outer WHERE, still 1x1 (pre-fix ACCEPT); "
         "caught post-fix by the structural closure only"),
        ("V1c_outer_where_false", base + " WHERE 'a'='b'", "confirmed "
         "exploit: outer WHERE 'a'='b' filters to 0 rows (pre-fix ACCEPT)"),
        ("V2_wrap_derived_where_1eq0",
         "SELECT * FROM (" + base + ") q WHERE 1=0",
         "derived-table wrap: already rejected before round 2 (non-empty "
         "outer FROM); documented, not newly pinned"),
        ("V3_num_leg_and_1eq0",
         base.replace("< '2016-12-01') * 1.0", "< '2016-12-01' AND 1=0) * 1.0"),
         "leg-level AND 1=0: already rejected before round 2 (V6P_PREDICATE)"),
        ("V4_multirow_from_values", base + " FROM (VALUES (1),(2),(3)) v(x)",
         "outer FROM (VALUES ...): forces 3 rows; already rejected before "
         "round 2 (non-empty outer FROM); V6P_ARITY now also fires"),
    ]
    rows = []
    for name, sql, note in variants:
        c = copy.deepcopy(gen)
        c["sql"] = sql
        rep = verify(c, q, db)
        v6p = next((x for x in rep["checks"] if x["check"] == "V6a+"), None)
        v6px = next((x for x in rep["checks"] if x["check"] == "V6a+x"), None)
        rows.append({
            "name": name, "sql": sql, "note": note,
            "verdict": rep["verdict"], "rejected_by": rep["rejected_by"],
            "v6aplus_code": code_of(v6p), "v6aplus_x_code": code_of(v6px),
            "executed_shape": exec_shape(sql, db),
        })
    # the confirmed exploits the round-1 verifier ACCEPTed and round 2 must
    # REJECT: V1 and V1c (V1b is the denotation-preserving control).
    confirmed = ["V1_outer_where_1eq0", "V1c_outer_where_false"]
    out = {
        "provenance": "scratchpad p0-repro (Codex 2026-08-27); "
                      "CARD-Q2 ratio base",
        "warehouse": db,
        "confirmed_exploit_names": confirmed,
        "confirmed_all_reject": all(
            r["verdict"] == "REJECT" for r in rows
            if r["name"] in confirmed),
        "rows": rows,
    }
    with open(os.path.join(HERE, "exploits_run.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


# ---------------------------------------------------------------- sweep
def run_sweep():
    """Append an outer `WHERE 1=0` to every genuine cert's answer SQL and
    verify. REFUSE certificates carry no answer SQL (the outer-row-filter
    attack surface does not exist), recorded as no_answer_sql."""
    rows = []
    for q, db, cert_path in runall.suite_p2():
        cert = json.load(open(cert_path, encoding="utf-8"))
        cobj, out_sql, env_ref = chk.load_cert(cert)
        kind, dec = kind_of(cobj, out_sql, env_ref, q, db)
        top = cert.get("sql")
        has_sql = bool(isinstance(top, str) and top.strip())
        if not has_sql:
            rows.append({"qid": q["qid"], "decision": dec, "metric_kind": kind,
                         "has_answer_sql": False, "mutation": None,
                         "verdict": None, "rejected_by": None,
                         "status": "no_answer_sql"})
            continue
        c = copy.deepcopy(cert)
        c["sql"] = top + " WHERE 1=0"
        rep = verify(c, q, db)
        rows.append({"qid": q["qid"], "decision": dec, "metric_kind": kind,
                     "has_answer_sql": True, "mutation": "append ' WHERE 1=0'",
                     "verdict": rep["verdict"], "rejected_by": rep["rejected_by"],
                     "status": "REJECT" if rep["verdict"] == "REJECT"
                     else "ACCEPT"})
    rows.sort(key=lambda r: r["qid"])
    answer_bearing = [r for r in rows if r["has_answer_sql"]]
    no_sql = [r for r in rows if not r["has_answer_sql"]]
    rej = [r for r in answer_bearing if r["verdict"] == "REJECT"]
    out = {
        "mutation": "append top-level ' WHERE 1=0' to the answer SQL",
        "n_total_bases": len(rows),
        "n_answer_bearing": len(answer_bearing),
        "n_answer_bearing_reject": len(rej),
        "n_refuse_no_answer_sql": len(no_sql),
        "answer_bearing_all_reject": len(rej) == len(answer_bearing)
        and len(answer_bearing) > 0,
        "refuse_no_answer_sql_qids": sorted(r["qid"] for r in no_sql),
        "rows": rows,
    }
    with open(os.path.join(HERE, "sweep_run.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


def main():
    g = run_genuine60()
    e = run_exploits()
    s = run_sweep()
    print("genuine60: ACCEPT %d/%d  (v6aplus=%s, v6aplus_x=%s)"
          % (g["n_accept"], g["n_total"], g["v6aplus_status_counts"],
             g["v6aplus_x_status_counts"]))
    print("exploits: confirmed_all_reject=%s" % e["confirmed_all_reject"])
    print("sweep: answer_bearing %d/%d REJECT; %d REFUSE with no answer SQL"
          % (s["n_answer_bearing_reject"], s["n_answer_bearing"],
             s["n_refuse_no_answer_sql"]))


if __name__ == "__main__":
    main()
