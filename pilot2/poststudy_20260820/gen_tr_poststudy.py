#!/usr/bin/env python3
# ---------------------------------------------------------------------
# gen_tr_poststudy.py -- emit paper/tr/generated/poststudy_20260820.tex,
# the TR chapter "Post-Registration Robustness Studies (2026-08-20)".
#
# Sources of record (ALL numbers in the emitted .tex flow through here;
# nothing is hand-typed):
#   pilot2/poststudy_20260820/PREREG_poststudy_20260820.md   (frozen; sha
#       re-computed and asserted == the registered constant below)
#   pilot2/poststudy_20260820/s1/loco_report.json            (S1)
#   pilot2/poststudy_20260820/s2/tsql_summary.json           (S2 headline)
#   pilot2/poststudy_20260820/s2/tsql_ledger.json            (S2 per-question)
#   pilot2/poststudy_20260820/s3/s3_summary.json             (S3)
#
# Discipline: the script re-derives every tally it prints, cross-checks
# the ledger against the summary, and FAILS rather than emit stale or
# inconsistent content.  Prediction verdicts are rendered as data --
# misses are typeset as misses, never asserted away.  Constants that the
# prose leans on (the 0.40 line, seeds, k) are parsed out of the frozen
# statements/JSONs, not typed here.
#
# Regenerate:  python3 pilot2/poststudy_20260820/gen_tr_poststudy.py
# (invoked by paper/tr/build.sh step 1)
# ---------------------------------------------------------------------
import hashlib
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))          # .../pilot2/poststudy_20260820
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))     # .../explore_opportunity_cc
OUT = os.path.join(ROOT, "paper", "tr", "generated", "poststudy_20260820.tex")

PREREG_MD = os.path.join(HERE, "PREREG_poststudy_20260820.md")
PREREG_SHA_REGISTERED = \
    "f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24"

S1_JSON = os.path.join(HERE, "s1", "loco_report.json")
S2_SUM_JSON = os.path.join(HERE, "s2", "tsql_summary.json")
S2_LED_JSON = os.path.join(HERE, "s2", "tsql_ledger.json")
S3_JSON = os.path.join(HERE, "s3", "s3_summary.json")

ARM_SHORT = {
    "baseline_claude": "Bl-C", "baseline_qwen": "Bl-Q",
    "baseline_deepseek": "Bl-D", "baseline_minimax": "Bl-M",
    "trivial_claude": "Tr-C", "trivial_v2": "Tr-2", "trivial_v3": "Tr-3",
    "governance_informed": "Gov", "mechanism": "Mech",
}
DOM_ORDER = [
    "california_schools", "card_games", "codebase_community",
    "debit_card_specializing", "european_football_2", "financial",
    "formula_1", "thrombosis_prediction", "world_1",
]
REASON_SHORT = {"out-of-validity": r"$\bot_{\mathsf{OOV}}$",
                "anchor-mismatch": r"$\bot_{\mathsf{AM}}$",
                "missing-caliber": r"$\bot_{\mathsf{MC}}$",
                "disclosure-blocked": r"$\bot_{\mathsf{DB}}$"}
VERDICT_SHORT = {"correct": r"\checkmark", "wrong_value": "wv",
                 "answered_should_refuse": "ar", "execution_error": "xe",
                 "refused_should_answer": "rs", "no_sql": "ns"}


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def esc(s):
    """LaTeX-escape plain text (keeps a handful of preamble-mapped
    unicode; normalises typographic punctuation)."""
    if s is None:
        return ""
    out = []
    for ch in str(s):
        out.append({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
                    "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
                    "}": r"\}", "~": r"\textasciitilde{}",
                    "^": r"\textasciicircum{}",
                    "§": r"\S{}",
                    "±": r"\ensuremath{\pm}",
                    "—": "---", "–": "--",
                    "‘": "`", "’": "'",
                    "“": "``", "”": "''",
                    }.get(ch, ch))
    return "".join(out)


def tt(s):
    return r"\texttt{%s}" % esc(s)


def md_inline(s):
    """Convert the tiny markdown subset used by the prereg (bold, code
    spans) into LaTeX, escaping everything else."""
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", s)
    out = []
    for p in parts:
        if p.startswith("**") and p.endswith("**"):
            out.append(r"\textbf{%s}" % esc(p[2:-2]))
        elif p.startswith("`") and p.endswith("`"):
            out.append(tt(p[1:-1]))
        else:
            out.append(esc(p))
    return "".join(out)


def pct(x, dp=1):
    return r"%.*f\%%" % (dp, 100.0 * x)


def num(x, sig=6):
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float) and x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return "%.*g" % (sig, x)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verdict_word(ok):
    return "MET" if ok else "MISSED"


