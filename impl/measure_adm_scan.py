#!/usr/bin/env python3
"""Scan volume of the clause-(iv) anchor-pair admissibility replays.

WHY THIS FILE EXISTS (2026-08-07, round-4 finding R4-X4-5).  The paper claims
that Proposition 5.11's full-scan escape hatch has *no* instance in the pilot2
corpus, because the corpus's only clause-(iv) audits are the window-restricted
``window_realization_symdiff``.  That claim was asserted, never measured:
``measure_cost.py``'s scan-volume gate was still pinned to the retired public
track's spelling ``symdiff_audit``, so every pilot2 certificate recorded
``symdiff_scan: null`` and the exemption went unquantified.

The gate in ``measure_cost.py`` is now widened, but re-running that script would
perturb all fifteen published timings, which are gated by
``paper/tools/check_numbers.py``.  So this companion measures the scan volume
ONLY -- no wall-clock timing of verification or answering is produced, nothing
in ``impl/cost_p2.json`` is read or written -- and writes its own file.

What it records per certificate, per anchor:
  * the semantic object the replay reads and its effective-date column,
  * the table's row count,
  * ``|V(a)|``, the distinct marker dates the whole-marking-set audit would
    have to scan, and their calendar span,
  * ``|realisation days|`` under the verifier's own
    ``chk.p2_realization_days``, which is exactly what the window-restricted
    replay reads,
  * the request window's width in days.

The headline the paper's ``no instance here`` sentence rests on is
``window_bounded``: for every certificate, the realisation set the replay
touches is contained in the request window, so the cost is O(|W|) and not
O(|V(a_n)|+|V(a_d)|).  If any certificate ever reported ``window_bounded:
false``, the paper's scalability paragraph would have to change.

Read-only: opens every duckdb warehouse with ``read_only=True`` and writes
nothing but its ``--out`` path.

Usage:
    python3 impl/measure_adm_scan.py \
        --pilot pilot2 --certs impl/certs2 --out impl/adm_scan_p2.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import duckdb

HERE = pathlib.Path(__file__).resolve().parent          # .../impl
ROOT = HERE.parent                                      # repo root

sys.path.insert(0, str(HERE / "asof_verifier"))
import chk as CHKMOD  # noqa: E402  (the independent verifier's own replay code)

# Kept in sync with measure_cost.py; duplicated rather than imported so this
# script has no dependency on the timing harness.
FULL_SCAN_MODES = {"symdiff_audit"}
WINDOW_BOUNDED_MODES = {"window_realization_symdiff"}
SCAN_MODES = FULL_SCAN_MODES | WINDOW_BOUNDED_MODES


def cert_adm_modes(cert):
    blob = json.dumps(cert, ensure_ascii=False, default=str)
    return sorted(m for m in CHKMOD.ADM_MODES
                  if '"%s"' % m in blob or m in blob)


def window_pairs(win_obj):
    """Parsed [lo, hi) day intervals of a certificate window object."""
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


def graph_version(cert):
    """The version pin Gv must be built with.  pilot2 spells it graph_version;
    the retired track spelled it version.  Reading the wrong key silently yields
    an empty registry, which is how this measurement was missed the first time."""
    pin = cert.get("graph_pin") or {}
    return pin.get("graph_version") or pin.get("version")


def scan_volume(con, cert, q, domain):
    gv = CHKMOD.Gv(con, q.get("domain") or domain, graph_version(cert))
    if not (gv.anchors() or []):
        raise SystemExit("FATAL: empty anchor registry for %s at pin %r -- "
                         "refusing to report an unmeasured exemption"
                         % (q["qid"], graph_version(cert)))
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
        # What the window-restricted replay actually reads: the verifier's own
        # p2_realization_days, not a re-implementation of it.
        realised = CHKMOD.p2_realization_days(gv, arow, pairs or None)
        rows = con.execute("SELECT COUNT(*) FROM %s" % tab).fetchone()[0]
        out["anchors"].append({
            "anchor_id": aid,
            "role": ent.get("role"),
            "table": tab,
            "effective_date_column": col,
            "coverage_mode": arow.get("coverage_mode"),
            "granularity": arow.get("granularity"),
            "table_rows": int(rows),
            "distinct_markers_full": len(marks),
            "marker_span_days": ((max(marks) - min(marks)).days + 1
                                 if marks else None),
            "marker_min": min(marks).isoformat() if marks else None,
            "marker_max": max(marks).isoformat() if marks else None,
            "realisation_days_replayed": (None if realised is None
                                          else len(realised)),
            "request_window_days": window_days(ent.get("window")),
        })
    wd = [a["request_window_days"] for a in out["anchors"]
          if a["request_window_days"] is not None]
    if wd:
        out["request_window_days"] = max(wd)
    full = sum(a["distinct_markers_full"] for a in out["anchors"])
    restr = [a["realisation_days_replayed"] for a in out["anchors"]]
    out["markers_scanned_full_audit"] = full
    out["days_replayed_window_restricted"] = (
        None if any(x is None for x in restr) else sum(restr))
    # The property the paper's "no full-scan instance here" sentence needs: what
    # the replay reads is bounded by the request window, not by |V(a)|.
    out["window_bounded"] = (all(
        a["realisation_days_replayed"] is not None
        and a["request_window_days"] is not None
        and a["realisation_days_replayed"] <= a["request_window_days"]
        for a in out["anchors"]) if out["anchors"] else None)
    if out["request_window_days"] and full:
        out["full_audit_amplification"] = full / out["request_window_days"]
    return out


def domain_dirs(pilot_root):
    root = pathlib.Path(pilot_root)
    ds = sorted(p for p in (root / "domains").iterdir()
                if (p / "questions.json").is_file())
    if (root / "public" / "questions.json").is_file():
        ds.append(root / "public")
    return ds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", default=str(ROOT / "pilot2"))
    ap.add_argument("--certs", default=str(HERE / "certs2"))
    ap.add_argument("--out", default=str(HERE / "adm_scan_p2.json"))
    args = ap.parse_args()
    certs_dir = pathlib.Path(args.certs)

    records, census = [], {}
    for d in domain_dirs(args.pilot):
        questions = json.loads((d / "questions.json").read_text(encoding="utf-8"))
        con = duckdb.connect(str(d / "warehouse.duckdb"), read_only=True)
        try:
            for q in questions:
                cpath = certs_dir / ("%s.json" % q["qid"])
                if not cpath.is_file():
                    continue
                cert = json.loads(cpath.read_text(encoding="utf-8"))["certificate"]
                modes = cert_adm_modes(cert)
                for m in modes:
                    census.setdefault(m, []).append(q["qid"])
                if not (SCAN_MODES & set(modes)):
                    continue
                rec = {"qid": q["qid"], "cluster": d.name,
                       "domain": q.get("domain") or d.name,
                       "adm_modes": modes}
                rec.update(scan_volume(con, cert, q, d.name))
                records.append(rec)
        finally:
            con.close()

    full_hits = sorted(qid for m in FULL_SCAN_MODES for qid in census.get(m, []))
    bounded_hits = sorted(qid for m in WINDOW_BOUNDED_MODES
                          for qid in census.get(m, []))
    out = {
        "schema": "asofgov/adm_scan.v1",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": "impl/measure_adm_scan.py",
        "inputs": {"pilot": str(args.pilot), "certs": str(args.certs)},
        "notes": {
            "purpose": "Measure, rather than assert, that Prop 5.11's full-scan "
                       "escape hatch has no instance in this corpus.",
            "no_timing": "This script produces no wall-clock timing and does not "
                         "read or write impl/cost_p2.json; the published medians "
                         "are untouched.",
        },
        "census": {m: sorted(v) for m, v in sorted(census.items())},
        "full_scan_certificates": full_hits,
        "window_bounded_certificates": bounded_hits,
        "verdict": {
            "full_scan_instances": len(full_hits),
            "window_bounded_instances": len(bounded_hits),
            "all_window_bounded": (all(r.get("window_bounded") for r in records)
                                   if records else None),
        },
        "per_certificate": records,
    }
    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ADM-SCAN: %d certificate(s) carry a clause-(iv) replay; "
          "full-scan instances = %d; all window-bounded = %s -> %s"
          % (len(records), len(full_hits), out["verdict"]["all_window_bounded"],
             args.out))
    return 0 if len(full_hits) == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
