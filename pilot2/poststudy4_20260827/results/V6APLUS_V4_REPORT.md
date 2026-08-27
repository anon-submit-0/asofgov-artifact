# V6APLUS_V4_REPORT — verifier hardening V6a+ round 2 (poststudy4_20260827)

Post-registration study under `PREREG_poststudy4_20260827.md` (sha256 `a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75`). Every number below is rendered by `gen_v6aplus_v4_summary.py` from the recorded run artifacts in this directory; none is typed by hand.

## What round 2 hardened

A second external review (Codex, 2026-08-27), reproduced independently (scratchpad `p0-repro`), showed the round-1 V6a+ still ACCEPTed a genuine ratio/delta certificate whose outer SELECT carried a top-level `WHERE` filtering the scalar answer to zero rows (`WHERE 1=0`, `WHERE 'a'='b'`): `_check_ratio`/`_check_delta` did not reject an outer `where_clause`, and no check executed the answer to test its shape. Two fixes, both fail-closed:

- **Fix 1 (outer-filter closure, structural).** `_plain_node` now rejects a non-null outer `WHERE` by default (`allow_outer_where=False`) with `V6P_SHAPE`; the scalar outer nodes of atomic/ratio/delta route through that default, while the FROM-carrying leg / report / attribute predicate walkers pass `allow_outer_where=True` and read their own `where_clause` as before.
- **Fix 2 (execution-shape check, semantic).** A new check `V6a+x` is appended LAST in the order `V0..V6c,V6a+,V6a+x`; it is the first V6a+-family site to EXECUTE the answer SQL, running each ANSWER/REWRITE answer read-only against the warehouse (the same connection the V6b/V6c probes use) and requiring the certified row/column arity, else `V6P_ARITY`. REFUSE certificates carry no answer SQL and are SKIPped. Appending last keeps every pre-existing first-FAIL attribution frozen.

