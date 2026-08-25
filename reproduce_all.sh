#!/usr/bin/env bash
# reproduce_all.sh -- rebuild every number, figure and table of the paper from
# the frozen evidence in this repository, and diff the results against the
# committed copies.
#
# Stages (cumulative):
#   gates  (stage 0, always) the paper's own two source gates, run over the
#                     shipped paper/main.tex + paper/sections/*.tex against the
#                     shipped evidence JSONs.  Needs NOTHING -- no warehouses,
#                     no network, no LaTeX -- so it is the cheapest possible
#                     answer to "is every number the PDF prints still backed?".
#                     Added 2026-08-10: before that date the gates lived only
#                     in the authors' paper tree, so a reader of this artifact
#                     could not re-run the checks the paper cites.
#   light  (default)  stage 0 + scoring -> figure data -> figures -> tables,
#                     all diffed.
#                     ZERO LLM calls: the 8 LLM arms are re-scored as a pure
#                     function of the frozen response caches pilot2/runs/.
#                     NEEDS the 9 warehouses in-tree (scoring re-executes every
#                     cached SQL): run ./fetch_and_rebuild.sh once first.
#   verify            light + the independent-verification battery:
#                     compiler gold acceptance (60/60, certificates diffed
#                     byte-for-byte against impl/certs2), verifier replay over
#                     the 60 certificates (both protocols), the forgery battery
#                     (34/34 over 11 bases, families F1-F5, each rejection
#                     pinned on its pre-registered check), import-disjointness
#                     red line, leak/nondegeneracy/witness CI gates, and the
#                     cost stage -- fresh wall-clock medians, printed and
#                     shape-asserted but deliberately NOT diffed, since they
#                     are machine-dependent.
#   full              fetch_and_rebuild.sh + verify.
#
# Re-running the LLM arms from scratch is deliberately NOT wired here: it
# costs money, needs your own model gateway, and the paper's claims are about
# the frozen, pre-registered runs.  See README section "Re-running the arms".
#
# Usage:  ./reproduce_all.sh [gates|light|verify|full]
set -uo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
STAGE="${1:-light}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/asofgov-repro.XXXXXX")"
PASS=0; FAIL=0; NOTES=""