# ---------------------------------------------------------------------
# 0. prereg freeze verification + quote extraction
# ---------------------------------------------------------------------
def prereg_checks():
    sha = sha256_file(PREREG_MD)
    assert sha == PREREG_SHA_REGISTERED, \
        f"PREREG sha drift: {sha} != registered {PREREG_SHA_REGISTERED}"
    lines = open(PREREG_MD, encoding="utf-8").read().splitlines()
    # opening block: title + the frozen/motivation paragraph (everything
    # before the first '## ' heading).
    head = []
    for ln in lines:
        if ln.startswith("## "):
            break
        head.append(ln)
    title = head[0].lstrip("# ").strip()
    para = " ".join(ln.strip() for ln in head[1:] if ln.strip())
    # the four S2 prediction bullets, verbatim from the frozen file
    s2_bullets = []
    cur = None
    in_s2 = False
    for ln in lines:
        if ln.startswith("## "):
            in_s2 = ln.startswith("## S2")
            continue
        if not in_s2:
            continue
        if re.match(r"- \*\*S2-P\d\*\*", ln):
            if cur is not None:
                s2_bullets.append(cur)
            cur = ln[2:].strip()
        elif cur is not None:
            if ln.strip() and (ln.startswith("  ") or ln.startswith("\t")):
                cur += " " + ln.strip()
            else:
                s2_bullets.append(cur)
                cur = None
    if cur is not None:
        s2_bullets.append(cur)
    assert len(s2_bullets) == 4, s2_bullets
    return sha, title, para, s2_bullets


# ---------------------------------------------------------------------
# S1
# ---------------------------------------------------------------------
def s1_section(A, s1):
    assert s1["prereg_sha256"] == PREREG_SHA_REGISTERED
    arms = s1["arms"]
    assert list(ARM_SHORT) == arms, arms
    folds = s1["loco_folds"]
    assert sorted(folds) == sorted(DOM_ORDER)
    n_folds = len(folds)
    n_q = s1["n_questions"]
    full = s1["full_sample_error_rate"]
    for dom, fd in folds.items():
        assert fd["n_questions_left_out"] + fd["n_questions_kept"] == n_q
        for a in arms:
            assert close(fd["error_count"][a] / fd["n_questions_kept"],
                         fd["error_rate"][a]), (dom, a)
    full_counts = {}
    for a in arms:
        c = full[a] * n_q
        assert close(c, round(c), 1e-6), (a, c)
        full_counts[a] = int(round(c))
    src = s1["matrix_source"]
    assert src["sha256"]["frozen_sha256"] == src["sha256"]["sandbox_sha256"]
    assert src["sandbox_byte_identical_to_frozen"] is True

    A(r"\subsection{S1: Subset Robustness of the Frozen Score Matrix}")
    A(r"\label{app:ps:s1}")
    A("")
    A(r"Deterministic, zero LLM calls. The per-question $\times$ per-arm"
      r" correctness matrix is reconstructed from the frozen caches with"
      r" the frozen scorer semantics in an isolated sandbox; the committed"
      r" matrix source (%s) was byte-identical to the frozen original"
      r" (SHA-256 %s), and the sandbox reproduction run reported: %s."
      % (tt(src["file"]),
         r"\texttt{\scriptsize %s}" % esc(src["sha256"]["frozen_sha256"]),
         esc(src["reproduction"])))
    A(r"Table~\ref{tab:ps-loco} gives the %d LOCO folds,"
      r" Table~\ref{tab:ps-jack} the question-level jackknife on the two"
      r" headline arms, and Table~\ref{tab:ps-boot} the bootstrap"
      r" restatement." % n_folds)
    A("")
    # ---- LOCO table -------------------------------------------------
    A(r"\begin{table}[h]")
    A(r"\centering\scriptsize")
    A(r"\setlength{\tabcolsep}{3.2pt}")
    A(r"\caption{S1 leave-one-database-out (LOCO): error rate of every arm"
      r" on the questions that remain when each of the %d public databases"
      r" is left out in turn (error count in parentheses). Top row: the"
      r" frozen full-suite rates for reference. Arms: %s.}"
      % (n_folds,
         "; ".join(r"%s = %s" % (ARM_SHORT[a], tt(a)) for a in arms)))
    A(r"\label{tab:ps-loco}")
    A(r"\begin{tabular}{@{}lr%s@{}}" % ("r" * len(arms)))
    A(r"\toprule")
    A(r"left-out DB & kept & %s \\" % " & ".join(ARM_SHORT[a] for a in arms))
    A(r"\midrule")
    A(r"\emph{none (full suite)} & %d & %s \\"
      % (n_q, " & ".join(r"%s\,(%d)" % (pct(full[a]), full_counts[a])
                         for a in arms)))
    A(r"\midrule")
    for dom in DOM_ORDER:
        fd = folds[dom]
        A(r"%s & %d & %s \\" % (
            tt(dom), fd["n_questions_kept"],
            " & ".join(r"%s\,(%d)" % (pct(fd["error_rate"][a]),
                                      fd["error_count"][a]) for a in arms)))
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{table}")
    A("")
    # ---- jackknife table --------------------------------------------
    jk = s1["question_jackknife"]
    A(r"\begin{table}[h]")
    A(r"\centering\small")
    A(r"\caption{S1 question-level jackknife on the two headline arms"
      r" ($n=%d$): point error rate, jackknife standard error, the"
      r" normal-approximation 95\%% interval, and the range of the %d"
      r" leave-one-question-out rates.}" % (n_q, n_q))
    A(r"\label{tab:ps-jack}")
    A(r"\begin{tabular}{@{}lrrrcc@{}}")
    A(r"\toprule")
    A(r"arm & errors & error rate & jackknife SE & 95\% CI & LOO range \\")
    A(r"\midrule")
    for a, d in jk.items():
        assert d["n"] == n_q and close(d["error_count"] / n_q,
                                       d["point_error_rate"])
        lo, hi = d["ci95_normal_approx"]
        A(r"%s & %d/%d & %s & %.4f & [%s, %s] & [%s, %s] \\" % (
            tt(a), d["error_count"], d["n"], pct(d["point_error_rate"]),
            d["jackknife_se"], pct(lo), pct(hi),
            pct(d["leave_one_out_min"]), pct(d["leave_one_out_max"])))
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{table}")
    A("")
    # ---- bootstrap restatement --------------------------------------
    bs = s1["bootstrap_restatement"]
    b0 = next(iter(bs.values()))
    assert all(d["B"] == b0["B"] and d["seed"] == b0["seed"]
               and d["cluster_unit"] == b0["cluster_unit"]
               for d in bs.values())
    for a in arms:
        assert close(bs[a]["err"], full[a])
    frozen_key = [k for k in b0 if k.startswith("ci95_frozen_seed")]
    assert len(frozen_key) == 1
    frozen_key = frozen_key[0]
    frozen_seed = int(re.search(r"(\d+)$", frozen_key).group(1))
    A(r"\begin{table}[h]")
    A(r"\centering\small")
    A(r"\caption{S1 database-level bootstrap restatement"
      r" ($B=%d$, fresh seed %d, cluster unit: %s): the frozen cluster"
      r" bootstrap re-run under a new seed, next to the frozen-seed (%d)"
      r" intervals. A consistency check, not new evidence.}"
      % (b0["B"], b0["seed"], esc(b0["cluster_unit"]), frozen_seed))
    A(r"\label{tab:ps-boot}")
    A(r"\begin{tabular}{@{}lrcc@{}}")
    A(r"\toprule")
    A(r"arm & error rate & 95\%% CI (seed %d) & 95\%% CI (seed %d) \\"
      % (b0["seed"], frozen_seed))
    A(r"\midrule")
    for a in arms:
        d = bs[a]
        A(r"%s & %s & [%s, %s] & [%s, %s] \\" % (
            tt(a), pct(d["err"]),
            pct(d["ci95_seed20260820"][0]), pct(d["ci95_seed20260820"][1]),
            pct(d[frozen_key][0]), pct(d[frozen_key][1])))
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{table}")
    A("")
    # ---- predictions ------------------------------------------------
    P = s1["predictions"]
    A(r"\paragraph{Pre-registered predictions (S1).}")
    A(r"\begin{itemize}\itemsep2pt")
    for pid in ("S1-P1", "S1-P2", "S1-P3"):
        p = P[pid]
        viol = []
        for k, v in p.items():
            if k.startswith("violations") and v:
                viol.append("%s: %s" % (k, v))
        vtxt = "" if not viol else " (%s)" % esc("; ".join(map(str, viol)))
        A(r"\item \textbf{%s} (``%s''): \textbf{%s}%s"
          % (pid, esc(p["statement"]), esc(p["verdict"]), vtxt))
    A(r"\end{itemize}")
    A("")


