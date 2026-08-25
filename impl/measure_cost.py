#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_cost.py -- per-certificate cost measurement (E-4 / figure F-D panel (a)).

This is a RE-RUN of capabilities the artifact already has, not a new experiment.
It measures, for each of the 51 certificates in impl/certs/:

  1. verification wall-clock       -- Chk(C, G_v, D) via impl/asof_verifier/chk.py,
                                      measured BOTH as a cold process (the shape the
                                      paper's 5.9 s total was measured in: one process
                                      per certificate, paying interpreter start-up and
                                      a fresh database open) AND warm in-process (the
                                      check work alone, one duckdb connection per
                                      domain, chk imported once);
  2. certificate size in bytes     -- on-disk (indent=1, as acceptance.py writes it)
                                      and re-serialised compact (separators=(',',':'));
  3. the answering query's own     -- the SQL the certificate certifies, executed against
     execution time                  the same warehouse, measured in the same two shapes.
                                      Only the 37 SQL-emitting questions have one; the 14
                                      refusals have no answering query and are recorded
                                      with null, never with a zero.

Why both shapes: Prop 5.11 (C5 §complexity) bounds only the *probe* term of Chk by the
answering query ("窗内探测 ... 与回答查询同阶或更低"); the governance-table term is bounded
by |C| and the gov_* table sizes, NOT by the answering query. A wall-clock ratio > 1 is
therefore not a counterexample to Prop 5.11 -- it is the deployment tax, which is what
this script exists to put a number on.

Prop 5.11 also declares two probe classes that escape the bound. The full-scan one is the
whole-marking-set AM symmetric-difference replay (adm_check_mode=symdiff_audit): a dedup
anti-join over BOTH anchors' full marking sets, O(|V(a_n)|+|V(a_d)|), independent of the
request window.  CORRECTION (2026-08-07, R4-X4-5): the pilot2 corpus instantiates NO
full-scan member.  Its only clause-(iv) audits are the window-restricted
adm_check_mode=window_realization_symdiff on CARD-Q2, CARD-Q7 and EF2-Q6, whose cost is
bounded by the request window; symdiff_audit belongs to the retired public track.  The
scan-volume block below therefore fires on both spellings, and impl/measure_adm_scan.py
measures the window-restricted ones without re-timing anything here.  For every
certificate carrying either mode this script records the scan volume forced -- distinct
marker dates per anchor, the underlying table row counts, the calendar span of the
replayed history, and the width of the request window that history certifies.

Read-only: opens every duckdb warehouse with read_only=True, writes nothing but
impl/cost.json (+ optionally a --out path). Certificates, questions, warehouses, gold
files and run caches are never touched.

Usage:
    python3 impl/measure_cost.py [--repeats-cold 5] [--repeats-warm 9] [--out impl/cost.json]
    # pilot2 corpus (60 certificates, 9 public-domain warehouses):
    python3 impl/measure_cost.py --pilot pilot2 --certs impl/certs2 --out impl/cost_p2.json

