#!/usr/bin/env python3
"""Adversarial re-check of S5: own timing loop at 2 scale points, full-scan
census over all 48 row-scale certs, and independent re-adjudication of
S5-P1/P2/P3 from the study's own per-certificate records."""
import json, statistics, sys, time, pathlib

S5 = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2/poststudy2_20260823/s5")
OUT = S5.parent / "verification2" / "v2_s5_recheck.json"
IMPL = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/impl")
sys.path.insert(0, str(IMPL)); sys.path.insert(0, str(IMPL/"asof_verifier"))
from asof_compiler import compile_question
import chk as CHK
import duckdb

sweep = json.loads((S5/"s5_cost_sweep.json").read_text())

# ---- (1) own timing loop at scale_100 and scale_400 ----
own = {}
for label in ["scale_100","scale_400"]:
    ddir = S5/"work"/"rowscale"/label/"financial"
    qs = json.loads((ddir/"questions.json").read_text())
    con = duckdb.connect(str(ddir/"warehouse.duckdb"), read_only=True)
    per = {}
    try:
        for q in qs:
            env = compile_question(q, ddir)
            CHK.verify(env, q, con, None)  # warm-up
            ts = []
            for _ in range(11):
                t0 = time.perf_counter(); CHK.verify(env, q, con, None)
                ts.append(time.perf_counter()-t0)
            per[q["qid"]] = statistics.median(ts)
    finally:
        con.close()
    own[label] = {"per_cert_ms": {k: round(v*1000,3) for k,v in per.items()},
                  "median_over_certs_ms": round(statistics.median(per.values())*1000,3)}

claimed = {p["label"]: p for p in sweep["row_scale_axis"]}
own_cmp = {}
for label in own:
    c = claimed[label]["verify_warm_median_over_certs_s"]*1000
    m = own[label]["median_over_certs_ms"]
    own_cmp[label] = {"claimed_ms": round(c,3), "mine_ms": m, "ratio": round(m/c,3)}
growth_mine = own["scale_400"]["median_over_certs_ms"]/own["scale_100"]["median_over_certs_ms"]

# ---- (2) full-scan census over all 48 certs from cert files ----
census = {}
for label in ["scale_0125","scale_025","scale_050","scale_100","scale_200","scale_400"]:
    cd = S5/"work"/"rowscale"/label/"certs"
    n_full = 0; n_wb = 0; n = 0
    for f in sorted(cd.glob("FIN-*.json")):
        blob = f.read_text(); n += 1
        if "symdiff_audit" in blob.replace("window_realization_symdiff",""): n_full += 1
        if "window_realization_symdiff" in blob: n_wb += 1
    census[label] = {"n_certs": n, "full_scan": n_full, "window_bounded": n_wb}

# ---- (3) independent re-adjudication from study's own records ----
meds = {p["label"]: p["verify_warm_median_over_certs_s"] for p in sweep["row_scale_axis"] if p["reachable"]}
order = ["scale_0125","scale_025","scale_050","scale_100","scale_200","scale_400"]
mono = all(meds[a] <= meds[b] for a,b in zip(order,order[1:]))
growth = meds["scale_400"]/meds["scale_100"]
p1_verdict = "MET" if (mono and growth <= 4.0) else "MISS"

ratios = {}
for p in sweep["row_scale_axis"]:
    rs = [r["ratio_warm"] for r in p["per_certificate"] if r["ratio_warm"]]
    ratios[p["label"]] = {"median": statistics.median(rs), "min": min(rs), "max": max(rs)}
p2_median_ok = all(1.0 <= v["median"] <= 60.0 for v in ratios.values())
p2_strict_ok = all(v["min"] >= 1.0 and v["max"] <= 60.0 for v in ratios.values())

fullscan_from_records = {p["label"]: sum(r["n_full_scan_audits"] for r in p["per_certificate"]) for p in sweep["row_scale_axis"]}
p3_ok = all(v == 0 for v in fullscan_from_records.values()) and all(c["full_scan"] == 0 for c in census.values())

# span-axis independent look
span = [(r["span_months"], r["verify_warm_median_s"], r["ratio_warm"], r["verdict"]) for r in sweep["window_span_axis"]["per_span"]]

out = {
 "own_timing": {"points": own, "compare": own_cmp,
                "growth_100_to_400_mine": round(growth_mine,3),
                "growth_100_to_400_claimed": round(growth,3)},
 "fullscan_census_from_cert_files": census,
 "fullscan_from_sweep_records": fullscan_from_records,
 "readjudication": {
   "S5-P1": {"monotone": mono, "growth": growth, "verdict": p1_verdict,
             "claimed": sweep["predictions"]["S5-P1"]["verdict"],
             "dip": {a+"->"+b: (meds[b]-meds[a])*1000 for a,b in zip(order,order[1:])}},
   "S5-P2": {"median_reading": "MET" if p2_median_ok else "MISS",
             "strict_reading": "MET" if p2_strict_ok else "MISS",
             "claimed": sweep["predictions"]["S5-P2"]["verdict"],
             "claimed_strict": sweep["predictions"]["S5-P2"]["strict_all_certificates_verdict"],
             "per_point": {k: {kk: round(vv,3) for kk,vv in v.items()} for k,v in ratios.items()}},
   "S5-P3": {"verdict": "MET" if p3_ok else "MISS", "claimed": sweep["predictions"]["S5-P3"]["verdict"]},
 },
 "span_axis": span,
 "prereg_sha_quoted_in_sweep": sweep["prereg"]["sha256"],
 "prereg_sha_quoted_len": len(sweep["prereg"]["sha256"]),
}
OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
print(json.dumps(out, indent=1, sort_keys=True))
