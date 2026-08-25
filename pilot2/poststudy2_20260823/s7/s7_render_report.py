#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s7_render_report.py — render S7_REPORT.md from s7_summary.json +
s7_ledger.json ONLY (no recomputation, no other data source; deterministic).

prereg sha256: 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

FIELD_ORDER = [
    "as_of", "declared_at", "metric_alias", "scope", "pinned_version",
    "cross_window", "anchor_override", "window_request",
    "requested_granularity", "requested_time_gran", "presentation",
    "ctx_role", "periods",
]


def main() -> int:
    S = json.loads((HERE / "s7_summary.json").read_text(encoding="utf-8"))
    L = json.loads((HERE / "s7_ledger.json").read_text(encoding="utf-8"))
    n = S["n"]
    P = S["predictions"]

    def mark(met):
        return "**MET**" if met else "**MISS**"

    lines = []
    A = lines.append
    A("# S7 — NL→σ arm, Stage B full run (post-registration report)")
    A("")
    A(f"- Governing prereg: `PREREG_poststudy2_20260823.md`, "
      f"sha256 `{S['prereg_sha256']}`")
    A(f"- Extractor model: `{S['model']}` (llmhub, channel `tuzi` asserted at "
      f"preflight); 1 sample + 1 format-retry; hard call budget 120")
    A(f"- Bridge: extracted σ → frozen `impl/asof_compiler` (Pilot2Adapter) → "
      f"frozen `acceptance_pilot2` gate-1 scoring rules")
    A(f"- Arm purity: questions loaded 3-key-stripped "
      f"({{qid, domain, question_zh}}); prompt-leak preflight over gold-side "
      f"fields passed before any call")
    A(f"- This run: {S['llm_calls_this_run']} LLM calls, "
      f"{S['cache_hits_this_run']} cache hits (the 3 Stage-A smoke questions "
      f"were cache-skipped, never re-called)")
    A(f"- Caches: `s7/runs_sigma/<qid>.json` (append-only, refuse-overwrite); "
      f"raw harness output `s7_nl2sigma_full.json`; adjudication "
      f"`s7_summary.json` + `s7_ledger.json` (this report is rendered from "
      f"those two JSONs only)")
    A("")
    A("## Stage-B fix-forward changes to the Stage-A harness (documented)")
    A("")
    A("1. Cache directory repointed `runs_nl2sigma/` → `runs_sigma/` to match "
      "the Stage-B tasking; the 3 smoke caches were copied in byte-identical "
      "(originals retained; append-only).")
    A("2. The full run now passes the hard call budget explicitly "
      "(`budget=120` = 60 questions × structural max 2 calls).")
    A("3. The Stage-A harness was preserved byte-for-byte as "
      "`nl2sigma_harness_stageA_orig.py` before editing.")
    A("")
    A("No prompt, schema, scoring, or bridging logic changed between the "
      "Stage-A smoke and this full run.")
    A("")
    A("## Headline numbers")
    A("")
    A("| quantity | value |")
    A("|---|---|")
    A(f"| questions | {n} |")
    A(f"| exact full-σ recovery | {S['exact_full_sigma']}/{n} |")
    A(f"| end-to-end correct | {S['end_to_end_correct']}/{n} |")
    A(f"| end-to-end error | {S['end_to_end_error']}/{n} |")
    A(f"| metric-identity (metric_alias) recovery | "
      f"{S['per_field_match']['metric_alias']}/{n} |")
    A(f"| extraction errors (invalid JSON after retry) | "
      f"{len(S['extraction_error_qids'])} |")
    A(f"| compile errors (σ crashed frozen compiler) | "
      f"{len(S['compile_error_qids'])} |")
    A(f"| format-retried questions | {len(S['format_retried_qids'])} |")
    A("")
    A(f"Frozen reference points (for context): governance-informed arm error "
      f"{S['reference_points']['governance_informed_error_frozen']}/60; "
      f"backbone error "
      f"{S['reference_points']['backbone_error_frozen']}/60.")
    A("")
    A("## Prediction adjudication (exactly as pre-registered)")
    A("")
    p1 = P["S7-P1"]
    A(f"### S7-P1 — {mark(p1['met'])}")
    A(f"> {p1['statement']}")
    A(f"Observed: exact full-σ recovery "
      f"{p1['observed']['exact_full_sigma']}/{n} vs threshold "
      f"≥ {p1['threshold']}.")
    A("")
    p2 = P["S7-P2"]
    A(f"### S7-P2 — {mark(p2['met'])}")
    A(f"> {p2['statement']}")
    A(f"Observed: end-to-end error {p2['observed']['end_to_end_error']}/{n} "
      f"vs threshold ≤ {p2['threshold']}.")
    A("")
    p3 = P["S7-P3"]
    A(f"### S7-P3 — {mark(p3['met'])}")
    A(f"> {p3['statement']}")
    w = p3["observed"]["witnesses"]
    A(f"Observed: {p3['observed']['exact_sigma_questions']} exact-σ "
      f"questions, {p3['observed']['errors_among_them']} of them scored "
      f"error." + (f" Witnesses: {', '.join(w)}." if w else ""))
    A("")
    p4 = P["S7-P4"]
    A(f"### S7-P4 — {mark(p4['met'])}")
    A(f"> {p4['statement']}")
    o = p4["observed"]
    A(f"Observed: metric_alias recovery {o['metric_alias_match']}/{n} vs "
      f"threshold ≥ {p4['threshold']}; metric_alias mismatches "
      f"{o['metric_alias_mismatches']} vs window/scope/version-field "
      f"mismatches {o['window_scope_version_mismatches_total']} "
      f"(fields: {', '.join(o['window_scope_version_fields'])}); "
      f"concentration clause "
      f"{'holds' if o['concentration_ok'] else 'FAILS'}.")
    A("")
    A(f"Descriptive (outside the gate): `as_of` — a time-point field outside "
      f"the window/scope/version family — is the single largest mismatch "
      f"field at {o['as_of_mismatches_descriptive']}/{n}; see the per-field "
      f"table and the ledger for the mismatch content.")
    A("")
    A(f"**Predictions met: {S['predictions_met']}.** Misses above are "
      f"published as misses.")
    A("")
    A("## Per-field σ-recovery accuracy")
    A("")
    A("| field | match | mismatch |")
    A("|---|---|---|")
    for f in FIELD_ORDER:
        A(f"| `{f}` | {S['per_field_match'][f]}/{n} | "
          f"{S['per_field_mismatch'][f]} |")
    A("")
    A("## By domain")
    A("")
    A("| domain | n | exact σ | e2e correct | e2e error |")
    A("|---|---|---|---|---|")
    for d in sorted(S["by_domain"]):
        v = S["by_domain"][d]
        A(f"| {d} | {v['n']} | {v['exact_full_sigma']} | "
          f"{v['e2e_correct']} | {v['e2e_error']} |")
    A("")
    A("## By gold kind")
    A("")
    A("| gold kind | n | exact σ | e2e correct | e2e error |")
    A("|---|---|---|---|---|")
    for k in sorted(S["by_gold_kind"]):
        v = S["by_gold_kind"][k]
        A(f"| {k} | {v['n']} | {v['exact_full_sigma']} | "
          f"{v['e2e_correct']} | {v['e2e_error']} |")
    A("")
    A("## Error ledger (all questions scored error)")
    A("")
    A("| qid | gold kind | outcome | why | σ mismatched fields |")
    A("|---|---|---|---|---|")
    any_err = False
    for r in L["ledger"]:
        if r["verdict"] == "correct":
            continue
        any_err = True
        mm = ", ".join(sorted(r["sigma_mismatches"])) or "—"
        oc = r["compile_outcome"]
        od = oc["kind"]
        if oc.get("reason"):
            od += f"({oc['reason']}/{oc.get('subtype')})"
        if oc.get("rewrite_kinds"):
            od += f"({'+'.join(oc['rewrite_kinds'])})"
        why = (r["why"] or "").replace("|", "\\|")[:160]
        A(f"| {r['qid']} | {r['gold_kind']} | {od} | {why} | {mm} |")
    if not any_err:
        A("| — | — | — | — | — |")
    A("")
    A("## Full per-question ledger")
    A("")
    A("See `s7_ledger.json` (per question: extracted σ, 13-field match "
      "vector, compile outcome, gold kind, verdict).")
    A("")

    (HERE / "S7_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote S7_REPORT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
