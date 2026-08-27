#!/usr/bin/env python3
# ---------------------------------------------------------------------
# gen_tr_poststudy4.py -- emit paper/tr/generated/poststudy4_20260827.tex:
# the round-2 external-review response appendix + a statistics appendix.
#
#   (1) "External-Review Response II: Outer-Filter Closure & Executed-
#       Arity Check (2026-08-27)" [app:poststudy4] -- the post-
#       registration V6a+ round-2 hardening study: the disclosed round-1
#       residual gap (an outer WHERE that empties a genuine ratio/atomic
#       answer, which the round-1 V6a+ still ACCEPTed), the two fixes
#       (Fix 1 outer-filter closure -> V6P_SHAPE; Fix 2 executed-arity
#       check V6a+x -> V6P_ARITY), the full battery (60 genuine / 7 pinned
#       regressions / 34 F1-F5 / 31 F6-F10 / 8 F11 / the 45-base append-
#       outer-WHERE sweep), the reason-code distribution, the two pinned
#       exploit SQLs (V1, V1c), and the P1-P4 prediction scoreboard.
#
#   (2) "Governance-Arm Statistics from the Frozen Verdict Matrix
#       (2026-08-27)" [app:poststudy4stats] -- computed deterministically
#       FROM the frozen per-question verdict matrix: the McNemar test
#       reference-vs-governance, the per-question paired-difference
#       (discordant-pair) table, cluster-bootstrap 95% CIs (the frozen
#       per-arm error CIs plus a seeded paired gov-ref difference CI),
#       the answer/rewrite/refusal stratified accuracy per arm, and the
#       refusal-decision macro-F1 per arm.  Every number is re-derived
#       here and cross-checked against the frozen summary's own slices;
#       nothing is hand-typed.
#
# Sources of record (ALL numbers flow through here; nothing hand-typed):
#   pilot2/poststudy4_20260827/PREREG_poststudy4_20260827.md  (frozen;
#       sha re-computed and asserted == the registered constant below)
#   pilot2/poststudy4_20260827/results/v6aplus_v4_summary.json (battery;
#       its six input-record hashes are re-computed from the sibling
#       files and asserted -- the chain the study record commits to)
#   pilot2/poststudy4_20260827/results/exploits_run.json  (the pinned
#       exploit SQL text for V1 and V1c, byte-verbatim from the record)
#   pilot2/pilot2_arms_summary.json  (frozen arms study; sha asserted;
#       the per-question verdict matrix + slices the statistics use)
#
# The statistics are deterministic: the McNemar 2x2 and the stratified
# and macro-F1 tables are exact functions of the frozen matrix, and the
# paired cluster bootstrap uses a fixed seed and fixed B, disclosed in
# the emitted prose.  Prediction misses are rendered as misses; the four
# poststudy4 predictions all held and the scoreboard says so from the
# JSON, but a miss, were one recorded, would be listed first.
#
# Regenerate:  python3 pilot2/poststudy4_20260827/gen_tr_poststudy4.py
# (invoked by paper/tr/build.sh step 1)
# ---------------------------------------------------------------------
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from math import comb, erfc, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))       # .../pilot2/poststudy4_20260827
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))  # .../explore_opportunity_cc
OUT = os.path.join(ROOT, "paper", "tr", "generated", "poststudy4_20260827.tex")

PREREG_MD = os.path.join(HERE, "PREREG_poststudy4_20260827.md")
PREREG_SHA_REGISTERED = \
    "a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75"
SUMMARY_JSON = os.path.join(HERE, "results", "v6aplus_v4_summary.json")
EXPLOITS_JSON = os.path.join(HERE, "results", "exploits_run.json")
ARMS_JSON = os.path.join(ROOT, "pilot2", "pilot2_arms_summary.json")
ARMS_SHA_REGISTERED = \
    "2604bff0e7632c0e367a124ba5717d33cf858fba2e46417e35d8d740b29ef90e"

REF = "baseline_claude"          # the reference (backbone) arm
GOV = "governance_informed"      # the governance-informed arm
ARMS8 = ["baseline_claude", "baseline_qwen", "baseline_deepseek",
         "baseline_minimax", "trivial_claude", "trivial_v2", "trivial_v3",
         "governance_informed"]
# qid-prefix -> public DB (the nine bootstrap clusters)
PREFIX_DB = {"CA": "california_schools", "CARD": "card_games",
             "CODE": "codebase_community", "DEB": "debit_card_specializing",
             "EF2": "european_football_2", "FIN": "financial",
             "F1": "formula_1", "TH": "thrombosis_prediction",
             "W1": "world_1"}
BOOT_SEED = 20260827             # disclosed in the emitted prose
BOOT_B = 10000                   # disclosed in the emitted prose


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def esc(s):
    out = []
    for ch in str(s):
        out.append({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
                    "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
                    "}": r"\}", "~": r"\textasciitilde{}",
                    "^": r"\textasciicircum{}", "§": r"\S{}",
                    "—": "---", "–": "--", "≥": r"\ensuremath{\ge}",
                    "‘": "`", "’": "'", "“": "``", "”": "''",
                    }.get(ch, ch))
    return "".join(out)


