#!/usr/bin/env python3
"""Red-line presence check.

PUBLIC-BASE EDITION (2026-08-04).  Each section file's header comment names
content that no compression pass may remove.  This script asserts every one
of those items is still present, so a page-budget cut cannot quietly eat a
load-bearing number, a mandatory block or a fairness disclosure.  It is a
presence test, not a correctness test --- the numbers themselves are checked
by tools/check_numbers.py (also public-base edition).

Superseded red lines are retired here WITH a dated note rather than silently
dropped, because a presence check that pins a false sentence is worse than
no check:
  - "disclosure layer has zero instances" (old base): FALSE on pilot2 ---
    the layer is exercised (3 blocked / 5 roll-ups / 2 masks); replaced by
    the exercised-instances lines below.
  - "version axis unexercised / never exercised" (old base): FALSE on
    pilot2 (two committed versions per DB, four flip pairs); replaced by
    the version-axis-exercised lines plus the three still-unexercised
    defence paths.
  - the old 51/51 + 16/16 + 22x/29x numbers: superseded by 60/60 + 34/34 +
    17.7x/10.2x; the old strings are BANNED by check_numbers.py's stale
    list rather than required here.  (The forgery total in this note read
    30/30 until 2026-08-10, when family F5 took the battery to 34 over 11
    bases, and the battery grew again to 70 on 2026-08-26 with the
    poststudy3 V6a+ hardening; the live pin is the "E: 60/60 certificates"
    entry below, not this comment.)
  - 2026-08-26 (M2 honest uncertainty + template restoration), all per the
    relocated-to-TR protocol with the full content preserved in the TR and
    the frozen artifacts: the in-body S5.2 per-prediction digits, the
    case-(iii) denominator sensitivity clause, and the full 15-row
    D1-D15 table each compressed in body and relocated; every affected
    entry below carries its own dated note, the surviving compressed form
    is re-pinned, and the new five-rep span + paired-CI content is pinned
    as "M2: ..." -- no value assertion was weakened (check_numbers.py
    still derives and scores every relocated number).

Exit code 0 iff every red line is present.  Usage: python3 tools/check_redlines.py
"""
import os
import re
import sys

PAPER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel):
    return re.sub(r"\s+", " ",
                  open(os.path.join(PAPER, rel), encoding="utf-8").read())


F = {r: load(r) for r in [
    "main.tex", "sections/01-intro.tex", "sections/03-semantics.tex",
    "sections/04-binding.tex", "sections/05-rewrite.tex",
    "sections/06-certificates.tex", "sections/07-system.tex",
    "sections/08-eval.tex", "sections/09-related.tex",
    "sections/10-conclusion.tex", "tables/tab_divergence.tex"]}
ALL = " ".join(F.values())

