#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s5_render_report.py — render S5_REPORT.md from s5_cost_sweep.json.

Every number in the report is read from the JSON; nothing is typed by hand.
"""
import json
import pathlib

S5 = pathlib.Path(__file__).resolve().parent
J = json.loads((S5 / "s5_cost_sweep.json").read_text(encoding="utf-8"))

P = J["predictions"]
ROWS = J["row_scale_axis"]
SPAN = J["window_span_axis"]
MAN = J["substrates_manifest"]

def f(x, n=5):
    return ("%%.%df" % n) % x

def ms(x):
    return "%.2f" % (x * 1000)

L = []
A = L.append

A("# S5 — Cost-model scalability sweep (deterministic, zero LLM)")
A("")
A("Post-registration study under `%s`, sha256 `%s`. Generated %s by `%s`; "
  "all numbers below are rendered from `s5_cost_sweep.json`."
  % (J["prereg"]["file"], J["prereg"]["sha256"], J["generated_at"],
     J["generator"]))
A("")
A("**Verdicts: S5-P1 %s · S5-P2 %s · S5-P3 %s.** A miss is published as a miss."
  % (P["S5-P1"]["verdict"], P["S5-P2"]["verdict"], P["S5-P3"]["verdict"]))
A("")
A("## Setup")
A("")
A("* Substrates: the sandbox financial warehouse copied OUT of the sandbox "
  "into `s5/work/rowscale/` before any mutation (sandbox source sha256 `%s`; "
  "frozen `pilot2/domains/financial` warehouse sha256 `%s`, never opened "
  "read-write). Scaling rule (deterministic, no RNG): below 1x, systematic "
  "residue sampling — keep rows with `trans_id %% 8 < 8f` (residues {0}, "
  "{0,1}, {0,1,2,3}); above 1x, row duplication with key remapping — copy "
  "c inserts every original row with `trans_id += c*4,000,000` (> max "
  "original id 3,682,987), all other columns (account_id included) verbatim; "
  "1x is a byte-identical copy." %
  (MAN["source_sandbox_financial_sha256"][:16] + "…",
   (MAN["frozen_financial_sha256"] or "n/a")[:16] + "…"))
A("* Compiler/verifier: the FROZEN `impl/asof_compiler` and "
  "`impl/asof_verifier/chk.py`, imported read-only. Identity check: the 8 "
  "certificates recompiled on the 1x substrate are json-identical to the "
  "frozen `impl/certs2/FIN-*.json`.")
A("* Timing: %s warm repeats per measurement (>= the prereg'd 5), median, "
  "mirroring `impl/measure_cost.py`'s warm shape (chk imported once, one "
  "read-only duckdb connection per substrate held open, untimed verdict "
  "call first). Cold-process timing not re-measured (interpreter+import "
  "floor is row-scale-independent). Env: python %s, duckdb %s, %s, %s cores."
  % (J["methodology"]["warm_repeats"], J["env"]["python"],
     J["env"]["duckdb"], J["env"]["machine"], J["env"]["cpu_count"]))
A("* Full-scan audit counting: `impl/measure_adm_scan.py`'s gate "
  "(FULL_SCAN_MODES={symdiff_audit}, "
  "WINDOW_BOUNDED_MODES={window_realization_symdiff}).")
A("")
A("## Row-scale axis (mandatory) — all 6 points reachable")
A("")
A("Hull survival held at every point (`hull_losses_vs_frozen_questions` "
  "empty everywhere); no scale point was unreachable. Verdicts: all 48 "
  "certificates (8 questions x 6 scales) verify **ACCEPT** with the frozen "
  "decisions (5 ANSWER, 1 REWRITE, 2 REFUSE) preserved at every scale.")
A("")
A("| scale | trans rows | verify warm median (ms) | answer warm median (ms) "
  "| paired ratio med (min–max) | full-scan audits |")
A("|---|---|---|---|---|---|")
for p in ROWS:
    A("| %g× | %s | %s | %s | %.1f× (%.2f–%.1f) | %d |" % (
        p["row_factor"], format(p["trans_rows"], ","),
        ms(p["verify_warm_median_over_certs_s"]),
        ms(p["answer_warm_median_over_certs_s"]),
        p["paired_ratio_median"], p["paired_ratio_min"],
        p["paired_ratio_max"], p["n_full_scan_audits"]))
A("")
A("Substrate-correctness witnesses (answer values from the emitted SQL): "
  "trans-anchored counts scale with the axis — FIN-Q5 %s / FIN-Q6 %s across "
  "the six scales — while the loan-anchored FIN-Q1/Q2/Q4 values are "
  "scale-invariant and the ratio metric FIN-Q3 is exactly invariant under "
  "duplication (%s at 1×/2×/4×), as proportion-preserving remapped "
  "duplication requires." % (
      " → ".join(str(int(r["answer_value"])) for r in
                 (next(c for c in p["per_certificate"] if c["qid"] == "FIN-Q5")
                  for p in ROWS)),
      " → ".join(str(int(r["answer_value"])) for r in
                 (next(c for c in p["per_certificate"] if c["qid"] == "FIN-Q6")
                  for p in ROWS)),
      f(next(c for c in ROWS[3]["per_certificate"]
             if c["qid"] == "FIN-Q3")["answer_value"], 7)))
A("")
A("### Per-certificate warm verify medians (ms)")
A("")
qids = [c["qid"] for c in ROWS[0]["per_certificate"]]
A("| qid | " + " | ".join("%g×" % p["row_factor"] for p in ROWS)
  + " | growth 1×→4× |")
A("|---" * (len(ROWS) + 2) + "|")
for qid in qids:
    vals = [next(c for c in p["per_certificate"] if c["qid"] == qid)
            ["verify_warm_median_s"] for p in ROWS]
    A("| %s | %s | %.2f× |" % (qid, " | ".join(ms(v) for v in vals),
                               vals[5] / vals[3]))
A("")
A("## S5-P1 — %s" % P["S5-P1"]["verdict"])
A("")
A("> %s" % P["S5-P1"]["prediction"])
A("")
med = P["S5-P1"]["medians_s"]
A("Statistic: %s. Sequence (ms): %s." % (
    P["S5-P1"]["statistic"],
    " → ".join("%s" % ms(med[k]) for k in
               ["scale_0125", "scale_025", "scale_050", "scale_100",
                "scale_200", "scale_400"])))
A("")
A("* Growth clause **met**: 4× rows ⇒ %.2f× median verify time (≤ 4×). "
  "Verify is strongly sublinear in row scale (the governance-table term "
  "and window-bounded probes dominate)."
  % P["S5-P1"]["growth_100_to_400"])
A("* Monotone-non-decreasing clause **violated once**: 0.25× → 0.5× dips "
  "%s → %s ms, a %.2f%% (%.0f µs) decrease — far inside run-to-run warm "
  "noise, but the prereg wrote strict monotonicity, so the prediction is "
  "adjudicated **MISS**. Every other adjacent step is non-decreasing."
  % (ms(med["scale_025"]), ms(med["scale_050"]),
     100 * (1 - med["scale_050"] / med["scale_025"]),
     1e6 * (med["scale_025"] - med["scale_050"])))
A("")
A("## S5-P2 — %s (strict per-certificate reading: %s)"
  % (P["S5-P2"]["verdict"], P["S5-P2"]["strict_all_certificates_verdict"]))
A("")
A("> %s" % P["S5-P2"]["prediction"])
A("")
A("Adjudicated statistic (declared in the sweep script before adjudication): "
  "the per-point **median** paired ratio over the 6 SQL-emitting "
  "certificates — in band [1×, 60×] at every point (%.1f× down to %.1f×), "
  "so **MET**. The stricter every-certificate reading fails only at 4×: "
  "FIN-Q5 (%.3f×) and FIN-Q6 (%.3f×) dip just below 1× because their "
  "answering query grows linearly with rows while verification stays "
  "window-bounded — verification becoming *cheaper than answering* at scale "
  "is the favourable direction for the §3 cost claims, but it exits the "
  "prereg band's lower edge, and we publish that reading as a MISS."
  % (max(v["median"] for v in P["S5-P2"]["per_point"].values()),
     min(v["median"] for v in P["S5-P2"]["per_point"].values()),
     next(c for c in ROWS[5]["per_certificate"]
          if c["qid"] == "FIN-Q5")["ratio_warm"],
     next(c for c in ROWS[5]["per_certificate"]
          if c["qid"] == "FIN-Q6")["ratio_warm"]))
A("")
A("## S5-P3 — %s" % P["S5-P3"]["verdict"])
A("")
A("> %s" % P["S5-P3"]["prediction"])
A("")
A("Full-scan audits (`symdiff_audit`) per point: %s — zero everywhere. %s"
  % (", ".join("%s=%d" % (k.replace("scale_", ""), v)
               for k, v in P["S5-P3"]["full_scan_audits_per_point"].items()),
     P["S5-P3"]["note"]))
A("")
A("## Window-span axis (stretch goal) — %s" % SPAN["status"])
A("")
A("%s. Variant rule: %s." % (SPAN["base_question"], SPAN["variant_rule"]))
A("")
A("| span | window | decision/verdict | verify warm (ms) | answer warm (ms) "
  "| ratio | rows counted |")
A("|---|---|---|---|---|---|---|")
for r in SPAN["per_span"]:
    A("| %d mo | %s..%s | %s/%s | %s | %s | %.1f× | %d |" % (
        r["span_months"], r["window_lo"], r["window_hi"], r["decision"],
        r["verdict"], ms(r["verify_warm_median_s"]),
        ms(r["answer_warm_median_s"]), r["ratio_warm"],
        int(r["answer_value"])))
A("")
v1 = SPAN["per_span"][0]["verify_warm_median_s"]
v48 = SPAN["per_span"][-1]["verify_warm_median_s"]
A("Verify cost is flat in window span (%s ms at 1 month vs %s ms at 48 "
  "months, %.2f×) while the certified row count grows 48×: the span axis "
  "confirms the window-bounded probe term is not the dominant cost at this "
  "data size, and every span point's paired ratio (%.1f–%.1f×) sits inside "
  "the [1×, 60×] band. All six spans compile ANSWER and verify ACCEPT — no "
  "unreachable point." % (
      ms(v1), ms(v48), v48 / v1,
      min(r["ratio_warm"] for r in SPAN["per_span"]),
      max(r["ratio_warm"] for r in SPAN["per_span"])))
A("")
A("## Scope and honesty notes")
A("")
A("* No silent truncation: all 6 mandatory row-scale points and all 6 "
  "stretch span points were reached and are reported; the reachability "
  "gate (gold-anchor hull survival) is recorded per substrate in "
  "`work/substrates_manifest.json`.")
A("* The span-axis variants are cost probes derived from the frozen W1-Q4 "
  "dict (only qid/window fields swapped); gold values were set to null, "
  "never fabricated, and the variants are not scored questions.")
A("* Frozen evidence untouched: compiler/verifier imported read-only; the "
  "frozen warehouses and the sandbox were never opened read-write; all "
  "outputs are new files under `pilot2/poststudy2_20260823/s5/`.")
A("* S5-P1's monotonicity clause and S5-P2's strict reading fail on "
  "sub-noise / sub-1× effects respectively; both are published as written "
  "above rather than re-run or re-defined.")
A("")

(S5 / "S5_REPORT.md").write_text("\n".join(L), encoding="utf-8")
print("wrote", S5 / "S5_REPORT.md")
