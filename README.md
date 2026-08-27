# AsOfGov: As-Of Correctness for Governed Queries with Typed Refusals and Certificates

This is the artifact repository for the paper *AsOfGov: As-Of Correctness
for Governed Queries with Typed Refusals and Certificates* (Hongsheng Wang
and Xiubo Liang, Zhejiang University). It is the paper's complete evidence base: the
benchmark build (9 public BIRD/Spider-derived databases, **3,830,036 real
rows**), the frozen pre-registered LLM-arm runs, the binding compiler +
certificates, the independent verifier + forgery battery, and every script
that produced every figure, table and prose number. The extended technical
report is [`tr/asof-gov-tr.pdf`](tr/asof-gov-tr.pdf) (161 pp., referenced
from the paper as `\extendedtrurl`).

Headline result (all reproducible below): plain NL2SQL baselines err on
**60.0–76.7%** of the 60 as-of questions, a fully governance-informed prompt
arm still errs on **46.7%**, while the binding compiler is at **0/60** with
60/60 machine-checkable certificates accepted by an independent verifier that
rejects all 78 certificate forgeries (34 pre-registered F1–F5, plus the 44
post-registration V6a+ hardening battery of 2026-08-26/27, below).

## Requirements

* python 3.9+ (reference environment: python 3.9.6 on macOS 15) with
  `duckdb==1.4.4`, `matplotlib==3.9.4`, `numpy==2.0.2` — exact pins in
  [`requirements.txt`](requirements.txt)
* ~1 GB disk + network only for the optional data-substrate rebuild
  (§4/§5); the entry gate below needs neither

## Setup

```bash
pip install -r requirements.txt
```

## Quickstart

```bash
# The entry point. Needs NOTHING beyond this repository + python3:
# no warehouses, no network, no LaTeX, no LLM keys.
bash reproduce_all.sh gates   # the paper's 588-assertion number gate +
                              # 163-assertion red-line gate; prints PASS/FAIL
```

The full pipeline — data rebuild → scoring → figures/tables → verifier +
forgery battery — with its needs-matrix is in §4. These zero-dependency
gates check that every number the shipped paper sources print is still
backed by the shipped evidence JSONs; reproducing that evidence itself
(scoring, figures, tables, verifier + forgery batteries) is the separate
full path of §4, which first rebuilds the ~1 GB data substrate via
`fetch_and_rebuild.sh`.

---

## 1. Paper figure/table → script map

