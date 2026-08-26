#!/usr/bin/env python3
# ---------------------------------------------------------------------
# gen_tr_poststudy3.py -- emit paper/tr/generated/poststudy3_20260826.tex:
# two TR appendix sections.
#
#   (1) "External-Review Response: Verifier Hardening (2026-08-26)"
#       [app:poststudy3] -- the post-registration V6a+ hardening study:
#       the disclosed pre-hardening gap, the five structural faces, the
#       full battery (60 genuine / 5 pinned regressions / 34 old + 31
#       new forgeries = 70/70), and the P1-P4 prediction scoreboard.
#   (2) "Relocated Body Evidence (2026-08-26)" [app:relocated20260826]
#       -- the two evidence blocks the 2026-08-26 template-restoration
#       compression (M2) moved out of the submission body VERBATIM: the
#       full D1-D15 divergence ledger float and the S7.3 "Prediction
#       accounting, in full" paragraph (with the case-(iii) sentence
#       whose sensitivity clause the body compressed), plus the two
#       item-by-item prediction tables the body's ledger pointer
#       promises.
#
# Sources of record (ALL numbers in the emitted .tex flow through here;
# nothing is hand-typed):
#   pilot2/poststudy3_20260826/PREREG_poststudy3_20260826.md  (frozen;
#       sha re-computed and asserted == the registered constant below)
#   pilot2/poststudy3_20260826/results/v6aplus_summary.json   (battery;
#       its three input-record hashes are re-computed from the sibling
#       files and asserted -- the chain the study record commits to)
#   pilot2/PREREG_pilot2_arms.md      (frozen 2026-08-04; the S5.1 and
#       S5.2 prediction rows are PARSED from it, never typed)
#   pilot2/pilot2_arms_summary.json   (observed error counts, refusal
#       stats, per-question verdict matrix; error_counts re-derived
#       from the matrix and asserted)
#   paper/tables/tab_divergence.audit.json  (machine-readable D1-D15
#       ledger; every row of the verbatim float is re-built from it and
#       asserted to match, so the relocated table cannot drift)
#
# VERBATIM DISCIPLINE.  The relocated float and paragraphs are embedded
# below as string constants copied byte-for-byte from the pre-surgery
# body sources (artifact clone git lineage of commit d523512; HEAD
# db09e19 identical for both files), with exactly two mechanical
# adaptations, each asserted and disclosed in the emitted prose:
#   - the float label tab:divergence  ->  tab:divergence-full (the TR
#     also typesets the body's slimmed float under the original label);
#   - the caption's self-citation ~\cite{asofgov-tr} -> the in-report
#     pointer \S\ref{app:eval:divergence}.
# Every numeric literal inside the verbatim constants is re-derived
# from the frozen sources above and asserted BEFORE the file is
# written; the generator fails rather than emit stale content.
# Prediction misses are rendered as data; the four poststudy3
# predictions all held and the scoreboard says so from the JSON, but a
# miss, were one recorded, would be listed first and typeset as a miss.
#
# Regenerate:  python3 pilot2/poststudy3_20260826/gen_tr_poststudy3.py
# (invoked by paper/tr/build.sh step 1)
# ---------------------------------------------------------------------
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))      # .../pilot2/poststudy3_20260826
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))  # .../explore_opportunity_cc
OUT = os.path.join(ROOT, "paper", "tr", "generated", "poststudy3_20260826.tex")

PREREG_MD = os.path.join(HERE, "PREREG_poststudy3_20260826.md")
PREREG_SHA_REGISTERED = \
    "426017ddfd8af8608e452b44175e2158c620c2e8cebe3a17572ee3fe15d7a192"
SUMMARY_JSON = os.path.join(HERE, "results", "v6aplus_summary.json")
ARMS_PREREG_MD = os.path.join(ROOT, "pilot2", "PREREG_pilot2_arms.md")
ARMS_JSON = os.path.join(ROOT, "pilot2", "pilot2_arms_summary.json")
AUDIT_JSON = os.path.join(ROOT, "paper", "tables", "tab_divergence.audit.json")
EVAL_TEX = os.path.join(ROOT, "paper", "sections", "08-eval.tex")

GOV = "governance_informed"
BACKBONE = "baseline_claude"
ARMS8 = ["baseline_claude", "baseline_qwen", "baseline_deepseek",
         "baseline_minimax", "trivial_claude", "trivial_v2", "trivial_v3",
         "governance_informed"]


def die(msg):
    raise AssertionError(msg)


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


def md_inline(s):
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


# =====================================================================
# VERBATIM CONSTANTS (pre-surgery body sources, commit-d523512 lineage)
# =====================================================================

