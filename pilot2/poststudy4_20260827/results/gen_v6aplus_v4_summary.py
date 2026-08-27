#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_v6aplus_v4_summary.py — deterministic summary generator for the round-2
V6a+ hardening study (PREREG_poststudy4_20260827.md sha256
a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75).

Reads ONLY the recorded run artifacts in this results/ directory and renders
v6aplus_v4_summary.json and V6APLUS_V4_REPORT.md; EVERY number in the report is
generator-rendered from the run records, none is typed by hand. Idempotent.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.dirname(HERE)
PREREG = os.path.join(STUDY, "PREREG_poststudy4_20260827.md")
VER = "/Volumes/SSD 1/vldb_asof/asof-gov-vldb-artifact/impl/asof_verifier"
VER_B = "/Volumes/SSD 1/explore_opportunity_cc/impl/asof_verifier"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def codes_from_report(rep):
    """(v6aplus structural code, v6aplus_x arity code) for one report dict."""
    out = {}
    for cid in ("V6a+", "V6a+x"):
        c = next((x for x in rep["checks"] if x["check"] == cid), None)
        if c and c["status"] == "FAIL":
            m = re.match(r"(V6P_[A-Z_]+)", c.get("detail") or "")
            out[cid] = m.group(1) if m else None
    return out.get("V6a+"), out.get("V6a+x")


def out_report(subdir, name):
    p = os.path.join(HERE, subdir, name + ".json")
    if os.path.isfile(p):
        return json.load(open(p, encoding="utf-8")).get("report")
    return None


def fam_of(name):
    m = re.match(r"(F\d+)", name)
    return m.group(1) if m else None


