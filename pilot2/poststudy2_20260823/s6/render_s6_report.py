#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render S6_REPORT.md from s6_summary.json — deterministic, zero LLM calls.
Every number in the report flows from the JSON; nothing is hand-typed.
Refuses overwrite (append-only discipline)."""
from __future__ import annotations

import json
import pathlib
import sys

S6 = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2/poststudy2_20260823/s6")
OUT = S6 / "S6_REPORT.md"


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"[REFUSE] overwrite existing report: {OUT}")
    s = json.loads((S6 / "s6_summary.json").read_text(encoding="utf-8"))

    arms = ("baseline_claude", "governance_informed")
    P = s["predictions"]
    n_met = sum(1 for p in P.values() if p["met"])
    fc = s["flip_counts"]
    pr = s["probe7"]

    def pct(x):
        return f"{x:.4f}"

    L = []
    L.append("# S6 — English-question control · Stage B report")
    L.append("")
    L.append(f"- PREREG: `PREREG_poststudy2_20260823.md` sha256 `{s['prereg_sha256']}` (read first; §S6 governs; zero design freedom).")
    L.append(f"- Frozen EN question set: `s6/questions_en.json` sha256 `{s['questions_en_sha256']}` (Stage A freeze, verified before every call).")
    L.append(f"- Protocol: model `{s['protocol']['model']}`, {s['protocol']['sampling']}.")
    L.append(f"- **Single delta** vs the byte-frozen protocol: {s['protocol']['single_delta']}.")
    L.append(f"- Scoring: {s['protocol']['scorer']}.")
    L.append(f"- Caches: `s6/runs_en/<arm>/<qid>.json`, append-only (overwrite refused); "
             f"call metadata in `s6/call_log_en.jsonl` (never in cache records).")
    L.append("")
    L.append("## Headline result")
    L.append("")
    L.append("| arm | EN errors /60 | EN error rate | ZH errors /60 (frozen) | ZH error rate |")
    L.append("|---|---|---|---|---|")
    for a in arms:
        L.append(f"| {a} | {s['error_counts_en'][a]} | {pct(s['error_rate_en'][a])} | "
                 f"{s['zh_anchors_frozen']['error_counts'][a]} | "
                 f"{pct(s['zh_anchors_frozen']['error_rate'][a])} |")
    L.append("")
    L.append(f"Empty responses: {json.dumps(s['empty_responses'])}. "
             f"Call accounting: {json.dumps(s['call_log_account'])}.")
    L.append("")
    L.append("## Verdict taxonomy (EN)")
    L.append("")
    for a in arms:
        L.append(f"- `{a}`: {json.dumps(s['taxonomy_en'][a])}")
    L.append("")
    L.append(f"Refusal-slice (EN): {json.dumps(s['refusal_stats_en'])}")
    L.append("")
    L.append(f"## Pre-registered predictions — {n_met}/4 met "
             f"({'no misses' if n_met == 4 else 'misses published as misses'})")
    L.append("")
    L.append("| id | prediction | observed | adjudication |")
    L.append("|---|---|---|---|")
    for pid in ("S6-P1", "S6-P2", "S6-P3", "S6-P4"):
        p = P[pid]
        obs = p["observed"]
        if isinstance(obs, float):
            obs_s = pct(obs)
        elif isinstance(obs, list):
            obs_s = " vs ".join(pct(x) if isinstance(x, float) else str(x) for x in obs)
        else:
            obs_s = str(obs)
        band = f" (band {p['band']})" if "band" in p else ""
        L.append(f"| {pid} | {p['stated']} | {obs_s}{band} | "
                 f"{'**MET**' if p['met'] else '**MISS**'} |")
    L.append("")
    L.append("## Probe-only refusal questions (S6-P4 substrate)")
    L.append("")
    L.append(f"The 7 probe-only refusal qids and their provenance: {pr['provenance']}.")
    L.append("")
    L.append("| qid | ZH governance verdict (frozen) | EN governance verdict |")
    L.append("|---|---|---|")
    for q in pr["qids"]:
        L.append(f"| {q} | {pr['zh_governance_verdicts'][q]} | {pr['en_governance_verdicts'][q]} |")
    L.append("")
    L.append(f"ZH governance errors on probe7: {pr['zh_governance_errors']}/7; "
             f"EN governance errors on probe7: {pr['en_governance_errors']}/7.")
    L.append("")
    L.append("## EN-vs-ZH flip counts")
    L.append("")
    L.append("| arm | both correct | both error | ZH✓→EN✗ | ZH✗→EN✓ |")
    L.append("|---|---|---|---|---|")
    for a in arms:
        L.append(f"| {a} | {fc[a]['both_correct']} | {fc[a]['both_error']} | "
                 f"{fc[a]['zh_correct_en_error']} | {fc[a]['zh_error_en_correct']} |")
    L.append("")
    L.append("## Per-question EN-vs-ZH flip table")
    L.append("")
    L.append("| qid | cluster | kind | base ZH | base EN | base flip | gov ZH | gov EN | gov flip |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    short = {"both_correct": "=✓", "both_error": "=✗",
             "zh_correct_en_error": "✓→✗", "zh_error_en_correct": "✗→✓"}
    for qid, row in s["per_question_flips"].items():
        b, g = row["baseline_claude"], row["governance_informed"]
        L.append(f"| {qid} | {row['cluster']} | {row['expected_kind']} | "
                 f"{b['zh']} | {b['en']} | {short[b['flip']]} | "
                 f"{g['zh']} | {g['en']} | {short[g['flip']]} |")
    L.append("")
    L.append("---")
    L.append("Rendered by `render_s6_report.py` from `s6_summary.json`; "
             "all numbers flow from the JSON.")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"WROTE {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
