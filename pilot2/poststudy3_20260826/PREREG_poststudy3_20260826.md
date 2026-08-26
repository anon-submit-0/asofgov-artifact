# PREREG — Verifier hardening in response to external review (V6a+)

**Written and frozen 2026-08-26, BEFORE the hardened verifier is run on any
certificate or forgery.** Trigger: an external review (Codex, 2026-08-26)
demonstrated — and our independent reproduction against the real verifier
and a rebuilt card_games warehouse confirmed — that check V6a accepts
semantically wrong SQL mutations of a genuine certificate: (a) numerator
aggregate replaced by COUNT(DISTINCT rulings.date), (b) numerator/
denominator legs swapped, (c) a constant multi-row SELECT 999, and (d) a
narrowed time predicate, all ACCEPTed while touching only certified tables,
windows, and non-blacklisted aggregates. The five reproduction artifacts
are preserved (scratchpad m1-repro) and become mandatory regression cases.

## Hardening scope (V6a+)

A fail-closed structural check, implemented in the verifier's own tree with
no import from the compiler (import-disjointness preserved), parsing each
certificate's SQL with DuckDB's own parser (json_serialize_sql; no new
dependency) and validating against independently loaded governance seeds:
1. **Template membership, fail-closed**: anything unparseable, non-scalar
   (not exactly one row, one column), constant-only, or outside the
   declared shape (single aggregate per leg; ratio = leg/leg) is REJECT.
2. **Measure implementation**: each leg's aggregate function and argument
   must implement that leg's registered gov_measure_def measure (count /
   count-distinct-of-registered-key / sum-of-registered-column, as
   registered — the registered form, not a lookalike).
3. **Leg-role binding**: the numerator position must be computed from the
   numerator leg's registered table/column and the denominator position
   from the denominator leg's; swapped legs REJECT.
4. **Registered predicates**: every predicate registered for the binding
   (time window on the anchor column, plus non-temporal registered
   predicates) must appear with the certified constants; extra predicates
   that narrow or widen a certified window REJECT.
5. **Join keys**: multi-table legs must join exactly on the registered
   routing keys.

## New forgery families (each over multiple genuine bases)

F6 wrong-aggregate, F7 leg-swap, F8 wrong/absent registered predicate,
F9 narrowed-or-widened window predicate, F10 constant/multi-row output.
Plus the five preserved reproduction mutations as pinned regressions.

## Predictions

- **P1**: all 60 genuine certificates still ACCEPT under V6a+ (if any
  genuine certificate fails, that is a finding to be published, not
  silently accommodated; the check may only encode REGISTERED equivalences,
  never per-certificate exceptions).
- **P2**: all five reproduction mutations REJECT.
- **P3**: every new F6–F10 forgery REJECTs.
- **P4**: the original 34 F1–F5 forgeries still all REJECT.

## Publication rule

Results land in the TR and the artifact (poststudy3_20260826/), labelled
post-registration with this document's sha256. The paper's Definition 5.3,
Theorem 5.2(b) scope, and §7.5 forgery counts are updated to state exactly
what V6a+ decides; the earlier version's gap is disclosed, not erased. A
prediction miss is published as a miss.
