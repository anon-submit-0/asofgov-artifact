# PREREG — V6a+ outer-filter closure + execution shape check (round-2 review)

**Frozen 2026-08-27, BEFORE the fix is run on any certificate/forgery.**
Trigger: a second external-review pass (Codex, 2026-08-27) demonstrated —
and our independent reproduction against the CURRENT hardened verifier
confirmed — that V6a+ still ACCEPTs a genuine ratio/delta certificate whose
outer SELECT carries a top-level WHERE that filters the scalar answer to
zero rows (WHERE 1=0, WHERE 'a'='b'), and that no verifier path checks the
executed answer's SHAPE (exactly one row, one column). Root cause verified
code-accurate: _check_atomic rejects an outer where_clause; _check_ratio and
_check_delta do not; _plain_node permits where_clause by default. Evidence
(exploit_results.json, ROOT_CAUSE.md) preserved as pinned regressions.

## Fix scope

1. **Outer-filter closure (structural)**: _plain_node gains
   allow_outer_where=False as its DEFAULT; it rejects a non-null outer
   where_clause with V6P_SHAPE. _check_atomic, _check_ratio, _check_delta,
   _check_report, _check_attribute all route their OUTER node through the
   same default (leg/report/attribute predicate walkers, which carry a real
   FROM, keep reading their own where_clause as before). Nested set-op /
   derived-table wrappers with an outer FROM remain rejected as today
   (V2 in the repro already REJECTs).
2. **Execution shape check (semantic, fail-closed)**: the verifier executes
   each ANSWER and REWRITE certificate's answer SQL read-only against the
   warehouse and requires exactly one row and exactly one column (ratio/
   atomic) or the certified row/column arity for report/attribute forms;
   any other shape REJECTs with a new code V6P_ARITY. This is the first
   time V6a+ executes the answer SQL (previously parse-only); it uses a
   read_only DuckDB connection, no writes, and is added as a distinct
   check appended last so all frozen attributions persist.
3. **New forgery family F11 outer-row-filter**: >=6 forgeries over >=4
   bases covering WHERE 1=0, WHERE 1=1 (true but still shape-legal — must
   still ACCEPT if it is the genuine cert, REJECT only if it changes
   denotation; the family targets the FALSE/zero-row and multi-row cases),
   'a'='b', and the ratio/delta/atomic variants; plus a systematic
   mutation corpus sweep (append outer WHERE to every genuine cert and
   confirm REJECT). The 3 confirmed exploit SQLs (V1, V1c, and any other
   VULNERABLE-CONFIRMED variant) are pinned regressions.

## Predictions

- **P1**: all 60 genuine certificates still ACCEPT (the shape check must
  pass on every genuine answer — if any genuine cert now fails shape or
  outer-where, that is a real defect to publish, never a silent exception).
- **P2**: the confirmed outer-filter exploits all REJECT (V6P_SHAPE for the
  outer WHERE; V6P_ARITY as the independent backstop on zero/multi-row).
- **P3**: every F11 forgery REJECTs; the systematic append-outer-WHERE
  sweep REJECTs on all 60 bases.
- **P4**: the full prior battery still holds — 60/60 genuine ACCEPT, the
  earlier pinned regressions + F1-F10 (70 forgeries) all REJECT.

## Publication rule

Results land in the TR and artifact (poststudy4_20260827/), labelled
post-registration with this sha256. The paper's Definition 5.3 /
Theorem 5.2(b) membership statement and the E5 forgery counts are updated
to state that V6a+ now decides outer-filter membership AND checks executed
arity; the round-2 gap is disclosed, not erased. A prediction miss is
published as a miss.
