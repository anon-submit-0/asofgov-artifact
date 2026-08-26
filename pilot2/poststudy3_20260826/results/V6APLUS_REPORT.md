# V6APLUS_REPORT — verifier hardening V6a+ (poststudy3_20260826)

Post-registration study under `PREREG_poststudy3_20260826.md` (sha256 `426017ddfd8af8608e452b44175e2158c620c2e8cebe3a17572ee3fe15d7a192`). Every number below is rendered by `gen_v6aplus_summary.py` from the recorded run artifacts in this directory; none is typed by hand.

## What was hardened

V6a+ is a fail-closed structural check appended to the verifier's conjunction (check order `V0..V6c,V6a+`; appended last so every pre-existing forgery keeps its frozen `rejected_by` attribution). It parses each answer SQL with DuckDB's own parser (`json_serialize_sql`, no new dependency) and validates the tree against the independently loaded governance seeds: template membership per registered metric kind, measure implementation per `gov_measure_def`, leg-role binding, registered + question-scope predicates with exact window equality, and registered routing join keys. Implementation: `v6aplus.py` in the verifier tree, imported by `chk.py`; the import-disjointness gate (`ci_check.py`) now asserts its presence (A5) and its stdlib-only imports (A1/A2). Machine-readable reason codes: `V6P_PARSE`, `V6P_KIND`, `V6P_SHAPE`, `V6P_MEASURE`, `V6P_LEG_ROLE`, `V6P_PREDICATE`, `V6P_WINDOW`, `V6P_JOIN`, `V6P_TABLE`.

## Matrix totals

| suite | n | result |
|---|---:|---|
| genuine certificates | 60 | 60 ACCEPT / 0 REJECT (V6a+ per-status: PASS=45, SKIP=15) |
| pinned reproduction mutations | 5 | 5 REJECT (5 with the pinned reason code) |
| old forgeries F1-F5 | 34 | 34 REJECT (34 keep the frozen `rejected_by`) |
| new forgeries F6-F10 | 31 | 31 REJECT |

## New forgery families (per prereg)

| family | forgeries | REJECT | distinct bases | rejected_by |
|---|---:|---:|---|---|
| F6 | 6 | 6 | CA-Q1, CARD-Q2, DEB-Q3, F1-Q1, TH-Q1, W1-Q1 | V6a+=6 |
| F7 | 5 | 5 | CA-Q1, CODE-Q1, EF2-Q2, FIN-Q1, W1-Q3 | V6a+=5 |
| F8 | 8 | 8 | CA-Q1, CARD-Q4, CODE-Q1, CODE-Q2, F1-Q1, FIN-Q1, FIN-Q3, TH-Q1 | V6a+=8 |
| F9 | 6 | 6 | CA-Q3, CARD-Q1, DEB-Q1, EF2-Q2, FIN-Q4, W1-Q1 | V6a=3, V6a+=3 |
| F10 | 6 | 6 | CARD-Q1, CODE-Q3, EF2-Q1, FIN-Q5, TH-Q2, W1-Q2 | V6a+=6 |

F9's widened/shifted cases (`F9b`, `F9c`) and the moved in-effect bound (`F9f`) are caught first by the frozen V6a containment/SCD-2 gate — its jurisdiction all along — and V6a+ fails them too (asserted); every narrowing case, invisible to containment, is caught by V6a+ alone.

## Pinned regressions (the Codex 2026-08-26 reproduction)

| mutation | expected | actual |
|---|---|---|
| PINNED_cert_mut_a_count_distinct_date | REJECT(V6P_MEASURE) | REJECT by V6a+ |
| PINNED_cert_mut_b_leg_swap | REJECT(V6P_PARSE) | REJECT by V6a+ |
| PINNED_cert_mut_b2_leg_swap_valid | REJECT(V6P_LEG_ROLE) | REJECT by V6a+ |
| PINNED_cert_mut_c_constant_999 | REJECT(V6P_SHAPE) | REJECT by V6a+ |
| PINNED_cert_mut_d_narrowed_predicate | REJECT(V6P_WINDOW) | REJECT by V6a+ |

## V6a+ reason-code distribution (all rejecting evaluations in the batteries)

| code | count |
|---|---:|
| V6P_KIND | 2 |
| V6P_LEG_ROLE | 1 |
| V6P_MEASURE | 9 |
| V6P_PARSE | 1 |
| V6P_PREDICATE | 13 |
| V6P_SHAPE | 9 |
| V6P_WINDOW | 9 |

## Predictions adjudicated

| id | prereg statement | observed | verdict |
|---|---|---|---|
| P1 | all 60 genuine certificates still ACCEPT under V6a+ | 60/60 ACCEPT | HOLDS |
| P2 | all five reproduction mutations REJECT | 5/5 REJECT (5/5 with the pinned reason code) | HOLDS |
| P3 | every new F6-F10 forgery REJECTs | 31/31 REJECT | HOLDS |
| P4 | the original 34 F1-F5 forgeries still all REJECT | 34/34 REJECT (34/34 with the frozen rejected_by attribution) | HOLDS |

**All predictions hold: yes.**

## Additional finding (closed during hardening, before any battery freeze)

While implementing check family 4 we found the first V6a+ draft accepted an ANSWER whose SQL silently drops the question's declared scope predicate and its routing join (e.g. F1-Q1 computing every driver's 2009 points instead of `driver='button'`). The declared scope keys are registered predicates of the binding (`gov_semantic_node.scope_keys`), so the final V6a+ requires every applicable declared scope key to be implemented in each ANSWER leg (REWRITE coarsening remains V5's rollup/mask jurisdiction). The two closing forgeries are pinned as `F8g`/`F8h`.

## Behavioural invariance on genuine corpora

Both suites were replayed under the pre-hardening verifier (byte-identical `chk.py`, sha256 `37f051913b77a5230aa7ce7b1937c1c0c102c0a6cc43d61e1d8c0f79a0ffe492`) and the hardened one: per-qid verdicts are identical on the 60 genuine pilot2 certificates in both window modes (60/60 declared, 50/60 no-declared-windows) and on the old51 suite (45/51, the six pre-existing V3/V6b adm_check_mode rejects unchanged) — see `runall_v6aplus_record.txt`. The hardening adds rejection power on forgeries only.

## Reproduce

```
cd '/Volumes/SSD 1/vldb_asof/asof-gov-vldb-artifact/impl/asof_verifier'
python3 ci_check.py
python3 forge_v6aplus.py --p2 '/Volumes/SSD 1/explore_opportunity_cc/pilot2/domains'
python3 -c "import forge_p2; forge_p2.P2='/Volumes/SSD 1/explore_opportunity_cc/pilot2/domains'; forge_p2.main([])"
python3 gen_v6aplus_summary.py   # from this results/ dir
```

Input record hashes: `genuine60_verdicts.json` sha256 `5d5f8a8e3864bcf834f480110c603234abab771f8d509119e119e9dcb9aa5e96`; `forge_v6aplus_run.json` sha256 `2b07416c810e8effebbd9f7d2e7cd9e0523d4d6c0a8714d6a24ab0e838ddd500`; `forge_p2_v6aplus_run.json` sha256 `843192ef7f455879a594f37fd061d287ca3aef323add9d74fc9f25b8d4cbd77e`
