# VERIFICATION2 — adversarial verification of S4/S5/S6/S7

Governing prereg: `PREREG_poststudy2_20260823.md`, sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669` (recomputed from disk by the render script). Verifier: independent re-derivation scripts under `verification2/` (`v2_s4_recheck.py`, `v2_s5_recheck.py`, `v2_s6_recheck.py`, `v2_s7_recheck.py`); every number below is read back out of their JSON outputs. Frozen evidence was opened read-only; all verification outputs are new files under `poststudy2_20260823/verification2/`.

| study | verdict | basis |
|---|---|---|
| S4 | **CONFIRMED** | own bootstrap (same seed/convention) reproduces all 4 CIs exactly; per-rep elim matches; 2/3 misses honestly published |
| S5 | **CONFIRMED** (with one provenance defect) | own timing loop reproduces medians within 6.5%; 0/48 full-scan census independently confirmed; P1 miss honestly published; defect: corrupted 62-char prereg-sha citation, never re-asserted from disk |
| S6 | **CONFIRMED** | freeze provably minted before first scored call; 8/8 sampled translations gold-invariant; 6/6 hand re-scores match; full recount matches; 4/4 predictions independently MET |
| S7 | **CONFIRMED** | all 60 cached extractions re-bridged through frozen compiler + frozen scorer with 0 ledger mismatches; arm path clean; 4/4 predictions independently MET |

## S4 — paired-difference uncertainty: CONFIRMED

Independent bootstrap implementation (written from scratch; `random.Random(20260823)`, 9 cluster draws/iteration from sorted names, pooled mean, B=2000, CI=[sorted[49],sorted[1949]] — the frozen convention) over the frozen verdict matrix:

| arm | my mean | my 95% CI | matches s4_summary |
|---|---|---|---|
| governance_informed | 0.1333 | [-0.0500, 0.3000] | mean ✓ · CI ✓ (bit-exact) |
| trivial_claude | 0.0667 | [-0.0462, 0.1774] | mean ✓ · CI ✓ (bit-exact) |
| trivial_v2 | 0.0167 | [-0.1017, 0.1167] | mean ✓ · CI ✓ (bit-exact) |
| trivial_v3 | -0.0667 | [-0.1429, -0.0152] | mean ✓ · CI ✓ (bit-exact) |

Elimination restatement re-derived from the rep caches: per-rep fracs [0.3611, 0.4167, 0.4167, 0.4167, 0.3889] — all equal to the claimed values. 

Prediction re-adjudication (mine vs claimed): **S4-P1** MISS (claimed MISS); **S4-P2** MISS (claimed MISS); **S4-P3** MET (claimed MET). Full agreement. S4-P1 and S4-P2 are genuine misses and were published as misses — the headline governance effect is NOT resolvable at 95% under the 9-cluster bootstrap (CI [-0.05, 0.30] includes 0), and trivial_v3's CI excludes 0 on the harmful side.

## S5 — cost-model scalability sweep: CONFIRMED, one provenance defect

**Defect (provenance, not results):** `s5_measure.py`/`s5_build_substrates.py` hardcode a corrupted prereg sha (`838a214fc5a09902703d969c839872ff843f190e9f2e9f6902f231e061c669`, 62 hex chars — the true sha is 64 chars; two chars `1c` dropped at position 44), and it propagates into `s5_cost_sweep.json` and the S5_REPORT.md header. Unlike S4/S6/S7, no S5 script re-asserts the prereg hash from disk — an assert would have caught the typo. The prereg document itself is intact (its sha matches everywhere else); the mislabel does not touch any measured number.

Independent re-measurement (own 11-repeat timing loop, frozen compiler/verifier, read-only connections):

| point | claimed median (ms) | my median (ms) | mine/claimed |
|---|---|---|---|
| scale_100 | 19.691 | 18.42 | 0.935 |
| scale_400 | 24.804 | 23.802 | 0.96 |

Growth 1×→4×: mine 1.292× vs claimed 1.26× — the strongly-sublinear claim stands. 1× substrate verified byte-identical to the frozen financial warehouse (sha256 3409ec36…, hashed independently). Full-scan census recomputed two ways — string-scan over all 48 emitted certificate files and re-summing the sweep records: 0 full-scan audits (and 0 window-bounded audits) at every scale — the S5-P3 claim is confirmed by census.

Prediction re-adjudication from the study's own per-certificate records:
- **S5-P1 MISS** (claimed MISS — agreement). Monotonicity fails once: 0.25×→0.5× dips by 45 µs (sub-noise, but the prereg wrote strict monotonicity); growth 1.260× ≤ 4×. Honest adjudication of a technically-failed clause.
- **S5-P2 MET on the declared statistic; strict per-certificate reading MISS** (claimed the same, both published). Caveat: the prereg sentence does not name the per-point statistic; the median-over-certificates reading was chosen post-prereg in the sweep script. The choice is disclosed and the strict reading (FIN-Q5 0.978×, FIN-Q6 0.981× at 4× — below the band's lower edge in the *favourable* direction) is published alongside. I verify both readings from the per-certificate records: median in [20.4×, 24.8×] at all 6 points (MET); strict fails only at 4× (MISS). Re-adjudication: agreement, with the reading-selection freedom noted.
- **S5-P3 MET** (claimed MET — agreement), by independent census as above.

## S6 — English-question control: CONFIRMED

Freeze-before-call: `questions_en.json`, `FREEZE_questions_en.sha256` and `translation_audit.json` all have birth/mtime 2026-08-23 21:47:55; the first scored call is logged and cache-born 21:53:24, the last 22:04:48; 120 calls logged (60×2 arms, 0 retries). The freeze sha `d9508f3f…` matches the file on disk today. The freeze was verifiably minted BEFORE the first scored call.

Translation re-audit, 8 seeded-random questions (CA-Q4, CARD-Q3, CODE-Q6, EF2-Q5, F1-Q8, FIN-Q8, TH-Q1, W1-Q2): field-by-field against the frozen ZH structured fields (as-of instant, declared-at instant, window tokens, scope values, version pin, plus a no-gold-leak scan). All 8 faithful. Two automated literal-date flags (FIN-Q8, W1-Q2 `as_of` not literally present in the EN text) are false alarms: the ZH originals also never state those dates literally (FIN-Q8 phrases the windows as 1997年5月/4月; W1-Q2 says as-of 2026-05 月粒), and the EN texts preserve exactly that phrasing.

Hand re-score of 6 cached EN responses (3 per arm, seeded-random) — cached raw re-extracted with the frozen `RP.extract_sql` and re-scored with the frozen `R2.fetch_and_score` against the frozen warehouses: 6/6 verdicts match, SQL re-extraction and values byte/value-identical: baseline_claude/DEB-Q1→correct; baseline_claude/EF2-Q3→correct; baseline_claude/FIN-Q2→wrong_value; governance_informed/CA-Q3→correct; governance_informed/CARD-Q1→correct; governance_informed/DEB-Q6→answered_should_refuse.

Full independent recount of all 120 caches: baseline_claude 35/60, governance_informed 29/60 errors; taxonomy identical to S6_REPORT. Probe7 (re-derived from the frozen PROBE7 list in make_pilot2_summary.py: FIN-Q7, F1-Q7, DEB-Q6, EF2-Q5, CARD-Q7, F1-Q8, EF2-Q6): EN governance errors 5/7.

Prediction re-adjudication (mine vs claimed): **S6-P1** MET; **S6-P2** MET; **S6-P3** MET; **S6-P4** MET — all four MET, agreeing with the report (P1: 0.5833 ∈ [0.5,0.7]; P2: 0.4833 ∈ [0.367,0.567]; P3: 0.5833>0.4833; P4: 5≥4).

## S7 — NL→σ arm: CONFIRMED

Harness audit: the arm path is structurally clean — `load_questions_arm()` strips every question to {qid, domain, question_zh} at load; `build_prompt` asserts exactly those three keys; gold-side and σ fields are only read in `audit_load_full()`, which is called solely by the scoring/σ-accuracy path and by the preflight leak assert (which only checks absence from prompts). Grep for question-specific hardcoding: the only qid literals are the 3 smoke qids (cache control), no per-question branches. The Stage-B fix-forward (cache dir rename) is clean: all 3 smoke caches byte-identical (`cmp`) between `runs_nl2sigma/` and `runs_sigma/`. Call accounting: 57 new calls + 3 cache hits, budget 120 never approached; all cache births (21:39–21:46) postdate the prereg freeze (21:31:10). Minor note: the one-shot σ example in the prompt is a fictional financial question (asserted ∉ the 60) whose metric alias is a real registered alias — aliases are already present in the shared gov pack, so no gold-side leak.

Full independent re-derivation — all 60 cached extractions re-bridged through the frozen `asof_compiler.compile_question` and re-scored with the frozen `acceptance_pilot2._gold_match`, with my own field-canonicalisation code: **0/60 ledger mismatches** (outcome kind, verdict, exact-σ flag and all 13 field-match bits identical per question). Headline numbers: exact full-σ 40/60 (claimed 40), e2e error 5/60 (claimed 5), metric-alias match 58/60 (claimed 58). The 5 error rows re-derive identically: CA-Q5, CA-Q6 (compile_error), CODE-Q4, CODE-Q5, TH-Q3 (expected rewrite, got disclosure-blocked refusal). `exact_sigma_and_wrong` = [] — the S7-P3 witness set is empty in my re-derivation too.

Prediction re-adjudication (mine vs claimed): **S7-P1** MET; **S7-P2** MET; **S7-P3** MET; **S7-P4** MET — all four MET, agreeing with the report. Caveat on **S7-P4**: the quantitative gate (58/60 ≥ 54) is clearly MET; the descriptive concentration clause is only weakly satisfied (metric mismatches 2 vs window/scope/version-affected questions 2 — parity, not concentration — and the dominant mismatch field is `as_of` at 16/60, which belongs to neither family). The report itself discloses this in a "Descriptive (outside the gate)" note; I read the pre-registered gate as the ≥54/60 threshold and adjudicate MET, but the concentration wording should not be quoted as independently confirmed.

## Consolidated prediction re-adjudication (independent)

| prediction | claimed | my verdict | agree |
|---|---|---|---|
| S4-P1 | MISS | MISS | ✓ |
| S4-P2 | MISS | MISS | ✓ |
| S4-P3 | MET | MET | ✓ |
| S5-P1 | MISS | MISS | ✓ |
| S5-P2 | MET (median) / MISS (strict) | MET (median) / MISS (strict) | ✓ |
| S5-P3 | MET | MET | ✓ |
| S6-P1 | MET | MET | ✓ |
| S6-P2 | MET | MET | ✓ |
| S6-P3 | MET | MET | ✓ |
| S6-P4 | MET | MET | ✓ |
| S7-P1 | MET | MET | ✓ |
| S7-P2 | MET | MET | ✓ |
| S7-P3 | MET | MET | ✓ |
| S7-P4 | MET | MET | ✓ |

14/14 verdict agreements (S5-P2 agreeing on both the declared-statistic and the strict reading). The battery's honesty properties held under adversarial re-derivation: the three misses (S4-P1, S4-P2, S5-P1) are published as misses, and no adjudication required trusting a study's own numbers — every one was recomputed from frozen evidence or cached raw model output.

## Defect list

1. **S5 provenance**: corrupted 62-char prereg sha quoted in `s5_measure.py`, `s5_build_substrates.py`, `s5_cost_sweep.json`, `S5_REPORT.md`; no from-disk sha assert anywhere in S5 (S4/S6/S7 all have one). Fix: correct the constant and add the assert in any future S5 rerun; any TR citation of S5 must quote the true sha `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669`.
2. **S5-P2 statistic selection**: the adjudicating statistic (median over SQL-emitting certificates) was fixed post-prereg; both readings are published, so no result hinges on the choice, but the TR should state the clause was ambiguous as pre-registered.
3. **S7-P4 concentration clause**: quantitative gate MET; the descriptive clause ("failures concentrate in window/scope/version fields") is at parity (2 vs 2) with the real mass on `as_of` (16/60) — keep the report's own outside-the-gate framing when citing.

---
Verifier scripts and JSONs: `verification2/v2_s4_recheck.{py,json}`, `v2_s5_recheck.{py,json}`, `v2_s6_recheck.{py,json}`, `v2_s7_recheck.{py,json}`; rendered by `render_verification2.py`.