# ---------------------------------------------------------------------
# S2
# ---------------------------------------------------------------------
def s2_cross_checks(s2, led):
    """Re-derive every S2 headline tally from the per-question ledger and
    assert it against the summary; fail rather than emit stale content."""
    assert s2["prereg"]["sha256"] == PREREG_SHA_REGISTERED
    assert len(led) == 60 and len({q["qid"] for q in led}) == 60
    for arm in ("TSQL-W", "TSQL-H"):
        for reading, vkey in (("null_as_error",
                               "verdict_frozen_null_as_error"),
                              ("null_as_refusal_credit",
                               "verdict_null_as_refusal_credit")):
            rd = s2["arms"][arm]["readings"][reading]
            tal = Counter(q["arms"][arm][vkey] for q in led)
            assert tal == Counter(rd["taxonomy"]), (arm, reading, tal)
            errs = sorted(q["qid"] for q in led
                          if q["arms"][arm][vkey] != "correct")
            assert errs == sorted(rd["error_qids"]), (arm, reading)
            assert rd["error_count"] == len(errs)
            assert close(rd["error_rate"], len(errs) / len(led))
            byf = Counter(q["expected_kind"] for q in led
                          if q["arms"][arm][vkey] != "correct")
            for form, d in rd["by_form"].items():
                assert d["errors"] == byf.get(form, 0), (arm, reading, form)
        bn = sorted(q["qid"] for q in led if q["arms"][arm]["bare_null"])
        assert bn == sorted(s2["arms"][arm]["bare_null_qids"]), (arm, bn)
    # TSQL-H: the two readings coincide on every question (no bare NULLs)
    for q in led:
        assert (q["arms"]["TSQL-H"]["verdict_frozen_null_as_error"]
                == q["arms"]["TSQL-H"]["verdict_null_as_refusal_credit"]), \
            q["qid"]


