# PREREG — Post-registration studies, second battery (S4/S5/S6/S7)

**Written and frozen 2026-08-23, BEFORE any study below is run.**
Post-registration relative to `PREREG_pilot2_arms.md` (2026-08-04) and
`PREREG_poststudy_20260820.md` (2026-08-20, sha `f2fb136a…`); every frozen
result of both was known when this was written. Motivation: the four
review conditions raised by the simulated four-round review loop and
legitimately declined there as new experiments — paired-difference
uncertainty (R1-EXP-6), cost scalability (R3-1-2), an English-question
control (R1-EXP-5/R3-1-3), and an NL→σ arm (R1-EXP-3). Frozen evidence
(`pilot2/runs/`, `pilot2/*.json`, `impl/certs2/`, both poststudy caches)
stays byte-untouched; all outputs are append-only under
`pilot2/poststudy2_20260823/`. Predictions are stated in advance; misses
are published as misses.

## S4 — Paired-difference uncertainty (deterministic, zero LLM)

From the frozen per-question verdict matrix: cluster-bootstrap (9 database
clusters, B=2000, seed 20260823) 95% CIs on the **paired per-question error
differences** for reference−governance and reference−each prompt variant;
and an elimination-uncertainty restatement using the five S3 reps (elim of
the 36 frozen reference errors per rep).

- **S4-P1**: the reference−governance paired-difference CI excludes 0.
- **S4-P2**: every variant−reference paired-difference CI includes 0.
- **S4-P3**: per-rep elim values all lie in [0.30, 0.45] and the min–max
  range straddles the pre-registered 0.40 line (the case-(iii) call is
  boundary-honest, not comfortable).

## S5 — Cost-model scalability sweep (deterministic, zero LLM)

Operationalises the §3 cost claims on scaled substrates, in an isolated
workspace (never the frozen warehouses). **Row-scale axis** (mandatory):
`financial` with `trans` scaled to {12.5%, 25%, 50%, 100%, 200%, 400%}
(sampling below 1×, row duplication with key remapping above 1×); on each
substrate re-compile the financial questions' certificates with the frozen
compiler and measure warm answer/verify cost per `impl/measure_cost.py`
methodology. **Window-span axis** (stretch goal): `world_1` (84-month
authored history) with request windows spanning {1, 3, 6, 12, 24, 48}
months. If an axis point is unreachable (e.g., gold anchors vanish under
sampling), report the point as unreachable with the reason — no silent
truncation.

- **S5-P1**: warm verify median is monotone non-decreasing in row scale
  with growth at most linear (4× rows ⇒ ≤ 4× median verify time).
- **S5-P2**: the paired verify/answer ratio stays inside [1×, 60×] at
  every reachable scale point.
- **S5-P3**: zero full-scan audits at every scale (all clause-(iv) audits
  window-bounded, as at 1×).

## S6 — English-question control (LLM; translations + 2 arms × 60)

**Translations first, frozen before any scored call**: all 60
`question_zh` translated to English by an LLM, then independently audited
question-by-question for gold-invariance (as-of instant, declared-at
instant, window phrase, metric alias meaning, version-pin phrasing all
preserved; no content added; the frozen string-level leak audit re-run
over the English texts). The audited set is sha256-frozen. Then
`baseline_claude` and `governance_informed` run on the English questions
under the byte-frozen protocol (same model `claude-opus-4-6`, same prompt
assembly with only the question text swapped, one sample, retry only on
empty ×3, 512-token cap), caches append-only under
`poststudy2_20260823/s6/runs_en/`.

- **S6-P1**: English backbone error within 0.600 ± 0.10.
- **S6-P2**: English governance-informed error within 0.467 ± 0.10.
- **S6-P3**: backbone error > governance error in English.
- **S6-P4**: of the 7 probe-only refusal questions, the English
  governance arm still errs ≥ 4 (the probe-dependence mechanism is not
  language-bound).

## S7 — NL→σ arm (LLM; 60 extraction calls + frozen compiler)

The hybrid the paper's architecture implies: a model extracts the
structured intent σ from the question text; the frozen binding compiler
does the rest. Extractor: `claude-opus-4-6`, given the schema pack + the
governance pack (same context family as the governance-informed arm) + a
σ-format specification, and the `question_zh` text ONLY — every σ field
(as-of, declared-at, metric id, scope, windows, version pin, presentation,
role, periods) must come from the model's output; none may be copied from
`questions.json` (the arm code must not read `gold_sql`, `gold_value`,
`expected_kind`, `refusal_*`, `rewrite`, nor any σ field as input to the
arm). Invalid JSON gets one format-retry, then scores as error. Extracted
σ feeds the same pilot2 compiler adapter; end-to-end outcomes scored under
the frozen rules. Report σ-recovery accuracy per field and end-to-end
error, with the per-question ledger.

- **S7-P1**: exact full-σ recovery on ≥ 36/60 questions.
- **S7-P2**: end-to-end error ≤ 28/60 (the governance-informed arm's).
- **S7-P3**: on questions with exact σ recovery, end-to-end error = 0
  (compiler correctness transfers).
- **S7-P4**: metric-identity recovery ≥ 54/60 (≥90%) — failures
  concentrate in window/scope/version fields, not metric identity.

## Publication rule

All four studies land in the TR and the artifact
(`poststudy2_20260823/`), labelled post-registration with this document's
sha256. Paper-body citation only through gate-asserted, length-paid
sentences. A prediction miss is published as a miss.
