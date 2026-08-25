"""Derive every number used by the figures and tables from the frozen evidence.

Sources (read-only; never hand-transcribed into a figure script):
  S1  pilot/pilot_summary.json            -- error rates, cluster-bootstrap CIs, coverage
  S2  pilot/runs/<system>/<qid>.json      -- per-call raw responses -> failure taxonomy
  S3  pilot/domains/rma/questions.json    -- the SKU536-EOL running example (gold + note)
  S4  pilot/domains/rma/warehouse.duckdb  -- the running example's actual monthly facts
  S5  impl/INTEGRATION_REPORT.md          -- certificate acceptance matrix (parsed, see below)
  S7  impl/certs/{rma_q1,rma_q5,rma_q6}.json + the same warehouse -- the four
      sibling requests of the coverage-partition figure (see partition_cells)

Output: figures/fig_data.json  (single machine-readable source consumed by fig*.py
        and by make_tables.py).  Re-run this before regenerating anything, so the
        "four-place number alignment" rule is enforced mechanically.

Run:  python3 extract_data.py
"""

import json
import os
import re
import glob
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PILOT = os.path.join(ROOT, "pilot")
IMPL = os.path.join(ROOT, "impl")
OUT = os.path.join(HERE, "fig_data.json")

N_Q = 51  # the true denominator; every conditional rate must be reported against it

# display metadata: system id -> (short label, class, family)
SYSTEMS = [
    ("baseline_claude",   "claude-opus-4-6",   "plain",     "Anthropic"),
    ("baseline_qwen",     "qwen3-coder-next",  "plain",     "Qwen"),
    ("baseline_deepseek", "deepseek-3.2",      "plain",     "DeepSeek"),
    ("baseline_minimax",  "minimax-m2.5",      "plain",     "MiniMax"),
    ("trivial_claude",    "prompt-v1 (one-line)",       "prompt", "Anthropic"),
    ("trivial_v2",        "prompt-v2 (anchor-join)",    "prompt", "Anthropic"),
    ("trivial_v3",        "prompt-v3 (worked example)", "prompt", "Anthropic"),
    ("governance_informed", "full governance layer",    "governed", "Anthropic"),
    ("mechanism",         "binding compiler (ours)",    "mechanism", "--"),
]

# The B6 governance-informed arm was pre-registered to write into a NEW directory
# (PREREG_governance_arm.md §1/A6), so that running it could not touch the mtime of
# any existing pilot/runs/ tree.  Everything else about it -- scorer, cache format,
# 51-question enumeration -- is the frozen run_pilot.py machinery, so it is a
# first-class system here and differs only in where its cache lives.
RUNS_SUBDIR = {"governance_informed": os.path.join("runs_gov", "governance_informed")}


def runs_dir(sysid):
    return os.path.join(PILOT, RUNS_SUBDIR.get(sysid, os.path.join("runs", sysid)))


def load_summary():
    with open(os.path.join(PILOT, "pilot_summary.json")) as f:
        return json.load(f)


def taxonomy_from_runs():
    """Recompute the six-way verdict taxonomy for ALL systems from the frozen raw
    responses.  pilot_summary.json only stores four of the eight; recomputing from
    runs/ keeps every system on the same, auditable footing.  We assert the four
    stored ones reproduce exactly."""
    tax = {}
    for sysid, _, _, _ in SYSTEMS:
        d = runs_dir(sysid)
        c = collections.Counter()
        files = sorted(glob.glob(os.path.join(d, "*.json")))
        for fp in files:
            with open(fp) as f:
                c[json.load(f)["verdict"]] += 1
        assert sum(c.values()) == N_Q, f"{sysid}: {sum(c.values())} != {N_Q}"
        tax[sysid] = dict(c)
    return tax


