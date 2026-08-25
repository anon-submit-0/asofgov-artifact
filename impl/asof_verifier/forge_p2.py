#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forge_p2.py — forgery-family generator + acceptance runner on the pilot2
base (C5 Theorem 5.10 obligations / Prop 5.12 deletion attacks, instantiated
on the nine public-domain warehouses and the real compiler-emitted
certificates in impl/certs2/).

Unlike the rma-era forge.py (whose bases were hand-built envelopes), the p2
bases are REAL certificates: every mutation starts from an envelope the
independent verifier ACCEPTs, so each REJECT is pinned on the mutation.

Families:
  F1  semantic swaps (coherent wrong-coordinate carriage)
      F1a  wrong-year ANSWER            FIN-Q1  windows+SQL+probe → 1995   -> V0
      F1b  empty-denominator ANSWER     CARD-Q7 refusal flipped to ANSWER  -> V6c
      F1c  window-shift MC refusal      CARD-Q7 α+probe → 2016-12 (empty)  -> V0
      F1d  fake window-pair AM          FIN-Q1  forged AM(ii) refusal      -> V0
      F1e  off-diagonal marker deleted  F1-Q3   off_diagonal → None        -> V1
      F1f  version swap                 FIN-Q1  ν → v2 (ver(T)=v1)         -> V1
  F2  field deletions (Prop 5.12)
      F2a  delete ν                     FIN-Q1                              -> V0 (+V1)
      F2b  delete α                     FIN-Q1                              -> V0
      F2c  delete ρ                     FIN-Q1                              -> V4
      F2d  delete δ                     FIN-Q1                              -> V5
      F2e  delete witness               CARD-Q7                             -> V6b
  F3  supplementary attack shapes
      F3a  dangling version pin         FIN-Q1  ν → v9                      -> V0 (+V1)

  (F2a/F3a note: on the p2 base the alias→metric map is version-scoped, so a
  missing/dangling ν already fails V0's alias re-resolution — the first FAIL
  in canonical order — while V1 fails too with the classic 'graph_pin missing'
  / '0 rows' detail. The harness asserts BOTH: rejected_by=V0 and V1 ∈ failed
  checks. On the rma base (forge.py) the same attacks attribute to V1 because
  the legacy schema has no version-scoped alias layer in V0.)
      F3b  ungoverned unmarked          FIN-Q1  D5 annotation dropped       -> V5
      F3c  sum(rate) form               FIN-Q1  AVG(daily_rate)             -> V6a
      F3d  fake-pair AM(iv) payload     EF2-Q6  num_window → 2013-11-30     -> V6b
      F3d2 symdiff_count tamper         EF2-Q6  1 → 3                       -> V6b
      F3e  alien table                  FIN-Q1  joins "card" (∉ closure)    -> V6a
      F3f  self-declared override       FIN-Q1  α[0] → A-FIN-TRANS          -> V0
      F3g  routing hop tamper           FIN-Q1  via_table → trans           -> V4
      F3h  metric swap under alias      FIN-Q1  metric → penalty_trans_rate -> V0
  F4  disclosure-gate forgeries (NEW: rollup traces / policy sets / masks)
      F4a  fine-grain ANSWER despite k  CA-Q5   school-grain, no rollup     -> V5
      F4b  over-coarsened rollup        CODE-Q4 band→all (band already ok)  -> V5
      F4c  forged SUPPMIN transcript    CODE-Q7 probe SQL → SELECT 999      -> V6b
      F4d  policy set Π cleared         CA-Q5   policy_ids=[]               -> V5
      F4e  governed claimed ungoverned  CODE-Q6 full launder, raw column    -> V5
      F4f  DB blocking set emptied      CODE-Q7 blocking_policy_ids=[]      -> V6b
      F4g  DB alien policy cited        TH-Q5   + th.pi99 (unregistered)    -> V6b
      F4h  mask closure omitted         CODE-Q6 μ*=[] under dec=REWRITE     -> V0
      F4i  mask transform stripped      CODE-Q6 μ* intact, SQL raw          -> V5
      F4j  mask strength downgraded     TH-Q4   year_only → year_month@v2   -> V5
  F5  refusal-class substitution across the OOV/AM(iv) boundary, and the
      clause-(iv) replay variant a certificate declares for itself (added
      2026-08-10 with the R5-M1/R5-M2 verifier fixes: the battery had no
      landing on this face, and each hole it left open accepted a forgery)
      F5a  OOV substitution, honest leg  EF2-Q6  AM(iv)→OOV, witness on the
                                                 truly vacuous leg A-EF2-PA -> V6b
      F5b  OOV substitution, covered leg EF2-Q6  same, witness on A-EF2-MATCH -> V6b
      F5c  fabricated AM(iv) refusal     CARD-Q2 an ANSWER refused by self-
                                                 declaring symdiff_audit     -> V3
      F5d  variant swap, genuine refusal EF2-Q6  right class, self-chosen
                                                 variant + honest payload    -> V3

  (F5a and F5c are the two the pre-fix verifier ACCEPTED. F5a: V6b(0) ran only
  for r ∈ {AM,MC,DB}, so nothing replayed the guard an OOV certificate claims,
  and a single-anchor witness carried a verdict the semantics adjudicates
  pair-wise. F5c: no seed spells an `adm_check_mode` column, so the clause-(iv)
  variant was read off the certificate — a coordinate §6.2 forbids inheriting.
  F5b was already rejected; F5d was rejected only incidentally, on a payload
  type mismatch inside a replay variant it should never have been granted.)

