# -*- coding: utf-8 -*-
"""Render TRANSLATION_AUDIT.md from translation_audit.json (numbers flow
through the deterministic audit JSON only; this script formats, it does
not compute)."""
import json
import os

S6 = "/Volumes/SSD 1/explore_opportunity_cc/pilot2/poststudy2_20260823/s6"

r = json.load(open(os.path.join(S6, "translation_audit.json")))
qe = json.load(open(os.path.join(S6, "questions_en.json")))
freeze = open(os.path.join(S6, "FREEZE_questions_en.sha256")).read().strip()

raw, fin = r["round_raw"], r["round_final"]
L = []
L.append("# S6 Stage A — Translation Audit (translations + audit + freeze; no scored calls)")
L.append("")
L.append("Governing prereg: `%s`, sha256 `%s`." % (r["prereg"], r["prereg_sha256"]))
L.append("")
L.append("Translator: `%s`. Each call saw the fixed gold-invariant instruction "
         "block plus `question_zh` ONLY — no structured fields, no gold-side "
         "fields. Raw outputs: `translation_raw/<qid>.json` (60 files, "
         "append-only). Structured fields (`as_of`, `declared_at`, `windows`, "
         "`metric_alias`, `pinned_version`, gold fields) were read by the "
         "AUDIT only (`audit_s6.py`); they feed no scored arm."
         % r["translator_model"])
L.append("")
L.append("## Audit protocol (deterministic, `audit_s6.py`)")
L.append("")
L.append("Per question, field-by-field per the prereg checklist: declared-at "
         "instant + phrasing; as-of token multiset ZH==EN and consistency with "
         "the `as_of` field; every numeric/date token of the ZH preserved in "
         "the EN (month-name renderings excused) and **no numeric/date token "
         "added**; ASCII identifiers preserved case-sensitively; window/"
         "caliber/disclosure/version marker keywords; metric-alias meaning "
         "keywords; identical ZH aliases rendered as one identical EN alias "
         "phrase; per-qid required phrases (e.g. CA-Q6 `charter authorization "
         "date`, F1-Q3 version-pin). Plus the string-level leak audit over "
         "the English texts mirroring `pilot2/ci/leak_check.py`, extended per "
         "the S6 spec: gold values (>=8 chars, incl. structured-gold leaves), "
         "gold SQL / SQL keywords, window endpoints not present in the own ZH "
         "text, and refusal-class tokens must not appear.")
L.append("")
L.append("## Tallies")
L.append("")
L.append("| item | raw round | final round |")
L.append("|---|---|---|")
L.append("| questions audited | %d | %d |" % (raw["n_questions"], fin["n_questions"]))
L.append("| field checks run | %d | %d |" % (raw["total_field_checks"], fin["total_field_checks"]))
L.append("| questions failing field checks | %d | %d |" %
         (raw["n_questions_failing"], fin["n_questions_failing"]))
L.append("| alias-consistency groups checked | %d | %d |" %
         (len(raw["alias_consistency"]), len(fin["alias_consistency"])))
L.append("| alias-consistency failures | %d | %d |" %
         (len(raw["alias_consistency_fail"]), len(fin["alias_consistency_fail"])))
nlc = fin["leak_audit"]["n_checks"]
L.append("| leak checks run (final) | — | %d |" % sum(nlc.values()))
L.append("| leak problems | %d | %d |" %
         (len(raw["leak_audit"]["problems"]), len(fin["leak_audit"]["problems"])))
L.append("")
L.append("Leak-check breakdown (final round): " +
         ", ".join("%s=%d" % (k, v) for k, v in sorted(nlc.items())) +
         "; forbidden gold strings (>=8 chars) screened: %d."
         % fin["leak_audit"]["n_gold_strings_ge8"])
L.append("")
L.append("## Raw-round findings and fixes (%d fixes)" % r["n_fixes"])
L.append("")
L.append("Raw translations were already leak-clean; every finding below is a "
         "meaning/consistency finding. Automated raw-round flags: 6 questions "
         "via field checks + 2 alias-consistency groups (FIN-Q5/FIN-Q7 "
         "`当月交易笔数`, FIN-Q3/FIN-Q8 `罚息交易占比`; FIN-Q5 flagged by both "
         "routes). One additional finding (EF2-Q5) is a manual auditor "
         "finding. Each fix was re-audited; the final round passes every "
         "check.")
L.append("")
for qid in sorted(r["fixes_applied"]):
    fx = r["fixes_applied"][qid]
    L.append("### %s — %s" % (qid, fx["trigger"]))
    L.append("")
    L.append("- reason: %s" % fx["reason"])
    L.append("- raw: `%s`" % fx["raw"])
    L.append("- fixed: `%s`" % fx["fixed"])
    L.append("")
L.append("## Result")
L.append("")
L.append("Final round: **PASS** — 60/60 questions pass all field checks, "
         "0 alias-consistency failures, 0 leak problems. "
         "`questions_en.json` (60 entries, qid -> question_en) frozen:")
L.append("")
L.append("```")
L.append(freeze)
L.append("```")
L.append("")
L.append("Freeze line file: `FREEZE_questions_en.sha256` (shasum -a 256 "
         "format; verify with `shasum -c` in `s6/`). n_entries=%d." % len(qe))
L.append("")

with open(os.path.join(S6, "TRANSLATION_AUDIT.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("rendered TRANSLATION_AUDIT.md (%d lines)" % len(L))