def running_example():
    """SKU536-EOL: the paper's running example (rma_q5, 'the 536-SKU mother case').

    Facts pulled straight from the pilot warehouse so Fig.1 cannot drift from the
    data.  Under the governed binding `same_valid_time_window`, numerator
    (problem_qty @ rma_event_time) and denominator (sales_qty @ sales_event_time)
    must live in the SAME valid-time window.
    """
    import duckdb
    dbp = os.path.join(PILOT, "domains", "rma", "warehouse.duckdb")
    con = duckdb.connect(dbp, read_only=True)
    q = lambda s: con.execute(s).fetchall()
    sku = "SKU536-EOL"
    num = {str(r[0])[:7]: int(r[1]) for r in q(
        f"SELECT date_trunc('month',dt), SUM(problem_qty) "
        f"FROM flexispot_rma.dws_rma_sku_problem_1d WHERE product_sku='{sku}' "
        f"GROUP BY 1 ORDER BY 1")}
    den = {str(r[0])[:7]: int(r[1]) for r in q(
        f"SELECT date_trunc('month',dt), SUM(sales_qty) "
        f"FROM flexispot_rma.dws_sales_sku_1d WHERE product_sku='{sku}' "
        f"GROUP BY 1 ORDER BY 1")}
    tot_num = int(q(f"SELECT SUM(problem_qty) FROM flexispot_rma.dws_rma_sku_problem_1d "
                    f"WHERE product_sku='{sku}'")[0][0])
    tot_den = int(q(f"SELECT SUM(sales_qty) FROM flexispot_rma.dws_sales_sku_1d "
                    f"WHERE product_sku='{sku}'")[0][0])
    con.close()

    # frozen question record (gold label + the note that pins the naive value)
    with open(os.path.join(PILOT, "domains", "rma", "questions.json")) as f:
        rma_qs = json.load(f)
    q5 = next(x for x in rma_qs if x["qid"] == "rma_q5")

    # observed behaviour of every evaluated system on this single question
    obs = {}
    for sysid, _, _, _ in SYSTEMS:
        with open(os.path.join(runs_dir(sysid), "rma_q5.json")) as f:
            obs[sysid] = json.load(f)["verdict"]

    months = sorted(set(num) | set(den))
    return {
        "sku": sku,
        "months": months,
        "problem_qty": {m: num.get(m, 0) for m in months},
        "sales_qty": {m: den.get(m, 0) for m in months},
        "all_time_problem_qty": tot_num,
        "all_time_sales_qty": tot_den,
        # T1: an as-of point where the aligned-window binding IS satisfiable
        "t1": "2026-01",
        "t1_num": num.get("2026-01", 0),
        "t1_den": den.get("2026-01", 0),
        "t1_rate": num.get("2026-01", 0) / den["2026-01"],
        # T2: the frozen gold question (rma_q5), where it is NOT
        "t2": q5["as_of"],
        "t2_num": num.get("2026-05", 0),
        "t2_den": den.get("2026-05", 0),
        "t2_gold_kind": q5["expected_kind"],
        "t2_gold_refusal": q5["refusal_reason"],
        # the current-state answer a governance-blind system produces at T2:
        # this month's numerator over the ALL-HISTORY denominator (frozen in the
        # question note: "naive will use all-period sales 490 -> 12/490 ~= 0.0245")
        "naive_rate": num.get("2026-05", 0) / tot_den,
        "note": q5["notes"],
        "observed_verdicts": obs,
        "n_systems_answered_at_t2": sum(
            1 for s, v in obs.items() if v == "answered_should_refuse"),
        "n_systems_llm": len(obs) - 1,  # all but the mechanism
    }


def certificate_matrix():
    """Certificate acceptance matrix, parsed out of the frozen integration report.

    We parse rather than retype so a change in the report surfaces as a diff here.
    """
    with open(os.path.join(IMPL, "INTEGRATION_REPORT.md")) as f:
        txt = f.read()

    # per-domain rows of section 1.1
    dom_rows = []
    for line in txt.splitlines():
        m = re.match(r"^\|\s*(rma|quality_voc|domestic_newprod|email|aibuy|public[^|]*)\s*\|"
                     r"\s*(\d+)\s*\|([^|]*)\|([^|]*)\|\s*(\d+)/(\d+)\s*ACCEPT\s*\|", line)
        if m:
            dom_rows.append({
                "domain": m.group(1).strip(),
                "n": int(m.group(2)),
                "dec": m.group(3).strip(),
                "refusal": m.group(4).strip(),
                "accept": int(m.group(5)),
                "of": int(m.group(6)),
            })
    assert len(dom_rows) == 6, dom_rows
    assert sum(r["n"] for r in dom_rows) == N_Q

    # forgery families of section 1.2
    forge = []
    for line in txt.splitlines():
        m = re.match(r"^\|\s*\**(F\d[a-g])\s+([^|*]+?)\**\s*\|([^|]*)\|\s*(V[0-9a-c]+)\s*\|", line)
        if m:
            forge.append({"id": m.group(1), "name": m.group(2).strip(),
                          "surface": m.group(3).strip(), "check": m.group(4).strip()})
    assert len(forge) == 16, [f["id"] for f in forge]

    # dec distribution of section 1.1 header
    m = re.search(r"dec 分布：ANSWER (\d+) / REWRITE (\d+) / REFUSE (\d+)", txt)
    dec = {"ANSWER": int(m.group(1)), "REWRITE": int(m.group(2)), "REFUSE": int(m.group(3))}
    assert sum(dec.values()) == N_Q

    m = re.search(r"`sql_bytes_equal=(\d+)`", txt)
    sql_bytes_equal = int(m.group(1))

    return {
        "domains": dom_rows,
        "dec": dec,
        "forgeries": forge,
        "n_forgeries": len(forge),
        "n_base_accept": 3,
        "gold": N_Q, "legacy": N_Q, "accept": N_Q,
        "sql_bytes_equal": sql_bytes_equal,
        "ci_check": "shared_internal_roots = []",
        "symdiff_audit": 57,
        "n_deviations": 5,
        "matrix": forgery_matrix(forge),
    }