Verifier-side file: imports chk only (stdlib + duckdb underneath); certificates
and questions are consumed as DATA. Nothing is imported from any compiler.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chk  # the verifier under test (same side of the red line)

HERE = os.path.dirname(os.path.abspath(__file__))
IMPL = os.path.dirname(HERE)
ROOT = os.path.dirname(IMPL)
P2 = os.path.join(ROOT, "pilot2", "domains")
CERTS2 = os.path.join(IMPL, "certs2")

BASE_QIDS = {
    "FIN-Q1": "financial",
    "F1-Q3": "formula_1",
    "CARD-Q2": "card_games",
    "CARD-Q7": "card_games",
    "EF2-Q6": "european_football_2",
    "CA-Q5": "california_schools",
    "CODE-Q4": "codebase_community",
    "CODE-Q6": "codebase_community",
    "CODE-Q7": "codebase_community",
    "TH-Q4": "thrombosis_prediction",
    "TH-Q5": "thrombosis_prediction",
}


def load_base(qid):
    dom = BASE_QIDS[qid]
    with open(os.path.join(P2, dom, "questions.json"), encoding="utf-8") as fh:
        q = next(x for x in json.load(fh) if x["qid"] == qid)
    with open(os.path.join(CERTS2, qid + ".json"), encoding="utf-8") as fh:
        env = json.load(fh)
    return q, env, os.path.join(P2, dom, "warehouse.duckdb")


def _shift(text, pairs):
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def _win_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    nxt = "%04d-01-01" % (y + 1) if m == 12 else "%04d-%02d-01" % (y, m + 1)
    return {"kind": "month", "lo": "%s-01" % ym, "hi_excl": nxt}