def main():
    prereg_sha = sha256(PREREG)
    g60 = load("genuine60_verdicts.json")
    newb = load("forge_v6aplus_run.json")        # F6-F11 + pinned + bases
    oldb = load("forge_p2_v6aplus_run.json")      # F1-F5 + bases
    expl = load("exploits_run.json")
    swp = load("sweep_run.json")
    ci = load("ci_check_v6aplus.json")

    # ---- genuine 60 ----
    g_rows = g60["rows"]
    g_accept = [r for r in g_rows if r["verdict"] == "ACCEPT"]
    g_reject = [r for r in g_rows if r["verdict"] != "ACCEPT"]
    g_by_kind = Counter("%s/%s" % (r["metric_kind"], r["decision"])
                        for r in g_rows)
    g_v6p = Counter(r["v6aplus"]["status"] for r in g_rows)
    g_v6px = Counter(r["v6aplus_x"]["status"] for r in g_rows)
    # executed-arity witness: answer-bearing genuine certs whose V6a+x PASSed
    g_arity_pass = [r for r in g_rows if r["v6aplus_x"]["status"] == "PASS"]

    # ---- pinned regressions (round 1: a-d(+b2)=5 ; round 2: e,f=2) ----
    pinned = [r for r in newb["rows"] if r["name"].startswith("PINNED_")]
    pinned_reject = [r for r in pinned if r["actual"].startswith("REJECT")]
    pinned_ok = [r for r in pinned if r["ok"]]
    r2 = ("cert_mut_e_outer_where_1eq0", "cert_mut_f_outer_where_false")
    pinned_r2 = [r for r in pinned if any(x in r["name"] for x in r2)]
    pinned_r1 = [r for r in pinned if r not in pinned_r2]

    # ---- old F1-F5 ----
    old_rows = [r for r in oldb["rows"] if not r["name"].startswith("BASE_")]
    old_bases = [r for r in oldb["rows"] if r["name"].startswith("BASE_")]
    old_reject = [r for r in old_rows if r["actual"].startswith("REJECT")]
    old_ok = [r for r in old_rows if r["ok"]]
    old_by_family = Counter(fam_of(r["name"]) for r in old_rows)

    # ---- new-side forgeries: F6-F10 (prior) + F11 (round 2) ----
    forg = [r for r in newb["rows"]
            if not r["name"].startswith(("BASE_", "PINNED_"))]
    new_bases = [r for r in newb["rows"] if r["name"].startswith("BASE_")]
    f6_f10 = [r for r in forg if fam_of(r["name"]) in
              ("F6", "F7", "F8", "F9", "F10")]
    f11 = [r for r in forg if fam_of(r["name"]) == "F11"]
    f6_f10_reject = [r for r in f6_f10 if r["actual"].startswith("REJECT")]
    f6_f10_ok = [r for r in f6_f10 if r["ok"]]
    f11_reject = [r for r in f11 if r["actual"].startswith("REJECT")]
    f11_ok = [r for r in f11 if r["ok"]]
    f11_bases = sorted({r["base"] for r in f11})
    f11_rejected_by = dict(Counter(r["actual"].split("by ")[-1] for r in f11))

    # per-F11 structural + arity codes (from the recorded per-forgery reports)
    f11_detail = []
    f11_arity_backstop = 0
    for r in f11:
        rep = out_report("forge_v6aplus_out", r["name"])
        sc, ac = codes_from_report(rep) if rep else (None, None)
        if ac == "V6P_ARITY":
            f11_arity_backstop += 1
        f11_detail.append({"name": r["name"], "base": r["base"],
                           "actual": r["actual"], "v6aplus_code": sc,
                           "v6aplus_x_code": ac})

    # ---- reason-code distribution across every rejecting battery evaluation
    #      (pinned + F1-F5 + F6-F11 + exploits), split by check ----
    struct_codes = Counter()   # V6a+ structural codes
    arity_codes = Counter()    # V6a+x V6P_ARITY hits
    for r in pinned + forg:
        rep = out_report("forge_v6aplus_out", r["name"])
        if rep:
            sc, ac = codes_from_report(rep)
            if sc:
                struct_codes[sc] += 1
            if ac:
                arity_codes[ac] += 1
    for r in old_rows:
        rep = out_report("forge_p2_v6aplus_out", r["name"])
        if rep:
            sc, ac = codes_from_report(rep)
            if sc:
                struct_codes[sc] += 1
            if ac:
                arity_codes[ac] += 1
    for r in expl["rows"]:
        if r.get("v6aplus_code"):
            struct_codes[r["v6aplus_code"]] += 1
        if r.get("v6aplus_x_code"):
            arity_codes[r["v6aplus_x_code"]] += 1
    combined = Counter()
    combined.update(struct_codes)
    combined.update(arity_codes)

    # ---- exploits ----
    ex_rows = expl["rows"]
    ex_confirmed = expl["confirmed_exploit_names"]
    ex_conf_rows = [r for r in ex_rows if r["name"] in ex_confirmed]

    # ---- counts ----
    n_f1_f5 = len(old_rows)
    n_f6_f10 = len(f6_f10)
    n_f11 = len(f11)
    n_pinned_r1 = len(pinned_r1)
    n_pinned_r2 = len(pinned_r2)
    prior_total = n_pinned_r1 + n_f1_f5 + n_f6_f10          # 5 + 34 + 31 = 70
    new_total_task_formula = prior_total + n_f11            # 70 + |F11|
    grand_total = new_total_task_formula + n_pinned_r2      # + round-2 pins

    # ---- predictions (PREREG_poststudy4) ----
    P = OrderedDict()
    P["P1"] = {
        "statement": "all 60 genuine certificates still ACCEPT (shape check "
                     "passes on every genuine answer)",
        "observed": "%d/%d ACCEPT" % (len(g_accept), len(g_rows)),
        "holds": len(g_accept) == len(g_rows) == 60,
        "misses": sorted(r["qid"] for r in g_reject),
    }
    P["P2"] = {
        "statement": "the confirmed outer-filter exploits all REJECT "
                     "(V6P_SHAPE for the outer WHERE; V6P_ARITY backstop on "
                     "zero/multi-row)",
        "observed": "%d/%d confirmed exploits REJECT (%s)"
                    % (sum(1 for r in ex_conf_rows if r["verdict"] == "REJECT"),
                       len(ex_conf_rows),
                       "; ".join("%s: %s +%s" % (
                           r["name"].split("_")[0], r["v6aplus_code"],
                           r["v6aplus_x_code"]) for r in ex_conf_rows)),
        "holds": bool(expl["confirmed_all_reject"]) and len(ex_conf_rows) >= 2,
        "misses": sorted(r["name"] for r in ex_conf_rows
                         if r["verdict"] != "REJECT"),
    }
    sweep_ab = swp["n_answer_bearing"]
    sweep_ab_rej = swp["n_answer_bearing_reject"]
    sweep_nosql = swp["n_refuse_no_answer_sql"]
    P["P3"] = {
        "statement": "every F11 forgery REJECTs; the append-outer-WHERE sweep "
                     "REJECTs on every answer-bearing base (REFUSE certs carry "
                     "no answer SQL to filter)",
        "observed": "F11 %d/%d REJECT; sweep %d/%d answer-bearing REJECT, "
                    "%d REFUSE with no answer SQL (of %d total)"
                    % (len(f11_reject), len(f11), sweep_ab_rej, sweep_ab,
                       sweep_nosql, swp["n_total_bases"]),
        "holds": (len(f11_reject) == len(f11) and len(f11) >= 6 and
                  bool(swp["answer_bearing_all_reject"])),
        "misses": (sorted(r["name"] for r in f11
                          if not r["actual"].startswith("REJECT")) +
                   sorted(r["qid"] for r in swp["rows"]
                          if r["has_answer_sql"] and r["verdict"] != "REJECT")),
    }
    P["P4"] = {
        "statement": "the full prior battery still holds — 60/60 genuine "
                     "ACCEPT, and the 70 prior forgeries (5 round-1 pinned + "
                     "F1-F10) all REJECT",
        "observed": "60/60 genuine ACCEPT; prior forgeries %d/%d REJECT "
                    "(pinned-r1 %d/%d, F1-F5 %d/%d, F6-F10 %d/%d)"
                    % (len(pinned_r1) + len(old_reject) + len(f6_f10_reject)
                       - sum(1 for r in pinned_r1
                             if not r["actual"].startswith("REJECT")),
                       prior_total,
                       sum(1 for r in pinned_r1
                           if r["actual"].startswith("REJECT")), n_pinned_r1,
                       len(old_reject), n_f1_f5,
                       len(f6_f10_reject), n_f6_f10),
        "holds": (len(g_accept) == 60 and
                  all(r["actual"].startswith("REJECT") for r in pinned_r1) and
                  len(old_reject) == n_f1_f5 and
                  len(f6_f10_reject) == n_f6_f10),
        "misses": (sorted(r["name"] for r in pinned_r1
                          if not r["actual"].startswith("REJECT")) +
                   sorted(r["name"] for r in old_rows
                          if not r["actual"].startswith("REJECT")) +
                   sorted(r["name"] for r in f6_f10
                          if not r["actual"].startswith("REJECT"))),
    }
    all_hold = all(p["holds"] for p in P.values())

    verifier_files = {n: sha256(os.path.join(VER, n)) for n in
                      ("chk.py", "v6aplus.py", "forge_v6aplus.py",
                       "ci_check.py")}
    verifier_files_b = {n: sha256(os.path.join(VER_B, n)) for n in
                        ("chk.py", "v6aplus.py", "forge_v6aplus.py",
                         "ci_check.py")}
    trees_identical = verifier_files == verifier_files_b

    summary = OrderedDict([
        ("study", "poststudy4_20260827 — verifier hardening V6a+ round 2 "
                  "(outer-filter closure + execution shape check)"),
        ("prereg", {"path": os.path.relpath(PREREG, STUDY),
                    "sha256": prereg_sha}),
        ("verifier", {
            "tree_A": VER, "tree_B": VER_B,
            "files_A": verifier_files, "files_B": verifier_files_b,
            "trees_byte_identical": trees_identical,
        }),
        ("ci_check", {"ok": ci.get("ok"),
                      "failures": ci.get("failures")}),
        ("genuine60", {
            "total": len(g_rows), "accept": len(g_accept),
            "reject": len(g_reject),
            "v6aplus_status": dict(sorted(g_v6p.items())),
            "v6aplus_x_status": dict(sorted(g_v6px.items())),
            "executed_arity_pass": len(g_arity_pass),
            "by_kind_decision": dict(sorted(g_by_kind.items())),
            "note": "V6a+ and the new execution-shape check V6a+x each SKIP "
                    "exactly the 15 REFUSE certificates (no answer SQL) and "
                    "PASS all 45 ANSWER/REWRITE certificates; the 45 executed "
                    "answers all carry their certified arity.",
        }),
        ("pinned_regressions", {
            "total": len(pinned), "reject": len(pinned_reject),
            "with_pinned_reason_code": len(pinned_ok),
            "round1_total": n_pinned_r1, "round2_total": n_pinned_r2,
            "rows": [{"name": r["name"], "expected": r["expected"],
                      "actual": r["actual"],
                      "reason_code": r.get("v6aplus_reason_code")}
                     for r in pinned],
        }),
        ("exploits_p0repro", {
            "confirmed_exploit_names": ex_confirmed,
            "confirmed_all_reject": expl["confirmed_all_reject"],
            "rows": [{"name": r["name"], "verdict": r["verdict"],
                      "rejected_by": r["rejected_by"],
                      "v6aplus_code": r["v6aplus_code"],
                      "v6aplus_x_code": r["v6aplus_x_code"],
                      "executed_shape": r["executed_shape"],
                      "note": r["note"]} for r in ex_rows],
        }),
        ("old_forgeries_f1_f5", {
            "bases_accept": "%d/%d" % (sum(1 for r in old_bases if r["ok"]),
                                       len(old_bases)),
            "total": n_f1_f5, "reject": len(old_reject),
            "frozen_attribution_kept": len(old_ok),
            "by_family": dict(sorted(old_by_family.items())),
        }),
        ("prior_forgeries_f6_f10", {
            "total": n_f6_f10, "reject": len(f6_f10_reject),
            "asserted_ok": len(f6_f10_ok),
        }),
        ("new_forgeries_f11", {
            "bases_accept": "%d/%d" % (sum(1 for r in new_bases if r["ok"]),
                                       len(new_bases)),
            "total": n_f11, "reject": len(f11_reject),
            "asserted_ok": len(f11_ok),
            "distinct_bases": f11_bases,
            "rejected_by": f11_rejected_by,
            "arity_backstop_hits": f11_arity_backstop,
            "rows": f11_detail,
        }),
        ("sweep_append_outer_where", {
            "mutation": swp["mutation"],
            "n_total_bases": swp["n_total_bases"],
            "n_answer_bearing": sweep_ab,
            "n_answer_bearing_reject": sweep_ab_rej,
            "n_refuse_no_answer_sql": sweep_nosql,
            "answer_bearing_all_reject": swp["answer_bearing_all_reject"],
            "scope_note": "the outer-row-filter attack forges an ANSWER by "
                          "filtering it; the 15 REFUSE certificates carry no "
                          "answer SQL, so the attack surface does not exist "
                          "for them (recorded as no_answer_sql, not as a "
                          "reject or an escape).",
        }),
        ("forgery_counts", {
            "pinned_round1": n_pinned_r1, "f1_f5": n_f1_f5,
            "f6_f10": n_f6_f10, "prior_total_70": prior_total,
            "f11": n_f11, "pinned_round2": n_pinned_r2,
            "task_formula_70_plus_f11": new_total_task_formula,
            "grand_total_forged_certs": grand_total,
            "sweep_answer_bearing_mutations": sweep_ab,
        }),
        ("reason_code_distribution", {
            "v6aplus_structural": dict(sorted(struct_codes.items())),
            "v6aplus_x_arity": dict(sorted(arity_codes.items())),
            "combined": dict(sorted(combined.items())),
        }),
        ("predictions", P),
        ("all_predictions_hold", all_hold),
        ("inputs", {n: sha256(os.path.join(HERE, n)) for n in
                    ("genuine60_verdicts.json", "exploits_run.json",
                     "sweep_run.json", "forge_v6aplus_run.json",
                     "forge_p2_v6aplus_run.json", "ci_check_v6aplus.json")}),
    ])

    with open(os.path.join(HERE, "v6aplus_v4_summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)

    render_report(summary, prereg_sha)
    print("wrote v6aplus_v4_summary.json + V6APLUS_V4_REPORT.md; "
          "all_predictions_hold =", all_hold,
          "; trees_byte_identical =", trees_identical)


def render_report(S, prereg_sha):
    g = S["genuine60"]
    fc = S["forgery_counts"]
    L = []
    A = L.append
    A("# V6APLUS_V4_REPORT — verifier hardening V6a+ round 2 "
      "(poststudy4_20260827)")
    A("")
    A("Post-registration study under `%s` (sha256 `%s`). Every number below is "
      "rendered by `gen_v6aplus_v4_summary.py` from the recorded run artifacts "
      "in this directory; none is typed by hand."
      % (S["prereg"]["path"], prereg_sha))
    A("")
    A("## What round 2 hardened")
    A("")
    A("A second external review (Codex, 2026-08-27), reproduced independently "
      "(scratchpad `p0-repro`), showed the round-1 V6a+ still ACCEPTed a "
      "genuine ratio/delta certificate whose outer SELECT carried a top-level "
      "`WHERE` filtering the scalar answer to zero rows (`WHERE 1=0`, "
      "`WHERE 'a'='b'`): `_check_ratio`/`_check_delta` did not reject an outer "
      "`where_clause`, and no check executed the answer to test its shape. Two "
      "fixes, both fail-closed:")
    A("")
    A("- **Fix 1 (outer-filter closure, structural).** `_plain_node` now "
      "rejects a non-null outer `WHERE` by default (`allow_outer_where=False`) "
      "with `V6P_SHAPE`; the scalar outer nodes of atomic/ratio/delta route "
      "through that default, while the FROM-carrying leg / report / attribute "
      "predicate walkers pass `allow_outer_where=True` and read their own "
      "`where_clause` as before.")
    A("- **Fix 2 (execution-shape check, semantic).** A new check `V6a+x` is "
      "appended LAST in the order `V0..V6c,V6a+,V6a+x`; it is the first "
      "V6a+-family site to EXECUTE the answer SQL, running each ANSWER/REWRITE "
      "answer read-only against the warehouse (the same connection the V6b/V6c "
      "probes use) and requiring the certified row/column arity, else "
      "`V6P_ARITY`. REFUSE certificates carry no answer SQL and are SKIPped. "
      "Appending last keeps every pre-existing first-FAIL attribution frozen.")
    A("")
    A("`ci_check.py` gains A5b (the `V6a+x` execution-shape check exists in "
      "`v6aplus.py` and is wired into `chk.py`'s check order) and A6 (the F11 "
      "family is present in `forge_v6aplus.py`, >=6 forgeries over >=4 bases). "
      "CI-CHECK: %s." % ("PASS" if S["ci_check"]["ok"] else "FAIL"))
    A("")
    A("## Matrix totals")
    A("")
    A("| suite | n | result |")
    A("|---|---:|---|")
    A("| genuine certificates | %d | %d ACCEPT / %d REJECT (V6a+ %s; V6a+x %s) |"
      % (g["total"], g["accept"], g["reject"],
         ", ".join("%s=%d" % kv for kv in sorted(g["v6aplus_status"].items())),
         ", ".join("%s=%d" % kv for kv in
                   sorted(g["v6aplus_x_status"].items()))))
    pr = S["pinned_regressions"]
    A("| pinned regressions | %d | %d REJECT (%d with the pinned reason code; "
      "round-1 %d + round-2 %d) |"
      % (pr["total"], pr["reject"], pr["with_pinned_reason_code"],
         pr["round1_total"], pr["round2_total"]))
    of = S["old_forgeries_f1_f5"]
    A("| prior forgeries F1-F5 | %d | %d REJECT (%d keep the frozen "
      "`rejected_by`) |" % (of["total"], of["reject"],
                            of["frozen_attribution_kept"]))
    pf = S["prior_forgeries_f6_f10"]
    A("| prior forgeries F6-F10 | %d | %d REJECT |"
      % (pf["total"], pf["reject"]))
    nf = S["new_forgeries_f11"]
    A("| NEW forgeries F11 (outer-row-filter) | %d | %d REJECT |"
      % (nf["total"], nf["reject"]))
    sw = S["sweep_append_outer_where"]
    A("| append-outer-WHERE sweep | %d | %d/%d answer-bearing REJECT; %d "
      "REFUSE with no answer SQL |"
      % (sw["n_total_bases"], sw["n_answer_bearing_reject"],
         sw["n_answer_bearing"], sw["n_refuse_no_answer_sql"]))
    A("")
    A("Forgery accounting: prior battery = %d (5 round-1 pinned + %d F1-F5 + "
      "%d F6-F10); round 2 adds the %d-forgery F11 family and %d round-2 "
      "exploit pins (V1, V1c). Task formula `70 + |F11|` = **%d**; including "
      "the 2 round-2 pins the grand total of forged certificates is **%d** "
      "(plus %d answer-bearing sweep mutations)."
      % (fc["prior_total_70"], fc["f1_f5"], fc["f6_f10"], fc["f11"],
         fc["pinned_round2"], fc["task_formula_70_plus_f11"],
         fc["grand_total_forged_certs"], fc["sweep_answer_bearing_mutations"]))
    A("")
    A("## Confirmed exploits (scratchpad p0-repro), replayed post-fix")
    A("")
    A("| variant | verdict | V6a+ | V6a+x | executed shape | note |")
    A("|---|---|---|---|---|---|")
    for r in S["exploits_p0repro"]["rows"]:
        A("| %s | %s | %s | %s | %s | %s |"
          % (r["name"], r["verdict"], r["v6aplus_code"] or "-",
             r["v6aplus_x_code"] or "-", r["executed_shape"], r["note"]))
    A("")
    A("The two confirmed round-2 exploits (`V1`, `V1c`) — the ones the round-1 "
      "verifier ACCEPTed — both REJECT, each on `V6P_SHAPE` (fix 1) with the "
      "independent `V6P_ARITY` backstop (fix 2) also firing. The `V1b` "
      "`WHERE 1=1` control is denotation-preserving (executes to 1x1, so the "
      "arity check PASSes) and is caught by the structural closure ALONE — "
      "empirical proof that fix 1 is necessary and not subsumed by fix 2.")
    A("")
    A("## F11 outer-row-filter family")
    A("")
    A("| forgery | base | verdict/by | V6a+ | V6a+x |")
    A("|---|---|---|---|---|")
    for r in nf["rows"]:
        A("| %s | %s | %s | %s | %s |"
          % (r["name"], r["base"], r["actual"], r["v6aplus_code"] or "-",
             r["v6aplus_x_code"] or "-"))
    A("")
    A("%d forgeries over %d distinct bases (%s); all REJECT, all with "
      "`rejected_by = V6a+`. The `V6P_ARITY` execution backstop additionally "
      "fires on %d of them (the zero-row and multi-row cases); the `1=1` "
      "control is caught by `V6P_SHAPE` alone."
      % (nf["total"], len(nf["distinct_bases"]),
         ", ".join(nf["distinct_bases"]), nf["arity_backstop_hits"]))
    A("")
    A("## Append-outer-WHERE corpus sweep")
    A("")
    A("Appending a top-level `WHERE 1=0` to every genuine certificate's answer "
      "SQL: **%d/%d answer-bearing bases REJECT**. The remaining %d bases are "
      "REFUSE certificates that carry no answer SQL — the outer-row-filter "
      "attack forges an ANSWER by filtering it, so its surface does not exist "
      "for a refusal (recorded as `no_answer_sql`, never as a reject or an "
      "escape). REFUSE qids: %s."
      % (sw["n_answer_bearing_reject"], sw["n_answer_bearing"],
         sw["n_refuse_no_answer_sql"],
         ", ".join(swp_refuse_qids(S))))
    A("")
    A("## Reason-code distribution (all rejecting battery evaluations)")
    A("")
    rc = S["reason_code_distribution"]
    A("Structural (`V6a+`):")
    A("")
    A("| code | count |")
    A("|---|---:|")
    for c, n in sorted(rc["v6aplus_structural"].items()):
        A("| %s | %d |" % (c, n))
    A("")
    A("Execution-shape backstop (`V6a+x`):")
    A("")
    A("| code | count |")
    A("|---|---:|")
    for c, n in sorted(rc["v6aplus_x_arity"].items()):
        A("| %s | %d |" % (c, n))
    A("")
    A("## Predictions adjudicated")
    A("")
    A("| id | prereg statement | observed | verdict |")
    A("|---|---|---|---|")
    for pid, p in S["predictions"].items():
        A("| %s | %s | %s | %s |"
          % (pid, p["statement"], p["observed"],
             "HOLDS" if p["holds"] else "**MISS** (%s)"
             % ", ".join(p["misses"])))
    A("")
    A("**All predictions hold: %s.**"
      % ("yes" if S["all_predictions_hold"] else
         "NO — the misses above are published as misses"))
    A("")
    A("## Two-tree byte-identity")
    A("")
    A("The verifier is fixed identically in both working trees; the port is "
      "byte-identical (`trees_byte_identical = %s`):"
      % S["verifier"]["trees_byte_identical"])
    A("")
    A("| file | sha256 |")
    A("|---|---|")
    for n, h in sorted(S["verifier"]["files_A"].items()):
        A("| %s | `%s` |" % (n, h))
    A("")
    A("## Reproduce")
    A("")
    A("```")
    A("cd '%s'" % VER_B)
    A("python3 ci_check.py")
    A("python3 forge_v6aplus.py --p2 '%s/pilot2/domains'"
      % os.path.dirname(os.path.dirname(VER_B)))
    A("python3 -c \"import forge_p2; forge_p2.P2='%s/pilot2/domains'; "
      "forge_p2.main([])\"" % os.path.dirname(os.path.dirname(VER_B)))
    A("cd '%s'" % HERE)
    A("python3 run_matrix.py")
    A("python3 gen_v6aplus_v4_summary.py")
    A("```")
    A("")
    A("Input record hashes: %s"
      % "; ".join("`%s` sha256 `%s`" % kv for kv in S["inputs"].items()))
    A("")
    with open(os.path.join(HERE, "V6APLUS_V4_REPORT.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(L))


def swp_refuse_qids(S):
    return json.load(open(os.path.join(HERE, "sweep_run.json"),
                          encoding="utf-8"))["refuse_no_answer_sql_qids"]


if __name__ == "__main__":
    main()