| Paper item | Produced by | Reads |
|---|---|---|
| **Figure 1** (`fig:running`, the as-of gap on `card_games`) | [`paper/figures/fig1_asof_gap.py`](paper/figures/fig1_asof_gap.py) | `pilot2/domains/card_games/{warehouse.duckdb,questions.json}`, `pilot2/pilot2_arms_summary.json` |
| **Figure 2** (`fig:partition`, the four-sibling partition) | [`paper/figures/figA_partition.py`](paper/figures/figA_partition.py) | `paper/figures/fig_data_pilot2.json` → key `partition` |
| **Figure 3** (`fig:taxonomy`, failure taxonomy, bars sum to 60) | [`paper/figures/fig3_failure_taxonomy.py`](paper/figures/fig3_failure_taxonomy.py) | `fig_data_pilot2.json` → keys `taxonomy`, `error_counts`, `per_gold_form` |
| **Table 1** (`tab:notation`, the §2–§5 notation table) | hand-authored in the paper (§2); carries no measured number | — |
| **Table 2** (`tab:suite`, benchmark composition) | [`paper/figures/make_tables_p2.py`](paper/figures/make_tables_p2.py) → `paper/tables/tab_benchmark.tex` (+ `.audit.json`) | `fig_data_pilot2.json` → key `benchmark` |
| **Table 3** (`tab:main` = `tab:taxonomy`, main results, 9 arms × 60) | [`paper/figures/make_tables_p2.py`](paper/figures/make_tables_p2.py) → `paper/tables/tab_main_results.tex` (+ `.audit.json`) | `fig_data_pilot2.json` → keys `error_rate`, `ci95`, `eliminated_by`, `coverage`, `refusal_stats`, `per_gold_form` |
| **Table 4** (`tab:divergence`, D1–D15 first-cross-check ledger) | [`paper/tools/gen_table_divergence.py`](paper/tools/gen_table_divergence.py) → `paper/tables/tab_divergence.tex` (+ `.audit.json`) | `impl/INTEGRATION_REPORT.md` §5 (parsed + re-asserted) |
| **Table 5** (`tab:delta`, qualitative related-work delta) | hand-authored prose table in the paper (§8); no measured number | — |
| *Threats* paragraph, LOCO + repetition sentences (post-registration, added 2026-08-20) | asserted by the poststudy block of [`paper/tools/check_numbers.py`](paper/tools/check_numbers.py) — the S1 fold matrix is recomputed cell-by-cell from the same per-question verdict matrix the rest of the gate uses | `pilot2/poststudy_20260820/s1/loco_report.json`, `pilot2/poststudy_20260820/s3/s3_summary.json` |
| governance-blind temporal-SQL sentences, §7.7 *Threats* + §8 *Related Work* (post-registration, added 2026-08-20; the §7.7 copy 2026-08-23) | same gate, S2 sub-block — both pre-declared scoring readings and both prose copies asserted, so neither reading can be cherry-picked and the copies cannot drift apart | `pilot2/poststudy_20260820/s2/tsql_summary.json` (per-question ledger: `s2/tsql_ledger.json`) |
| cross-lingual *Threats* sentences, §7.7 (post-registration battery 2, added 2026-08-23 --- the same-protocol English-question control) | poststudy2 sub-block of [`paper/tools/check_numbers.py`](paper/tools/check_numbers.py) --- all four error counts printed in the sentence, the one-question-per-arm EN/ZH movement, the English ordering and the probe-side concentration are re-derived from the study JSON and the frozen verdict matrix, and the superseded no-English-control concession is asserted absent from the body | `pilot2/poststudy2_20260823/s6/s6_summary.json` (frozen EN questions `s6/questions_en.json` + sha freeze, response caches `s6/runs_en/`, call log `s6/call_log_en.jsonl`) |
| NL$\to\sigma$ *Threats* sentence, §7.7 (post-registration battery 2, added 2026-08-23 --- $\sigma$ extracted from the question text, frozen compiler downstream) | same gate, S7 sub-block --- the printed error count is re-derived from the study JSON, recounted question-by-question from the per-question ledger, and the exact-$\sigma$-implies-zero-error witness is asserted empty | `pilot2/poststudy2_20260823/s7/s7_summary.json` (per-question ledger `s7/s7_ledger.json`, extraction caches `s7/runs_sigma/`) |
| every number in Figures 2–3 / Tables 2–3 | [`paper/figures/extract_p2.py`](paper/figures/extract_p2.py) → `paper/figures/fig_data_pilot2.json` | `pilot2/pilot2_arms_summary.json`, `pilot2/pilot2_summary.json`, the 9 warehouses, `impl/certs2/`, `impl/asof_verifier/forge_p2_out/`, `impl/asof_verifier/chk.py` (re-run read-only), gov seeds, `pilot2/runs/` |
| the scored matrix itself | [`pilot2/make_pilot2_summary.py`](pilot2/make_pilot2_summary.py) → `pilot2/pilot2_arms_summary.json` + `pilot2_summary.json` | `pilot2/runs/<arm>/<qid>.json` (frozen caches; **zero LLM calls**), `pilot2/domains/*/questions.json`, the warehouses (every cached SQL is re-executed), frozen `pilot/run_pilot.py` (sha-asserted) |

Note on Tables 2–3: in the paper body they are typeset inline (a layout
surgery joined the taxonomy block into Table 3), so `paper/tables/*.tex`
here are the generated reference twins; cell-for-cell equality between the
body tables, these twins and the JSON evidence is enforced by the paper
588-assertion number gate (shipped here, and re-runnable: see
§4), which reads the same
`fig_data_pilot2.json` / `pilot2_*.json` shipped here.

Unused-by-the-body pipeline scripts kept for lineage: `fig1_combined.py`,
`figB_forgery_matrix.py` (forgery matrix, TR), `figD_cost_ablation.py`
(cost/ablation, TR), each reading only `fig_data_pilot2.json` +
`impl/cost_p2.json`.

## 2. Where each headline prose number lives

