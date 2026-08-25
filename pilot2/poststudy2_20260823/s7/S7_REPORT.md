# S7 — NL→σ arm, Stage B full run (post-registration report)

- Governing prereg: `PREREG_poststudy2_20260823.md`, sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669`
- Extractor model: `claude-opus-4-6` (llmhub, channel `tuzi` asserted at preflight); 1 sample + 1 format-retry; hard call budget 120
- Bridge: extracted σ → frozen `impl/asof_compiler` (Pilot2Adapter) → frozen `acceptance_pilot2` gate-1 scoring rules
- Arm purity: questions loaded 3-key-stripped ({qid, domain, question_zh}); prompt-leak preflight over gold-side fields passed before any call
- This run: 57 LLM calls, 3 cache hits (the 3 Stage-A smoke questions were cache-skipped, never re-called)
- Caches: `s7/runs_sigma/<qid>.json` (append-only, refuse-overwrite); raw harness output `s7_nl2sigma_full.json`; adjudication `s7_summary.json` + `s7_ledger.json` (this report is rendered from those two JSONs only)

## Stage-B fix-forward changes to the Stage-A harness (documented)

1. Cache directory repointed `runs_nl2sigma/` → `runs_sigma/` to match the Stage-B tasking; the 3 smoke caches were copied in byte-identical (originals retained; append-only).
2. The full run now passes the hard call budget explicitly (`budget=120` = 60 questions × structural max 2 calls).
3. The Stage-A harness was preserved byte-for-byte as `nl2sigma_harness_stageA_orig.py` before editing.

No prompt, schema, scoring, or bridging logic changed between the Stage-A smoke and this full run.

## Headline numbers

| quantity | value |
|---|---|
| questions | 60 |
| exact full-σ recovery | 40/60 |
| end-to-end correct | 55/60 |
| end-to-end error | 5/60 |
| metric-identity (metric_alias) recovery | 58/60 |
| extraction errors (invalid JSON after retry) | 0 |
| compile errors (σ crashed frozen compiler) | 2 |
| format-retried questions | 0 |

Frozen reference points (for context): governance-informed arm error 28/60; backbone error 36/60.

## Prediction adjudication (exactly as pre-registered)

### S7-P1 — **MET**
> exact full-σ recovery on >= 36/60 questions
Observed: exact full-σ recovery 40/60 vs threshold ≥ 36.

### S7-P2 — **MET**
> end-to-end error <= 28/60 (the governance-informed arm's)
Observed: end-to-end error 5/60 vs threshold ≤ 28.

### S7-P3 — **MET**
> on questions with exact σ recovery, end-to-end error = 0 (compiler correctness transfers)
Observed: 40 exact-σ questions, 0 of them scored error.

### S7-P4 — **MET**
> metric-identity recovery >= 54/60 (>=90%); failures concentrate in window/scope/version fields, not metric identity
Observed: metric_alias recovery 58/60 vs threshold ≥ 54; metric_alias mismatches 2 vs window/scope/version-field mismatches 2 (fields: window_request, cross_window, scope, pinned_version); concentration clause holds.

Descriptive (outside the gate): `as_of` — a time-point field outside the window/scope/version family — is the single largest mismatch field at 16/60; see the per-field table and the ledger for the mismatch content.

**Predictions met: 4/4.** Misses above are published as misses.

## Per-field σ-recovery accuracy

| field | match | mismatch |
|---|---|---|
| `as_of` | 44/60 | 16 |
| `declared_at` | 60/60 | 0 |
| `metric_alias` | 58/60 | 2 |
| `scope` | 59/60 | 1 |
| `pinned_version` | 60/60 | 0 |
| `cross_window` | 60/60 | 0 |
| `anchor_override` | 59/60 | 1 |
| `window_request` | 59/60 | 1 |
| `requested_granularity` | 60/60 | 0 |
| `requested_time_gran` | 59/60 | 1 |
| `presentation` | 56/60 | 4 |
| `ctx_role` | 60/60 | 0 |
| `periods` | 60/60 | 0 |

## By domain

| domain | n | exact σ | e2e correct | e2e error |
|---|---|---|---|---|
| california_schools | 6 | 4 | 4 | 2 |
| card_games | 7 | 6 | 7 | 0 |
| codebase_community | 7 | 4 | 5 | 2 |
| debit_card_specializing | 7 | 2 | 7 | 0 |
| european_football_2 | 6 | 6 | 6 | 0 |
| financial | 8 | 7 | 8 | 0 |
| formula_1 | 8 | 8 | 8 | 0 |
| thrombosis_prediction | 6 | 3 | 5 | 1 |
| world_1 | 5 | 0 | 5 | 0 |

## By gold kind

| gold kind | n | exact σ | e2e correct | e2e error |
|---|---|---|---|---|
| refusal | 15 | 7 | 14 | 1 |
| rewrite | 12 | 7 | 8 | 4 |
| value | 33 | 26 | 33 | 0 |

## Error ledger (all questions scored error)

| qid | gold kind | outcome | why | σ mismatched fields |
|---|---|---|---|---|
| CA-Q5 | rewrite | compile_error | compile_error | as_of, presentation |
| CA-Q6 | refusal | compile_error | compile_error | anchor_override, as_of, scope |
| CODE-Q4 | rewrite | refusal(disclosure-blocked/) | expected rewrite, got refusal disclosure-blocked | presentation |
| CODE-Q5 | rewrite | refusal(disclosure-blocked/) | expected rewrite, got refusal disclosure-blocked | presentation |
| TH-Q3 | rewrite | refusal(disclosure-blocked/) | expected rewrite, got refusal disclosure-blocked | as_of, presentation, window_request |

## Full per-question ledger

See `s7_ledger.json` (per question: extracted σ, 13-field match vector, compile outcome, gold kind, verdict).
