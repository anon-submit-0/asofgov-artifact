#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic generator for Table F-C -- the D1--D15 divergence ledger (E5).

  Usage:  python3 tools/gen_table_divergence.py            # writes tables/tab_divergence.tex
          python3 tools/gen_table_divergence.py --check    # verify only, write nothing

WHY A GENERATOR AND NOT A HAND-WRITTEN TABLE.  Every cell that carries a fact
is read out of, or asserted against, the artifact:

  * columns "Divergence", "Cls" and "Right" are PARSED, row by row, out of the
    15-row markdown table in impl/INTEGRATION_REPORT.md section 5.  The parse
    is asserted: 15 rows, ids D1..D15 in order, class counts 5/5/5, side counts
    as recorded there.  If that table is edited, this script fails loudly
    instead of silently printing stale content.
  * column "Check" is the verifier check that fired.  For D6/D7/D8 it was
    MEASURED (see the A/B below); for the others it is the per-family label of
    the corresponding section-2 subsection of the same report, recorded here
    with its provenance string and re-asserted against the report text.
  * column "Value gold?" is uniformly "missed"; the per-row REASON code is an
    editorial judgement, recorded with its evidence, and the headline case is
    measured rather than asserted.

THE MEASUREMENT BEHIND THE LAST COLUMN (re-runnable, read-only, ~40 s):

  1. cp -R impl/asof_compiler <scratch>/asof_compiler
  2. revert the three compiler-side defects in the copy:
       D6  adapters._bound_pred          -> `return legacy_pred` unconditionally
       D7  adapters.NxAdapter.intent     -> drop `and tpl["kind"] == "ratio"` so an
                                            atomic metric again cites the borrowed
                                            binding row model_mismatch_rate_align
       D8  adapters aibuy den_probe      -> upper bound as
                                            `recorded_at < (DATE 'd' + INTERVAL 1 DAY)`
  3. python3 <scratch>/asof_compiler/acceptance.py --pilot pilot --certs <scratch>/certs
  4. per-question: python3 impl/asof_verifier/chk.py --cert <scratch>/certs/<qid>.json ...

  RESULT, defects in place:
      value-level gold ..................... 51/51   PASS
      compiler well-formedness self-check ... 0 errors
      deployed-compiler equivalence ........ 51/51   PASS  (sql_bytes_equal 37)
      independent re-derivation ............ 39/51   -- 12 REJECT
        D6 -> V6a on EMAIL-ASOF-01/02/04, NX-Q1/Q2/Q3/Q5, AIBUY-Q1/Q2/Q4  (10)
             ("time predicate denotation [-inf, hi) not subset of certified window")
        D7 -> V3  on NX-Q4
             ("binding row 'model_mismatch_rate_align' governs metric
               'model_mismatch_rate', not q.metric 'product_versions_valid_asof'")
        D8 -> V6b on AIBUY-Q6
             ("MC(ii) probe: probe window denotation [-inf, +inf) not subset of
               certified window [-inf, 2026-06-01)")
  RESULT, current tree: gold 51/51, self-check 0, re-derivation 51/51 ACCEPT.

  Section 2.2 of the report labels the D6 family with 7 questions; that is the
  FIRST-ROUND count.  The blast radius measured above is 10, because AIBUY-Q1/
  Q2/Q4 were first rejected upstream (V0, V4) and their V6a exposure surfaces
  only once those are closed.  The table prints the traceable 7; this note is
  the honest correction and is reproduced in the caption's artifact pointer.

  Independent corroboration of the same blindness, no reverting required: the
  DEPLOYED per-domain compilers (pilot/domains/*/compiler.py, pilot/public/
  compiler.py), which emit no certificate at all, also score 51/51 on the same
  value-level gold (37 numeric comparisons + 14 refusal-token comparisons).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PAPER = HERE.parent
ROOT = PAPER.parent
REPORT = ROOT / "impl" / "INTEGRATION_REPORT.md"
OUT_TEX = PAPER / "tables" / "tab_divergence.tex"
OUT_AUDIT = PAPER / "tables" / "tab_divergence.audit.json"

# --------------------------------------------------------------------------
# Editorial layer.  One entry per row; keyed by the id parsed out of section 5.
#   short   : the disagreement, <=45 chars at \scriptsize in a 241pt column
#   check   : verifier check(s) that fired
#   chk_src : provenance for `check`
#   gold    : reason code for the last column (a/b/c/d, see CAPTION)
#   gold_why: provenance / argument for that code
# --------------------------------------------------------------------------
EDIT = {
 "D1": dict(short=r"coverage domain gates before $\MC$?",
            check="V6b", chk_src="report 2.4 family label [V6b x2] (AIBUY-Q6)",
            gold="d",
            gold_why="compiler emitted MC(ii) = frozen gold label; the verifier's "
                     "literal hull reading says OOV. Gold passes the compiler, so it "
                     "surfaces nothing -- but report 2.4/4 record that the gold label "
                     "is what adjudicated the reading (DEVIATION-1)."),
 "D2": dict(short=r"$\beta_v$ defined when both legs are NULL?",
            check="V6b", chk_src="report 2.4 family label [V6b x2] (AIBUY-Q5)",
            gold="c",
            gold_why="report 2.4 calls the AIBUY-Q5 half a verifier defect; the "
                     "gold suite (acceptance.py) runs the compiler only."),
 "D3": dict(short="prescribed anchor of an atomic metric",
            check="V0", chk_src="report 2.1 family label [V0 x3] (AIBUY-Q1/Q2/Q3)",
            gold="b",
            gold_why="the anchor was correct; it lived in compiler.BINDINGS instead "
                     "of A_v. Same SQL, same value; gold never asks where the "
                     "compiler's knowledge came from."),
 "D4": dict(short="must a ratio carry a caliber route?",
            check="V4, V6c", chk_src="report 2.3 family label [V4/V6c x1] (AIBUY-Q4)",
            gold="b",
            gold_why="AIBUY-Q4 answered with the right value throughout; rho is a "
                     "certificate/registry field the value gold does not read."),
 "D5": dict(short=r"is \texttt{avg\_handle\_hours} a ratio?",
            check="V3", chk_src="report 2.6 family label [V3 x2] (QVOC-03)",
            gold="d",
            gold_why="the verifier's reading would refuse MC(i); the frozen gold is a "
                     "VALUE question (93.264444), so the gold label is what settles it. "
                     "The compiler passed via a declared deviation, so gold flagged nothing."),
 "D6": dict(short=r"must a rewrite emit $w^*$'s lower bound?",
            check="V6a", chk_src="MEASURED (A/B, see module docstring) + report 2.2 [V6a x7]",
            gold="a",
            gold_why="MEASURED: with the defect reverted, gold 51/51 and deployed-compiler "
                     "equivalence 51/51 while 10 questions' SQL text differs -- no earlier "
                     "rows exist below the cut, so the value is identical either way."),
 "D7": dict(short="may an atom borrow another's binding row?",
            check="V3", chk_src="MEASURED (A/B) + report 2.6 [V3 x2] (NX-Q4)",
            gold="b",
            gold_why="MEASURED: gold 51/51 with the defect in place. NX-Q4's SQL has no "
                     "window predicate at all and its anchor comes from the template, so "
                     "no choice of binding row can move the value; the lie is confined to "
                     "the certificate's beta_v claim."),
 "D8": dict(short="probe bound: arithmetic or literal window",
            check="V6b", chk_src="MEASURED (A/B): V6b 'MC(ii) probe: probe window "
                                 "denotation ... certified window' on AIBUY-Q6",
            gold="b",
            gold_why="MEASURED: gold 51/51 with the defect in place. The probe SQL is "
                     "certificate content; both spellings count the same rows, so the "
                     "refusal token -- all the gold compares on a refusal question -- "
                     "is unchanged."),
 "D9": dict(short="does a month marker denote the month?",
            check="V6c", chk_src="report 2.7 family label [V6c x1] (QVOC-03 probe)",
            gold="c",
            gold_why="report 2.7 calls the verifier over-strict; the compiler was right. "
                     "The gold suite never runs the verifier."),
 "D10": dict(short="is a derived-table alias a read object?",
             check="V6a", chk_src="report 2.8 family label [V6a x2] (rma_q3)",
             gold="c",
             gold_why="verifier-side SQL block decomposition; nothing about the "
                      "compiler's output changes."),
 "D11": dict(short="does a conformed-dim join leave closure?",
             check="V6a", chk_src="report 2.8 family label [V6a x2] (rma_q4)",
             gold="b",
             gold_why="rma_q4 returns gold 42.0 either way; what was missing is the "
                      "dimension_of edge in G_v, which the value gold does not read."),
 "D12": dict(short="replay of the interval-anchor predicate",
             check=r"V6a$^{\dagger}$",
             chk_src="report 2.9 crash item: NX-Q4's V6a raised NameError "
                     "(scd2_point_predicate never defined); verify()'s try counted it "
                     "as a failure rather than a silent pass",
             gold="c",
             gold_why="a function missing from the verifier; the compiler's output is "
                      "untouched."),
 "D13": dict(short=r"where the re-anchoring $\bar a$ is carried",
             check="V0", chk_src="report 2.5 family label [V0 x6] (EMAIL-ASOF-05, NX-Q6)",
             gold="b",
             gold_why="both are value questions and both answered correctly; the "
                      "disagreement is whether abar may live only in the question's prose "
                      "plus a certificate self-record -- neither is read by the gold."),
 "D14": dict(short=r"how a delta question presents $\vec\omega$",
             check="V0", chk_src="report 2.5 family label [V0 x6] (period-expansion rows)",
             gold="b",
             gold_why="the compiler expanded the period sequence internally and computed "
                      "the right values; the gap is in sigma's presentation layer. Report 3 "
                      "records that the spec patch touched only windows/params, never "
                      "as_of/metric/gold_sql/gold_value/refusal_reason."),
 "D15": dict(short="certificate spelling of an unreg. anchor",
             check="V0 (V2)", chk_src="report 2.5 companion note: cert_alpha accepts both "
                                      "spellings, V2 re-checks the declaration (NX-Q6)",
             gold="b",
             gold_why="a certificate schema question that section 6.2 leaves open; the "
                      "value gold reads no certificate field."),
}

CLASS_TEX = {"S": "S", "Dc": r"D$_{\mathrm{c}}$", "Dv": r"D$_{\mathrm{v}}$", "R": "R"}
# the last column prints its own reason, so the caption needs no code legend
GOLD_TEX = {"a": "value", "b": "cert", "c": "verif.", "d": "label"}
SIDE_TEX = {"compiler": "comp.", "verifier": "verif.", "spec": "spec", "either": "either"}


# --------------------------------------------------------------------------
def parse_section5(text: str) -> list[dict]:
    """Parse the 15-row divergence table out of section 5 of the report."""
    m = re.search(r"^## 5\..*?$(.*?)^## 6\.", text, re.S | re.M)
    if not m:
        sys.exit("FATAL: section 5 of INTEGRATION_REPORT.md not found")
    body = m.group(1)
    rows = []
    for line in body.split("\n"):
        if not line.startswith("| D") or "---" in line[:6]:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            sys.exit(f"FATAL: expected 7 cells, got {len(cells)}: {line[:90]}")
        did, point, c_read, v_read, right, cls, landing = cells

        if "规范理解分歧" in cls:
            k = "S"
        elif "实现缺陷" in cls:
            k = "Dc" if "编译器侧" in cls else "Dv"
        elif "数据登记缺口" in cls:
            k = "R"
        else:
            sys.exit(f"FATAL: unrecognised class cell for {did}: {cls!r}")

        if right.startswith("规范"):
            s = "spec"
        elif right.startswith("校验器"):
            s = "verifier"
        elif right.startswith("编译器"):
            s = "compiler"
        elif right.startswith("两侧皆可"):
            s = "either"
        else:
            sys.exit(f"FATAL: unrecognised side cell for {did}: {right!r}")

        rows.append(dict(id=did, point=re.sub(r"\*\*", "", point), cls=k, side=s,
                         compiler_reading=c_read, verifier_reading=v_read,
                         landing=landing, raw=line.strip()))
    return rows


def assert_invariants(rows: list[dict], text: str) -> None:
    ids = [r["id"] for r in rows]
    assert ids == [f"D{i}" for i in range(1, 16)], f"row ids are {ids}"
    cls = {k: sum(1 for r in rows if r["cls"] == k) for k in ("S", "Dc", "Dv", "R")}
    assert cls == {"S": 5, "Dc": 3, "Dv": 2, "R": 5}, f"class counts are {cls}"
    # the report states these counts in prose right below the table; re-read them
    # rather than trusting our own parse.
    assert "［规范理解分歧］5（D1/D2/D9/D13/D15）" in text
    assert "［实现缺陷］5（D6/D7/D8/D10/D12，其中编译器侧 3、校验器侧 2）" in text
    assert "［数据登记缺口］5（D3/D4/D5/D11/D14）" in text
    # 25 first-round rejections must reconstruct from the section-2 family labels
    fam = {"[V0 ×3]": 3, "[V6a ×7]": 7, "[V4/V6c ×1]": 1, "[V6b ×2]": 2,
           "[V0 ×6 / V3 ×1]": 7, "[V3 ×2]": 2, "[V6c ×1]": 1, "[V6a ×2]": 2}
    for label in fam:
        assert label in text, f"section-2 family label {label} not found in the report"
    assert sum(fam.values()) == 25, "family labels no longer sum to 25"
    assert "ACCEPT 51/51**（起点 26/51）" in text, "the 26/51 starting point moved"
    assert set(EDIT) == set(f"D{i}" for i in range(1, 16))


# ---------------------------------------------------------------------------
# SLIMMED 2026-08-26 (template-restoration funding; see paper/main.tex and the
# sections/08-eval.tex red-line note of the same date).  The emitted table is
# now a SUMMARY: per-root-cause-class counts plus the three most instructive
# rows; the full 15-row ledger, both readings per row, stays in the TR
# (asof-gov-tr.pdf carries every row and both readings), in
# impl/INTEGRATION_REPORT.md section 5 (source of record), and in
# tab_divergence.audit.json, which this generator still writes with ALL 15
# rows and their evidence.  parse_section5/assert_invariants are UNCHANGED:
# the generator still parses and asserts the full ledger before printing
# anything, so a stale or edited report still fails loudly.
#
# THE THREE EXEMPLARS are the rows the E6 lessons quote, one per class:
#   D1 (S)  guard order settled by the frozen gold label -- the row the
#           suite's frozen guard-order adjudications descend from;
#   D7 (Dc) compiler defect returning the RIGHT answer under a
#           non-re-derivable certificate claim -- the "value gold catches
#           none of this" lesson in one row;
#   D4 (R)  a ratio's caliber route missing from the registry -- the
#           registration-gap lesson (checkability measures governedness).
# The choice is pinned here and asserted one-per-class below.
# ---------------------------------------------------------------------------
EXEMPLARS = ("D1", "D7", "D4")

CAPTION = r"""The two implementations' first cross-check: root-cause
counts plus the three rows the \S\ref{sec:eval-divergence} lessons quote
(full D1--D15 ledger, both readings per row:~\cite{asofgov-tr}).
\emph{Provenance}: recorded during the two sides' integration on the
production (enterprise) track, before the public suite existed ---
specification-level content, no production data value.
\emph{Cls}: S~spec-reading, D$_{\mathrm{c/v}}$~defect
(compiler/verifier side), R~registration gap; \emph{Right}: the side the
frozen text vindicated; \emph{Check}: the check that fired.
\emph{Value gold?}: the 51-question value-level gold fails on \emph{no}
row --- the lie sits in the \emph{cert}ificate/registry gold never reads,
or the gold \emph{label} itself settled the reading."""


def emit(rows: list[dict]) -> str:
    by_id = {r["id"]: r for r in rows}
    # the exemplar pick is pinned above; assert it is one row per class so a
    # future edit cannot quietly bias the sample toward one root cause.
    assert [by_id[x]["cls"] for x in EXEMPLARS] == ["S", "Dc", "R"], \
        [by_id[x]["cls"] for x in EXEMPLARS]
    L = []
    A = L.append
    A("% ---------------------------------------------------------------------")
    A("%  Table F-C -- D1-D15 divergence SUMMARY.  GENERATED FILE, DO NOT EDIT.")
    A("%  Regenerate:  python3 tools/gen_table_divergence.py")
    A("%  Source of record: impl/INTEGRATION_REPORT.md section 5 (15-row table)")
    A("%  and section 2 (per-family check labels).  tools/gen_table_divergence.py")
    A("%  parses that table, asserts 15 rows / 5+5+5 / the 25-rejection family")
    A("%  decomposition, and fails rather than print stale content.  SLIMMED")
    A("%  2026-08-26: the emitted table prints per-class counts + the three")
    A("%  exemplar rows the E6 lessons quote; the full ledger stays in the TR,")
    A("%  the report, and tab_divergence.audit.json (all 15 rows, unchanged).")
    A("%  The verifier column's headline case is MEASURED, not asserted: see")
    A("%  the A/B recipe in the generator's module docstring.")
    A("%  Macros used (\\MC, \\beta_v ...) are \\providecommand'd in 03-semantics.")
    A("% ---------------------------------------------------------------------")
    A(r"\begin{table}[t]")
    A(r"\centering")
    A(r"\scriptsize")
    A(r"\setlength{\tabcolsep}{2.0pt}")
    A(r"\renewcommand{\arraystretch}{0.93}")
    A(r"\caption{" + CAPTION + "}")
    A(r"\label{tab:divergence}")
    A(r"\begin{tabular}{@{}lccll@{}}")
    A(r"\toprule")
    A(r"Divergence & Cls & Right & Check & Value\\")
    A(r" & & & fired & gold?\\")
    A(r"\midrule")
    for rid in EXEMPLARS:
        r = by_id[rid]
        e = EDIT[rid]
        num = rid[1:]
        A(f"$D_{{{num}}}$ {e['short']} & {CLASS_TEX[r['cls']]} & {SIDE_TEX[r['side']]}"
          f" & {e['check']} & " + r"\ding{55}\," + GOLD_TEX[e["gold"]] + r"\\")
    A(r"\midrule")
    n = len(rows)
    nS = sum(1 for r in rows if r["cls"] == "S")
    nDc = sum(1 for r in rows if r["cls"] == "Dc")
    nDv = sum(1 for r in rows if r["cls"] == "Dv")
    nR = sum(1 for r in rows if r["cls"] == "R")
    rem = [r for r in rows if r["id"] not in EXEMPLARS]
    rS = sum(1 for r in rem if r["cls"] == "S")
    rDc = sum(1 for r in rem if r["cls"] == "Dc")
    rDv = sum(1 for r in rem if r["cls"] == "Dv")
    rR = sum(1 for r in rem if r["cls"] == "R")
    A(r"\multicolumn{4}{@{}l}{" + f"the other {len(rem)}: {rS} S $\\cdot$ "
      + f"{rDc}+{rDv} D $\\cdot$ {rR} R, rows in~\\cite{{asofgov-tr}}}}"
      + r" & \ding{55}\,$0/" + str(len(rem)) + r"$\\")
    A(r"\multicolumn{4}{@{}l}{" + f"all {n}: {nS} S $\\cdot$ {nDc}+{nDv} D "
      + f"$\\cdot$ {nR} R"
      + r"\ \ (25 rejections $\to$ " + str(n) + r" causes)} & \ding{55}\,$0/"
      + str(n) + r"$\\")
    A(r"\bottomrule")
    A(r"\end{tabular}")
    A(r"\end{table}")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = ap.parse_args()

    text = REPORT.read_text(encoding="utf-8")
    rows = parse_section5(text)
    assert_invariants(rows, text)

    tex = emit(rows)
    audit = {
        # Repo-relative, never absolute: this file is committed to the public
        # artifact, and an absolute path both leaks the author's directory
        # layout and makes the audit differ between a working-tree run and an
        # in-artifact run of reproduce_all.sh (the file is generated in both).
        "source_of_record": str(REPORT.relative_to(ROOT)),
        "source_section": "5 (15-row table) + 2 (per-family check labels)",
        "printed_rows": list(EXEMPLARS),
        "printed_rows_note": "2026-08-26 slimming: the body table prints "
                             "per-class counts plus these three exemplar "
                             "rows (one per root-cause class, the rows the "
                             "E6 lessons quote); this audit and the TR keep "
                             "all 15 rows.",
        "rows": [{"id": r["id"],
                  "section5_line": r["raw"],
                  "point_zh": r["point"],
                  "class": r["cls"], "right": r["side"],
                  "printed_short": EDIT[r["id"]]["short"],
                  "check": EDIT[r["id"]]["check"],
                  "check_provenance": EDIT[r["id"]]["chk_src"],
                  "gold_code": EDIT[r["id"]]["gold"],
                  "gold_evidence": EDIT[r["id"]]["gold_why"]} for r in rows],
        "measured_ab": {
            "prefix_gold_match": "51/51",
            "prefix_wellformed_errors": 0,
            "prefix_legacy_regression": "51/51 (sql_bytes_equal=37)",
            "prefix_independent_accept": "39/51",
            "prefix_rejected": ["AIBUY-Q1", "AIBUY-Q2", "AIBUY-Q4", "AIBUY-Q6",
                                "NX-Q1", "NX-Q2", "NX-Q3", "NX-Q4", "NX-Q5",
                                "EMAIL-ASOF-01", "EMAIL-ASOF-02", "EMAIL-ASOF-04"],
            "current_gold_match": "51/51",
            "current_independent_accept": "51/51",
            "deployed_certificate_free_gold": "51/51 (37 numeric + 14 refusal-token)",
        },
    }
    if args.check:
        print(f"OK: parsed {len(rows)} rows from section 5; invariants hold.")
        return 0
    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_TEX.write_text(tex, encoding="utf-8")
    OUT_AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT_TEX}  ({len(rows)} rows)")
    print(f"wrote {OUT_AUDIT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