The --pilot/--certs pair generalises the measured corpus (default: the original
pilot 51). Domain discovery = <pilot>/domains/* with a questions.json, plus
<pilot>/public when present. Everything else is corpus-independent.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time

import duckdb

HERE = pathlib.Path(__file__).resolve().parent          # .../impl
ROOT = HERE.parent                                      # repo root
PILOT = ROOT / "pilot"
CERTS = HERE / "certs"
CHK = HERE / "asof_verifier" / "chk.py"

sys.path.insert(0, str(HERE / "asof_verifier"))
import chk as CHKMOD  # noqa: E402  (independent verifier, imported for the warm timing)


# ---------------------------------------------------------------- helpers ---

def nearest_rank(vals, p):
    """Nearest-rank percentile (index = ceil(p*n) - 1 over the sorted sample).
    Documented explicitly so the number is reproducible; no interpolation."""
    if not vals:
        return None
    s = sorted(vals)
    k = max(1, math.ceil(p * len(s)))
    return s[k - 1]


def summarise(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": min(vals),
        "median": statistics.median(vals),
        "p90": nearest_rank(vals, 0.90),
        "max": max(vals),
        "mean": statistics.fmean(vals),
        "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
        "sum": sum(vals),
    }


def domain_dirs(pilot_root=None):
    root = pathlib.Path(pilot_root) if pilot_root else PILOT
    ds = sorted([p for p in (root / "domains").iterdir()
                 if (p / "questions.json").is_file()])
    if (root / "public" / "questions.json").is_file():
        ds.append(root / "public")
    return ds


def cert_adm_modes(cert):
    """Declared anchor-pair admissibility replay modes present in the certificate."""
    blob = json.dumps(cert, ensure_ascii=False, default=str)
    return sorted(m for m in CHKMOD.ADM_MODES if '"%s"' % m in blob or m in blob)


def window_days(win_obj):
    """Width in days of a certificate window object (None when unbounded/unparseable)."""
    w = CHKMOD.parse_window_obj(win_obj)
    if not w:
        return None
    total = 0
    for lo, hi in w:
        if lo is None or hi is None:
            return None
        total += (hi - lo).days
    return total


# -------------------------------------------------------- symdiff volume ---

# The clause-(iv) replay modes whose scan volume is worth recording: the retired
# track's whole-marking-set audit and pilot2's window-restricted successor.
SCAN_MODES = {"symdiff_audit", "window_realization_symdiff"}
# Which of them is the FULL-SCAN escape hatch of Prop 5.11, and which is bounded
# by the request window.  Getting this wrong is exactly the R4-X4-5 defect.
FULL_SCAN_MODES = {"symdiff_audit"}
WINDOW_BOUNDED_MODES = {"window_realization_symdiff"}


def _as_date(x):
    """chk.anchor_valid_dates yields date objects for DATE/TIMESTAMP columns and
    strings for VARCHAR ones; normalise so span arithmetic is well typed."""
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    try:
        return dt.date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def _hatch_sentence(records):
    """Prop 5.11's escape-hatch sentence, derived from the modes this run saw.

    Never assert a member the corpus does not instantiate: the retired track's
    whole-marking-set symdiff_audit is a full scan, pilot2's
    window_realization_symdiff is bounded by the request window, and the paper's
    scalability claim turns on which of the two is present."""
    full, bounded = {}, {}
    for r in records:
        for m in (r.get("adm_modes") or []):
            if m in FULL_SCAN_MODES:
                full.setdefault(m, []).append(r["qid"])
            elif m in WINDOW_BOUNDED_MODES:
                bounded.setdefault(m, []).append(r["qid"])
    if full:
        return ("Prop 5.11's full-scan escape hatch IS instantiated here: "
                + "; ".join("%s on %s" % (m, ", ".join(sorted(q)))
                            for m, q in sorted(full.items())) + ".")
    if bounded:
        return ("Prop 5.11's full-scan escape hatch has NO instance in this "
                "corpus. Its only clause-(iv) audits are window-restricted and "
                "therefore inside the bound: "
                + "; ".join("%s on %s" % (m, ", ".join(sorted(q)))
                            for m, q in sorted(bounded.items()))
                + ". Their scan volume is in the symdiff_scan field of each "
                "record (see also impl/measure_adm_scan.py).")
    return ("No clause-(iv) admissibility replay is instantiated in this corpus, "
            "so Prop 5.11's escape hatch is vacuous here.")


def symdiff_scan_volume(con, cert, q, domain):
    """For a certificate whose AM admissibility replay is symdiff_audit, record the
    scan the replay forces: V(a) per anchor (chk.anchor_valid_dates: SELECT DISTINCT
    <effective_date> FROM <semantic_object>, a full-table scan independent of the
    request window), the table's row count, the calendar span of the marker set, and
    the width of the request window being certified."""
    # R4-X4-5: pilot2 spells the pin graph_version, the retired track version.
    # Reading only the old key silently yields an EMPTY registry, i.e. a
    # scan-volume record with no anchors that looks like a measurement.
    pin = cert.get("graph_pin") or {}
    gv = CHKMOD.Gv(con, q.get("domain") or domain,
                   pin.get("graph_version") or pin.get("version"))
    out = {"anchors": [], "request_window_days": None, "note": ""}
    if not (gv.anchors() or []):
        out["note"] = ("anchor registry empty at this pin: scan volume not "
                       "measured (see impl/measure_adm_scan.py)")
        return out
    seen = set()
    for ent in (cert.get("anchors") or []):
        aid = ent.get("anchor_id")
        if not aid or aid in seen:
            continue
        seen.add(aid)
        arow = gv.anchor(aid)
        if not arow:
            continue
        tab = gv.qualify(arow.get("semantic_object"))
        col = arow.get("effective_date")
        if not tab or not col:
            continue
        t0 = time.perf_counter()
        marks = {d for d in (_as_date(m)
                             for m in CHKMOD.anchor_valid_dates(gv, arow))
                 if d is not None}
        t1 = time.perf_counter()
        rows = con.execute("SELECT COUNT(*) FROM %s" % tab).fetchone()[0]
        span = None
        if marks:
            span = (max(marks) - min(marks)).days + 1
        out["anchors"].append({
            "anchor_id": aid, "role": ent.get("role"),
            "table": tab, "effective_date_column": col,
            "table_rows": int(rows),
            "distinct_markers": len(marks),
            "marker_span_days": span,
            "marker_min": min(marks).isoformat() if marks else None,
            "marker_max": max(marks).isoformat() if marks else None,
            "replay_s": t1 - t0,
        })
    wd = [window_days(e.get("window")) for e in (cert.get("anchors") or [])]
    wd = [x for x in wd if x is not None]
    if wd:
        out["request_window_days"] = max(wd)
    tot = sum(a["distinct_markers"] for a in out["anchors"])
    if out["request_window_days"]:
        out["scan_amplification"] = tot / out["request_window_days"]
    return out


# ------------------------------------------------------------ timing runs ---

ANSWER_RUNNER = r'''
import sys, json, duckdb
db, path = sys.argv[1], sys.argv[2]
sql = json.load(open(path, encoding="utf-8"))["sql"]
con = duckdb.connect(db, read_only=True)
try:
    con.execute(sql).fetchone()
finally:
    con.close()
'''


def time_cold(cmd, repeats):
    ts = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
        ts.append(time.perf_counter() - t0)
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats-cold", type=int, default=5)
    ap.add_argument("--repeats-warm", type=int, default=9)
    ap.add_argument("--out", default=str(HERE / "cost.json"))
    ap.add_argument("--pilot", default=str(PILOT),
                    help="corpus root holding domains/ (default: pilot)")
    ap.add_argument("--certs", default=str(CERTS),
                    help="certificate directory (default: impl/certs)")
    args = ap.parse_args()
    certs_dir = pathlib.Path(args.certs)

    runner = HERE / ".measure_answer_runner.py"
    runner.write_text(ANSWER_RUNNER, encoding="utf-8")
    nullprog = HERE / ".measure_null_runner.py"
    nullprog.write_text("import duckdb\n", encoding="utf-8")

    # interpreter + duckdb-import floor: how much of a cold process is not our work
    floor = time_cold([sys.executable, str(nullprog)], args.repeats_cold * 3)

    records = []
    for d in domain_dirs(args.pilot):
        questions = json.loads((d / "questions.json").read_text(encoding="utf-8"))
        db = str(d / "warehouse.duckdb")
        qpath = str(d / "questions.json")
        con = duckdb.connect(db, read_only=True)
        try:
            for q in questions:
                qid = q["qid"]
                cpath = certs_dir / ("%s.json" % qid)
                env = json.loads(cpath.read_text(encoding="utf-8"))
                cert = env["certificate"]
                sql = env.get("sql")

                # ---- verdict (untimed, captured once) ----
                proc = subprocess.run(
                    [sys.executable, str(CHK), "--cert", str(cpath),
                     "--questions", qpath, "--qid", qid, "--db", db, "--json"],
                    capture_output=True, text=True, check=False)
                rep = json.loads(proc.stdout) if proc.stdout.strip() else {}

                # ---- cold verification ----
                vcold = time_cold(
                    [sys.executable, str(CHK), "--cert", str(cpath),
                     "--questions", qpath, "--qid", qid, "--db", db],
                    args.repeats_cold)

                # ---- warm verification (check work only) ----
                vwarm = []
                for _ in range(args.repeats_warm):
                    t0 = time.perf_counter()
                    CHKMOD.verify(env, q, con, None)
                    vwarm.append(time.perf_counter() - t0)

                # ---- answering query ----
                acold = awarm = None
                aval = None
                if sql:
                    acold = time_cold(
                        [sys.executable, str(runner), db, str(cpath)],
                        args.repeats_cold)
                    awarm = []
                    for _ in range(args.repeats_warm):
                        t0 = time.perf_counter()
                        row = con.execute(sql).fetchone()
                        awarm.append(time.perf_counter() - t0)
                        aval = None if row is None else row[0]

                adm = cert_adm_modes(cert)
                sym = None
                # R4-X4-5: accept BOTH spellings.  The ADM_MODES rename during the
                # pilot2 port left this gate pinned to the retired track's
                # whole-marking-set spelling, so the pilot2 corpus's three
                # clause-(iv) audits recorded symdiff_scan=null and the exemption
                # went unmeasured.
                if SCAN_MODES & set(adm):
                    sym = symdiff_scan_volume(con, cert, q, d.name)

                vw_med = statistics.median(vwarm)
                vc_med = statistics.median(vcold)
                aw_med = statistics.median(awarm) if awarm else None
                ac_med = statistics.median(acold) if acold else None

                records.append({
                    "qid": qid,
                    "domain": q.get("domain") or d.name,
                    "cluster": d.name,
                    "output_kind": "sql" if sql else "refusal",
                    "refusal": env.get("refusal"),
                    "decision": (cert.get("disclosure") or {}).get("decision"),
                    "verdict": rep.get("verdict"),
                    "rejected_by": rep.get("rejected_by"),
                    "n_anchors": len(cert.get("anchors") or []),
                    "n_probes": len(cert.get("probes") or []),
                    "adm_modes": adm,
                    "cert_bytes_file": cpath.stat().st_size,
                    "cert_bytes_compact": len(json.dumps(
                        env, ensure_ascii=False, separators=(",", ":"),
                        default=str).encode("utf-8")),
                    "sql_bytes": len(sql.encode("utf-8")) if sql else None,
                    "answer_value": float(aval) if isinstance(aval, (int, float)) else None,
                    "verify_cold_s": vcold,
                    "verify_cold_median_s": vc_med,
                    "verify_warm_s": vwarm,
                    "verify_warm_median_s": vw_med,
                    "answer_cold_s": acold,
                    "answer_cold_median_s": ac_med,
                    "answer_warm_s": awarm,
                    "answer_warm_median_s": aw_med,
                    "ratio_warm": (vw_med / aw_med) if aw_med else None,
                    "ratio_cold": (vc_med / ac_med) if ac_med else None,
                    "symdiff_scan": sym,
                })
                print("  %-14s %-18s verify_cold=%.4fs warm=%.5fs  answer_warm=%s  "
                      "cert=%dB%s"
                      % (qid, rep.get("verdict"), vc_med, vw_med,
                         ("%.5fs" % aw_med) if aw_med else "n/a",
                         cpath.stat().st_size,
                         "  [symdiff]" if sym else ""),
                      flush=True)
        finally:
            con.close()

    runner.unlink(missing_ok=True)
    nullprog.unlink(missing_ok=True)

    sql_recs = [r for r in records if r["output_kind"] == "sql"]
    agg = {
        "n_certificates": len(records),
        "n_accept": sum(1 for r in records if r["verdict"] == "ACCEPT"),
        "n_sql": len(sql_recs),
        "n_refusal": sum(1 for r in records if r["output_kind"] == "refusal"),
        "percentile_method": "nearest-rank, index = ceil(p*n) - 1 over the sorted sample",
        "verify_cold_s": summarise([r["verify_cold_median_s"] for r in records]),
        "verify_warm_s": summarise([r["verify_warm_median_s"] for r in records]),
        "answer_cold_s": summarise([r["answer_cold_median_s"] for r in sql_recs]),
        "answer_warm_s": summarise([r["answer_warm_median_s"] for r in sql_recs]),
        "ratio_warm": summarise([r["ratio_warm"] for r in sql_recs]),
        "ratio_cold": summarise([r["ratio_cold"] for r in sql_recs]),
        "cert_bytes_file": summarise([r["cert_bytes_file"] for r in records]),
        "cert_bytes_compact": summarise([r["cert_bytes_compact"] for r in records]),
        "sql_bytes": summarise([r["sql_bytes"] for r in sql_recs]),
        "cold_process_floor_s": summarise(floor),
    }
    # aggregate ratio of medians (a second, less outlier-sensitive framing)
    if agg["verify_warm_s"] and agg["answer_warm_s"]:
        agg["ratio_of_medians_warm"] = (agg["verify_warm_s"]["median"]
                                        / agg["answer_warm_s"]["median"])
    if agg["verify_cold_s"] and agg["answer_cold_s"]:
        agg["ratio_of_medians_cold"] = (agg["verify_cold_s"]["median"]
                                        / agg["answer_cold_s"]["median"])
    agg["verify_cold_total_s"] = agg["verify_cold_s"]["sum"]

    out = {
        "schema": "asofgov/cost.v1",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": "impl/measure_cost.py",
        "measurement_notes": {
            # R1-F6 (2026-08-06): both corpus-dependent numbers below are
            # interpolated from THIS run's aggregate, never hard-coded (the
            # old literals "5.9 s" / "The 14" described the legacy 51-cert
            # corpus and went stale on pilot2).
            "cold": "one OS process per measurement: interpreter start-up + import duckdb "
                    "+ fresh read-only database open + the work. This is the shape the "
                    "%.2f s total in the evaluation section was measured in."
                    % agg["verify_cold_total_s"],
            "warm": "work only: chk imported once, one read-only duckdb connection per "
                    "cluster held open, median over repeats.",
            "answering_query": "the SQL the certificate certifies, run on the same "
                               "warehouse. The %d refusal certificates have no answering "
                               "query: recorded as null, never as zero."
                               % agg["n_refusal"],
            # R4-X4-5 (2026-08-07): the escape-hatch sentence used to assert
            # symdiff_audit unconditionally.  That is FALSE on pilot2 -- the port
            # renamed the clause-(iv) member to the window-restricted
            # window_realization_symdiff and no full-scan member survives.  Derive
            # the sentence from the modes THIS run actually saw.
            "prop_5_11_scope": "Prop 5.11 bounds the in-window probe term of Chk by the "
                               "answering query and bounds the governance-table term by "
                               "|C| and the gov_* table sizes instead. An end-to-end "
                               "wall-clock ratio > 1 is the deployment tax, not a "
                               "counterexample. " + _hatch_sentence(records),
        },
        "env": {
            "python": sys.version.split()[0],
            "duckdb": duckdb.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "repeats_cold": args.repeats_cold,
            "repeats_warm": args.repeats_warm,
        },
        "aggregate": agg,
        "per_certificate": records,
    }
    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n=== aggregate ===")
    print("certificates          : %d (ACCEPT %d)" % (agg["n_certificates"], agg["n_accept"]))
    print("verify cold  total    : %.2f s" % agg["verify_cold_total_s"])
    print("verify cold  med/p90/max : %.4f / %.4f / %.4f s"
          % (agg["verify_cold_s"]["median"], agg["verify_cold_s"]["p90"],
             agg["verify_cold_s"]["max"]))
    print("cold process floor    : %.4f s (import duckdb only)"
          % agg["cold_process_floor_s"]["median"])
    print("verify warm  med/p90/max : %.5f / %.5f / %.5f s"
          % (agg["verify_warm_s"]["median"], agg["verify_warm_s"]["p90"],
             agg["verify_warm_s"]["max"]))
    print("answer warm  med/p90/max : %.5f / %.5f / %.5f s"
          % (agg["answer_warm_s"]["median"], agg["answer_warm_s"]["p90"],
             agg["answer_warm_s"]["max"]))
    print("ratio warm   med/p90/max : %.1fx / %.1fx / %.1fx  (n=%d SQL questions)"
          % (agg["ratio_warm"]["median"], agg["ratio_warm"]["p90"],
             agg["ratio_warm"]["max"], agg["ratio_warm"]["n"]))
    print("ratio cold   med/max     : %.2fx / %.2fx"
          % (agg["ratio_cold"]["median"], agg["ratio_cold"]["max"]))
    print("cert bytes   med/min/max : %d / %d / %d B"
          % (agg["cert_bytes_file"]["median"], agg["cert_bytes_file"]["min"],
             agg["cert_bytes_file"]["max"]))
    print("SQL bytes    med/min/max : %d / %d / %d B"
          % (agg["sql_bytes"]["median"], agg["sql_bytes"]["min"], agg["sql_bytes"]["max"]))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