def s2_section(A, s2, led, s2_bullets, line_a):
    s2_cross_checks(s2, led)
    W = s2["arms"]["TSQL-W"]["readings"]
    H = s2["arms"]["TSQL-H"]["readings"]
    # reading order: the reading LESS favourable to the paper's separation
    # claim (the lower TSQL-W error rate) is printed first.
    readings = sorted(["null_as_refusal_credit", "null_as_error"],
                      key=lambda r: W[r]["error_rate"])
    READING_NAME = {
        "null_as_error": "A: frozen-literal (bare NULL = error)",
        "null_as_refusal_credit": "B: NULL-as-implicit-refusal credit",
    }
    fro = s2["frozen_scorer"]
    bn_qids = s2["arms"]["TSQL-W"]["bare_null_qids"]
    forms = W["null_as_error"]["by_form"]

    A(r"\subsection{S2: Governance-Blind Temporal-SQL Arms}")
    A(r"\label{app:ps:s2}")
    A("")
    A(r"Deterministic, zero LLM calls. Two hand-built arms operationalise"
      r" ``temporal-SQL machinery without the governance axis'':")
    A(r"\begin{itemize}\itemsep2pt")
    A(r"\item \textbf{TSQL-W} (same-window, latest-version, guard-free):"
      r" applies the question's requested window to both metric legs on"
      r" their \emph{latest committed version's} anchors and always"
      r" answers a number; it never refuses, never rewrites, never checks"
      r" version-in-effect, coverage, admissibility or disclosure.")
    A(r"\item \textbf{TSQL-H} (all-history at $T$): each leg aggregated"
      r" over all valid rows dated $\le$ \texttt{as\_of} --- the classic"
      r" time-travel dashboard reading.")
    A(r"\end{itemize}")
    A("")
    A(r"Independence and scoring, as executed: %s. Inputs per question"
      r" exclude %s. The frozen scorer chain was reused byte-identically"
      r" (\texttt{run\_pilot.py} SHA-256 %s; relative tolerance %s;"
      r" dispatch %s). Neither arm ever declares a refusal, and %d"
      r" \mbox{TSQL-W} queries return a bare SQL \texttt{NULL} (%s ---"
      r" all on refusal-gold questions), so both scoring readings of a"
      r" bare \texttt{NULL} are published; the frozen null-edge rule"
      r" reads: %s."
      % (esc(s2["import_disjointness"]),
         ", ".join(tt(x) for x in s2["exclusion_list_enforced"]),
         r"\texttt{\scriptsize %s}" % esc(fro["run_pilot_sha256"]),
         num(fro["REL_TOL"]), esc(fro["dispatch"]),
         len(bn_qids), ", ".join(tt(q) for q in bn_qids),
         esc(s2["null_edge_rule"])))
    A(r"Table~\ref{tab:ps-tsql} is the headline;"
      r" Table~\ref{tab:ps-flip} walks the %d version-flip pairs; the"
      r" full per-question ledger is Table~\ref{tab:ps-ledger}."
      % len(s2["version_flip_pairs"]))
    A("")
    # ---- headline table ---------------------------------------------
    A(r"\begin{table}[h]")
    A(r"\centering\small")
    A(r"\setlength{\tabcolsep}{4.2pt}")
    A(r"\caption{S2 headline: both arms under both bare-\texttt{NULL}"
      r" scoring readings, the reading less favourable to the paper's"
      r" separation claim first. Splits: errors on the %d value / %d"
      r" rewrite / %d refusal questions; taxonomy: wv = wrong value,"
      r" ar = answered-should-refuse, xe = execution error.}"
      % (forms["value"]["n"], forms["rewrite"]["n"], forms["refusal"]["n"]))
    A(r"\label{tab:ps-tsql}")
    A(r"\begin{tabular}{@{}llrrrrrrrr@{}}")
    A(r"\toprule")
    A(r"arm & \texttt{NULL} reading & \multicolumn{2}{c}{total error}"
      r" & val & rew & ref & wv & ar & xe \\")
    A(r"\midrule")
    for arm, R in (("TSQL-W", W), ("TSQL-H", H)):
        for r in readings:
            d = R[r]
            bf = d["by_form"]
            tx = d["taxonomy"]
            A(r"%s & %s & %d/%d & %s & %d/%d & %d/%d & %d/%d"
              r" & %d & %d & %d \\" % (
                  tt(arm), esc(READING_NAME[r]),
                  d["error_count"], len(led), pct(d["error_rate"]),
                  bf["value"]["errors"], bf["value"]["n"],
                  bf["rewrite"]["errors"], bf["rewrite"]["n"],
                  bf["refusal"]["errors"], bf["refusal"]["n"],
                  tx["wrong_value"], tx["answered_should_refuse"],
                  tx["execution_error"]))
        A(r"\addlinespace")
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{table}")
    A("")
    # ---- version-flip pair table ------------------------------------
    pairs = s2["version_flip_pairs"]
    off_err = s2["off_version_sides_errors_TSQL_W"]
    off_sides = [sd for p in pairs for sd in p["sides"]
                 if sd["off_version_side"]]
    credited = [sd["qid"] for sd in off_sides if sd["qid"] not in off_err]
    assert sorted(off_err) == sorted(sd["qid"] for sd in off_sides
                                     if sd["tsql_w_verdict"] != "correct")
    A(r"\begin{table}[h]")
    A(r"\centering\small")
    A(r"\setlength{\tabcolsep}{4.2pt}")
    A(r"\caption{S2: the %d version-flip pairs under TSQL-W's"
      r" latest-version binding. Off-version sides are the questions whose"
      r" version-in-effect is not the latest committed version the arm"
      r" binds; TSQL-W errs on %d of the %d off-version sides, and the"
      r" remaining one (%s) is credited only because its two committed"
      r" definitions differ by less than the scoring tolerance.}"
      % (len(pairs), len(off_err), len(off_sides),
         ", ".join(tt(q) for q in credited)))
    A(r"\label{tab:ps-flip}")
    A(r"\begin{tabular}{@{}llccrrrcl@{}}")
    A(r"\toprule")
    A(r"pair & side & $\nu$ in effect & $\nu$ used & gold & TSQL-W"
      r" & rel.\ diff & $\le$ tol & verdict \\")
    A(r"\midrule")
    for p in pairs:
        pr = r"\texttt{%s}" % esc("/".join(p["pair"]))
        for i, sd in enumerate(p["sides"]):
            assert sd["off_version_side"] == \
                (sd["ver_in_effect"] != sd["latest_used"])
            A(r"%s & %s%s & %s & %s & %s & %s & %s & %s & %s \\" % (
                pr if i == 0 else "",
                tt(sd["qid"]),
                r"\,(off-$\nu$)" if sd["off_version_side"] else "",
                tt(sd["ver_in_effect"]), tt(sd["latest_used"]),
                num(sd["gold"], 9), num(sd["tsql_w_value"], 9),
                num(sd["rel_diff"], 3),
                r"\checkmark" if sd["within_tol"] else r"$\times$",
                esc(sd["tsql_w_verdict"])))
        A(r"\addlinespace")
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{table}")
    A("")
    # ---- predictions, incl. the reading-B miss ----------------------
    PA = s2["predictions"]["null_as_error"]
    PB = s2["predictions"]["null_as_refusal_credit"]
    A(r"\paragraph{Pre-registered predictions (S2).} Verbatim from the"
      r" frozen protocol, with the verdict under each reading"
      r" (A = frozen-literal, B = \texttt{NULL}-credit):")
    A(r"\begin{itemize}\itemsep2pt")
    for i, pid in enumerate(("S2-P1", "S2-P2", "S2-P3", "S2-P4")):
        A(r"\item %s --- reading A: \textbf{%s}; reading B: \textbf{%s}."
          % (md_inline(s2_bullets[i]),
             verdict_word(PA[pid]["met"]), verdict_word(PB[pid]["met"])))
    A(r"\end{itemize}")
    A("")
    pb1, pa1 = PB["S2-P1"]["detail"], PA["S2-P1"]["detail"]
    # the prose below is written for exactly this outcome; fail loudly if
    # the data ever changes rather than print a stale narrative.
    assert PA["S2-P1"]["met"] is True and PB["S2-P1"]["met"] is False
    assert W["null_as_refusal_credit"]["error_rate"] < line_a \
        <= W["null_as_error"]["error_rate"]
    bn_ref = s2["arms"]["TSQL-W"]["bare_null_on_refusal_gold_qids"]
    A(r"\textbf{The S2-P1 reading-B miss, stated plainly.} S2-P1 predicted"
      r" zero refusal declarations and, in consequence, zero credit on the"
      r" refusal questions. The declaration half held under both readings"
      r" (\mbox{TSQL-W}: %d declarations; \mbox{TSQL-H}: %d), and under"
      r" the frozen-literal reading A the prediction is met exactly"
      r" (\mbox{TSQL-W} %s, \mbox{TSQL-H} %s correct on refusal gold). But"
      r" under reading B the %d bare-\texttt{NULL} outputs (%s) all land"
      r" on refusal-gold questions and are credited as implicit refusals:"
      r" \mbox{TSQL-W} scores %s on refusal gold, so the prediction"
      r" \emph{as written} fails under this reading --- and \mbox{TSQL-W}'s"
      r" reading-B headline error (%s) also slips below the frozen %s"
      r" line that its reading-A error (%s) respects. We publish the miss"
      r" rather than adopt only the reading that avoids it, and note what"
      r" the credit is: an artifact of scoring generosity --- the arm"
      r" never \emph{declares} a refusal, carries no refusal class, and"
      r" its bare \texttt{NULL}s carry no typed reason."
      % (pb1["refusal_declarations"]["TSQL-W"],
         pb1["refusal_declarations"]["TSQL-H"],
         tt(pa1["refusal_correct_W"]), tt(pa1["refusal_correct_H"]),
         len(bn_ref), ", ".join(tt(q) for q in bn_ref),
         tt(pb1["refusal_correct_W"]),
         pct(W["null_as_refusal_credit"]["error_rate"]),
         pct(line_a, 0),
         pct(W["null_as_error"]["error_rate"])))
    A("")
    if s2.get("notes"):
        A(r"\paragraph{Edge notes (from the run record).}")
        A(r"\begin{itemize}\itemsep2pt")
        for n in s2["notes"]:
            A(r"\item %s" % esc(n))
        A(r"\end{itemize}")
        A("")
    # ---- per-question ledger ----------------------------------------
    A(r"\subsubsection*{S2 per-question ledger}")
    A("")
    A(r"All %d questions. Gold: outcome class ($\bot$-classes as in the"
      r" body); $\nu_{\mathrm{eff}}$: the version in effect at the"
      r" question's bi-temporal coordinates (TSQL-W always binds the"
      r" latest committed version). Out: the raw SQL scalar"
      r" (\texttt{NULL} = bare SQL \texttt{NULL}). Verdicts:"
      r" \checkmark{} = correct, wv = wrong value, ar ="
      r" answered-should-refuse, xe = execution error; A = frozen-literal"
      r" reading, B = \texttt{NULL}-credit reading (the two readings never"
      r" differ for TSQL-H, whose verdict column is single)." % len(led))
    A("")
    A(r"{\scriptsize")
    A(r"\setlength{\tabcolsep}{3.6pt}")
    A(r"\begin{longtable}{@{}llclcclc@{}}")
    A(r"\caption{S2 per-question ledger: gold class, version in effect,"
      r" raw output and verdict per arm under both readings.}"
      r"\label{tab:ps-ledger}\\")
    A(r"\toprule")
    A(r"QID & gold & $\nu_{\mathrm{eff}}$ & TSQL-W out & W:A & W:B"
      r" & TSQL-H out & H \\")
    A(r"\midrule")
    A(r"\endfirsthead")
    A(r"\multicolumn{8}{@{}l}{\emph{(continued)}}\\\toprule")
    A(r"QID & gold & $\nu_{\mathrm{eff}}$ & TSQL-W out & W:A & W:B"
      r" & TSQL-H out & H \\")
    A(r"\midrule")
    A(r"\endhead")
    A(r"\bottomrule")
    A(r"\endlastfoot")
    led_by_dom = {}
    for q in led:
        led_by_dom.setdefault(q["domain"], []).append(q)
    assert sorted(led_by_dom) == sorted(DOM_ORDER)
    for dom in DOM_ORDER:
        A(r"\multicolumn{8}{@{}l}{\rule{0pt}{2.2ex}\textbf{%s}}\\[0.1ex]"
          % esc(dom))
        for q in led_by_dom[dom]:
            gold = (REASON_SHORT[q["refusal_reason"]]
                    if q["expected_kind"] == "refusal"
                    else q["expected_kind"])
            w, h = q["arms"]["TSQL-W"], q["arms"]["TSQL-H"]
            wout = w["raw_output"] if w["exec_ok"] else "(exec error)"
            hout = h["raw_output"] if h["exec_ok"] else "(exec error)"
            A(r"%s & %s & %s & %s & %s & %s & %s & %s \\" % (
                tt(q["qid"]), gold, tt(q["ver_in_effect"]),
                tt(wout),
                VERDICT_SHORT[w["verdict_frozen_null_as_error"]],
                VERDICT_SHORT[w["verdict_null_as_refusal_credit"]],
                tt(hout),
                VERDICT_SHORT[h["verdict_frozen_null_as_error"]]))
    A(r"\end{longtable}")
    A(r"}")
    A("")


