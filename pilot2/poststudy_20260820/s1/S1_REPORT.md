# S1 — Subset robustness of the frozen score matrix (deterministic, zero LLM)

- **Governing prereg**: `PREREG_poststudy_20260820.md`,
  sha256 `f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24`
  (verified before analysis; the analysis driver re-asserts it at start).
- **Study date**: 2026-08-20. Zero LLM calls. All outputs append-only under
  `pilot2/poststudy_20260820/s1/`; no frozen file modified.
- **Machine-readable twin**: [`loco_report.json`](loco_report.json)
  (every number in this file). Analysis driver:
  [`s1_loco_analysis.py`](s1_loco_analysis.py).

## Prediction verdicts

| Prediction | Statement (verbatim scope) | Verdict |
|---|---|---|
| **S1-P1** | in every LOCO fold, every plain-baseline family error ≥ 0.40 | **MET** — minimum plain-baseline fold error 0.5577 (`baseline_claude`, leave-out `formula_1`), 0 violations over 9 folds × 4 arms |
| **S1-P2** | in every LOCO fold, `governance_informed` error < every plain-baseline error, and `mechanism` = 0 errors | **MET** — 0 violations over 9 folds × 4 comparisons; tightest margin 0.5577 − 0.4231 = 0.1346 (leave-out `formula_1` vs `baseline_claude`); `mechanism` 0 errors in all 9 folds |
| **S1-P3** | in every LOCO fold, `governance_informed` error ≥ 0.35 | **MET** — minimum fold error 0.4151 (leave-out `codebase_community`) |

No prediction miss. (Per the prereg publication rule, a miss would have been
reported as MISSED_PREDICTION; none occurred.)

## (a) LOCO — leave-one-database-out, 9 folds, all 9 arms

Fold = drop all questions of one database; error rate over the remaining
questions. Full sample n=60; per-fold n_kept in brackets.

| left-out DB (n_kept) | b_claude | b_qwen | b_deepseek | b_minimax | triv_claude | triv_v2 | triv_v3 | gov_informed | mechanism |
|---|---|---|---|---|---|---|---|---|---|
| california_schools (54) | 0.5741 | 0.7407 | 0.7037 | 0.7778 | 0.5185 | 0.5741 | 0.6296 | 0.4815 | 0.0000 |
| card_games (53) | 0.6415 | 0.7358 | 0.7925 | 0.7925 | 0.5472 | 0.5849 | 0.6792 | 0.4528 | 0.0000 |
| codebase_community (53) | 0.5660 | 0.6981 | 0.6981 | 0.7358 | 0.4906 | 0.5472 | 0.6415 | 0.4151 | 0.0000 |
| debit_card_specializing (53) | 0.6226 | 0.6792 | 0.7170 | 0.7358 | 0.5472 | 0.6038 | 0.6981 | 0.5094 | 0.0000 |
| european_football_2 (54) | 0.6296 | 0.7407 | 0.7778 | 0.8148 | 0.5741 | 0.5926 | 0.6852 | 0.4444 | 0.0000 |
| financial (52) | 0.6154 | 0.7308 | 0.7308 | 0.7885 | 0.5192 | 0.6154 | 0.6923 | 0.5192 | 0.0000 |
| formula_1 (52) | 0.5577 | 0.7115 | 0.7308 | 0.7500 | 0.5385 | 0.5769 | 0.6346 | 0.4231 | 0.0000 |
| thrombosis_prediction (54) | 0.5741 | 0.7222 | 0.7407 | 0.7593 | 0.5185 | 0.5556 | 0.6481 | 0.4630 | 0.0000 |
| world_1 (55) | 0.6182 | 0.6909 | 0.7091 | 0.7455 | 0.5455 | 0.6000 | 0.6909 | 0.4909 | 0.0000 |
| **full sample (60)** | 0.6000 | 0.7167 | 0.7333 | 0.7667 | 0.5333 | 0.5833 | 0.6667 | 0.4667 | 0.0000 |

Ranges across folds: plain-baseline family min 0.5577 / max 0.8148;
`governance_informed` min 0.4151 / max 0.5192; `mechanism` identically 0.
The ordering plain > trivial-family > governance_informed > mechanism = 0
holds in every fold, and `governance_informed` < the *best* plain baseline in
every fold — no single database carries the headline gap.

## (b) Database-level bootstrap restatement (B=2000, seed 20260820)

