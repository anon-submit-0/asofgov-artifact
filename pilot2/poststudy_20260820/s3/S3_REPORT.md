# S3 — Repetition study (LLM, paid; k=4 new reps per arm)

- **Governing prereg**: `PREREG_poststudy_20260820.md`,
  sha256 `f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24`
  (recomputed from disk by the generator before any analysis).
- **Study date**: 2026-08-20 (smoke 14:39, full run 15:08–16:21 local). 480 paid LLM calls total (2 arms × 4 new reps × 60 questions; rep1 := the frozen main-study run, reused not re-run). All outputs append-only under `pilot2/poststudy_20260820/s3/`; no frozen file modified.
- **Machine-readable twin**: [`s3_summary.json`](s3_summary.json)
  (every number in this file). Generator:
  [`make_s3_summary.py`](make_s3_summary.py). Run harness:
  [`rep_harness.py`](rep_harness.py); side log:
  [`call_log.jsonl`](call_log.jsonl); smoke record:
  [`S3_SMOKE.md`](S3_SMOKE.md).
- **Protocol**: claude-opus-4-6 (frozen gateway channel; protocol byte-identical to the frozen runs, see rep_harness.py); scoring: frozen chain (R2.fetch_and_score at run time; verdicts read from caches here, rep1 verdicts asserted equal to frozen pilot2_arms_summary.json per_question_verdicts)
- **Prompt byte-identity**: all 480 rep2–5 cache records match their frozen rep1 record on `prompt_sha256` + `prompt_chars` (re-asserted by this generator; the harness additionally asserted it before every paid call).

## Prediction verdicts

| Prediction | Statement (verbatim scope) | Verdict |
|---|---|---|
| **S3-P1** | every baseline_claude rep error within 0.600 +/- 0.10 | **MET** — per-rep errors 36/37/35/36/37 of 60 (rates 0.6000, 0.6167, 0.5833, 0.6000, 0.6167), all within 30–42 questions (= 0.6000 ± 0.10) |
| **S3-P2** | every governance_informed rep error within 0.467 +/- 0.10 | **MET** — per-rep errors 28/25/26/26/26 of 60 (rates 0.4667, 0.4167, 0.4333, 0.4333, 0.4333), all within 22–34 questions (= 0.4667 ± 0.10) |
| **S3-P3** | baseline_claude error > governance_informed error in every rep | **MET** — margin (baseline − governance) per rep: +8, +12, +9, +10, +11 questions; ordering holds in 5/5 reps |
| **S3-P4** | pooled per-question flip rate (per arm) < 0.15 | **MET** — `baseline_claude` 4/60 = 0.0667, `governance_informed` 8/60 = 0.1333, both < 0.15 |

No prediction miss. (Per the prereg publication rule, a miss would
have been reported as MISSED_PREDICTION; none occurred.)

## Per-rep results

Error = verdict ≠ `correct` (frozen scorer semantics). Verdict-class
key: wv = wrong_value, xe = execution_error, asr =
answered_should_refuse, rsa = refused_should_answer, ns = no_sql.

### `baseline_claude`

| rep | errors/60 | error rate | empty | correct | wv | xe | asr | rsa | ns | vs rep1: agree (correctness) | flips vs rep1 (→correct / →wrong) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1* | 36 | 0.6000 | 1 | 24 | 15 | 4 | 11 | 5 | 1 | —(reference) | — |
| 2 | 37 | 0.6167 | 0 | 23 | 18 | 2 | 11 | 6 | 0 | 59/60 = 0.9833 | 0 / 1 |
| 3 | 35 | 0.5833 | 0 | 25 | 16 | 2 | 11 | 6 | 0 | 57/60 = 0.9500 | 2 / 1 |
| 4 | 36 | 0.6000 | 0 | 24 | 19 | 2 | 11 | 4 | 0 | 58/60 = 0.9667 | 1 / 1 |
| 5 | 37 | 0.6167 | 0 | 23 | 17 | 3 | 11 | 6 | 0 | 57/60 = 0.9500 | 1 / 2 |

Errors across the 5 reps: min 35, max 37, mean 36.2. (*rep1 = frozen main-study run.)

### `governance_informed`

| rep | errors/60 | error rate | empty | correct | wv | xe | asr | rsa | ns | vs rep1: agree (correctness) | flips vs rep1 (→correct / →wrong) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1* | 28 | 0.4667 | 0 | 32 | 8 | 9 | 10 | 1 | 0 | —(reference) | — |
| 2 | 25 | 0.4167 | 0 | 35 | 9 | 4 | 11 | 1 | 0 | 53/60 = 0.8833 | 5 / 2 |
| 3 | 26 | 0.4333 | 0 | 34 | 10 | 3 | 11 | 2 | 0 | 54/60 = 0.9000 | 4 / 2 |
| 4 | 26 | 0.4333 | 0 | 34 | 9 | 3 | 11 | 3 | 0 | 54/60 = 0.9000 | 4 / 2 |
| 5 | 26 | 0.4333 | 0 | 34 | 9 | 4 | 10 | 3 | 0 | 54/60 = 0.9000 | 4 / 2 |