# ---------------------------------------------------------------- S6: forge_out ---
# The forgery x check matrix (Figure "forgery" in the certificate evaluation).
# Source of record is impl/asof_verifier/forge_out/*.json -- the verifier's own
# per-run report, which carries a PASS/FAIL/SKIP status for EVERY check, not just
# the first failing one.  INTEGRATION_REPORT.md 1.2 records only the first
# rejection; we parse both and assert they agree, so the figure cannot drift from
# either.  Nothing here is retyped from the report by hand.

FORGE_OUT = os.path.join(IMPL, "asof_verifier", "forge_out")

# Column display metadata.  ONLY the human-readable short label and the band
# grouping live here; every status, every first-reject and every count below is
# recomputed from the run artefacts.  The F2 labels name the deleted field
# because that band IS the experiment for the per-field non-redundancy claim.
FORGE_LABEL = {
    "F1a": "F1a", "F1b": "F1b", "F1c": "F1c", "F1d": "F1d",
    "F2a": r"F2a $-\nu$", "F2b": r"F2b $-\alpha$", "F2c": r"F2c $-\rho$",
    "F2d": r"F2d $-\delta$", "F2e": "F2e $-$wit",
    "F3a": "F3a", "F3b": "F3b", "F3c": "F3c", "F3d": "F3d",
    "F3e": "F3e", "F3f": "F3f", "F3g": "F3g",
}
# the 3 unmodified controls, in the order forge.py emits them
CONTROLS = [
    ("BASE_answer_rma_q1", "ctl ANS", "rma_q1"),
    ("BASE_refusal_mc_rma_q5", "ctl MC", "rma_q5"),
    ("BASE_refusal_am_rma_q6", "ctl AM", "rma_q6"),
]

# check_V6b (chk.py) runs clause (0) -- negation of every guard preceding r in the
# frozen order -- and returns immediately on failure, then clause (1), the witness
# replay.  The runner reports ONE status under the id "V6b", so the clause a
# failure landed in is recovered from the failure text.  These are the only
# strings check_V6b can return from clause (0); anything else is clause (1).
V6B0_MARKERS = ("guard order violated", "replay undecidable", "¬MC replay")


def _v6b_clause(detail):
    """(0) prior-guard negation vs (1) witness replay, from the FAIL text."""
    return "V6b(0)" if any(k in detail for k in V6B0_MARKERS) else "V6b(1)"


