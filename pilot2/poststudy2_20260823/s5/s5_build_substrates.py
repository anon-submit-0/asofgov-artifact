#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s5_build_substrates.py — S5 row-scale substrate construction (PREREG
poststudy2 2026-08-23, sha 838a214fc5a09902703d969c839872ff843f190e9f2e
1f9902f231e061c669 truncated in filename-safe form; full sha recorded in
the emitted JSON).

Row-scale axis (mandatory): `financial` with `trans` scaled to
{12.5%, 25%, 50%, 100%, 200%, 400%}.

EXACT SCALING RULE (deterministic, no RNG):
  * Source substrate: the sandbox copy of the financial warehouse
    (copied OUT of the sandbox before any mutation; the sandbox and the
    frozen pilot2/domains/financial are never opened read-write).
  * Below 1x (f in {1/8, 1/4, 1/2}): systematic residue sampling on the
    primary key —  keep exactly the rows with  trans_id % 8 < 8*f
    (i.e. residues {0}, {0,1}, {0,1,2,3}).  trans_id is unique over the
    table, so the kept fraction is |{ids with residue<8f}| / N, reported
    exactly per substrate.  DELETE of the complement + CHECKPOINT.
  * Above 1x (m in {2, 4}): row duplication with key remapping — for
    copy c = 1 .. m-1, INSERT a full copy of the ORIGINAL rows
    (trans_id <= original max id 3,682,987) with
        new trans_id = old trans_id + c * 4,000,000
    (4,000,000 > max original id, so uniqueness is preserved).  Only the
    primary key trans_id is remapped; every other column — account_id
    included — is copied verbatim, so per-account transaction
    multiplicity scales with the axis and join topology is preserved.
  * 1x: byte-identical copy of the source warehouse (no mutation).

The `windows-span` (world_1) substrate is a byte-identical copy of the
sandbox world_1 domain — that axis varies the REQUEST, not the data.

