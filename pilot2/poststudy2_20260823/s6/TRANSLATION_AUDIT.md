# S6 Stage A — Translation Audit (translations + audit + freeze; no scored calls)

Governing prereg: `PREREG_poststudy2_20260823.md`, sha256 `838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669`.

Translator: `claude-opus-4-6 (llmhub), question_zh only as input`. Each call saw the fixed gold-invariant instruction block plus `question_zh` ONLY — no structured fields, no gold-side fields. Raw outputs: `translation_raw/<qid>.json` (60 files, append-only). Structured fields (`as_of`, `declared_at`, `windows`, `metric_alias`, `pinned_version`, gold fields) were read by the AUDIT only (`audit_s6.py`); they feed no scored arm.

## Audit protocol (deterministic, `audit_s6.py`)

Per question, field-by-field per the prereg checklist: declared-at instant + phrasing; as-of token multiset ZH==EN and consistency with the `as_of` field; every numeric/date token of the ZH preserved in the EN (month-name renderings excused) and **no numeric/date token added**; ASCII identifiers preserved case-sensitively; window/caliber/disclosure/version marker keywords; metric-alias meaning keywords; identical ZH aliases rendered as one identical EN alias phrase; per-qid required phrases (e.g. CA-Q6 `charter authorization date`, F1-Q3 version-pin). Plus the string-level leak audit over the English texts mirroring `pilot2/ci/leak_check.py`, extended per the S6 spec: gold values (>=8 chars, incl. structured-gold leaves), gold SQL / SQL keywords, window endpoints not present in the own ZH text, and refusal-class tokens must not appear.

## Tallies

| item | raw round | final round |
|---|---|---|
| questions audited | 60 | 60 |
| field checks run | 951 | 951 |
| questions failing field checks | 6 | 0 |
| alias-consistency groups checked | 13 | 13 |
| alias-consistency failures | 2 | 0 |
| leak checks run (final) | — | 2440 |
| leak problems | 0 | 0 |

Leak-check breakdown (final round): gold_sql=60, gold_value_ge8=1560, gold_value_int_gt30=60, refusal_classes=600, sql_keyword=60, window_endpoints=100; forbidden gold strings (>=8 chars) screened: 26.

## Raw-round findings and fixes (8 fixes)

Raw translations were already leak-clean; every finding below is a meaning/consistency finding. Automated raw-round flags: 6 questions via field checks + 2 alias-consistency groups (FIN-Q5/FIN-Q7 `当月交易笔数`, FIN-Q3/FIN-Q8 `罚息交易占比`; FIN-Q5 flagged by both routes). One additional finding (EF2-Q5) is a manual auditor finding. Each fix was re-audited; the final round passes every check.

### CA-Q6 — automated: per-qid required phrase 'charter authorization date'

- reason: metric/window-anchor meaning: ZH 特许授权日期 names the charter authorization date anchor (california_schools charter semantics); raw had 'franchise authorization date', which loses the anchor identity the question deliberately references.
- raw: `With 2015-09-01 as the declaration instant, compute the free meal rate for the 2014-2015 school year, windowed by franchise authorization date.`
- fixed: `With 2015-09-01 as the declaration instant, compute the free meal rate for the 2014-2015 school year, windowed by charter authorization date.`

### CARD-Q6 — automated: alias keyword check for 保留卡收藏溢价率

- reason: metric-alias meaning: ZH 保留卡收藏溢价率 refers to reserved cards (MTG Reserved List) and a collector premium; raw 'retained card collection premium rate' obscures the alias meaning.
- raw: `With 2017-03-01 as the declaration instant, what is the retained card collection premium rate for February 2017?`
- fixed: `With 2017-03-01 as the declaration instant, what is the reserved card collector premium rate for February 2017?`

### CODE-Q4 — automated: alias keyword check for 用户采纳答案数报表

- reason: metric-alias meaning + intra-domain consistency: 采纳 is rendered 'accepted/acceptance' everywhere else in this domain (CODE-Q1/Q2 'question acceptance rate', CODE-Q7 'accepted answers'); raw had 'adopted answer count report'.
- raw: `With 2013-08-01 as the declaration instant, provide the June 2013 adopted answer count report for each user (user level).`
- fixed: `With 2013-08-01 as the declaration instant, provide the June 2013 accepted answer count report for each user (user level).`

### EF2-Q5 — manual: auditor read-through (duplication artifact)

- reason: nothing-added discipline: raw duplicated the phrase 'snapshot date' ('...on the snapshot date as-of 2013-12-25 snapshot date?'); duplicate removed, aligning with EF2-Q1's rendering of the same alias.
- raw: `With 2014-02-01 as the declaration instant, what is the average composite rating of players on the snapshot date as-of 2013-12-25 snapshot date?`
- fixed: `With 2014-02-01 as the declaration instant, what is the average composite rating of players on the snapshot date as-of 2013-12-25?`

### EF2-Q6 — automated: alias keyword check for 评分归一当日胜率

- reason: metric-alias meaning: 评分 in this domain is the player rating (综合评分 -> composite rating in EF2-Q1/Q5); raw 'score-normalized' mistakes rating for match score.
- raw: `With 2014-02-01 as the declaration instant, what is the score-normalized same-day win rate for the as-of 2013-12-01 single-day window?`
- fixed: `With 2014-02-01 as the declaration instant, what is the rating-normalized same-day win rate for the as-of 2013-12-01 single-day window?`

### FIN-Q5 — automated: alias consistency check for 当月交易笔数

- reason: metric-alias consistency: FIN-Q5 and FIN-Q7 share the identical ZH alias 当月交易笔数; raw rendered FIN-Q5 as 'the number of transactions' but FIN-Q7 as 'the monthly transaction count'; harmonized to one alias string.
- raw: `With 1997-06-15 as the declaration instant, what is the number of transactions for June 1996 (as-of 1996-06-15 the containing month window)?`
- fixed: `With 1997-06-15 as the declaration instant, what is the monthly transaction count for June 1996 (as-of 1996-06-15 the containing month window)?`

### FIN-Q8 — automated: alias consistency check for 罚息交易占比

- reason: metric-alias consistency: FIN-Q3 and FIN-Q8 share the identical ZH alias 罚息交易占比; raw rendered Q3 'proportion' but Q8 'share'; harmonized to 'proportion'.
- raw: `Calculate the penalty interest transaction share, but with the numerator taken from May 1997 and the denominator taken from April 1997 (declaration instant 1998-09-15).`
- fixed: `Calculate the penalty interest transaction proportion, but with the numerator taken from May 1997 and the denominator taken from April 1997 (declaration instant 1998-09-15).`

### TH-Q2 — automated: alias keyword check for 年度检查记录数

- reason: metric-alias meaning: 检查 in this medical domain means patient examinations; raw 'annual inspection records' suggests facility inspection.
- raw: `With 1996-06-01 as the declaration instant, what is the number of annual inspection records for the 1995 calendar year (as-of 1995-06-30 the containing year window)?`
- fixed: `With 1996-06-01 as the declaration instant, what is the number of annual examination records for the 1995 calendar year (as-of 1995-06-30 the containing year window)?`

## Result

Final round: **PASS** — 60/60 questions pass all field checks, 0 alias-consistency failures, 0 leak problems. `questions_en.json` (60 entries, qid -> question_en) frozen:

```
d9508f3f6e1617e080772630f51f6d1860cd0cfe1dae174b7f226ada548ba63f  questions_en.json
```

Freeze line file: `FREEZE_questions_en.sha256` (shasum -a 256 format; verify with `shasum -c` in `s6/`). n_entries=60.