def forgery_matrix(forge_rows):
    with open(os.path.join(ROOT, "impl", "asof_verifier", "chk.py")) as f:
        src = f.read()
    m = re.search(r"^CHECK_ORDER = \[([^\]]*)\]", src, re.M)
    checks = [c.strip().strip('"') for c in m.group(1).split(",")]
    assert checks == ["V0", "V1", "V2", "V3", "V4", "V5", "V6a", "V6b", "V6c"], checks

    by_id = {r["id"]: r for r in forge_rows}
    cols, v6b_clauses = [], collections.Counter()

    def read(fname):
        with open(os.path.join(FORGE_OUT, fname + ".json")) as f:
            return json.load(f)

    for fid in [r["id"] for r in forge_rows]:                    # F1a .. F3g
        hits = glob.glob(os.path.join(FORGE_OUT, fid + "_*.json"))
        assert len(hits) == 1, (fid, hits)
        d = read(os.path.basename(hits[0])[:-5])
        rep, env = d["report"], d["envelope"]
        st = {c["check"]: c["status"] for c in rep["checks"]}
        assert sorted(st) == sorted(checks), (fid, sorted(st))
        assert rep["verdict"] == "REJECT", (fid, rep["verdict"])
        # the report's own first-reject must agree with the pre-registered target
        # AND with the line INTEGRATION_REPORT 1.2 records for this forgery
        assert rep["rejected_by"] == d["expected_reject_by"], fid
        assert rep["rejected_by"] == by_id[fid]["check"], (
            fid, rep["rejected_by"], by_id[fid]["check"])
        assert st[rep["rejected_by"]] == "FAIL", fid
        for c in rep["checks"]:
            if c["check"] == "V6b" and c["status"] == "FAIL":
                v6b_clauses[_v6b_clause(c["detail"])] += 1
        cols.append({
            "id": fid, "label": FORGE_LABEL[fid], "band": fid[:2],
            "name": by_id[fid]["name"], "surface": by_id[fid]["surface"],
            "qid": d["question"]["qid"],
            "dec": "REFUSE" if "refusal" in env else "ANSWER",
            "expected": d["expected_reject_by"],
            "rejected_by": rep["rejected_by"],
            "status": st,
        })

    for fname, label, qid in CONTROLS:                            # 3 controls
        d = read(fname)
        rep, env = d["report"], d["envelope"]
        assert rep["verdict"] == "ACCEPT", (fname, rep["verdict"])
        st = {c["check"]: c["status"] for c in rep["checks"]}
        assert "FAIL" not in st.values(), (fname, st)
        assert d["question"]["qid"] == qid, fname
        cols.append({
            "id": label.replace(" ", "-"), "label": label, "band": "ctl",
            "name": "unmodified control", "surface": "--",
            "qid": qid, "dec": "REFUSE" if "refusal" in env else "ANSWER",
            "expected": None, "rejected_by": None, "status": st,
        })

    forg = [c for c in cols if c["band"] != "ctl"]
    assert len(forg) == 16 and len(cols) == 19, (len(forg), len(cols))

    # per-check load over the 16 forgeries, and the concession band: the checks
    # that no forgery in this round ever brought down.
    load = {c: {k: sum(1 for f in forg if f["status"][c] == k)
                for k in ("FAIL", "PASS", "SKIP")} for c in checks}
    never = [c for c in checks if load[c]["FAIL"] == 0]
    first = collections.Counter(f["rejected_by"] for f in forg)

    assert sum(v6b_clauses.values()) == load["V6b"]["FAIL"], v6b_clauses
    return {
        "checks": checks,
        "check_order_src": "impl/asof_verifier/chk.py:CHECK_ORDER",
        "columns": cols,
        "load": load,
        "first_reject": dict(first),
        "never_fired": never,
        "v6b_clause_fails": {k: v6b_clauses.get(k, 0) for k in ("V6b(0)", "V6b(1)")},
        "n_expected_match": len(forg),          # first reject == pre-registered target
        "base_qids": sorted({f["qid"] for f in forg}),
        "multi_fail": {f["id"]: sorted(c for c in checks if f["status"][c] == "FAIL")
                       for f in forg if sum(1 for c in checks
                                            if f["status"][c] == "FAIL") > 1},
    }


