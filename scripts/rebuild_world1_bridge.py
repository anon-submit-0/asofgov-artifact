#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the world_1 legacy bridge from the official Spider distribution.

Why this exists
---------------
pilot2/build/build_all.py imports the world_1 domain not from Spider's
world_1.sqlite directly but from a small "bridge" duckdb
(pilot/public/warehouse.duckdb, table country_v2026_01) that carries the
Spider dev world_1.country ORIGINAL VALUES -- a lineage stop-over from the
project's earlier public track.  The bridge is not redistributed in this
repository (Spider data stays under Spider's own license and distribution
channel); this script reconstructs the only table the pilot2 build reads.

Input : spider_data/database/world_1/world_1.sqlite from the official Spider
        distribution (https://yale-lily.github.io/spider).
Output: a duckdb file containing country_v2026_01 with exactly the nine
        columns the build consumes, values copied 1:1 from Spider.

The result is verified against a LOGICAL content hash (row-order and
float-representation canonicalized) recorded in
manifests/sha256_sources.txt; file-level hashes of duckdb databases are not
stable across duckdb versions, logical content is.

Usage:
  python3 scripts/rebuild_world1_bridge.py <path/to/world_1.sqlite> \
          [--out pilot/public/warehouse.duckdb] [--force]
  python3 scripts/rebuild_world1_bridge.py --hash-only <bridge.duckdb>
"""
import argparse
import hashlib
import os
import pathlib
import sys

import duckdb

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "pilot" / "public" / "warehouse.duckdb"

COLS = ("Code", "Name", "Continent", "Region", "SurfaceArea",
        "IndepYear", "Population", "LifeExpectancy", "GNP")
TYPES = ("VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "DOUBLE",
         "INTEGER", "BIGINT", "DOUBLE", "DOUBLE")
# sha256 over SELECT <COLS> FROM country_v2026_01 ORDER BY "Code", cells joined
# by \x1f and rows by \n; NULL -> "NULL", floats -> "%.17g".  Recorded from the
# frozen bridge that produced the paper's evidence (239 rows).
EXPECTED_LOGICAL_SHA = "cc37b01db6d262831563d69b0c0303c8107f660017bed776ddd51a6e3158a98e"
EXPECTED_ROWS = 239


def logical_hash(db_path: str) -> tuple[int, str]:
    con = duckdb.connect(db_path, read_only=True)
    try:
        sel = ", ".join(f'"{c}"' for c in COLS)
        rows = con.execute(
            f'SELECT {sel} FROM country_v2026_01 ORDER BY "Code"').fetchall()
    finally:
        con.close()

    def cell(c):
        if c is None:
            return "NULL"
        if isinstance(c, float):
            return "%.17g" % c
        return str(c)

    blob = "\n".join("\x1f".join(cell(c) for c in r) for r in rows).encode("utf-8")
    return len(rows), hashlib.sha256(blob).hexdigest()


def verdict(db_path: str) -> int:
    n, h = logical_hash(db_path)
    ok = (n == EXPECTED_ROWS and h == EXPECTED_LOGICAL_SHA)
    print(f"[bridge] {db_path}\n[bridge] rows={n} logical_sha256={h}")
    print(f"[bridge] {'MATCH: identical to the frozen evidence bridge' if ok else 'MISMATCH vs frozen bridge -- do not build on this'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sqlite", nargs="?", help="path to Spider world_1.sqlite")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--hash-only", metavar="BRIDGE_DUCKDB",
                    help="only verify an existing bridge duckdb")
    a = ap.parse_args()

    if a.hash_only:
        return verdict(a.hash_only)
    if not a.sqlite:
        ap.error("need <world_1.sqlite> (or --hash-only)")
    if not os.path.isfile(a.sqlite):
        print(f"[bridge] not a file: {a.sqlite}")
        return 2
    out = pathlib.Path(a.out)
    if out.exists() and not a.force:
        print(f"[bridge] {out} already exists; verifying instead (use --force to rebuild)")
        return verdict(str(out))

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    try:
        con.execute("INSTALL sqlite; LOAD sqlite;")
        con.execute(f"ATTACH '{a.sqlite}' AS src (TYPE sqlite)")
        cast_sel = ", ".join(f'CAST("{c}" AS {t}) AS "{c}"'
                             for c, t in zip(COLS, TYPES))
        con.execute(f'CREATE TABLE country_v2026_01 AS SELECT {cast_sel} '
                    f'FROM src."country"')
        con.execute("DETACH src")
    finally:
        con.close()
    return verdict(str(out))


if __name__ == "__main__":
    sys.exit(main())
