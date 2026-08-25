#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable runner for the three pilot2 CI gates.

The gate scripts (pilot2/ci/{leak_check,nondegeneracy_gate,witness_pairs}.py)
hardcode the authors' pilot2 path in a module constant ROOT.  This wrapper
imports each frozen file unmodified, overrides ROOT (and witness_pairs.WORK,
which is derived from ROOT at import time), and calls its main().

  leak_check          static field-partition + import-disjointness audit (no DB)
  nondegeneracy_gate  reads build/dualpath_report.json + questions (no DB)
  witness_pairs       needs the 9 rebuilt warehouses (copies them to a work dir
                      and mutates only the copies)

Usage:  python3 scripts/run_ci_portable.py [leak|nd|witness ...]  (default: all)
Each gate rewrites its pilot2/ci/*_report.json; reproduce_all.sh diffs those
against the committed reports.
"""
import importlib
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
P2 = str(REPO / "pilot2")
sys.path.insert(0, str(REPO / "pilot2" / "ci"))

GATES = {"leak": "leak_check", "nd": "nondegeneracy_gate", "witness": "witness_pairs"}


def run(gate: str) -> int:
    mod = importlib.import_module(GATES[gate])
    mod.ROOT = P2
    if hasattr(mod, "WORK"):
        mod.WORK = os.path.join(P2, "ci", "witness_work")
        os.makedirs(mod.WORK, exist_ok=True)
    print(f"== {GATES[gate]} ==", flush=True)
    rc = mod.main()
    return int(rc or 0)


def main() -> int:
    picks = sys.argv[1:] or list(GATES)
    bad = [p for p in picks if p not in GATES]
    if bad:
        print(f"unknown gate(s) {bad}; choose from {list(GATES)}")
        return 2
    rc = 0
    for p in picks:
        rc |= run(p)
    return rc


if __name__ == "__main__":
    sys.exit(main())