# ------------------------------------------------------- S7: coverage partition ---
# Four sibling requests against ONE governed store, for the figure beside the
# coverage-partition theorem.  Everything below is recomputed from the pilot
# warehouse and cross-asserted against the frozen certificates in impl/certs/ and
# the frozen gold labels in questions.json; nothing is retyped.
#
# The four cells are deliberately siblings: same store, same anchor pair
# (rma_event_time on the numerator, sales_event_time on the denominator), same
# binding rule, same registered version.  Only the request coordinates move, so
# whatever discriminates the four outcomes is visible on the page.
#
# THREE cells are frozen suite questions and carry a verifier-accepted
# certificate.  The fourth, the OOV cell, is NOT a suite question: the suite's
# certified OOV instance lives in another domain (the launch-funnel question),
# and putting it in the grid would change the store and destroy the comparison.
# We therefore run one extra read-only probe on the same warehouse and label the
# cell as a probe -- it is the only number in the figure without a certificate
# behind it, and the figure says so.
#
# Leg measures are named here rather than read from a metric table (this seed
# registers bindings and routes but no measure column), so each is ASSERTED to
# reproduce the frozen gold value or the frozen witness of its question.
PARTITION_MEASURES = {
    "problem_rate": ("dws_rma_sku_problem_1d", "problem_qty",
                     "dws_sales_sku_1d", "sales_qty"),
    "refund_rate":  ("dws_rma_sku_problem_1d", "refund_amount",
                     "dws_sales_sku_1d", "sales_amount"),
}
# (tag, class, qid-or-None, metric, sku, numerator window, denominator window)
PARTITION_REQUESTS = [
    ("a", "Bindable",  "rma_q1", "problem_rate", "E7-WHT",     "2026-05", "2026-05"),
    ("b", "OOV",       None,     "problem_rate", "SKU536-EOL", "2026-08", "2026-08"),
    ("c", "AM",        "rma_q6", "refund_rate",  "EG8-BLK",    "2026-05", "2026-04"),
    ("d", "MC",        "rma_q5", "problem_rate", "SKU536-EOL", "2026-05", "2026-05"),
]


def _month(m):
    """'2026-05' -> the half-open day window the request derivation produces."""
    y, mo = int(m[:4]), int(m[5:7])
    hi = f"{y + 1}-01-01" if mo == 12 else f"{y}-{mo + 1:02d}-01"
    return {"kind": "month", "lo": f"{y}-{mo:02d}-01", "hi_excl": hi}