| Number in the paper | Machine source (JSON path) |
|---|---|
| plain-baseline error 60.0% / 71.7% / 73.3% / 76.7% | `pilot2/pilot2_arms_summary.json` → `error_rate.baseline_{claude,qwen,deepseek,minimax}` |
| governance-informed 46.7% (28/60) | `error_rate.governance_informed`; audit detail in `gov_arm` of `paper/figures/fig_data_pilot2.json` |
| compiler 0/60 | `error_rate.mechanism` (anchored to the frozen `impl/certs2/`, re-checked by `extract_p2.py`) |
| 95% CIs (cluster bootstrap, 9 clusters, B=2000, seed 20260731) | `cluster_bootstrap.<arm>.ci95` |
| elimination of reference-baseline errors (e.g. gov arm 36.1%, compiler 100%) | `eliminated_by.<arm>` |
| 3,830,036 real rows (+20,094 authored) | sum over `pilot2/domains/*/provenance.json` → `tables.<t>.rows` split by `authored` |
| certificates 60/60 ACCEPT; strict no-declared-windows track 50/60 | `fig_data_pilot2.json` → `ablation.rungs` (`A1`=60, `A3`=50); re-runnable via `impl/asof_verifier/runall.py p2` |
| 34/34 forgeries rejected over 11 bases (F1×6, F2×5, F3×9, F4×10, F5×4) | `fig_data_pilot2.json` → `forge`; raw runs in `impl/asof_verifier/forge_p2_out/`; re-runnable via `./reproduce_all.sh verify` (stage 6b) or `python3 impl/asof_verifier/forge_p2.py` |
| verify cost (median warm ≈17 ms, cold ≈116 ms per certificate) | `impl/cost_p2.json` → `aggregate.verify_{warm,cold}_s` |
| 60 questions = 33 value + 12 rewrite + 15 refusal | asserted in `pilot2/make_pilot2_summary.py` (`load_questions`) over `domains/*/questions.json` |

Every prose number is machine-diffed against these same JSONs by the
paper's 588-assertion number gate, which is **shipped and runnable in this
repository**: `paper/tools/check_numbers.py` plus the paper sources it
parses (`paper/main.tex`, `paper/sections/*.tex`) are here, and
`./reproduce_all.sh gates` re-runs it -- together with the 137-assertion
red-line presence check -- against the JSONs below, with no warehouses, no
network and no LaTeX.

<!-- POSTSTUDY_BLOCK_BEGIN generated by scripts/gen_readme_poststudy.py; do not hand-edit -->
### Post-registration studies (2026-08-20)

Three robustness studies answer the three most predictable review
objections --- is the n=60 headline subset-stable, how far does non-LLM
temporal-SQL machinery get without the governance axis, and is one LLM
sample per question enough. All three were pre-registered in
[`pilot2/poststudy_20260820/PREREG_poststudy_20260820.md`](pilot2/poststudy_20260820/PREREG_poststudy_20260820.md)
(sha256 `f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24`,
frozen before any study ran; re-asserted from the on-disk bytes by
`FREEZE_poststudy.sha256`, by every study JSON and by the number gate),
with predictions stated in advance and misses published as misses --- one
occurred, S2-P1 under its reading B, below. Nothing frozen moved:
`pilot2/runs/`, `pilot2/*.json` and `impl/certs2/` are byte-untouched;
every output is append-only under [`pilot2/poststudy_20260820/`](pilot2/poststudy_20260820/).

* **S1 --- leave-one-database-out robustness** (deterministic, zero LLM;
  evidence [`pilot2/poststudy_20260820/s1/loco_report.json`](pilot2/poststudy_20260820/s1/loco_report.json)): in
  every one of the 9 LOCO folds, every plain-baseline error stays
  >= 0.40 (minimum observed fold error 0.558),
  `governance_informed` stays below all four plain baselines, and the
  compiler stays at 0 errors. All three pre-registered predictions
  (S1-P1..P3) MET.
* **S2 --- governance-blind temporal-SQL arms** (deterministic, zero LLM,
  import-disjoint from `impl/`; evidence
  [`pilot2/poststudy_20260820/s2/tsql_summary.json`](pilot2/poststudy_20260820/s2/tsql_summary.json), per-question
  ledger `s2/tsql_ledger.json`): the same-window latest-version arm
  TSQL-W answers 60/60 with zero refusal declarations and errs
  28/60 = 46.7% under the
  frozen-literal scoring --- exactly level with the governance-informed
  LLM arm's 28/60 --- or 23/60 =
  38.3% when its 5 bare `NULL`s are credited as
  implicit refusals; value questions 6/33 under both
  readings; the all-history twin TSQL-H errs 54/60 = 90.0%.
  **Published prediction miss**: S2-P1 predicted 0/15 refusal-gold
  correct for both arms, and under the pre-declared NULL-as-implicit-
  refusal reading B the 5 bare `NULL`s score 5/15, so
  S2-P1 is recorded **MISSED under reading B** (MET under the
  frozen-literal reading A; both readings are computed in full in the
  JSON and both are asserted by the number gate, so neither can be
  cherry-picked).
