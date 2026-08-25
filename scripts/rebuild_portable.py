#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable wrapper around pilot2/build/build_all.py.

The frozen build scripts hardcode the authors' machine paths in
pilot2/build/lib_build.py (ROOT, BIRD, W1_SRC_DUCK).  This wrapper leaves
every frozen file byte-identical and instead overrides those three module
constants at run time, then delegates to build_all.main() unchanged.

Environment (all optional):
  ASOF_BIRD_DIR   directory containing the BIRD dev databases
                  (<dir>/<db>/<db>.sqlite for the 8 BIRD-derived domains)
                  default: <repo>/data/bird/dev_20240627/dev_databases
  ASOF_W1_BRIDGE  path to the world_1 legacy bridge duckdb
                  (table country_v2026_01 = Spider dev world_1.country
                  original values; build with scripts/rebuild_world1_bridge.py)
                  default: <repo>/pilot/public/warehouse.duckdb

Usage:
  python3 scripts/rebuild_portable.py            # all 9 domains + gold materialization
  python3 scripts/rebuild_portable.py financial  # a single domain (no gold step)

After a full rebuild the script re-checks every rebuilt frozen file
(domains/*/questions.json, domains/*/gov_seed/*.jsonl) against
pilot2/FREEZE_pilot2_arms.json, including the aggregate hash.  A FAIL means
your environment reproduced different bytes (usually a duckdb version skew);
the paper's numbers were produced under the versions pinned in
requirements.txt.
"""
import hashlib
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
P2 = REPO / "pilot2"
sys.path.insert(0, str(P2 / "build"))

import lib_build as L  # noqa: E402  (frozen file, imported unmodified)

L.ROOT = str(P2)
L.BIRD = os.environ.get(
    "ASOF_BIRD_DIR", str(REPO / "data" / "bird" / "dev_20240627" / "dev_databases"))
L.W1_SRC_DUCK = os.environ.get(
    "ASOF_W1_BRIDGE", str(REPO / "pilot" / "public" / "warehouse.duckdb"))

import build_all  # noqa: E402  (frozen file; reads L.* at call time)


def freeze_check() -> int:
    fz = json.loads((P2 / "FREEZE_pilot2_arms.json").read_text(encoding="utf-8"))
    bad = []
    for rel, want in fz["files"].items():
        if rel.startswith("~") or rel.startswith(".."):
            continue  # llmhub / run_pilot.py: not touched by the rebuild
        if not (rel.startswith("domains/")):
            continue  # prompt_pack + PREREG are not rebuilt here
        p = (P2 / rel).resolve()
        got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
        if got != want:
            bad.append(rel)
    agg_files = sorted(str(x) for x in
                       list(P2.glob("domains/*/questions.json"))
                       + list(P2.glob("domains/*/gov_seed/*.jsonl"))
                       if "/._" not in str(x))
    h = hashlib.sha256()
    for f in agg_files:
        h.update(pathlib.Path(f).read_bytes())
    agg_ok = h.hexdigest() == fz["aggregate"]["sha256"]
    n_checked = sum(1 for r in fz["files"] if r.startswith("domains/"))
    if bad or not agg_ok:
        print(f"[freeze] FAIL: {len(bad)} file(s) drifted {bad[:6]}; aggregate_ok={agg_ok}")
        return 1
    print(f"[freeze] OK: {n_checked} rebuilt files byte-identical to "
          f"FREEZE_pilot2_arms.json (+ aggregate over {len(agg_files)} parts)")
    return 0


def main() -> int:
    for name, path in (("BIRD dir", L.BIRD),
                       ("world_1 bridge", L.W1_SRC_DUCK)):
        if not os.path.exists(path):
            print(f"[rebuild] MISSING {name}: {path}\n"
                  f"          run ./fetch_and_rebuild.sh (see README) first")
            return 2
    sys.argv = ["build_all.py"] + sys.argv[1:]
    build_all.main()
    if len(sys.argv) == 1:          # full build -> gold materialized -> check freeze
        return freeze_check()
    print("[rebuild] partial build done (freeze check runs only on a full build)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
