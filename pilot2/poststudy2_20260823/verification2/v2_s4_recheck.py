#!/usr/bin/env python3
"""Independent adversarial re-derivation of S4 (verification2).

Own bootstrap implementation (written from scratch), same seed 20260823 and
the frozen convention (Random(seed) fresh per arm, 9 cluster choices per
iteration from sorted names, pooled mean, B=2000, CI=[sorted[49],sorted[1949]]).
Compares against s4_summary.json values.
"""
import hashlib, json, random
from pathlib import Path

PILOT2 = Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2")
POST2 = PILOT2 / "poststudy2_20260823"
OUT = POST2 / "verification2" / "v2_s4_recheck.json"

prereg_sha = hashlib.sha256((POST2/"PREREG_poststudy2_20260823.md").read_bytes()).hexdigest()

arms = json.loads((PILOT2/"pilot2_arms_summary.json").read_text())
verd = arms["per_question_verdicts"]

# clusters straight from domains/*/questions.json
clusters = {}
for qf in sorted((PILOT2/"domains").glob("*/questions.json")):
    qs = json.loads(qf.read_text())
    clusters[qf.parent.name] = [q["qid"] for q in qs]

def e(q, a): return 0 if verd[q][a] == "correct" else 1

REF = "baseline_claude"
res = {}
names = sorted(clusters)
for arm in ["governance_informed","trivial_claude","trivial_v2","trivial_v3"]:
    diff = {q: e(q,REF)-e(q,arm) for q in verd}
    mean = sum(diff.values())/60.0
    rng = random.Random(20260823)
    stats = []
    for _ in range(2000):
        picked = [rng.choice(names) for _ in range(9)]
        pool = [q for c in picked for q in clusters[c]]
        stats.append(sum(diff[q] for q in pool)/len(pool))
    stats.sort()
    ci = [stats[49], stats[1949]]
    res[arm] = {"mean": mean, "ci95": ci, "excludes0": bool(ci[0]>0 or ci[1]<0),
                "errors_arm": sum(e(q,arm) for q in verd),
                "errors_ref": sum(e(q,REF) for q in verd)}

# elim restatement from rep caches
ref_err = sorted(q for q in verd if e(q,REF)==1)
per_rep = {}
for rep in [1,2,3,4,5]:
    if rep == 1:
        n = sum(1 for q in ref_err if verd[q]["governance_informed"]=="correct")
    else:
        n = 0
        for q in ref_err:
            f = PILOT2/"poststudy_20260820"/"s3"/"runs_rep"/"governance_informed"/f"rep{rep}"/f"{q}.json"
            if json.loads(f.read_text())["verdict"] == "correct":
                n += 1
    per_rep[rep] = {"n": n, "frac": n/36}

fracs = [per_rep[r]["frac"] for r in [1,2,3,4,5]]

# compare with claimed s4_summary
s4 = json.loads((POST2/"s4"/"s4_summary.json").read_text())
cmp = {}
for arm in res:
    c = s4["paired_differences"][arm]
    cmp[arm] = {
        "mean_match": abs(c["mean_paired_diff"]-res[arm]["mean"]) < 1e-12,
        "ci_match": c["ci95_percentile"] == res[arm]["ci95"],
        "claimed_ci": c["ci95_percentile"], "my_ci": res[arm]["ci95"],
    }
elim_cmp = {str(r): (s4["elimination_restatement"]["per_rep"][str(r)]["eliminated_n"] == per_rep[r]["n"]) for r in per_rep}

# independent prediction adjudication
p1 = res["governance_informed"]["excludes0"]                       # prereg wants True
p2 = all(not res[a]["excludes0"] for a in ["trivial_claude","trivial_v2","trivial_v3"])
p3 = all(0.30 <= f <= 0.45 for f in fracs) and (min(fracs) < 0.40 < max(fracs))
out = {
 "prereg_sha256": prereg_sha,
 "my_bootstrap": res,
 "my_elim": {str(r): per_rep[r] for r in per_rep},
 "compare_to_s4_summary": cmp,
 "elim_match": elim_cmp,
 "independent_verdicts": {"S4-P1": "MISS" if not p1 else "MET",
                          "S4-P2": "MISS" if not p2 else "MET",
                          "S4-P3": "MET" if p3 else "MISS"},
 "claimed_verdicts": {k: v["verdict"] for k,v in s4["predictions"].items()},
}
OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
print(json.dumps(out["compare_to_s4_summary"], indent=1))
print("elim_match", elim_cmp)
print("independent", out["independent_verdicts"], "claimed", out["claimed_verdicts"])
