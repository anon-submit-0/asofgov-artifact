#!/bin/bash
# S3 full-run driver (PREREG §S3). Staged: baseline reps 2-5, then governance
# reps 2-5 with an empty-completion circuit breaker between reps: if a finished
# governance rep has >9/60 cached records with empty_response=true (>15%), the
# driver STOPS so the infra issue can be dealt with instead of contaminating
# the study. Existing cache files are skipped by the harness (no re-calls).
set -u
POST="/Volumes/SSD 1/explore_opportunity_cc/pilot2/poststudy_20260820"
cd "$POST/s3"
for rep in 2 3 4 5; do
  echo "=== baseline_claude rep$rep start $(date '+%H:%M:%S') ==="
  python3 rep_harness.py run baseline_claude "$rep" --all
done
for rep in 2 3 4 5; do
  echo "=== governance_informed rep$rep start $(date '+%H:%M:%S') ==="
  python3 rep_harness.py run governance_informed "$rep" --all
  n_empty=$(python3 - "$rep" <<'PY'
import json,glob,sys
rep=sys.argv[1]
files=[f for f in glob.glob(f"runs_rep/governance_informed/rep{rep}/*.json") if "/._" not in f]
print(sum(1 for f in files if json.load(open(f)).get("empty_response")))
PY
)
  echo "=== governance rep$rep empty_response count: $n_empty ==="
  if [ "$n_empty" -gt 9 ]; then echo "CIRCUIT BREAKER: >9 empties in rep$rep — stopping driver"; exit 3; fi
done
echo "=== S3 DRIVER COMPLETE $(date '+%H:%M:%S') ==="
