#!/usr/bin/env python3
"""Adversarial re-check of S6: (1) field-by-field re-audit of 8 seeded-random
translations vs frozen ZH structured fields; (2) independent re-score of 6
cached EN responses via the frozen scorer applied to cached raw/sql;
(3) full independent recount of both arms + independent P1-P4 adjudication."""
import hashlib, importlib.util, json, pathlib, random, re, sys

P2 = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2")
S6 = P2/"poststudy2_20260823"/"s6"
OUT = P2/"poststudy2_20260823"/"verification2"/"v2_s6_recheck.json"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
R2 = load("run_pilot2_arms", P2/"run_pilot2_arms.py")

qen = json.loads((S6/"questions_en.json").read_text())
zh = {q["qid"]: (q, d) for q, d in R2.questions()}

# ---- (1) translation re-audit, 8 seeded-random qids ----
rng = random.Random(20260823)
sample8 = sorted(rng.sample(sorted(qen), 8))
audit = {}
for qid in sample8:
    q, _ = zh[qid]
    en = qen[qid]
    checks = {}
    if q.get("as_of"): checks["as_of_present"] = q["as_of"] in en
    if q.get("declared_at"): checks["declared_at_present"] = q["declared_at"] in en
    pv = q.get("pinned_version")
    if pv: checks["version_pin_present"] = str(pv) in en
    wr = q.get("window_request")
    if wr:
        toks = [str(v) for v in (wr.values() if isinstance(wr, dict) else [wr])
                if isinstance(v, str) and re.match(r"\d{4}", str(v))]
        if toks: checks["window_tokens_present"] = all(t in en for t in toks)
    # scope string values
    for k, v in (q.get("scope") or {}).items():
        if isinstance(v, str) and len(v) > 2 and not re.search(r"[一-鿿]", v):
            checks[f"scope_{k}_present"] = v in en
    # no gold-side leak into EN text
    leak = False
    for f in ("gold_sql","refusal_reason","windows_note","notes"):
        v = q.get(f)
        if isinstance(v, str) and len(v.strip()) >= 8 and v.strip() in en: leak = True
    if q.get("gold_value") is not None and len(str(q["gold_value"])) >= 8:
        if str(q["gold_value"]) in en: leak = True
    checks["no_gold_leak"] = not leak
    audit[qid] = {"zh": q["question_zh"], "en": en, "checks": checks,
                  "all_pass": all(checks.values())}

# ---- (2) re-score 6 cached EN responses via frozen scorer on cached sql ----
rng2 = random.Random(20260824)
picks = [("baseline_claude", x) for x in rng2.sample(sorted(qen), 3)] + \
        [("governance_informed", x) for x in rng2.sample(sorted(qen), 3)]
rescore = {}
for arm, qid in picks:
    rec = json.loads((S6/"runs_en"/arm/f"{qid}.json").read_text())
    q, d = zh[qid]
    # independent path: re-extract sql from cached raw, re-run frozen scorer
    sql2 = R2.RP.extract_sql(rec["raw"])
    db = str(d/"warehouse.duckdb")
    kind, value, verdict = R2.fetch_and_score(q, sql2, db)
    rescore[f"{arm}/{qid}"] = {
        "cached_verdict": rec["verdict"], "rescored_verdict": verdict,
        "sql_reextract_matches": sql2 == rec["sql"],
        "value_matches": value == rec["value"],
        "match": verdict == rec["verdict"],
        "expected_kind": q["expected_kind"],
        "raw_head": rec["raw"][:200],
    }

# ---- (3) full recount + independent P1-P4 ----
counts, tax, verd_en = {}, {}, {}
for arm in ("baseline_claude","governance_informed"):
    errs = 0; t = {}
    for qid in qen:
        rec = json.loads((S6/"runs_en"/arm/f"{qid}.json").read_text())
        v = rec["verdict"]; t[v] = t.get(v,0)+1
        verd_en.setdefault(qid, {})[arm] = v
        if v != "correct": errs += 1
    counts[arm] = errs; tax[arm] = t

# probe7 from frozen make_pilot2_summary.py
src = (P2/"make_pilot2_summary.py").read_text()
m = re.search(r"PROBE7\s*=\s*[\[\(]([^\]\)]*)[\]\)]", src)
probe7 = re.findall(r"[\"']([A-Z0-9]+-Q\d+)[\"']", m.group(1)) if m else None
probe7_errs = sum(1 for qid in (probe7 or []) if verd_en[qid]["governance_informed"] != "correct")

p1 = abs(counts["baseline_claude"]/60 - 0.600) <= 0.10
p2 = abs(counts["governance_informed"]/60 - 0.467) <= 0.10
p3 = counts["baseline_claude"]/60 > counts["governance_informed"]/60
p4 = probe7_errs >= 4

s6sum = json.loads((S6/"s6_summary.json").read_text())
claimed = {k: v.get("adjudication", v.get("verdict")) for k, v in s6sum.get("predictions", {}).items()}

out = {
 "translation_reaudit": {"sample": sample8, "detail": audit,
                         "all_pass": all(a["all_pass"] for a in audit.values())},
 "rescore6": rescore,
 "rescore_all_match": all(r["match"] for r in rescore.values()),
 "recount": {"errors": counts, "taxonomy": tax},
 "probe7": {"qids": probe7, "gov_en_errors": probe7_errs},
 "independent_predictions": {"S6-P1": "MET" if p1 else "MISS",
   "S6-P2": "MET" if p2 else "MISS", "S6-P3": "MET" if p3 else "MISS",
   "S6-P4": "MET" if p4 else "MISS"},
 "claimed_predictions": claimed,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
print(json.dumps({k: out[k] for k in ("rescore_all_match","recount","probe7","independent_predictions","claimed_predictions")}, ensure_ascii=False, indent=1))
print("translation sample:", sample8, "all_pass:", out["translation_reaudit"]["all_pass"])
for qid, a in audit.items():
    print(qid, a["checks"])
for k, r in rescore.items():
    print(k, "cached:", r["cached_verdict"], "rescored:", r["rescored_verdict"], "match:", r["match"])