# ---------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------
def s3_section(A, s3):
    assert s3["prereg_sha256"] == PREREG_SHA_REGISTERED
    assert s3["prereg_sha256_reasserted_from_disk"] is True
    n_q = s3["n_questions"]
    reps = s3["reps"]
    assert reps == sorted(reps) and reps[0] == 1
    k_new = len(reps) - 1
    arms = s3["arms"]
    assert arms == ["baseline_claude", "governance_informed"]
    per = s3["per_arm"]
    for a in arms:
        for k, d in per[a]["per_rep"].items():
            assert d["n"] == n_q
            assert close(d["errors"] / n_q, d["error_rate"]), (a, k)
            assert n_q - d["verdict_counts"]["correct"] == d["errors"], (a, k)
        pe = per[a]["errors_across_reps"]
        seq = [per[a]["per_rep"][str(k)]["errors"] for k in reps]
        assert seq == pe["per_rep_errors"]
        assert min(seq) == pe["min"] and max(seq) == pe["max"]
        assert close(sum(seq) / len(seq), pe["mean"])
        pf = per[a]["pooled_flip"]
        assert pf["n_flips"] == len(pf["flip_qids"])
        assert close(pf["flip_rate"], pf["n_flips"] / n_q)
    elim = s3["elimination_governance_informed"]
    n_ref = elim["n_reference_errors"]
    for k, d in elim["per_rep"].items():
        assert d["of_reference_errors"] == n_ref
        assert close(d["eliminated_frac"], d["eliminated_n"] / n_ref)
    assert n_ref == per["baseline_claude"]["per_rep"]["1"]["errors"]
    ordv = s3["ordering_check"]["per_rep"]
    for k in map(str, reps):
        assert ordv[k]["margin_questions"] == \
            ordv[k]["baseline_claude_errors"] - \
            ordv[k]["governance_informed_errors"]
    assert s3["ordering_check"]["all_reps_pass"] is True
    cls = s3["call_log_stats"]
    ops = s3["operational"]

    A(r"\subsection{S3: Repetition Study (LLM, $k=%d$ New Runs per Arm)}"
      % k_new)
    A(r"\label{app:ps:s3}")
    A("")
    A(r"Arms %s and %s only (the two arms carrying the headline), model"
      r" %s; rep~1 is the"
      r" frozen main-study run, reused not re-run, and reps~%d--%d are new"
      r" paid runs (%d paid calls in total). Every prompt sent was checked"
      r" byte-identical to the frozen rep-1 prompt (%d/%d cache"
      r" cross-checks passed); the new reps produced %d empty completions"
      r" (the one empty completion on record, %s, is the frozen rep-1"
      r" baseline artifact already disclosed in the main study), and the"
      r" driver's circuit breaker (stop if a finished governance rep has"
      r" more than %d/%d empty caches) never tripped."
      % (tt(arms[0]), tt(arms[1]), tt(s3["model"]),
         reps[1], reps[-1], cls["n_total_paid_calls"],
         ops["prompt_byte_identity_checks"]
            ["rep_caches_vs_frozen_rep1_sha256_and_chars"],
         cls["n_total_paid_calls"],
         ops["empty_responses_new_reps_total"],
         tt(ops["empty_responses_frozen_rep1"]["per_arm_qids"]
            ["baseline_claude"][0]),
         ops["circuit_breaker"]["threshold_empties"], n_q))
    A(r"Table~\ref{tab:ps-reps} gives the per-rep results.")
    A("")
    # ---- per-rep table ----------------------------------------------
    A(r"\begin{table}[h]")
    A(r"\centering\small")
    A(r"\setlength{\tabcolsep}{4.2pt}")
    A(r"\caption{S3 per-rep results. Verdict split: ok = correct, wv ="
      r" wrong value, xe = execution error, ar = answered-should-refuse,"
      r" rs = refused-should-answer, ns = no SQL. Margin = baseline errors"
      r" minus governance errors in that rep; elim.\ = fraction of the"
      r" frozen rep-1 \texttt{baseline\_claude} error set (%d questions)"
      r" eliminated by \texttt{governance\_informed} in that rep.}" % n_ref)
    A(r"\label{tab:ps-reps}")
    A(r"\begin{tabular}{@{}llrrrrrrrrcc@{}}")
    A(r"\toprule")
    A(r"arm & rep & errors & rate & ok & wv & xe & ar & rs & ns"
      r" & margin & elim. \\")
    A(r"\midrule")
    for a in arms:
        for k in map(str, reps):
            d = per[a]["per_rep"][k]
            vc = d["verdict_counts"]
            A(r"%s & %s%s & %d & %s & %d & %d & %d & %d & %d & %d"
              r" & %s & %s \\" % (
                  tt(a) if k == "1" else "", k,
                  r"$^{\dagger}$" if k == "1" else "",
                  d["errors"], pct(d["error_rate"]),
                  vc.get("correct", 0), vc.get("wrong_value", 0),
                  vc.get("execution_error", 0),
                  vc.get("answered_should_refuse", 0),
                  vc.get("refused_should_answer", 0),
                  vc.get("no_sql", 0),
                  str(ordv[k]["margin_questions"]) if a == arms[0] else "",
                  pct(elim["per_rep"][k]["eliminated_frac"])
                  if a == "governance_informed" else ""))
        A(r"\addlinespace")
    A(r"\bottomrule")
    A(r"\multicolumn{12}{@{}l}{\rule{0pt}{2.2ex}\footnotesize"
      r" $^{\dagger}$rep 1 = the frozen main-study run, reused not"
      r" re-run.}\\")
    A(r"\end{tabular}")
    A(r"\end{table}")
    A("")
    # ---- stability / flips ------------------------------------------
    rp = s3["rep1_position"]
    agree = {a: [per[a]["rep1_vs_repk"][str(k)]
                 ["correctness_agreement_rate"] for k in reps[1:]]
             for a in arms}
    elim_lo = min(d["eliminated_frac"] for d in elim["per_rep"].values())
    elim_hi = max(d["eliminated_frac"] for d in elim["per_rep"].values())
    assert rp["governance_informed"]["rep1_is_strict_worst"] is True
    assert elim["frozen_rep1_value_reasserted"] is True
    A(r"Per-question stability: rep-1-vs-rep-$k$ correctness agreement is"
      r" %s--%s for %s and %s--%s for %s. Pooling all %d reps, a question"
      r" \emph{flips} iff its correctness is not constant across reps:"
      r" %s flips %d/%d questions (rate %s: %s); %s flips %d/%d (rate %s:"
      r" %s). Across reps the error count stays within [%d, %d] (mean %s)"
      r" for %s and [%d, %d] (mean %s) for %s. The frozen rep-1 headline"
      r" for %s (%d errors, %s) is the \emph{worst} of its five reps ---"
      r" the frozen headline is the conservative end of the observed range"
      r" --- and the per-rep elimination of the frozen baseline error set"
      r" brackets the frozen value (rep 1: %s) between %s and %s."
      % (pct(min(agree[arms[0]])), pct(max(agree[arms[0]])), tt(arms[0]),
         pct(min(agree[arms[1]])), pct(max(agree[arms[1]])), tt(arms[1]),
         len(reps),
         tt(arms[0]), per[arms[0]]["pooled_flip"]["n_flips"], n_q,
         pct(per[arms[0]]["pooled_flip"]["flip_rate"]),
         ", ".join(tt(q) for q in per[arms[0]]["pooled_flip"]["flip_qids"]),
         tt(arms[1]), per[arms[1]]["pooled_flip"]["n_flips"], n_q,
         pct(per[arms[1]]["pooled_flip"]["flip_rate"]),
         ", ".join(tt(q) for q in per[arms[1]]["pooled_flip"]["flip_qids"]),
         per[arms[0]]["errors_across_reps"]["min"],
         per[arms[0]]["errors_across_reps"]["max"],
         num(per[arms[0]]["errors_across_reps"]["mean"]), tt(arms[0]),
         per[arms[1]]["errors_across_reps"]["min"],
         per[arms[1]]["errors_across_reps"]["max"],
         num(per[arms[1]]["errors_across_reps"]["mean"]), tt(arms[1]),
         tt(arms[1]), rp["governance_informed"]["rep1_errors"],
         pct(per[arms[1]]["per_rep"]["1"]["error_rate"]),
         pct(elim["per_rep"]["1"]["eliminated_frac"]),
         pct(elim_lo), pct(elim_hi)))
    A("")
    # ---- predictions ------------------------------------------------
    P = s3["predictions"]
    n_missed_derived = sum(0 if P[p]["pass"] else 1 for p in P)
    assert n_missed_derived == s3["n_predictions_missed"]
    A(r"\paragraph{Pre-registered predictions (S3).}")
    A(r"\begin{itemize}\itemsep2pt")
    for pid in ("S3-P1", "S3-P2", "S3-P3", "S3-P4"):
        p = P[pid]
        if "band_questions" in p:
            extra = " (band in questions: [%d, %d]; per-rep errors %s)" % (
                p["band_questions"][0], p["band_questions"][1],
                ", ".join("%d" % p["per_rep_errors"][str(k)] for k in reps))
        elif pid == "S3-P3":
            extra = " (per-rep margins %s)" % ", ".join(
                "%d" % p["per_rep"][str(k)]["margin_questions"]
                for k in reps)
        elif pid == "S3-P4":
            extra = " (%s)" % "; ".join(
                r"%s %d/%d = %s" % (tt(a), p["per_arm"][a]["n_flips"], n_q,
                                    pct(p["per_arm"][a]["flip_rate"]))
                for a in arms)
        else:
            extra = ""
        A(r"\item \textbf{%s} (``%s''): \textbf{%s}%s."
          % (pid, esc(p["statement"]), verdict_word(p["pass"]), extra))
    A(r"\end{itemize}")
    A("")
    A(r"Of the %d S3 predictions, %d were missed."
      % (len(P), s3["n_predictions_missed"]))
    A("")


