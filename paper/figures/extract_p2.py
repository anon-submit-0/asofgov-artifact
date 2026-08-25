#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Derive every number used by the pilot2 figures and tables from frozen evidence.

This is the pilot2 (public-base) successor of extract_data.py: the paper's
evidence base migrated from the enterprise pilot (51 questions, 6 clusters) to
nine public BIRD/Spider-derived databases (60 questions, 9 clusters) by author
ruling; enterprise material is motivation only and enters no figure or table.

Sources (read-only; never hand-transcribed into a figure script):
  S1  pilot2/pilot2_arms_summary.json    -- 9-arm scored matrix (error rates,
      cluster-bootstrap CIs, coverage, six-way taxonomy, per-question verdicts,
      elimination fractions, refusal stats, governance-arm audit)
  S2  pilot2/pilot2_summary.json         -- the old-structure alignment copy;
      every overlapping number is cross-asserted against S1
  S3  pilot2/domains/card_games/{questions.json, warehouse.duckdb}
      -- the running example (ruling_intensity, as-of 2017-02) and the
         coverage-partition probes; every mass recomputed from the warehouse
  S4  impl/certs2/<qid>.json             -- the 60 frozen certificates; the
      running example, the partition rows and the ablation ladder are asserted
      against (never copied from) them
  S5  impl/asof_verifier/forge_p2_out/*.json -- the verifier's own 34 forgery
      run reports (F1 x6, F2 x5, F3 x9, F4 x10, F5 x4; F5 added 2026-08-10
      with the two verifier repairs it forced -- see forge_p2.py's docstring)
  S6  impl/asof_verifier/chk.py          -- re-run here (read-only) to (i)
      re-verify the 11 unmutated base certificates the forgeries start from,
      and (ii) recompute the verifier rungs of the ablation ladder, including
      the strict no-declared-windows track (50/60)
  S7  pilot2/domains/*/provenance.json + gov_seed/*.jsonl + questions.json
      -- the benchmark-composition table (real/authored rows, versions,
         disclosure-policy instances, per-cluster question budget)
  S8  pilot2/runs/<arm>/CARD-Q7.json     -- what the evaluated arms actually
      returned on the running example (frozen response cache; no new calls)

Output: figures/fig_data_pilot2.json -- the single machine-readable source consumed
by fig1_combined.py, fig3_failure_taxonomy.py, figA_partition.py,
figB_forgery_matrix.py, figD_cost_ablation.py and make_tables_p2.py.

Run:  python3 extract_p2.py
"""
import collections
import glob
import json
import math
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
P2 = os.path.join(ROOT, "pilot2")
DOM = os.path.join(P2, "domains")
IMPL = os.path.join(ROOT, "impl")
CERTS2 = os.path.join(IMPL, "certs2")
FORGE_OUT = os.path.join(IMPL, "asof_verifier", "forge_p2_out")
OUT = os.path.join(HERE, "fig_data_pilot2.json")

sys.path.insert(0, os.path.join(IMPL, "asof_verifier"))
import chk  # noqa: E402  (verifier side only; read-only use)

N_Q = 60
DOMAINS = ["california_schools", "card_games", "codebase_community",
           "debit_card_specializing", "european_football_2", "financial",
           "formula_1", "thrombosis_prediction", "world_1"]

# display metadata: arm id -> (short label, class, backbone).  Row order here IS
# the row order of the main results table and of the failure-taxonomy figure.
SYSTEMS = [
    ("baseline_claude",     "claude-opus-4-6",            "plain",     "Anthropic"),
    ("baseline_qwen",       "qwen3-coder-next",           "plain",     "Qwen"),
    ("baseline_deepseek",   "deepseek-3.2",               "plain",     "DeepSeek"),
    ("baseline_minimax",    "minimax-m2.5",               "plain",     "MiniMax"),
    ("trivial_claude",      "prompt-v1 (one-line)",       "prompt",    "Anthropic"),
    ("trivial_v2",          "prompt-v2 (anchor-join)",    "prompt",    "Anthropic"),
    ("trivial_v3",          "prompt-v3 (worked example)", "prompt",    "Anthropic"),
    ("governance_informed", "full governance layer",      "governed",  "Anthropic"),
    ("mechanism",           "binding compiler (ours)",    "mechanism", "--"),
]
TAX_KEYS = ("correct", "wrong_value", "execution_error", "answered_should_refuse",
            "refused_should_answer", "no_sql")


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def questions(domain):
    return jload(os.path.join(DOM, domain, "questions.json"))


def all_questions():
    out = []
    for d in DOMAINS:
        out.extend(questions(d))
    assert len(out) == N_Q, len(out)
    return out


def cert_env(qid):
    return jload(os.path.join(CERTS2, qid + ".json"))


# ============================================================ S1/S2: the arms ===
def arms_block():
    A = jload(os.path.join(P2, "pilot2_arms_summary.json"))
    S = jload(os.path.join(P2, "pilot2_summary.json"))
    assert A["n_questions"] == S["n_questions"] == N_Q

    ids = [s[0] for s in SYSTEMS]
    assert set(A["error_rate"]) == set(ids)

    # cross-assert every overlapping number between the two summary files
    for sysid in ids:
        assert abs(A["error_rate"][sysid] - S["error_rate"][sysid]) < 1e-12, sysid
        assert A["cluster_bootstrap"][sysid]["ci95"] == \
            S["cluster_bootstrap"][sysid]["ci95"], sysid
        assert A["cluster_bootstrap"][sysid]["B"] == 2000
        assert A["coverage"][sysid] == S["coverage"][sysid], sysid
        assert A["taxonomy"][sysid] == S["taxonomy"][sysid], sysid
        # refusal stats live under slightly different field names in the two
        # files; the numbers themselves must agree
        ra, rs_ = A["refusal_stats"][sysid], S["refusal_stats"][sysid]
        assert ra["correct_refusals"] == rs_["correct_refusals"], sysid
        assert ra["over_refusals_on_answer_questions"] == \
            rs_["over_refusals_on_value_questions"], sysid
        assert ra["n_refusal_questions"] == rs_["n_refusal_questions"] == 15
        assert ra["n_answer_questions"] == rs_["n_value_questions"] == 45
        # internal closure: taxonomy sums to 60 and reproduces the error count
        tax = A["taxonomy"][sysid]
        assert set(tax) <= set(TAX_KEYS), (sysid, tax)
        assert sum(tax.values()) == N_Q, (sysid, tax)
        assert N_Q - tax.get("correct", 0) == A["error_counts"][sysid], sysid
        assert abs(A["error_counts"][sysid] / N_Q - A["error_rate"][sysid]) < 1e-12
        cov = A["coverage"][sysid]
        # answered + refused <= 1 (no-SQL / empty responses are neither)
        assert cov["answered"] + cov["refused"] <= 1.0 + 1e-12, (sysid, cov)

    assert A["reference_baseline"] == "baseline_claude"
    assert A["reference_errors"] == 36 == A["error_counts"]["baseline_claude"]
    assert len(A["reference_error_qids"]) == 36

    # elimination fractions: recompute from the per-question verdict matrix
    ref_err = set(A["reference_error_qids"])
    pqv = A["per_question_verdicts"]
    assert len(pqv) == N_Q
    for sysid in ids:
        fixed = sum(1 for q in ref_err if pqv[q][sysid] == "correct")
        assert abs(fixed / 36 - A["eliminated_by"][sysid]) < 1e-12, sysid
    assert A["eliminated_by"]["mechanism"] == 1.0
    assert abs(A["eliminated_by"]["governance_informed"] - 13 / 36) < 1e-12

    G = A["governance_informed_arm"]
    assert G["E_gov"] == 28 == A["error_counts"]["governance_informed"]
    assert G["nd4_nondegeneracy"] == "PASS"
    assert G["probe7_errors"] == 6 and G["md5_fixed"] == 4
    assert len(G["disclosure_blocked_3"]) == 3
    assert all(v == "answered_should_refuse" for v in G["disclosure_blocked_3"].values())

    # per-gold-form / per-refusal-reason slices close on their denominators
    for sysid in ids:
        gf = A["slices"]["per_gold_form"][sysid]
        assert (gf["value"]["n"], gf["rewrite"]["n"], gf["refusal"]["n"]) == (33, 12, 15)
        errs = gf["value"]["errors"] + gf["rewrite"]["errors"] + gf["refusal"]["errors"]
        assert errs == A["error_counts"][sysid], sysid
        rr = A["slices"]["per_refusal_reason"][sysid]
        assert {k: rr[k]["n"] for k in rr} == {"OOV": 4, "AM": 5, "MC": 3, "DB": 3}
        assert sum(rr[k]["correct"] for k in rr) == \
            A["refusal_stats"][sysid]["correct_refusals"], sysid

    return {
        "systems": [{"id": i, "label": l, "class": c, "family": f}
                    for i, l, c, f in SYSTEMS],
        "error_rate": {k: A["error_rate"][k] for k in ids},
        "error_counts": {k: A["error_counts"][k] for k in ids},
        "ci95": {k: A["cluster_bootstrap"][k]["ci95"] for k in ids},
        "coverage": {k: A["coverage"][k] for k in ids},
        "taxonomy": {k: A["taxonomy"][k] for k in ids},
        "eliminated_by": {k: A["eliminated_by"][k] for k in ids},
        "refusal_stats": {k: {
            "correct_refusals": A["refusal_stats"][k]["correct_refusals"],
            "n_refusal_questions": 15,
            "over_refusals": A["refusal_stats"][k]["over_refusals_on_answer_questions"],
            "n_answer_questions": 45,
        } for k in ids},
        "per_gold_form": {k: A["slices"]["per_gold_form"][k] for k in ids},
        "per_refusal_reason": {k: A["slices"]["per_refusal_reason"][k] for k in ids},
        "per_cluster": A["slices"]["per_cluster"],
        "reference": {"id": "baseline_claude", "errors": 36},
        "bootstrap": {"B": 2000, "unit": "domain (9 public DBs)", "n_clusters": 9},
        "gov_arm": {
            "E_gov": G["E_gov"],
            "elim": G["eliminated_by_governance"],
            "prereg_case": G["prereg_case"],
            "probe7_errors": G["probe7_errors"],
            "md5_fixed": G["md5_fixed"],
            "disclosure_blocked_errors": len(G["disclosure_blocked_3"]),
            "paired_vs_reference": G["paired_vs_baseline_claude"],
        },
        "per_question_verdicts": pqv,
    }


# ==================================== S3/S4/S8: the running example (card_games) ===
def running_example(arms):
    dbp = os.path.join(DOM, "card_games", "warehouse.duckdb")
    con = duckdb.connect(dbp, read_only=True)
    q = lambda s: con.execute(s).fetchall()  # noqa: E731

    def rulings_in(lo, hi):
        return q(f"SELECT COUNT(*) FROM rulings WHERE date >= '{lo}' "
                 f"AND date < '{hi}'")[0][0]

    def printings_in(lo, hi):
        return q(f"SELECT COUNT(*) FROM cards t0 JOIN sets t1 ON t0.setCode = t1.code "
                 f"WHERE t1.releaseDate >= '{lo}' AND t1.releaseDate < '{hi}'")[0][0]

    MONTHS = ["2016-11", "2016-12", "2017-01", "2017-02", "2017-03", "2017-04"]

    def month_bounds(m):
        y, mo = int(m[:4]), int(m[5:7])
        return f"{m}-01", (f"{y+1}-01-01" if mo == 12 else f"{y}-{mo+1:02d}-01")

    num = {m: int(rulings_in(*month_bounds(m))) for m in MONTHS}
    den = {m: int(printings_in(*month_bounds(m))) for m in MONTHS}

    hull_rul = q("SELECT MIN(date), MAX(date) FROM rulings")[0]
    hull_set = q("SELECT MIN(releaseDate), MAX(releaseDate) FROM sets")[0]
    con.close()

    QS = {x["qid"]: x for x in questions("card_games")}
    q2, q7, q1 = QS["CARD-Q2"], QS["CARD-Q7"], QS["CARD-Q1"]
    assert q2["metric"] == q7["metric"] == "card.ruling_intensity"
    assert q2["declared_at"] == q7["declared_at"] == "2017-03-01"
    assert q7["expected_kind"] == "refusal" and q7["refusal_reason"] == "missing-caliber"
    assert q7["refusal_subtype"] == "mc_ii"

    # the two as-of points: T1 answerable (CARD-Q2), T2 the MC(ii) gold (CARD-Q7)
    t1, t2 = "2016-11", "2017-02"
    assert q2["as_of"][:7] == t1 and q7["as_of"][:7] == t2
    assert den[t1] > 0 and den[t2] == 0 and num[t2] > 0
    t1_rate = num[t1] / den[t1]
    assert abs(t1_rate - q2["gold_value"]) < 1e-12, (t1_rate, q2["gold_value"])
    assert num[t2] == q1["gold_value"] == 2161  # CARD-Q1 pins the same numerator

    # frozen certificates: sibling ANSWER and the MC(ii) refusal with its probe
    e2, e7 = cert_env("CARD-Q2"), cert_env("CARD-Q7")
    assert e2["certificate"]["graph_pin"]["graph_version"] == "v1"
    assert e7["certificate"]["graph_pin"]["graph_version"] == "v1"
    b7 = e7["certificate"]["binding"]
    assert b7["rule"] == "same_valid_time_window"
    assert (b7["numerator_anchor"], b7["denominator_anchor"]) == \
        ("A-CARD-RUL", "A-CARD-SET")
    assert e7["refusal"] == "missing-caliber"
    wit = e7["certificate"]["refusal"]["witness"]
    assert wit["type"] == "empty-denominator-probe" and wit["observed"] == 0.0
    # re-execute the certificate's own probe SQL against the warehouse
    con = duckdb.connect(dbp, read_only=True)
    probe_val = con.execute(wit["probe_sql"]).fetchone()[0]
    con.close()
    assert float(probe_val) == 0.0, probe_val

    # what the evaluated arms actually did on the two questions (frozen cache)
    pqv = arms["per_question_verdicts"]
    obs_t2 = {s[0]: pqv["CARD-Q7"][s[0]] for s in SYSTEMS}
    obs_t1 = {s[0]: pqv["CARD-Q2"][s[0]] for s in SYSTEMS}
    llm = [s[0] for s in SYSTEMS if s[0] != "mechanism"]
    n_answered_t2 = sum(1 for s in llm
                        if obs_t2[s] == "answered_should_refuse")
    n_correct_t1 = sum(1 for s in llm if obs_t1[s] == "correct")
    assert obs_t2["mechanism"] == "correct" and obs_t1["mechanism"] == "correct"

    # the strongest arm's actual output at T2: 2161/0 evaluated to +inf
    gov_run = jload(os.path.join(P2, "runs", "governance_informed", "CARD-Q7.json"))
    gov_inf = isinstance(gov_run.get("value"), float) and math.isinf(gov_run["value"])
    assert gov_run["verdict"] == "answered_should_refuse"
    assert gov_inf, "expected the governance arm's cached 2161/0 = inf value"

    return {
        "domain": "card_games",
        "metric": "ruling_intensity",
        "metric_def": "rulings issued in the month / new printings released in the month",
        "months": MONTHS,
        "rulings": num,
        "printings": den,
        "t1": t1, "t1_qid": "CARD-Q2",
        "t1_num": num[t1], "t1_den": den[t1], "t1_rate": t1_rate,
        "t2": t2, "t2_qid": "CARD-Q7",
        "t2_num": num[t2], "t2_den": den[t2],
        "t2_gold_kind": "refusal", "t2_gold_refusal": "missing-caliber",
        "t2_subtype": "MC(ii)",
        "declared_at": q7["declared_at"],
        "graph_version": "v1",
        "anchors": {"num": "A-CARD-RUL (rulings.date)",
                    "den": "A-CARD-SET (sets.releaseDate)"},
        "hull_rulings": [str(hull_rul[0]), str(hull_rul[1])],
        "hull_sets": [str(hull_set[0]), str(hull_set[1])],
        "observed_t1": obs_t1, "observed_t2": obs_t2,
        "n_llm": len(llm),
        "n_answered_at_t2": n_answered_t2,
        "n_correct_at_t1": n_correct_t1,
        "gov_arm_t2_value": "Infinity",
        "sibling_note": "CARD-Q2 certificate ACCEPT; CARD-Q7 certificate ACCEPT "
                        "(refusal witness re-executed above)",
    }


# ==================================== S3/S4: the coverage partition, four cells ===
def partition_cells():
    dbp = os.path.join(DOM, "card_games", "warehouse.duckdb")
    con = duckdb.connect(dbp, read_only=True)
    q = lambda s: con.execute(s).fetchall()  # noqa: E731

    # the shared context: one store, one binding, one version, day granule.
    # Coverage hulls are recomputed from the anchors' marking columns -- the
    # covered domain is a property of the anchor's table, never of the request.
    lo_r, hi_r, n_r = q("SELECT MIN(date), MAX(date), COUNT(*) FROM rulings")[0]
    lo_s, hi_s, n_s = q("SELECT MIN(releaseDate), MAX(releaseDate), COUNT(*) FROM sets")[0]
    cov = {
        "num": {"anchor_id": "A-CARD-RUL", "object": "rulings", "column": "date",
                "mode": "hull", "granule": "day", "lo": str(lo_r), "hi": str(hi_r),
                "n_rows": int(n_r)},
        "den": {"anchor_id": "A-CARD-SET", "object": "sets", "column": "releaseDate",
                "mode": "hull", "granule": "day", "lo": str(lo_s), "hi": str(hi_s),
                "n_rows": int(n_s)},
    }

    def month_w(m):
        y, mo = int(m[:4]), int(m[5:7])
        hi = f"{y+1}-01-01" if mo == 12 else f"{y}-{mo+1:02d}-01"
        return {"kind": "month", "lo": f"{m}-01", "hi_excl": hi}

    def mass_num(w):
        return int(q(f"SELECT COUNT(*) FROM rulings WHERE date >= '{w['lo']}' "
                     f"AND date < '{w['hi_excl']}'")[0][0])

    def mass_den(w):
        # the denominator leg is routed rulings -> cards -> sets (setCode join):
        # printings whose set released inside the window
        return int(q(f"SELECT COUNT(*) FROM cards t0 JOIN sets t1 "
                     f"ON t0.setCode = t1.code WHERE t1.releaseDate >= '{w['lo']}' "
                     f"AND t1.releaseDate < '{w['hi_excl']}'")[0][0])

    def overlaps(leg, w):
        c = cov[leg]
        return not (w["hi_excl"] <= c["lo"] or w["lo"] > c["hi"])

    # (tag, class, qid-or-None, as-of month, num window, den window)
    REQUESTS = [
        ("a", "Bindable", "CARD-Q2", "2016-11", "2016-11", "2016-11"),
        ("b", "OOV",      None,      "2021-06", "2021-06", "2021-06"),
        ("c", "AM",       None,      "2016-11", "2016-11", "2016-10"),
        ("d", "MC",       "CARD-Q7", "2017-02", "2017-02", "2017-02"),
    ]
    QS = {x["qid"]: x for x in questions("card_games")}
    cells = []
    for tag, cls, qid, asof, wn_m, wd_m in REQUESTS:
        Wn, Wd = month_w(wn_m), month_w(wd_m)
        c = {
            "tag": tag, "cls": cls, "qid": qid, "metric": "ruling_intensity",
            "scope": "card_games (whole domain)", "as_of": asof,
            "w_num": Wn, "w_den": Wd,
            "num_mass": mass_num(Wn), "den_mass": mass_den(Wd),
            "g_oov": {"num": overlaps("num", Wn), "den": overlaps("den", Wd)},
            "g_am_ii": Wn == Wd,
            "g_mc_i": True,        # metric, routing and binding all registered
        }
        c["g_mc_ii"] = c["den_mass"] > 0
        if not (c["g_oov"]["num"] and c["g_oov"]["den"]):
            got = "OOV"
        elif not c["g_am_ii"]:
            got = "AM"
        elif not c["g_mc_ii"]:
            got = "MC"
        else:
            got = "Bindable"
        assert got == cls, (tag, got, cls)
        if cls == "Bindable":
            c["value"] = c["num_mass"] / c["den_mass"]
        if cls == "AM":
            same = mass_den(Wn)   # the same-window reading the binding demands
            c["asked_value"] = c["num_mass"] / c["den_mass"]
            c["same_window_den"] = same
            c["same_window_value"] = c["num_mass"] / same
        if qid:  # assert the frozen gold label and certificate agree with the walk
            env, gold = cert_env(qid), QS[qid]
            cert = env["certificate"]
            byrole = {a["role"]: a for a in cert["anchors"]}
            assert cert["graph_pin"]["graph_version"] == "v1", qid
            assert cert["binding"]["rule"] == "same_valid_time_window", qid
            assert byrole["numerator"]["window"]["lo"] == Wn["lo"], qid
            assert byrole["numerator"]["window"]["hi_excl"] == Wn["hi_excl"], qid
            assert byrole["denominator"]["window"]["lo"] == Wd["lo"], qid
            assert byrole["numerator"]["coverage_mode"] == "hull", qid
            want = "ANSWER" if cls == "Bindable" else "REFUSE"
            assert cert["disclosure"]["decision"] == want, qid
            if cls == "Bindable":
                assert abs(c["value"] - gold["gold_value"]) < 1e-12, qid
                c["gold_value"] = gold["gold_value"]
            else:
                assert gold["refusal_reason"] == "missing-caliber", qid
                w = cert["refusal"]["witness"]
                assert w["type"] == "empty-denominator-probe", qid
                assert c["den_mass"] == 0, qid
                c["witness_type"] = w["type"]
            c["cert"] = os.path.join("impl", "certs2", qid + ".json")
        else:
            c["cert"] = None
        cells.append(c)
    con.close()

    eol = [c for c in cells if c["cls"] in ("OOV", "MC")]
    assert all(c["den_mass"] == 0 for c in eol)
    return {
        "version": "v1", "domain": "card_games", "metric": "ruling_intensity",
        "rule": "same_valid_time_window", "guard_chain": ["OOV", "AM", "MC"],
        "coverage": cov, "cells": cells,
        "n_certified": sum(1 for c in cells if c["cert"]),
        "boundary": {
            "mc_as_of": "2017-02", "oov_as_of": "2021-06",
            "hull_num_hi": cov["num"]["hi"], "hull_den_hi": cov["den"]["hi"],
            "jan_printings": mass_den_static(dbp, "2017-01"),
            "mar_printings": mass_den_static(dbp, "2017-03"),
        },
        "suite_note": "the suite's certified OOV / AM(ii) instances live in other "
                      "clusters (FIN-Q6, F1-Q6, DEB-Q6, EF2-Q5; FIN-Q8, W1-Q5); "
                      "rows (b) and (c) are read-only probes on this store",
    }


def mass_den_static(dbp, m):
    y, mo = int(m[:4]), int(m[5:7])
    hi = f"{y+1}-01-01" if mo == 12 else f"{y}-{mo+1:02d}-01"
    con = duckdb.connect(dbp, read_only=True)
    v = con.execute(f"SELECT COUNT(*) FROM cards t0 JOIN sets t1 ON "
                    f"t0.setCode = t1.code WHERE t1.releaseDate >= '{m}-01' "
                    f"AND t1.releaseDate < '{hi}'").fetchone()[0]
    con.close()
    return int(v)


# ============================= S5/S6: the forgery x check matrix (34 + 11 bases) ===
# The verifier's own frozen check order, read from the module we just imported.
CHECK_ORDER = list(chk.CHECK_ORDER)

# the 11 real-certificate bases, in forge_p2.py's own declaration order.
# CARD-Q2 joined on 2026-08-10 with family F5: no existing base was an ANSWER
# on a distinct-anchor ratio pair, which F5c requires.
BASE_QIDS = ["FIN-Q1", "F1-Q3", "CARD-Q2", "CARD-Q7", "EF2-Q6", "CA-Q5",
             "CODE-Q4", "CODE-Q6", "CODE-Q7", "TH-Q4", "TH-Q5"]
QID_DOMAIN = {
    "FIN-Q1": "financial", "F1-Q3": "formula_1", "CARD-Q2": "card_games",
    "CARD-Q7": "card_games",
    "EF2-Q6": "european_football_2", "CA-Q5": "california_schools",
    "CODE-Q4": "codebase_community", "CODE-Q6": "codebase_community",
    "CODE-Q7": "codebase_community", "TH-Q4": "thrombosis_prediction",
    "TH-Q5": "thrombosis_prediction",
}
# V6b clause-(0) markers (prior-guard negation), as in the legacy matrix; every
# other V6b failure text is the witness-replay clause (1).
V6B0_MARKERS = ("guard order violated", "replay undecidable", "¬MC replay")

FAMILY_SIZES = {"F1": 6, "F2": 5, "F3": 9, "F4": 10, "F5": 4}
N_FORGERIES = sum(FAMILY_SIZES.values())            # 34 since 2026-08-10


def forgery_matrix():
    files = sorted(glob.glob(os.path.join(FORGE_OUT, "F*.json")))
    files = [f for f in files if not os.path.basename(f).startswith("._")]
    assert len(files) == N_FORGERIES, len(files)

    cols, v6b_clause0 = [], 0
    for fp in files:
        d = jload(fp)
        name = os.path.basename(fp)[:-5]
        fid = name.split("_")[0]                       # F1a .. F4j (F3d2 incl.)
        rep, env = d["report"], d["envelope"]
        st = {c["check"]: c["status"] for c in rep["checks"]}
        assert sorted(st) == sorted(CHECK_ORDER), (fid, sorted(st))
        assert rep["verdict"] == "REJECT", fid
        assert rep["rejected_by"] == d["expected_reject_by"], (
            fid, rep["rejected_by"], d["expected_reject_by"])
        assert st[rep["rejected_by"]] == "FAIL", fid
        for c in rep["checks"]:
            if c["check"] == "V6b" and c["status"] == "FAIL" and \
                    any(k in (c.get("detail") or "") for k in V6B0_MARKERS):
                v6b_clause0 += 1
        cols.append({
            "id": fid, "band": fid[:2], "name": name,
            "qid": d["base_qid"],
            "dec": "REFUSE" if "refusal" in env else "ANSWER",
            "expected": d["expected_reject_by"],
            "rejected_by": rep["rejected_by"],
            "status": st,
        })

    fam = collections.Counter(c["band"] for c in cols)
    assert dict(fam) == FAMILY_SIZES, fam

    # the 10 unmutated bases, re-verified here with the same chk the forgeries
    # ran under (read-only; certificates and warehouses untouched)
    for qid in BASE_QIDS:
        env = cert_env(qid)
        qrec = next(x for x in questions(QID_DOMAIN[qid]) if x["qid"] == qid)
        con = duckdb.connect(os.path.join(DOM, QID_DOMAIN[qid], "warehouse.duckdb"),
                             read_only=True)
        try:
            rep = chk.verify(env, qrec, con, None, allow_declared_windows=True)
        finally:
            con.close()
        assert rep["verdict"] == "ACCEPT", (qid, rep["rejected_by"])
        st = {c["check"]: c["status"] for c in rep["checks"]}
        assert "FAIL" not in st.values(), (qid, st)
        cols.append({
            "id": "ctl-" + qid, "band": "ctl", "name": "unmutated base",
            "qid": qid,
            "dec": env["certificate"]["disclosure"]["decision"],
            "expected": None, "rejected_by": None, "status": st,
        })

    forg = [c for c in cols if c["band"] != "ctl"]
    load = {c: {k: sum(1 for f in forg if f["status"][c] == k)
                for k in ("FAIL", "PASS", "SKIP")} for c in CHECK_ORDER}
    first = collections.Counter(f["rejected_by"] for f in forg)
    never_first = [c for c in CHECK_ORDER if first.get(c, 0) == 0]
    never_fail = [c for c in CHECK_ORDER if load[c]["FAIL"] == 0]
    multi = {f["id"]: sorted(c for c in CHECK_ORDER if f["status"][c] == "FAIL")
             for f in forg
             if sum(1 for c in CHECK_ORDER if f["status"][c] == "FAIL") > 1}
    return {
        "checks": CHECK_ORDER,
        "check_order_src": "impl/asof_verifier/chk.py:CHECK_ORDER",
        "columns": cols,
        "families": dict(fam),
        "load": load,
        "first_reject": dict(first),
        "never_first": never_first,
        "never_fail": never_fail,
        "v6b_clause0_fails": v6b_clause0,
        "n_expected_match": len(forg),
        "n_bases": len(BASE_QIDS),
        "base_qids": BASE_QIDS,
        "multi_fail": multi,
        "declared_boundary": "a PARTIALLY omitted blocking set in a DB witness "
                             "(non-empty, all registered) is not rejected -- "
                             "only emptied (F4f) or unregistered (F4g) sets are",
    }


# =========================================== ablation ladder, all rungs recomputed ===
def num_eq(a, b, tol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    a, b = float(a), float(b)
    return abs(a) <= tol if b == 0 else abs(a - b) / abs(b) <= tol


# the frozen scorer dispatch (run_pilot2_arms.py section 4.2 / pilot2_summary
# "dispatch"): rowset-valued and string-valued golds; numeric otherwise
ROWSET_QIDS = {"CA-Q5", "CODE-Q4", "DEB-Q5", "TH-Q3"}
STRING_QIDS = {"CODE-Q6", "TH-Q4"}


def gold_match(qid, con, sql, gold):
    if qid in ROWSET_QIDS:
        rows = con.execute(sql).fetchall()
        if len(rows) != len(gold):
            return False
        for got, want in zip(rows, gold):
            if len(got) != len(want):
                return False
            for g, w in zip(got, want):
                if isinstance(w, (int, float)) and not isinstance(w, bool):
                    if not num_eq(g, w):
                        return False
                elif str(g) != str(w):
                    return False
        return True
    row = con.execute(sql).fetchone()
    if row is None:
        return False
    if qid in STRING_QIDS:
        return str(row[0]) == str(gold)
    return num_eq(row[0], gold)


def ablation():
    qs = all_questions()
    by_dom = collections.defaultdict(list)
    for qrec in qs:
        by_dom[qrec["domain"]].append(qrec)

    gold_ok = 0
    decisions = collections.Counter()
    rew_kinds = collections.Counter()
    db_refusals = []
    accept_normal = accept_strict = 0
    strict_rejects, wsrc_normal = [], collections.Counter()
    for d in DOMAINS:
        con = duckdb.connect(os.path.join(DOM, d, "warehouse.duckdb"), read_only=True)
        try:
            for qrec in by_dom[d]:
                env = cert_env(qrec["qid"])
                cert = env["certificate"]
                dec = cert["disclosure"]["decision"]
                decisions[dec] += 1
                if dec == "REWRITE":
                    kinds = {t.get("kind", "hull_trim")
                             for t in cert["rewrite"]["cut_trace"]}
                    assert len(kinds) == 1, (qrec["qid"], kinds)
                    rew_kinds[kinds.pop()] += 1
                if dec == "REFUSE" and env.get("refusal") == "disclosure-blocked":
                    db_refusals.append(qrec["qid"])
                # gold match on the shipped envelope, re-executed
                if qrec["expected_kind"] == "refusal":
                    ok = env.get("refusal") == qrec["refusal_reason"]
                else:
                    ok = gold_match(qrec["qid"], con, env["sql"], qrec["gold_value"])
                assert ok, qrec["qid"]
                gold_ok += 1
                # verifier, both tracks
                r1 = chk.verify(env, qrec, con, None, allow_declared_windows=True)
                r2 = chk.verify(env, qrec, con, None, allow_declared_windows=False)
                accept_normal += r1["verdict"] == "ACCEPT"
                wsrc_normal[(r1.get("independence") or {}).get("window_source")] += 1
                accept_strict += r2["verdict"] == "ACCEPT"
                if r2["verdict"] != "ACCEPT":
                    strict_rejects.append(
                        {"qid": qrec["qid"], "rejected_by": r2["rejected_by"]})
        finally:
            con.close()

    assert gold_ok == N_Q
    assert dict(decisions) == {"ANSWER": 33, "REWRITE": 12, "REFUSE": 15}
    assert dict(rew_kinds) == {"granularity_rollup": 5, "hull_trim": 5,
                               "mask_presentation": 2}, rew_kinds
    assert sorted(db_refusals) == ["CODE-Q7", "TH-Q5", "TH-Q6"]
    assert accept_normal == N_Q
    assert dict(wsrc_normal) == {"derived": 50, "declared": 8,
                                 "declared-override": 2}, wsrc_normal
    assert accept_strict == 50, accept_strict
    assert all(r["rejected_by"] == "V0" for r in strict_rejects)
    assert {r["qid"] for r in strict_rejects} == \
        {"CARD-Q5", "DEB-Q5", "DEB-Q7", "EF2-Q2", "EF2-Q4",
         "FIN-Q6", "FIN-Q8", "F1-Q6", "W1-Q4", "W1-Q5"}, strict_rejects

    n_gate = (rew_kinds_total := 0) or 0  # noqa: F841  (kept simple below)
    n_disc = 5 + 2 + 3   # rollups + masks + DB refusals, asserted above
    rungs = [
        {"id": "A1", "band": "compiler", "label": "full system",
         "correct": gold_ok, "lost": 0, "lost_classes": {},
         "provenance": "recomputed",
         "note": "gold match on the shipped envelopes, SQL re-executed: 60/60; "
                 "15 refusals all carry the gold refusal reason"},
        {"id": "A2", "band": "compiler", "label": "no rewrite layer",
         "correct": N_Q - decisions["REWRITE"], "lost": decisions["REWRITE"],
         "lost_classes": {"refused_should_answer": decisions["REWRITE"]},
         "provenance": "recomputed",
         "note": "refusing wherever the request is not directly bindable turns "
                 "the 12 REWRITE certificates (5 roll-ups + 5 hull trims + 2 "
                 "masks) into over-refusals"},
        {"id": "A3", "band": "compiler", "label": "no disclosure gate",
         "correct": N_Q - n_disc, "lost": n_disc,
         "lost_classes": {"wrong_value": 7, "answered_should_refuse": 3},
         "provenance": "recomputed",
         "note": "answering at the requested grain loses the 5 roll-ups + 2 "
                 "masks (fine-grained / unmasked values the policies forbid) "
                 "and answers the 3 DISCLOSURE-BLOCKED refusals"},
        {"id": "B1", "band": "verifier", "label": "as shipped",
         "correct": accept_normal, "lost": N_Q - accept_normal,
         "lost_classes": {}, "provenance": "recomputed",
         "note": "Chk ACCEPT 60/60 (window_source: derived 50 / declared 8 / "
                 "declared-override 2)"},
        {"id": "B2", "band": "verifier", "label": "no question-supplied windows",
         "correct": accept_strict, "lost": N_Q - accept_strict,
         "lost_classes": {"fail_closed_reject": N_Q - accept_strict},
         "provenance": "recomputed",
         "note": "--no-declared-windows: ACCEPT 50/60; all 10 rejects are V0 "
                 "fail-closed on the questions that present window coordinates "
                 "(8 range requests + 2 cross-window imperatives)"},
    ]
    for r in rungs:
        assert r["correct"] + r["lost"] == N_Q
        assert sum(r["lost_classes"].values()) == r["lost"]
    return {"n_questions": N_Q, "rungs": rungs,
            "strict_rejects": [r["qid"] for r in strict_rejects],
            "rewrite_kinds": dict(rew_kinds),
            "window_source": dict(wsrc_normal)}


# ============================================== S7: benchmark composition table ===
def benchmark():
    per = []
    for d in DOMAINS:
        prov = jload(os.path.join(DOM, d, "provenance.json"))
        real = sum(t["rows"] for t in prov["tables"].values() if not t["authored"])
        auth = sum(t["rows"] for t in prov["tables"].values() if t["authored"])
        big = max(((n, t["rows"]) for n, t in prov["tables"].items()
                   if not t["authored"]), key=lambda x: x[1])
        seed = prov["gov_seed_rows"]
        # anchors + coverage modes + policies, from the seed files themselves
        anchors = [json.loads(l) for l in open(
            os.path.join(DOM, d, "gov_seed", "gov_valid_time_anchor.jsonl"),
            encoding="utf-8") if l.strip()]
        modes = sorted({a["coverage_mode"] for a in anchors})
        anchor_ids = {a["anchor_id"] for a in anchors}
        # every anchor is registered under BOTH committed versions (no
        # is_current shortcut field): registry rows = 2 x distinct anchors
        assert len(anchors) == 2 * len(anchor_ids), d
        pol_path = os.path.join(DOM, d, "gov_seed", "gov_disclosure_policy.jsonl")
        pols = [json.loads(l) for l in open(pol_path, encoding="utf-8")
                if l.strip()] if os.path.exists(pol_path) else []
        assert len(pols) == seed["gov_disclosure_policy"], d
        vers = [json.loads(l) for l in open(
            os.path.join(DOM, d, "gov_seed", "gov_semantic_graph_version.jsonl"),
            encoding="utf-8") if l.strip()]
        assert len(vers) == seed["gov_semantic_graph_version"] == 2, d
        qs = questions(d)
        kinds = collections.Counter(x["expected_kind"] for x in qs)
        per.append({
            "domain": d,
            "source": prov["source"]["kind"],
            "real_rows": real, "authored_rows": auth,
            "largest_table": big[0], "largest_rows": big[1],
            "n_anchors": len(anchor_ids), "n_anchor_rows": len(anchors),
            "coverage_modes": modes,
            "versions": len(vers),
            "policy_rows": len(pols),
            "gov_seed_rows": sum(seed.values()),
            "n_q": len(qs),
            "q_value": kinds.get("value", 0),
            "q_rewrite": kinds.get("rewrite", 0),
            "q_refusal": kinds.get("refusal", 0),
        })
    tot_real = sum(p["real_rows"] for p in per)
    tot_auth = sum(p["authored_rows"] for p in per)
    tot_seed = sum(p["gov_seed_rows"] for p in per)
    tot_pol = sum(p["policy_rows"] for p in per)
    assert tot_real == 3830036, tot_real           # ACCEPTANCE_REPORT section 5.1
    assert tot_auth == 20094, tot_auth
    assert tot_seed == 847, tot_seed
    assert tot_pol == 18, tot_pol
    fin = next(p for p in per if p["domain"] == "financial")
    assert fin["largest_table"] == "trans" and fin["largest_rows"] == 1056320
    assert sum(p["n_q"] for p in per) == N_Q
    assert sum(p["q_value"] for p in per) == 33
    assert sum(p["q_rewrite"] for p in per) == 12
    assert sum(p["q_refusal"] for p in per) == 15
    return {"per_domain": per,
            "totals": {"real_rows": tot_real, "authored_rows": tot_auth,
                       "gov_seed_rows": tot_seed, "policy_rows": tot_pol,
                       "versions": sum(p["versions"] for p in per)}}


# ======================================================================== main ===
def main():
    arms = arms_block()
    data = {
        "n_questions": N_Q,
        "n_refusal_questions": 15,
        "n_value_questions": 33,
        "n_rewrite_questions": 12,
        "base": "pilot2 (9 public BIRD/Spider-derived DBs, frozen 2026-08-04)",
        **arms,
        "running_example": running_example(arms),
        "partition": partition_cells(),
        "forge": forgery_matrix(),
        "ablation": ablation(),
        "benchmark": benchmark(),
    }
    # keep the file compact: the per-question verdict matrix was only needed for
    # the cross-assertions and the two running-example rows already extracted
    del data["per_question_verdicts"]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print("wrote", OUT)
    R = data["running_example"]
    print(f"  running example {R['domain']}.{R['metric']}: "
          f"T1={R['t1']} {R['t1_num']}/{R['t1_den']}={R['t1_rate']:.4f} "
          f"({R['n_correct_at_t1']}/{R['n_llm']} LLM arms correct), "
          f"T2={R['t2']} ({R['t2_num']},{R['t2_den']}) -> MC(ii), "
          f"{R['n_answered_at_t2']}/{R['n_llm']} LLM arms answered")
    P = data["partition"]
    for c in P["cells"]:
        v = (f"{100*c['value']:.2f}%" if c["cls"] == "Bindable"
             else "_|_" + c["cls"])
        print(f"  partition ({c['tag']}) {c['cls']:9s} T={c['as_of']} "
              f"mu=({c['num_mass']},{c['den_mass']}) {v} "
              f"{c['qid'] or 'probe (no certificate)'}")
    F = data["forge"]
    print(f"  forgeries: {F['families']} -> {F['n_expected_match']}/{N_FORGERIES} "
          f"first reject == pre-registered; "
          f"bases {F['n_bases']}/{len(BASE_QIDS)} ACCEPT")
    print(f"  never-first: {F['never_first']}; never-fail: {F['never_fail']}; "
          f"V6b clause-0 fails: {F['v6b_clause0_fails']}")
    for r in data["ablation"]["rungs"]:
        print(f"  ladder {r['id']} {r['label']:32s} {r['correct']}/60 "
              f"lost {r['lost']:2d} {r['lost_classes']}")
    B = data["benchmark"]["totals"]
    print(f"  benchmark: real {B['real_rows']:,} + authored {B['authored_rows']:,} "
          f"rows; gov seed {B['gov_seed_rows']} rows; policies {B['policy_rows']}")


if __name__ == "__main__":
    main()