# paper/tables/tab_divergence.tex as of the pre-surgery clone HEAD
# (db09e19, identical to d523512), header comment dropped, label renamed
# tab:divergence -> tab:divergence-full and the caption self-citation
# ~\cite{asofgov-tr} -> \S\ref{app:eval:divergence} (both adaptations
# asserted below; everything else byte-identical).
LEDGER_FULL = r"""\begin{table}[t]
\centering
\scriptsize
\setlength{\tabcolsep}{2.0pt}
\renewcommand{\arraystretch}{0.93}
\caption{Every disagreement the two implementations had on their first
cross-check. \emph{Provenance}: this ledger was recorded during the two
sides' integration on the production (enterprise) track that motivated this
work, before the public suite of \S\ref{sec:eval-setup} existed; it is
specification-level content --- readings, checks, guard order --- and
carries no production data value, so it is reported as evidence about the
\emph{design}, not about the released benchmark.
\emph{Cls}: S~spec-reading, D~defect (subscript: which side),
R~registration gap; \emph{Right}: the side the frozen text vindicated;
\emph{Check}: the check that fired ($\dagger$~crashed). The 25 first-round
rejections were V0$\times9$, V6a$\times9$, V3$\times3$, V6b$\times2$,
V6c$\times1$, V4/V6c$\times1$, many-to-many onto these 15.
\emph{Value gold?}: would the integration suite's value-level gold --- 51
questions, 37 numeric and 14 refusal-token comparisons --- have failed? On
no row, and the cell says why not:
the value is unchanged; the lie is confined to the \emph{cert}ificate or
registry that gold never reads; the erring side is the \emph{verif}ier that gold
never runs; or the gold \emph{label} is itself what settled the reading. Both
readings per row: \S\ref{app:eval:divergence}.}
\label{tab:divergence-full}
\begin{tabular}{@{}lccll@{}}
\toprule
Divergence & Cls & Right & Check & Value\\
 & & & fired & gold?\\
\midrule
$D_{1}$ coverage domain gates before $\MC$? & S & spec & V6b & \ding{55}\,label\\
$D_{2}$ $\beta_v$ defined when both legs are NULL? & S & spec & V6b & \ding{55}\,verif.\\
$D_{3}$ prescribed anchor of an atomic metric & R & verif. & V0 & \ding{55}\,cert\\
$D_{4}$ must a ratio carry a caliber route? & R & verif. & V4, V6c & \ding{55}\,cert\\
$D_{5}$ is \texttt{avg\_handle\_hours} a ratio? & R & spec & V3 & \ding{55}\,label\\
$D_{6}$ must a rewrite emit $w^*$'s lower bound? & D$_{\mathrm{c}}$ & verif. & V6a & \ding{55}\,value\\
$D_{7}$ may an atom borrow another's binding row? & D$_{\mathrm{c}}$ & verif. & V3 & \ding{55}\,cert\\
$D_{8}$ probe bound: arithmetic or literal window & D$_{\mathrm{c}}$ & verif. & V6b & \ding{55}\,cert\\
$D_{9}$ does a month marker denote the month? & S & comp. & V6c & \ding{55}\,verif.\\
$D_{10}$ is a derived-table alias a read object? & D$_{\mathrm{v}}$ & comp. & V6a & \ding{55}\,verif.\\
$D_{11}$ does a conformed-dim join leave closure? & R & verif. & V6a & \ding{55}\,cert\\
$D_{12}$ replay of the interval-anchor predicate & D$_{\mathrm{v}}$ & comp. & V6a$^{\dagger}$ & \ding{55}\,verif.\\
$D_{13}$ where the re-anchoring $\bar a$ is carried & S & spec & V0 & \ding{55}\,cert\\
$D_{14}$ how a delta question presents $\vec\omega$ & R & spec & V0 & \ding{55}\,cert\\
$D_{15}$ certificate spelling of an unreg. anchor & S & either & V0 (V2) & \ding{55}\,cert\\
\midrule
\multicolumn{4}{@{}l}{5 S $\cdot$ 3+2 D $\cdot$ 5 R\ \ (25 rejections $\to$ 15 causes)} & \ding{55}\,$0/15$\\
\bottomrule
\end{tabular}
\end{table}"""

# The S7.3 "Prediction accounting, in full." paragraph, verbatim from the
# pre-surgery paper/sections/08-eval.tex (clone HEAD db09e19 = d523512).
ACCOUNTING_PAR = r"""\smallskip\noindent\looseness=-1\textbf{Prediction accounting, in full.} The frozen
predictions were optimistic: all 8 observed error counts
exceed their point predictions and 7 of 8 exceed the 80\% interval's upper
end (this arm most sharply: predicted 14 [8--22], observed 28). Direction and
arm ordering are unaffected; the probe prediction ($\geq$3 of 7) lands at
the interval's top with 6, correct refusals miss \emph{below} their interval
($9/15$ [6--12] predicted, 5 observed) and over-refusals sit at its floor
(${\sim}4/45$ [1--9], 1), and the elimination miss (predicted 0.55, observed
0.361) moved the arm from predicted case (i) to declared (iii)."""