def forgeries():
    """Yields (name, base_qid, mutate(env, con) -> env, expected_check, note)
    or with a 6th element: a list of checks that must ALSO be among the FAILs."""
    out = []
    Y = [("1996-01-01", "1995-01-01"), ("1997-01-01", "1996-01-01")]

    # ---------------- F1: semantic swaps ----------------
    def f1a(env, con):
        f = copy.deepcopy(env)
        f["sql"] = _shift(f["sql"], Y)
        c = f["certificate"]
        for a in c["anchors"]:
            a["window"] = {"kind": "year", "lo": "1995-01-01", "hi_excl": "1996-01-01"}
        for p in c.get("probes") or []:
            if p.get("sql"):
                p["sql"] = _shift(p["sql"], Y)
                if p.get("kind") == "DEN_POP":
                    v = con.execute(p["sql"]).fetchone()[0]
                    p["observed"] = None if v is None else float(v)
        return f
    out.append(("F1a_wrong_year_answer", "FIN-Q1", f1a, "V0",
                "1996 problem-loan-rate answered on coherently shifted 1995 windows; "
                "only V0's independent α re-derivation pins it"))

    def f1b(env, con):
        f = copy.deepcopy(env)
        c = f["certificate"]
        w = c["refusal"]["witness"]
        den_sql = w["probe_sql"]
        num_sql = ("SELECT COUNT(*) FROM \"rulings\" t0 WHERE "
                   "substr(CAST(t0.\"date\" AS VARCHAR),1,10) >= '2017-02-01' AND "
                   "substr(CAST(t0.\"date\" AS VARCHAR),1,10) < '2017-03-01'")
        f.pop("refusal", None)
        c.pop("refusal", None)
        c["disclosure"]["decision"] = "ANSWER"
        c.setdefault("probes", []).append(
            {"kind": "DEN_POP", "role": "denominator", "sql": den_sql,
             "observed": 490.0})  # the naive full-period lie
        f["sql"] = ("SELECT (%s) * 1.0 / NULLIF((%s), 0)"
                    % (num_sql, den_sql.replace("SELECT (", "SELECT (", 1)))
        return f
    out.append(("F1b_empty_denominator_answer", "CARD-Q7", f1b, "V6c",
                "mc_ii refusal flipped to ANSWER: re-executed μ_den=0 ∈ 𝒵 while the "
                "DEN_POP transcript records the 490 lie"))

    def f1c(env, con):
        f = copy.deepcopy(env)
        c = f["certificate"]
        S = [("2017-02-01", "2016-12-01"), ("2017-03-01", "2017-01-01")]
        for a in c["anchors"]:
            a["window"] = _win_month("2016-12")
        w = c["refusal"]["witness"]
        w["probe_sql"] = _shift(w["probe_sql"], S)
        v = con.execute(w["probe_sql"]).fetchone()[0]
        w["observed"] = None if v is None else float(v)
        return f
    out.append(("F1c_window_shift_mc", "CARD-Q7", f1c, "V0",
                "MC(ii) refusal replays fine on the shifted (also-empty) 2016-12 "
                "window; V0 rejects the α that is not q's α_{q,v}"))

    def f1d(env, con):
        f = copy.deepcopy(env)
        f.pop("sql", None)
        f["refusal"] = "anchor-mismatch"
        c = f["certificate"]
        c["anchors"][0]["window"] = {"kind": "year", "lo": "1996-01-01",
                                     "hi_excl": "1997-01-01"}
        c["anchors"][1]["window"] = {"kind": "year", "lo": "1995-01-01",
                                     "hi_excl": "1996-01-01"}
        c["disclosure"]["decision"] = "REFUSE"
        c["probes"] = [p for p in c.get("probes") or [] if p.get("kind") != "DEN_POP"]
        c["refusal"] = {
            "reason": "anchor-mismatch",
            "witness": {"type": "window-pair", "clause": "(ii)",
                        "num_window": {"kind": "year", "lo": "1996-01-01",
                                       "hi_excl": "1997-01-01"},
                        "den_window": {"kind": "year", "lo": "1995-01-01",
                                       "hi_excl": "1996-01-01"}},
            "ct": [{"slice": "(v1,B-FIN-LOAN)", "reason": "AM"}],
        }
        return f
    out.append(("F1d_fake_window_pair_am", "FIN-Q1", f1d, "V0",
                "same-window ratio refused AM(ii) on a fabricated (1996,1995) pair; "
                "the α carrying it fails the re-derivation"))

    def f1e(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["graph_pin"]["off_diagonal"] = None
        return f
    out.append(("F1e_offdiag_marker_deleted", "F1-Q3", f1e, "V1",
                "pinned v1 read at declared_at where ver(T)=v2: deleting the "
                "off_diagonal commitment is the GOLD-1 zero-trace surface"))

    def f1f(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["graph_pin"]["graph_version"] = "v2"
        f["certificate"]["graph_pin"]["commit_id"] = "1998-03-01"
        return f
    out.append(("F1f_version_swap", "FIN-Q1", f1f, "V1",
                "ν repinned to v2 while ver(declared_at)=v1 and no off-diagonal "
                "commitment marker exists"))

    # ---------------- F2: deletions ----------------
    def _del(key):
        def g(env, con):
            f = copy.deepcopy(env)
            f["certificate"].pop(key, None)
            return f
        return g
    out.append(("F2a_delete_nu", "FIN-Q1", _del("graph_pin"), "V0",
                "no version coordinate: version-swap surface (p2 alias layer is "
                "version-scoped, so V0's alias re-resolution fails first; V1 must "
                "also fail with the 'graph_pin missing' detail)", ["V1"]))
    out.append(("F2b_delete_alpha", "FIN-Q1", _del("anchors"), "V0",
                "no anchor assignment: window-swap surface"))
    out.append(("F2c_delete_rho", "FIN-Q1", _del("routing"), "V4",
                "ratio answered without ρ: caliber-blind substitution surface"))
    out.append(("F2d_delete_delta", "FIN-Q1", _del("disclosure"), "V5",
                "no disclosure decision: disclosure-laundering surface"))

    def f2e(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["refusal"].pop("witness", None)
        return f
    out.append(("F2e_delete_witness", "CARD-Q7", f2e, "V6b",
                "refusal without witness: unfalsifiable refusal"))

    # ---------------- F3: supplementary ----------------
    def f3a(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["graph_pin"]["graph_version"] = "v9"
        f["certificate"]["graph_pin"]["commit_id"] = "2099-12-31"
        return f
    out.append(("F3a_dangling_version_pin", "FIN-Q1", f3a, "V0",
                "ν pinned to a version absent from gov_semantic_graph_version "
                "(alias@v9 resolves nothing → V0 first; V1 must also fail with "
                "the 0-row pin-resolution detail)", ["V1"]))

    def f3b(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["disclosure"]["ungoverned_disclosure"] = False
        return f
    out.append(("F3b_ungoverned_unmarked", "FIN-Q1", f3b, "V5",
                "D5: zero-policy domain without the ungoverned-disclosure annotation"))

    def f3c(env, con):
        f = copy.deepcopy(env)
        f["sql"] = (
            "SELECT AVG(daily_rate) FROM (SELECT substr(CAST(t0.\"date\" AS VARCHAR),1,10) AS d, "
            "SUM(CASE WHEN t0.\"status\" IN ('B','D') THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS daily_rate "
            "FROM \"loan\" t0 WHERE substr(CAST(t0.\"date\" AS VARCHAR),1,10) >= '1996-01-01' "
            "AND substr(CAST(t0.\"date\" AS VARCHAR),1,10) < '1997-01-01' GROUP BY 1)")
        return f
    out.append(("F3c_sum_rate_form", "FIN-Q1", f3c, "V6a",
                "average-of-daily-rates violates the ratio-of-sums invariant "
                "(C3 note 3.13)"))

    def f3d(env, con):
        f = copy.deepcopy(env)
        w = f["certificate"]["refusal"]["witness"]
        w["num_window"] = {"kind": "point", "lo": "2013-11-30", "hi_excl": "2013-12-01"}
        return f
    out.append(("F3d_fake_pair_witness_am4", "EF2-Q6", f3d, "V6b",
                "AM(iv) payload cites a window that is not q's request pair "
                "(fake-pair replay rejected)"))

    def f3d2(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["refusal"]["witness"]["symdiff_count"] = 3
        return f
    out.append(("F3d2_symdiff_count_tamper", "EF2-Q6", f3d2, "V6b",
                "AM(iv) symdiff_count 3 ≠ replayed |Δ| = 1 on the request window pair"))

    def f3e(env, con):
        f = copy.deepcopy(env)
        f["sql"] = f["sql"] + " * (SELECT CASE WHEN COUNT(*) >= 0 THEN 1 END FROM \"card\")"
        return f
    out.append(("F3e_alien_table", "FIN-Q1", f3e, "V6a",
                "reads \"card\" outside the certified closure "
                "(α objects ∪ inheritance ∪ dims ∪ ρ via ∪ registered metric tables)"))

    def f3f(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["anchors"][0]["anchor_id"] = "A-FIN-TRANS"
        f["certificate"]["anchors"][0]["declared_override"] = True
        return f
    out.append(("F3f_self_declared_override", "FIN-Q1", f3f, "V0",
                "numerator re-anchored to A-FIN-TRANS behind a certificate-only "
                "declared_override record; q declares no ā"))

    def f3g(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["routing"][0]["via_table"] = "trans"
        return f
    out.append(("F3g_routing_via_tamper", "FIN-Q1", f3g, "V4",
                "cited hop's via_table contradicts gov_caliber_routing@v1"))

    def f3h(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["question"]["metric"] = "fin.penalty_trans_rate"
        return f
    out.append(("F3h_metric_swap", "FIN-Q1", f3h, "V0",
                "certificate pins a metric the registered alias map does not "
                "resolve q's alias to (alias-layer substitution)"))

    # ---------------- F4: disclosure-gate ----------------
    def f4a(env, con):
        f = copy.deepcopy(env)
        f["sql"] = f["sql"].replace('t0."County Name" AS cell',
                                    't0."CDSCode" AS cell', 1)
        c = f["certificate"]
        c["disclosure"]["decision"] = "ANSWER"
        c["disclosure"]["granularity"] = "school"
        c.pop("rewrite", None)
        c["probes"] = [p for p in c.get("probes") or [] if p.get("kind") != "SUPPMIN"]
        return f
    out.append(("F4a_finegrain_answer_despite_k", "CA-Q5", f4a, "V5",
                "school-grain roster ANSWER with the rollup trace stripped: the k "
                "clause re-computed from D gives min cell 1 < k=10 at the certified "
                "grain"))

    def f4b(env, con):
        f = copy.deepcopy(env)
        c = f["certificate"]
        c["disclosure"]["granularity"] = "all"
        for t in c["rewrite"]["cut_trace"]:
            if t.get("kind") == "granularity_rollup":
                t["effective_level"] = "all"
        return f
    out.append(("F4b_overcoarsened_rollup", "CODE-Q4", f4b, "V5",
                "rollup trace forged past the minimal legal level: reputation_band "
                "already has min cell 13 ≥ k=5, coarsening to 'all' violates "
                "SelectMin minimality"))

    def f4c(env, con):
        f = copy.deepcopy(env)
        tr = f["certificate"]["refusal"]["witness"]["probe_transcript"]
        tr[0]["sql"] = "SELECT 999"
        tr[0]["observed"] = 999
        return f
    out.append(("F4c_forged_suppmin_transcript", "CODE-Q7", f4c, "V6b",
                "DB witness transcript replaced by a fabricated big-cell probe: "
                "re-execution yields 999 ≥ threshold, the refusal does not replay"))

    def f4d(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["disclosure"]["policy_ids"] = []
        return f
    out.append(("F4d_policy_set_cleared", "CA-Q5", f4d, "V5",
                "Π cleared on a governed rollup certificate: independent Π "
                "re-derivation expects ['ca.pi1']"))

    def f4e(env, con):
        f = copy.deepcopy(env)
        c = f["certificate"]
        c["disclosure"] = {"decision": "ANSWER", "policy_ids": [],
                           "policy_table_present": False,
                           "ungoverned_disclosure": True,
                           "granularity": "value", "mask_closure": []}
        c.pop("rewrite", None)
        f["sql"] = 'SELECT t0."Location" FROM "users" t0 WHERE t0."Id" = 22047'
        return f
    out.append(("F4e_governed_claimed_ungoverned", "CODE-Q6", f4e, "V5",
                "governed domain laundered as ungoverned: raw protected column "
                "surfaced as a plain ANSWER"))

    def f4f(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["refusal"]["witness"]["blocking_policy_ids"] = []
        return f
    out.append(("F4f_db_blocking_set_emptied", "CODE-Q7", f4f, "V6b",
                "DISCLOSURE-BLOCKED witness citing no blocking policy"))

    def f4g(env, con):
        f = copy.deepcopy(env)
        w = f["certificate"]["refusal"]["witness"]
        w["blocking_policy_ids"] = list(w.get("blocking_policy_ids") or []) + ["th.pi99"]
        return f
    out.append(("F4g_db_alien_policy_cited", "TH-Q5", f4g, "V6b",
                "DB witness cites th.pi99, absent from gov_disclosure_policy@v"))

    def f4h(env, con):
        f = copy.deepcopy(env)
        f["certificate"]["disclosure"]["mask_closure"] = []
        return f
    out.append(("F4h_mask_closure_omitted", "CODE-Q6", f4h, "V0",
                "μ* emptied under dec=REWRITE: no narrowing axis remains, the "
                "C4 Def 4.10 mapping demands dec=ANSWER (silent-narrowing surface)"))

    def f4i(env, con):
        f = copy.deepcopy(env)
        f["sql"] = 'SELECT t0."Location" FROM "users" t0 WHERE t0."Id" = 22047'
        return f
    out.append(("F4i_mask_transform_stripped", "CODE-Q6", f4i, "V5",
                "μ* still claims generalize_last_component but the emitted query "
                "surfaces Location without the masking transform"))

    def f4j(env, con):
        f = copy.deepcopy(env)
        c = f["certificate"]
        f["sql"] = ('SELECT substr(CAST(t0."Birthday" AS VARCHAR),1,7) '
                    'FROM "Patient" t0 WHERE t0."ID" = 2110')
        for e in c["disclosure"]["mask_closure"]:
            e["mask"] = "year_month"
        for t in c["rewrite"]["cut_trace"]:
            if t.get("kind") == "mask_presentation":
                t["mask"] = "year_month"
        return f
    out.append(("F4j_mask_strength_downgraded", "TH-Q4", f4j, "V5",
                "v2 registers year_only for Birthday; the certificate presents the "
                "v1-strength year_month mask"))

    # ---------------- F5: refusal-class / replay-variant substitution --------
    # Both halves of this family were opened by verifier defects found in the
    # fifth review round (R5-M1, R5-M2); the mutations are written against the
    # frozen semantics, not against the patch.
    def _oov_substitution(env, anchor_id, coverage_mode):
        """EF2-Q6's genuine AM(iv) refusal re-labelled ⊥_OOV, carrying the
        single-anchor coverage triple (a, W_T, π_V) §6.2 prescribes."""
        f = copy.deepcopy(env)
        c = f["certificate"]
        win = next(a["window"] for a in c["anchors"] if a["anchor_id"] == anchor_id)
        f["refusal"] = "out-of-validity"
        c["refusal"] = {
            "reason": "out-of-validity",
            "witness": {"type": "window-outside-validity", "anchor_id": anchor_id,
                        "coverage_mode": coverage_mode, "requested": win,
                        "assertion": "W ∩ Cov_v(%s)[%s] = ∅" % (anchor_id, coverage_mode)},
            "ct": [{"slice": "(v1,B-EF2-RWWR-N|B-EF2-RWWR-D)",
                    "reason": "out-of-validity"}],
            "slices_pass": [],
            "composition": "slice-major(⊥_OOV 单腿真空见证)",
        }
        c["probes"] = []
        return f

    def f5a(env, con):
        return _oov_substitution(env, "A-EF2-PA", "strict_member")
    out.append(("F5a_oov_class_substitution_honest_leg", "EF2-Q6", f5a, "V6b",
                "the vacuum witness is TRUE on its own leg (2013-12-01 is no "
                "Player_Attributes marker day) — but the pair is mixed, the match "
                "leg meets its hull, and Def 3.14's coverage disjunct is pair-level: "
                "the denotation is ⊥_AM(iv), not ⊥_OOV"))

    def f5b(env, con):
        return _oov_substitution(env, "A-EF2-MATCH", "hull")
    out.append(("F5b_oov_class_substitution_covered_leg", "EF2-Q6", f5b, "V6b",
                "same substitution witnessed on the covered leg: false at leg level "
                "too (the old verifier caught only this half)"))

    def _marker_symdiff(con, ta, ca, tb, cb):
        """Unwindowed marker-day symmetric difference V(a_n) △ V(a_d), computed
        here from D so the forged payload is HONEST under the variant it
        declares — what is forged is the choice of variant, not the numbers."""
        stmt = ('SELECT DISTINCT substr(CAST("%s" AS VARCHAR),1,10) FROM main."%s" '
                'WHERE "%s" IS NOT NULL')
        A = {r[0] for r in con.execute(stmt % (ca, ta, ca)).fetchall()}
        B = {r[0] for r in con.execute(stmt % (cb, tb, cb)).fetchall()}
        return sorted(A ^ B)

    def f5c(env, con):
        f = copy.deepcopy(env)
        f.pop("sql", None)
        f["refusal"] = "anchor-mismatch"
        c = f["certificate"]
        sd = _marker_symdiff(con, "rulings", "date", "sets", "releaseDate")
        c["binding"]["adm_check_mode"] = "symdiff_audit"
        c["disclosure"]["decision"] = "REFUSE"
        c["probes"] = []
        c["refusal"] = {
            "reason": "anchor-mismatch",
            "witness": {"type": "validity-set-symdiff", "clause": "(iv)",
                        "adm_check_mode": "symdiff_audit",
                        "num_anchor": "A-CARD-RUL", "den_anchor": "A-CARD-SET",
                        "symdiff_count": len(sd), "discriminant_date": sd[0],
                        "assertion": "|V(a_n) △ V(a_d)| ≠ 0"},
            "ct": [{"slice": "(v1,B-CARD-RI-N|B-CARD-RI-D)",
                    "reason": "anchor-mismatch"}],
            "slices_pass": [], "composition": "slice-major",
        }
        return f
    out.append(("F5c_am4_variant_swap_fabricated_refusal", "CARD-Q2", f5c, "V3",
                "a question the compiler ANSWERS is refused instead: β_v's registered "
                "pair passes the window-realisation audit, so the forgery grants "
                "itself the unwindowed symdiff_audit variant, under which the two "
                "marker sets differ — a refusal manufactured out of a replay mode"))

    def f5d(env, con):
        f = copy.deepcopy(env)
        c = f["certificate"]
        sd = _marker_symdiff(con, "Match", "date", "Player_Attributes", "date")
        c["binding"]["adm_check_mode"] = "symdiff_audit"
        c["probes"] = []
        c["refusal"]["witness"] = {
            "type": "validity-set-symdiff", "clause": "(iv)",
            "adm_check_mode": "symdiff_audit",
            "num_anchor": "A-EF2-MATCH", "den_anchor": "A-EF2-PA",
            "symdiff_count": len(sd), "discriminant_date": sd[0],
            "assertion": "|V(a_n) △ V(a_d)| ≠ 0",
        }
        return f
    out.append(("F5d_am4_variant_swap_on_genuine_refusal", "EF2-Q6", f5d, "V3",
                "right verdict, self-chosen reason: the genuine AM(iv) refusal "
                "re-declared under a variant β_v does not register for this pair, "
                "with an honest payload computed under that variant"))

    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="pilot2 forgery families (F1–F5) runner")
    ap.add_argument("--out", default=os.path.join(HERE, "forge_p2_out"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    loaded = {qid: load_base(qid) for qid in BASE_QIDS}
    rows = []
    ok = True

    # harness sanity: every base certificate must ACCEPT unmutated
    for qid, (q, env, db) in sorted(loaded.items()):
        con = duckdb.connect(db, read_only=True)
        try:
            rep = chk.verify(copy.deepcopy(env), q, con)
        finally:
            con.close()
        good = rep["verdict"] == "ACCEPT"
        ok &= good
        rows.append({"name": "BASE_" + qid, "expected": "ACCEPT",
                     "actual": rep["verdict"], "ok": good,
                     "first_fail_detail": "" if good else next(
                         c["detail"] for c in rep["checks"] if c["status"] == "FAIL")[:200],
                     "note": "real compiler-emitted certificate (must ACCEPT)"})

    for row in forgeries():
        name, qid, mut, expected, note = row[:5]
        also = row[5] if len(row) > 5 else []
        q, env, db = loaded[qid]
        con = duckdb.connect(db, read_only=True)
        try:
            f = mut(copy.deepcopy(env), con)
            rep = chk.verify(f, q, con)
        finally:
            con.close()
        fails = [c for c in rep["checks"] if c["status"] == "FAIL"]
        failed_ids = [c["check"] for c in fails]
        good = (rep["verdict"] == "REJECT" and rep["rejected_by"] == expected
                and all(a in failed_ids for a in also))
        ok &= good
        rows.append({"name": name, "base": qid, "expected": expected,
                     "actual": "%s by %s" % (rep["verdict"], rep.get("rejected_by")),
                     "ok": good,
                     "failed_checks": [c["check"] for c in fails],
                     "first_fail_detail": (fails[0]["detail"][:220] if fails else ""),
                     "note": note})
        with open(os.path.join(args.out, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump({"base_qid": qid, "expected_reject_by": expected,
                       "envelope": f, "report": rep}, fh,
                      ensure_ascii=False, indent=1, default=str)

    n_base = sum(1 for r in rows if r["name"].startswith("BASE_"))
    if args.json:
        print(json.dumps({"ok": ok, "rows": rows}, ensure_ascii=False, indent=2))
    else:
        wid = max(len(r["name"]) for r in rows)
        for r in rows:
            print("%-*s  expect=%-7s  got=%-14s  %s"
                  % (wid, r["name"], r["expected"], r["actual"],
                     "OK" if r["ok"] else "** MISMATCH **"))
            if not r["ok"]:
                print("%*s  └─ %s" % (wid, "", r["first_fail_detail"] or "(accepted)"))
        print("\nFORGE-P2: %s (%d bases, %d forgeries)"
              % ("PASS" if ok else "FAIL", n_base, len(rows) - n_base))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