`ci_check.py` gains A5b (the `V6a+x` execution-shape check exists in `v6aplus.py` and is wired into `chk.py`'s check order) and A6 (the F11 family is present in `forge_v6aplus.py`, >=6 forgeries over >=4 bases). CI-CHECK: PASS.

## Matrix totals

| suite | n | result |
|---|---:|---|
| genuine certificates | 60 | 60 ACCEPT / 0 REJECT (V6a+ PASS=45, SKIP=15; V6a+x PASS=45, SKIP=15) |
| pinned regressions | 7 | 7 REJECT (7 with the pinned reason code; round-1 5 + round-2 2) |
| prior forgeries F1-F5 | 34 | 34 REJECT (34 keep the frozen `rejected_by`) |
| prior forgeries F6-F10 | 31 | 31 REJECT |
| NEW forgeries F11 (outer-row-filter) | 8 | 8 REJECT |
| append-outer-WHERE sweep | 60 | 45/45 answer-bearing REJECT; 15 REFUSE with no answer SQL |

Forgery accounting: prior battery = 70 (5 round-1 pinned + 34 F1-F5 + 31 F6-F10); round 2 adds the 8-forgery F11 family and 2 round-2 exploit pins (V1, V1c). Task formula `70 + |F11|` = **78**; including the 2 round-2 pins the grand total of forged certificates is **80** (plus 45 answer-bearing sweep mutations).

## Confirmed exploits (scratchpad p0-repro), replayed post-fix

| variant | verdict | V6a+ | V6a+x | executed shape | note |
|---|---|---|---|---|---|
| V1_outer_where_1eq0 | REJECT | V6P_SHAPE | V6P_ARITY | [0, 1] | confirmed exploit: outer WHERE filters the ratio to 0 rows (pre-fix ACCEPT) |
| V1b_outer_where_1eq1_control | REJECT | V6P_SHAPE | - | [1, 1] | denotation-preserving control: TRUE outer WHERE, still 1x1 (pre-fix ACCEPT); caught post-fix by the structural closure only |
| V1c_outer_where_false | REJECT | V6P_SHAPE | V6P_ARITY | [0, 1] | confirmed exploit: outer WHERE 'a'='b' filters to 0 rows (pre-fix ACCEPT) |
| V2_wrap_derived_where_1eq0 | REJECT | V6P_SHAPE | V6P_ARITY | [0, 1] | derived-table wrap: already rejected before round 2 (non-empty outer FROM); documented, not newly pinned |
| V3_num_leg_and_1eq0 | REJECT | V6P_PREDICATE | - | [1, 1] | leg-level AND 1=0: already rejected before round 2 (V6P_PREDICATE) |
| V4_multirow_from_values | REJECT | V6P_SHAPE | V6P_ARITY | [3, 1] | outer FROM (VALUES ...): forces 3 rows; already rejected before round 2 (non-empty outer FROM); V6P_ARITY now also fires |

The two confirmed round-2 exploits (`V1`, `V1c`) — the ones the round-1 verifier ACCEPTed — both REJECT, each on `V6P_SHAPE` (fix 1) with the independent `V6P_ARITY` backstop (fix 2) also firing. The `V1b` `WHERE 1=1` control is denotation-preserving (executes to 1x1, so the arity check PASSes) and is caught by the structural closure ALONE — empirical proof that fix 1 is necessary and not subsumed by fix 2.

## F11 outer-row-filter family

| forgery | base | verdict/by | V6a+ | V6a+x |
|---|---|---|---|---|
| F11a_ratio_outer_where_1eq0 | CARD-Q2 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |
| F11b_ratio_outer_where_false_str | FIN-Q1 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |
| F11c_delta_outer_where_1eq0 | F1-Q4 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |
| F11d_atomic_outer_where_1eq0 | CARD-Q1 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |
| F11e_ratio_outer_where_1eq1_true | CA-Q1 | REJECT by V6a+ | V6P_SHAPE | - |
| F11f_ratio_outer_from_values_multirow | TH-Q1 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |
| F11g_atomic_outer_where_false_str | DEB-Q1 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |
| F11h_ratio_outer_where_numeric_false | CODE-Q1 | REJECT by V6a+ | V6P_SHAPE | V6P_ARITY |

8 forgeries over 8 distinct bases (CA-Q1, CARD-Q1, CARD-Q2, CODE-Q1, DEB-Q1, F1-Q4, FIN-Q1, TH-Q1); all REJECT, all with `rejected_by = V6a+`. The `V6P_ARITY` execution backstop additionally fires on 7 of them (the zero-row and multi-row cases); the `1=1` control is caught by `V6P_SHAPE` alone.

## Append-outer-WHERE corpus sweep

Appending a top-level `WHERE 1=0` to every genuine certificate's answer SQL: **45/45 answer-bearing bases REJECT**. The remaining 15 bases are REFUSE certificates that carry no answer SQL — the outer-row-filter attack forges an ANSWER by filtering it, so its surface does not exist for a refusal (recorded as `no_answer_sql`, never as a reject or an escape). REFUSE qids: CA-Q6, CARD-Q6, CARD-Q7, CODE-Q7, DEB-Q6, DEB-Q7, EF2-Q5, EF2-Q6, F1-Q7, F1-Q8, FIN-Q7, FIN-Q8, TH-Q5, TH-Q6, W1-Q5.

## Reason-code distribution (all rejecting battery evaluations)

Structural (`V6a+`):

| code | count |
|---|---:|
| V6P_KIND | 2 |
| V6P_MEASURE | 8 |
| V6P_PREDICATE | 14 |
| V6P_SHAPE | 21 |
| V6P_WINDOW | 8 |

Execution-shape backstop (`V6a+x`):

| code | count |
|---|---:|
| V6P_ARITY | 17 |

## Predictions adjudicated

| id | prereg statement | observed | verdict |
|---|---|---|---|
| P1 | all 60 genuine certificates still ACCEPT (shape check passes on every genuine answer) | 60/60 ACCEPT | HOLDS |
| P2 | the confirmed outer-filter exploits all REJECT (V6P_SHAPE for the outer WHERE; V6P_ARITY backstop on zero/multi-row) | 2/2 confirmed exploits REJECT (V1: V6P_SHAPE +V6P_ARITY; V1c: V6P_SHAPE +V6P_ARITY) | HOLDS |
| P3 | every F11 forgery REJECTs; the append-outer-WHERE sweep REJECTs on every answer-bearing base (REFUSE certs carry no answer SQL to filter) | F11 8/8 REJECT; sweep 45/45 answer-bearing REJECT, 15 REFUSE with no answer SQL (of 60 total) | HOLDS |
| P4 | the full prior battery still holds — 60/60 genuine ACCEPT, and the 70 prior forgeries (5 round-1 pinned + F1-F10) all REJECT | 60/60 genuine ACCEPT; prior forgeries 70/70 REJECT (pinned-r1 5/5, F1-F5 34/34, F6-F10 31/31) | HOLDS |

**All predictions hold: yes.**

## Two-tree byte-identity

The verifier is fixed identically in both working trees; the port is byte-identical (`trees_byte_identical = True`):

| file | sha256 |
|---|---|
| chk.py | `f3f23be5a5dcf1232edc60908594ca3585a9e41a2538a579c0d037297443a510` |
| ci_check.py | `0875d0e6075f01d553c7e5aee95b2aef18425811dd8d354783388f9d34d7c9bc` |
| forge_v6aplus.py | `1f08abc57b9e6d503a68a7605723c2f149a2d91d3173359b57edb7b31eba4ca4` |
| v6aplus.py | `d09dece46e71b112131bfef72c20872a8f8bc4864fb6fccf41d3d57a26023c11` |

## Reproduce

```
cd '/Volumes/SSD 1/explore_opportunity_cc/impl/asof_verifier'
python3 ci_check.py
python3 forge_v6aplus.py --p2 '/Volumes/SSD 1/explore_opportunity_cc/pilot2/domains'
python3 -c "import forge_p2; forge_p2.P2='/Volumes/SSD 1/explore_opportunity_cc/pilot2/domains'; forge_p2.main([])"
cd '/Volumes/SSD 1/explore_opportunity_cc/pilot2/poststudy4_20260827/results'
python3 run_matrix.py
python3 gen_v6aplus_v4_summary.py
```

Input record hashes: `genuine60_verdicts.json` sha256 `d59da3149e1810381cbcfe322f31ed12bbd5159163150fb2478faa321f794b42`; `exploits_run.json` sha256 `4079728a6bdde8d410c55444e76040ec1627b39920e5534590b8d0a5428c759a`; `sweep_run.json` sha256 `5060b350fc9265870f16fba60be963769c24c894ef937a4bd0c0d50c82825613`; `forge_v6aplus_run.json` sha256 `e93302e83d68880a9c1f903e7aea4d68052c119702908e133b30d6bb512e0cc7`; `forge_p2_v6aplus_run.json` sha256 `2f3e0f9d9d537508a5ffcca4a9795335e3d54071d4e0460d7f54209f1535a7ae`; `ci_check_v6aplus.json` sha256 `5045f7ef18200e3dcbf7f0cfa56d72b832e9e94407e18cb92f0ca9adef450a4a`