# The pre-surgery case-(iii) sentence (same source), whose parenthetical
# sensitivity clause the body compressed on 2026-08-26; preserved here in
# full per the body's red-line note.
CASE3_SENT = r"""The pre-registered three-case rule puts the arm in
case \emph{(iii)}: $\mathrm{elim}_{\mathrm{gov}}=13/36=0.361<0.40$, \emph{no
substantial elimination} (two short of the line; the variant-2 instruction it
is anchored on is not the best-scoring of the three, $35$ errors against $32$,
and that two-question margin sits inside the ${\pm}4$ spread just quoted; the
pre-registration
specified no interval for $\mathrm{elim}$, its frozen 80\% prediction interval
$[0.35,0.75]$ straddling it; its denominator is a single measurement too, $36$
against a frozen point of $25$, and does not itself enter the rule --- at
$13/35=0.371$ without the reference arm's empty completion the case is
unchanged) --- the claim frozen before the run:
\textbf{under this protocol} (single turn, 512-token cap, database-level governance content plus
instruction), in-context governance does not substantially eliminate the
as-of gap; we do not extrapolate."""


def main():
    # ---- 0. freeze + chain verification --------------------------------
    sha = sha256(PREREG_MD)
    assert sha == PREREG_SHA_REGISTERED, \
        f"PREREG sha mismatch: {sha} != registered {PREREG_SHA_REGISTERED}"
    prereg_raw = open(PREREG_MD, encoding="utf-8").read()
    J = json.load(open(SUMMARY_JSON, encoding="utf-8"))
    assert J["prereg"]["sha256"] == PREREG_SHA_REGISTERED, J["prereg"]
    for fname, want in J["inputs"].items():
        got = sha256(os.path.join(HERE, "results", fname))
        assert got == want, f"input-record hash drift for {fname}: {got}"

    # ---- 1. battery cross-derivation (V6a+ study) ----------------------
    G = J["genuine60"]
    assert (G["total"], G["accept"], G["reject"]) == (60, 60, 0), G
    assert G["v6aplus_status"]["PASS"] + G["v6aplus_status"]["SKIP"] == 60, G
    assert sum(G["by_kind_decision"].values()) == 60, G["by_kind_decision"]
    n_refuse = sum(v for k, v in G["by_kind_decision"].items()
                   if k.endswith("/REFUSE"))
    assert n_refuse == G["v6aplus_status"]["SKIP"] == 15, \
        (n_refuse, G["v6aplus_status"])

    P = J["pinned_regressions"]
    assert P["total"] == P["reject"] == P["with_pinned_reason_code"] \
        == len(P["rows"]) == 5, P
    for r in P["rows"]:
        assert f"REJECT({r['reason_code']})" == r["expected"], r
        assert r["actual"] == "REJECT by V6a+", r

    OLD = J["old_forgeries_f1_f5"]
    assert OLD["total"] == OLD["reject"] == OLD["frozen_attribution_kept"] \
        == sum(OLD["by_family"].values()) == 34, OLD
    assert OLD["bases_accept"] == "11/11", OLD

    NEW = J["new_forgeries_f6_f10"]
    fams = NEW["families"]
    assert sum(f["total"] for f in fams.values()) == NEW["total"] \
        == NEW["reject"] == NEW["asserted_ok"] == 31, NEW
    for name, f in fams.items():
        assert f["total"] == f["rejected"] == f["asserted_ok"] \
            == len(f["bases"]) == len(set(f["bases"])), (name, f)
        assert sum(f["rejected_by"].values()) == f["total"], (name, f)
    new_bases = sorted({b for f in fams.values() for b in f["bases"]})
    assert NEW["bases_accept"] == f"{len(new_bases)}/{len(new_bases)}" \
        == "22/22", (NEW["bases_accept"], len(new_bases))

    total_forge = OLD["total"] + NEW["total"] + P["total"]
    assert total_forge == 70, total_forge

    RC = J["v6aplus_reason_code_distribution"]

    PRED = J["predictions"]
    assert list(PRED) == ["P1", "P2", "P3", "P4"], list(PRED)
    assert J["all_predictions_hold"] == all(
        PRED[p]["holds"] and PRED[p]["misses"] == [] for p in PRED), PRED
    # scoreboard order: misses first (none here, but the rule is coded)
    order = sorted(PRED, key=lambda p: (PRED[p]["holds"], p))

    VF = J["verifier"]["files"]
    assert set(VF) == {"chk.py", "v6aplus.py", "forge_v6aplus.py",
                       "ci_check.py"}, VF

    # the prereg's own four mutation faces, quoted from the frozen text
    m = re.search(r"certificate: (\(a\).*?)The five reproduction",
                  prereg_raw, re.S)
    assert m, "prereg trigger faces not found"
    faces_raw = " ".join(m.group(1).split())

    # ---- 2. relocated-content derivation and verbatim gating -----------
    # 2a. ledger: every row of the verbatim float re-built from the audit
    AUD = json.load(open(AUDIT_JSON, encoding="utf-8"))
    rows = AUD["rows"]
    assert len(rows) == 15 and [r["id"] for r in rows] == \
        [f"D{i}" for i in range(1, 16)], [r["id"] for r in rows]
    cls_map = {"S": "S", "Dc": r"D$_{\mathrm{c}}$",
               "Dv": r"D$_{\mathrm{v}}$", "R": "R"}
    right_map = {"spec": "spec", "verifier": "verif.",
                 "compiler": "comp.", "either": "either"}
    gold_map = {"a": "value", "b": "cert", "c": "verif.", "d": "label"}
    ledger_lines = LEDGER_FULL.splitlines()
    for i, r in enumerate(rows, 1):
        want = (r"$D_{%d}$ %s & %s & %s & %s & \ding{55}\,%s\\"
                % (i, r["printed_short"], cls_map[r["class"]],
                   right_map[r["right"]], r["check"], gold_map[r["gold_code"]]))
        assert want in ledger_lines, f"verbatim ledger drifted on D{i}: {want}"
    from collections import Counter
    cc = Counter(r["class"] for r in rows)
    assert (cc["S"], cc["Dc"], cc["Dv"], cc["R"]) == (5, 3, 2, 5), cc
    assert r"5 S $\cdot$ 3+2 D $\cdot$ 5 R\ \ (25 rejections $\to$ 15 causes)" \
        in LEDGER_FULL
    assert 9 + 9 + 3 + 2 + 1 + 1 == 25  # the caption's rejection decomposition
    # the two disclosed adaptations, and nothing else non-verbatim
    assert r"\label{tab:divergence-full}" in LEDGER_FULL
    assert r"\cite{asofgov-tr}" not in LEDGER_FULL
    assert r"\S\ref{app:eval:divergence}" in LEDGER_FULL

    # 2b. prediction accounting: re-derive every literal from the frozen
    #     PREREG_pilot2_arms.md + the observed arms summary
    arms_raw = open(ARMS_PREREG_MD, encoding="utf-8").read()
    A = json.load(open(ARMS_JSON, encoding="utf-8"))
    V = A["per_question_verdicts"]
    EC = A["error_counts"]

    def errors(arm, qids=None):
        return sum(1 for q in (qids or V) if V[q][arm] != "correct")

    pred = {}
    for arm in ARMS8:
        m = re.search(
            r"^\|\s*`%s`\s*\|\s*\*{0,2}(\d+)[^|]*\|\s*(\d+)\s*[–-]\s*(\d+)\s*\|"
            % re.escape(arm), arms_raw, re.M)
        assert m, f"PREREG S5.1 row not found for {arm}"
        pred[arm] = tuple(int(x) for x in m.groups())
        assert EC[arm] == errors(arm), (arm, EC[arm], errors(arm))
    above_point = sum(1 for a in ARMS8 if EC[a] > pred[a][0])
    above_hi = sum(1 for a in ARMS8 if EC[a] > pred[a][2])
    inside = sorted(a for a in ARMS8 if pred[a][1] <= EC[a] <= pred[a][2])
    assert (above_point, above_hi, inside) == (8, 7, ["trivial_claude"]), \
        (above_point, above_hi, inside)
    assert pred[GOV] == (14, 8, 22) and EC[GOV] == 28, (pred[GOV], EC[GOV])
    assert pred[BACKBONE][0] == 25 and EC[BACKBONE] == 36, \
        (pred[BACKBONE], EC[BACKBONE])

    # S5.2 rows, parsed exactly as tools/check_numbers.py parses them
    RS = A["refusal_stats"][GOV]
    m = re.search(r"`correct_refusals`\s*点\s*\*\*(\d+)/(\d+)\*\*"
                  r"（区间\s*(\d+)[–-](\d+)）", arms_raw)
    assert m, "S5.2 correct_refusals row not found"
    cr = tuple(int(x) for x in m.groups())
    cr_obs = RS["correct_refusals"]
    assert cr == (9, 15, 6, 12) and cr_obs == 5 and cr_obs < cr[2], (cr, cr_obs)
    assert RS["n_refusal_questions"] == 15
    m = re.search(r"`over_refusals`\s*由素基线的\s*~(\d+)/(\d+)\s*升至\s*"
                  r"~(\d+)/(\d+)，\s*区间\s*(\d+)[–-](\d+)）", arms_raw)
    assert m, "S5.2 over_refusals row not found"
    orow = tuple(int(x) for x in m.groups())
    or_obs = RS["over_refusals_on_answer_questions"]
    assert orow[2:] == (4, 45, 1, 9) and or_obs == 1 == orow[4], (orow, or_obs)
    assert RS["n_answer_questions"] == 45
    m = re.search(r"`elim_gov`\s*点\s*\*\*([\d.]+)\*\*"
                  r"（区间\s*([\d.]+)[–-]([\d.]+)）", arms_raw)
    assert m and m.groups() == ("0.55", "0.35", "0.75"), m
    m = re.search(r"答错\s*≥(\d+)/(\d+)\*\*（区间\s*(\d+)[–-](\d+)）", arms_raw)
    assert m and tuple(int(x) for x in m.groups()) == (3, 7, 3, 6), m
    m = re.search(r"OOV×4\s*\{([^}]+)\}.*?×2\s*\{([^}]+)\}.*?×1\s*\{([^}]+)\}",
                  arms_raw, re.S)
    assert m, "S5.2 probe set not found"
    probe7 = [q.strip() for grp in m.groups() for q in grp.split(",")]
    assert len(probe7) == 7 == len(set(probe7)), probe7
    probe_err = errors(GOV, probe7)
    assert probe_err == 6, (probe7, probe_err)

    # elimination: 13/36 = 0.361; sensitivity 13/35 = 0.371 without the
    # reference arm's empty completion
    ref_err_q = [q for q in V if V[q][BACKBONE] != "correct"]
    elim_q = [q for q in ref_err_q if V[q][GOV] == "correct"]
    assert (len(ref_err_q), len(elim_q)) == (36, 13), \
        (len(ref_err_q), len(elim_q))
    assert round(13 / 36, 3) == 0.361 and 0.361 < 0.40
    empties = A["empty_responses"][BACKBONE]
    assert len(empties) == 1 and set(empties) <= set(ref_err_q), empties
    elim_sens = [q for q in ref_err_q if q not in empties
                 and V[q][GOV] == "correct"]
    assert len(elim_sens) == 13 and round(13 / 35, 3) == 0.371, elim_sens

    # every literal in the two verbatim paragraphs is covered by a
    # derivation above; pin the strings so silent edits break the build
    for lit in ("all 8 observed error counts", "7 of 8",
                "predicted 14 [8--22], observed 28", r"($\geq$3 of 7)",
                "with 6", "$9/15$ [6--12] predicted, 5 observed",
                r"(${\sim}4/45$ [1--9], 1)", "predicted 0.55, observed",
                "0.361"):
        assert lit in ACCOUNTING_PAR, f"accounting paragraph lost: {lit}"
    for lit in (r"$\mathrm{elim}_{\mathrm{gov}}=13/36=0.361<0.40$",
                "$[0.35,0.75]$", "$36$", "of $25$", "$13/35=0.371$",
                "$35$ errors against $32$"):
        assert lit in CASE3_SENT, f"case-(iii) sentence lost: {lit}"

    # the body must still point here the way the surgery promised
    eval_body = open(EVAL_TEX, encoding="utf-8").read()
    assert "the miss ledger is accounted item by item" in " ".join(
        eval_body.split()), "body lost the TR miss-ledger pointer"
    assert r"frozen first~\cite{asofgov-tr}" in eval_body, \
        "body lost the V6a+ frozen-first pointer"
    assert "full D1--D15 ledger, both readings per row" in " ".join(
        open(os.path.join(ROOT, "paper", "tables", "tab_divergence.tex"),
             encoding="utf-8").read().split()), \
        "body ledger caption lost the full-ledger promise"

    # ---- 3. emit --------------------------------------------------------
    L = []
    w = L.append
    w("% ------------------------------------------------------------------")
    w("% GENERATED FILE, DO NOT EDIT.")
    w("% Regenerate: python3 pilot2/poststudy3_20260826/gen_tr_poststudy3.py")
    w("% Sources of record: pilot2/poststudy3_20260826/{PREREG_poststudy3_")
    w("%   20260826.md, results/v6aplus_summary.json (input-record hashes")
    w("%   re-verified)}, pilot2/PREREG_pilot2_arms.md (S5.1/S5.2 rows")
    w("%   parsed, never typed), pilot2/pilot2_arms_summary.json, and")
    w("%   paper/tables/tab_divergence.audit.json.  The relocated float and")
    w("%   paragraphs are byte-verbatim from the pre-surgery body sources")
    w("%   (artifact-clone lineage of commit d523512), with exactly two")
    w("%   disclosed mechanical adaptations (float label; self-citation),")
    w("%   and every row/literal in them is re-derived and asserted before")
    w("%   this file is written.  The generator fails rather than emit")
    w("%   stale content.")
    w("% ------------------------------------------------------------------")
    w(r"\section{External-Review Response: Verifier Hardening (2026-08-26)}")
    w(r"\label{app:poststudy3}")
    w("")
    w("An external review (Codex, 2026-08-26) demonstrated --- and our "
      "independent reproduction against the real verifier and a rebuilt "
      r"\texttt{card\_games} warehouse confirmed --- that check V6a, as it "
      "stood through every battery above, accepts semantically wrong SQL "
      "mutations of a genuine certificate. This appendix is the "
      "post-registration response: the gap is disclosed (not erased), the "
      "hardened check V6a+ was scoped and its predictions frozen "
      "\\emph{before} it was run on any certificate or forgery, and the "
      "battery below is reported in full, misses-first by construction. "
      "All outputs are append-only under "
      r"\texttt{pilot2/poststudy3\_20260826/}; the frozen evidence of the "
      "preceding sections is byte-untouched, and the body's \\S\\ref{sec:eval-cert} "
      "carries the same numbers under the same freeze.")
    w("")
    w(r"\paragraph{The protocol freeze.} From the frozen protocol "
      r"(\texttt{PREREG\_poststudy3\_20260826.md}; its SHA-256 was "
      "re-computed at chapter-generation time and matches the registered "
      "value below, restated inside the committed summary JSON):")
    w("")
    w(r"\begin{center}\small")
    w(r"\begin{tabular}{@{}ll@{}}")
    w(r"\toprule")
    w("frozen protocol & SHA-256 \\\\")
    w(r"\midrule")
    w(r"\texttt{PREREG\_poststudy3\_20260826.md} & "
      r"\texttt{\scriptsize %s} \\" % PREREG_SHA_REGISTERED)
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w(r"\subsection{The disclosed gap}")
    w(r"\label{app:ps3:gap}")
    w("")
    w("In the frozen protocol's own words, the review exhibited, on a "
      "genuine certificate, mutations")
    w(r"\begin{quote}\small " + md_inline(faces_raw) + r"\end{quote}")
    w(r"\noindent The five reproduction artifacts were preserved and are "
      "the pinned regression cases of \\S\\ref{app:ps3:battery}. Nothing "
      "in the pre-registered F1--F5 battery had landed on these faces: "
      "V6a checked object closure, window \\emph{containment} and the "
      "leg-before-divide shape, but not whether the emitted aggregate "
      "\\emph{implements the registered measure}, whether each leg is "
      "computed from \\emph{its own} registered objects, or whether the "
      "time predicate equals the certified window exactly rather than "
      "denoting a subset of it.")
    w("")
    w(r"\subsection{V6a+: the hardened check}")
    w(r"\label{app:ps3:check}")
    w("")
    w("V6a+ is a fail-closed structural check appended \\emph{last} to the "
      "verifier's conjunction (order V0\\,\\dots\\,V6c,\\,V6a+), so every "
      "pre-existing forgery keeps its frozen \\emph{rejected-by} "
      "attribution. It parses each answer SQL with DuckDB's own parser "
      r"(\texttt{json\_serialize\_sql}; no new dependency, and "
      "import-disjointness from the compiler is preserved) and validates "
      "the tree against \\emph{independently loaded} governance seeds on "
      "the five faces the frozen protocol registered:")
    w(r"\begin{enumerate}\setlength\itemsep{1pt}")
    w(r"\item \textbf{Template membership, fail-closed}: anything "
      "unparseable, non-scalar (not exactly one row, one column), "
      "constant-only, or outside the declared shape (single aggregate per "
      "leg; ratio $=$ leg$/$leg) is REJECT;")
    w(r"\item \textbf{measure implementation}: each leg's aggregate "
      "function and argument must implement that leg's registered "
      r"\texttt{gov\_measure\_def} measure --- the registered form, not a "
      "lookalike;")
    w(r"\item \textbf{leg-role binding}: the numerator position must be "
      "computed from the numerator leg's registered table/column and the "
      "denominator position from the denominator leg's; swapped legs "
      "REJECT;")
    w(r"\item \textbf{registered predicates}: every predicate registered "
      "for the binding (the time window on the anchor column, plus "
      "non-temporal registered predicates) must appear with the certified "
      "constants at \\emph{exact} window equality; a predicate that "
      "narrows or widens a certified window REJECTs;")
    w(r"\item \textbf{join keys}: multi-table legs must join exactly on "
      "the registered routing keys.")
    w(r"\end{enumerate}")
    w("The four shipped verifier files, hashed in the committed study "
      "record:")
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
    w(r"\subsection{The battery}")
    w(r"\label{app:ps3:battery}")
    w("")
    w("Four suites, %d certificates and forgeries in all (%d genuine "
      "certificates and the %d-forgery corpus: %d pre-registered F1--F5, "
      "%d pinned reproduction mutations, %d new F6--F10):"
      % (G["total"] + total_forge, G["total"], total_forge,
         OLD["total"], P["total"], NEW["total"]))
    w("")
    w(r"\begin{center}\small")
    w(r"\begin{tabular}{@{}lrl@{}}")
    w(r"\toprule")
    w("suite & $n$ & result \\\\")
    w(r"\midrule")
    w(r"genuine certificates & %d & %d ACCEPT / %d REJECT "
      r"(V6a+ status: PASS $=$ %d, SKIP $=$ %d) \\"
      % (G["total"], G["accept"], G["reject"],
         G["v6aplus_status"]["PASS"], G["v6aplus_status"]["SKIP"]))
    w(r"pinned reproduction mutations & %d & %d REJECT "
      r"(%d/%d on the pinned reason code) \\"
      % (P["total"], P["reject"], P["with_pinned_reason_code"], P["total"]))
    w(r"old forgeries F1--F5 & %d & %d REJECT (%d/%d keep the frozen "
      r"\emph{rejected-by}; %s bases accept) \\"
      % (OLD["total"], OLD["reject"], OLD["frozen_attribution_kept"],
         OLD["total"], OLD["bases_accept"]))
    w(r"new forgeries F6--F10 & %d & %d REJECT (over %s accepted genuine "
      r"bases) \\" % (NEW["total"], NEW["reject"], NEW["bases_accept"]))
    w(r"\midrule")
    w(r"forgery total & %d & %d/%d REJECT \\"
      % (total_forge, total_forge, total_forge))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    w("V6a+ SKIPs exactly the %d REFUSE certificates (a refusal carries "
      "no answer SQL to validate); every ANSWER and REWRITE certificate "
      "PASSes it, and the genuine per-question verdicts are identical to "
      "the pre-hardening verifier's. By certified kind and decision: %s."
      % (n_refuse,
         "; ".join(r"%s~%d" % (tt(k), v) for k, v in
                   sorted(G["by_kind_decision"].items()))))
    w("")
    w(r"\paragraph{The five pinned regressions (P2).} The preserved "
      "reproduction mutations, replayed as mandatory regression cases; "
      "each must reject \\emph{on its pinned reason code}, not merely "
      "reject:")
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
    w(r"\paragraph{The five new families (P3).} Each built over multiple "
      "genuine bases (all %s bases accept before mutation):"
      % NEW["bases_accept"].split("/")[0])
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}lp{4.1cm}rrp{5.0cm}l@{}}")
    w(r"\toprule")
    w("family & mutation & $n$ & rej. & bases & rejected by \\\\")
    w(r"\midrule")
    fam_desc = {"F6": "wrong aggregate", "F7": "leg swap",
                "F8": "wrong/absent registered predicate",
                "F9": "narrowed-or-widened window predicate",
                "F10": "constant/multi-row output"}
    for name in ("F6", "F7", "F8", "F9", "F10"):
        f = fams[name]
        rb = ", ".join("%s$\\,\\times\\,$%d" % (k, v)
                       for k, v in sorted(f["rejected_by"].items()))
        w(r"%s & %s & %d & %d & %s & %s \\"
          % (name, fam_desc[name], f["total"], f["rejected"],
             esc(", ".join(f["bases"])), rb))
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{center}")
    w("")
    f9 = fams["F9"]
    w("F9's widened and shifted windows are caught first by the frozen "
      "V6a containment gate --- its jurisdiction all along (%d of %d) --- "
      "while every \\emph{narrowing} mutation, invisible to containment, "
      "is caught by V6a+ alone (%d of %d). Across all rejecting V6a+ "
      "evaluations in the batteries, the reason codes distribute as %s."
      % (f9["rejected_by"].get("V6a", 0), f9["total"],
         f9["rejected_by"].get("V6a+", 0), f9["total"],
         ", ".join(r"%s~%d" % (tt(k), v) for k, v in sorted(RC.items()))))
    w("")
    w(r"\subsection{Prediction scoreboard}")
    w(r"\label{app:ps3:scoreboard}")
    w("")
    n_miss = sum(1 for p in PRED if not PRED[p]["holds"])
    w("All four frozen predictions are adjudicated below (%d met, %d "
      "missed%s); a miss, had one occurred, would head this list and be "
      "published as a miss per the frozen protocol's publication rule."
      % (len(PRED) - n_miss, n_miss,
         "" if n_miss == 0 else "; misses listed first"))
    w("")
    w(r"\begin{center}\small")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}lp{6.4cm}p{5.2cm}l@{}}")
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
    w("The body's Definition~\\ref{def:tmpl}, the V6a+ clause of the "
      "check list in \\S\\ref{sec:cert:verifier}, the declared scope of "
      "Theorem~\\ref{thm:certsound}(b) under (A-tmpl), and the "
      "\\S\\ref{sec:eval-cert} hardening paragraph all state exactly what "
      "V6a+ decides; the pre-hardening gap is disclosed there and here, "
      "not erased.")
    w("")
    # ------------------------------------------------------------------
    w(r"\clearpage")
    w(r"\section{Relocated Body Evidence (2026-08-26): the Full "
      r"Divergence Ledger and the Prediction Accounting}")
    w(r"\label{app:relocated20260826}")
    w("")
    w("The 2026-08-26 template-restoration pass (M2) recovered the "
      "submission's reclaimed space with \\emph{content}, not spacing "
      "overrides: two evidence blocks moved out of the body into this "
      "report, verbatim. Their sources of record are unchanged "
      r"(\texttt{impl/INTEGRATION\_REPORT.md} \S5 with "
      r"\texttt{tab\_divergence.audit.json}; the frozen "
      r"\texttt{PREREG\_pilot2\_arms.md} with the committed arms summary), "
      "and the paper's number gate still parses and scores every "
      "prediction from the frozen pre-registration. The text below is "
      "byte-verbatim from the pre-relocation body sources, with two "
      "mechanical adaptations, both disclosed: the float label is renamed "
      r"(\texttt{tab:divergence-full}), since this report also typesets "
      "the body's slimmed summary float under the original label, and the "
      "caption's citation of this report now points at the in-report "
      "dissection (\\S\\ref{app:eval:divergence}).")
    w("")
    w(r"\subsection{The full D1--D15 divergence ledger}")
    w(r"\label{app:ps3:ledger}")
    w("")
    w("The body's Table~\\ref{tab:divergence} prints the per-class counts "
      "and three exemplar rows; Table~\\ref{tab:divergence-full} is the "
      "full fifteen-row float as the body carried it before 2026-08-26, "
      "every row re-verified against the machine-readable audit record "
      "at generation time. Both readings of every row: "
      "\\S\\ref{app:eval:divergence}.")
    w("")
    w(LEDGER_FULL)
    w("")
    w(r"\subsection{S7.3 prediction accounting, in full}")
    w(r"\label{app:ps3:accounting}")
    w("")
    w("The case-(iii) verdict sentence as the body carried it before "
      "2026-08-26 --- the sensitivity clause the body now compresses to "
      "``the denominator's own overshoot'' is the parenthetical:")
    w("")
    w(r"\begin{quote}")
    w(CASE3_SENT)
    w(r"\end{quote}")
    w("")
    w("\\noindent and the accounting paragraph, in full:")
    w("")
    w(r"\begin{quote}")
    w(ACCOUNTING_PAR)
    w(r"\end{quote}")
    w("")
    w("\\noindent Item by item, from the frozen \\S5.1 per-arm table "
      "(parsed from the pre-registration at generation time, never "
      "typed) against the committed verdict matrix:")
    w("")
    w(r"\begin{table}[h]")
    w(r"\centering\small")
    w(r"\caption{The S5.1 miss ledger: frozen per-arm error predictions "
      r"(point and 80\%% interval, errors of 60) against the observed "
      r"counts. All %d observed counts exceed their points; %d of %d "
      r"exceed the interval's upper end (\texttt{trivial\_claude} alone "
      r"lands inside its interval).}"
      % (above_point, above_hi, len(ARMS8)))
    w(r"\label{tab:ps3-s51}")
    w(r"\begin{tabular}{@{}lrcrl@{}}")
    w(r"\toprule")
    w(r"arm & point & 80\% interval & observed & position \\")
    w(r"\midrule")
    for arm in ARMS8:
        pt, lo, hi = pred[arm]
        obs = EC[arm]
        pos = ("above the interval" if obs > hi else
               "inside the interval" if lo <= obs <= hi else
               "below the interval")
        w(r"%s & %d & %d--%d & %d & %s \\" % (tt(arm), pt, lo, hi, obs, pos))
    w(r"\midrule")
    w(r"\texttt{mechanism} & 0 & (anchor, not a prediction) & %d & "
      r"as anchored \\" % EC["mechanism"])
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{table}")
    w("")
    w(r"\begin{table}[h]")
    w(r"\centering\small")
    w(r"\caption{The S5.2 miss ledger: the four frozen governance-arm "
      r"decomposition predictions against the observed run. The "
      r"elimination miss's frozen 80\%% interval $[0.35,0.75]$ straddles "
      r"the pre-registered $0.40$ line; the denominator's own overshoot "
      r"($%d$ observed reference errors against a frozen point of $%d$) "
      r"does not enter the case rule, and at $13/35=0.371$ without the "
      r"reference arm's single empty completion the case is unchanged.}"
      % (EC[BACKBONE], pred[BACKBONE][0]))
    w(r"\label{tab:ps3-s52}")
    w(r"\setlength{\tabcolsep}{4pt}")
    w(r"\begin{tabular}{@{}lccll@{}}")
    w(r"\toprule")
    w(r"prediction & point & 80\% interval & observed & position \\")
    w(r"\midrule")
    w(r"\texttt{elim\_gov} & 0.55 & $[0.35,0.75]$ & $13/36=0.361$ & "
      r"inside, below the point \\")
    w(r"probe-set errors & $\geq$3/7 & 3--6 & %d/7 & at the interval's "
      r"top \\" % probe_err)
    w(r"\texttt{correct\_refusals} & 9/15 & 6--12 & %d/15 & "
      r"\emph{below} the interval \\" % cr_obs)
    w(r"\texttt{over\_refusals} & ${\sim}$4/45 & 1--9 & %d/45 & at the "
      r"interval's floor \\" % or_obs)
    w(r"\bottomrule")
    w(r"\end{tabular}")
    w(r"\end{table}")
    w("")
    w("The two refusal-side rows miss in the direction \\emph{against} "
      "the informed arm: it refuses less than predicted, not more. "
      "Direction and arm ordering are unaffected throughout; what the "
      "optimism cost is magnitude, and the body's case-(iii) paragraph "
      "carries the five-repetition span and the paired nine-cluster CI "
      "that bound it (Appendix~\\ref{app:poststudy} S3, "
      "Appendix~\\ref{app:poststudy2} S4).")
    w("")

    out = "\n".join(L) + "\n"
    for bad in ("TODO", "placeholder", "PLACEHOLDER", "XXX", "�",
                "textbackslash"):
        assert bad not in out, f"emitted chapter contains {bad!r}"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", OUT,
          "| prereg sha OK | inputs re-hashed OK | battery %d/%d reject,"
          " genuine %d/%d accept | ledger 15/15 rows audit-matched |"
          " S5.1 8 arms + S5.2 4 predictions parsed and scored |"
          " predictions %d/%d met"
          % (total_forge, total_forge, G["accept"], G["total"],
             len(PRED) - n_miss, len(PRED)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