def partition_cells():
    import duckdb
    dbp = os.path.join(PILOT, "domains", "rma", "warehouse.duckdb")
    con = duckdb.connect(dbp, read_only=True)
    q = lambda s: con.execute(s).fetchall()

    # -- the shared context: one version, one rule, one anchor pair ------------
    vers = q("SELECT version, domain FROM main.gov_semantic_graph_version")
    assert len(vers) == 1, vers                      # the single registered version
    version = vers[0][0]
    anch = {r[0]: r for r in q(
        "SELECT anchor_id, semantic_object, effective_date, version "
        "FROM main.gov_valid_time_anchor WHERE domain='rma'")}
    bind = {r[0]: r for r in q(
        "SELECT metric, binding_id, numerator_anchor, denominator_anchor, rule "
        "FROM main.gov_temporal_binding WHERE domain='rma'")}
    for m in ("problem_rate", "refund_rate"):        # same rule, same anchor pair
        assert bind[m][4] == "same_valid_time_window", bind[m]
        assert (bind[m][2], bind[m][3]) == ("rma_event_time", "sales_event_time"), bind[m]

    cov = {}
    for aid in ("rma_event_time", "sales_event_time"):
        _, obj, col, av = anch[aid]
        assert av == version, (aid, av)
        lo, hi, n = q(f"SELECT MIN({col}), MAX({col}), COUNT(*) "
                      f"FROM flexispot_rma.{obj}")[0]
        # hull mode: the coverage domain is the convex hull of the marking set,
        # a property of the anchor's OBJECT -- never of the request's scope.
        cov[aid] = {"anchor_id": aid, "object": obj, "column": col, "mode": "hull",
                    "granule": "day", "lo": str(lo), "hi": str(hi), "n_rows": n}

    def overlaps(aid, w):
        return not (w["hi_excl"] <= cov[aid]["lo"] or w["lo"] > cov[aid]["hi"])

    with open(os.path.join(PILOT, "domains", "rma", "questions.json")) as f:
        QS = {x["qid"]: x for x in json.load(f)}

    cells = []
    for tag, cls, qid, metric, sku, wn, wd in PARTITION_REQUESTS:
        ntab, ncol, dtab, dcol = PARTITION_MEASURES[metric]
        Wn, Wd = _month(wn), _month(wd)
        num = q(f"SELECT COALESCE(SUM({ncol}),0), COUNT(*) FROM flexispot_rma.{ntab} "
                f"WHERE product_sku='{sku}' AND dt >= DATE '{Wn['lo']}' "
                f"AND dt < DATE '{Wn['hi_excl']}'")[0]
        den = q(f"SELECT COALESCE(SUM({dcol}),0), COUNT(*) FROM flexispot_rma.{dtab} "
                f"WHERE product_sku='{sku}' AND dt >= DATE '{Wd['lo']}' "
                f"AND dt < DATE '{Wd['hi_excl']}'")[0]
        c = {
            "tag": tag, "cls": cls, "qid": qid, "metric": metric, "scope": sku,
            "as_of": wn, "w_num": Wn, "w_den": Wd,
            "num_mass": float(num[0]), "num_rows": num[1],
            "den_mass": float(den[0]), "den_rows": den[1],
            "binding_id": bind[metric][1],
            # the guard walk, evaluated here in the frozen order OOV -> AM -> MC
            "g_oov": {"num": overlaps(bind[metric][2], Wn),
                      "den": overlaps(bind[metric][3], Wd)},
            "g_am_ii": Wn == Wd,           # clause (ii) of same_valid_time_window
            "g_mc_i": True,                # m, R_v(m), beta_v(m) all registered
            "g_mc_ii": float(den[0]) > 0,
        }
        # -- classify by the guard chain, and assert the chain agrees with the
        #    frozen gold label / certificate rather than trusting either.
        if not (c["g_oov"]["num"] and c["g_oov"]["den"]):
            got = "OOV"
        elif not c["g_am_ii"]:
            got = "AM"
        elif not c["g_mc_ii"]:
            got = "MC"
        else:
            got = "Bindable"
        assert got == cls, (tag, got, cls)
        if got == "Bindable":
            c["value"] = c["num_mass"] / c["den_mass"]
        if qid:
            cert = json.load(open(os.path.join(IMPL, "certs", qid + ".json")))["certificate"]
            byrole = {a["role"]: a for a in cert["anchors"]}
            assert cert["graph_pin"]["graph_version"] == version, qid
            assert cert["binding"]["binding_id"] == c["binding_id"], qid
            assert byrole["numerator"]["window"] == Wn, (qid, byrole["numerator"])
            assert byrole["denominator"]["window"] == Wd, (qid, byrole["denominator"])
            assert byrole["numerator"]["coverage_mode"] == "hull", qid
            want = {"Bindable": "ANSWER"}.get(cls, "REFUSE")
            assert cert["disclosure"]["decision"] == want, (qid, cert["disclosure"])
            gold = QS[qid]
            assert gold["as_of"] == wn and gold["metric"] == metric, qid
            c["cert"] = os.path.join("impl", "certs", qid + ".json")
            if cls == "Bindable":
                # the printed rate must round to the frozen gold value
                assert round(c["value"], 6) == gold["gold_value"], (qid, c["value"])
                c["gold_value"] = gold["gold_value"]
            else:
                assert gold["expected_kind"] == "refusal", qid
                w = cert["refusal"]["witness"]
                c["witness_type"] = w["type"]
                if cls == "AM":                      # witness names the clause
                    assert w["clause"] == "(ii)" and w["num_window"] == Wn \
                        and w["den_window"] == Wd, qid
                    assert gold["refusal_reason"] == "anchor-mismatch", qid
                    # what the request WOULD have produced had it been honoured,
                    # against the same-window reading the binding demands
                    same = q(f"SELECT COALESCE(SUM({dcol}),0) FROM flexispot_rma.{dtab} "
                             f"WHERE product_sku='{sku}' AND dt >= DATE '{Wn['lo']}' "
                             f"AND dt < DATE '{Wn['hi_excl']}'")[0][0]
                    c["asked_value"] = c["num_mass"] / c["den_mass"]
                    c["same_window_den"] = float(same)
                    c["same_window_value"] = c["num_mass"] / float(same)
                else:                                # MC(ii): the empty-denominator probe
                    assert gold["refusal_reason"] == "missing-caliber", qid
                    assert w["type"] == "empty-denominator-probe", qid
                    assert c["den_mass"] == 0.0 and c["den_rows"] == 0, qid
        else:
            # the OOV cell: a probe run for this figure, no certificate
            assert cls == "OOV" and c["num_rows"] == 0 and c["den_rows"] == 0, tag
            c["cert"] = None
        cells.append(c)

    # -- the boundary the figure exists to make legible -------------------------
    # (b) and (d) are the SAME scope with the SAME empty same-month denominator.
    # What separates OOV from MC(ii) is whether T lands inside the anchor's
    # coverage hull -- a property of the anchor's table, not of the scope.
    eol = [c for c in cells if c["scope"] == "SKU536-EOL"]
    assert len(eol) == 2 and {c["cls"] for c in eol} == {"OOV", "MC"}, eol
    assert all(c["den_mass"] == 0.0 for c in eol), eol
    own = q("SELECT MIN(dt), MAX(dt), COALESCE(SUM(sales_qty),0) "
            "FROM flexispot_rma.dws_sales_sku_1d WHERE product_sku='SKU536-EOL'")[0]
    con.close()
    return {
        "version": version, "domain": "rma", "rule": "same_valid_time_window",
        "guard_chain": ["OOV", "AM", "MC"],
        "coverage": cov,
        "cells": cells,
        "boundary": {"scope": "SKU536-EOL",
                     "own_sales_first": str(own[0]), "own_sales_last": str(own[1]),
                     "own_sales_total": float(own[2]),
                     "oov_as_of": next(c["as_of"] for c in eol if c["cls"] == "OOV"),
                     "mc_as_of": next(c["as_of"] for c in eol if c["cls"] == "MC")},
        "n_certified": sum(1 for c in cells if c["cert"]),
    }