say()  { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
gate() { # gate <name> <cmd...>
  local name="$1"; shift
  if "$@"; then echo "[PASS] $name"; PASS=$((PASS+1));
  else echo "[FAIL] $name"; FAIL=$((FAIL+1)); NOTES="$NOTES  FAIL: $name\n"; fi
}
diffgate() { # diffgate <name> <regenerated> <committed-snapshot>
  gate "$1 (byte-identical)" cmp -s "$2" "$3"
}

need_warehouses() {
  for db in california_schools card_games codebase_community debit_card_specializing \
            european_football_2 financial formula_1 thrombosis_prediction world_1; do
    if [ ! -f "$REPO/pilot2/domains/$db/warehouse.duckdb" ]; then
      echo "Missing $REPO/pilot2/domains/$db/warehouse.duckdb"
      echo "The warehouses are not shipped (see README); run ./fetch_and_rebuild.sh first."
      exit 2
    fi
  done
}

[ "$STAGE" = full ] && { say "fetch_and_rebuild"; "$REPO/fetch_and_rebuild.sh"; }

# --------------------------------------------------------- stage 0: gates
# Deliberately BEFORE need_warehouses: these two need no data substrate at
# all, so a reviewer with nothing but a clone can still audit every printed
# number.  check_numbers.py re-derives each of them from the evidence JSONs
# shipped here and asserts the string the .tex actually prints; the paper's
# body PDF is the typeset image of exactly these sources.  check_redlines.py
# asserts that no compression pass removed a load-bearing disclosure.
# check_bodylength.py is shipped too but is NOT wired here: it measures a
# COMPILED PDF (pdftotext -bbox main.pdf main.bbox) and this repository ships
# no LaTeX build.
say "stage 0: paper source gates (no warehouses, no network, no LaTeX)"
gate "check_numbers.py (every printed number vs the evidence JSONs)" \
  sh -c "cd '$REPO/paper' && python3 tools/check_numbers.py"
gate "check_redlines.py (load-bearing content still present)" \
  sh -c "cd '$REPO/paper' && python3 tools/check_redlines.py"
if [ "$STAGE" = gates ]; then
  say "result"; echo "PASS=$PASS FAIL=$FAIL  (stage=gates)"
  [ -n "$NOTES" ] && printf "$NOTES"
  if [ "$FAIL" = 0 ]; then exit 0; else exit 1; fi
fi

need_warehouses

# ---------------------------------------------------------------- scoring
say "stage 1: re-score the 9 arms from the frozen caches (zero LLM calls)"
cp "$REPO/pilot2/pilot2_summary.json"      "$TMP/committed_summary.json"
cp "$REPO/pilot2/pilot2_arms_summary.json" "$TMP/committed_arms.json"
gate "make_pilot2_summary.py runs" \
  python3 "$REPO/pilot2/make_pilot2_summary.py"
diffgate "pilot2_summary.json"      "$REPO/pilot2/pilot2_summary.json"      "$TMP/committed_summary.json"
diffgate "pilot2_arms_summary.json" "$REPO/pilot2/pilot2_arms_summary.json" "$TMP/committed_arms.json"

# ---------------------------------------------------------------- figure data
say "stage 2: re-derive every figure/table number (extract_p2.py)"
cp "$REPO/paper/figures/fig_data_pilot2.json" "$TMP/committed_figdata.json"
gate "extract_p2.py runs (cross-asserts summaries, warehouses, certs, forgeries)" \
  sh -c "cd '$REPO/paper/figures' && python3 extract_p2.py"
diffgate "fig_data_pilot2.json" "$REPO/paper/figures/fig_data_pilot2.json" "$TMP/committed_figdata.json"

# ---------------------------------------------------------------- figures
say "stage 3: regenerate the paper figures (PDF bytes not asserted)"
for f in fig1_asof_gap figA_partition fig3_failure_taxonomy fig1_combined figB_forgery_matrix figD_cost_ablation; do
  gate "$f.py" sh -c "cd '$REPO/paper/figures' && python3 $f.py >/dev/null"
done

# ---------------------------------------------------------------- tables
say "stage 4: regenerate the tables"
for t in tab_main_results tab_benchmark; do
  cp "$REPO/paper/tables/$t.tex" "$TMP/committed_$t.tex"
  cp "$REPO/paper/tables/$t.audit.json" "$TMP/committed_$t.audit.json"
done
gate "make_tables_p2.py runs" \
  sh -c "cd '$REPO/paper/figures' && python3 make_tables_p2.py >/dev/null"
for t in tab_main_results tab_benchmark; do
  diffgate "$t.tex"        "$REPO/paper/tables/$t.tex"        "$TMP/committed_$t.tex"
  diffgate "$t.audit.json" "$REPO/paper/tables/$t.audit.json" "$TMP/committed_$t.audit.json"
done
cp "$REPO/paper/tables/tab_divergence.tex" "$TMP/committed_tab_divergence.tex"
gate "gen_table_divergence.py runs (re-measures the verifier column, ~40 s)" \
  python3 "$REPO/paper/tools/gen_table_divergence.py"
diffgate "tab_divergence.tex" "$REPO/paper/tables/tab_divergence.tex" "$TMP/committed_tab_divergence.tex"

# ---------------------------------------------------------------- verify
if [ "$STAGE" = verify ] || [ "$STAGE" = full ]; then
  say "stage 5: compiler gold acceptance (60/60) with certificates diffed vs impl/certs2"
  mkdir -p "$TMP/certs_re"
  gate "acceptance_pilot2.py 60/60" \
    python3 "$REPO/impl/asof_compiler/acceptance_pilot2.py" --pilot2 "$REPO/pilot2" --certs "$TMP/certs_re"
  gate "60 certificates byte-identical to impl/certs2" \
    diff -rq "$TMP/certs_re" "$REPO/impl/certs2"

  say "stage 6: independent verifier replay (both protocols) + red lines"
  gate "runall.py p2 (verifier ACCEPT 60/60 + strict track)" \
    python3 "$REPO/impl/asof_verifier/runall.py" p2
  gate "ci_check.py import-disjointness red line" \
    python3 "$REPO/impl/asof_verifier/ci_check.py"

  # The paper's E5 claim ("rejects 34/34, each on the check its construction
  # pre-registered") is the discriminating experiment for the certificate
  # layer, so it must be re-runnable here and not merely asserted.  The runner
  # mutates real compiler-emitted certificates in memory, re-verifies each,
  # and FAILS unless (a) all 11 unmutated bases still ACCEPT, (b) all 34
  # mutants REJECT, and (c) every rejection lands on the check the family
  # registered in advance -- attribution drift is a failure, not a pass.
  # Writes only into the scratch tree; impl/asof_verifier/forge_p2_out/ (the
  # committed run) is left untouched and is diffed for the verdict fields.
  say "stage 6b: forgery battery (34/34 over 11 bases, families F1-F5)"
  gate "forge_p2.py 11 bases ACCEPT + 34/34 REJECT on pre-registered checks" \
    python3 "$REPO/impl/asof_verifier/forge_p2.py" --out "$TMP/forge_re"
  gate "re-run verdicts match the committed forge_p2_out/ run" \
    python3 - "$TMP/forge_re" "$REPO/impl/asof_verifier/forge_p2_out" <<'PYFORGE'
import json, os, sys
fresh, comm = sys.argv[1], sys.argv[2]
def load(d):
    out = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn.startswith("._"):
            continue
        r = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        rep = r.get("report", {})
        # compare only the adjudication, never timings or absolute paths
        out[fn] = (r.get("base_qid"), r.get("expected_reject_by"),
                   rep.get("verdict"), rep.get("rejected_by"))
    return out
a, b = load(fresh), load(comm)
if a == b:
    print("   %d forgery verdicts identical to the committed run" % len(a))
    sys.exit(0)
for k in sorted(set(a) | set(b)):
    if a.get(k) != b.get(k):
        print("   DRIFT %-46s fresh=%s committed=%s" % (k, a.get(k), b.get(k)))
sys.exit(1)
PYFORGE
  for r in leak_report nondegeneracy_report witness_report; do
    cp "$REPO/pilot2/ci/$r.json" "$TMP/committed_$r.json"
  done
  gate "pilot2 CI gates (leak / nondegeneracy / witness)" \
    python3 "$REPO/scripts/run_ci_portable.py"
  for r in leak_report nondegeneracy_report witness_report; do
    diffgate "ci/$r.json" "$REPO/pilot2/ci/$r.json" "$TMP/committed_$r.json"
  done

  # -------------------------------------------------------------- cost
  # Paper section "Cost, and Threats to Validity" was the one subsection an
  # evaluator could not exercise, because its numbers are wall-clock medians:
  # they are machine-dependent and MUST NOT be diffed against the committed
  # copy.  So this stage re-measures into a scratch path and asserts only the
  # shape-invariant facts (which certificates were timed, and that verifying
  # is never cheaper than answering), then PRINTS the fresh medians for the
  # reader to compare by eye against impl/cost_p2.json.
  say "stage 7: re-measure verification cost (fresh medians, NOT diffed)"
  gate "measure_cost.py runs into a scratch path (impl/cost_p2.json untouched)" \
    python3 "$REPO/impl/measure_cost.py" --pilot "$REPO/pilot2" \
            --certs "$REPO/impl/certs2" --out "$TMP/cost_fresh.json"
  gate "cost shape: 60 certificates, 45 with an answering query, ratio_warm.min > 1" \
    python3 - "$TMP/cost_fresh.json" "$REPO/impl/cost_p2.json" <<'PYCOST'
import json, sys
fresh = json.load(open(sys.argv[1], encoding="utf-8"))["aggregate"]
comm  = json.load(open(sys.argv[2], encoding="utf-8"))["aggregate"]
ok = True
def need(name, cond, got):
    global ok
    print("   %-34s %s   (%s)" % (name, "ok" if cond else "MISMATCH", got))
    ok &= bool(cond)
need("n_certificates == 60", fresh["n_certificates"] == 60, fresh["n_certificates"])
need("n_sql == 45",          fresh["n_sql"] == 45,          fresh["n_sql"])
need("n_refusal == 15",      fresh["n_refusal"] == 15,      fresh["n_refusal"])
need("all 60 ACCEPT",        fresh["n_accept"] == 60,       fresh["n_accept"])
need("ratio_warm.min > 1",   fresh["ratio_warm"]["min"] > 1,
     "%.2f" % fresh["ratio_warm"]["min"])
print("   -- fresh medians on THIS machine (committed values in brackets;"
      " wall-clock, so differences are expected):")
for k in ("verify_warm_s", "answer_warm_s", "verify_cold_s", "ratio_warm"):
    print("      %-14s median %.6g   [committed %.6g]"
          % (k, fresh[k]["median"], comm[k]["median"]))
print("      %-14s        %.6g   [committed %.6g]"
      % ("cert_bytes_file", fresh["cert_bytes_file"]["median"],
         comm["cert_bytes_file"]["median"]))
sys.exit(0 if ok else 1)
PYCOST

  # The paper's "no scan-amplification regime" sentence rests on the corpus
  # instantiating no full-scan clause-(iv) audit.  Measure it, do not assume it.
  gate "clause-(iv) audits are window-bounded (no full-scan escape hatch)" \
    sh -c "python3 '$REPO/impl/measure_adm_scan.py' --pilot '$REPO/pilot2' \
             --certs '$REPO/impl/certs2' --out '$TMP/adm_scan_fresh.json' &&
           python3 -c \"
import json,sys
d=json.load(open('$TMP/adm_scan_fresh.json'))
v=d['verdict']; print('   ',v)
sys.exit(0 if v['full_scan_instances']==0 and v['all_window_bounded'] else 1)\""
fi

# ---------------------------------------------------------------- summary
say "result"
echo "PASS=$PASS FAIL=$FAIL  (stage=$STAGE)"
[ -n "$NOTES" ] && printf "$NOTES"
echo "scratch kept at $TMP (committed snapshots for any failing diff)"
[ "$FAIL" = 0 ]
