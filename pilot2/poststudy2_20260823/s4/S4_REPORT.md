# S4 — Paired-difference uncertainty (deterministic)

Governing prereg: `PREREG_poststudy2_20260823.md`, sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669` (re-asserted from disk at run time). Zero LLM calls; every number below is computed by `s4_paired_ci.py` from frozen inputs and read back out of `s4_summary.json`.

## Inputs

- Verdict matrix: pilot2/pilot2_arms_summary.json per_question_verdicts (frozen rep1) (sha256 `2604bff0e7632c0e…`)
- Clusters: pilot2/domains/*/questions.json (9 databases)
- S3 rep caches: pilot2/poststudy_20260820/s3/runs_rep/governance_informed/rep{2..5}; frozen s3_summary.json sha256 `053ffb62c3e62042…`
- Reference arm: `baseline_claude` with 36 frozen errors (error set re-derived from the matrix and asserted equal to the frozen list).

## (a) Paired per-question error differences, cluster-bootstrap 95% CIs

Difference direction: reference − arm (positive = arm makes fewer errors). Bootstrap: database cluster (9 domains), B=2000, seed 20260823, 95% percentile, [sorted[49], sorted[1949]] of B=2000 (frozen convention).

| arm | ref errs | arm errs | mean paired diff | 95% CI | excludes 0 | discordant (ref-err/arm-ok, ref-ok/arm-err) |
|---|---|---|---|---|---|---|
| governance_informed | 36 | 28 | 0.1333 | [-0.0500, 0.3000] | no | 13 / 5 |
| trivial_claude | 36 | 32 | 0.0667 | [-0.0462, 0.1774] | no | 8 / 4 |
| trivial_v2 | 36 | 35 | 0.0167 | [-0.1017, 0.1167] | no | 6 / 5 |
| trivial_v3 | 36 | 40 | -0.0667 | [-0.1429, -0.0152] | yes | 2 / 6 |

Sign note: arm−reference is the exact negation of reference−arm; whether a CI includes 0 is invariant to the sign convention, so S4-P2 is adjudicated on the reference−variant CIs above.

Per-cluster mean paired differences (reference − arm):

| arm | california_schools | card_games | codebase_community | debit_card_specializing | european_football_2 | financial | formula_1 | thrombosis_prediction | world_1 |
|---|---|---|---|---|---|---|---|---|---|
| governance_informed | 0.5000 | -0.2857 | 0.0000 | 0.2857 | -0.3333 | 0.3750 | 0.1250 | 0.3333 | 0.2000 |
| trivial_claude | 0.1667 | -0.1429 | 0.0000 | 0.0000 | 0.1667 | -0.1250 | 0.3750 | 0.1667 | 0.0000 |
| trivial_v2 | 0.1667 | -0.2857 | 0.0000 | 0.0000 | -0.1667 | 0.1250 | 0.2500 | 0.0000 | 0.0000 |
| trivial_v3 | -0.1667 | -0.2857 | 0.0000 | 0.0000 | -0.1667 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## (b) Elimination-uncertainty restatement (five S3 reps)

Elim = fraction of the 36 frozen reference errors the governance-informed arm answers correctly in a given rep. Re-derived here from the rep caches and asserted equal to the frozen `s3_summary.json` values (`reasserted_equal_to_frozen_s3_summary = True`).

| rep | eliminated | frac | source |
|---|---|---|---|
| 1 | 13/36 | 0.3611 | frozen pilot2_arms_summary.json per_question_verdicts |
| 2 | 15/36 | 0.4167 | poststudy_20260820/s3/runs_rep/governance_informed/rep2/ |
| 3 | 15/36 | 0.4167 | poststudy_20260820/s3/runs_rep/governance_informed/rep3/ |
| 4 | 15/36 | 0.4167 | poststudy_20260820/s3/runs_rep/governance_informed/rep4/ |
| 5 | 14/36 | 0.3889 | poststudy_20260820/s3/runs_rep/governance_informed/rep5/ |

Min–max range: [0.3611, 0.4167]; pre-registered line 0.4; band [0.3, 0.45]. All reps in band: yes; range straddles the 0.4 line: yes. The frozen case-(iii) call (rep1 elim 0.3611 < 0.40) sits inside a rep-to-rep band that crosses the line — boundary-honest, not comfortable, exactly as pre-registered.

## Pre-registered predictions

- **S4-P1** — the reference−governance paired-difference CI excludes 0: **MISS**
  - mean 0.1333, CI [-0.0500, 0.3000]
- **S4-P2** — every variant−reference paired-difference CI includes 0: **MISS**
  - trivial_claude: mean 0.0667, CI [-0.0462, 0.1774], includes 0: yes
  - trivial_v2: mean 0.0167, CI [-0.1017, 0.1167], includes 0: yes
  - trivial_v3: mean -0.0667, CI [-0.1429, -0.0152], includes 0: no
- **S4-P3** — per-rep elim values all lie in [0.30, 0.45] and the min–max range straddles the pre-registered 0.40 line: **MET**
  - per-rep fracs [0.3611, 0.4167, 0.4167, 0.4167, 0.3889], min 0.3611, max 0.4167

Predictions missed: 2/3. A miss is published as a miss.