Consistency restatement of the frozen cluster bootstrap (frozen run: same
algorithm, seed 20260731). Algorithm byte-mirrors
`make_pilot2_summary.bootstrap()`: fresh `random.Random(20260820)` per arm,
9 sorted cluster names resampled with replacement, error rate over the
concatenated questions, ci95 = [rates[49], rates[1949]] of the sorted 2000.

| arm | err | ci95 (seed 20260820, this study) | ci95 (frozen, seed 20260731) |
|---|---|---|---|
| baseline_claude | 0.6000 | [0.4464, 0.7500] | [0.4407, 0.7460] |
| baseline_qwen | 0.7167 | [0.6066, 0.8393] | [0.6102, 0.8333] |
| baseline_deepseek | 0.7333 | [0.5574, 0.8814] | [0.5667, 0.8852] |
| baseline_minimax | 0.7667 | [0.6140, 0.9000] | [0.6271, 0.8983] |
| trivial_claude | 0.5333 | [0.4098, 0.6508] | [0.4068, 0.6452] |
| trivial_v2 | 0.5833 | [0.4762, 0.7000] | [0.4828, 0.6935] |
| trivial_v3 | 0.6667 | [0.5333, 0.7969] | [0.5273, 0.8033] |
| governance_informed | 0.4667 | [0.2833, 0.6333] | [0.2857, 0.6393] |
| mechanism | 0.0000 | [0.0000, 0.0000] | [0.0000, 0.0000] |

Consistent: every endpoint moves by < 0.014 under the new seed; every
qualitative statement of the paper (separation of the plain family from
`governance_informed`; `mechanism` at 0) is unchanged. As pre-registered,
this is a consistency check, not new evidence.

## (c) Question-level jackknife — two headline arms (n=60)

| arm | err (count) | jackknife SE | 95% CI (normal approx) | leave-one-out min/max |
|---|---|---|---|---|
| baseline_claude | 0.6000 (36/60) | 0.063779 | [0.4750, 0.7250] | 0.5932 / 0.6102 |
| governance_informed | 0.4667 (28/60) | 0.064950 | [0.3394, 0.5940] | 0.4576 / 0.4746 |

No single question moves either headline arm by more than 0.017 absolute
(1/59). The jackknife CIs are slightly narrower than the cluster-bootstrap
CIs, as expected: the bootstrap respects database clustering; the jackknife
treats questions as exchangeable. The cluster bootstrap remains the
inference of record; the jackknife is the pre-registered supplementary view.

## Method note (exact reproduction status)

1. **Sandbox reproduction (step 1 of protocol)**: in the disposable sandbox
   copy (`.../scratchpad/poststudy-sandbox/`), `./reproduce_all.sh light`
   completed with **PASS=20 FAIL=0**, including byte-identical regeneration of
   `pilot2/pilot2_summary.json`, `pilot2/pilot2_arms_summary.json`,
   `paper/figures/fig_data_pilot2.json`, `tab_main_results.tex`(+audit),
   `tab_benchmark.tex`(+audit) and `tab_divergence.tex`, plus stage-0 paper
   gates `check_numbers.py` (426 assertions) and `check_redlines.py` (117)
   both PASS. Scoring re-executed every cached SQL against the 9 in-tree
   warehouses; **zero LLM calls**. Environment: python 3.9.6, duckdb 1.4.4
   (reference environment of `requirements.txt`).
2. **Byte-diff against the committed matrix**: the sandbox-regenerated
   `pilot2_arms_summary.json` was additionally `cmp`-verified byte-identical
   to the frozen committed copy at
   `/Volumes/SSD 1/explore_opportunity_cc/pilot2/pilot2_arms_summary.json`;
   the analysis driver re-asserts this byte-equality at load time
   (sha256 of both copies recorded in `loco_report.json → matrix_source`).
3. **Matrix source (step 2)**: the per-question × per-arm correctness matrix
   is taken directly from the frozen summary's `per_question_verdicts`
   (60 qids × 9 arms; produced by the frozen scorer
   `make_pilot2_summary.py`, itself importing sha-asserted
   `pilot/run_pilot.py`). No instrumentation of frozen modules was needed;
   no frozen file was modified or re-scored outside the sandbox.
4. **qid → database mapping** read from the frozen
   `pilot2/domains/*/questions.json` (9 DBs; cluster sizes 6,7,7,7,6,8,8,6,5).
5. Error definition throughout: `verdict != "correct"` — identical to the
   frozen scorer's error definition (all five error verdicts counted).
6. Determinism: the driver is seed-fixed (bootstrap seed 20260820 per
   prereg) and re-runnable; re-running overwrites only the two files in this
   directory.
