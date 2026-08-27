#!/usr/bin/env python3
"""Four-place consistency check for every pilot number in the paper.

PUBLIC-BASE EDITION (2026-08-04).  The evidence base moved to the pilot2
public suite by author ruling; this gate moved with it.  The old enterprise
edition of this file gated pilot/pilot_summary.json + impl/cost.json and is
superseded -- old-base numbers may now appear ONLY inside the provenance-
marked motivation (S1) and the D1-D15 ledger caption, and a STALE list below
bans them from every result-bearing prose file.

The places that must agree, in dependency order:

  (1) pilot2/pilot2_summary.json        -- single source of truth for the 9
                                           arms, written by
                                           pilot2/make_pilot2_summary.py from
                                           the frozen response caches
      pilot2/pilot2_arms_summary.json   -- per-question verdict matrix (the
                                           recompute source for elim / paired
                                           counts / family splits)
      pilot2/domains/*/questions.json   -- frozen suite composition
      pilot2/domains/*/provenance.json  -- real/authored row ledger
      impl/cost_p2.json                 -- cost measurements (measure_cost.py)
  (2) sections/08-eval.tex tables tab:main / tab:taxonomy / tab:suite, and
      the taxonomy figure's data file figures/fig_data_pilot2.json
      (fig3_failure_taxonomy; the six-class half moved there in the
      2026-08-04 float surgery)
  (3) prose: main.tex abstract, sections/01-intro.tex, sections/08-eval.tex,
             sections/10-conclusion.tex

Every assertion is derived from (1); nothing is hard-coded except the
mapping from a system id to the label the paper prints, and the frozen
question-set definitions (flip pairs, hull trims) whose membership is fixed
in PREREG_pilot2_arms.md / ACCEPTANCE_REPORT.md.

NOTE the figure-pipeline blocks of the old edition (fig_data.json, the
partition figure, figD ablation) are intentionally absent while the public
figure pipeline (figures/extract_p2.py) lands; re-add them against the new
extractor once its outputs freeze.  EXCEPTION (2026-08-04 float surgery):
the taxonomy-figure block below IS live --- fig3_failure_taxonomy returned
to the body, so its data file is gated here cell-by-cell against (1).

Exit code 0 iff all checks pass.  Usage:  python3 tools/check_numbers.py
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
ROOT = os.path.dirname(PAPER)

S = json.load(open(os.path.join(ROOT, "pilot2", "pilot2_summary.json")))
A = json.load(open(os.path.join(ROOT, "pilot2", "pilot2_arms_summary.json")))
COST = json.load(open(os.path.join(ROOT, "impl", "cost_p2.json")))
# (2026-08-26) poststudy3 verifier-hardening summary (V6a+); sha-gated in the
# poststudy3 block below, loaded here so the E5 forgery-count assertions can
# derive every grown total from it instead of typing one.
V6P = json.load(open(os.path.join(ROOT, "pilot2", "poststudy3_20260826",
                                  "results", "v6aplus_summary.json")))
# (2026-08-27) poststudy4 verifier-hardening ROUND 2 (V6a+ outer-filter
# closure + execution-shape/arity check); sha-gated in the poststudy4 block
# below.  The E5 forgery FAMILY total grows 70 -> 78 with the F11 family; the
# two confirmed round-2 exploits pinned as regressions take the GRAND total to
# 80.  Every grown count DERIVES from this summary, never typed.
V6P4 = json.load(open(os.path.join(ROOT, "pilot2", "poststudy4_20260827",
                                   "results", "v6aplus_v4_summary.json")))
# (2026-08-27) S7 NL->sigma hybrid arm (poststudy2/s7), promoted to a 10th
# main-results row; its 5/60 end-to-end error is gated here on the S7 summary.
S7 = json.load(open(os.path.join(ROOT, "pilot2", "poststudy2_20260823",
                                  "s7", "s7_summary.json")))


def rawfile(rel):
    return open(os.path.join(PAPER, rel), encoding="utf-8").read()


def tex(rel):
    """File contents with whitespace runs collapsed, so a phrase assertion is
    not defeated by wherever the source happens to wrap."""
    return re.sub(r"\s+", " ", rawfile(rel))


MAIN = tex("main.tex")
INTRO = tex("sections/01-intro.tex")
EVAL = tex("sections/08-eval.tex")
CONCL = tex("sections/10-conclusion.tex")
REWRITE = tex("sections/05-rewrite.tex")   # NOT in PROSE: several loops below
# quantify over PROSE and assert eval-headline numbers in every member, which
# S5 neither carries nor should.  Referenced directly where it is needed.
PROSE = {"main.tex": MAIN, "01-intro.tex": INTRO, "08-eval.tex": EVAL,
         "10-conclusion.tex": CONCL}

# Table 2 row order, top to bottom, as printed.
ROWS = ["baseline_claude", "baseline_qwen", "baseline_deepseek",
        "baseline_minimax", "trivial_claude", "trivial_v2", "trivial_v3",
        "governance_informed", "mechanism"]
PLAIN = ROWS[:4]
VARIANTS = ROWS[4:7]
BACKBONE = "baseline_claude"
GOV = "governance_informed"
N = S["n_questions"]
assert N == 60

fails, checks = [], 0


def ck(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        fails.append(f"{name}: {detail}")


def pct(x):            # the paper's print format for an error rate
    return f"{100*x:.1f}"


def rnd2(x):           # the paper's print format for an answered/refused share
    return f"{x:.2f}"


# ------------------------------------------------- internal invariants of (1)
for sysid in ROWS:
    t = S["taxonomy"][sysid]
    ck(f"taxonomy[{sysid}] stacks to {N}", sum(t.values()) == N,
       f"sums to {sum(t.values())}")
    errs = sum(v for k, v in t.items() if k != "correct")
    ck(f"taxonomy[{sysid}] agrees with error_rate",
       abs(errs / N - S["error_rate"][sysid]) < 1e-12, f"{errs}/{N}")

V = A["per_question_verdicts"]          # qid -> {arm: verdict}
QIDS = sorted(V)
ck("verdict matrix covers the suite", len(QIDS) == N, len(QIDS))
ref_errs = {q for q in QIDS if V[q][BACKBONE] != "correct"}
ck("reference_errors recomputes", len(ref_errs) == S["reference_errors"] == 36,
   f"{len(ref_errs)} vs {S['reference_errors']}")


def eliminated(arm):
    return sum(1 for q in ref_errs if V[q][arm] == "correct")


def errors(arm, qids=QIDS):
    return sum(1 for q in qids if V[q][arm] != "correct")


for sysid in ROWS[1:]:
    if sysid == "mechanism":
        ck("mechanism eliminates all 36", eliminated("mechanism") == 36,
           eliminated("mechanism"))
    else:
        e = eliminated(sysid) / 36
        ck(f"summary elim consistent for {sysid} (verdict matrix)",
           errors(sysid) == round(S["error_rate"][sysid] * N),
           f"{errors(sysid)}")

# ---------------------------------------------------------------- (1) vs (2)
# tab:main carries two labels on one float (tab:taxonomy anchors the retained
# errors-by-gold-form half; the six-class taxonomy half moved to the
# fig:taxonomy figure in the 2026-08-04 float surgery and is gated below
# against its data file).  Columns, positionally after dropping the
# \multirow group cell:
#   0 System | 1 E/60 | 2 Err. | 3 CI | 4 elim | 5 Ans. | 6 Ref. | 7 ok/15 |
#   8-10 errors by gold form (value/rewrite/refusal)
EVAL_RAW = rawfile("sections/08-eval.tex")
ck("float carries both labels adjacently",
   r"\label{tab:main}\label{tab:taxonomy}" in EVAL_RAW, "labels split")
tbl = EVAL_RAW[EVAL_RAW.index(r"\label{tab:main}"):]
tbl = tbl[:tbl.index(r"\end{tabular}")]
body = [l for l in tbl.splitlines() if l.strip().endswith(r"\\")]
rows = [l for l in body if "&" in l and "System" not in l]   # single header row
# (2026-08-27, poststudy4 item B) A 10th arm -- the post-registered NL->sigma
# hybrid -- is APPENDED after the compiler row.  The zip(ROWS, rows) loop below
# validates the 9 pre-registered arms exactly as before (ROWS has 9, so zip
# stops there); the appended 10th row is validated separately, from S7, in the
# hybrid block just after the loop.
ck("tab:main has 10 data rows (9 pre-registered arms + NL->sigma hybrid)",
   len(rows) == 10, f"found {len(rows)}")

ELIM_PRINT = {"baseline_claude": "---"}
for sysid in ROWS[1:]:
    ELIM_PRINT[sysid] = f"{eliminated(sysid)/36:.3f}"

ORDER6 = ["correct", "wrong_value", "execution_error", "answered_should_refuse",
          "refused_should_answer", "no_sql"]
for sysid, line in zip(ROWS, rows):
    cells = [c.strip() for c in line.replace(r"\\", "").split("&")]
    if cells and cells[0].startswith(r"\multirow"):
        cells = cells[1:]
    if cells and cells[0] == "":                  # continuation rows
        cells = cells[1:]
    raw = " ".join(cells)
    e, cov = S["error_rate"][sysid], S["coverage"][sysid]
    lo, hi = S["cluster_bootstrap"][sysid]["ci95"]
    ck(f"tab:main {sysid} E/60",
       re.sub(r"\\textbf\{(.*?)\}", r"\1", cells[1]) == str(errors(sysid)),
       f"want {errors(sysid)} in {cells[1]!r}")
    ck(f"tab:main {sysid} Err.", pct(e) + r"\%" in raw, f"want {pct(e)}% in {raw!r}")
    if sysid == "mechanism":
        # (2026-08-07, R3-X10) The compiler row is a deterministic acceptance
        # transcript over the frozen certificates, not a sample: resampling the
        # nine clusters of a constant-zero vector can only return [0.0, 0.0],
        # which reads as a measured interval that happens to be tight.  The row
        # therefore prints an em-dash.  The assertion is not dropped, it is
        # complemented: the cell must be the em-dash AND the caption must say
        # why, so the exemption cannot be silently widened to another row.
        ck("tab:main mechanism prints no CI", cells[3] == "---",
           f"want '---' in the CI column, found {cells[3]!r}")
        ck("tab:main caption explains the missing compiler CI",
           "deterministic acceptance transcript, not a sample" in EVAL
           and "carries no interval" in EVAL,
           "caption lost the no-interval justification")
        ck("the bootstrap cell the em-dash replaces is degenerate",
           (lo, hi) == (0.0, 0.0), f"mechanism ci95 = {(lo, hi)}")
    else:
        ck(f"tab:main {sysid} CI", f"[{pct(lo)},\\,{pct(hi)}]" in raw,
           f"want [{pct(lo)},{pct(hi)}] in {raw!r}")
    ck(f"tab:main {sysid} elim", ELIM_PRINT[sysid] in raw,
       f"want {ELIM_PRINT[sysid]} in {raw!r}")
    ck(f"tab:main {sysid} Ans.", cells[5] == rnd2(cov["answered"]),
       f"want {rnd2(cov['answered'])} at col 5 in {cells!r}")
    ck(f"tab:main {sysid} Ref.", cells[6] == rnd2(cov["refused"]),
       f"want {rnd2(cov['refused'])} at col 6 in {cells!r}")
    ck(f"tab:main {sysid} Ref.ok",
       cells[7] == str(S["refusal_stats"][sysid]["correct_refusals"]),
       f"want {S['refusal_stats'][sysid]['correct_refusals']} at col 7 in {cells!r}")
    t = S["taxonomy"][sysid]
    want5 = [str(t.get(k, 0)) for k in ORDER6[1:]]
    g = S["slices"]["per_gold_form"][sysid]
    want3 = [str(g["value"]["errors"]), str(g["rewrite"]["errors"]),
             str(g["refusal"]["errors"])]
    ck(f"tab:taxonomy {sysid} errors by form", cells[8:11] == want3,
       f"printed {cells[8:11]}, want {want3}")
    ck(f"tab:taxonomy {sysid} form split sums to E/60",
       sum(int(x) for x in want3) == errors(sysid), "form split broken")
    ck(f"tab:taxonomy {sysid} stacks to 60 with its complement",
       errors(sysid) == sum(int(x) for x in want5) + 0
       and t["correct"] + errors(sysid) == 60, "complement broken")

# ---- (1) vs (2): the appended NL->sigma hybrid row (poststudy4 item B) -------
# The 10th row's numbers are the frozen S7 measurement, not the pilot2 matrix,
# so they are gated here against s7_summary.json.  E/60 and the gold-form error
# split come from S7; the CI/elim/coverage columns S7 does not measure are
# em-dashed (a post-registered single run, not part of the pre-registered
# nine-arm cluster-bootstrap matrix), which the caption discloses.  The
# compiler row's constructive-upper-bound framing is untouched.
hyb = [c.strip() for c in rows[9].replace(r"\\", "").split("&")]
if hyb and hyb[0] == "":
    hyb = hyb[1:]
S7_ERR = S7["end_to_end_error"]                              # 5
S7_REF_OK = S7["by_gold_kind"]["refusal"]["e2e_correct"]     # 14 correct refusals
S7_V = S7["by_gold_kind"]["value"]["e2e_error"]              # 0
S7_RW = S7["by_gold_kind"]["rewrite"]["e2e_error"]           # 4
S7_RF = S7["by_gold_kind"]["refusal"]["e2e_error"]           # 1
ck("s7 hybrid: 5/60 end-to-end error, gold-form split 0/4/1 sums to 5",
   S7_ERR == 5 and S7["n"] == 60
   and (S7_V, S7_RW, S7_RF) == (0, 4, 1)
   and S7_V + S7_RW + S7_RF == S7_ERR
   and S7["predictions"]["S7-P2"]["met"], (S7_ERR, S7_V, S7_RW, S7_RF))
ck("tab:main 10th row is the NL->sigma hybrid with E/60 = s7 end-to-end error",
   "hybrid" in rows[9] and hyb[1] == str(S7_ERR) == "5", hyb[:2])
ck("tab:main hybrid Err. is 8.3% (5/60), gate-wired from s7",
   hyb[2] == pct(S7_ERR / 60) + r"\%" == r"8.3\%", hyb[2])
ck("tab:main hybrid em-dashes the CI/elim/coverage columns it does not measure",
   hyb[3] == "---" and hyb[4] == "---"
   and hyb[5] == "---" and hyb[6] == "---", hyb[3:7])
ck("tab:main hybrid ok/15 and gold-form error split are the s7 counts",
   hyb[7] == str(S7_REF_OK) == "14"
   and hyb[8:11] == [str(S7_V), str(S7_RW), str(S7_RF)] == ["0", "4", "1"],
   (hyb[7], hyb[8:11]))
ck("tab:main caption discloses the hybrid row's source + em-dashed columns",
   "NL-to-$\\sigma$ hybrid" in EVAL
   and "post-registered single run" in EVAL, "missing")
ck("E-takeaway promotes the hybrid as the recommended deployment path",
   r"NL-to-$\sigma$ hybrid errs $5/60$" in EVAL
   and "deployment path" in EVAL, "missing")

# ---- (1) vs the fig:taxonomy float (poststudy4 figure redesign) ------------
# (2026-08-27, FIGURE_REDESIGN_SPEC v1) The body float at label fig:taxonomy
# was REDRAWN: the six-class stacked taxonomy bar (fig3_failure_taxonomy.pdf)
# is replaced by the two-panel paired-effect + stratified-accuracy figure
# (fig3_paired_stratified.pdf), and the six-class bar relocates to the TR.
# This is a figure SWAP, not a gate weakening: the DATA-integrity assertions
# below still gate fig_data_pilot2.json cell-by-cell against the summary (the
# file is unchanged and still feeds the new figure's row order + stratified
# panel), and the "true denominator of 60" honesty phrase survives in the new
# caption; only the float's filename and the six-way-typing prose ref move.
FD = json.load(open(os.path.join(PAPER, "figures", "fig_data_pilot2.json")))
ck("fig:taxonomy data file covers the suite", FD["n_questions"] == N
   and FD["n_refusal_questions"] == 15,
   (FD["n_questions"], FD["n_refusal_questions"]))
ck("fig:taxonomy row order is the table's row order",
   [s["id"] for s in FD["systems"]] == ROWS, [s["id"] for s in FD["systems"]])
for sysid in ROWS:
    ck(f"fig:taxonomy {sysid} six classes equal the summary",
       {k: FD["taxonomy"][sysid].get(k, 0) for k in ORDER6}
       == {k: S["taxonomy"][sysid].get(k, 0) for k in ORDER6},
       f"{FD['taxonomy'][sysid]} vs {S['taxonomy'][sysid]}")
    ck(f"fig:taxonomy {sysid} bar closes on 60",
       sum(FD["taxonomy"][sysid].values()) == N,
       sum(FD["taxonomy"][sysid].values()))
ck("fig:taxonomy per-gold-form block equals the summary",
   FD["per_gold_form"] == S["slices"]["per_gold_form"], "per_gold_form drift")
ck("fig:taxonomy float wired at column width (redrawn paired+stratified)",
   r"\includegraphics[width=\columnwidth]{fig3_paired_stratified.pdf}"
   in EVAL_RAW and r"\label{fig:taxonomy}" in EVAL_RAW, "float missing")
ck("fig:taxonomy referenced at least twice in the eval section",
   EVAL_RAW.count(r"\ref{fig:taxonomy}") >= 2,
   EVAL_RAW.count(r"\ref{fig:taxonomy}"))
ck("fig:taxonomy pdf present beside the tex (redrawn paired+stratified)",
   os.path.isfile(os.path.join(PAPER, "figures",
                               "fig3_paired_stratified.pdf")), "pdf missing")
ck("fig:taxonomy caption keeps the true-denominator honesty phrase",
   "true denominator of 60" in EVAL, "missing")

# ---- tab:suite: composition against the frozen questions.json --------------
qs = {}
for f in sorted(glob.glob(os.path.join(ROOT, "pilot2", "domains", "*",
                                       "questions.json"))):
    dom = os.path.basename(os.path.dirname(f))
    for q in json.load(open(f)):
        q["_dom"] = dom
        qs[q["qid"]] = q
ck("frozen suite is 60 questions", len(qs) == 60, len(qs))
kinds = {"value": 0, "rewrite": 0, "refusal": 0}
for q in qs.values():
    kinds[q["expected_kind"]] += 1
ck("gold split 33/12/15", (kinds["value"], kinds["rewrite"], kinds["refusal"])
   == (33, 12, 15), kinds)
reasons = {}
for q in qs.values():
    if q["expected_kind"] == "refusal":
        reasons[q["refusal_reason"]] = reasons.get(q["refusal_reason"], 0) + 1
ck("refusal classes 4/5/3/3",
   (reasons.get("out-of-validity"), reasons.get("anchor-mismatch"),
    reasons.get("missing-caliber"), reasons.get("disclosure-blocked"))
   == (4, 5, 3, 3), reasons)
ck("eval prose carries the gold split",
   "33 answers, 12 rewrites and 15" in EVAL, "missing")
# (R4-TC-R4-7, landed round 5) The E4 opening said "the semantics declares
# unanswerable", but 3 of the 15 are declared unanswerable by the DISCLOSURE
# layer, not by S2's binding semantics.  Re-derive the 12/3 split from the
# same frozen questions and require the prose to carry it.
_BIND15 = sum(v for k, v in reasons.items() if k != "disclosure-blocked")
_DISC15 = reasons.get("disclosure-blocked", 0)
ck("the 15 refusals split 12 binding / 3 disclosure, re-derived",
   (_BIND15, _DISC15) == (12, 3), reasons)
ck("E4 attributes the refusal set to the specification, with the split",
   f"{_BIND15} by the binding semantics" in EVAL
   and f"{_DISC15} by the disclosure layer" in EVAL
   and "the specification declares unanswerable" in EVAL
   and "the semantics declares unanswerable" not in EVAL,
   f"{_BIND15}/{_DISC15}")

# ---- refusal-class recovery over the eight LLM arms ------------------------
# (2026-08-07, R2-F13/E-5) The E1 sentence prints one (recovered, chances) pair
# per refusal class.  Both members of all FOUR pairs are recomputed here from
# the verdict matrix against the frozen suite, so the missing-caliber pair
# cannot go missing from the prose again without this gate noticing.
LLM8 = ROWS[:8]
CLASSMACRO = {"out-of-validity": r"\OOV", "disclosure-blocked": r"\DBL",
              "anchor-mismatch": r"\AM", "missing-caliber": r"\MC"}
recov = {c: [0, 0] for c in CLASSMACRO}
for _q in qs.values():
    if _q["expected_kind"] != "refusal":
        continue
    cell = recov[_q["refusal_reason"]]
    for _arm in LLM8:
        cell[1] += 1
        cell[0] += (V[_q["qid"]][_arm] == "correct")
ck("missing-caliber recovery over the eight LLM arms is 10 of 24",
   recov["missing-caliber"] == [10, 24], recov["missing-caliber"])
for _cls, (_ok, _tot) in recov.items():
    ck(f"E1 prints the {_cls} recovery pair",
       f"{CLASSMACRO[_cls]}$ {_ok} of {_tot}" in EVAL, f"{_ok} of {_tot}")

real = auth = 0
per_dom_real = {}
for f in glob.glob(os.path.join(ROOT, "pilot2", "domains", "*",
                                "provenance.json")):
    d = json.load(open(f))
    dom = d["domain"]
    r = sum(t["rows"] for t in d["tables"].values() if not t.get("authored"))
    a = sum(t["rows"] for t in d["tables"].values() if t.get("authored"))
    per_dom_real[dom] = r
    real += r
    auth += a
ck("Sigma real rows = 3,830,036", real == 3830036, real)
ck("Sigma authored rows = 20,094", auth == 20094, auth)
ck("largest table number printed", "1{,}056{,}320" in EVAL, "missing")
ck("Sigma printed in tab:suite", "3{,}830{,}036" in EVAL, "missing")
for dom, r in per_dom_real.items():
    pretty = f"{r:,}".replace(",", "{,}")
    ck(f"tab:suite row count for {dom}", pretty in EVAL, f"want {pretty}")
gov_rows = sum(sum(json.load(open(f))["gov_seed_rows"].values()) for f in
               glob.glob(os.path.join(ROOT, "pilot2", "domains", "*",
                                      "provenance.json")))
ck("847 seed rows printed where computed", gov_rows == 847 and "847" in EVAL,
   gov_rows)

# ---------------------------------------------------------------- (1) vs (3)
plain_lo, plain_hi = pct(min(S["error_rate"][s] for s in PLAIN)), \
    pct(max(S["error_rate"][s] for s in PLAIN))
var_lo, var_hi = pct(min(S["error_rate"][s] for s in VARIANTS)), \
    pct(max(S["error_rate"][s] for s in VARIANTS))
RANGE = f"{plain_lo}--{plain_hi}" + r"\%"
VRANGE = f"{var_lo}--{var_hi}" + r"\%"
FOUR = ", ".join(pct(S["error_rate"][s]) + r"\%" for s in PLAIN[:3]) \
    + " and " + pct(S["error_rate"][PLAIN[3]]) + r"\%"
VTHREE = ", ".join(pct(S["error_rate"][s]) + r"\%" for s in VARIANTS[:2]) \
    + " and " + pct(S["error_rate"][VARIANTS[2]]) + r"\%"
for f_, txt in PROSE.items():
    ck(f"{f_} carries the plain range or its four values",
       RANGE in txt or FOUR in txt, f"neither {RANGE!r} nor {FOUR!r}")
    ck(f"{f_} carries the variant range or its three values",
       VRANGE in txt or VTHREE in txt, f"neither {VRANGE!r} nor {VTHREE!r}")
GRATE = pct(S["error_rate"][GOV]) + r"\%"
for f_, txt in PROSE.items():
    ck(f"{f_} carries the governance-arm rate {GRATE}", GRATE in txt, "missing")

asr = [str(S["taxonomy"][s]["answered_should_refuse"]) for s in PLAIN]
rok = [str(S["refusal_stats"][s]["correct_refusals"]) for s in PLAIN]
ASR = f"{asr[0]}, {asr[1]}, {asr[2]} and {asr[3]}"
ROK = f"{rok[0]}, {rok[1]}, {rok[2]} and {rok[3]}"
for f_ in ("01-intro.tex", "08-eval.tex"):
    ck(f"{f_} carries answer-through row order {ASR}", ASR in PROSE[f_], ASR)
ck(f"08-eval.tex carries correct-refusal row order {ROK}", ROK in EVAL, ROK)

best = max(VARIANTS, key=eliminated)
ck("E2 elimination sentence",
   f"removes {eliminated(best)} of the reference's 36 errors" in EVAL
   and f"elim}}={eliminated(best)/36:.3f}" in EVAL,
   f"best variant {best} eliminates {eliminated(best)}")

# ------------------------------------------------- governance arm (E3) block
G = S["governance_informed_arm"]
gerr = errors(GOV)
ck("gov errors 28", gerr == G["E_gov"] == 28, gerr)
ck("gov headline printed", r"$46.7\%$ ($28/60$)" in EVAL, "missing")
elim_gov = eliminated(GOV)
ck("elim_gov = 13/36", elim_gov == 13
   and abs(G["eliminated_by_governance"] - 13/36) < 1e-12, elim_gov)
ck("case-(iii) line printed",
   r"$\mathrm{elim}_{\mathrm{gov}}=13/36=0.361<0.40$" in EVAL, "missing")
# (2026-08-10, M6) The DENOMINATOR of the case-(iii) ratio is itself a single
# measurement, and it overshot its own frozen S5.1 point prediction (36 errors
# against 25, +44%) -- S7.3 printed elim's miss but never the denominator's
# role.  The paragraph now says so, and states the sensitivity: netting out the
# reference arm's one empty completion (CODE-Q6, which the governance arm also
# gets wrong, so only the denominator moves) gives 13/35 = 0.371, still under
# the 0.40 line, so the frozen rule still adjudicates at 0.361.  Both numbers
# are re-derived here; the clause must NOT claim the sensitivity changes the
# verdict, and must NOT be read as re-adjudicating on 0.371.
_empty = S["empty_responses"][BACKBONE]
_errs = [q for q in QIDS if V[q][BACKBONE] != "correct"]
_elim = [q for q in _errs if V[q][GOV] == "correct"]
_errs_ne = [q for q in _errs if q not in _empty]
_elim_ne = [q for q in _elim if q not in _empty]
ck("empty-completion sensitivity is 13/35=0.371 (numerator unmoved)",
   (len(_elim_ne), len(_errs_ne)) == (13, 35)
   and f"{len(_elim_ne)/len(_errs_ne):.3f}" == "0.371",
   (len(_elim_ne), len(_errs_ne)))
# (2026-08-26, M2 honest-uncertainty pass) RELOCATED TO TR per protocol:
# the in-body sensitivity clause ("does not itself enter the rule",
# "$13/35=0.371$ ...", "the case is unchanged") moved to the TR's
# item-by-item ledger, which prints the full clause.  The 13/35=0.371
# VALUE above still re-derives and must stay true; the body keeps the
# overshoot NAMED inside the ledger sentence plus the TR pointer,
# asserted here instead.
ck("denominator overshoot named in the ledger sentence (full clause: TR)",
   "the denominator's own overshoot" in EVAL
   and r"accounted item by item in~\cite{asofgov-tr}" in EVAL, "missing")
ck("protocol-scoped wording", r"\textbf{under this protocol}" in EVAL
   and "512-token" in EVAL, "missing")
for f_ in ("main.tex", "01-intro.tex", "10-conclusion.tex"):
    ck(f"{f_} keeps the protocol scoping phrase",
       "under this protocol" in PROSE[f_], "missing")

new_break = sum(1 for q in QIDS
                if V[q][BACKBONE] == "correct" and V[q][GOV] != "correct")
ck("gov paired vs backbone 13/5",
   (elim_gov, new_break) == (13, 5)
   and G["paired_vs_baseline_claude"]["c_other_wrong_gov_correct"] == 13
   and G["paired_vs_baseline_claude"]["b_other_correct_gov_wrong"] == 5,
   (elim_gov, new_break))
ck("gov elim/new sentence printed",
   "eliminates 13 of the reference's 36 errors and introduces 5 new" in EVAL,
   "missing")
c_v2 = sum(1 for q in QIDS
           if V[q]["trivial_v2"] != "correct" and V[q][GOV] == "correct")
b_v2 = sum(1 for q in QIDS
           if V[q]["trivial_v2"] == "correct" and V[q][GOV] != "correct")
ck("gov paired vs trivial_v2 11/4", (c_v2, b_v2) == (11, 4), (c_v2, b_v2))
ck("two-factor sentence printed",
   r"$36\to35$" in EVAL and r"$35\to28$" in EVAL, "missing")

PROBE7 = sorted(G["probe7_metadata_undecidable"])
MD5 = sorted(G["metadata_decidable_5"])
DB3 = sorted(G["disclosure_blocked_3"])
ck("probe set is 7 / md set 5 / db set 3",
   (len(PROBE7), len(MD5), len(DB3)) == (7, 5, 3))
p7 = errors(GOV, PROBE7)
ck("gov probe errors 6/7", p7 == 6 == G["probe7_errors"], p7)
ck("probe sentence printed", r"errs on \textbf{6 of 7}" in EVAL, "missing")
m5 = len(MD5) - errors(GOV, MD5)
# (2026-08-10, M3) RENAMED.  This quantity is the arm's ABSOLUTE correct count
# on the registry-decidable five -- it is NOT a repair count, and the old name
# ("fixed 4/5") plus the old prose ("fixes 4 of 5") asserted a repair reading
# the matrix refutes.  Under the paired reading the arm repairs 3 (DEB-Q7,
# FIN-Q8, W1-Q5), was ALREADY correct on CA-Q6 under the backbone, and
# REGRESSES on CARD-Q6 (backbone correct -> gov answers where gold refuses).
# The abstract always used the absolute reading ("1 of 5"), so the old body
# wording also contradicted it.  Body and abstract now share one reading, and
# the transition census below is asserted so the repair mislabel cannot return.
ck("gov metadata-decidable ABSOLUTE correct 4/5 (not a repair count)",
   m5 == 4 == G["md5_fixed"], m5)
md5_repairs = sum(1 for q in MD5
                  if V[q][BACKBONE] != "correct" and V[q][GOV] == "correct")
md5_already = sum(1 for q in MD5
                  if V[q][BACKBONE] == "correct" and V[q][GOV] == "correct")
md5_broken = sum(1 for q in MD5
                 if V[q][BACKBONE] == "correct" and V[q][GOV] != "correct")
ck("md5 transition census is 3 repairs / 1 already correct / 1 regression",
   (md5_repairs, md5_already, md5_broken) == (3, 1, 1),
   (md5_repairs, md5_already, md5_broken))
ck("md5 sentence printed in the absolute reading, parallel to probe7",
   r"errs on only \textbf{1 of" in EVAL and "fixes 4 of 5" not in EVAL,
   "missing, or the refuted repair wording came back")
# (2026-08-07, R2-F12/E-3) The abstract no longer says the arm's errors
# "concentrate on exactly the decisions that need a data probe" (they do not:
# the value side carries most of them).  It now names the refusal-side split,
# and both fractions are derived here from the same two counts the E3 block
# already gates -- 6 of 7 probe-decidable, 5-4=1 of 5 registry-decidable.
ck("abstract prints the refusal-side split derived from probe7/md5",
   f"({p7} of {len(PROBE7)}, against {len(MD5) - m5} of {len(MD5)} on "
   "registry-decidable refusals)" in MAIN
   and "refusal-side errors concentrate where only a data probe decides"
   in MAIN, f"{p7} of {len(PROBE7)} / {len(MD5) - m5} of {len(MD5)}")
d3 = errors(GOV, DB3)
ck("gov disclosure 3/3 answered", d3 == 3, d3)
ck("policy-on-file sentence printed",
   "a policy on file is not a policy enforced" in EVAL, "missing")

# (2026-08-23, R2-1-4) The probe-oracle ceiling is now printed (E3(f), the
# abstract, S9), so every half of it is re-derived from the frozen matrix:
# crediting the arm with all six probe-decidable residuals leaves 22/60, and
# lifts elim by exactly the overlap of those residuals with the reference's
# 36 errors -- the two regressions (backbone correct, arm wrong) add nothing
# to elim by elim's own definition.  Nothing here is a new run: it is
# arithmetic over per_question_verdicts, the same source as elim_gov.
p7_resid = sorted(q for q in PROBE7 if V[q][GOV] != "correct")
ck("probe-oracle residual set size re-derives as 6",
   len(p7_resid) == p7 == 6, len(p7_resid))
p7_overlap = sum(1 for q in p7_resid if q in ref_errs)
ck("probe-oracle overlap with the reference's 36 errors is 4",
   p7_overlap == 4, p7_overlap)
ck("probe-oracle regressions (backbone correct) are the other 2",
   len(p7_resid) - p7_overlap == 2
   and sum(1 for q in p7_resid if V[q][BACKBONE] == "correct") == 2,
   len(p7_resid) - p7_overlap)
ck("probe-oracle error floor 22/60",
   errors(GOV) - len(p7_resid) == 22, errors(GOV) - len(p7_resid))
_orac = elim_gov + p7_overlap
ck("probe-oracle elim ceiling 17/36 = 0.472",
   _orac == 17 and len(ref_errs) == 36
   and f"{_orac/len(ref_errs):.3f}" == "0.472", _orac)
ck("probe-oracle sentence printed in E3 with all three numbers",
   r"crediting the arm with all six probe-decidable residuals" in EVAL
   and "four sit among the reference's 36 errors" in EVAL
   and r"leaves $22/60$" in EVAL and r"$17/36=0.472$" in EVAL, "missing")
ck("policy/registry residual count is the printed four",
   d3 + (len(MD5) - m5) == 4
   and "the four policy/registry residuals are not probe-decidable" in EVAL,
   d3 + (len(MD5) - m5))
# (2026-08-26, M2) The ABSTRACT's copy of the probe-oracle ceiling moved
# out under the ~210-word compression; E3's arithmetic (asserted above)
# and S9's sentence remain, and the abstract must stay clean of remnants.
ck("S9 carries the probe-oracle ceiling; abstract no longer prints it",
   "probe-oracle ceiling" in CONCL and "0.472" not in MAIN, "missing")

# (2026-08-23, R3-1-4) The ceiling above credits only the probe-decidable
# refusal residuals; an execution-feedback loop would also recover the
# arm's failed executions (Figure 3 shows execution errors in every LLM
# arm), so the printed bound is EXTENDED: credit also every
# execution-error residual of the governance-informed arm.  Every count
# re-derives from the same frozen verdict matrix as elim_gov; the two
# credited sets are disjoint by verdict class, so no residual is counted
# twice.  Nothing here is a new run.
exec_resid = sorted(q for q in QIDS if V[q][GOV] == "execution_error")
ck("exec-residual set re-derives as 9 (taxonomy agrees)",
   len(exec_resid) == 9 == S["taxonomy"][GOV]["execution_error"],
   len(exec_resid))
ck("exec residuals disjoint from the probe-decidable six",
   not set(exec_resid) & set(p7_resid),
   sorted(set(exec_resid) & set(p7_resid)))
exec_overlap = sum(1 for q in exec_resid if q in ref_errs)
ck("exec-residual overlap with the reference's 36 errors is 7",
   exec_overlap == 7, exec_overlap)
ck("exec-residual regressions (backbone correct) are the other 2",
   len(exec_resid) - exec_overlap == 2
   and sum(1 for q in exec_resid if V[q][BACKBONE] == "correct") == 2,
   len(exec_resid) - exec_overlap)
ck("probe+execution error floor 13/60",
   errors(GOV) - len(p7_resid) - len(exec_resid) == 13,
   errors(GOV) - len(p7_resid) - len(exec_resid))
_orac2 = elim_gov + p7_overlap + exec_overlap
ck("probe+execution elim ceiling 24/36 = 0.667",
   _orac2 == 24 and f"{_orac2/len(ref_errs):.3f}" == "0.667", _orac2)
ck("extended-ceiling sentence printed in E3 with all its numbers",
   "further crediting all nine execution-error residuals" in EVAL
   and "seven among the 36, two regressions" in EVAL
   and r"leaves $13/60$" in EVAL and r"$24/36=0.667$" in EVAL, "missing")
# (2026-08-26, M2) same relocation as the probe-oracle ceiling above.
ck("S9 carries the extended ceiling; abstract no longer prints it",
   r"bounds the recoverable share at $0.667$" in CONCL
   and "0.667" not in MAIN, "missing")

FLIP8 = ["CA-Q1", "CA-Q2", "FIN-Q1", "FIN-Q2", "F1-Q1", "F1-Q2",
         "W1-Q1", "W1-Q2"]           # RC-8 pairs, ACCEPTANCE_REPORT S5
f8 = errors(GOV, FLIP8)
ck("gov flip-question errors 3/8", f8 == 3, f8)
# DERIVED (2026-08-06, R1-E3): the verdict composition of the 3 flip errors
# is recomputed from the matrix -- 2 wrong_value + 1 execution_error -- and
# the prose must say so (the old string pinned "all by resolving the wrong").
flip_verd = sorted(V[q][GOV] for q in FLIP8 if V[q][GOV] != "correct")
ck("gov flip-error verdicts derive 2 wrong_value + 1 execution_error",
   flip_verd == ["execution_error", "wrong_value", "wrong_value"], flip_verd)
ck("flip sentence printed",
   "errs on 3 --- two by resolving the wrong" in EVAL
   and "one a failed execution" in EVAL, "missing")
HULL5 = ["CARD-Q5", "EF2-Q4", "FIN-Q6", "F1-Q6", "W1-Q4"]  # PREREG S4.2(c)
ck("gov hull-trim errors 1/5 (giveaway questions)", errors(GOV, HULL5) == 1,
   errors(GOV, HULL5))

pc = S["slices"]["per_cluster"]
ck("gov cluster gradient printed",
   pc[GOV]["codebase_community"]["errors"] == 6
   and pc[GOV]["financial"]["errors"] == 1
   and "6/7 errors" in EVAL and r"$4\to1$" in EVAL, "cluster split moved")
# DERIVED (2026-08-06, R1-E2): the E1 depth sentence no longer claims
# codebase_community is EVERY arm's worst cluster (false for 3 arms); it
# claims top-3-hardest for every LLM arm, and the check recomputes that rank
# plus the four plain-baseline codebase error counts from per_cluster.
for arm in ROWS[:8]:
    rates = {c: d["errors"] / d["n"] for c, d in pc[arm].items()}
    cb_rank = 1 + sum(1 for r_ in rates.values()
                      if r_ > rates["codebase_community"])
    ck(f"codebase_community within the 3 hardest clusters for {arm}",
       cb_rank <= 3, cb_rank)
ck("plain baselines err 6,6,7,7 of 7 on codebase_community",
   [pc[s]["codebase_community"]["errors"] for s in PLAIN] == [6, 6, 7, 7]
   and all(pc[s]["codebase_community"]["n"] == 7 for s in PLAIN),
   [pc[s]["codebase_community"]["errors"] for s in PLAIN])
ck("E1 depth sentence printed (top-3 wording + baseline counts)",
   "is among the hardest clusters for every arm" in EVAL
   and "$6,6,7,7$ of 7" in EVAL, "missing")
ck("gov refusal side printed",
   S["refusal_stats"][GOV]["correct_refusals"] == 5
   and S["refusal_stats"][GOV]["over_refusals_on_value_questions"] == 1
   and r"$4\to5$ of 15" in EVAL and "1 of 45" in EVAL, "missing")
# R1-E10 companions: the over-refusal comparison in prose is derived here.
ck("over-refusal comparison derives (backbone 5, trivial_v2 1, gov 1)",
   S["refusal_stats"][BACKBONE]["over_refusals_on_value_questions"] == 5
   and S["refusal_stats"]["trivial_v2"]["over_refusals_on_value_questions"]
   == 1 and "down from the plain backbone's 5" in EVAL, "missing")

# alternative explanations + their exclusion evidence
for pat, why in ((r"r=0\.400", "dilution correlation"),
                 ("zero empty responses", "transport exclusion"),
                 ("correctly refused", "imperative-compliance exclusion"),
                 ("28.3k", "longest package"), ("23.5k", "financial package")):
    ck(f"E3 alternative-explanation block carries {why}",
       re.search(pat, EVAL), pat)
ck("gov arm empty responses really zero",
   S["empty_responses"][GOV] == [], S["empty_responses"][GOV])

# prediction accounting -- DERIVED (2026-08-06, R1-E1): the 8 point
# predictions and 80% intervals are parsed from the frozen PREREG S5.1 table
# (mechanism row is an anchor, not a prediction; the interval dash is an
# en-dash), scored against pilot2_arms_summary.json error_counts, and only
# then is the prose sentence asserted.  The old string-presence-only check
# pinned a wrong tally (6 of 8).
PREREG_RAW = open(os.path.join(ROOT, "pilot2", "PREREG_pilot2_arms.md"),
                  encoding="utf-8").read()
pred = {}
for arm in ROWS[:8]:
    m = re.search(r"^\|\s*`%s`\s*\|\s*\*{0,2}(\d+)[^|]*\|\s*(\d+)\s*[–-]\s*(\d+)\s*\|"
                  % re.escape(arm), PREREG_RAW, re.M)
    ck(f"PREREG S5.1 prediction row parses for {arm}", m is not None,
       "row not found")
    if m:
        pred[arm] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
EC = A["error_counts"]
for arm in pred:
    ck(f"error_counts[{arm}] agrees with the verdict matrix",
       EC[arm] == errors(arm), (EC[arm], errors(arm)))
# (2026-08-10, M6) the case-(iii) denominator against its own frozen point --
# asserted here because `pred` is only parsed above; see the M6 block at the
# case-(iii) line for why this matters.
ck("case-(iii) denominator (36) overshot its own frozen point prediction (25)",
   (errors(BACKBONE), pred[BACKBONE][0]) == (36, 25),
   (errors(BACKBONE), pred.get(BACKBONE)))
# (2026-08-26, M2) the "$36$ against a frozen point of $25$" literal moved
# to the TR ledger with the rest of the sensitivity clause; the VALUE ck
# above still scores 36 vs 25 from the frozen PREREG, and the compressed
# overshoot clause is asserted at the M6 site above.
above_point = sum(1 for a, (pt, lo, hi) in pred.items() if EC[a] > pt)
above_hi = sum(1 for a, (pt, lo, hi) in pred.items() if EC[a] > hi)
inside = sorted(a for a, (pt, lo, hi) in pred.items() if lo <= EC[a] <= hi)
ck("all 8 observed error counts exceed their point predictions",
   len(pred) == 8 and above_point == 8, (len(pred), above_point))
ck("7 of 8 exceed the 80% upper end; trivial_claude alone inside",
   above_hi == 7 and inside == ["trivial_claude"], (above_hi, inside))
# (2026-08-26, M2 second pass) The accounting paragraph moved to the TR in
# full; the body keeps the optimism tally and the ledger pointer inside the
# case-(iii) verdict paragraph.  The sharpest-miss literal (14 [8--22] ->
# 28) and the elimination miss's point pair (0.55 -> 0.361) are TR-side
# now; both stay DERIVED and SCORED here (above/below) so the values
# cannot drift while relocated.
ck("prediction-optimism sentence printed with the TR ledger pointer",
   "all 8 observed error counts exceed their point predictions and 7 of 8"
   in EVAL
   and r"the miss ledger is accounted item by item in~\cite{asofgov-tr}"
   in EVAL, "missing")

# (2026-08-10, M4) "Prediction accounting, in full" was NOT full: PREREG S5.2
# freezes two more governance-arm predictions besides elim_gov and the probe
# set -- correct_refusals and over_refusals -- and the paragraph reported
# neither.  Both are now parsed out of the frozen PREREG the same way S5.1's
# per-arm table is, scored against the observed refusal statistics, and only
# then is the prose asserted, so "in full" is machine-enforced rather than a
# promise.  Note the direction: correct_refusals lands BELOW its interval and
# over_refusals AT its floor -- i.e. the arm refuses less than we predicted,
# which is the unflattering direction for the paper's own thesis.
RS = S["refusal_stats"][GOV]
m = re.search(r"`correct_refusals`\s*点\s*\*\*(\d+)/(\d+)\*\*（区间\s*(\d+)[–-](\d+)）",
              PREREG_RAW)
ck("PREREG S5.2 correct_refusals prediction parses", m is not None, "row not found")
if m:
    cr_pt, cr_den, cr_lo, cr_hi = (int(x) for x in m.groups())
    cr_obs = RS["correct_refusals"]
    ck("S5.2 correct_refusals denominator is the 15 refusal questions",
       cr_den == RS["n_refusal_questions"] == 15, (cr_den, RS["n_refusal_questions"]))
    ck("correct_refusals observed 5 falls BELOW its frozen 80% interval",
       (cr_pt, cr_lo, cr_hi, cr_obs) == (9, 6, 12, 5) and cr_obs < cr_lo,
       (cr_pt, cr_lo, cr_hi, cr_obs))
    # (2026-08-26, M2; deepened same day) the correct-refusal miss moved
    # to the TR's item-by-item ledger with the rest of the accounting
    # paragraph; it stays parsed and SCORED from the frozen PREREG above
    # (below-interval asserted on values), and the body's ledger pointer
    # is asserted at the optimism-sentence ck.
m = re.search(r"`over_refusals`\s*由素基线的\s*~(\d+)/(\d+)\s*升至\s*~(\d+)/(\d+)，"
              r"\s*区间\s*(\d+)[–-](\d+)）", PREREG_RAW)
ck("PREREG S5.2 over_refusals prediction parses", m is not None, "row not found")
if m:
    _, _, or_pt, or_den, or_lo, or_hi = (int(x) for x in m.groups())
    or_obs = RS["over_refusals_on_value_questions"]
    ck("S5.2 over_refusals denominator is the 45 value questions",
       or_den == RS["n_value_questions"] == 45, (or_den, RS["n_value_questions"]))
    ck("over_refusals observed 1 sits AT its frozen interval floor",
       (or_pt, or_lo, or_hi, or_obs) == (4, 1, 9, 1) and or_obs == or_lo,
       (or_pt, or_lo, or_hi, or_obs))
    # (2026-08-26, M2; deepened same day) same relocation as the
    # correct-refusal miss: TR-side, values still scored above.
# the two S5.2 predictions the paragraph already carried, re-parsed from source
m = re.search(r"`elim_gov`\s*点\s*\*\*([\d.]+)\*\*（区间\s*([\d.]+)[–-]([\d.]+)）",
              PREREG_RAW)
ck("PREREG S5.2 elim_gov prediction parses and matches the printed 0.55",
   m is not None and m.group(1) == "0.55"
   and (m.group(2), m.group(3)) == ("0.35", "0.75"),
   m.groups() if m else "row not found")
# (2026-08-23, review R1-EXP-6, partial) The abstract's categorical
# elimination claim now reports elim's own frozen 80% prediction interval
# beside the point value, and says the interval straddles the 0.40 line
# (the C' threshold asserted at the case-(iii) site above).  The interval
# is parsed from the frozen PREREG here, never typed into the paper; the
# straddle itself is re-derived, not asserted as prose.
if m:
    _lo, _hi = float(m.group(2)), float(m.group(3))
    ck("elim's frozen interval really straddles the 0.40 line",
       _lo < 0.40 < _hi, (_lo, _hi))
    # (2026-08-26, M2 honest-uncertainty pass; deepened same day)
    # RELOCATED: the abstract now prints the frozen-run verdict + five-rep
    # span + paired nine-cluster CI (asserted in the M2 block below, all
    # derived from the s3/s4 summary JSONs); the frozen [0.35,0.75]
    # interval literal moved to the TR ledger with the accounting
    # paragraph, and the body NAMES it ("the elimination miss's frozen
    # interval") next to the ledger pointer.  The straddle VALUE stays
    # re-derived just above; nothing numeric weakens.
    ck("the frozen elim interval is named beside the TR ledger pointer",
       "the elimination miss's frozen interval" in EVAL,
       "the ledger sentence lost the named interval")
m = re.search(r"答错\s*≥(\d+)/(\d+)\*\*（区间\s*(\d+)[–-](\d+)）", PREREG_RAW)
ck("PREREG S5.2 probe-set prediction parses as >=3/7 [3-6]",
   m is not None and tuple(int(x) for x in m.groups()) == (3, 7, 3, 6),
   m.groups() if m else "row not found")
# (2026-08-26, M2; deepened same day) the accounting paragraph relocated
# to the TR in full; all four S5.2 predictions still parsed + scored
# above, and the body's case-(iii) paragraph carries the optimism tally,
# the ledger pointer, and names both TR-side items (frozen interval,
# denominator overshoot) -- asserted at their own cks.
ck("the miss ledger is pointed at from the case-(iii) paragraph",
   r"accounted item by item in~\cite{asofgov-tr}" in EVAL
   and "the elimination miss's frozen interval" in EVAL,
   "the ledger pointer or its named items are gone")

# trivial_v2 void disclosure (both runs)
ck("trivial_v2 void disclosed with both runs",
   "27 correct/33 errors" in EVAL and "25/35" in EVAL
   and "voided" in EVAL, "missing")
void_dir = os.path.join(ROOT, "pilot2", "runs",
                        "trivial_v2__VOID_RUN1_2026-08-04")
ck("voided run preserved on disk", os.path.isdir(void_dir), void_dir)

# pre-registered criteria (A'/B'/C'), labelled as new, not the old gates
ck("criteria A'/B'/C' all pass in the summary",
   S["A_pass(min plain-baseline err>=0.30)"]
   and S["B_pass(mechanism err=0 & elim=1.0)"]
   and S["C_pass(trivial eliminates<0.40)"], "a criterion flipped")
ck("criteria named in eval", "A$'$" in EVAL and "B$'$" in EVAL
   and "C$'$" in EVAL, "missing")
ck("criteria-note guard: old gates not re-run",
   "NOT a re-run" in S.get("criteria_note", ""), S.get("criteria_note"))

# empty-response ledger
ck("empty-response ledger matches",
   S["empty_responses"]["baseline_claude"] == ["CODE-Q6"]
   and len(S["empty_responses"]["trivial_claude"]) == 2
   and len(S["empty_responses"]["trivial_v3"]) == 2, S["empty_responses"])

# mechanism anchor
ck("mechanism 0/60 with 15/15 refusals",
   S["error_rate"]["mechanism"] == 0.0
   and S["refusal_stats"]["mechanism"]["correct_refusals"] == 15, "")

# certificates / forgeries prose
for pat, why in ((r"accepts \$60/60\$", "verifier acceptance"),
                 (r"rejects \$34/34\$", "forgery rejection"),
                 ("11 unmodified compiler certificates", "genuine bases"),
                 (r"those \$50/60\$", "strict track"),
                 ("fails closed", "fail-closed wording"),
                 ("6 value/window lies", "F1 family"),
                 (r"5 \\emph\{field deletions\}", "F2 family"),
                 ("9 semantic lies", "F3 family"),
                 ("10 disclosure", "F4 family"),
                 ("4 refusal-class substitutions", "F5 family"),
                 (r"deleting \\emph\{part\}", "accepted boundary case")):
    ck(f"E5 carries {why}", re.search(pat, EVAL), pat)
# (2026-08-10) F5 added verifier-side: the OOV/AM(iv) class-substitution face
# and the self-declared clause-(iv) replay variant.  Battery grows 30 -> 34
# over 10 -> 11 bases (CARD-Q2 joins: no prior base was an ANSWER on a
# distinct-anchor ratio pair, which the fabricated-refusal forgery requires).
# (2026-08-26, poststudy3 / PREREG sha 426017dd...) The corpus grows again:
# an external review exhibited V6a-accepted mutations, and the hardened
# V6a+ ships with 5 pinned reproduction mutations + 31 new F6-F10 forgeries
# on top of the 34.  Every grown total below DERIVES from the poststudy3
# summary JSON (V6P, sha-gated in the poststudy3 block); the pre-registered
# battery's own strings stay asserted above, so nothing is weakened -- the
# totals are extended.
# (2026-08-27, poststudy4 / PREREG sha a7ff1311...) ROUND 2: a second external
# review exhibited a genuine ratio/delta certificate whose OUTER SELECT carries
# a top-level WHERE filtering the answer to zero rows, which V6a+ still
# ACCEPTed; the round-2 V6a+ closes it (outer-filter closure V6P_SHAPE +
# executed-arity check V6P_ARITY).  The forgery FAMILY total grows 70 -> 78
# with the 8-forgery F11 outer-row-filter family; the two confirmed exploits
# (V1, V1c) pinned as round-2 regressions take the GRAND total to 80.  Every
# grown total below DERIVES from V6P4 (sha-gated in the poststudy4 block).
F15_TOT = V6P["old_forgeries_f1_f5"]["total"]   # 34 pre-registered (F1-F5)
NEW_TOT = V6P["new_forgeries_f6_f10"]["total"]  # 31 F6-F10 (poststudy3)
PIN_TOT = V6P["pinned_regressions"]["total"]    # 5 round-1 pinned mutations
PRIOR_70 = F15_TOT + NEW_TOT + PIN_TOT          # 70 (the poststudy3 total)
F11_TOT = V6P4["new_forgeries_f11"]["total"]        # 8 F11 outer-row-filter
PIN2_TOT = V6P4["forgery_counts"]["pinned_round2"]  # 2 round-2 pinned (V1, V1c)
TOT_FORGE = PRIOR_70 + F11_TOT                  # 78 (task formula 70+|F11|)
GRAND_FORGE = TOT_FORGE + PIN2_TOT              # 80 (incl. 2 round-2 pinned)
POST_TOT = NEW_TOT + PIN_TOT + F11_TOT          # 44 (F6-F10 + pin-r1 + F11)
ck("forgery family battery derives as 34+31+5+8=78, post-registered 44",
   (F15_TOT, NEW_TOT, PIN_TOT, F11_TOT, TOT_FORGE, POST_TOT)
   == (34, 31, 5, 8, 78, 44), (F15_TOT, NEW_TOT, PIN_TOT, F11_TOT))
ck("poststudy4 summary pins the same counts (70 prior, 78 family, 80 grand)",
   V6P4["forgery_counts"]["prior_total_70"] == PRIOR_70 == 70
   and V6P4["forgery_counts"]["f11"] == F11_TOT == 8
   and V6P4["forgery_counts"]["task_formula_70_plus_f11"] == TOT_FORGE == 78
   and V6P4["forgery_counts"]["grand_total_forged_certs"] == GRAND_FORGE == 80
   and V6P4["forgery_counts"]["pinned_round2"] == PIN2_TOT == 2,
   V6P4["forgery_counts"])
ck("family sizes sum to the pre-registered 34",
   6 + 5 + 9 + 10 + 4 == F15_TOT == 34)
ck("old F1-F5 corpus still fully rejects with frozen attribution kept",
   V6P["old_forgeries_f1_f5"]["reject"] == F15_TOT
   and V6P["old_forgeries_f1_f5"]["frozen_attribution_kept"] == F15_TOT
   and V6P["old_forgeries_f1_f5"]["bases_accept"] == "11/11"
   and V6P["old_forgeries_f1_f5"]["by_family"]
   == {"F1": 6, "F2": 5, "F3": 9, "F4": 10, "F5": 4},
   V6P["old_forgeries_f1_f5"])
ck("forgery total consistent across intro/abstract/rewrite/conclusion",
   rf"rejects ${TOT_FORGE}/{TOT_FORGE}$ forgeries" in PROSE["01-intro.tex"]
   and f"{TOT_FORGE} of {TOT_FORGE} forgeries" in MAIN
   and f"10 of the {F15_TOT} pre-registered forgeries" in REWRITE
   and f"11 bases and {F15_TOT} forgeries plus the post-registered V6a+"
   in PROSE["10-conclusion.tex"], "drift")
ck("intro and E-takeaway carry the post-registered share",
   f"{POST_TOT} of them post-registered" in PROSE["01-intro.tex"]
   and (f"rejects all {TOT_FORGE} forgeries, {POST_TOT} of them "
        "post-registered") in EVAL, "missing")
ck("E5 announces the 78-forgery corpus with its split",
   f"{TOT_FORGE} forged certificates in all" in EVAL
   and f"{F15_TOT} pre-registered with the suite" in EVAL
   and f"{POST_TOT} post-registered with the V6a+ hardening" in EVAL,
   "missing")
per_fam3 = {k: v["total"] for k, v in
            V6P["new_forgeries_f6_f10"]["families"].items()}
ck("F6-F10 family sizes derive and sum to 31, each fully rejected+asserted",
   per_fam3 == {"F6": 6, "F7": 5, "F8": 8, "F9": 6, "F10": 6}
   and sum(per_fam3.values()) == NEW_TOT
   and all(v["rejected"] == v["total"] == v["asserted_ok"] for v in
           V6P["new_forgeries_f6_f10"]["families"].values()), per_fam3)
for _fam, _label in (("F6", "F6 wrong aggregate"), ("F7", "F7 leg swap"),
                     ("F8", "F8 wrong/absent predicate"),
                     ("F9", "F9 narrowed/widened window"),
                     ("F10", "F10 constant/multi-row")):
    ck(f"E5 prints {_fam} with its derived count",
       f"{_label} ({per_fam3[_fam]})" in EVAL, per_fam3[_fam])
NEW_BASES = sorted({b for v in V6P["new_forgeries_f6_f10"]["families"].values()
                    for b in v["bases"]})
ck("F6-F10 distinct bases recompute to 22, all in the frozen suite, all "
   "accepted", len(NEW_BASES) == 22
   and V6P["new_forgeries_f6_f10"]["bases_accept"] == "22/22"
   and all(b in qs for b in NEW_BASES), (len(NEW_BASES), NEW_BASES[:6]))
ck("E5 prints the 22-base coverage and the 31/31 rejection",
   f"over {len(NEW_BASES)} accepted bases" in EVAL
   and rf"reject ${NEW_TOT}/{NEW_TOT}$" in EVAL, "missing")
ck("the 5 reproduction mutations reject, each on its pinned reason code",
   V6P["pinned_regressions"]["reject"] == PIN_TOT == 5
   and V6P["pinned_regressions"]["with_pinned_reason_code"] == 5
   and sorted(r["reason_code"] for r in V6P["pinned_regressions"]["rows"])
   == ["V6P_LEG_ROLE", "V6P_MEASURE", "V6P_PARSE", "V6P_SHAPE",
       "V6P_WINDOW"], V6P["pinned_regressions"])
ck("E5 prints the pinned-regression sentence",
   f"the {PIN_TOT} reproduction mutations" in EVAL
   and "pinned reason code" in EVAL, "missing")
ck("genuine 60 accept under V6a+; PASS/SKIP = answer+rewrite / refusal",
   V6P["genuine60"]["total"] == 60 and V6P["genuine60"]["accept"] == 60
   and V6P["genuine60"]["reject"] == 0
   and V6P["genuine60"]["v6aplus_status"]["PASS"]
   == kinds["value"] + kinds["rewrite"] == 45
   and V6P["genuine60"]["v6aplus_status"]["SKIP"] == kinds["refusal"] == 15,
   V6P["genuine60"])
ck("all four poststudy3 predictions hold with no misses",
   V6P["all_predictions_hold"]
   and all(V6P["predictions"][p]["holds"]
           and V6P["predictions"][p]["misses"] == []
           for p in ("P1", "P2", "P3", "P4")), V6P["predictions"])
ck("E5 prints attribution persistence, invariance and the outcome",
   "keep every frozen" in EVAL
   and "per-question verdicts identical" in EVAL
   and "All four frozen predictions held" in EVAL
   and rf"total is ${TOT_FORGE}/{TOT_FORGE}$ rejected" in EVAL, "missing")
ck("E5 discloses the review-found gap in one sentence",
   "An external review (2026-08) exhibited what this battery had not probed"
   in EVAL
   and ("V6a accepted wrong-aggregate, swapped-leg, constant-output and "
        "narrowed-window mutations") in EVAL, "missing")
# ===================================================== poststudy4 round-2 (F11)
# (2026-08-27) Round-2 V6a+ closes the outer-row-filter gap (a genuine
# ratio/delta whose OUTER SELECT filters the scalar answer to 0 rows, which
# V6a+ still ACCEPTed) with an outer-filter closure (V6P_SHAPE) plus a
# read-only execution-shape/arity check (V6P_ARITY).  All counts derive from
# V6P4; the E5 prose that states them is asserted here.  The poststudy4
# provenance chain (PREREG bytes, FREEZE, shipped verifier files) is pinned in
# the poststudy4 block at the end of this file.
F11 = V6P4["new_forgeries_f11"]
ck("F11 outer-row-filter family derives as 8, all reject, all asserted",
   F11["total"] == F11_TOT == 8 and F11["reject"] == 8
   and F11["asserted_ok"] == 8 and F11["rejected_by"] == {"V6a+": 8}, F11)
F11_BASES = sorted(F11["distinct_bases"])
ck("F11 distinct bases recompute to 8, all in the frozen suite, all accepted",
   len(F11_BASES) == 8 and F11["bases_accept"] == "23/23"
   and all(b in qs for b in F11_BASES), (len(F11_BASES), F11_BASES))
ck("E5 prints the F11 family with its derived count and 8/8 rejection",
   f"F11 outer-row-filter ({F11_TOT})" in EVAL
   and rf"${F11_TOT}/{F11_TOT}$" in EVAL, "missing")
# the read-only execution-shape check V6P_ARITY is the new round-2 code; the
# arity backstop trips on 7 of the 8 F11 forgeries (the 8th is the TRUE outer
# WHERE, still 1x1, caught by the structural closure alone).
ck("V6P_ARITY is the round-2 execution-shape code; arity backstop hits 7 of 8",
   F11["arity_backstop_hits"] == 7
   and V6P4["reason_code_distribution"]["v6aplus_x_arity"] == {"V6P_ARITY": 17},
   (F11["arity_backstop_hits"],
    V6P4["reason_code_distribution"]["v6aplus_x_arity"]))
# the 2 confirmed exploits (V1, V1c) that motivated the fix, pinned as round-2
# regressions -> grand total 80 = 78 family + 2 pinned
EXP = V6P4["exploits_p0repro"]
ck("the 2 confirmed round-2 exploits (V1, V1c) all REJECT, pinned round-2",
   EXP["confirmed_all_reject"]
   and set(EXP["confirmed_exploit_names"])
   == {"V1_outer_where_1eq0", "V1c_outer_where_false"}
   and V6P4["pinned_regressions"]["round2_total"] == PIN2_TOT == 2
   and V6P4["pinned_regressions"]["total"] == 7, EXP["confirmed_exploit_names"])
_v1 = next(r for r in EXP["rows"] if r["name"] == "V1_outer_where_1eq0")
_v1c = next(r for r in EXP["rows"] if r["name"] == "V1c_outer_where_false")
ck("V1/V1c reject with V6P_SHAPE (structural) + V6P_ARITY (execution backstop)",
   _v1["v6aplus_code"] == _v1c["v6aplus_code"] == "V6P_SHAPE"
   and _v1["v6aplus_x_code"] == _v1c["v6aplus_x_code"] == "V6P_ARITY"
   and _v1["executed_shape"] == _v1c["executed_shape"] == [0, 1],
   (_v1, _v1c))
# the systematic append-outer-WHERE sweep: 45 answer-bearing bases all reject;
# the 15 REFUSE certs carry no answer SQL, so the attack surface does not exist
SW = V6P4["sweep_append_outer_where"]
ck("append-outer-WHERE sweep: 45/45 answer-bearing reject, 15 REFUSE no-SQL",
   SW["n_total_bases"] == 60 and SW["n_answer_bearing"] == 45
   and SW["n_answer_bearing_reject"] == 45 and SW["answer_bearing_all_reject"]
   and SW["n_refuse_no_answer_sql"] == 15, SW)
# (2026-08-27) the sweep's 45/45 detail is TR-side and JSON-gated above; E5
# under the 12-page ceiling keeps the one-sentence gap disclosure + the F11
# family total, not the sweep digits (task item A: "one honest sentence").
# grand total 80 (family 78 + 2 pinned round-2 exploits); the family 78/78 is
# also asserted at the poststudy3 outcome ck above
ck("E5 states the grand total 80/80 (family 78 + 2 pinned round-2 exploits)",
   rf"${GRAND_FORGE}/{GRAND_FORGE}$" in EVAL, GRAND_FORGE)
ck("all four poststudy4 predictions hold with no misses",
   V6P4["all_predictions_hold"]
   and all(V6P4["predictions"][p]["holds"]
           and V6P4["predictions"][p]["misses"] == []
           for p in ("P1", "P2", "P3", "P4")), V6P4["predictions"])
# the gap sentence lives in E5; the two reason codes V6P_SHAPE / V6P_ARITY are
# named at their definition in S5 (asserted in the CERT block below), not
# duplicated into E5 under the page ceiling.
ck("E5 discloses the round-2 outer-filter gap in one honest sentence",
   "filtering the scalar answer to zero rows" in EVAL, "missing")
# genuine 60 still ACCEPT under both V6a+ and the new execution-shape check
ck("round-2: genuine 60 ACCEPT, 45 executed answers carry certified arity",
   V6P4["genuine60"]["accept"] == 60 and V6P4["genuine60"]["reject"] == 0
   and V6P4["genuine60"]["executed_arity_pass"] == 45
   and V6P4["genuine60"]["v6aplus_x_status"]["PASS"] == 45, V6P4["genuine60"])
# ---- S5: the check definition and the soundness rescope (Def 5.3 / 5.2(b)).
# NOT added to PROSE (the per-file headline loops would wrongly demand eval
# numbers there); read directly, like sections/05-rewrite.tex.
CERT = tex("sections/06-certificates.tex")
ck("S5 defines V6a+ as the eleventh check with the five structural faces",
   "conjunction of the eleven checks" in CERT and "V6a+" in CERT
   and "template membership for" in CERT
   and "implementing its registered" in CERT
   and "window equality" in CERT
   and "registered routing keys" in CERT
   and "fail-closed" in CERT, "missing")
ck("S5 rescopes Def 5.3 and (A-tmpl) onto V6a+",
   "V6a+ decides full membership" in CERT
   and "V6a+'s structural validation implies" in CERT, "missing")
# (2026-08-26, page pass) the four-mutation enumeration lives at the E5
# battery (asserted above); S5 keeps the provenance pointer -- review,
# date, and that the ORIGINAL V6a accepted the mutations.
ck("S5 carries the gap disclosure pointer with review provenance",
   "an external review (2026-08)" in CERT
   and "the original V6a accepted" in CERT, "missing")
# (2026-08-27, poststudy4 round 2) S5 states that V6a+ now ALSO decides
# outer-filter membership (rejects a non-null outer WHERE, V6P_SHAPE) AND
# checks executed arity (V6P_ARITY), and discloses the round-2 gap in one
# honest sentence.  The five round-1 faces asserted above stay; these are
# ADDED, not substituted -- Def 5.3 / Thm 5.2(b) are extended, not weakened.
ck("S5 states V6a+ decides outer-filter membership and checks executed arity",
   "outer-filter membership" in CERT
   and "executed arity" in CERT
   and r"V6P\_ARITY" in CERT, "missing")
ck("S5 discloses the round-2 outer-filter gap with its provenance",
   "a second external review (2026-08)" in CERT
   and "outer filter" in CERT.replace("-", " "), "missing")

# disclosure-gate first instances
ck("disclosure instances printed",
   re.search(r"three \\texttt\{DISCLOSURE-BLOCKED\}", EVAL)
   and "five granularity roll-ups" in EVAL
   and "two mask degradations" in EVAL, "missing")
ck("RC-7xRC-8 interaction printed", r"$10\to20$" in EVAL, "missing")
ck("version flips printed",
   r"$100.0$ vs.\ $252.0$" in EVAL and r"$0.1368\to0.0855$" in EVAL,
   "missing")

# ---------------------------------------------------------------- cost block
CA = COST["aggregate"]
CR = COST["per_certificate"]
sqlrows = [r for r in CR if r["sql_bytes"]]
ck("cost_p2: 60 certificates, 45 emitting SQL",
   len(CR) == 60 and len(sqlrows) == 45, (len(CR), len(sqlrows)))
ck("cost_p2: all 60 ACCEPT", CA["n_accept"] == 60, CA["n_accept"])


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


t_ratio = med([r["verify_warm_median_s"] / r["answer_warm_median_s"]
               for r in sqlrows])
b_ratio = med([r["cert_bytes_file"] / r["sql_bytes"] for r in sqlrows])
ck("cost: paired time multiplier agrees with aggregate",
   abs(t_ratio - CA["ratio_warm"]["median"]) < 1e-9, t_ratio)
T_MULT = f"{t_ratio:.1f}"                                    # 17.7
B_MULT = f"{b_ratio:.1f}"                                    # 10.2
ck("cost: no question cheaper to verify than answer",
   min(r["verify_warm_median_s"] / r["answer_warm_median_s"]
       for r in sqlrows) > 1.0, "a question verifies faster than it answers")
SPAN_LO = f"{min(r['verify_warm_median_s']/r['answer_warm_median_s'] for r in sqlrows):.1f}"
SPAN_HI = f"{max(r['verify_warm_median_s']/r['answer_warm_median_s'] for r in sqlrows):.1f}"
P90 = f"{CA['ratio_warm']['p90']:.1f}"
V_MED = f"{CA['verify_warm_s']['median']*1000:.1f}"          # 17.0
A_MED = f"{CA['answer_warm_s']['median']*1000:.2f}"          # 1.31
COLD_TOT = f"{CA['verify_cold_total_s']:.2f}"                # 7.60
COLD = [f"{CA['verify_cold_s'][k]*1000:.0f}" for k in ("median", "p90", "max")]
FLOOR = f"{CA['cold_process_floor_s']['median']*1000:.0f}"   # 53
REPEATS_COLD = str(COST["env"]["repeats_cold"])              # 5

for f_ in ("main.tex", "01-intro.tex", "08-eval.tex"):
    ck(f"{f_} carries the verify/answer multiplier {T_MULT}x",
       rf"median ${T_MULT}\times$" in PROSE[f_], "missing")
    ck(f"{f_} carries the byte multiplier {B_MULT}x",
       rf"${B_MULT}\times$" in PROSE[f_], "missing")
# (2026-08-07, R3-F2) The abstract no longer carries the absolute ms pair --
# 07.7 owns the marginal medians and the abstract keeps only the two
# multipliers.  This loop existed to keep the abstract and the body in sync on
# a number the abstract printed; with the number gone the sync obligation is
# gone with it, so main.tex leaves the loop.  The 08-eval assertion and the
# 12.9x ratio-of-medians companion below both stay, and the two multipliers are
# still asserted in main.tex by the loop above -- the abstract is not unpinned.
for f_ in ("08-eval.tex",):
    ck(f"{f_} carries the absolute pair {V_MED} vs {A_MED} ms",
       rf"${V_MED}$\,ms against ${A_MED}$\,ms" in PROSE[f_], "missing")
ck("the abstract no longer prints the absolute ms pair",
   rf"${V_MED}$\,ms" not in MAIN and rf"${A_MED}$\,ms" not in MAIN,
   "abstract still carries the marginal medians")
# (2026-08-07, R2-F6/TC-6+E-7) The prose also prints the quotient of the two
# MARGINAL medians, so a reader cannot divide 17.0 by 1.31, get 12.9 and think
# the paired median 17.7x is broken arithmetic.  cost_p2.json stores no such
# aggregate, so it is DERIVED from the two medians the same sentence prints --
# a tighter binding than a stored field would give.
RATIO_OF_MEDIANS = f"{CA['verify_warm_s']['median'] / CA['answer_warm_s']['median']:.1f}"
ck("eval carries the ratio-of-medians companion to the paired median",
   rf"quotient is ${RATIO_OF_MEDIANS}\times$" in EVAL, RATIO_OF_MEDIANS)
ck("the paired median and the ratio of medians are different numbers",
   RATIO_OF_MEDIANS != T_MULT, (RATIO_OF_MEDIANS, T_MULT))
ck("eval carries the per-question ratio span",
   rf"${SPAN_LO}\times$ to ${SPAN_HI}\times$" in EVAL
   and rf"p90 ${P90}\times$" in EVAL, f"{SPAN_LO}-{SPAN_HI}/{P90}")
ck("eval carries the cold figures",
   rf"${COLD_TOT}$\,s" in EVAL and f"median {COLD[0]}\\,ms" in EVAL
   and f"p90 {COLD[1]}\\,ms" in EVAL and f"max {COLD[2]}\\,ms" in EVAL
   and f"{FLOOR}\\,ms" in EVAL, "a cold figure is stale")
ck("eval declares the cold protocol",
   f"median of {REPEATS_COLD} processes per certificate" in EVAL, "missing")
# (2026-08-07, R3-FIX-17 = X-9/X-12/X-13, landed round 5) Three cost repairs
# that the round-3 and round-4 page budgets could not fund, all gated here:
#  (i)  the byte multiplier is measured on the PRETTY-PRINTED envelope; the
#       minified one is what a wire format would carry, so print both;
#  (ii) 7.60 s is the SUM of 60 per-certificate cold medians, not the wall
#       clock of one 60-process run -- the old "As 60 cold processes ... the
#       suite verifies in 7.60 s" invited the second reading;
#  (iii) only the scary WARM ratio was printed.  Cold, the same paired median
#       is 1.8x, because the per-process floor dominates.  Omitting it while
#       printing 17.7x is selective, so it is now printed and gated.
B_MULT_MIN = f"{med([r['cert_bytes_compact'] / r['sql_bytes'] for r in sqlrows]):.1f}"
ck("cost: the minified byte multiplier re-derives from the same 45 pairs",
   B_MULT_MIN == "8.4" and float(B_MULT_MIN) < float(B_MULT), B_MULT_MIN)
ck("eval prints both byte multipliers with their serialisations named",
   rf"${B_MULT}\times$ the query's bytes (pretty-printed; ${B_MULT_MIN}\times$"
   in EVAL, f"{B_MULT}/{B_MULT_MIN}")
COLD_MULT = f"{CA['ratio_cold']['median']:.1f}"              # 1.8
ck("cost: the cold paired median re-derives from the per-certificate rows",
   abs(med([r["verify_cold_median_s"] / r["answer_cold_median_s"]
            for r in sqlrows]) - CA["ratio_cold"]["median"]) < 1e-9
   and COLD_MULT == "1.8", COLD_MULT)
ck("eval prints the cold multiplier beside the warm one, not only the warm",
   rf"the paired median falls to ${COLD_MULT}\times$" in EVAL, COLD_MULT)
ck("eval states 7.60 s as a sum of per-certificate medians, not a wall clock",
   f"per-certificate cold medians (median of {REPEATS_COLD} processes per "
   f"certificate) sum to ${COLD_TOT}$" in EVAL
   and "As 60 cold processes" not in EVAL, COLD_TOT)
# (2026-08-06, W2/R1-E9 fallback taken under the 12.00-page ceiling): the
# absolute byte-medians parenthesis was DELETED from the prose rather than
# repaired -- the printed 2,600 was the all-60 aggregate median while the
# 10.2x ratio is the 45-question paired population (pair median 2,529).
# Only the derived paired RATIO is printed now, so no byte-median presence
# assertion remains; the mixed-population aggregate must not reappear.
ck("stale mixed-population byte median absent from prose",
   "2{,}600" not in EVAL, "the all-60 byte median resurfaced")
ck("cost: warm tail is the codebase cluster",
   max(CR, key=lambda r: r["verify_warm_median_s"])["cluster"]
   == "codebase_community", "tail moved")
ck("eval carries the warm tail", r"$0.18$\,s" in EVAL, "missing")
ck("cost: no symdiff full-scan instance on this base",
   all(r["symdiff_scan"] is None for r in CR)
   and r"\emph{no} instance here" in EVAL, "scan-class statement stale")
# R1-E5: the measurement-environment sentence is derived from COST["env"].
ENVSTR = (f"{COST['env']['cpu_count']}-core {COST['env']['machine']} "
          f"macOS 15 machine; Python {COST['env']['python']}, "
          f"DuckDB {COST['env']['duckdb']}")
ck("eval pins the cost environment from cost_p2.json env",
   COST["env"]["platform"].startswith("macOS-15") and ENVSTR in EVAL, ENVSTR)
# R1-F6: the JSON's own measurement notes must be derived from its
# aggregates (cold total seconds; refusal-certificate count), not hard-coded.
ck("cost notes derive from aggregates (cold total, n_refusal)",
   COLD_TOT in COST["measurement_notes"]["cold"]
   and str(CA["n_refusal"]) in COST["measurement_notes"]["answering_query"]
   and CA["n_refusal"] == 15,
   (COST["measurement_notes"]["cold"][-60:],
    COST["measurement_notes"]["answering_query"][-60:]))

# ------------------------------------------------------------ stale-number ban
STALE = {
    r"51-question": "old dual-track suite headline",
    r"\ball 51 questions\b": "old suite denominator",
    r"\$51/51\$": "old certificate count",
    r"\$16/16\$": "old forgery count",
    r"37\.3\\%": "old baseline range low",
    r"39\.2\\%": "old backbone rate",
    r"52\.9\\%": "old deepseek rate",
    r"68\.6\\%": "old baseline range high",
    r"45\.1": "old variant rate",
    r"49\.0\\%": "old variant rate",
    r"33\.3\\%": "old governance-arm rate",
    r"\$22\\times\$": "old time multiplier",
    r"\$29\\times\$": "old byte multiplier",
    r"\$6\.1\$\\,ms": "old verify median",
    r"\$0\.24\$\\,ms": "old answer median",
    r"17/31": "old enterprise split",
    r"PLACEHOLDER": "artifact URL placeholder",
}
for f_, txt in PROSE.items():
    for pat, why in STALE.items():
        ck(f"{f_} free of stale {pat!r}", not re.search(pat, txt), why)

# provenance guards: the production observation stays marked, results public
ck("intro marks the production observation",
   "production observation" in INTRO and r"16.2\%" in INTRO.replace("$", "")
   or re.search(r"16\.2\\%", INTRO), "production pair unmarked or missing")
ck("divergence caption carries its provenance note",
   "Provenance" in tex("tables/tab_divergence.tex")
   and "production" in tex("tables/tab_divergence.tex"), "missing")
ck("eval E6 keeps the ledger provenance framing",
   "recorded during" in EVAL and "no production data value" in
   tex("tables/tab_divergence.tex"), "missing")

# ==================================================================== R3 block
# (2026-08-07) Three numbers this file did not previously re-derive.  Each is
# added because its absence is exactly why an error shipped or a verdict was
# unsupported; the contract is unchanged -- no printed number may be
# un-re-derivable from the frozen artifacts.

# ---- leak-audit skip count (R3-X3).  The suite prose printed "22 shorter
# numeric gold literals"; the project's own frozen resume log records 23, and
# the 23rd is not numeric (CODE-Q6's two-character string "UK").  Replay
# run_pilot2_arms.py's A2 field list over the frozen questions.json rather than
# trusting either the log line or the prose.
LEAK_FIELDS = ("gold_sql", "windows", "windows_note", "notes", "rewrite",
               "refusal_reason", "gold_value")
skipped = []
CLUSTER_OF = {}
for _p in sorted(glob.glob(os.path.join(ROOT, "pilot2", "domains", "*",
                                        "questions.json"))):
    for _q in json.load(open(_p, encoding="utf-8")):
        CLUSTER_OF[_q["qid"]] = os.path.basename(os.path.dirname(_p))
        _f = {"gold_sql": _q.get("gold_sql"),
              "windows": None if _q.get("windows") is None
              else json.dumps(_q["windows"], ensure_ascii=False),
              "windows_note": _q.get("windows_note"), "notes": _q.get("notes"),
              "rewrite": None if _q.get("rewrite") is None
              else json.dumps(_q["rewrite"], ensure_ascii=False),
              "refusal_reason": _q.get("refusal_reason"),
              "gold_value": None if _q.get("gold_value") is None
              else str(_q["gold_value"])}
        assert tuple(_f) == LEAK_FIELDS
        for _k, _v in _f.items():
            if _v is None:
                continue
            _s = _v.strip() if isinstance(_v, str) else str(_v)
            if len(_s) < 8:
                skipped.append((_q["qid"], _k, _s))


def _numeric(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


N_SKIP = len(skipped)
N_SKIP_NUM = sum(1 for _, _, s in skipped if _numeric(s))
NON_NUM = [(q, k, s) for q, k, s in skipped if not _numeric(s)]
ck("leak-audit skip count re-derives from the frozen suite", N_SKIP == 23,
   f"replay gives {N_SKIP}")
ck("the skip set is 22 numeric plus one short string",
   N_SKIP_NUM == 22 and len(NON_NUM) == 1 and NON_NUM[0][2] == "UK", NON_NUM)
ck("eval prints the re-derived skip count and names the non-numeric literal",
   f"({N_SKIP} shorter gold literals" in EVAL
   and f"{N_SKIP_NUM} numeric plus the two-character string" in EVAL
   and r"\texttt{UK}" in EVAL, f"{N_SKIP}/{N_SKIP_NUM}")

# ---- context-dilution correlation (R3-X11).  The question-level point-biserial
# was the only statistic in the paper computed at a unit the cluster bootstrap
# does not use.  Both units are re-derived here from the frozen prompt pack and
# the frozen verdict matrix, so the printed pair cannot drift apart.
MANIFEST = json.load(open(os.path.join(ROOT, "pilot2", "prompt_pack",
                                       "MANIFEST.json"), encoding="utf-8"))
PLR = MANIFEST["prompt_len_range"][GOV]
GOV_RUNS = os.path.join(ROOT, "pilot2", "runs", GOV)
QLEN = {f[:-5]: json.load(open(os.path.join(GOV_RUNS, f),
                               encoding="utf-8"))["prompt_chars"]
        for f in os.listdir(GOV_RUNS)
        if f.endswith(".json") and not f.startswith("._")}
SPREAD = max(hi - lo for lo, hi in PLR.values())
ck("within-database package spread is what the prose claims", SPREAD == 80,
   f"max within-DB spread = {SPREAD}")
ck("the manifest ranges bound the per-question prompt lengths actually sent",
   all(PLR[CLUSTER_OF[q]][0] <= n <= PLR[CLUSTER_OF[q]][1]
       for q, n in QLEN.items()), "a cached prompt_chars is outside its range")


def _pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) ** 0.5
           * sum((b - my) ** 2 for b in ys) ** 0.5)
    return num / den


_qs = sorted(QLEN)
R_Q = _pearson([QLEN[q] for q in _qs],
               [0.0 if V[q][GOV] == "correct" else 1.0 for q in _qs])
_cl = sorted(PLR)
_pcg = S["slices"]["per_cluster"][GOV]
R_C = _pearson([(PLR[c][0] + PLR[c][1]) / 2 for c in _cl],
               [_pcg[c]["errors"] / _pcg[c]["n"] for c in _cl])
DF_C = len(_cl) - 2
T_C = R_C * (DF_C / (1 - R_C ** 2)) ** 0.5
ck("eval prints the question-level point-biserial it re-derives",
   f"$r={R_Q:.3f}$" in EVAL, f"{R_Q:.4f}")
ck("eval prints the cluster-unit correlation it re-derives",
   f"$r={R_C:.3f}$" in EVAL, f"{R_C:.4f}")
ck("eval prints the cluster-unit t and df it re-derives",
   f"$t={T_C:.2f}$" in EVAL and rf"$\mathrm{{df}}={DF_C}$" in EVAL,
   f"t={T_C:.4f}, df={DF_C}")
ck("the two units disagree, which is why both are printed",
   f"{R_Q:.3f}" != f"{R_C:.3f}" and R_C > R_Q, (R_Q, R_C))
ck("eval does not claim dilution excluded",
   "we do not claim dilution excluded" in EVAL
   and "cannot separate dilution from depth" in EVAL, "verdict not retracted")

# ==================================================================== R4 block
# (2026-08-07) The round-4 meta-review found the gates' blind spot: a printed
# sentence that carries no number and no red-lined substring can be simply
# FALSE and still sail through both checkers ("the only cluster where
# disclosure binds" -- codebase_community is not the only one).  Every round-4
# repair that replaced a claim with a countable fact is re-derived here, so the
# replacement is machine-checked rather than typed.

# ---- disclosure-policy row census (R4-X4-4).  The cluster parenthetical now
# prints a count, not a uniqueness claim.  Re-derive both halves from the
# frozen gov_disclosure_policy seeds.
POLICY_ROWS = {}
for _p in sorted(glob.glob(os.path.join(ROOT, "pilot2", "domains", "*",
                                        "gov_seed",
                                        "gov_disclosure_policy.jsonl"))):
    _dom = os.path.basename(os.path.dirname(os.path.dirname(_p)))
    POLICY_ROWS[_dom] = sum(
        1 for _l in open(_p, encoding="utf-8") if _l.strip())
POLICY_TOTAL = sum(POLICY_ROWS.values())
POLICY_CB = POLICY_ROWS.get("codebase_community", 0)
ck("disclosure policy rows total re-derives from the seeds", POLICY_TOTAL == 18,
   f"{POLICY_TOTAL} rows over {len(POLICY_ROWS)} domains: {POLICY_ROWS}")
ck("codebase_community's share of the policy rows re-derives", POLICY_CB == 8,
   f"{POLICY_CB}")
ck("more than one cluster carries policy rows, so no uniqueness may be printed",
   sum(1 for v in POLICY_ROWS.values() if v) == 4,
   {k: v for k, v in POLICY_ROWS.items() if v})
ck("eval prints the re-derived policy-row count, not a uniqueness claim",
   f"carrying {POLICY_CB} of the {POLICY_TOTAL} policy rows" in EVAL
   and "only cluster where disclosure binds" not in EVAL,
   "cluster parenthetical")

# ---- authored-row provenance split (R4-F1).  The setup printed one lump
# "20,094 authored rows" beside "zero synthetic", which let a reader carry the
# zero-synthetic scope across the whole suite; world_1's history is authored by
# formula.  Re-derive the split from the frozen provenance ledgers so the new
# parenthetical and the threats sentence cannot drift from it.
REAL_ROWS = AUTH_ROWS = 0
AUTHORED = {}
for _p in sorted(glob.glob(os.path.join(ROOT, "pilot2", "domains", "*",
                                        "provenance.json"))):
    _dom = os.path.basename(os.path.dirname(_p))
    for _t, _i in json.load(open(_p, encoding="utf-8"))["tables"].items():
        if _i.get("authored"):
            AUTH_ROWS += _i["rows"]
            AUTHORED[f"{_dom}.{_t}"] = _i["rows"]
        else:
            REAL_ROWS += _i["rows"]
W1_HIST = AUTHORED.get("world_1.country_history", 0)
ck("real fact rows re-derive from the provenance ledgers", REAL_ROWS == 3830036,
   f"{REAL_ROWS}")
ck("authored fact rows re-derive from the provenance ledgers",
   AUTH_ROWS == 20094, f"{AUTH_ROWS}: {AUTHORED}")
ck("world_1's authored history is the bulk of the authored rows",
   W1_HIST == 20076 and W1_HIST / AUTH_ROWS > 0.99, f"{W1_HIST}/{AUTH_ROWS}")
ck("eval prints the re-derived authored split beside the lump",
   f"{REAL_ROWS:,}".replace(",", "{,}") in EVAL
   and f"{AUTH_ROWS:,}".replace(",", "{,}") in EVAL
   and f"({W1_HIST:,}".replace(",", "{,}") + " of them" in EVAL,
   "8.1 authored-row parenthetical")
ck("the threats paragraph scopes 'shipped public data' away from world_1",
   r"shipped public data save \texttt{world\_1}'s authored history" in EVAL,
   "8.6 threats scope")

# ---- version-flip scoring concession (R4-X4-3 / R2-F10, landed round 5).
# S7.4 says the answer flips with the in-effect version, which is true of the
# GOLD values; what the 8.6 concession list now also discloses is that on one
# of the four pairs the flip is smaller than the scorer's own tolerance, so a
# version-blind answer is CREDITED there.  Both halves are re-derived: the
# per-pair relative difference from the frozen questions.json gold values, and
# REL_TOL from the frozen scorer block -- neither is typed into the paper.
FLIP_PAIRS = [("california_schools", "CA-Q1", "CA-Q2"),
              ("financial", "FIN-Q1", "FIN-Q2"),
              ("formula_1", "F1-Q1", "F1-Q2"),
              ("world_1", "W1-Q1", "W1-Q2")]          # RC-8, ACCEPTANCE S5
REL_TOL = S["scorer"]["REL_TOL"]
ck("the scorer's relative tolerance re-derives from the frozen scorer block",
   REL_TOL == 0.005, REL_TOL)


def _flip_reldiff(dom, qa, qb):
    g = {q["qid"]: q.get("gold_value") for q in json.load(
        open(os.path.join(ROOT, "pilot2", "domains", dom, "questions.json"),
             encoding="utf-8"))}
    a, b = g[qa], g[qb]
    # scored either way round, so the pair is inside tolerance only if BOTH
    # directions are -- take the max, which is the honest (conservative) read
    return max(abs(a - b) / abs(a), abs(a - b) / abs(b))


FLIP_RD = {d: _flip_reldiff(d, a, b) for d, a, b in FLIP_PAIRS}
INSIDE = sorted(d for d, r in FLIP_RD.items() if r <= REL_TOL)
ck("exactly one flip pair falls inside the scoring tolerance, and it is "
   "california_schools", INSIDE == ["california_schools"],
   {k: round(v, 6) for k, v in FLIP_RD.items()})
ck("the other three flip pairs are outside the tolerance by a wide margin",
   all(r > 10 * REL_TOL for d, r in FLIP_RD.items() if d not in INSIDE),
   {k: round(v, 6) for k, v in FLIP_RD.items() if k not in INSIDE})
CA_PCT = f"{FLIP_RD['california_schools'] * 100:.2f}"
TOL_PCT = f"{REL_TOL * 100:.1f}"
ck("the printed flip-tolerance concession carries the re-derived figures",
   rf"the two gold values differ by ${CA_PCT}\%$, inside" in EVAL
   and rf"the ${TOL_PCT}\%$ scoring tolerance" in EVAL
   and r"credits a version-blind answer" in EVAL,
   f"{CA_PCT}% against {TOL_PCT}%")
ck("the concession names the pair and does not overstate its extent",
   r"on one of the four version-flip pairs" in EVAL
   and r"(\texttt{california\_schools})" in EVAL, "8.6 concession scope")

# ---- prompt-variant sizes (R3-X11 = FIX-19a, landed round 5).  "Prompting
# does not close the gap" is only honest if the reader can see how small the
# prompts were.  Re-derive the three lengths from the FROZEN instruction
# constants in pilot/run_pilot.py (read with ast, never imported, so this gate
# cannot execute the harness).
import ast as _ast

_RP = _ast.parse(open(os.path.join(ROOT, "pilot", "run_pilot.py"),
                      encoding="utf-8").read())
_NOTES = {}
for _n in _RP.body:
    if isinstance(_n, _ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, _ast.Name) and _t.id.startswith("TRIVIAL"):
                _NOTES[_t.id] = len(_ast.literal_eval(_n.value))
_VLENS = [_NOTES["TRIVIAL_NOTE"], _NOTES["TRIVIAL_V2_NOTE"],
          _NOTES["TRIVIAL_V3_NOTE"]]
ck("the three prompt-variant instruction lengths re-derive from the frozen "
   "constants", _VLENS == [115, 226, 187], _NOTES)
ck("eval prints the variant lengths in the order the variants are named",
   "a worked example (${}$, ${}$ and ${}$ characters)".format(*_VLENS)
   in EVAL, _VLENS)
ck("the E1--E2 heading and the takeaway both scope prompting to one line",
   "One-Line Prompting Does Not Close It" in EVAL
   and "one-line prompting (E2)" in EVAL, "prompting scope")
ck("the threats list owns the prompt-technique breadth limit",
   "prompt technique is one line deep" in EVAL
   and "no decomposition, self-consistency, in-domain" in EVAL,
   "prompt-technique breadth")

# ---- cluster-gradient regressions (R3-X6 = FIX-14, landed round 5).  The
# gradient sentence listed only the clusters that REPAIR; two regress, and
# they are the third- and fourth-longest packages, which is the whole point of
# printing them.  Re-derive both the counts and the length rank.
PCVR = S["governance_informed_arm"]["per_cluster_vs_reference"]
for _c, _b, _g in [("financial", 4, 1), ("debit_card_specializing", 3, 1),
                   ("world_1", 2, 1), ("card_games", 2, 4),
                   ("european_football_2", 2, 4)]:
    ck(f"cluster {_c} moves {_b}->{_g} against the reference arm",
       (PCVR[_c]["baseline_claude_errors"], PCVR[_c]["errors"]) == (_b, _g),
       PCVR[_c])
_PKG = {}
for _p in sorted(glob.glob(os.path.join(ROOT, "pilot2", "runs",
                                        "governance_informed", "*.json"))):
    _r = json.load(open(_p, encoding="utf-8"))
    _dom = qs[_r["qid"]]["domain"]
    _PKG[_dom] = max(_PKG.get(_dom, 0), _r["prompt_chars"])
_RANK = [d for _, d in sorted(((v, k) for k, v in _PKG.items()), reverse=True)]
ck("the two regressing clusters are the 3rd- and 4th-longest packages",
   set(_RANK[2:4]) == {"european_football_2", "card_games"}, _RANK[:5])
ck("eval prints the two regressions with their package rank",
   r"\texttt{card\_games} and \texttt{european\_football\_2} each regress "
   r"$2\to4$" in EVAL and "third- and fourth-longest packages" in EVAL,
   "cluster-gradient regressions")

# ---- probe-7 vs registry-5 length confound (R4-X4-2, landed round 5).
# S7.3(a)/(b) contrast two question sets that are NOT length-matched, so the
# depth story and the dilution story are entangled in the very contrast that
# carries the depth claim.  The disclosure now prints both means; re-derive
# them from the frozen governance_informed response caches (prompt_chars is
# written by run_pilot2_arms.py at call time, so this is the same number the
# arm actually saw).
def _mean_prompt_chars(qids):
    vs = [json.load(open(os.path.join(ROOT, "pilot2", "runs",
                                      "governance_informed", q + ".json"),
                         encoding="utf-8"))["prompt_chars"] for q in qids]
    return sum(vs) / len(vs)


P7_CHARS = _mean_prompt_chars(PROBE7)
M5_CHARS = _mean_prompt_chars(MD5)
ck("the probe-7 and registry-5 prompt-length means re-derive from the caches",
   round(P7_CHARS) == 24594 and round(M5_CHARS) == 20287,
   f"{P7_CHARS:.1f} vs {M5_CHARS:.1f}")
ck("the two sets really are not length-matched (>15% apart)",
   P7_CHARS / M5_CHARS > 1.15, f"{P7_CHARS / M5_CHARS:.4f}")
ck("eval prints the re-derived means with the entanglement caveat",
   f"means ${P7_CHARS / 1000:.1f}$k vs ${M5_CHARS / 1000:.1f}$k characters"
   in EVAL and "not length-matched" in EVAL
   and "dilution/depth entanglement" in EVAL,
   f"{P7_CHARS / 1000:.1f}k vs {M5_CHARS / 1000:.1f}k")

# ============================================================ poststudy block
# (2026-08-20) Three post-registered studies shipped in
# pilot2/poststudy_20260820/ under PREREG_poststudy_20260820.md (sha256
# asserted below, on-disk bytes, not a quoted constant): S1 leave-one-cluster-
# out over the frozen verdict matrix, S2 governance-blind temporal-SQL arms
# (deterministic, zero LLM), S3 a five-repetition rerun of the two headline
# arms.  The body added two passages from them -- the S8 temporal-SQL sentence
# and the S7 threats extensions -- and every number those passages print is
# re-derived here from the shipped study JSONs; the S1 fold matrix is
# additionally recomputed from the same per-question verdict matrix V the rest
# of this file already gates, so the study cannot drift from the paper's own
# source of truth.
import hashlib

PS = os.path.join(ROOT, "pilot2", "poststudy_20260820")
PREREG_PS_SHA = ("f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde"
                 "07889bb31c68dd4ac8aace24")
_ps_sha = hashlib.sha256(open(os.path.join(
    PS, "PREREG_poststudy_20260820.md"), "rb").read()).hexdigest()
ck("poststudy PREREG on disk hashes to its frozen sha256",
   _ps_sha == PREREG_PS_SHA, _ps_sha)
ck("poststudy FREEZE file records that same sha256",
   PREREG_PS_SHA in open(os.path.join(PS, "FREEZE_poststudy.sha256"),
                         encoding="utf-8").read(), "FREEZE drift")
S1J = json.load(open(os.path.join(PS, "s1", "loco_report.json"),
                     encoding="utf-8"))
S2J = json.load(open(os.path.join(PS, "s2", "tsql_summary.json"),
                     encoding="utf-8"))
S3J = json.load(open(os.path.join(PS, "s3", "s3_summary.json"),
                     encoding="utf-8"))
ck("all three study JSONs pin the poststudy PREREG sha",
   S1J["prereg_sha256"] == S2J["prereg"]["sha256"] == S3J["prereg_sha256"]
   == PREREG_PS_SHA, "a study ran under a different pre-registration")
RELATED = tex("sections/09-related.tex")   # NOT in PROSE, same reason as S5:
# the per-file headline loops above assert eval numbers in every PROSE member,
# which S8 neither carries nor should.  Referenced directly here.

# ---- S1: leave-one-cluster-out (deterministic, zero LLM) -------------------
# The fold matrix is recomputed cell-by-cell from V + the frozen suite, then
# the printed threats sentence is asserted.  The 0.40 floor is parsed out of
# the frozen S1-P1 statement, not typed here.
ck("S1 covers the nine clusters with one fold each",
   sorted(S1J["loco_folds"]) == sorted(per_dom_real), sorted(S1J["loco_folds"]))
ck("S1 arms are the paper's nine arms", S1J["arms"] == ROWS, S1J["arms"])
for _dom, _fold in sorted(S1J["loco_folds"].items()):
    _kept = [q for q in QIDS if CLUSTER_OF[q] != _dom]
    ck(f"S1 fold {_dom} re-derives from the frozen verdict matrix",
       _fold["n_questions_kept"] == len(_kept)
       and _fold["n_questions_left_out"] == 60 - len(_kept)
       and all(_fold["error_count"][a] == errors(a, _kept) for a in ROWS)
       and all(abs(_fold["error_rate"][a] - errors(a, _kept) / len(_kept))
               < 1e-12 for a in ROWS), _dom)
_m = re.search(r">=\s*([\d.]+)", S1J["predictions"]["S1-P1"]["statement"])
ck("S1-P1 floor parses from the frozen prediction statement",
   _m is not None and _m.group(1) == "0.40", _m and _m.group(1))
LOCO_FLOOR = float(_m.group(1)) if _m else None
_minplain = min(f["error_rate"][s]
                for f in S1J["loco_folds"].values() for s in PLAIN)
ck("every fold keeps every plain baseline at or above the printed floor",
   LOCO_FLOOR is not None and _minplain >= LOCO_FLOOR,
   f"min plain fold error {_minplain:.4f} vs floor {LOCO_FLOOR}")
ck("governance sits below all four plain baselines in every fold",
   all(f["error_rate"][GOV] < min(f["error_rate"][s] for s in PLAIN)
       for f in S1J["loco_folds"].values()), "an ordering flipped")
ck("the compiler errs 0 in every fold",
   all(f["error_count"]["mechanism"] == 0
       for f in S1J["loco_folds"].values()), "mechanism nonzero")
ck("S1's own pre-registered verdicts are MET with no violation recorded",
   S1J["predictions"]["S1-P1"]["verdict"] == "MET"
   and S1J["predictions"]["S1-P2"]["verdict"] == "MET"
   and S1J["predictions"]["S1-P1"]["violations"] == []
   and S1J["predictions"]["S1-P2"]["violations_gov_vs_plain"] == []
   and S1J["predictions"]["S1-P2"]["violations_mechanism_nonzero"] == [],
   S1J["predictions"])
ck("threats print the LOCO fact with the parsed floor",
   "leave-one-cluster-out moves no ordering" in EVAL
   and rf"each plain baseline's error ${{\geq}}{LOCO_FLOOR:.2f}$" in EVAL
   and "governance below all four, the compiler at $0$" in EVAL, "missing")

# ---- S3: five-repetition rerun of the two headline arms --------------------
ck("S3 is five reps of the two headline arms on the frozen 60",
   S3J["reps"] == [1, 2, 3, 4, 5] and S3J["arms"] == [BACKBONE, GOV]
   and S3J["n_questions"] == 60, (S3J["reps"], S3J["arms"]))
ck("S3 rep1 is the frozen main-study run, re-asserted not re-run",
   "frozen main-study caches" in S3J["rep1_source"]
   and S3J["per_arm"][BACKBONE]["per_rep"]["1"]["errors"] == errors(BACKBONE)
   and S3J["per_arm"][GOV]["per_rep"]["1"]["errors"] == errors(GOV),
   S3J["rep1_source"])
_oc = S3J["ordering_check"]["per_rep"]
ck("the reference-governance ordering holds in all five reps, recomputed",
   len(_oc) == 5 and S3J["ordering_check"]["all_reps_pass"]
   and all(S3J["per_arm"][BACKBONE]["per_rep"][r]["errors"]
           > S3J["per_arm"][GOV]["per_rep"][r]["errors"]
           and _oc[r]["baseline_claude_errors"]
           == S3J["per_arm"][BACKBONE]["per_rep"][r]["errors"]
           and _oc[r]["governance_informed_errors"]
           == S3J["per_arm"][GOV]["per_rep"][r]["errors"]
           for r in "12345"), _oc)
_flip = {a: S3J["per_arm"][a]["pooled_flip"] for a in (BACKBONE, GOV)}
for _a, _f in _flip.items():
    ck(f"S3 pooled flip rate for {_a} is n_flips/60 with the qids to match",
       len(_f["flip_qids"]) == _f["n_flips"]
       and abs(_f["flip_rate"] - _f["n_flips"] / 60) < 1e-12, _f)
FLIP_MAX = max(_f["flip_rate"] for _f in _flip.values())
ck("the printed 13.3% is the larger per-arm flip rate (gov 8/60; ref 4/60)",
   f"{100 * FLIP_MAX:.1f}" == "13.3" and _flip[GOV]["n_flips"] == 8
   and _flip[BACKBONE]["n_flips"] == 4, _flip)
ck("no S3 prediction missed (S3-P1..P4 pass, miss count 0)",
   S3J["n_predictions_missed"] == 0
   and all(S3J["predictions"][p]["pass"]
           for p in ("S3-P1", "S3-P2", "S3-P3", "S3-P4")),
   S3J["n_predictions_missed"])
ck("threats print the repetition fact",
   "\\emph{One sample per question is the protocol}: five reps of both "
   "headline arms (rep\\,1 the frozen run) hold the ordering in all five"
   in EVAL and rf"flips ${{\leq}}{100 * FLIP_MAX:.1f}\%$ per arm" in EVAL,
   "missing")
# the retouched hull-trim parenthetical now prints the gov value split; gate
# it here since the old wording carried it un-derived.
_gval = S["slices"]["per_gold_form"][GOV]["value"]
ck("threats value-errors parenthetical is the gov arm's 11/33 value split",
   (_gval["errors"], _gval["n"]) == (11, 33)
   and f"value errors {_gval['errors']}/{_gval['n']} even with those freebies"
   in EVAL, _gval)

# ---- S2: governance-blind temporal-SQL arms (deterministic, zero LLM) ------
# Both pre-declared scoring readings are gated; the S8 sentence prints the
# frozen-literal one AND the NULL-credit one, so neither can be cherry-picked.
TSQLW = S2J["arms"]["TSQL-W"]
TSQLH = S2J["arms"]["TSQL-H"]
WA = TSQLW["readings"]["null_as_error"]
WB = TSQLW["readings"]["null_as_refusal_credit"]
ck("S2 ran import-disjoint from the compiler and verifier",
   S2J["import_disjointness"].startswith("IMPORT-DISJOINTNESS OK"),
   S2J["import_disjointness"][:60])
ck("TSQL-W answers 60/60 with zero refusal declarations",
   TSQLW["answered_60_of_60_no_refusal_declaration"]
   and TSQLW["refusal_declarations"] == 0, "the arm refused")
ck("TSQL-W errs 28/60 under the frozen-literal reading, qids to match",
   WA["error_count"] == 28 and len(WA["error_qids"]) == 28
   and abs(WA["error_rate"] - 28 / 60) < 1e-12, WA["error_count"])
ck("28/60 is level with the governance-informed arm, recomputed from V",
   WA["error_count"] == errors(GOV) == 28,
   (WA["error_count"], errors(GOV)))
ck("all 15 refusal-gold questions are answered (15/15 err, literal reading)",
   WA["by_form"]["refusal"] == {"n": 15, "errors": 15}
   and kinds["refusal"] == 15, WA["by_form"]["refusal"])
ck("TSQL-W form split stacks to its total (6+7+15=28)",
   (WA["by_form"]["value"]["errors"], WA["by_form"]["rewrite"]["errors"],
    WA["by_form"]["refusal"]["errors"]) == (6, 7, 15)
   and sum(v["errors"] for v in WA["by_form"].values())
   == WA["error_count"], WA["by_form"])
ck("TSQL-W value split is 6/33 under BOTH readings",
   WA["by_form"]["value"] == WB["by_form"]["value"] == {"n": 33, "errors": 6}
   and kinds["value"] == 33, WA["by_form"]["value"])
NULLS = TSQLW["bare_null_qids"]
ck("the five bare NULLs all fall on refusal-gold questions",
   len(NULLS) == 5 and set(NULLS)
   == set(TSQLW["bare_null_on_refusal_gold_qids"])
   and all(qs[q]["expected_kind"] == "refusal" for q in NULLS), NULLS)
ck("crediting them as refusals gives the alternate 23/60, arithmetic intact",
   WB["error_count"] == 23 == WA["error_count"] - len(NULLS)
   and len(WB["error_qids"]) == 23
   and WB["by_form"]["refusal"] == {"n": 15, "errors": 10}, WB["error_count"])
ck("TSQL-H all-history errs 54/60 under both readings (no NULL to credit)",
   TSQLH["readings"]["null_as_error"]["error_count"] == 54
   == TSQLH["readings"]["null_as_refusal_credit"]["error_count"]
   and TSQLH["bare_null_qids"] == [], "all-history reading moved")
_NWORD = {5: "five"}[len(NULLS)]
ck("S8 prints the temporal-SQL measurement, post-registered, TR-cited",
   "is a point in the compiler's design space minus the refusal classes and "
   "the certificate. Post-registered, we built one~\\cite{asofgov-tr}"
   in RELATED
   and "it errs $28/60$ --- level with the governance-informed arm --- all "
   "15 refusals answered" in RELATED, "S8 sentence lost")
ck("S8 prints the NULL-credit alternate reading beside the literal one",
   f"($23/60$ crediting its {_NWORD} bare \\texttt{{NULL}}s)" in RELATED,
   "alternate reading missing")
ck("S8 prints the all-history twin and the value-split verdict",
   "an all-history twin errs $54/60$" in RELATED
   and "values $6/33$ --- the data axis is not the bottleneck" in RELATED,
   "missing")
# (2026-08-23, R4-1-3) The S2 arms must be visible to a reader of the
# evaluation section alone, not only in S8: the threats paragraph now
# prints all four headline numbers, re-derived here from the same study
# JSON so neither copy can drift from the evidence or from the other.
ck("threats print the S2 governance-blind temporal-SQL sentence (S7 copy)",
   "\\emph{Nor does governance-blind temporal-SQL close it}: post-registered"
   in EVAL
   and f"hand-built arms err ${WA['error_count']}/60$ same-window --- "
   "level with the governance-informed arm" in EVAL,
   "S7 temporal-SQL sentence lost")
ck("the S7 copy prints the NULL-credit alternate beside the literal one",
   f"${WB['error_count']}/60$ crediting {_NWORD} bare "
   "\\texttt{NULL}s as refusals" in EVAL,
   "S7 alternate reading missing")
ck("the S7 copy prints the all-history twin and the value split",
   f"${TSQLH['readings']['null_as_error']['error_count']}/60$ all-history"
   in EVAL
   and (f"values ${WA['by_form']['value']['errors']}"
        f"/{WA['by_form']['value']['n']}$ under both readings") in EVAL,
   "S7 twin or value split missing")

# =========================================================== poststudy2 block
# (2026-08-23, battery 2) Four more post-registered studies shipped in
# pilot2/poststudy2_20260823/ under PREREG_poststudy2_20260823.md (sha256
# asserted below, on-disk bytes, not a quoted constant): S4 paired-difference
# uncertainty over the frozen verdict matrix (deterministic, zero LLM), S5 a
# cost-model scalability sweep (deterministic; it ships with a DISCLOSED
# provenance correction of a corrupted 62-char prereg-sha citation, so the
# corrected 64-char value is asserted here and a regression fails), S6 an
# English-question control of the two headline arms, and S7 an NL->sigma
# extraction arm.  The body added two threat-item upgrades from them --- the
# cross-lingual item now prints the measured English control in place of the
# old "cannot separate language from form" concession, and the input-modality
# item prints the NL->sigma end-to-end error --- and every number those
# passages print is re-derived here from the shipped study JSONs; the frozen
# ZH anchors and reference points are additionally recomputed from the same
# per-question verdict matrix V the rest of this file already gates.
PS2 = os.path.join(ROOT, "pilot2", "poststudy2_20260823")
PREREG_PS2_SHA = ("838a214fc5a09902703d969c839872ff"
                  "843f190e9f2e1c9f6902f231e061c669")
_ps2_sha = hashlib.sha256(open(os.path.join(
    PS2, "PREREG_poststudy2_20260823.md"), "rb").read()).hexdigest()
ck("poststudy2 PREREG on disk hashes to its frozen sha256",
   _ps2_sha == PREREG_PS2_SHA, _ps2_sha)
ck("poststudy2 FREEZE file records that same sha256",
   PREREG_PS2_SHA in open(os.path.join(PS2, "FREEZE_poststudy2.sha256"),
                          encoding="utf-8").read(), "FREEZE drift")
S4J = json.load(open(os.path.join(PS2, "s4", "s4_summary.json"),
                     encoding="utf-8"))
S5J = json.load(open(os.path.join(PS2, "s5", "s5_cost_sweep.json"),
                     encoding="utf-8"))
S6J = json.load(open(os.path.join(PS2, "s6", "s6_summary.json"),
                     encoding="utf-8"))
S7J = json.load(open(os.path.join(PS2, "s7", "s7_summary.json"),
                     encoding="utf-8"))
S7L = json.load(open(os.path.join(PS2, "s7", "s7_ledger.json"),
                     encoding="utf-8"))
ck("all four study JSONs (and the S7 ledger) pin the poststudy2 PREREG sha",
   S4J["prereg_sha256"] == S6J["prereg_sha256"] == S7J["prereg_sha256"]
   == S7L["prereg_sha256"] == S5J["prereg"]["sha256"] == PREREG_PS2_SHA,
   "a study ran under a different pre-registration")

# ---- S5: the provenance correction is applied, disclosed, and cannot revert
ck("S5 sweep carries the corrected 64-hex prereg sha in BOTH cited fields",
   S5J["prereg"]["sha256"] == S5J["substrates_manifest"]["prereg_sha256"]
   == PREREG_PS2_SHA and len(PREREG_PS2_SHA) == 64,
   (S5J["prereg"]["sha256"], S5J["substrates_manifest"]["prereg_sha256"]))
_pc = S5J["provenance_correction"]["defect"]
ck("S5 provenance_correction discloses the corrupted->correct sha pair",
   _pc["correct_value"] == PREREG_PS2_SHA
   and len(_pc["corrupted_value"]) == 62
   and _pc["corrupted_value"] != PREREG_PS2_SHA
   and _pc["dropped_chars"] == "1c", _pc)

# ---- S4: paired-difference restatement (anchors; no body number prints yet)
_s4gov = S4J["paired_differences"]["governance_informed"]
ck("S4 reference/arm error counts equal the frozen verdict matrix, n=60",
   _s4gov["errors_reference"] == errors(BACKBONE)
   and _s4gov["errors_arm"] == errors(GOV)
   and _s4gov["n_questions"] == 60,
   (_s4gov["errors_reference"], _s4gov["errors_arm"]))
ck("S4 publishes its two prediction misses (P1, P2 MISS; P3 MET)",
   S4J["n_predictions_missed"] == 2
   and S4J["predictions"]["S4-P1"]["verdict"] == "MISS"
   and S4J["predictions"]["S4-P2"]["verdict"] == "MISS"
   and S4J["predictions"]["S4-P3"]["verdict"] == "MET",
   {k: v["verdict"] for k, v in S4J["predictions"].items()})
ck("S4 trivial_v3 is the one variant whose CI excludes zero, harmful side",
   S4J["paired_differences"]["trivial_v3"]["ci_excludes_zero"]
   and S4J["paired_differences"]["trivial_v3"]["ci95_percentile"][1] < 0
   and not any(S4J["paired_differences"][a]["ci_excludes_zero"]
               for a in ("governance_informed", "trivial_claude",
                         "trivial_v2")),
   {a: v["ci95_percentile"]
    for a, v in S4J["paired_differences"].items()})

# ---- S6: English-question control (the cross-lingual threat upgrade) -------
_enq_sha = hashlib.sha256(open(os.path.join(
    PS2, "s6", "questions_en.json"), "rb").read()).hexdigest()
ck("S6 frozen questions_en on disk matches its FREEZE file and study JSON",
   _enq_sha == S6J["questions_en_sha256"]
   and _enq_sha in open(os.path.join(PS2, "s6", "FREEZE_questions_en.sha256"),
                        encoding="utf-8").read(), _enq_sha)
EN_B = S6J["error_counts_en"][BACKBONE]
EN_G = S6J["error_counts_en"][GOV]
ZH_B = S6J["zh_anchors_frozen"]["error_counts"][BACKBONE]
ZH_G = S6J["zh_anchors_frozen"]["error_counts"][GOV]
ck("S6 ZH anchors equal the frozen verdict matrix, recomputed from V",
   ZH_B == errors(BACKBONE) and ZH_G == errors(GOV), (ZH_B, ZH_G))
ck("S6 EN run is 2 arms x 60 with zero empty responses",
   S6J["n_questions"] == 60
   and S6J["empty_responses"][BACKBONE] == 0
   and S6J["empty_responses"][GOV] == 0, S6J["empty_responses"])
ck("S6 EN error counts agree with their taxonomy complements",
   EN_B == 60 - S6J["taxonomy_en"][BACKBONE]["correct"]
   and EN_G == 60 - S6J["taxonomy_en"][GOV]["correct"], (EN_B, EN_G))
ck("each headline arm moves by exactly one question, EN against ZH",
   abs(EN_B - ZH_B) == 1 and abs(EN_G - ZH_G) == 1,
   (EN_B, ZH_B, EN_G, ZH_G))
ck("the reference-governance ordering persists in English",
   EN_B > EN_G, (EN_B, EN_G))
ck("S6 probe-7 set equals the frozen PROBE7 list; concentration persists "
   "(EN gov errs 5 of 7 against ZH 6 of 7), verdicts recounted",
   set(S6J["probe7"]["qids"])
   == set(A["governance_informed_arm"]["probe7_metadata_undecidable"])
   and len(S6J["probe7"]["qids"]) == 7
   and S6J["probe7"]["en_governance_errors"] == 5
   == sum(v != "correct"
          for v in S6J["probe7"]["en_governance_verdicts"].values())
   and S6J["probe7"]["zh_governance_errors"] == 6
   == sum(v != "correct"
          for v in S6J["probe7"]["zh_governance_verdicts"].values())
   and S6J["probe7"]["en_governance_errors"] > 7 // 2, S6J["probe7"])
ck("no S6 prediction missed (S6-P1..P4 all met)",
   all(S6J["predictions"][p]["met"]
       for p in ("S6-P1", "S6-P2", "S6-P3", "S6-P4")), S6J["predictions"])
ck("threats print the measured English control with all four counts, "
   "JSON-derived",
   "a post-registered English run of both headline arms moves each arm one "
   f"question (${EN_B}/60$, ${EN_G}/60$ against ${ZH_B}/60$, ${ZH_G}/60$)"
   in EVAL
   and "ordering and probe-side concentration intact~\\cite{asofgov-tr}"
   in EVAL
   and "language does not drive the gap" in EVAL, "missing")
ck("the superseded no-English-control concession is retired from the body",
   "absent a same-protocol English-question control" not in EVAL
   and "cannot separate language from form" not in EVAL
   and "reads as a Chinese-question result" not in EVAL, "stale concession")

# ---- S7: NL->sigma arm (the input-modality threat upgrade) -----------------
ck("S7 headline: e2e error 5/60 with complement 55, exact full-sigma 40/60",
   S7J["n"] == 60 and S7J["end_to_end_error"] == 5
   and S7J["end_to_end_correct"] == 55
   and S7J["end_to_end_error"] + S7J["end_to_end_correct"] == S7J["n"]
   and S7J["exact_full_sigma"] == 40,
   (S7J["end_to_end_error"], S7J["exact_full_sigma"]))
ck("S7 ledger recount matches the summary on the frozen 60 qids",
   sorted(r["qid"] for r in S7L["ledger"]) == QIDS
   and sum(r["verdict"] == "error" for r in S7L["ledger"])
   == S7J["end_to_end_error"]
   and sum(bool(r["exact_full_sigma"]) for r in S7L["ledger"])
   == S7J["exact_full_sigma"], len(S7L["ledger"]))
ck("S7 exact-sigma questions carry zero end-to-end errors (P3 witness empty)",
   S7J["exact_sigma_and_wrong"] == []
   and not any(r["verdict"] == "error" for r in S7L["ledger"]
               if r["exact_full_sigma"]), S7J["exact_sigma_and_wrong"])
ck("S7 reference points equal the frozen verdict matrix, recomputed from V",
   S7J["reference_points"]["governance_informed_error_frozen"] == errors(GOV)
   and S7J["reference_points"]["backbone_error_frozen"] == errors(BACKBONE),
   S7J["reference_points"])
ck("no S7 prediction missed (S7-P1..P4 all met)",
   all(S7J["predictions"][p]["met"]
       for p in ("S7-P1", "S7-P2", "S7-P3", "S7-P4")), S7J["predictions"])
ck("threats print the NL->sigma measurement, JSON-derived, TR-cited",
   "a post-registered arm that extracts $\\sigma$ from the question text "
   "and hands it to the compiler errs "
   f"${S7J['end_to_end_error']}/60$~\\cite{{asofgov-tr}}" in EVAL
   and "recovering $\\sigma$ is not where the difficulty lives" in EVAL,
   "missing")
# (2026-08-26, D-visibility) The E-takeaway promotes the same hybrid; its
# count derives from the same S7 summary so the two copies cannot drift.
ck("E-takeaway promotes the NL->sigma hybrid with the derived count",
   f"NL-to-$\\sigma$ hybrid errs ${S7J['end_to_end_error']}/60$" in EVAL,
   "missing")

# =========================================================== poststudy3 block
# (2026-08-26, verifier hardening V6a+) One post-registered study shipped in
# pilot2/poststudy3_20260826/ under PREREG_poststudy3_20260826.md (sha256
# asserted below, on-disk bytes, not a quoted constant): the response to an
# external review that exhibited V6a-accepted mutations of a genuine
# certificate.  Every forgery-count and V6a+ assertion above derives from
# the study's summary JSON (V6P, loaded at the top); this block pins the
# provenance chain -- PREREG bytes, FREEZE record, the summary's own sha
# citation, and the hardened verifier files the summary certifies, hashed
# on disk against the recorded values so the shipped code cannot drift from
# the study that validated it.
PS3 = os.path.join(ROOT, "pilot2", "poststudy3_20260826")
PREREG_PS3_SHA = ("426017ddfd8af8608e452b44175e2158"
                  "c620c2e8cebe3a17572ee3fe15d7a192")
_ps3_sha = hashlib.sha256(open(os.path.join(
    PS3, "PREREG_poststudy3_20260826.md"), "rb").read()).hexdigest()
ck("poststudy3 PREREG on disk hashes to its frozen sha256",
   _ps3_sha == PREREG_PS3_SHA, _ps3_sha)
ck("poststudy3 FREEZE file records that same sha256",
   PREREG_PS3_SHA in open(os.path.join(PS3, "FREEZE_poststudy3.sha256"),
                          encoding="utf-8").read(), "FREEZE drift")
ck("v6aplus summary pins the poststudy3 PREREG sha",
   V6P["prereg"]["sha256"] == PREREG_PS3_SHA, V6P["prereg"]["sha256"])
# (2026-08-27, poststudy4 supersession) The round-1 V6a+ files this study
# recorded were themselves hardened in ROUND 2 (outer-filter closure +
# execution-shape check), so the SHIPPED impl/asof_verifier/ tree no longer
# hashes to poststudy3's recorded values -- it hashes to the poststudy4
# files_A values, pinned live against the on-disk tree in the poststudy4 block
# below.  This is a SUPERSESSION, not a weakened pin: the shipped code is
# hashed HARDER below (both working trees, byte-identical, all four files),
# and this study's own recorded hashes stay asserted for internal consistency
# (its summary JSON is frozen evidence).  The per-file live-hash loop that
# used to live here therefore MOVED to the poststudy4 block; the four-file
# structural pin stays here.
ck("the poststudy3 summary records exactly the four hardening-relevant files",
   set(V6P["verifier"]["files"])
   == {"chk.py", "v6aplus.py", "forge_v6aplus.py", "ci_check.py"},
   sorted(V6P["verifier"]["files"]))
ck("poststudy3 recorded hashes differ from the shipped round-2 tree (proof "
   "the code moved on, superseded not silently mutated)",
   V6P["verifier"]["files"] != V6P4["verifier"]["files_A"], "hashes coincide")

# =========================================================== poststudy4 block
# (2026-08-27, verifier hardening V6a+ ROUND 2) The second post-registered
# study shipped in pilot2/poststudy4_20260827/ under
# PREREG_poststudy4_20260827.md (sha256 asserted below from on-disk bytes):
# the response to a second external review that exhibited an outer-row-filter
# gap (a genuine ratio/delta whose OUTER SELECT filters the scalar answer to
# 0 rows) V6a+ still ACCEPTed.  Every F11 / round-2 / grand-total assertion
# above derives from this study's summary JSON (V6P4, loaded at the top); this
# block pins the provenance chain -- PREREG bytes, FREEZE record, the summary's
# own sha citation, and the round-2 hardened verifier files (both working trees
# byte-identical), hashed on disk so the shipped code cannot drift from the
# study that validated it.
PS4 = os.path.join(ROOT, "pilot2", "poststudy4_20260827")
PREREG_PS4_SHA = ("a7ff13112c6988e98fceb238972a0ae0f"
                  "ff87a037b9f9630577fc618c04b1a75")
_ps4_sha = hashlib.sha256(open(os.path.join(
    PS4, "PREREG_poststudy4_20260827.md"), "rb").read()).hexdigest()
ck("poststudy4 PREREG on disk hashes to its frozen sha256",
   _ps4_sha == PREREG_PS4_SHA, _ps4_sha)
ck("poststudy4 FREEZE file records that same sha256",
   PREREG_PS4_SHA in open(os.path.join(PS4, "FREEZE_poststudy4.sha256"),
                          encoding="utf-8").read(), "FREEZE drift")
ck("v6aplus v4 summary pins the poststudy4 PREREG sha",
   V6P4["prereg"]["sha256"] == PREREG_PS4_SHA, V6P4["prereg"]["sha256"])
for _fn, _want in sorted(V6P4["verifier"]["files_A"].items()):
    _got = hashlib.sha256(open(os.path.join(
        ROOT, "impl", "asof_verifier", _fn), "rb").read()).hexdigest()
    ck(f"shipped verifier file {_fn} hashes to the poststudy4 files_A sha256",
       _got == _want, _got)
ck("poststudy4 certifies the four files, both trees byte-identical",
   set(V6P4["verifier"]["files_A"])
   == {"chk.py", "v6aplus.py", "forge_v6aplus.py", "ci_check.py"}
   and V6P4["verifier"]["files_A"] == V6P4["verifier"]["files_B"]
   and V6P4["verifier"]["trees_byte_identical"] is True,
   sorted(V6P4["verifier"]["files_A"]))
# the round-2 study's own inputs are hash-pinned in the summary; re-verify a
# couple of the answer-bearing ledgers on disk so the copied study cannot drift
for _fn in ("genuine60_verdicts.json", "exploits_run.json", "sweep_run.json"):
    _got = hashlib.sha256(open(os.path.join(
        PS4, "results", _fn), "rb").read()).hexdigest()
    ck(f"poststudy4 input {_fn} hashes to the summary-recorded value",
       _got == V6P4["inputs"][_fn], _got)

# ========================================================== M2 block
# (2026-08-26, M2 honest uncertainty) The elimination verdict now prints,
# in the abstract, at the E3 case-(iii) verdict, and in S9, the frozen-run
# scope beside the five-repetition span and the paired nine-cluster CI.
# Every printed number derives here from the s3/s4 summary JSONs; the span
# is cross-derived from S3J's per-rep eliminations and S4J's restatement,
# and rep 1 is re-anchored to the same elim_gov this file derives from the
# frozen verdict matrix.
ER = S4J["elimination_restatement"]
_fr5 = [S3J["elimination_governance_informed"]["per_rep"][r]
        ["eliminated_frac"] for r in "12345"]
ck("five-rep elimination fractions agree across S3 and S4; rep1 = 13/36",
   [ER["per_rep"][r]["eliminated_frac"] for r in "12345"] == _fr5
   and abs(_fr5[0] - elim_gov / 36) < 1e-12
   and ER["reasserted_equal_to_frozen_s3_summary"], _fr5)
SPAN_LO3, SPAN_HI3 = f"{min(_fr5):.3f}", f"{max(_fr5):.3f}"
ck("the span is 0.361-0.417, in the prereg band, straddling the 0.40 line",
   (SPAN_LO3, SPAN_HI3) == ("0.361", "0.417")
   and ER["prereg_line"] == 0.40 and ER["range_straddles_line"]
   and min(_fr5) < ER["prereg_line"] < max(_fr5)
   and ER["all_in_band"] and S4J["predictions"]["S4-P3"]["met"],
   (SPAN_LO3, SPAN_HI3))
_ci9 = S4J["paired_differences"]["governance_informed"]["ci95_percentile"]
CI_STR = f"[{_ci9[0]:.2f},{_ci9[1]:.2f}]"
ck("the paired nine-cluster CI formats as [-0.05,0.30] and includes zero",
   CI_STR == "[-0.05,0.30]" and _ci9[0] < 0 < _ci9[1]
   and not S4J["paired_differences"]["governance_informed"]
   ["ci_excludes_zero"], CI_STR)
ck("abstract prints the frozen-run verdict with span and CI",
   ("the frozen run does not cross the pre-registered $40\\%$ elimination "
    "line") in MAIN
   and f"five repetitions span {SPAN_LO3}--{SPAN_HI3}" in MAIN
   and f"${CI_STR}$" in MAIN, "abstract lost the M2 form")
ck("E3 case-(iii) verdict carries the span and CI, TR-cited",
   f"elimination spans ${SPAN_LO3}$--${SPAN_HI3}$" in EVAL
   and "straddling the $0.40$ line" in EVAL
   and f"${CI_STR}$" in EVAL
   and "ordering stable in all five" in EVAL, "missing")
ck("the all-five ordering claim is S3's ordering check, re-asserted",
   S3J["ordering_check"]["all_reps_pass"]
   and all(S3J["ordering_check"]["per_rep"][r]["baseline_gt_governance"]
           for r in "12345"), "ordering broke")
ck("E3 claim wording is frozen-run-scoped",
   "the frozen run does not substantially eliminate the" in EVAL, "missing")
# (the span+CI print in the abstract and at the E3 verdict; S9 keeps the
# frozen-run scope with the line's-edge pointer, funding the page budget)
ck("S9 scopes the verdict to the frozen run, pointing at the E3 numbers",
   "the frozen run yields no substantial elimination" in CONCL
   and "at the line's edge" in CONCL, "missing")

# ============================================== template-restoration block
# (2026-08-26) main.tex dropped the route-C spacing block and the
# \@BAlancecol patch; the paper typesets on template defaults.  Guard the
# restoration so a later pass cannot quietly re-introduce glue overrides,
# and pin the slimmed divergence summary's content beside its audit.  The
# guard runs on COMMENT-STRIPPED source: the restoration note may name the
# removed macros, live code may not.  The \@BAlancecol balance.sty fix is
# the one documented exception and it FIRED: the template-default build
# emitted the references-page `Overfull \vbox (1.13pt) ... while \output
# is active' (the package's height-only column sizing), so the patch is
# re-added ALONE per the exception and asserted PRESENT here -- it is a
# package-bug correctness fix, not a spacing override, and every route-C
# glue item below stays banned.
MAIN_CODE = re.sub(r"\s+", " ",
                   re.sub(r"(?<!\\)%.*", "", rawfile("main.tex")))
for _pat, _why in ((r"\\microtypesetup", "protrusion raise"),
                   (r"\\captionsetup", "caption gap"),
                   (r"\\setlength\\textfloatsep", "float gap"),
                   (r"\\setlength\\aboverulesep", "booktabs padding"),
                   (r"\\renewcommand\\smallskip", "smallskip lead"),
                   (r"thm@preskip", "theorem surround")):
    ck(f"main.tex stays template-pristine: no {_why}",
       not re.search(_pat, MAIN_CODE), _pat)
ck("main.tex keeps the balance.sty ht+dp fix (documented exception; the "
   "references-page overfull vbox resurfaced without it)",
   re.search(r"\\@BAlancecol", MAIN_CODE) is not None
   and "max(ht+dp)" in MAIN, "the balance fix or its justification is gone")
DTEX = tex("tables/tab_divergence.tex")
ck("slimmed divergence table prints the class counts and total",
   r"all 15: 5 S $\cdot$ 3+2 D $\cdot$ 5 R" in DTEX
   and r"(25 rejections $\to$ 15 causes)" in DTEX
   and r"$0/15$" in DTEX, "missing")
ck("slimmed divergence table prints one exemplar per class + TR pointer",
   "$D_{1}$" in DTEX and "$D_{7}$" in DTEX and "$D_{4}$" in DTEX
   and r"in~\cite{asofgov-tr}" in DTEX, "missing")
DAUD = json.load(open(os.path.join(PAPER, "tables",
                                   "tab_divergence.audit.json")))
ck("divergence audit still ships all 15 rows with the printed-rows note",
   len(DAUD["rows"]) == 15 and DAUD["printed_rows"] == ["D1", "D7", "D4"]
   and [r["id"] for r in DAUD["rows"]] == [f"D{i}" for i in range(1, 16)],
   (len(DAUD.get("rows", [])), DAUD.get("printed_rows")))
# (2026-08-26, D-visibility) S8 restores the schema-evolution delineation
# without citing removed papers.
ck("S8 delineates schema-version rewriting from governance re-scoping",
   r"query rewriting across \emph{schema}" in RELATED
   and "re-scopes governed meaning over unchanged rows" in RELATED
   and "typed refusal has no counterpart" in RELATED, "missing")

# ---------------------------------------------------------------- report
print(f"four-place number check (public base): {checks} assertions, "
      f"{len(fails)} failed")
for f_ in fails:
    print("  FAIL " + f_)
sys.exit(1 if fails else 0)
