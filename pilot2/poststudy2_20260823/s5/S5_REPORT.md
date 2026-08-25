# S5 — Cost-model scalability sweep (deterministic, zero LLM)

Post-registration study under `PREREG_poststudy2_20260823.md`, sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669`. Generated 2026-08-23T21:39:03+08:00 by `pilot2/poststudy2_20260823/s5/s5_measure.py`; all numbers below are rendered from `s5_cost_sweep.json`.

**Verdicts: S5-P1 MISS · S5-P2 MET · S5-P3 MET.** A miss is published as a miss.

## Setup

* Substrates: the sandbox financial warehouse copied OUT of the sandbox into `s5/work/rowscale/` before any mutation (sandbox source sha256 `3409ec368c551f2c…`; frozen `pilot2/domains/financial` warehouse sha256 `3409ec368c551f2c…`, never opened read-write). Scaling rule (deterministic, no RNG): below 1x, systematic residue sampling — keep rows with `trans_id % 8 < 8f` (residues {0}, {0,1}, {0,1,2,3}); above 1x, row duplication with key remapping — copy c inserts every original row with `trans_id += c*4,000,000` (> max original id 3,682,987), all other columns (account_id included) verbatim; 1x is a byte-identical copy.
* Compiler/verifier: the FROZEN `impl/asof_compiler` and `impl/asof_verifier/chk.py`, imported read-only. Identity check: the 8 certificates recompiled on the 1x substrate are json-identical to the frozen `impl/certs2/FIN-*.json`.
* Timing: 9 warm repeats per measurement (>= the prereg'd 5), median, mirroring `impl/measure_cost.py`'s warm shape (chk imported once, one read-only duckdb connection per substrate held open, untimed verdict call first). Cold-process timing not re-measured (interpreter+import floor is row-scale-independent). Env: python 3.9.6, duckdb 1.4.4, arm64, 10 cores.
* Full-scan audit counting: `impl/measure_adm_scan.py`'s gate (FULL_SCAN_MODES={symdiff_audit}, WINDOW_BOUNDED_MODES={window_realization_symdiff}).

## Row-scale axis (mandatory) — all 6 points reachable

Hull survival held at every point (`hull_losses_vs_frozen_questions` empty everywhere); no scale point was unreachable. Verdicts: all 48 certificates (8 questions x 6 scales) verify **ACCEPT** with the frozen decisions (5 ANSWER, 1 REWRITE, 2 REFUSE) preserved at every scale.

| scale | trans rows | verify warm median (ms) | answer warm median (ms) | paired ratio med (min–max) | full-scan audits |
|---|---|---|---|---|---|
| 0.125× | 132,000 | 18.04 | 2.82 | 24.8× (3.56–41.4) | 0 |
| 0.25× | 263,927 | 18.10 | 2.84 | 24.2× (3.60–41.8) | 0 |
| 0.5× | 527,900 | 18.06 | 2.87 | 22.3× (3.46–41.9) | 0 |
| 1× | 1,056,320 | 19.69 | 3.92 | 21.5× (2.58–40.5) | 0 |
| 2× | 2,112,640 | 21.03 | 6.19 | 20.6× (1.61–41.3) | 0 |
| 4× | 4,225,280 | 24.80 | 11.13 | 20.4× (0.98–42.1) | 0 |

Substrate-correctness witnesses (answer values from the emitted SQL): trans-anchored counts scale with the axis — FIN-Q5 1945 → 3971 → 7923 → 15885 → 31770 → 63540 / FIN-Q6 18877 → 37727 → 75571 → 151237 → 302474 → 604948 across the six scales — while the loan-anchored FIN-Q1/Q2/Q4 values are scale-invariant and the ratio metric FIN-Q3 is exactly invariant under duplication (0.0014310 at 1×/2×/4×), as proportion-preserving remapped duplication requires.

### Per-certificate warm verify medians (ms)

| qid | 0.125× | 0.25× | 0.5× | 1× | 2× | 4× | growth 1×→4× |
|---|---|---|---|---|---|---|---|
| FIN-Q1 | 40.57 | 40.44 | 40.64 | 40.48 | 40.65 | 40.98 | 1.01× |
| FIN-Q2 | 39.60 | 39.33 | 39.74 | 40.11 | 39.67 | 40.00 | 1.00× |
| FIN-Q3 | 48.80 | 47.58 | 48.75 | 53.57 | 60.24 | 74.11 | 1.38× |
| FIN-Q4 | 14.67 | 14.45 | 14.62 | 14.72 | 14.65 | 14.48 | 0.98× |
| FIN-Q5 | 16.77 | 16.84 | 16.76 | 17.81 | 19.05 | 20.89 | 1.17× |
| FIN-Q6 | 16.56 | 16.97 | 16.75 | 18.05 | 19.02 | 20.81 | 1.15× |
| FIN-Q7 | 14.44 | 14.53 | 14.81 | 16.42 | 18.46 | 22.47 | 1.37× |
| FIN-Q8 | 19.31 | 19.24 | 19.35 | 21.34 | 23.02 | 27.14 | 1.27× |

## S5-P1 — MISS

> warm verify median is monotone non-decreasing in row scale with growth at most linear (4x rows => <=4x median verify time)

Statistic: median over the 8 financial certificates of the per-certificate warm-verify medians, per scale point. Sequence (ms): 18.04 → 18.10 → 18.06 → 19.69 → 21.03 → 24.80.

* Growth clause **met**: 4× rows ⇒ 1.26× median verify time (≤ 4×). Verify is strongly sublinear in row scale (the governance-table term and window-bounded probes dominate).
* Monotone-non-decreasing clause **violated once**: 0.25× → 0.5× dips 18.10 → 18.06 ms, a 0.25% (45 µs) decrease — far inside run-to-run warm noise, but the prereg wrote strict monotonicity, so the prediction is adjudicated **MISS**. Every other adjacent step is non-decreasing.

## S5-P2 — MET (strict per-certificate reading: MISS)

> paired verify/answer ratio stays inside [1x, 60x] at every reachable scale point

Adjudicated statistic (declared in the sweep script before adjudication): the per-point **median** paired ratio over the 6 SQL-emitting certificates — in band [1×, 60×] at every point (24.8× down to 20.4×), so **MET**. The stricter every-certificate reading fails only at 4×: FIN-Q5 (0.978×) and FIN-Q6 (0.981×) dip just below 1× because their answering query grows linearly with rows while verification stays window-bounded — verification becoming *cheaper than answering* at scale is the favourable direction for the §3 cost claims, but it exits the prereg band's lower edge, and we publish that reading as a MISS.

## S5-P3 — MET

> zero full-scan audits at every scale (all clause-(iv) audits window-bounded, as at 1x)

Full-scan audits (`symdiff_audit`) per point: 0125=0, 025=0, 050=0, 100=0, 200=0, 400=0 — zero everywhere. the financial certificates carry no clause-(iv) replay at any scale (the corpus's three window_realization_symdiff audits live on CARD-Q2/CARD-Q7/EF2-Q6, outside this domain); zero full-scan audits is therefore confirmed by census, and the window-bounded clause is vacuously true here

## Window-span axis (stretch goal) — REACHED

W1-Q4 (w1.history_rows_range), 84-month authored history 2020-01..2026-12. Variant rule: month_token_range ending 2026-12, span in {1,3,6,12,24,48} months, inside validity; cost probes only, gold never fabricated.

| span | window | decision/verdict | verify warm (ms) | answer warm (ms) | ratio | rows counted |
|---|---|---|---|---|---|---|
| 1 mo | 2026-12..2026-12 | ANSWER/ACCEPT | 9.77 | 0.33 | 29.2× | 239 |
| 3 mo | 2026-10..2026-12 | ANSWER/ACCEPT | 9.67 | 0.37 | 26.3× | 717 |
| 6 mo | 2026-07..2026-12 | ANSWER/ACCEPT | 9.51 | 0.35 | 27.2× | 1434 |
| 12 mo | 2026-01..2026-12 | ANSWER/ACCEPT | 9.55 | 0.35 | 27.5× | 2868 |
| 24 mo | 2025-01..2026-12 | ANSWER/ACCEPT | 9.54 | 0.37 | 25.5× | 5736 |
| 48 mo | 2023-01..2026-12 | ANSWER/ACCEPT | 9.49 | 0.39 | 24.4× | 11472 |

Verify cost is flat in window span (9.77 ms at 1 month vs 9.49 ms at 48 months, 0.97×) while the certified row count grows 48×: the span axis confirms the window-bounded probe term is not the dominant cost at this data size, and every span point's paired ratio (24.4–29.2×) sits inside the [1×, 60×] band. All six spans compile ANSWER and verify ACCEPT — no unreachable point.

## Scope and honesty notes

* No silent truncation: all 6 mandatory row-scale points and all 6 stretch span points were reached and are reported; the reachability gate (gold-anchor hull survival) is recorded per substrate in `work/substrates_manifest.json`.
* The span-axis variants are cost probes derived from the frozen W1-Q4 dict (only qid/window fields swapped); gold values were set to null, never fabricated, and the variants are not scored questions.
* Frozen evidence untouched: compiler/verifier imported read-only; the frozen warehouses and the sandbox were never opened read-write; all outputs are new files under `pilot2/poststudy2_20260823/s5/`.
* S5-P1's monotonicity clause and S5-P2's strict reading fail on sub-noise / sub-1× effects respectively; both are published as written above rather than re-run or re-defined.
---

## CORRECTION (2026-08-23) — prereg sha256 provenance

The prereg sha256 quoted in the header above was corrected on 2026-08-23.
The original run's sweep-script constant dropped two hex characters
(`1c` at offset 44) and cited the 62-character value
`838a214fc5a09902703d969c839872ff843f190e9f2e9f6902f231e061c669` in place of the true
64-character sha (recomputed from the frozen prereg on disk)
`838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669`;
no S5 script re-asserted the hash from disk. The defect was found
by adversarial verification (`VERIFICATION2.md`, S5 section and
Defect list item 1). Measured numbers are unaffected and nothing
was re-run: this report was re-rendered (byte-identically, sha
string aside) from the corrected `s5_cost_sweep.json` by the
study's own `s5_render_report.py`; see that JSON's
`provenance_correction` object. `s5_measure.py`'s constant was
corrected and a runtime re-assert-from-disk added, so a future
re-run refuses on mismatch. Correction applied by
`fix_provenance.py`; byte-level before/after proof in
`fix_provenance_result.json`.