* **S3 --- repetition study** (4 new reps per headline arm, LLM,
  paid; evidence [`pilot2/poststudy_20260820/s3/s3_summary.json`](pilot2/poststudy_20260820/s3/s3_summary.json),
  response caches `s3/runs_rep/`, call log `s3/call_log.jsonl`): across
  5 reps (rep 1 := the frozen main-study run, reused not
  re-run), `baseline_claude` errs 35-37/60 and
  `governance_informed` 25-28/60; the
  reference-above-governance ordering holds in all 5 reps;
  pooled per-question flip rate 4/60 (reference) and
  8/60 (governance), i.e. <= 13.3%
  per arm. All four predictions (S3-P1..P4) pass; 0 misses.

**Re-running.** S1 and S2 are deterministic and LLM-free (S1 needs
nothing beyond the shipped JSONs; S2 re-executes SQL, so it needs the
rebuilt warehouses). S3 needs your own LLM keys/gateway, exactly as in
"Re-running the arms" below --- and, as there, the shipped caches make
re-running unnecessary for any claim: `s3/make_s3_summary.py` re-scores
reps 2-5 from `s3/runs_rep/` with zero LLM calls. The study
scripts (`s1/s1_loco_analysis.py`, `s2/tsql_arms.py`, `s3/rep_harness.py`)
are shipped byte-frozen from the study tree and keep authors'-machine
path constants (the section-7 policy: frozen originals are not
re-authored for the artifact); independent re-verification of every
paper-body number they feed goes through `./reproduce_all.sh gates`,
whose poststudy block re-derives each one from the study JSONs --- the S1
fold matrix cell-by-cell from the same per-question verdict matrix the
rest of the gate already uses.

*This subsection --- and this README's page/assertion counts --- is
generated by
[`scripts/gen_readme_poststudy.py`](scripts/gen_readme_poststudy.py) from
the study JSONs; `python3 scripts/gen_readme_poststudy.py --check`
re-asserts it byte-for-byte.*
<!-- POSTSTUDY_BLOCK_END -->

<!-- POSTSTUDY2_BLOCK_BEGIN generated by scripts/gen_readme_poststudy2.py; do not hand-edit -->
### Post-registration studies, battery 2 (2026-08-23)