# ---------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------
def main():
    sha, title, para, s2_bullets = prereg_checks()
    s1 = load(S1_JSON)
    s2 = load(S2_SUM_JSON)
    led = load(S2_LED_JSON)
    s3 = load(S3_JSON)

    # the frozen pre-registered line A' (0.40), parsed from the frozen
    # S1-P1 statement rather than typed here
    m = re.search(r">=\s*([0-9.]+)", s1["predictions"]["S1-P1"]["statement"])
    line_a = float(m.group(1))

    n_q = s1["n_questions"]
    assert n_q == s3["n_questions"] == len(led)
    k_new = len(s3["reps"]) - 1

    L = []
    A = L.append
    A("% ------------------------------------------------------------------")
    A("% GENERATED FILE, DO NOT EDIT.")
    A("% Regenerate: python3 pilot2/poststudy_20260820/gen_tr_poststudy.py")
    A("% Sources of record: pilot2/poststudy_20260820/{PREREG_poststudy_")
    A("%   20260820.md, s1/loco_report.json, s2/tsql_summary.json,")
    A("%   s2/tsql_ledger.json, s3/s3_summary.json}.")
    A("% Every number below flows from those files through the generator;")
    A("% the generator re-derives all tallies (ledger vs summary) and the")
    A("% prereg SHA-256, and fails rather than emit stale content.")
    A("% ------------------------------------------------------------------")
    A(r"\section{Post-Registration Robustness Studies (2026-08-20)}")
    A(r"\label{app:poststudy}")
    A("")
    A(r"Three robustness studies were run \emph{after} the main-study"
      r" results were frozen, against a protocol written and hashed before"
      r" any of them started; they are therefore \emph{post-registration}"
      r" relative to the operative pre-registration of"
      r" Appendix~\ref{app:prereg2}, and every number they add is labelled"
      r" as such. They address three anticipated objections: (i)"
      r" sufficiency of the $n=%d$ suite (S1: leave-one-database-out and"
      r" question-level jackknife over the frozen score matrix); (ii) the"
      r" absence of a non-LLM temporal-SQL comparison arm (S2: two"
      r" deterministic governance-blind arms); (iii) single-run LLM"
      r" variance (S3: $k=%d$ new paid repetitions of each of the two"
      r" headline arms). Nothing in the frozen evidence is modified; all"
      r" outputs are append-only under"
      r" \texttt{pilot2/poststudy\_20260820/}." % (n_q, k_new))
    A("")
    A(r"\paragraph{The protocol freeze.} From the frozen protocol"
      r" (\texttt{PREREG\_poststudy\_20260820.md}; its SHA-256 was"
      r" re-computed at chapter-generation time, matches the registered"
      r" value below, and is restated inside each study's committed"
      r" report):")
    A("")
    A(r"\begin{quote}\small")
    A(r"\textbf{%s.} %s" % (esc(title), md_inline(para)))
    A(r"\end{quote}")
    A("")
    A(r"\begin{center}\small")
    A(r"\begin{tabular}{@{}ll@{}}")
    A(r"\toprule")
    A(r"frozen protocol & SHA-256 \\")
    A(r"\midrule")
    A(r"\texttt{PREREG\_poststudy\_20260820.md} &"
      r" \texttt{\scriptsize %s} \\" % esc(sha))
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{center}")
    A("")
    s1_section(A, s1)
    s2_section(A, s2, led, s2_bullets, line_a)
    s3_section(A, s3)

    out = "\n".join(L) + "\n"
    # final gates on the emitted chapter itself
    for bad in ("TODO", "placeholder", "PLACEHOLDER", "XXX", "�"):
        assert bad not in out, f"emitted chapter contains {bad!r}"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", OUT,
          "| prereg sha OK | S1 folds=%d, S2 ledger=%d, S3 reps=%d"
          " cross-checked" % (len(s1["loco_folds"]), len(led),
                              len(s3["reps"])))


if __name__ == "__main__":
    sys.exit(main())
