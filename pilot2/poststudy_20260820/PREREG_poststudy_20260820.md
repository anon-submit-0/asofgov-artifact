# PREREG — Post-registration robustness studies (S1/S2/S3)

**Written and frozen 2026-08-20, BEFORE any study below is run.**
Status: post-registration relative to `PREREG_pilot2_arms.md` (frozen
2026-08-04). Every frozen result of the main study was known when this
document was written; nothing in the frozen evidence
(`pilot2/runs/`, `pilot2/*.json`, `impl/certs2/`) is modified by these
studies — all outputs are append-only under `pilot2/poststudy_20260820/`.
Motivation: three anticipated review objections — (i) n=60 sufficiency,
(ii) no non-LLM temporal-SQL comparison arm, (iii) single-run LLM variance.
Predictions below are best guesses stated in advance; misses will be
published exactly as the main study published its prediction misses.

## S1 — Subset robustness of the frozen score matrix (deterministic, zero LLM)

Method: reconstruct the per-question × per-arm correctness matrix from the
frozen caches with the frozen scorer semantics (re-execution path identical
to `make_pilot2_summary.py`, run in an isolated sandbox; committed JSONs
byte-diffed untouched). Compute, for all 9 arms:
(a) leave-one-database-out (LOCO, 9 folds) error rates;
(b) database-level bootstrap (B=2000, seed 20260820) — this restates the
frozen cluster bootstrap and is a consistency check, not new evidence;
(c) question-level jackknife on the two headline arms.

Predictions:
- **S1-P1**: in every LOCO fold, every plain-baseline family error ≥ 0.40
  (the frozen pre-registered line A′).
- **S1-P2**: in every LOCO fold, `governance_informed` error < every
  plain-baseline error, and `mechanism` = 0 errors.
- **S1-P3**: in every LOCO fold, `governance_informed` error ≥ 0.35.

## S2 — Governance-blind temporal-SQL arms (deterministic, zero LLM)

Two hand-built arms operationalising "temporal-SQL machinery without the
governance axis" (the claim added to §9 of the paper body). Independent
implementation: imports nothing from `impl/asof_compiler/` or
`impl/asof_verifier/` (asserted the same way the verifier asserts
import-disjointness). Inputs per question: the structured fields of
`questions.json` EXCLUDING `gold_sql`, `gold_value`, `expected_kind`,
`refusal_*`, `rewrite`, `pinned_version`; plus the **latest committed
version's** metric leg/anchor/route rows from `gov_seed` (an engineer who
knows the current definition); plus the warehouse.
- **TSQL-W** (same-window, latest-version, guard-free): applies the
  question's requested window to both legs on their latest-version anchors;
  always answers a number; never refuses, never rewrites, never checks
  version-in-effect, coverage, admissibility or disclosure.
- **TSQL-H** (all-history at T): each leg aggregated over all valid rows
  dated ≤ `as_of` (the classic time-travel dashboard reading; Fig 1 bottom
  row generalised).

Scoring: byte-identical rules to the frozen LLM-arm scorer (0.5% relative
tolerance, multiset/string forms, refusal question answered-with-number =
error, rewrite questions scored with the same concessions incl. the five
hull-trim freebies). Per-question ledger published.

Predictions:
- **S2-P1**: both arms answer 60/60 (zero refusals) → 0/15 correct on
  refusal questions.
- **S2-P2**: TSQL-W total error in [0.35, 0.60]; TSQL-H error ≥ TSQL-W.
- **S2-P3**: on the four version-flip pairs, latest-version binding errs on
  ≥2 of the 4 off-version sides (one pair is inside scoring tolerance by
  the frozen main-study finding and may credit a blind answer).
- **S2-P4**: TSQL-W value-question (n=33) error ≤ the best plain LLM
  baseline's value-question error (correct valid-time binding is most of
  what the value split needs when governance does not move the answer).

## S3 — Repetition study (LLM, paid; k=4 new runs per arm)

Arms: `baseline_claude` and `governance_informed` only (the two arms
carrying the headline), model `claude-opus-4-6` through the same gateway
CLI, protocol byte-identical to the frozen runs (temperature unset, one
sample, retry only on empty completion ×3, 512-token cap, same prompts from
`prompt_pack/`). New caches under
`poststudy_20260820/runs_rep/<arm>/rep{2..5}/<qid>.json` (rep1 := the
frozen main-study run, reused not re-run). Frozen caches untouched.

Predictions:
- **S3-P1**: every `baseline_claude` rep error within 0.600 ± 0.10.
- **S3-P2**: every `governance_informed` rep error within 0.467 ± 0.10.
- **S3-P3**: `baseline_claude` error > `governance_informed` error in
  every rep.
- **S3-P4**: pooled per-question flip rate (fraction of questions whose
  correctness differs across reps, per arm) < 0.15.

## Publication rule

All three studies land in the technical report and the artifact
(`poststudy_20260820/`), each labelled post-registration with this
document's sha256. The paper body may cite their numbers only via
equal-length sentence swaps (the body is at 12.001/12.00 pages with zero
slack) and only with the post-registration label. A prediction miss is
published as a miss.