# (label, file-or-None-for-anywhere, list of substrings/regexes that must appear)
RED = [
 # ---- 08-eval.tex: the evaluation's declared red lines ---------------------
 ("E: answered/refused shares beside every rate", "sections/08-eval.tex",
  [r"Ans\.", r"Ref\.", r"sits beside its answered/refused shares"]),
 ("E: true denominator of 60 stated", "sections/08-eval.tex",
  [r"true denominator of 60", r"all 60 questions"]),
 ("E: cluster bootstrap CIs at nine clusters", "sections/08-eval.tex",
  [r"cluster bootstrap 95\\% intervals", r"B\{=\}2000"]),
 ("E: failure-taxonomy table with the form split", "sections/08-eval.tex",
  [r"\\label\{tab:taxonomy\}", r"errors by (gold )?form"]),
 # (2026-08-26, poststudy3 V6a+): the battery GREW 34 -> 70 (34 pre-registered
 # F1-F5 + 5 pinned reproduction mutations + 31 post-registered F6-F10, all
 # rejected; values gated by check_numbers.py on v6aplus_summary.json).  The
 # pre-registered strings stay pinned and the grown totals are pinned WITH
 # them -- extension, not retirement.
 # (2026-08-27, poststudy4 round 2) the battery grew 70 -> 78 with the F11
 # outer-row-filter family (34 pre-registered + 44 post-registered); the pre-
 # registered strings stay pinned and the grown totals are pinned WITH them --
 # extension, not retirement (values gated by check_numbers.py on
 # v6aplus_v4_summary.json).
 ("E: 60/60 certificates; 34/34 pre-registered + 78/78 family forgeries",
  "sections/08-eval.tex",
  [r"accepts \$60/60\$", r"rejects \$34/34\$",
   r"11 unmodified compiler certificates",
   r"78 forged certificates in all", r"reject \$31/31\$",
   r"total is \$78/78\$ rejected"]),
 # (2026-08-27, poststudy4) the round-2 outer-filter closure is DISCLOSED with
 # its F11 family, the two pinned exploits (grand total 80) and both new reason
 # codes; a compression pass must not keep the grown counts while eating the
 # reason they grew.
 ("E5+C5: round-2 outer-filter closure disclosed with F11 and the grand total",
  None,
  [r"F11 outer-row-filter \(8\)", r"\$8/8\$", r"\$80/80\$",
   r"filtering the scalar answer to zero rows",
   r"V6P\\_SHAPE", r"V6P\\_ARITY",
   r"a second external review \(2026-08\)"]),
 # (2026-08-26, poststudy3): the review-found V6a gap is DISCLOSED -- in S5
 # at the soundness scope and in E5 at the battery -- and stays disclosed: a
 # compression pass must not keep the grown counts while eating the reason
 # they grew.
 ("C5+E5: V6a+ hardening disclosed with its review provenance", None,
  [r"[Aa]n external review \(2026-08\)", r"pinned reason code",
   r"narrowed-window mutations", r"All four frozen predictions held",
   r"the original V6a accepted"]),
 ("E: strict track fail-closed, the 10 questions characterised",
  "sections/08-eval.tex",
  [r"those \$50/60\$", r"fails closed", r"8 questions", r"2 cross-window"]),
 ("E: accepted forgery boundary case disclosed", "sections/08-eval.tex",
  [r"deleting \\emph\{part\}", r"is accepted and we say"]),
 ("E: 5+5+5 divergence decomposition", "sections/08-eval.tex",
  [r"rejected 25 of the 51", r"15 distinct root causes",
   r"5 implementation defects", r"5 registration gaps",
   r"5\s*specification-reading divergences"]),
 ("E: constructive upper bound on the compiler row", "sections/08-eval.tex",
  [r"constructive upper\s*bound"]),
 ("E: scoring asymmetry disclosed in the main-table caption",
  "sections/08-eval.tex",
  [r"asymmetric in the baselines' favour"]),
 ("E: disclosure gate exercised with all three instance kinds",
  "sections/08-eval.tex",
  [r"three \\texttt\{DISCLOSURE-BLOCKED\}", r"five granularity roll-ups",
   r"two mask degradations"]),
 ("E: rewrite ablation labelled arithmetic, not a run", "sections/08-eval.tex",
  [r"arithmetic rather than a run"]),
 ("E: version axis exercised with real-history flip", "sections/08-eval.tex",
  [r"\$100\.0\$ vs\.\\ \$252\.0\$", r"off-diagonal"]),
 ("E: RC-7xRC-8 interaction on gold", "sections/08-eval.tex",
  [r"\$10\\to20\$ \\emph\{between\s*versions\}"]),
 ("E: A'/B'/C' labelled pre-registered, B' not re-run", "sections/08-eval.tex",
  [r"A\$'\$", r"B\$'\$", r"C\$'\$", r"not re-run"]),
 # ---- the governance-informed arm: the G8 answer ---------------------------
 ("GOV: arm present with protocol-scoped claim", "sections/08-eval.tex",
  [r"\\label\{sec:eval-gov\}", r"\\textbf\{under this protocol\}",
   r"0\.361<0\.40"]),
 ("GOV: depth split (probes / registry-decidable / disclosure)",
  "sections/08-eval.tex",
  # (2026-08-10, M3) RE-PINNED, not dropped: the protected content is the
  # DEPTH SPLIT (probe-decidable vs registry-decidable vs disclosure), which
  # still holds.  Only the registry-decidable leg's reading changed, from a
  # refuted repair count ("fixes 4 of 5") to the absolute error count the
  # abstract already used.  The split is unchanged; its wording is corrected.
  [r"errs on \\textbf\{6 of 7\}", r"errs on only \\textbf\{1 of\s*5\}",
   r"a policy on file is not a policy enforced"]),
 ("GOV: three alternative explanations with exclusion evidence",
  "sections/08-eval.tex",
  [r"Context dilution", r"r=0\.400", r"Transport faults",
   r"zero empty responses", r"Imperative\s*compliance", r"correctly refused"]),
 ("GOV: ND-4 adversarial non-degeneracy with the 0/20 history",
  "sections/08-eval.tex",
  [r"\$0/20\$", r"ND-4"]),
 ("GOV: bounded in our favour", None,
  [r"upper bound\s*on what in-context governance buys",
   r"not a tuned\s*opponent's floor"]),
 # (2026-08-23, R2-1-4) The measured probe-oracle ceiling: the E3 narrative's
 # most predictable objection ("an agent would just run the probes") is now
 # answered with arithmetic over the frozen matrix, and a compression pass
 # must not eat it -- nor its honest sting (the ceiling CROSSES the 0.40
 # line, so the verdict is protocol-scoped by measurement, not by wording).
 ("GOV: probe-oracle ceiling printed, with the crossing owned",
  "sections/08-eval.tex",
  [r"crediting the arm with all six probe-decidable residuals",
   r"\$17/36=0\.472\$", r"past\s*the \$0\.40\$ line",
   r"not probe-decidable at all"]),
 # (2026-08-23, R3-1-4) The ceiling is extended to credit execution-error
 # residuals as well -- the recoverable-share bound an execution-feedback
 # loop is held to.  Both halves are pinned: the extended arithmetic in E3
 # and the consistently re-worded recoverable-share sentences (abstract,
 # S9), so no compression pass can quietly fall back to the probe-only
 # bound while still claiming it bounds "the recoverable share".
 # (2026-08-26, M2): the ABSTRACT's copy of the recoverable-share bound
 # ("to at most $0.667$") moved out under the ~210-word compression;
 # the protected content -- the extended ceiling's arithmetic in E3 and
 # the recoverable-share sentence in S9 -- remains pinned, and
 # check_numbers.py now asserts the abstract stays CLEAN of the ceilings.
 ("GOV: extended probe+execution ceiling printed and quoted consistently",
  None,
  [r"further crediting all nine execution-error residuals",
   r"\$24/36=0\.667\$",
   r"bounds the recoverable share at \$0\.667\$"]),
 # (2026-08-26, M2 honest uncertainty): the five-repetition span and the
 # paired nine-cluster CI now carry the elimination verdict's uncertainty
 # in the abstract, at the E3 verdict, and in S9 (values gated by
 # check_numbers.py on the s3/s4 summary JSONs).  A compression pass must
 # not eat the span, the CI, or the straddle.
 ("M2: five-rep span + paired CI printed at the verdict", None,
  [r"0\.361\$?--\$?0\.417", r"\[-0\.05,0\.30\]",
   r"straddling the \$0\.40\$ line",
   r"the frozen run does not cross the pre-registered \$40\\%\$"]),
 # (2026-08-23, R3-1-5) Q_tmpl is formally defined in the body and Theorem
 # certsound(b) is restated over Definition def:tmpl under the explicit,
 # still-open assumption (A-tmpl); S9 mirrors the assumption.  A page cut
 # must not demote the class back to a prose description.
 ("C5: Q_tmpl formal definition + (A-tmpl) stated at theorem and in S9",
  None,
  [r"\\begin\{definition\}\[template class",
   r"\\label\{def:tmpl\}",
   r"Membership is decidable",
   r"\(A-tmpl\)",
   r"syntax\s*implies semantics"]),
 # (2026-08-23, R2-1-3) The headline magnitudes were scoped to the
 # Chinese-question workload and the threats item named the MISSING
 # English-question control.  SUPERSEDED same day by battery 2
 # (pilot2/poststudy2_20260823/s6): the control was run post-registered,
 # so the item now prints the measured result instead of conceding its
 # absence --- pinning the old wording would pin a false sentence.  The
 # counts themselves are re-derived from the study JSON by
 # check_numbers.py; this pins the sentence and its conclusion.
 ("H: cross-lingual threat carries the measured English-question control",
  "sections/08-eval.tex",
  [r"post-registered English run of both headline arms",
   r"moves each arm one question",
   r"ordering and probe-side concentration intact",
   r"language does not drive the gap"]),
 # (2026-08-23, battery 2) The input-modality threat ("the compiler is
 # handed sigma") carries the S7 measurement: an NL->sigma arm errs 5/60,
 # so the concession is quantified, not open-ended.  A compression pass
 # must not eat the measurement and fall back to the bare concession.
 ("H: input-modality threat carries the measured NL->sigma arm",
  "sections/08-eval.tex",
  [r"extracts \$\\sigma\$ from the question text and hands it to the\s*compiler",
   r"recovering \$\\sigma\$ is not where the difficulty\s*lives"]),
 # (2026-08-23, R2-1-2) SVRC is defined in the body, [REDACTED-CONCURRENT] reduced to
 # name attribution -- Theorem thm:degen must stay checkable from this
 # submission alone, with no under-submission manuscript on the path.
 # (2026-08-24, author decision) SUPERSEDED IN PART: the author ruled that
 # the three concurrent same-author submissions (REDACTED-CONCURRENT, REDACTED-CONCURRENT,
 # REDACTED-CONCURRENT) are not cited or mentioned anywhere in this paper, so the
 # "\cite{REDACTED-CONCURRENT} supplies the name only" pattern would pin a sentence
 # that no longer exists and is retired.  The protected content -- SVRC
 # defined completely in the body, so thm:degen is checkable from this
 # submission alone -- still holds and stays pinned.
 ("S2: SVRC defined in the body, self-contained",
  "sections/03-semantics.tex",
  [r"\(SVRC\) iff a single committed\s*version",
   r"a definition complete here"]),
 # ---- honesty disclosures that may not be dropped --------------------------
 ("H: trivial_v2 void + rerun, both runs disclosed", "sections/08-eval.tex",
  [r"run\\,1: 27 correct/33 errors", r"run\\,2, the scored one: 25/35",
   r"voided"]),
 # (2026-08-07, R3-X8 / R4-X4-9, landed round 5) The resumed session is on the
 # REFERENCE arm and its 21 pre-crash questions are an enumeration prefix, not
 # a chosen subset.  Naming the arm is the whole disclosure, so pin the arm and
 # the prefix claim together -- a compression pass that drops either turns an
 # honest disclosure back into an anonymous one.
 ("H: resumed session names its arm and its prefix", "sections/08-eval.tex",
  [r"crashed", r"baseline\\_claude", r"enumeration\s+prefix",
   r"pre-registered resume clause"]),
 # (2026-08-10, M4) EXTENDED, not replaced: "in full" now has to be full.
 # PREREG S5.2 freezes four governance-arm predictions, and the paragraph had
 # reported only two (elim and the probe set).  The two added here are the
 # unflattering ones -- correct_refusals landed BELOW its interval and
 # over_refusals AT its floor -- so they are exactly the ones a compression
 # pass would be tempted to drop.  check_numbers.py re-parses both out of the
 # frozen PREREG and scores them; this pins their presence in the prose.
 # (2026-08-26, M2 honest-uncertainty pass) RELOCATED TO TR, per protocol:
 # the "Prediction accounting" paragraph moved to the TR in full -- the
 # sharpest-miss literal (14 [8-22] -> 28), the elimination miss's point
 # pair and frozen [0.35,0.75] interval, the S5.2 digits (correct_refusals
 # 9/15 [6-12] observed 5 BELOW; over_refusals ~4/45 [1-9] observed 1 at
 # the floor) and the denominator sensitivity all print there (the TR
 # carries the full paragraph and both tables), and check_numbers.py STILL
 # parses and scores every one of those predictions from the frozen
 # PREREG, so no value weakened.  Pinned in body: the 8/8 + 7/8 optimism
 # tally inside the case-(iii) paragraph, the named TR-side items, and the
 # item-by-item ledger pointer.
 ("H: prediction misses published; the item ledger relocated to TR",
  "sections/08-eval.tex",
  [r"The frozen predictions were\s*optimistic",
   r"exceed their point predictions and 7 of 8",
   r"the elimination miss's frozen interval",
   r"the\s*denominator's own overshoot",
   r"accounted item by item\s*in~\\cite\{asofgov-tr\}"]),
 # (2026-08-10, M6) The case-(iii) verdict is a ratio whose DENOMINATOR is
 # itself one measurement that overshot its own frozen prediction.  The clause
 # discloses that, states the sensitivity, and explicitly does NOT re-adjudicate
 # on it.  All three halves are pinned together: dropping the "does not itself
 # enter the rule" half would turn a disclosure into a second adjudication.
 # (2026-08-26, M2 honest-uncertainty pass) RELOCATED TO TR, per protocol:
 # the full clause ("$36$ against a frozen point of $25$", "does not itself
 # enter the rule", "$13/35=0.371$", "the case is unchanged") moved to the
 # TR's item-by-item accounting, which prints it verbatim; check_numbers.py
 # still re-derives 36-vs-25 and 13/35=0.371 from the frozen artifacts, so
 # the values cannot drift.  The body keeps the overshoot NAMED inside the
 # miss-ledger sentence -- a disclosure that survives compression without
 # re-adjudicating -- and that surviving form is pinned below.
 ("H: case-(iii) denominator overshoot still disclosed (full clause: TR)",
  "sections/08-eval.tex",
  [r"the\s*denominator's own overshoot"]),
 ("H: hull-trim giveaway questions disclosed", "sections/08-eval.tex",
  [r"window-blind aggregate equals gold by construction"]),
 ("H: gateway third-party preamble disclosed", "sections/08-eval.tex",
  [r"third-party system prompt", r"channel-matched"]),
 ("H: authored governance layer owned as ours", "sections/08-eval.tex",
  [r"is ours", r"witness pairs"]),
 ("H: sigma isolation stated (parsing out of scope)", "sections/08-eval.tex",
  [r"parsing language into \$\\sigma\$ is out of\s*scope"]),
 ("H: execution feedback is the remaining absent comparator", None,
  [r"What no arm has\}? is \\emph\{execution feedback\}"]),
 ("H: no scan-amplification regime claimed", "sections/08-eval.tex",
  [r"\\emph\{no\} instance here", r"report no scalability sweep"]),
 # (2026-08-07, R3-X1) The protocol is cross-lingual -- Chinese questions over
 # English schemas.  It is a setup fact no other red line names, so a
 # compression pass could drop it without tripping anything; pin both halves.
 ("H: cross-lingual protocol disclosed", "sections/08-eval.tex",
  [r"authored in Chinese", r"cross-lingual"]),
 # (2026-08-24, author decision) RETIRED: "H: concurrent same-author
 # submissions self-declared" pinned the S8 concurrent-submission paragraph
 # and its "under submission" wording.  The author ruled on 2026-08-24 --
 # after the venue's concurrent-submission policy conflict was shown and
 # explicitly accepted -- that the three concurrent same-author submissions
 # are removed from the paper in full (citations, table row, paragraph, bib
 # entries), so the pinned sentence no longer exists and the red line is
 # retired rather than left to pin absent text.
 # ---- provenance discipline (author ruling 2026-08-04) ---------------------
 ("P: production observation marked in the intro, and only there",
  "sections/01-intro.tex",
  [r"16\.2\\%", r"3\.8\\%", r"4\.2\\times", r"production observation"]),
 ("P: public caliber pair carried where caliber is defined",
  "sections/03-semantics.tex",
  [r"15\.2\\times"]),
 # (2026-08-26, template restoration) The FULL 15-row ledger RELOCATED TO
 # TR, per protocol: the TR prints every row with both readings, the
 # machine-readable source of record stays impl/INTEGRATION_REPORT.md
 # section 5, and tab_divergence.audit.json still ships all 15 rows with
 # evidence (asserted by check_numbers.py).  The body table is a summary
 # -- per-class counts + three exemplar rows, one per root-cause class --
 # whose provenance pin below is UNCHANGED (the caption keeps it), and
 # whose summary content gets its own pin beside it.
 ("P: D1-D15 ledger keeps its integration provenance",
  "tables/tab_divergence.tex",
  [r"Provenance", r"production", r"no production data value"]),
 ("P: slimmed divergence summary carries counts, exemplars, TR pointer",
  "tables/tab_divergence.tex",
  [r"all 15: 5 S \$\\cdot\$ 3\+2 D \$\\cdot\$ 5 R",
   r"\$D_\{1\}\$", r"\$D_\{7\}\$", r"\$D_\{4\}\$",
   r"asofgov-tr"]),
 ("P: E6 frames the ledger with provenance", "sections/08-eval.tex",
  [r"recorded during", r"integration on the production track"]),
 # (2026-08-26, D-visibility): the NL->sigma hybrid is promoted in the
 # E-takeaway (count gated on the S7 summary by check_numbers.py) and the
 # precise schema-evolution delineation is restored in S8 (schema-version
 # query rewriting vs governance-version re-scoping over unchanged rows;
 # typed refusal absent there) without citing removed papers.
 # (2026-08-27, poststudy4 item B) the hybrid is now BOTH in the E-takeaway
 # and a main-results row (tab:main, 5/60, gate-wired from s7_summary.json);
 # its caption names it the recommended deployment path.
 ("D: NL->sigma hybrid promoted to the E-takeaway and a main-results row",
  "sections/08-eval.tex",
  [r"NL-to-\$\\sigma\$ hybrid errs \$5/60\$",
   r"recommended deployment path"]),
 ("D: schema-evolution delineation restored in S8", "sections/09-related.tex",
  [r"query rewriting across \\emph\{schema\}",
   r"re-scopes governed meaning over unchanged rows",
   r"typed refusal has no counterpart"]),
 # ---- 10-conclusion: version axis + artifact + AI disclosure ---------------
 ("S9: version axis exercised + residual unexercised paths",
  "sections/10-conclusion.tex",
  [r"version axis is now exercised", r"three defence paths"]),
 ("S9: generative-AI disclosure, full wording", "sections/10-conclusion.tex",
  [r"Disclosure of generative AI use",
   r"take full\s*responsibility for the entire content of this paper"]),
 # (2026-08-26, poststudy3): inventory EXTENDED with the V6a+ battery
 # (pinned reproduction mutations + F6-F10); the original pin stays.
 ("S9: artifact availability inventory (public base)",
  "sections/10-conclusion.tex",
  [r"Artifact availability", r"\\url\{\\artifacturl\}",
   r"voided \\texttt\{trivial\\_v2\} first run", r"11 bases and 34\s*forgeries",
   r"post-registered\s*V6a\+ battery"]),
 # ---- 07-system: the four CI assertions ------------------------------------
 ("S6: four CI assertions verbatim", "sections/07-system.tex",
  [r"\(a\)~each import resolves to the Python standard library",
   r"\(b\)~no verifier file\s*imports any compiler location",
   r"\(c\)~the two sides' project-internal import roots intersect in the empty set",
   r"\(d\)~no dynamic-import or path-manipulation escape hatch"]),
 # ---- 09-related: four-neighbour delineation -------------------------------
 ("S8: four nearest neighbours, one sentence each", "sections/09-related.tex",
  [r"Schema-evolution robustness", r"Bitemporal agent memory",
   r"Lakehouse time travel", r"Static semantic layers", r"\\label\{tab:delta\}"]),
 # ---- 01-intro: three contribution bullets ---------------------------------
 ("S1: three contribution bullets", "sections/01-intro.tex",
  [r"A bi-temporal governed query semantics",
   r"Binding compilation and its decidability",
   r"Point-in-time certificates and independent verification"]),
 # ---- main.tex: the mandatory VLDB blocks ----------------------------------
 ("main: VLDB block regions intact", "main.tex",
  [r"%%% VLDB block start %%%", r"\\usepackage\{pvldb\}",
   r"\\vldbtopmatter", r"\\renewcommand\\vldbdoi", r"\\renewcommand\\vldbpages",
   r"\\renewcommand\\vldbavailabilityurl"]),
 ("main: short title for the running head", "main.tex", [r"\\title\["]),
]

fails, checks = [], 0
for label, where, pats in RED:
    hay = F[where] if where else ALL
    for p in pats:
        checks += 1
        if not re.search(p, hay):
            fails.append(f"{label}  ::  missing {p!r}"
                         + (f"  in {where}" if where else ""))

print(f"red-line presence check: {checks} assertions, {len(fails)} failed")
for f in fails:
    print("  FAIL " + f)
sys.exit(1 if fails else 0)