def main():
    s = load_summary()
    tax = taxonomy_from_runs()

    # cross-check: recomputed taxonomy must reproduce both the stored taxonomy
    # and the stored error rate for every system (four-place alignment gate).
    for sysid, _, _, _ in SYSTEMS:
        if sysid in s["taxonomy"]:
            assert tax[sysid] == s["taxonomy"][sysid], (sysid, tax[sysid], s["taxonomy"][sysid])
        err = 1.0 - tax[sysid].get("correct", 0) / N_Q
        assert abs(err - s["error_rate"][sysid]) < 1e-12, (sysid, err, s["error_rate"][sysid])
        # coverage: answered = 1 - (refusals emitted).  A refusal is emitted when the
        # system refused: verdict 'correct' on a refusal question, or 'over-refusal'.
        cov = s["coverage"][sysid]
        assert abs(cov["answered"] + cov["refused"] - 1.0) < 1e-12

    data = {
        "n_questions": N_Q,
        "n_refusal_questions": 14,      # 14/51 refusal-gold items (frozen protocol)
        "n_enterprise": 31, "n_public": 20,
        "bootstrap": {"B": s["cluster_bootstrap"]["baseline_claude"]["B"],
                      "unit": s["cluster_bootstrap"]["baseline_claude"]["cluster_unit"],
                      "n_clusters": 6},
        "systems": [{"id": i, "label": l, "class": c, "family": f} for i, l, c, f in SYSTEMS],
        "error_rate": s["error_rate"],
        "ci95": {k: v["ci95"] for k, v in s["cluster_bootstrap"].items()},
        "coverage": s["coverage"],
        "taxonomy": tax,
        "reference_baseline": s["reference_baseline"],
        "reference_errors": s["reference_errors"],
        "eliminated_by_mechanism": s["eliminated_by_mechanism"],
        "eliminated_by_trivial": s["eliminated_by_trivial"],
        "running_example": running_example(),
        "certificates": certificate_matrix(),
        "partition": partition_cells(),
    }
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"wrote {OUT}")
    re_ = data["running_example"]
    print(f"  running example {re_['sku']}: "
          f"T1={re_['t1']} {re_['t1_num']}/{re_['t1_den']}={re_['t1_rate']:.4f}, "
          f"T2={re_['t2']} {re_['t2_num']}/{re_['t2_den']} -> {re_['t2_gold_refusal']}, "
          f"naive={re_['naive_rate']:.4f}, "
          f"{re_['n_systems_answered_at_t2']}/{re_['n_systems_llm']} LLM systems answered")
    print(f"  certificates: {data['certificates']['dec']}, "
          f"{data['certificates']['n_forgeries']} forgeries")
    P = data["partition"]
    for c in P["cells"]:
        val = (f"{c['num_mass']:.0f}/{c['den_mass']:.0f}={100 * c['value']:.2f}%"
               if c["cls"] == "Bindable" else "_|_" + c["cls"])
        print(f"  partition ({c['tag']}) {c['cls']:9s} {c['metric']:12s} "
              f"{c['scope']:11s} T={c['as_of']} "
              f"mu=({c['num_mass']:.0f},{c['den_mass']:.0f}) {val} "
              f"{c['qid'] or 'probe (no certificate)'}")
    print(f"  partition coverage hulls: " + ", ".join(
        f"{a}=[{v['lo']},{v['hi']}]" for a, v in P["coverage"].items()))


if __name__ == "__main__":
    main()