Errors across the 5 reps: min 25, max 28, mean 26.2. (*rep1 = frozen main-study run.)

## Stability: pooled per-question flip sets

A question *flips* iff its correctness is not constant across all 5
reps (rep1 + reps 2–5) — the pooled definition adjudicated in S3-P4.

| arm | flips | flip rate | flip qids |
|---|---|---|---|
| `baseline_claude` | 4/60 | 0.0667 | `CA-Q4`, `F1-Q5`, `FIN-Q1`, `W1-Q4` |
| `governance_informed` | 8/60 | 0.1333 | `CA-Q1`, `DEB-Q6`, `EF2-Q6`, `F1-Q1`, `F1-Q4`, `F1-Q5`, `TH-Q4`, `W1-Q4` |

108 of the 120 (arm, question) cells are perfectly stable across all
five reps; correctness, not the verbatim verdict class, is the unit
(a cell that moves e.g. wrong_value → execution_error does not flip).

## Ordering and reference-error elimination per rep

| rep | baseline errors | governance errors | margin | baseline > governance | governance eliminates of the frozen 36 reference errors |
|---|---|---|---|---|---|
| 1* | 36 | 28 | +8 | yes | 13/36 = 0.3611 |
| 2 | 37 | 25 | +12 | yes | 15/36 = 0.4167 |
| 3 | 35 | 26 | +9 | yes | 15/36 = 0.4167 |
| 4 | 36 | 26 | +10 | yes | 15/36 = 0.4167 |
| 5 | 37 | 26 | +11 | yes | 14/36 = 0.3889 |

Reference set = the frozen `baseline_claude` rep1 error qids
(`pilot2_arms_summary.json` → `reference_error_qids`); the rep1 row
re-derives the frozen `eliminated_by.governance_informed` value and is
asserted equal to it. Elimination in reps 2–5 is computed against the
SAME frozen reference set (not against each rep's own baseline errors),
so it reads as: how much of the frozen headline's error mass does the
governance arm remove, under resampling of the governance arm alone.

## Latency and attempts (from `call_log.jsonl`)

| phase / arm | calls | latency s (min / median / mean / p95 / max) | attempts (max, calls-with-retry) | prompt tok | completion tok | empty |
|---|---|---|---|---|---|---|
| full run `baseline_claude` | 239 | 4.413 / 6.622 / 6.987 / 9.609 / 28.889 | max 1, 0 retried | 454636 | 20163 | 0 |
| full run `governance_informed` | 239 | 4.835 / 7.94 / 11.077 / 37.487 / 52.1 | max 2, 1 retried | 2223392 | 19859 | 0 |
| full run overall | 478 | 4.413 / 7.225 / 9.032 / 27.421 / 52.1 | max 2, 1 retried | 2678028 | 40022 | 0 |
| smoke `baseline_claude` (14:39) | 1 | 41.156 | 1 attempt(s) | — | — | — |
| smoke `governance_informed` (14:42) | 1 | 176.333 | 3 attempt(s) | — | — | — |

## Operational note

- **Gateway slowness at smoke time, recovered by run time**: at the
  smoke check (14:39) the frozen `tuzi` channel was slow —
  the governance smoke call took 176.333 s and 3 attempts
  (first attempts empty/timeout; the protocol-internal empty-retry ×3
  absorbed it). In the full run the governance-arm median latency was
  7.94 s, and 1 of 478 full-run calls needed any retry.
- **Zero empty completions in the full new run**: 0 `empty_response`
  caches across all 4 new reps of both arms (480 paid calls; per-rep counts in the
  tables above). The 1 frozen-rep1 empty cache(s) (`baseline_claude`: `CODE-Q6`) are a main-study artifact already
  disclosed in the frozen `pilot2_arms_summary.json` `empty_responses`; this
  generator asserts the rep1 empty sets equal that frozen disclosure.
- **Circuit breaker never tripped**: the driver ([`s3_driver.sh`](s3_driver.sh)) stops if a
  finished governance rep exceeds 9/60 empty responses; observed per-rep
  governance empties {rep2: 0, rep3: 0, rep4: 0, rep5: 0} — driver ran to `S3 DRIVER COMPLETE`
  (asserted from `driver.log`, which contains no `CIRCUIT BREAKER` line;
  the per-rep counts logged by the driver are asserted equal to a fresh
  recount from the caches).

## The frozen rep is governance_informed's worst rep

The frozen main-study rep1 has 28 governance-arm errors; every new rep has fewer (25–26). The frozen `baseline_claude` rep1 (36 errors) sits inside its new-rep range (35–37).
The paper's frozen headline gap (0.6000 vs 0.4667) is therefore **conservative** with respect to repetition variance: every new rep also widens the baseline−governance margin (+8 frozen vs +9–+12 new), none narrows it.

---
*Post-registration study. Generated deterministically by `make_s3_summary.py` from the frozen rep1 caches, the rep2–5 caches, `call_log.jsonl`, `driver.log`, `s3_driver.sh`, and `pilot2_arms_summary.json`; every number above is read from `s3_summary.json`.*
