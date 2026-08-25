#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s5_measure.py — S5 cost-model scalability sweep (deterministic, zero LLM).

Governing prereg: PREREG_poststudy2_20260823.md,
sha256 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669.

Row-scale axis (mandatory): the six substrates under work/rowscale/
(built by s5_build_substrates.py; scaling rule documented there).  On
each substrate the FROZEN compiler (impl/asof_compiler, imported
read-only, never copied or edited) recompiles the 8 financial
questions' certificates; then per certificate:

  * warm verify   : chk.verify(env, q, con, None) — chk imported once,
                    one read-only duckdb connection per substrate held
                    open — median over WARM_REPEATS runs (mirrors
                    impl/measure_cost.py's warm shape; its default
                    repeats_warm=9 >= the prereg'd minimum 5).
  * warm answer   : con.execute(sql).fetchone() on the same connection,
                    median over WARM_REPEATS runs (SQL-emitting
                    certificates only; refusals recorded null, never 0).
  * verdict       : one untimed chk.verify call, captured first (this
                    also serves as the warm-up the cold/verdict
                    subprocess provided in measure_cost.py).
  * full-scan audit census: exactly impl/measure_adm_scan.py's gate —
    modes found in the certificate blob against chk.ADM_MODES;
    FULL_SCAN_MODES={'symdiff_audit'} (Prop 5.11's escape hatch),
    WINDOW_BOUNDED_MODES={'window_realization_symdiff'}; any
    certificate carrying either gets the measure_adm_scan-style
    window_bounded record via chk.p2_realization_days.

Window-span axis (stretch goal): world_1 (84-month authored history,
2020-01..2026-12) with request windows spanning {1,3,6,12,24,48}
months.  Variant questions are W1-Q4's frozen dict with only qid /
window_request / windows / expected_kind swapped: the window is a
month_token_range ending at the hull end 2026-12 with the given span,
entirely inside validity, so the decision is ANSWER (no trim) and the
certificate verifies against the same frozen graph.  The variants are
cost probes, not scored gold questions: gold_sql/gold_value are set to
null and never fabricated.

Cold-process timing is NOT re-measured here: the prereg operationalises
the §3 cost claims through the warm shape (the task's 'median of >=5
runs each, warm process'), and the cold shape's interpreter+import
floor is row-scale-independent by construction.

Emits: s5_cost_sweep.json (all numbers flow from here; the report is
rendered from this JSON).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import statistics
import sys
import time

import duckdb

S5 = pathlib.Path(__file__).resolve().parent
WORK = S5 / "work"
IMPL = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/impl")
sys.path.insert(0, str(IMPL))
sys.path.insert(0, str(IMPL / "asof_verifier"))
from asof_compiler import compile_question  # noqa: E402  (frozen, read-only)
import chk as CHKMOD  # noqa: E402          (frozen verifier)

WARM_REPEATS = 9          # measure_cost.py default; prereg minimum is 5
PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"

# Provenance re-assert added 2026-08-23 (fix_provenance.py; see
# s5_cost_sweep.json "provenance_correction"): the original run
# cited a corrupted 62-char sha because nothing checked the
# constant against the frozen prereg on disk.  A future re-run
# now refuses on mismatch.
PREREG_PATH = S5.parent / "PREREG_poststudy2_20260823.md"
_PREREG_DISK_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
if _PREREG_DISK_SHA != PREREG_SHA:
    raise SystemExit(
        "PREREG sha mismatch: disk %s != constant %s -- refusing to run"
        % (_PREREG_DISK_SHA, PREREG_SHA))

# kept in sync with impl/measure_adm_scan.py
FULL_SCAN_MODES = {"symdiff_audit"}
WINDOW_BOUNDED_MODES = {"window_realization_symdiff"}
SCAN_MODES = FULL_SCAN_MODES | WINDOW_BOUNDED_MODES

ROW_POINTS = ["scale_0125", "scale_025", "scale_050",
              "scale_100", "scale_200", "scale_400"]
ROW_FACTORS = {"scale_0125": 0.125, "scale_025": 0.25, "scale_050": 0.5,
               "scale_100": 1.0, "scale_200": 2.0, "scale_400": 4.0}
SPANS = [1, 3, 6, 12, 24, 48]


def cert_adm_modes(cert):
    blob = json.dumps(cert, ensure_ascii=False, default=str)
    return sorted(m for m in CHKMOD.ADM_MODES
                  if '"%s"' % m in blob or m in blob)


def window_pairs(win_obj):
    w = CHKMOD.parse_window_obj(win_obj)
    return w or []


def window_days(win_obj):
    total = 0
    for lo, hi in window_pairs(win_obj):
        if lo is None or hi is None:
            return None
        total += (hi - lo).days
    return total


def _as_date(x):
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    try:
        return dt.date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def scan_volume(con, cert, q, domain):
    """measure_adm_scan.py's per-certificate record, verbatim logic."""
    pin = cert.get("graph_pin") or {}
    gv = CHKMOD.Gv(con, q.get("domain") or domain,
                   pin.get("graph_version") or pin.get("version"))
    if not (gv.anchors() or []):
        raise SystemExit("FATAL: empty anchor registry for %s" % q["qid"])
    out = {"anchors": [], "request_window_days": None}
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
        marks = {d for d in (_as_date(m)
                             for m in CHKMOD.anchor_valid_dates(gv, arow))
                 if d is not None}
        pairs = window_pairs(ent.get("window"))
        realised = CHKMOD.p2_realization_days(gv, arow, pairs or None)
        rows = con.execute("SELECT COUNT(*) FROM %s" % tab).fetchone()[0]
        out["anchors"].append({
            "anchor_id": aid, "role": ent.get("role"), "table": tab,
            "table_rows": int(rows),
            "distinct_markers_full": len(marks),
            "realisation_days_replayed": (None if realised is None
                                          else len(realised)),
            "request_window_days": window_days(ent.get("window")),
        })
    wd = [a["request_window_days"] for a in out["anchors"]
          if a["request_window_days"] is not None]
    if wd:
        out["request_window_days"] = max(wd)
    out["window_bounded"] = (all(
        a["realisation_days_replayed"] is not None
        and a["request_window_days"] is not None
        and a["realisation_days_replayed"] <= a["request_window_days"]
        for a in out["anchors"]) if out["anchors"] else None)
    return out


def measure_one(env, q, con, domain):
    """Warm verify + warm answer + adm census for one compiled envelope."""
    cert = env["certificate"]
    rep = CHKMOD.verify(env, q, con, None)   # untimed verdict + warm-up
    sql = env.get("sql")
    vwarm = []
    for _ in range(WARM_REPEATS):
        t0 = time.perf_counter()
        CHKMOD.verify(env, q, con, None)
        vwarm.append(time.perf_counter() - t0)
    awarm = None
    aval = None
    if sql:
        con.execute(sql).fetchone()          # warm-up
        awarm = []
        for _ in range(WARM_REPEATS):
            t0 = time.perf_counter()
            row = con.execute(sql).fetchone()
            awarm.append(time.perf_counter() - t0)
            aval = None if row is None else row[0]
    adm = cert_adm_modes(cert)
    sym = scan_volume(con, cert, q, domain) if (SCAN_MODES & set(adm)) else None
    vw_med = statistics.median(vwarm)
    aw_med = statistics.median(awarm) if awarm else None
    return {
        "qid": q["qid"],
        "output_kind": "sql" if sql else "refusal",
        "refusal": env.get("refusal"),
        "decision": (cert.get("disclosure") or {}).get("decision"),
        "verdict": rep.get("verdict"),
        "rejected_by": rep.get("rejected_by"),
        "n_anchors": len(cert.get("anchors") or []),
        "n_probes": len(cert.get("probes") or []),
        "adm_modes": adm,
        "n_full_scan_audits": sum(1 for m in adm if m in FULL_SCAN_MODES),
        "n_window_bounded_audits": sum(1 for m in adm
                                       if m in WINDOW_BOUNDED_MODES),
        "cert_bytes_compact": len(json.dumps(
            env, ensure_ascii=False, separators=(",", ":"),
            default=str).encode("utf-8")),
        "answer_value": (float(aval) if isinstance(aval, (int, float))
                         else (str(aval) if aval is not None else None)),
        "verify_warm_s": vwarm,
        "verify_warm_median_s": vw_med,
        "answer_warm_s": awarm,
        "answer_warm_median_s": aw_med,
        "ratio_warm": (vw_med / aw_med) if aw_med else None,
        "symdiff_scan": sym,
    }


def month_sub(tok, k):
    y, m = int(tok[:4]), int(tok[5:7])
    i = y * 12 + (m - 1) - k
    return "%04d-%02d" % (i // 12, i % 12 + 1)


def main():
    manifest = json.loads((WORK / "substrates_manifest.json")
                          .read_text(encoding="utf-8"))
    sub_facts = {s["label"]: s for s in manifest["substrates"]}

    # ---------------- row-scale axis ----------------
    row_axis = []
    for label in ROW_POINTS:
        ddir = WORK / "rowscale" / label / "financial"
        qs = json.loads((ddir / "questions.json").read_text(encoding="utf-8"))
        point = {"label": label, "row_factor": ROW_FACTORS[label],
                 "trans_rows": sub_facts[label]["trans_rows"],
                 "reachable": True, "unreachable_reason": None,
                 "per_certificate": []}
        if sub_facts[label]["hull_losses_vs_frozen_questions"]:
            point["reachable"] = False
            point["unreachable_reason"] = ("gold anchors vanished under "
                                           "sampling: hull losses %r" %
                                           sub_facts[label]
                                           ["hull_losses_vs_frozen_questions"])
            row_axis.append(point)
            continue
        certs_dir = WORK / "rowscale" / label / "certs"
        certs_dir.mkdir(exist_ok=True)
        con = duckdb.connect(str(ddir / "warehouse.duckdb"), read_only=True)
        try:
            for q in qs:
                env = compile_question(q, ddir)   # frozen compiler
                (certs_dir / ("%s.json" % q["qid"])).write_text(
                    json.dumps(env, ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8")
                rec = measure_one(env, q, con, "financial")
                point["per_certificate"].append(rec)
                print("  %s %-8s %-10s %-8s verify=%.5fs answer=%s" % (
                    label, rec["qid"], rec["decision"], rec["verdict"],
                    rec["verify_warm_median_s"],
                    ("%.5fs" % rec["answer_warm_median_s"])
                    if rec["answer_warm_median_s"] else "n/a"), flush=True)
        finally:
            con.close()
        sqls = [r for r in point["per_certificate"] if r["output_kind"] == "sql"]
        point["verify_warm_median_over_certs_s"] = statistics.median(
            [r["verify_warm_median_s"] for r in point["per_certificate"]])
        point["answer_warm_median_over_certs_s"] = statistics.median(
            [r["answer_warm_median_s"] for r in sqls])
        point["paired_ratio_median"] = statistics.median(
            [r["ratio_warm"] for r in sqls])
        point["paired_ratio_min"] = min(r["ratio_warm"] for r in sqls)
        point["paired_ratio_max"] = max(r["ratio_warm"] for r in sqls)
        point["n_full_scan_audits"] = sum(r["n_full_scan_audits"]
                                          for r in point["per_certificate"])
        point["n_window_bounded_audits"] = sum(
            r["n_window_bounded_audits"] for r in point["per_certificate"])
        point["adm_census"] = sorted({m for r in point["per_certificate"]
                                      for m in r["adm_modes"]})
        row_axis.append(point)

    # ---------------- window-span axis (stretch) ----------------
    wdir = WORK / "winspan" / "world_1"
    w1qs = json.loads((wdir / "questions.json").read_text(encoding="utf-8"))
    q4 = next(q for q in w1qs if q["qid"] == "W1-Q4")
    span_axis = []
    certs_dir = WORK / "winspan" / "certs"
    certs_dir.mkdir(exist_ok=True)
    con = duckdb.connect(str(wdir / "warehouse.duckdb"), read_only=True)
    try:
        for span in SPANS:
            q = json.loads(json.dumps(q4))
            lo = month_sub("2026-12", span - 1)
            q["qid"] = "W1-SPAN-%02dM" % span
            wr = {"kind": "month_token_range", "lo": lo, "hi": "2026-12"}
            q["window_request"] = wr
            q["windows"] = {"requested": dict(wr), "effective": dict(wr)}
            q["expected_kind"] = "value"
            q["rewrite"] = None
            q["gold_sql"] = None
            q["gold_value"] = None
            env = compile_question(q, wdir)
            (certs_dir / ("%s.json" % q["qid"])).write_text(
                json.dumps(env, ensure_ascii=False, indent=1, default=str),
                encoding="utf-8")
            rec = measure_one(env, q, con, "world_1")
            rec["span_months"] = span
            rec["window_lo"] = lo
            rec["window_hi"] = "2026-12"
            span_axis.append(rec)
            print("  span=%02dm %-8s %-8s verify=%.5fs answer=%.5fs ratio=%.1fx"
                  % (span, rec["decision"], rec["verdict"],
                     rec["verify_warm_median_s"], rec["answer_warm_median_s"],
                     rec["ratio_warm"]), flush=True)
    finally:
        con.close()

    # ---------------- adjudication ----------------
    reach = [p for p in row_axis if p["reachable"]]
    med = {p["label"]: p["verify_warm_median_over_certs_s"] for p in reach}
    order = [p for p in ROW_POINTS if p in med]
    monotone = all(med[a] <= med[b] for a, b in zip(order, order[1:]))
    growth_4x = (med.get("scale_400") / med.get("scale_100")
                 if med.get("scale_400") and med.get("scale_100") else None)
    p1 = {
        "prediction": "warm verify median is monotone non-decreasing in row "
                      "scale with growth at most linear (4x rows => <=4x "
                      "median verify time)",
        "statistic": "median over the 8 financial certificates of the "
                     "per-certificate warm-verify medians, per scale point",
        "medians_s": {k: med[k] for k in order},
        "monotone_non_decreasing": monotone,
        "growth_100_to_400": growth_4x,
        "growth_at_most_linear": (growth_4x is not None and growth_4x <= 4.0),
        "verdict": ("MET" if monotone and growth_4x is not None
                    and growth_4x <= 4.0 else "MISS"),
    }
    p2_points = {p["label"]: {"median": p["paired_ratio_median"],
                              "min": p["paired_ratio_min"],
                              "max": p["paired_ratio_max"]} for p in reach}
    p2_med_ok = all(1.0 <= v["median"] <= 60.0 for v in p2_points.values())
    p2_all_ok = all(1.0 <= v["min"] and v["max"] <= 60.0
                    for v in p2_points.values())
    p2 = {
        "prediction": "paired verify/answer ratio stays inside [1x, 60x] at "
                      "every reachable scale point",
        "statistic": "per scale point, the median over the 6 SQL-emitting "
                     "certificates of (verify_warm_median / "
                     "answer_warm_median); per-certificate min/max also "
                     "reported and adjudicated as the stricter reading",
        "per_point": p2_points,
        "median_in_band_at_every_point": p2_med_ok,
        "every_certificate_in_band_at_every_point": p2_all_ok,
        "verdict": "MET" if p2_med_ok else "MISS",
        "strict_all_certificates_verdict": "MET" if p2_all_ok else "MISS",
    }
    p3_counts = {p["label"]: p["n_full_scan_audits"] for p in reach}
    wb_ok = all((r["symdiff_scan"] is None or
                 r["symdiff_scan"].get("window_bounded") is not False)
                for p in reach for r in p["per_certificate"])
    p3 = {
        "prediction": "zero full-scan audits at every scale (all clause-(iv) "
                      "audits window-bounded, as at 1x)",
        "full_scan_audits_per_point": p3_counts,
        "window_bounded_audits_per_point": {p["label"]:
                                            p["n_window_bounded_audits"]
                                            for p in reach},
        "all_window_bounded": wb_ok,
        "note": "the financial certificates carry no clause-(iv) replay at "
                "any scale (the corpus's three window_realization_symdiff "
                "audits live on CARD-Q2/CARD-Q7/EF2-Q6, outside this domain); "
                "zero full-scan audits is therefore confirmed by census, and "
                "the window-bounded clause is vacuously true here"
                if all(v == 0 for v in p3_counts.values()) else "",
        "verdict": ("MET" if all(v == 0 for v in p3_counts.values()) and wb_ok
                    else "MISS"),
    }

    out = {
        "schema": "asofgov/s5_cost_sweep.v1",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": "pilot2/poststudy2_20260823/s5/s5_measure.py",
        "prereg": {"file": "PREREG_poststudy2_20260823.md",
                   "sha256": PREREG_SHA, "study": "S5"},
        "methodology": {
            "compiler": "impl/asof_compiler (frozen, imported read-only)",
            "verifier": "impl/asof_verifier/chk.py (frozen)",
            "warm_repeats": WARM_REPEATS,
            "warm_shape": "mirrors impl/measure_cost.py: chk imported once, "
                          "one read-only duckdb connection per substrate held "
                          "open, median over repeats; untimed verdict call "
                          "first (doubles as warm-up)",
            "cold_shape": "not re-measured: prereg operationalises the warm "
                          "shape; the cold interpreter+import floor is "
                          "row-scale-independent",
            "adm_census": "impl/measure_adm_scan.py gate: FULL_SCAN_MODES="
                          "{symdiff_audit}, WINDOW_BOUNDED_MODES="
                          "{window_realization_symdiff}",
            "compile_identity_check_at_1x": "the 8 certificates recompiled on "
                          "the 1x substrate are json-identical to the frozen "
                          "impl/certs2/FIN-*.json (verified before this run)",
        },
        "env": {"python": sys.version.split()[0], "duckdb": duckdb.__version__,
                "platform": platform.platform(),
                "machine": platform.machine(), "cpu_count": os.cpu_count()},
        "substrates_manifest": manifest,
        "row_scale_axis": row_axis,
        "window_span_axis": {
            "status": "REACHED",
            "base_question": "W1-Q4 (w1.history_rows_range), 84-month "
                             "authored history 2020-01..2026-12",
            "variant_rule": "month_token_range ending 2026-12, span in "
                            "{1,3,6,12,24,48} months, inside validity; "
                            "cost probes only, gold never fabricated",
            "per_span": span_axis,
        },
        "predictions": {"S5-P1": p1, "S5-P2": p2, "S5-P3": p3},
    }
    (S5 / "s5_cost_sweep.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nS5-P1:", p1["verdict"], "| S5-P2:", p2["verdict"],
          "| S5-P3:", p3["verdict"])
    print("wrote", S5 / "s5_cost_sweep.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