Every substrate directory gets warehouse.duckdb + questions.json (the
frozen financial questions, byte-copied). Reachability facts recorded
per substrate: trans row count, distinct trans dates, date hull, and
whether the hull still covers every frozen question window (gold-anchor
survival); a lost hull ⇒ the point is flagged for UNREACHABLE reporting.
"""
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys

import duckdb

S5 = pathlib.Path(__file__).resolve().parent
WORK = S5 / "work"
SANDBOX = pathlib.Path("/private/tmp/claude-502/-Volumes-SSD-1-vldb-asof/"
                       "831806d7-8bc6-464b-9baf-a933f760e40d/scratchpad/"
                       "poststudy-sandbox")
SRC_FIN = SANDBOX / "pilot2" / "domains" / "financial"
SRC_W1 = SANDBOX / "pilot2" / "domains" / "world_1"
FROZEN_FIN = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2/"
                          "domains/financial/warehouse.duckdb")

ORIG_MAX_ID = 3682987
OFFSET = 4000000

# (label, factor, kind, param)
POINTS = [
    ("scale_0125", 0.125, "sample", 1),   # trans_id % 8 < 1
    ("scale_025",  0.25,  "sample", 2),   # trans_id % 8 < 2
    ("scale_050",  0.50,  "sample", 4),   # trans_id % 8 < 4
    ("scale_100",  1.0,   "copy",   0),
    ("scale_200",  2.0,   "dup",    1),   # +1 remapped copy
    ("scale_400",  4.0,   "dup",    3),   # +3 remapped copies
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hull_facts(db):
    con = duckdb.connect(str(db), read_only=True)
    try:
        n, dmin, dmax, ndays = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT date) "
            "FROM trans").fetchone()
        nid = con.execute("SELECT COUNT(DISTINCT trans_id), COUNT(*) "
                          "FROM trans").fetchone()
    finally:
        con.close()
    return {"trans_rows": int(n), "date_min": str(dmin), "date_max": str(dmax),
            "distinct_dates": int(ndays),
            "trans_id_unique": nid[0] == nid[1]}


def question_windows():
    """Every [lo, hi) day interval any frozen financial question needs the
    trans hull to cover (only trans-anchored metrics matter for hull
    survival, but we record all windows for the report)."""
    qs = json.loads((SRC_FIN / "questions.json").read_text(encoding="utf-8"))
    out = []
    for q in qs:
        w = q.get("windows") or {}
        for role, obj in w.items():
            if not isinstance(obj, dict):
                continue
            lo = obj.get("lo")
            hi = obj.get("hi_excl") or obj.get("hi")
            if lo and hi:
                out.append({"qid": q["qid"], "role": role, "lo": lo, "hi": hi})
    return out


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    src_db = SRC_FIN / "warehouse.duckdb"
    manifest = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": "s5_build_substrates.py",
        "prereg_sha256": "838a214fc5a09902703d969c839872ff843f190e9f2e"
                         "9f6902f231e061c669".replace("838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669", "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"),
        "source_sandbox_financial_sha256": sha256(src_db),
        "frozen_financial_sha256": sha256(FROZEN_FIN) if FROZEN_FIN.is_file() else None,
        "scaling_rule": {
            "below_1x": "systematic residue sampling: keep rows with trans_id % 8 < 8*f "
                        "(residues {0} for 12.5%, {0,1} for 25%, {0,1,2,3} for 50%); "
                        "DELETE complement + CHECKPOINT",
            "above_1x": "row duplication with key remap: for copy c in 1..m-1 insert all "
                        "original rows (trans_id <= 3682987) with trans_id += c*4000000; "
                        "only trans_id remapped, all other columns verbatim",
            "at_1x": "byte-identical copy, no mutation",
        },
        "substrates": [],
    }

    for label, factor, kind, param in POINTS:
        ddir = WORK / "rowscale" / label / "financial"
        ddir.mkdir(parents=True, exist_ok=True)
        db = ddir / "warehouse.duckdb"
        if db.exists():
            db.unlink()
        shutil.copyfile(src_db, db)
        shutil.copyfile(SRC_FIN / "questions.json", ddir / "questions.json")
        if kind == "sample":
            con = duckdb.connect(str(db))
            con.execute("DELETE FROM trans WHERE trans_id %% 8 >= %d" % param)
            con.execute("CHECKPOINT")
            con.close()
        elif kind == "dup":
            con = duckdb.connect(str(db))
            for c in range(1, param + 1):
                con.execute(
                    "INSERT INTO trans SELECT trans_id + %d, account_id, date, "
                    "type, operation, amount, balance, k_symbol, bank, account "
                    "FROM trans WHERE trans_id <= %d" % (c * OFFSET, ORIG_MAX_ID))
            con.execute("CHECKPOINT")
            con.close()
        facts = hull_facts(db)
        facts.update({"label": label, "factor": factor, "kind": kind,
                      "db_bytes": db.stat().st_size,
                      "db_sha256": sha256(db)})
        # gold-anchor survival: does the trans date hull still cover every
        # frozen question window that lies inside the ORIGINAL hull?
        losses = []
        for w in question_windows():
            lo, hi = w["lo"], w["hi"]
            if hi <= "1993-01-01" or lo > "1998-12-31":
                continue  # was outside the authored hull at 1x too (FIN-Q7)
            eff_lo = max(lo, "1993-01-01")
            eff_hi = min(hi, "1999-01-01")
            if not (facts["date_min"] <= eff_lo and
                    facts["date_max"] >= (dt.date.fromisoformat(eff_hi)
                                          - dt.timedelta(days=1)).isoformat()):
                losses.append(w)
        facts["hull_losses_vs_frozen_questions"] = losses
        manifest["substrates"].append(facts)
        print(label, facts["trans_rows"], facts["date_min"], facts["date_max"],
              "distinct_dates=%d" % facts["distinct_dates"],
              "losses=%d" % len(losses), flush=True)

    # window-span substrate: byte copy of world_1
    wdir = WORK / "winspan" / "world_1"
    wdir.mkdir(parents=True, exist_ok=True)
    for fn in ("warehouse.duckdb", "questions.json"):
        shutil.copyfile(SRC_W1 / fn, wdir / fn)
    manifest["winspan_world_1_sha256"] = sha256(wdir / "warehouse.duckdb")

    (WORK / "substrates_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", WORK / "substrates_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
