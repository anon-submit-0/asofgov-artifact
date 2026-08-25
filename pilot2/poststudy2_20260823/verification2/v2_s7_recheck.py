#!/usr/bin/env python3
"""Adversarial re-check of S7: full independent re-bridge + re-score of all 60
cached extractions through the frozen compiler and frozen gate-1 scorer, own
field-accuracy comparison, and independent P1-P4 adjudication. Compares against
s7_nl2sigma_full.json / s7_summary.json."""
import importlib.util, json, pathlib, sys

P2 = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2")
S7 = P2/"poststudy2_20260823"/"s7"
IMPL = P2.parent/"impl"
OUT = P2/"poststudy2_20260823"/"verification2"/"v2_s7_recheck.json"
sys.path.insert(0, str(IMPL))
from asof_compiler import compile_question
spec = importlib.util.spec_from_file_location("ap2", IMPL/"asof_compiler"/"acceptance_pilot2.py")
AP2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(AP2)

SIGMA_FIELDS = ["as_of","declared_at","metric_alias","scope","pinned_version",
 "cross_window","anchor_override","window_request","requested_granularity",
 "requested_time_gran","presentation","ctx_role","periods"]

full = {}
for d in sorted(p for p in (P2/"domains").iterdir() if p.is_dir() and not p.name.startswith("._") and (p/"questions.json").is_file()):
    for q in json.loads((d/"questions.json").read_text()):
        full[q["qid"]] = (q, d)

def canon(v, f=None):
    if f == "scope" and (v is None or v == {}): return {}
    if f == "periods" and isinstance(v, list): v = [str(x) for x in v]
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, dict): return {k: canon(x) for k, x in sorted(v.items())}
    if isinstance(v, list): return [canon(x) for x in v]
    return v

claim = json.loads((S7/"s7_nl2sigma_full.json").read_text())
claim_rows = {r["qid"]: r for r in claim["ledger"]}

rows = {}
for qid, (qf, d) in full.items():
    rec = json.loads((S7/"runs_sigma"/f"{qid}.json").read_text())
    sigma = rec.get("sigma")
    if sigma is None:
        env = None; outk = "compile_error"; verdict = "error"; why = "extraction_error"
    else:
        qs = {"qid": qid, "domain": rec["domain"]}
        for f in SIGMA_FIELDS:
            v = sigma.get(f)
            if f == "scope": v = v if isinstance(v, dict) else {}
            if f == "periods" and isinstance(v, list): v = [str(x) for x in v]
            qs[f] = v
        try:
            env = compile_question(qs, d)
        except Exception as e:
            env = None; why = f"{type(e).__name__}"
        if env is None:
            outk = "compile_error"; verdict = "error"; why = "compile_error"
        else:
            cert = env["certificate"]
            outk = "refusal" if "refusal" in env else ("rewrite" if cert["disclosure"]["decision"]=="REWRITE" else "answer")
            ok, why = AP2._gold_match(qf, env, cert, str(d/"warehouse.duckdb"))
            verdict = "correct" if ok else "error"
    fm = {f: canon((sigma or {}).get(f), f) == canon(qf.get(f), f) for f in SIGMA_FIELDS}
    rows[qid] = {"outcome": outk, "verdict": verdict, "why": why,
                 "exact": all(fm.values()), "field_match": fm}

# compare with claimed ledger
mismatch = []
for qid, r in rows.items():
    c = claim_rows[qid]
    if r["verdict"] != c["score"]["verdict"] or r["exact"] != c["sigma_accuracy"]["exact_full_sigma"] \
       or r["outcome"] != c["outcome"]["kind"] or r["field_match"] != c["sigma_accuracy"]["field_match"]:
        mismatch.append({"qid": qid, "mine": {k: r[k] for k in ("outcome","verdict","exact")},
                         "claimed": {"outcome": c["outcome"]["kind"], "verdict": c["score"]["verdict"],
                                     "exact": c["sigma_accuracy"]["exact_full_sigma"]}})

n_exact = sum(r["exact"] for r in rows.values())
n_err = sum(r["verdict"] != "correct" for r in rows.values())
n_metric = sum(r["field_match"]["metric_alias"] for r in rows.values())
exact_and_wrong = [q for q, r in rows.items() if r["exact"] and r["verdict"] != "correct"]
per_field = {f: sum(r["field_match"][f] for r in rows.values()) for f in SIGMA_FIELDS}

# P4 concentration clause: metric mismatches vs window/scope/version mismatches
n_wsv = sum(1 for r in rows.values() if not all(r["field_match"][f] for f in ("window_request","scope","pinned_version","cross_window")))
preds = {
 "S7-P1": "MET" if n_exact >= 36 else "MISS",
 "S7-P2": "MET" if n_err <= 28 else "MISS",
 "S7-P3": "MET" if not exact_and_wrong else "MISS",
 "S7-P4": "MET" if (n_metric >= 54 and (60-n_metric) <= n_wsv) else "MISS",
}
out = {
 "mine": {"exact_full_sigma": n_exact, "e2e_error": n_err, "metric_alias_match": n_metric,
          "exact_and_wrong": exact_and_wrong, "per_field_match": per_field,
          "wsv_mismatch_questions": n_wsv},
 "claimed": {"exact_full_sigma": claim["exact_full_sigma"], "e2e_error": claim["end_to_end_error"],
             "metric_alias_match": claim["metric_alias_match"]},
 "ledger_mismatches": mismatch,
 "independent_predictions": preds,
 "error_rows_mine": {q: rows[q] for q in sorted(rows) if rows[q]["verdict"] != "correct"},
}
def default(o): return str(o)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=default))
print(json.dumps({k: out[k] for k in ("mine","claimed","independent_predictions")}, ensure_ascii=False, indent=1, default=default))
print("ledger mismatches:", len(mismatch))
for m in mismatch: print(m)
print("my error rows:", {q: (rows[q]['outcome'], rows[q]['why']) for q in sorted(rows) if rows[q]['verdict']!='correct'})