A second pre-registered battery hardens four more threat sentences ---
uncertainty on the paired headline contrast, cost-model scalability,
the cross-lingual protocol, and the input modality. All four studies
were pre-registered in
[`pilot2/poststudy2_20260823/PREREG_poststudy2_20260823.md`](pilot2/poststudy2_20260823/PREREG_poststudy2_20260823.md)
(sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669`,
frozen before any study ran and re-asserted from the on-disk bytes by
`FREEZE_poststudy2.sha256`, by every study JSON and by the number gate),
misses published as misses --- 3 occurred
(S4-P1, S4-P2, S5-P1), plus the strict per-certificate reading of S5-P2,
below; nothing frozen moved, every output is append-only under
[`pilot2/poststudy2_20260823/`](pilot2/poststudy2_20260823/), and an adversarial re-derivation of all four studies
is recorded in `pilot2/poststudy2_20260823/VERIFICATION2.md` (verdict: all four CONFIRMED).
**S4** (deterministic, zero LLM; `s4/s4_summary.json`) puts a 9-cluster
bootstrap CI on the paired reference-minus-arm error difference: the
governance contrast's CI [-0.050, +0.300] includes 0, so
**S4-P1 is a published MISS** (the 36-vs-28-of-60 headline gap
is real but not resolvable at 95% under 9 clusters), and one trivial
variant (`trivial_v3`) excludes 0 on the harmful side, so **S4-P2 is a
published MISS**; the per-rep elimination restatement (S4-P3) is MET.
**S5** (deterministic, zero LLM; `s5/s5_cost_sweep.json`) re-measures
warm verify cost on 6 row-scale substrates of `financial`
(0.125x-4x) plus a windows-span axis: growth
1x-to-4x is 1.26x (strongly sublinear, within the pre-registered
linear bound) but one sub-noise dip breaks the strict monotonicity
clause, so **S5-P1 is a published MISS**; the verify/answer band (S5-P2)
is MET on its declared median statistic with the stricter
every-certificate reading published as a MISS alongside; the full-scan
census (S5-P3) is MET with 0 full-scan audits at every scale. The
scaled substrates themselves are deterministically rebuildable and not
shipped (`s5/SUBSTRATES.md`). S5 also carries the battery's one
**provenance correction**: the sweep script cited a
62-hex-char corrupted copy of the
prereg sha in 2 metadata fields of
its output JSON; the defect was caught by the adversarial verification,
corrected in place by `s5/fix_provenance.py` from the recomputed on-disk
hash, logged in the JSON's own `provenance_correction` block --- and it
is metadata-only: no measured number, verdict or certificate changed,
nothing was re-measured. **S6** (LLM, paid; `s6/s6_summary.json`, frozen
EN questions + sha freeze, caches `s6/runs_en/`, call log
`s6/call_log_en.jsonl`) runs the same-protocol English-question control
the battery-1 README could only concede was absent: both headline arms
move by exactly one question (35/60 and 29/60 in English
against the frozen 36/60 and 28/60), the
reference-above-governance ordering persists, and the governance arm
still errs 5/7 of the
probe-only refusal questions --- all four predictions MET, and the
paper's cross-lingual threat sentence now states the measured control
instead of the concession. **S7** (LLM, paid; `s7/s7_summary.json`,
per-question ledger `s7/s7_ledger.json`, caches `s7/runs_sigma/`) has
the same backbone extract the binding request $\sigma$ from the bare
question text and hands it to the frozen compiler: exact full-$\sigma$
recovery on 40/60, end-to-end error 5/60 against the
governance-informed arm's 28/60, and every exactly-recovered
$\sigma$ is end-to-end correct --- all four predictions MET; the
paper's input-modality threat sentence now carries the measurement.
Re-verification of every paper-body number the battery feeds goes
through `./reproduce_all.sh gates` (the poststudy2 sub-block re-derives
each one from these JSONs and the frozen verdict matrix).

*This subsection is generated by
[`scripts/gen_readme_poststudy2.py`](scripts/gen_readme_poststudy2.py)
from the battery-2 study JSONs;
`python3 scripts/gen_readme_poststudy2.py --check` re-asserts it
byte-for-byte.*
<!-- POSTSTUDY2_BLOCK_END -->

### Post-registration study 3 (2026-08-26): verifier hardening V6a+

*Added 2026-08-26, as a plain dated note.* An external review
(2026-08-26) demonstrated that the earlier check V6a accepted
semantically wrong SQL mutations of a genuine certificate (wrong
aggregate, swapped legs, constant output, narrowed window) while
touching only certified tables, windows and non-blacklisted aggregates.
We reproduced all five mutations against the real verifier, froze the
hardening plan in
[`pilot2/poststudy3_20260826/PREREG_poststudy3_20260826.md`](pilot2/poststudy3_20260826/PREREG_poststudy3_20260826.md)
(sha256 `426017ddfd8af8608e452b44175e2158c620c2e8cebe3a17572ee3fe15d7a192`,
frozen before the hardened verifier ran on any certificate or forgery),
and then added the fail-closed structural check **V6a+**
([`impl/asof_verifier/v6aplus.py`](impl/asof_verifier/v6aplus.py), wired
into `chk.py`/`ci_check.py`; SQL parsed with DuckDB's own
`json_serialize_sql`, no compiler import — the import-disjointness red
line still holds). Post-registration results
([`pilot2/poststudy3_20260826/results/v6aplus_summary.json`](pilot2/poststudy3_20260826/results/v6aplus_summary.json)):
all **60/60 genuine certificates still ACCEPT** (45 V6a+ PASS + 15
REFUSE certificates SKIPped — no answer SQL to validate); the **5
pinned reproduction mutations REJECT**, each with its pinned reason
code (`V6P_MEASURE`/`V6P_PARSE`/`V6P_LEG_ROLE`/`V6P_SHAPE`/`V6P_WINDOW`;
shipped as regressions in `impl/asof_verifier/pinned_regressions/`);
the **31 new F6–F10 forgeries over 22 bases all REJECT**
(`impl/asof_verifier/forge_v6aplus.py` + `forge_v6aplus_out/`); and the
**34 original F1–F5 forgeries still all REJECT** with their frozen
attribution. All four pre-registered predictions hold. The paper's
Definition 5.3, Theorem 5.2(b) scope and §7.5 forgery counts now state
exactly what V6a+ decides, and the earlier version's gap is disclosed,
not erased. `./reproduce_all.sh verify` runs the V6a+ battery as its
own stage; everything frozen stayed byte-untouched, and every output is
append-only under
[`pilot2/poststudy3_20260826/`](pilot2/poststudy3_20260826/).

### Post-registration study 4 (2026-08-27): verifier hardening V6a+, round 2

*Added 2026-08-27, as a plain dated note.* A second external review
(2026-08-27), reproduced independently, showed that the round-1 V6a+
still ACCEPTed a genuine ratio/delta certificate whose outer `SELECT`
carried a top-level `WHERE` that filtered the scalar answer to zero rows
(`WHERE 1=0`, `WHERE 'a'='b'`): the ratio/delta checks did not reject an
outer `where_clause`, and no check executed the answer to test its shape.
We reproduced both confirmed exploits against the real verifier, froze the
plan in
[`pilot2/poststudy4_20260827/PREREG_poststudy4_20260827.md`](pilot2/poststudy4_20260827/PREREG_poststudy4_20260827.md)
(sha256 `a7ff13112c6988e98fceb238972a0ae0fff87a037b9f9630577fc618c04b1a75`,
frozen before the hardened verifier ran on any certificate or forgery),
and then added two fail-closed fixes to
[`impl/asof_verifier/v6aplus.py`](impl/asof_verifier/v6aplus.py): an
**outer-filter closure** (`_plain_node` rejects a non-null outer `WHERE`
by default, `allow_outer_where=False`, with `V6P_SHAPE`; the scalar outer
nodes of atomic/ratio/delta route through that default) and an
**execution-shape check** (`V6a+x`, appended last so every prior
first-FAIL attribution stays frozen, executes each answer SQL read-only
against the warehouse and requires the certified row/column arity, else
`V6P_ARITY`). Post-registration results
([`pilot2/poststudy4_20260827/results/v6aplus_v4_summary.json`](pilot2/poststudy4_20260827/results/v6aplus_v4_summary.json),
report in `results/V6APLUS_V4_REPORT.md`): all **60/60 genuine
certificates still ACCEPT** (45 V6a+ PASS + 15 REFUSE SKIPped, identically
under V6a+x); the two confirmed exploits and the **8 new F11
outer-row-filter forgeries over 8 bases all REJECT** (each on `V6P_SHAPE`,
with the `V6P_ARITY` backstop also firing on the 7 non-trivial ones); the
denotation-preserving `WHERE 1=1` control is caught by the structural
closure alone, proving the two fixes are independent; a corpus sweep that
appends `WHERE 1=0` to every genuine answer SQL **REJECTs 45/45
answer-bearing bases** (the remaining 15 are REFUSE certificates with no
answer SQL to filter); and the **prior 70-forgery battery (34 F1–F5, 31
F6–F10, 5 round-1 pins) still all REJECT**, with two new round-2 exploit
pins shipped under `impl/asof_verifier/pinned_regressions/`. The forgery
total is now **78** (70 + the 8-forgery F11 family; the grand total of
forged certificates including the 2 round-2 pins is 80). The paper's §5
verifier definition, Theorem scope and §7.5 forgery counts state exactly
what V6a+ now decides, and the round-1 gap is disclosed, not erased.
`./reproduce_all.sh verify` runs the extended V6a+ battery; everything
frozen stayed byte-untouched, and every output is append-only under
[`pilot2/poststudy4_20260827/`](pilot2/poststudy4_20260827/).

## 3. Repository layout

```
pilot2/            benchmark + arms evidence
  build/           deterministic build: BIRD/Spider -> warehouses + gov seeds + gold
  ci/              leak / nondegeneracy / witness gates (+ frozen reports)
  domains/<db>/    questions.json, provenance.json, gov_seed/*.jsonl
                   (warehouse.duckdb rebuilt locally; not shipped)
  prompt_pack/     the exact prompts (schema + governance packs, MANIFEST, rebuilder)
  runs/<arm>/      frozen LLM response caches, 60 per arm, incl. the voided
                   trivial_v2 first run (trivial_v2__VOID_RUN1_2026-08-04/)
  PREREG_pilot2_arms.md      pre-registration (frozen before any result)
  FREEZE_pilot2_arms.json    sha256 freeze list the runner re-asserts (A0)
  make_pilot2_summary.py     cache -> scored matrix (pure function, no LLM)
  poststudy_20260820/        post-registration studies S1/S2/S3 (see the
                             subsection above): PREREG + sha freeze, per-study
                             reports + JSON evidence, study scripts, S3 rep
                             caches runs_rep/ + call_log.jsonl
impl/
  asof_compiler/   binding compiler (core, certificate, pilot2 adapters, acceptance)
  asof_verifier/   independent verifier chk.py + red lines + forgery battery
  certs2/          the 60 frozen certificates
  cost_p2.json     cost measurements (measure_cost.py)
  measure_adm_scan.py  clause-(iv) replay scan volume, timing-free
  adm_scan_p2.json     its output: 0 full-scan audits, all window-bounded
pilot/run_pilot.py frozen scorer (sha-asserted import; see pilot/README.md)
paper/main.tex     the submitted body sources, shipped so that the number
paper/sections/    and red-line gates below are runnable, not just readable
paper/tools/       check_numbers.py (588 assertions) + check_redlines.py (163)
                   + check_bodylength.py (needs a compiled PDF; not wired)
paper/figures      every figure/number script (see map above)
paper/tables       generated reference tables + cell-level audit JSONs
tr/asof-gov-tr.pdf extended technical report (161 pp.)
scripts/           path-portable wrappers (originals stay byte-frozen)
manifests/         sha256 of source data + of every tracked file
fetch_and_rebuild.sh   official-channel downloads -> rebuild everything derived
reproduce_all.sh       gates -> scoring -> figures -> tables (-> verifier +
                       forgery battery + cost)
```

## 4. Quickstart

```bash
# 0) python3.9+ with:  pip install -r requirements.txt

# 1) the entry gate.  Needs NOTHING -- no warehouses, no network, no LaTeX,
#    no LLM keys.  Start here.
bash reproduce_all.sh gates   # stage 0 only: the paper's 588-assertion number
                              #   gate + 163-assertion red-line gate over the
                              #   shipped .tex sources.

# 2) rebuild the data substrate (~1 GB, BIRD auto-download; Spider needs one
#    manual download from the official page -- the script tells you exactly what)
./fetch_and_rebuild.sh

# 3) reproduce every number/figure/table from the frozen evidence, zero LLM calls
./reproduce_all.sh            # light: gates + score -> figures -> tables, diffed
./reproduce_all.sh verify     # + compiler acceptance (certs byte-diffed vs certs2),
                              #   verifier replay 60/60 + strict track,
                              #   the forgery battery (34/34 over 11 bases),
                              #   the V6a+ hardening battery (5 pinned
                              #   mutations + 31 F6-F10 forgeries, all REJECT),
                              #   import-disjointness red line, CI gates,
                              #   cost re-measurement (fresh medians printed,
                              #   shape-asserted, NOT diffed: wall clock)
```

Everything the light path regenerates is byte-diffed against the committed
copies (`pilot2_arms_summary.json`, `pilot2_summary.json`,
`fig_data_pilot2.json`, `tab_*.tex` + audits); PASS/FAIL is printed per gate.

**What needs what**

| Step | Needs network | Needs warehouses | Needs LLM keys |
|---|---|---|---|
| `reproduce_all.sh gates` | no | **no** | no |
| `fetch_and_rebuild.sh` | yes (official BIRD link; Spider manual) | builds them | no |
| `reproduce_all.sh` light | no | yes | no |
| `reproduce_all.sh verify` | no | yes | no |
| re-running the arms | yes | yes | yes (your own) |

**Re-running the arms** (optional, costs money, not needed for any claim):
`pilot2/run_pilot2_arms.py` refuses to overwrite any cached response
(append-only cache) and pre-flights the sha256 freeze list (A0), the prompt
pack byte-rebuild (A3) and the leak assertions (A2) before the first call.
It calls models through the authors' local gateway CLI: `run_pilot.llm()`
executes `python3 ~/.claude/skills/llmhub/bin/llmhub.py chat --model <m>
--prompt <p>` and reads the completion from stdout. To re-run, place your own
shim implementing that CLI at that path (do **not** edit `pilot/run_pilot.py`
— its sha256 is asserted). The frozen caches make all of this unnecessary for
reproduction.

## 5. What is deliberately NOT in this repository

* **No `warehouse.duckdb`, no BIRD/Spider source data** (~1.3 GB). Licensing
  of the sources stays with their distributors (both CC BY-SA 4.0);
  `fetch_and_rebuild.sh` + `manifests/sha256_sources.txt` rebuild and verify
  bit-comparable warehouses locally. See
  [`DATA_AND_DOCS_LICENSE.md`](DATA_AND_DOCS_LICENSE.md).
* **No LLM credentials / gateway code** and no way to silently re-spend money:
  scoring is a pure function of the frozen caches.
* **No enterprise-track data.** The project was motivated by a production
  enterprise study; per the authors' ruling, that track contributes motivation
  only. Its data, questions, certificates and per-domain code are absent.
  Residual *identifiers* (cluster names like `AIBUY`/`rma`, and the D1–D15
  integration ledger of Table 4) appear in a bounded set of frozen files:
  the reports (`impl/INTEGRATION_REPORT.md`, `impl/INDEPENDENCE_REPORT.md`,
  `impl/PORT_REPORT.md`); code kept for import/lineage reasons
  (`impl/asof_compiler/adapters.py` — the pilot-1 adapter the compiler
  package imports, feeding no pilot2 result — plus domain-convention
  branches and header comments in `impl/asof_verifier/chk.py` and
  `impl/asof_compiler/core.py`, and the pilot-1 figure readers
  `paper/figures/extract_data.py` / `paper/figures/figD_extract.py`, which
  read paths absent from this repository and cannot run here); the Table-4
  pipeline (`paper/tools/gen_table_divergence.py`,
  `paper/tables/tab_divergence.audit.json`); design notes citing the
  motivating measurements (`pilot2/DESIGN_SPEC.md`,
  `pilot2/build/questions_def.py`, two `questions.json` notes); and the
  company-named key-file path in `pilot/run_pilot.py` — exactly as the
  paper itself discloses the motivation track. No enterprise data row
  exists anywhere in this repository.

## 6. Determinism and environment

* Build, gold materialization, certificates and scoring are deterministic;
  `scripts/rebuild_portable.py` ends by re-hashing every rebuilt frozen file
  against `pilot2/FREEZE_pilot2_arms.json` (108 files + aggregate).
* Reference environment: `requirements.txt` (python 3.9.6, duckdb 1.4.4,
  matplotlib 3.9.4). A different duckdb major may change float text in
  regenerated gold — the freeze check will tell you loudly.
* Figure PDFs are regenerated but not byte-asserted (matplotlib embeds
  timestamps); every number behind them is byte-asserted via
  `fig_data_pilot2.json`.
* The three CI gates rewrite `pilot2/ci/*_report.json` in place;
  `reproduce_all.sh verify` diffs them against the committed reports.
* The frozen pre-registration documents and build/acceptance reports are
  bilingual (Chinese/English) and sha-pinned — the number gate parses them
  as frozen bytes, which is why they are shipped verbatim.

## 7. Portability delta

Every file that produced paper evidence is shipped **byte-identical** to the
frozen originals (the freeze list in `pilot2/FREEZE_pilot2_arms.json` still
verifies, including `pilot/run_pilot.py` via `../pilot/run_pilot.py`). The
only authors'-machine paths that affect *runtime* live in
`pilot2/build/lib_build.py` and `pilot2/ci/*.py` module constants; the
wrappers in `scripts/` override those constants at run time instead of
editing the files. (Frozen reports, `provenance.json` files and header
comments additionally *mention* authors'-machine paths as historical
record; they are inert — nothing reads them.) New files added for the
artifact: `scripts/*`, `fetch_and_rebuild.sh`, `reproduce_all.sh`,
`manifests/*`, `README.md`, licenses, `pilot/README.md`.

Also shipped from the paper tree, so that the two gates the paper cites are
executable here rather than merely described: `paper/sections/*.tex` and the
full `paper/tools/*.py` (byte-identical), and `paper/main.tex`
(byte-identical body; a submission-tracking comment header was removed —
comments never reach the typeset PDF).  These are the same sources Part I of
`tr/asof-gov-tr.pdf` typesets, so they disclose nothing the report did not
already carry.

## 8. Citing

See [`CITATION.cff`](CITATION.cff). BIRD and Spider must be cited whenever the
rebuilt warehouses are used; see `DATA_AND_DOCS_LICENSE.md`.
