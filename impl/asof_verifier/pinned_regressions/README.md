# Pinned regression mutations (V6a+ hardening)

Provenance: SQL mutations of the genuine CARD-Q2 certificate that the relevant
pre-hardening verifier ACCEPTed, preserved verbatim as mandatory regressions —
all must REJECT under the hardened verifier, forever.

Round 1 (a–d), PREREG_poststudy3_20260826.md (sha256
426017ddfd8af8608e452b44175e2158c620c2e8cebe3a17572ee3fe15d7a192): the pre-V6a+
verifier (V0–V6c, chk.py sha256
37f051913b77a5230aa7ce7b1937c1c0c102c0a6cc43d61e1d8c0f79a0ffe492) ACCEPTed
them; demonstrated by the external review (Codex, 2026-08-26) and reproduced
independently (scratchpad m1-repro).

Round 2 (e–f), PREREG_poststudy4_20260827.md (sha256
a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75): the
round-1-hardened V6a+ STILL ACCEPTed a genuine ratio/delta certificate whose
outer SELECT carries a top-level WHERE filtering the scalar answer to zero
rows; demonstrated by the second review (Codex, 2026-08-27) and reproduced
independently (scratchpad p0-repro, exploit_results.json). Fix 1 (outer-filter
closure) rejects the outer WHERE structurally as V6P_SHAPE; fix 2's
execution-shape check (V6a+x) independently rejects the zero/multi-row result
as V6P_ARITY.

| file | mutation | expected under V6a+ |
|---|---|---|
| cert_mut_a_count_distinct_date.json | numerator COUNT(*) → COUNT(DISTINCT rulings."date") | REJECT (V6P_MEASURE) |
| cert_mut_b_leg_swap.json | legs swapped, no leading SELECT (expression form) | REJECT (V6P_PARSE) |
| cert_mut_b2_leg_swap_valid.json | legs swapped inside the intact ratio frame | REJECT (V6P_LEG_ROLE) |
| cert_mut_c_constant_999.json | SELECT 999 FROM "rulings" WHERE 〈window〉 (constant, multi-row) | REJECT (V6P_SHAPE) |
| cert_mut_d_narrowed_predicate.json | numerator window narrowed to [2016-11-10, 2016-11-20) | REJECT (V6P_WINDOW) |
| cert_mut_e_outer_where_1eq0.json | ratio + outer `WHERE 1=0` (filters the 1×1 answer to 0 rows) — round-2 exploit V1 | REJECT (V6P_SHAPE; V6a+x V6P_ARITY backstop) |
| cert_mut_f_outer_where_false.json | ratio + outer `WHERE 'a'='b'` (0 rows) — round-2 exploit V1c | REJECT (V6P_SHAPE; V6a+x V6P_ARITY backstop) |

Note on V2 (`SELECT * FROM (〈ratio〉) q WHERE 1=0`): the derived-table wrap was
ALREADY rejected before round 2 — the non-empty outer FROM trips the scalar
template's `allow_from=False` guard (V6P_SHAPE) — so it is documented here but
not separately pinned; the round-2 gap was specifically the DIRECT outer WHERE
on the empty-FROM scalar node (e/f), which no round-1 check policed.

q_CARD-Q2.json is the structured question the certificates answer;
the warehouse is the card_games pilot2 domain warehouse.

Runner: `python3 forge_v6aplus.py --p2 <pilot2/domains root>` replays these
(section PINNED_*) alongside forgery families F6–F11 and fails the battery if
any of them ACCEPTs.

File sha256 (as pinned):

- 0a8ea860a21bd1da70403988b2c17d2c4eb8d43e207b7ed483d3f3f9610127d3  cert_mut_a_count_distinct_date.json
- 1acc049378bd767d5eef64e0dee3ad466141bd9f52cf1b3d1fb5a18878c27012  cert_mut_b_leg_swap.json
- 95a25d9e1a9b55ece5f1015a167e183c776040bc1967f7989860bfb96e1b5283  cert_mut_b2_leg_swap_valid.json
- 32f2062d31be7844b0d8551bd15c74342343129eb50f3ba5317dbff8eee95a77  cert_mut_c_constant_999.json
- bf28ec907a95acc8b02133303847fbff8fdbe9ad843914e263a036ab5bbe111e  cert_mut_d_narrowed_predicate.json
- 9d077d4c611f243d1bf30843ab64e16641dd85c2fbda19e0130a32e5286ebfd0  cert_mut_e_outer_where_1eq0.json
- 6382c1807a4932985824287e0511f38c391b32f6e1c158ef6bc7feb01d3c7b6f  cert_mut_f_outer_where_false.json
- bb0fecc51afe301e529afdb76a61624229c9b2c93899d419a9400cb6b423f0c7  q_CARD-Q2.json
