# S6 — English-question control · Stage B report

- PREREG: `PREREG_poststudy2_20260823.md` sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669` (read first; §S6 governs; zero design freedom).
- Frozen EN question set: `s6/questions_en.json` sha256 `d9508f3f6e1617e080772630f51f6d1860cd0cfe1dae174b7f226ada548ba63f` (Stage A freeze, verified before every call).
- Protocol: model `claude-opus-4-6`, one sample, retry only on empty x3, 512-token cap, temperature unset.
- **Single delta** vs the byte-frozen protocol: question text = frozen question_en (all else byte-frozen R2/RP chain).
- Scoring: frozen R2.fetch_and_score (RP.score + §4.2 rowset/string dispatch).
- Caches: `s6/runs_en/<arm>/<qid>.json`, append-only (overwrite refused); call metadata in `s6/call_log_en.jsonl` (never in cache records).

## Headline result

| arm | EN errors /60 | EN error rate | ZH errors /60 (frozen) | ZH error rate |
|---|---|---|---|---|
| baseline_claude | 35 | 0.5833 | 36 | 0.6000 |
| governance_informed | 29 | 0.4833 | 28 | 0.4667 |

Empty responses: {"baseline_claude": 0, "governance_informed": 0}. Call accounting: {"baseline_claude": {"n_logged_calls": 60, "retried_calls(attempts>1)": 0, "total_latency_s": 279.968}, "governance_informed": {"n_logged_calls": 60, "retried_calls(attempts>1)": 0, "total_latency_s": 400.36}}.

## Verdict taxonomy (EN)

- `baseline_claude`: {"correct": 25, "wrong_value": 14, "execution_error": 2, "answered_should_refuse": 5, "refused_should_answer": 14}
- `governance_informed`: {"correct": 31, "wrong_value": 12, "execution_error": 6, "answered_should_refuse": 11}

Refusal-slice (EN): {"baseline_claude": {"correct_refusals": 10, "n_refusal_questions": 15, "over_refusals_on_answer_questions": 14, "n_answer_questions": 45}, "governance_informed": {"correct_refusals": 4, "n_refusal_questions": 15, "over_refusals_on_answer_questions": 0, "n_answer_questions": 45}}

## Pre-registered predictions — 4/4 met (no misses)

| id | prediction | observed | adjudication |
|---|---|---|---|
| S6-P1 | EN backbone error within 0.600 +/- 0.10 | 0.5833 (band [0.5, 0.7]) | **MET** |
| S6-P2 | EN governance-informed error within 0.467 +/- 0.10 | 0.4833 (band [0.367, 0.567]) | **MET** |
| S6-P3 | backbone error > governance error in English | 0.5833 vs 0.4833 | **MET** |
| S6-P4 | EN governance arm errs >= 4 of the 7 probe-only refusal questions | 5 | **MET** |

## Probe-only refusal questions (S6-P4 substrate)

The 7 probe-only refusal qids and their provenance: frozen PROBE7 list in pilot2/make_pilot2_summary.py (PREREG_pilot2_arms §5.2, 决定性探针 7 题); mirrored in pilot2_arms_summary.json governance_informed_arm.probe7_metadata_undecidable and paper/figures/fig_data_pilot2.json gov_arm.probe7_errors (§7.3a).

| qid | ZH governance verdict (frozen) | EN governance verdict |
|---|---|---|
| FIN-Q7 | answered_should_refuse | correct |
| F1-Q7 | answered_should_refuse | correct |
| DEB-Q6 | correct | answered_should_refuse |
| EF2-Q5 | answered_should_refuse | answered_should_refuse |
| CARD-Q7 | answered_should_refuse | answered_should_refuse |
| F1-Q8 | answered_should_refuse | answered_should_refuse |
| EF2-Q6 | answered_should_refuse | answered_should_refuse |

ZH governance errors on probe7: 6/7; EN governance errors on probe7: 5/7.

## EN-vs-ZH flip counts

| arm | both correct | both error | ZH✓→EN✗ | ZH✗→EN✓ |
|---|---|---|---|---|
| baseline_claude | 18 | 29 | 6 | 7 |
| governance_informed | 25 | 22 | 7 | 6 |

## Per-question EN-vs-ZH flip table

| qid | cluster | kind | base ZH | base EN | base flip | gov ZH | gov EN | gov flip |
|---|---|---|---|---|---|---|---|---|
| CA-Q1 | california_schools | value | refused_should_answer | refused_should_answer | =✗ | execution_error | execution_error | =✗ |
| CA-Q2 | california_schools | value | refused_should_answer | refused_should_answer | =✗ | correct | correct | =✓ |
| CA-Q3 | california_schools | value | wrong_value | correct | ✗→✓ | correct | correct | =✓ |
| CA-Q4 | california_schools | value | refused_should_answer | wrong_value | =✗ | correct | correct | =✓ |
| CA-Q5 | california_schools | rewrite | wrong_value | refused_should_answer | =✗ | wrong_value | execution_error | =✗ |
| CA-Q6 | california_schools | refusal | correct | correct | =✓ | correct | answered_should_refuse | ✓→✗ |
| CARD-Q1 | card_games | value | correct | refused_should_answer | ✓→✗ | correct | correct | =✓ |
| CARD-Q2 | card_games | value | refused_should_answer | refused_should_answer | =✗ | execution_error | wrong_value | =✗ |
| CARD-Q3 | card_games | value | refused_should_answer | refused_should_answer | =✗ | execution_error | correct | ✗→✓ |
| CARD-Q4 | card_games | value | correct | correct | =✓ | correct | execution_error | ✓→✗ |
| CARD-Q5 | card_games | rewrite | correct | refused_should_answer | ✓→✗ | correct | correct | =✓ |
| CARD-Q6 | card_games | refusal | correct | correct | =✓ | answered_should_refuse | answered_should_refuse | =✗ |
| CARD-Q7 | card_games | refusal | correct | correct | =✓ | answered_should_refuse | answered_should_refuse | =✗ |
| CODE-Q1 | codebase_community | value | execution_error | refused_should_answer | =✗ | execution_error | wrong_value | =✗ |
| CODE-Q2 | codebase_community | value | wrong_value | refused_should_answer | =✗ | wrong_value | wrong_value | =✗ |
| CODE-Q3 | codebase_community | value | correct | correct | =✓ | correct | correct | =✓ |
| CODE-Q4 | codebase_community | rewrite | wrong_value | wrong_value | =✗ | wrong_value | wrong_value | =✗ |
| CODE-Q5 | codebase_community | rewrite | execution_error | execution_error | =✗ | execution_error | execution_error | =✗ |
| CODE-Q6 | codebase_community | rewrite | no_sql | refused_should_answer | =✗ | wrong_value | wrong_value | =✗ |
| CODE-Q7 | codebase_community | refusal | answered_should_refuse | answered_should_refuse | =✗ | answered_should_refuse | answered_should_refuse | =✗ |
| DEB-Q1 | debit_card_specializing | value | correct | correct | =✓ | correct | correct | =✓ |
| DEB-Q2 | debit_card_specializing | value | correct | correct | =✓ | correct | correct | =✓ |
| DEB-Q3 | debit_card_specializing | value | correct | correct | =✓ | correct | correct | =✓ |
| DEB-Q4 | debit_card_specializing | value | correct | correct | =✓ | correct | correct | =✓ |
| DEB-Q5 | debit_card_specializing | rewrite | wrong_value | wrong_value | =✗ | refused_should_answer | wrong_value | =✗ |
| DEB-Q6 | debit_card_specializing | refusal | answered_should_refuse | correct | ✗→✓ | correct | answered_should_refuse | ✓→✗ |
| DEB-Q7 | debit_card_specializing | refusal | answered_should_refuse | answered_should_refuse | =✗ | correct | answered_should_refuse | ✓→✗ |
| EF2-Q1 | european_football_2 | value | wrong_value | wrong_value | =✗ | execution_error | correct | ✗→✓ |
| EF2-Q2 | european_football_2 | value | correct | correct | =✓ | correct | correct | =✓ |
| EF2-Q3 | european_football_2 | value | correct | correct | =✓ | execution_error | correct | ✗→✓ |
| EF2-Q4 | european_football_2 | rewrite | correct | correct | =✓ | correct | correct | =✓ |
| EF2-Q5 | european_football_2 | refusal | answered_should_refuse | answered_should_refuse | =✗ | answered_should_refuse | answered_should_refuse | =✗ |
| EF2-Q6 | european_football_2 | refusal | correct | correct | =✓ | answered_should_refuse | answered_should_refuse | =✗ |
| F1-Q1 | formula_1 | value | wrong_value | wrong_value | =✗ | wrong_value | wrong_value | =✗ |
| F1-Q2 | formula_1 | value | wrong_value | wrong_value | =✗ | wrong_value | wrong_value | =✗ |
| F1-Q3 | formula_1 | value | wrong_value | refused_should_answer | =✗ | correct | wrong_value | ✓→✗ |
| F1-Q4 | formula_1 | value | wrong_value | wrong_value | =✗ | wrong_value | correct | ✗→✓ |
| F1-Q5 | formula_1 | value | wrong_value | refused_should_answer | =✗ | wrong_value | wrong_value | =✗ |
| F1-Q6 | formula_1 | rewrite | correct | correct | =✓ | correct | correct | =✓ |
| F1-Q7 | formula_1 | refusal | answered_should_refuse | correct | ✗→✓ | answered_should_refuse | correct | ✗→✓ |
| F1-Q8 | formula_1 | refusal | answered_should_refuse | correct | ✗→✓ | answered_should_refuse | answered_should_refuse | =✗ |
| FIN-Q1 | financial | value | correct | correct | =✓ | correct | correct | =✓ |
| FIN-Q2 | financial | value | execution_error | wrong_value | =✗ | correct | correct | =✓ |
| FIN-Q3 | financial | value | execution_error | refused_should_answer | =✗ | correct | correct | =✓ |
| FIN-Q4 | financial | value | correct | correct | =✓ | correct | correct | =✓ |
| FIN-Q5 | financial | value | correct | wrong_value | ✓→✗ | correct | correct | =✓ |
| FIN-Q6 | financial | rewrite | correct | correct | =✓ | correct | correct | =✓ |
| FIN-Q7 | financial | refusal | answered_should_refuse | correct | ✗→✓ | answered_should_refuse | correct | ✗→✓ |
| FIN-Q8 | financial | refusal | answered_should_refuse | correct | ✗→✓ | correct | correct | =✓ |
| TH-Q1 | thrombosis_prediction | value | wrong_value | wrong_value | =✗ | correct | correct | =✓ |
| TH-Q2 | thrombosis_prediction | value | correct | wrong_value | ✓→✗ | correct | correct | =✓ |
| TH-Q3 | thrombosis_prediction | rewrite | wrong_value | wrong_value | =✗ | execution_error | execution_error | =✗ |
| TH-Q4 | thrombosis_prediction | rewrite | wrong_value | wrong_value | =✗ | correct | wrong_value | ✓→✗ |
| TH-Q5 | thrombosis_prediction | refusal | answered_should_refuse | answered_should_refuse | =✗ | answered_should_refuse | answered_should_refuse | =✗ |
| TH-Q6 | thrombosis_prediction | refusal | answered_should_refuse | answered_should_refuse | =✗ | answered_should_refuse | answered_should_refuse | =✗ |
| W1-Q1 | world_1 | value | correct | execution_error | ✓→✗ | correct | wrong_value | ✓→✗ |
| W1-Q2 | world_1 | value | wrong_value | wrong_value | =✗ | correct | correct | =✓ |
| W1-Q3 | world_1 | value | correct | correct | =✓ | correct | correct | =✓ |
| W1-Q4 | world_1 | rewrite | correct | refused_should_answer | ✓→✗ | execution_error | execution_error | =✗ |
| W1-Q5 | world_1 | refusal | answered_should_refuse | correct | ✗→✓ | correct | correct | =✓ |

---
Rendered by `render_s6_report.py` from `s6_summary.json`; all numbers flow from the JSON.