def tt(s):
    return r"\texttt{%s}" % esc(s)


def dom(q):
    return PREFIX_DB[q.split("-")[0]]


def main():
    # ---- 0. freeze + chain verification --------------------------------
    sha = sha256(PREREG_MD)
    assert sha == PREREG_SHA_REGISTERED, \
        f"PREREG sha mismatch: {sha} != registered {PREREG_SHA_REGISTERED}"
    J = json.load(open(SUMMARY_JSON, encoding="utf-8"))
    assert J["prereg"]["sha256"] == PREREG_SHA_REGISTERED, J["prereg"]
    for fname, want in J["inputs"].items():
        got = sha256(os.path.join(HERE, "results", fname))
        assert got == want, f"input-record hash drift for {fname}: {got}"
    ash = sha256(ARMS_JSON)
    assert ash == ARMS_SHA_REGISTERED, \
        f"arms summary sha drift: {ash} != registered {ARMS_SHA_REGISTERED}"

    # ---- 1. battery cross-derivation (V6a+ round 2) --------------------
    G = J["genuine60"]
    assert (G["total"], G["accept"], G["reject"]) == (60, 60, 0), G
    assert G["v6aplus_status"] == {"PASS": 45, "SKIP": 15}, G
    assert G["v6aplus_x_status"] == {"PASS": 45, "SKIP": 15}, G
    assert G["executed_arity_pass"] == 45, G
    assert sum(G["by_kind_decision"].values()) == 60, G["by_kind_decision"]
    n_refuse = sum(v for k, v in G["by_kind_decision"].items()
                   if k.endswith("/REFUSE"))
    assert n_refuse == G["v6aplus_status"]["SKIP"] == 15, n_refuse

    P = J["pinned_regressions"]
    assert P["total"] == P["reject"] == P["with_pinned_reason_code"] \
        == len(P["rows"]) == 7, P
    assert (P["round1_total"], P["round2_total"]) == (5, 2), P
    for r in P["rows"]:
        assert f"REJECT({r['reason_code']})" == r["expected"], r
        assert r["actual"] == "REJECT by V6a+", r

    OLD = J["old_forgeries_f1_f5"]
    assert OLD["total"] == OLD["reject"] == OLD["frozen_attribution_kept"] \
        == sum(OLD["by_family"].values()) == 34, OLD
    assert OLD["bases_accept"] == "11/11", OLD
    PRIOR = J["prior_forgeries_f6_f10"]
    assert PRIOR["total"] == PRIOR["reject"] == PRIOR["asserted_ok"] == 31, PRIOR
    F11 = J["new_forgeries_f11"]
    assert F11["total"] == F11["reject"] == F11["asserted_ok"] \
        == len(F11["rows"]) == 8, F11
    assert F11["bases_accept"] == "23/23", F11
    assert F11["rejected_by"] == {"V6a+": 8}, F11
    assert F11["arity_backstop_hits"] == 7, F11
    assert len(set(F11["distinct_bases"])) == 8, F11

    SW = J["sweep_append_outer_where"]
    assert (SW["n_total_bases"], SW["n_answer_bearing"],
            SW["n_answer_bearing_reject"], SW["n_refuse_no_answer_sql"]) \
        == (60, 45, 45, 15), SW
    assert SW["answer_bearing_all_reject"] is True, SW

    FC = J["forgery_counts"]
    assert FC["prior_total_70"] == 5 + 34 + 31 == 70, FC
    assert FC["task_formula_70_plus_f11"] == 70 + F11["total"] == 78, FC
    assert FC["grand_total_forged_certs"] == 80, FC
    prior_total = FC["prior_total_70"]
    family_total = FC["task_formula_70_plus_f11"]  # 78

    RC = J["reason_code_distribution"]["combined"]
    assert sum(RC.values()) == 70, RC          # all rejecting battery evals
    assert RC["V6P_ARITY"] == 17, RC

    EXP = J["exploits_p0repro"]
    assert EXP["confirmed_exploit_names"] == \
        ["V1_outer_where_1eq0", "V1c_outer_where_false"], EXP
    assert EXP["confirmed_all_reject"] is True, EXP

    PRED = J["predictions"]
    assert list(PRED) == ["P1", "P2", "P3", "P4"], list(PRED)
    assert J["all_predictions_hold"] == all(
        PRED[p]["holds"] and PRED[p]["misses"] == [] for p in PRED), PRED
    order = sorted(PRED, key=lambda p: (PRED[p]["holds"], p))  # misses first
    n_miss = sum(1 for p in PRED if not PRED[p]["holds"])

    VF = J["verifier"]["files_A"]
    assert J["verifier"]["files_A"] == J["verifier"]["files_B"], J["verifier"]
    assert J["verifier"]["trees_byte_identical"] is True, J["verifier"]
    assert J["ci_check"]["ok"] is True and J["ci_check"]["failures"] == [], J

    # the pinned exploit SQLs, byte-verbatim from the recorded run
    EX = json.load(open(EXPLOITS_JSON, encoding="utf-8"))
    exsql = {r["name"]: r["sql"] for r in EX["rows"]}
    for nm in ("V1_outer_where_1eq0", "V1c_outer_where_false"):
        assert exsql[nm].strip().endswith(("WHERE 1=0", "WHERE 'a'='b'")), \
            exsql[nm]

    # ---- 2. statistics from the frozen verdict matrix ------------------
    A = json.load(open(ARMS_JSON, encoding="utf-8"))
    V = A["per_question_verdicts"]
    qids = sorted(V)
    assert len(qids) == 60, len(qids)
    EC = A["error_counts"]

    def correct(arm, q):
        return V[q][arm] == "correct"

    # cluster map cross-check against the frozen per-cluster slice
    cc = Counter(dom(q) for q in qids)
    pcl = A["slices"]["per_cluster"][REF]
    for d in cc:
        assert cc[d] == pcl[d]["n"], (d, cc[d], pcl[d]["n"])

    # 2a. McNemar reference vs governance (exact 2x2 over 60 questions)
    n11 = sum(1 for q in qids if correct(REF, q) and correct(GOV, q))
    b = sum(1 for q in qids if correct(REF, q) and not correct(GOV, q))
    c = sum(1 for q in qids if not correct(REF, q) and correct(GOV, q))
    n00 = sum(1 for q in qids if not correct(REF, q) and not correct(GOV, q))
    assert (n11, b, c, n00) == (19, 5, 13, 23), (n11, b, c, n00)
    disc = b + c
    chi2_cc = (abs(b - c) - 1) ** 2 / disc
    chi2_p = erfc(sqrt(chi2_cc / 2))                  # 1-dof survival
    k = min(b, c)
    p_exact = min(1.0, 2 * sum(comb(disc, i)
                               for i in range(k + 1)) / 2 ** disc)
    assert round(chi2_cc, 4) == 2.7222, chi2_cc
    assert round(p_exact, 4) == 0.0963, p_exact
    ref_acc = (60 - EC[REF]) / 60
    gov_acc = (60 - EC[GOV]) / 60
    assert (round(ref_acc, 4), round(gov_acc, 4)) == (0.4, 0.5333), \
        (ref_acc, gov_acc)

    # 2b. per-question discordant pairs (the paired differences)
    fixes = [q for q in qids if not correct(REF, q) and correct(GOV, q)]
    breaks = [q for q in qids if correct(REF, q) and not correct(GOV, q)]
    assert (len(fixes), len(breaks)) == (c, b) == (13, 5), (fixes, breaks)

    # 2c. paired cluster bootstrap for the gov-ref accuracy difference
    doms = sorted(cc)
    by = {d: [q for q in qids if dom(q) == d] for d in doms}

    def acc(arm, qs):
        return sum(1 for q in qs if correct(arm, q)) / len(qs)

    rng = random.Random(BOOT_SEED)
    diffs = []
    for _ in range(BOOT_B):
        samp = []
        for _ in range(len(doms)):
            samp += by[rng.choice(doms)]
        diffs.append(acc(GOV, samp) - acc(REF, samp))
    diffs.sort()
    b_lo = diffs[int(0.025 * BOOT_B)]
    b_hi = diffs[int(0.975 * BOOT_B)]
    b_pt = gov_acc - ref_acc
    assert round(b_pt, 4) == round(8 / 60, 4), b_pt
    assert b_lo <= b_pt <= b_hi, (b_lo, b_pt, b_hi)
    CB = A["cluster_bootstrap"]
    assert CB[REF]["B"] == 2000, CB[REF]

    # 2d. stratified accuracy from the frozen gold-form slice
    GF = A["slices"]["per_gold_form"]
    forms = ["value", "rewrite", "refusal"]
    for arm in ARMS8:
        tot_err = sum(GF[arm][f]["errors"] for f in forms)
        assert tot_err == EC[arm], (arm, tot_err, EC[arm])
    assert [GF[REF][f]["n"] for f in forms] == [33, 12, 15], GF[REF]

    # 2e. refusal-decision macro-F1 (from the matrix, via refusal_stats)
    RS = A["refusal_stats"]
    TAX = A["taxonomy"]

    def f1(tp, fp, fn):
        d = 2 * tp + fp + fn
        return 0.0 if d == 0 else 2 * tp / d

    macro = {}
    for arm in ARMS8:
        r = RS[arm]
        nref, nans = r["n_refusal_questions"], r["n_answer_questions"]
        assert (nref, nans) == (15, 45), (arm, nref, nans)
        tp = r["correct_refusals"]
        fn = nref - tp                                   # answered_should_refuse
        fp = r["over_refusals_on_answer_questions"]      # refused_should_answer
        tn = nans - fp
        assert fn == TAX[arm].get("answered_should_refuse", 0), (arm, fn)
        assert fp == TAX[arm].get("refused_should_answer", 0), (arm, fp)
        f_ref, f_ans = f1(tp, fp, fn), f1(tn, fn, fp)
        macro[arm] = (tp, fp, fn, tn, f_ref, f_ans, (f_ref + f_ans) / 2)
    assert round(macro[GOV][6], 3) == 0.683, macro[GOV]
    assert round(macro[REF][6], 3) == 0.583, macro[REF]

    # ---- 3. emit --------------------------------------------------------
    L = []
    w = L.append
    fam_disp = {"F11a_ratio_outer_where_1eq0": "ratio, outer WHERE 1=0",
                "F11b_ratio_outer_where_false_str": "ratio, outer WHERE 'a'='b'",
                "F11c_delta_outer_where_1eq0": "delta, outer WHERE 1=0",
                "F11d_atomic_outer_where_1eq0": "atomic, outer WHERE 1=0",
                "F11e_ratio_outer_where_1eq1_true": "ratio, outer WHERE 1=1 (true)",
                "F11f_ratio_outer_from_values_multirow": "ratio, outer FROM VALUES (multi-row)",
                "F11g_atomic_outer_where_false_str": "atomic, outer WHERE 'a'='b'",
                "F11h_ratio_outer_where_numeric_false": "ratio, outer WHERE numeric-false"}

    w("% ------------------------------------------------------------------")
    w("% GENERATED FILE, DO NOT EDIT.")
    w("% Regenerate: python3 pilot2/poststudy4_20260827/gen_tr_poststudy4.py")
    w("% Sources of record: pilot2/poststudy4_20260827/{PREREG_poststudy4_")
    w("%   20260827.md (sha re-asserted), results/v6aplus_v4_summary.json")
    w("%   (six input-record hashes re-verified), results/exploits_run.json")
    w("%   (pinned exploit SQL, byte-verbatim)}, and pilot2/pilot2_arms_")
    w("%   summary.json (sha re-asserted; the frozen verdict matrix the")
    w("%   statistics section is computed from).  The McNemar 2x2 and the")
    w("%   stratified and macro-F1 tables are exact functions of the frozen")
    w("%   matrix; the paired cluster bootstrap is seeded (seed/B disclosed")
    w("%   in the prose).  No number is hand-typed; the generator fails")
    w("%   rather than emit stale content.")
    w("% ------------------------------------------------------------------")
    w(r"\section{External-Review Response II: Outer-Filter Closure \& "
      r"Executed-Arity Check (2026-08-27)}")
    w(r"\label{app:poststudy4}")
    w("")
    w("A second external review (Codex, 2026-08-27) demonstrated --- and our "
      "independent reproduction against the real verifier and the rebuilt "
      r"\texttt{card\_games} warehouse confirmed (\texttt{VULNERABLE-"
      r"CONFIRMED}) --- that the round-1 hardened check V6a+ of "
      r"Appendix~\ref{app:poststudy3} still ACCEPTed a genuine ratio/atomic "
      "certificate whose outer \\texttt{SELECT} carried a top-level "
      r"\texttt{WHERE} that filters the scalar answer to zero rows "
      r"(\texttt{WHERE 1=0}, \texttt{WHERE 'a'='b'}), because "
      r"\texttt{\_check\_ratio}/\texttt{\_check\_delta} did not reject an "
      r"outer \texttt{where\_clause} and no check executed the answer to "
      "test its shape. This appendix is the post-registration round-2 "
      "response: the residual gap is disclosed (not erased), two fixes were "
      "scoped and their predictions frozen \\emph{before} either was run on "
      "any certificate or forgery, and the battery below is reported in "
      "full, misses-first by construction. All outputs are append-only "
      r"under \texttt{pilot2/poststudy4\_20260827/}; the frozen evidence of "
      r"the preceding appendices is byte-untouched, and the body's "
      r"\S\ref{sec:eval-cert} and Definition~\ref{def:tmpl} carry the same "
      "numbers under the same freeze.")
    w("")
    w(r"\paragraph{The protocol freeze.} From the frozen protocol "
      r"(\texttt{PREREG\_poststudy4\_20260827.md}; its SHA-256 was "
      "re-computed at chapter-generation time and matches the registered "
      "value below, restated inside the committed summary JSON):")
    w("")
    w(r"\begin{center}\small")
    w(r"\begin{tabular}{@{}ll@{}}")
    w(r"\toprule")
    w("frozen protocol & SHA-256 \\\\")
    w(r"\midrule")
    w(r"\texttt{PREREG\_poststudy4\_20260827.md} & "
      r"\texttt{\scriptsize %s} \\" % PREREG_SHA_REGISTERED)
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w(r"\subsection{The disclosed residual gap}")
    w(r"\label{app:ps4:gap}")
    w("")
    w("The round-1 V6a+ decided template membership, measure implementation, "
      "leg-role binding, exact-window predicates and join keys, but it read "
      "only the \\emph{inner} leg nodes: the scalar outer node of a "
      r"ratio/atomic/delta answer was permitted a top-level \texttt{WHERE} "
      "by default, and the verifier never executed the answer SQL, so an "
      "outer row filter that empties the result was invisible. The review's "
      "reproduction (scratchpad \\texttt{p0-repro}, "
      r"\texttt{CARD-Q2} ratio base) exhibited exactly this. Two variants "
      "were pinned as regressions and both are replayed below; a "
      "denotation-preserving control (\\texttt{WHERE 1=1}, still $1{\\times}1$) "
      "isolates which fix is doing the work.")
    w("")
    w(r"\subsection{The two fixes}")
    w(r"\label{app:ps4:fix}")
    w("")
    w(r"\begin{enumerate}\setlength\itemsep{2pt}")
    w(r"\item \textbf{Fix 1 --- outer-filter closure (structural).} "
      r"\texttt{\_plain\_node} now rejects a non-null outer \texttt{WHERE} "
      r"by default (\texttt{allow\_outer\_where=False}) with "
      r"\texttt{V6P\_SHAPE}; the scalar outer nodes of atomic/ratio/delta "
      "route through that default, while the FROM-carrying leg, report and "
      r"attribute predicate walkers pass \texttt{allow\_outer\_where=True} "
      r"and read their own \texttt{where\_clause} as before. Nested set-op "
      "and derived-table wrappers with a non-empty outer FROM remain "
      "rejected as they were pre-round-2.")
    w(r"\item \textbf{Fix 2 --- executed-arity check (semantic, fail-"
      r"closed).} A new check \texttt{V6a+x} is appended \emph{last} in the "
      r"order \texttt{V0}\,\dots\,\texttt{V6c},\,\texttt{V6a+},\,"
      r"\texttt{V6a+x}; it is the first V6a+-family site to EXECUTE the "
      "answer SQL, running each ANSWER/REWRITE answer read-only against the "
      "warehouse (the connection the V6b/V6c probes already use) and "
      "requiring the certified row/column arity, else \\texttt{V6P\\_ARITY}. "
      "REFUSE certificates carry no answer SQL and are SKIPped. Appending "
      "last keeps every pre-existing first-FAIL attribution frozen.")
    w(r"\end{enumerate}")
    w(r"\texttt{ci\_check.py} gains \texttt{A5b} (the \texttt{V6a+x} "
      r"execution-shape check exists in \texttt{v6aplus.py} and is wired "
      r"into \texttt{chk.py}'s check order) and \texttt{A6} (the F11 family "
      r"is present in \texttt{forge\_v6aplus.py}, ${\ge}6$ forgeries over "
      r"${\ge}4$ bases); CI-CHECK PASSes. The four shipped verifier files "
      "are byte-identical across both working trees "
      r"(\texttt{trees\_byte\_identical}); their SHA-256 in the committed "
      "study record:")
    w("")
    w(r"\begin{center}\small")
    w(r"\begin{tabular}{@{}ll@{}}")
    w(r"\toprule")
    w("verifier file & SHA-256 \\\\")
    w(r"\midrule")
    for fname in ("chk.py", "v6aplus.py", "forge_v6aplus.py", "ci_check.py"):
        w(r"%s & \texttt{\scriptsize %s} \\" % (tt(fname), VF[fname]))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w(r"\subsection{The round-2 battery}")
    w(r"\label{app:ps4:battery}")
    w("")
    w("Six suites. The prior battery of %d forgeries "
      "(5 round-1 pinned $+$ 34 F1--F5 $+$ 31 F6--F10) is re-run intact; "
      "round 2 adds the 8-forgery F11 outer-row-filter family and 2 round-2 "
      "exploit pins. The family total under the frozen task accounting "
      r"($70+|\mathrm{F11}|$) is \textbf{%d}; including the 2 round-2 pins "
      "the grand total of forged certificates is %d, plus the %d answer-"
      "bearing append-outer-WHERE sweep mutations."
      % (prior_total, family_total, FC["grand_total_forged_certs"],
         SW["n_answer_bearing"]))
    w("")
    w(r"\begin{center}\small")
    w(r"\begin{tabular}{@{}lrl@{}}")
    w(r"\toprule")
    w("suite & $n$ & result \\\\")
    w(r"\midrule")
    w(r"genuine certificates & %d & %d ACCEPT / %d REJECT "
      r"(V6a+ PASS $=$ %d, SKIP $=$ %d; V6a+x PASS $=$ %d, SKIP $=$ %d) \\"
      % (G["total"], G["accept"], G["reject"],
         G["v6aplus_status"]["PASS"], G["v6aplus_status"]["SKIP"],
         G["v6aplus_x_status"]["PASS"], G["v6aplus_x_status"]["SKIP"]))
    w(r"pinned regressions & %d & %d REJECT (%d on the pinned reason "
      r"code; round-1 %d $+$ round-2 %d) \\"
      % (P["total"], P["reject"], P["with_pinned_reason_code"],
         P["round1_total"], P["round2_total"]))
    w(r"prior forgeries F1--F5 & %d & %d REJECT (%d keep the frozen "
      r"\emph{rejected-by}; %s bases accept) \\"
      % (OLD["total"], OLD["reject"], OLD["frozen_attribution_kept"],
         OLD["bases_accept"]))
    w(r"prior forgeries F6--F10 & %d & %d REJECT \\"
      % (PRIOR["total"], PRIOR["reject"]))
    w(r"\textbf{new} F11 outer-row-filter & %d & %d REJECT "
      r"(over %s accepted genuine bases; V6P\_ARITY backstop on %d) \\"
      % (F11["total"], F11["reject"], F11["bases_accept"],
         F11["arity_backstop_hits"]))
    w(r"append-outer-WHERE sweep & %d & %d/%d answer-bearing REJECT; "
      r"%d REFUSE carry no answer SQL \\"
      % (SW["n_total_bases"], SW["n_answer_bearing_reject"],
         SW["n_answer_bearing"], SW["n_refuse_no_answer_sql"]))
    w(r"\midrule")
    w(r"family total ($70+|\mathrm{F11}|$) & %d & %d/%d REJECT \\"
      % (family_total, family_total, family_total))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("V6a+ and V6a+x each SKIP exactly the %d REFUSE certificates (a "
      "refusal carries no answer SQL to validate or execute); every ANSWER "
      "and REWRITE certificate PASSes both, the %d executed answers all "
      "carry their certified arity, and the genuine per-question verdicts "
      "are identical to the pre-round-2 verifier's. By certified kind and "
      "decision: %s."
      % (n_refuse, G["executed_arity_pass"],
         "; ".join(r"%s~%d" % (tt(k), v) for k, v in
                   sorted(G["by_kind_decision"].items()))))
    w("")
    w(r"\paragraph{The seven pinned regressions.} Each must reject "
      r"\emph{on its pinned reason code}, not merely reject "
      "(round-1 five plus round-2 two):")
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}lll@{}}")
    w(r"\toprule")
    w("pinned mutation & expected & observed \\\\")
    w(r"\midrule")
    for r_ in P["rows"]:
        w(r"%s & %s & %s \\" % (tt(r_["name"]), tt(r_["expected"]),
                                "REJECT, code " + tt(r_["reason_code"])))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("The two confirmed round-2 exploits --- the ones the round-1 verifier "
      "ACCEPTed --- both REJECT, each on \\texttt{V6P\\_SHAPE} (Fix 1) with "
      "the independent \\texttt{V6P\\_ARITY} backstop (Fix 2) also firing; "
      "the \\texttt{WHERE 1=1} control is denotation-preserving (executes to "
      r"$1{\times}1$, so V6a+x PASSes) and is caught by the structural "
      "closure \\emph{alone} --- empirical proof that Fix 1 is necessary and "
      "not subsumed by Fix 2. The two pinned exploit SQLs, byte-verbatim "
      "from the recorded run:")
    w("")
    for nm, label in (("V1_outer_where_1eq0", "V1"),
                      ("V1c_outer_where_false", "V1c")):
        w(r"\noindent\texttt{\scriptsize [%s]}" % esc(label))
        w(r"\begin{quote}\ttfamily\scriptsize\raggedright")
        w(esc(exsql[nm]))
        w(r"\end{quote}")
    w("")
    w(r"\paragraph{The F11 outer-row-filter family.} 8 forgeries over 8 "
      "distinct genuine bases (%s); all REJECT with "
      r"\texttt{rejected\_by} $=$ V6a+, and the \texttt{V6P\_ARITY} "
      "execution backstop additionally fires on the %d zero-row/multi-row "
      "cases (the \\texttt{1=1} true control is caught by "
      r"\texttt{V6P\_SHAPE} alone):"
      % (", ".join(esc(x) for x in F11["distinct_bases"]),
         F11["arity_backstop_hits"]))
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}llll@{}}")
    w(r"\toprule")
    w(r"forgery (base) & shape & V6a+ & V6a+x \\")
    w(r"\midrule")
    for r_ in F11["rows"]:
        xc = r_["v6aplus_x_code"] or "---"
        w(r"%s (%s) & %s & %s & %s \\"
          % (tt(r_["name"]), esc(r_["base"]),
             esc(fam_disp.get(r_["name"], "")),
             tt(r_["v6aplus_code"]), tt(xc) if xc != "---" else "---"))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("The append-outer-WHERE corpus sweep appends a top-level "
      r"\texttt{WHERE 1=0} to every genuine certificate's answer SQL: "
      "\\textbf{%d/%d answer-bearing bases REJECT}. The remaining %d bases "
      "are REFUSE certificates that carry no answer SQL --- the outer-row-"
      "filter attack forges an ANSWER by filtering it, so its surface does "
      "not exist for a refusal (recorded as \\texttt{no\\_answer\\_sql}, "
      "never as a reject or an escape)."
      % (SW["n_answer_bearing_reject"], SW["n_answer_bearing"],
         SW["n_refuse_no_answer_sql"]))
    w("")
    w(r"\paragraph{Reason-code distribution.} Across all %d rejecting "
      "battery evaluations, the structural (V6a+) and execution-backstop "
      "(V6a+x) reason codes distribute as: %s."
      % (sum(RC.values()),
         ", ".join(r"%s~%d" % (tt(k), v) for k, v in sorted(RC.items()))))
    w("")
    w(r"\subsection{Prediction scoreboard}")
    w(r"\label{app:ps4:scoreboard}")
    w("")
    w("All four frozen predictions are adjudicated below (%d met, %d "
      "missed%s); a miss, had one occurred, would head this list and be "
      "published as a miss per the frozen protocol's publication rule."
      % (len(PRED) - n_miss, n_miss,
         "" if n_miss == 0 else "; misses listed first"))
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}lp{5.6cm}p{5.4cm}l@{}}")
    w(r"\toprule")
    w("id & frozen statement & observed & verdict \\\\")
    w(r"\midrule")
    for p in order:
        d = PRED[p]
        w(r"%s & %s & %s & %s \\"
          % (p, esc(d["statement"]), esc(d["observed"]),
             r"\textbf{HOLDS}" if d["holds"] else r"\textbf{MISS}"))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("The body's Definition~\\ref{def:tmpl}, the V6a+ clause of the check "
      "list in \\S\\ref{sec:cert:verifier}, the declared scope of "
      "Theorem~\\ref{thm:certsound}(b), and the \\S\\ref{sec:eval-cert} "
      "hardening paragraph all state that V6a+ now decides outer-filter "
      "membership \\emph{and} checks executed arity; the round-1 residual "
      "gap is disclosed there and here, not erased.")
    w("")
    # ===================================================================
    w(r"\clearpage")
    w(r"\section{Governance-Arm Statistics from the Frozen Verdict Matrix "
      r"(2026-08-27)}")
    w(r"\label{app:poststudy4stats}")
    w("")
    w("This appendix reports the reference-vs-governance comparison the "
      "round-2 review asked to see stated as a hypothesis test rather than "
      "as raw error counts. Every number is computed deterministically from "
      "the frozen per-question verdict matrix "
      r"(\texttt{pilot2\_arms\_summary.json}, SHA-256 re-asserted at "
      "generation time); the McNemar $2{\\times}2$ and the stratified and "
      "macro-F1 tables are exact functions of that matrix, and the paired "
      "cluster bootstrap uses a fixed seed. The reference arm is the "
      "governance-informed arm's own backbone "
      r"(\texttt{%s}); the governance arm is \texttt{%s}."
      % (esc(REF), esc(GOV)))
    w("")
    w(r"\subsection{McNemar test: reference vs.\ governance}")
    w(r"\label{app:ps4:mcnemar}")
    w("")
    w("Over all 60 questions, scoring each answer correct/not-correct, the "
      "paired outcomes form the contingency table")
    w("")
    w(r"\begin{center}\small")
    w(r"\begin{tabular}{@{}lcc@{}}")
    w(r"\toprule")
    w(r" & gov correct & gov wrong \\")
    w(r"\midrule")
    w(r"ref correct & %d & %d \\" % (n11, b))
    w(r"ref wrong & %d & %d \\" % (c, n00))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("The discordant pairs are $b{=}%d$ (reference right, governance "
      "wrong) and $c{=}%d$ (governance right, reference wrong): governance "
      "fixes %d reference errors while breaking %d, a net $-%d$ errors that "
      "matches the marginal counts (reference %d errors, governance %d). The "
      "continuity-corrected McNemar statistic is "
      r"$\chi^2=(|b-c|-1)^2/(b+c)=%.3f$ on 1 d.o.f.\ ($p=%.3f$); the exact "
      "two-sided binomial test on the %d discordant pairs gives $p=%.3f$. "
      "Governance improves paired accuracy from %.1f\\%% to %.1f\\%%, and "
      "the improvement is not significant at the $0.05$ level on this "
      "60-question, domain-clustered sample --- reported as observed."
      % (b, c, c, b, c - b, EC[REF], EC[GOV],
         chi2_cc, chi2_p, disc, p_exact,
         100 * ref_acc, 100 * gov_acc))
    w("")
    w(r"\subsection{Per-question paired differences (the discordant pairs)}")
    w(r"\label{app:ps4:paired}")
    w("")
    w("The %d concordant pairs (%d both-correct, %d both-wrong) carry no "
      "paired information; the %d discordant questions are listed in full "
      "below, %d where governance fixes a reference error and %d where it "
      "breaks a reference success."
      % (n11 + n00, n11, n00, disc, len(fixes), len(breaks)))
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}lllll@{}}")
    w(r"\toprule")
    w(r"direction & question & domain & ref verdict & gov verdict \\")
    w(r"\midrule")
    for q in fixes:
        w(r"gov fixes & %s & %s & %s & %s \\"
          % (esc(q), esc(dom(q)), tt(V[q][REF]), tt(V[q][GOV])))
    w(r"\midrule")
    for q in breaks:
        w(r"gov breaks & %s & %s & %s & %s \\"
          % (esc(q), esc(dom(q)), tt(V[q][REF]), tt(V[q][GOV])))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w(r"\subsection{Cluster-bootstrap 95\% confidence intervals}")
    w(r"\label{app:ps4:bootstrap}")
    w("")
    w("Questions are not independent within a public database, so intervals "
      "are formed by resampling the nine domain clusters with replacement. "
      "The frozen per-arm error-rate intervals "
      r"(\texttt{cluster\_bootstrap}, $B{=}%d$) are:"
      % CB[REF]["B"])
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{5pt}")
    w(r"\begin{tabular}{@{}lcc@{}}")
    w(r"\toprule")
    w(r"arm & error rate & 95\% CI \\")
    w(r"\midrule")
    for arm in ARMS8:
        e = CB[arm]
        w(r"%s & %.3f & [%.3f, %.3f] \\"
          % (tt(arm), e["err"], e["ci95"][0], e["ci95"][1]))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("For the paired governance-minus-reference accuracy difference we draw "
      "%d cluster-resamples at fixed seed %d (reproducible): the point "
      "difference is $+%.3f$ (governance %.3f accuracy against reference "
      "%.3f) with a 95\\%% interval $[%.3f, %.3f]$. The interval straddles "
      "zero, consistent with the McNemar test: the direction is a "
      "governance improvement, its magnitude is not resolved at $0.05$ on "
      "nine clusters, and we do not over-claim it."
      % (BOOT_B, BOOT_SEED, b_pt, gov_acc, ref_acc, b_lo, b_hi))
    w("")
    w(r"\subsection{Stratified accuracy by gold form}")
    w(r"\label{app:ps4:stratified}")
    w("")
    w("Accuracy on each arm split by the question's gold form --- "
      "value-answer (%d), rewrite (%d) and refusal (%d) --- from the frozen "
      "gold-form slice (errors summing to each arm's total):"
      % (GF[REF]["value"]["n"], GF[REF]["rewrite"]["n"],
         GF[REF]["refusal"]["n"]))
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{5pt}")
    w(r"\begin{tabular}{@{}lccc@{}}")
    w(r"\toprule")
    w(r"arm & value ($n{=}%d$) & rewrite ($n{=}%d$) & refusal ($n{=}%d$) \\"
      % (GF[REF]["value"]["n"], GF[REF]["rewrite"]["n"],
         GF[REF]["refusal"]["n"]))
    w(r"\midrule")
    for arm in ARMS8:
        cells = []
        for f in forms:
            n = GF[arm][f]["n"]
            e = GF[arm][f]["errors"]
            cells.append(r"%.2f" % ((n - e) / n))
        w(r"%s & %s & %s & %s \\" % (tt(arm), cells[0], cells[1], cells[2]))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w(r"\subsection{Refusal-decision macro-F1}")
    w(r"\label{app:ps4:macrof1}")
    w("")
    w("Treating each arm's decision to refuse-vs-answer as a binary "
      "classifier against the gold refusal set (15 refusal questions, 45 "
      "answer questions), the macro-averaged $F_1$ over the refuse and "
      "answer classes is:")
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{5pt}")
    w(r"\begin{tabular}{@{}lccccc@{}}")
    w(r"\toprule")
    w(r"arm & TP & FP & FN & $F_1$(refuse) / $F_1$(answer) & macro-$F_1$ \\")
    w(r"\midrule")
    for arm in ARMS8:
        tp, fp, fn, tn, f_ref, f_ans, mac = macro[arm]
        w(r"%s & %d & %d & %d & %.3f / %.3f & %.3f \\"
          % (tt(arm), tp, fp, fn, f_ref, f_ans, mac))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("The governance arm's refusal macro-$F_1$ (%.3f) improves on its own "
      "backbone reference (%.3f): it refuses less over-eagerly "
      "(FP $%d{\\to}%d$) while keeping more of the correct refusals "
      "(TP $%d{\\to}%d$). The improvement is on the refusal \\emph{decision} "
      "and is reported alongside, not in place of, the answer-value accuracy "
      "above."
      % (macro[GOV][6], macro[REF][6],
         macro[REF][1], macro[GOV][1], macro[REF][0], macro[GOV][0]))
    w("")

    out = "\n".join(L) + "\n"
    for bad in ("TODO", "placeholder", "PLACEHOLDER", "XXX", "�"):
        assert bad not in out, f"emitted chapter contains {bad!r}"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", OUT,
          "| prereg sha OK | 6 inputs re-hashed OK | arms sha OK |"
          " battery %d/%d reject, genuine %d/%d accept |"
          " McNemar chi2=%.3f exact_p=%.4f (b=%d,c=%d) |"
          " paired-boot +%.3f [%.3f,%.3f] seed=%d B=%d |"
          " gov macro-F1=%.3f ref=%.3f | predictions %d/%d met"
          % (family_total, family_total, G["accept"], G["total"],
             chi2_cc, p_exact, b, c, b_pt, b_lo, b_hi, BOOT_SEED, BOOT_B,
             macro[GOV][6], macro[REF][6], len(PRED) - n_miss, len(PRED)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
