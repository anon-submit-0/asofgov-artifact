#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""runall.py — batch harness for the independent verifier over both corpora.

Suites:
  old51 : impl/certs/<qid>.json     × pilot/domains/* + pilot/public   (51)
  p2    : impl/certs2/<qid>.json    × pilot2/domains/*                 (60)

For each suite the verifier runs twice: with the declared-window fallback
allowed (default protocol) and with --no-declared-windows (the honest measure
of how much the corpus certifies from the registered conventions alone).
Verifier-side file: imports chk only (stdlib + duckdb underneath) — the
ci_check import-disjointness red line stays intact.
"""
from __future__ import annotations

import json
import os
import sys

import duckdb

import chk

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL = os.path.dirname(HERE)
ROOT = os.path.dirname(IMPL)

P2_DOMAINS = ["california_schools", "card_games", "codebase_community",
              "debit_card_specializing", "european_football_2", "financial",
              "formula_1", "thrombosis_prediction", "world_1"]


def suite_old51():
    out = []
    pilot = os.path.join(ROOT, "pilot")
    doms = sorted(d for d in os.listdir(os.path.join(pilot, "domains"))
                  if not d.startswith("._") and
                  os.path.isfile(os.path.join(pilot, "domains", d, "questions.json")))
    for d in doms:
        base = os.path.join(pilot, "domains", d)
        qs = json.load(open(os.path.join(base, "questions.json"), encoding="utf-8"))
        for q in qs:
            out.append((q, os.path.join(base, "warehouse.duckdb"),
                        os.path.join(IMPL, "certs", q["qid"] + ".json")))
    pub = os.path.join(pilot, "public")
    if os.path.isfile(os.path.join(pub, "questions.json")):
        for q in json.load(open(os.path.join(pub, "questions.json"), encoding="utf-8")):
            out.append((q, os.path.join(pub, "warehouse.duckdb"),
                        os.path.join(IMPL, "certs", q["qid"] + ".json")))
    return out


def suite_p2():
    out = []
    for d in P2_DOMAINS:
        base = os.path.join(ROOT, "pilot2", "domains", d)
        qs = json.load(open(os.path.join(base, "questions.json"), encoding="utf-8"))
        for q in qs:
            out.append((q, os.path.join(base, "warehouse.duckdb"),
                        os.path.join(IMPL, "certs2", q["qid"] + ".json")))
    return out


def run(name, items, allow_declared=True, verbose=True):
    n_ok = 0
    fails = []
    wsrc = {}
    for q, db, cert_path in items:
        with open(cert_path, encoding="utf-8") as fh:
            cert = json.load(fh)
        con = duckdb.connect(db, read_only=True)
        try:
            rep = chk.verify(cert, q, con, None, allow_declared_windows=allow_declared)
        finally:
            con.close()
        src = (rep.get("independence") or {}).get("window_source")
        wsrc[src] = wsrc.get(src, 0) + 1
        if rep["verdict"] == "ACCEPT":
            n_ok += 1
        else:
            first = next(c for c in rep["checks"] if c["status"] == "FAIL")
            fails.append((q["qid"], rep["rejected_by"], first["detail"][:220]))
    tag = "declared-ok" if allow_declared else "no-declared-windows"
    print("[%s / %s] ACCEPT %d/%d  window_source=%s"
          % (name, tag, n_ok, len(items), wsrc))
    if verbose:
        for f in fails:
            print("   REJECT %-10s by %-3s : %s" % f)
    return n_ok, len(items), fails


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    rc = 0
    if which in ("all", "old51"):
        ok, n, _ = run("old51", suite_old51())
        if ok != n:
            rc = 1
        run("old51", suite_old51(), allow_declared=False, verbose=False)
    if which in ("all", "p2"):
        ok, n, _ = run("p2", suite_p2())
        if ok != n:
            rc = 1
        run("p2", suite_p2(), allow_declared=False, verbose=False)
    return rc


if __name__ == "__main__":
    sys.exit(main())
