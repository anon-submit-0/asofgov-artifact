#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6 Stage B harness — English-question control (poststudy2_20260823, PREREG §S6;
sha256 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669).

Mirrors poststudy_20260820/s3/rep_harness.py structure verbatim (frozen imports,
call tracing, write guard, gates, cache schema). Zero design freedom where the
prereg has spoken:
  * Imports the FROZEN modules (`pilot2/run_pilot2_arms.py` -> R2, which itself
    imports `pilot/run_pilot.py` -> RP). No prompt-assembly, call, extraction or
    scoring code is copied: prompts come from R2.build_prompt, calls from RP.llm
    (subprocess -> llmhub chat, max-tokens default 512, temperature unset, one
    sample, retry only on empty completion x3 = RP.llm(retries=2)), SQL
    extraction from RP.extract_sql, scoring from R2.fetch_and_score.
  * >>> THE SINGLE DELTA vs the frozen protocol: the question text passed to
    R2.build_prompt is `question_en` (from the sha256-frozen
    s6/questions_en.json) instead of `question_zh`. Everything else —
    schema pack, gov pack, PROMPT template, model, sampling, extraction,
    scoring — is byte-identical frozen code. <<<
  * Arms: baseline_claude / governance_informed only (PREREG §S6).
  * Freeze gate: before any call, s6/questions_en.json must hash to the value
    recorded in s6/FREEZE_questions_en.sha256 (Stage A freeze).
  * Byte-identity gate: before any call, every ZH prompt assembled with the
    frozen R2.build_prompt is asserted equal to the frozen main-study cache
    (runs/<arm>/<qid>.json) via prompt_sha256 + prompt_chars — proving the
    frozen assembly chain is unchanged; only then is the EN text swapped in.
  * Leak gate (A2 replica over EN prompts): the maximal-superset EN prompt
    (governance_informed assembly) must not contain any gold-side field string.
  * Write guard: REFUSES any write outside poststudy2_20260823/ and REFUSES to
    overwrite an existing cache file (existing cache = final, frozen-runner
    semantics; it is skipped without an LLM call).
  * Cache schema: identical key set + serialization to the frozen runner
    (qid, system, kind, value, verdict, raw[:RAW_CAP], sql, prompt_sha256,
    prompt_chars, empty_response; json indent=1 ensure_ascii=False, utf-8);
    prompt_sha256/prompt_chars describe the EN prompt actually sent.
    Call metadata (latency, token usage) goes to a SEPARATE side log
    (s6/call_log_en.jsonl), never into the cache record.

Usage:
  python3 s6_harness.py assert-only            # integrity + byte-identity, 0 calls
  python3 s6_harness.py estimate               # assemble 120 EN prompts, 0 calls
  python3 s6_harness.py run <arm> <qid> [<qid> ...]   # paid calls
  python3 s6_harness.py run <arm> --all               # full 60 (append-only)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import time

P2 = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/pilot2").resolve()
POSTSTUDY2 = (P2 / "poststudy2_20260823").resolve()
S6 = POSTSTUDY2 / "s6"
OUT_ROOT = S6 / "runs_en"
CALL_LOG = S6 / "call_log_en.jsonl"
PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"

ARMS = ("baseline_claude", "governance_informed")


# ---------------------------------------------------------------- frozen imports
def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R2 = _load("run_pilot2_arms", P2 / "run_pilot2_arms.py")   # frozen pilot2 runner
RP = R2.RP                                                  # frozen pilot runner


# ---------------------------------------------------------------- call tracing
# RP.llm is used UNCHANGED (same argv, env, timeout, retry discipline). We only
# wrap subprocess.run so the CompletedProcess (stderr carries llmhub's usage
# line "[model | prompt=N completion=M]") and wall time are observable.
_REAL_RUN = subprocess.run
TRACE: list[dict] = []


def _traced_run(*a, **kw):
    t0 = time.time()
    try:
        p = _REAL_RUN(*a, **kw)
    except Exception as e:
        TRACE.append({"dt_s": round(time.time() - t0, 3),
                      "exc": type(e).__name__, "stderr": "", "stdout_chars": 0})
        raise
    TRACE.append({"dt_s": round(time.time() - t0, 3), "exc": None,
                  "stderr": (p.stderr or "")[-2000:],
                  "stdout_chars": len(p.stdout or "")})
    return p


subprocess.run = _traced_run          # run_pilot did `import subprocess` -> same module object

_USAGE_RE = re.compile(r"\[\S+ \| prompt=(\d+|None) completion=(\d+|None)\]")


def _usage_from(trace_slice: list[dict]):
    """Last usage line wins (the successful attempt)."""
    pt = ct = None
    for t in trace_slice:
        for m in _USAGE_RE.finditer(t.get("stderr") or ""):
            pt = None if m.group(1) == "None" else int(m.group(1))
            ct = None if m.group(2) == "None" else int(m.group(2))
    return pt, ct


# ---------------------------------------------------------------- write guard
def guarded_write(path: pathlib.Path, text: str) -> None:
    rp = pathlib.Path(os.path.abspath(path))
    if not str(rp).startswith(str(POSTSTUDY2) + os.sep):
        raise SystemExit(f"[REFUSE] write outside poststudy2_20260823/: {rp}")
    if rp.exists():
        raise SystemExit(f"[REFUSE] overwrite existing cache file: {rp}")
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(text, encoding="utf-8")


def append_log(obj: dict) -> None:
    rp = pathlib.Path(os.path.abspath(CALL_LOG))
    if not str(rp).startswith(str(POSTSTUDY2) + os.sep):
        raise SystemExit(f"[REFUSE] log outside poststudy2_20260823/: {rp}")
    rp.parent.mkdir(parents=True, exist_ok=True)
    with open(rp, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- EN questions
def questions_en() -> dict:
    """Load the Stage-A frozen EN questions, gated on the freeze sha."""
    p = S6 / "questions_en.json"
    want = (S6 / "FREEZE_questions_en.sha256").read_text(encoding="utf-8").split()[0]
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    assert got == want, f"FREEZE FAIL questions_en.json: {got[:12]} != frozen {want[:12]}"
    qen = json.loads(p.read_text(encoding="utf-8"))
    assert len(qen) == 60, f"questions_en has {len(qen)} entries, want 60"
    zh_qids = {q["qid"] for q, _ in R2.questions()}
    assert set(qen) == zh_qids, "qid set mismatch EN vs frozen ZH"
    print(f"  GATE questions_en freeze OK (sha256 {got[:12]}…, 60 qids match frozen set)")
    return qen


# ---------------------------------------------------------------- gates (0 calls)
def gate_pack_integrity() -> None:
    """Prompt-pack byte/sha check against MANIFEST (18 files)."""
    man = json.loads((P2 / "prompt_pack/MANIFEST.json").read_text(encoding="utf-8"))
    for db, m in man["domains"].items():
        for kind, kc, kh in (("schema", "schema_chars", "schema_sha256"),
                             ("gov", "gov_chars", "gov_sha256")):
            t = (P2 / f"prompt_pack/{db}.{kind}.txt").read_text(encoding="utf-8")
            assert len(t) == m[kc], f"pack chars mismatch: {db}.{kind}"
            assert hashlib.sha256(t.encode()).hexdigest() == m[kh], \
                f"pack sha mismatch: {db}.{kind}"
    print("  GATE pack-integrity OK (18 files == MANIFEST byte/sha)")


def gate_channel() -> None:
    """A1 replica: first-hit channel must match frozen expectation."""
    reg = json.loads(pathlib.Path(os.path.expanduser(
        "~/.claude/skills/llmhub/channels.json")).read_text())
    for arm in ARMS:
        mdl = R2.MODEL[arm]
        homes = [c["name"] for c in reg["channels"] if mdl in c["models"]]
        assert homes and homes[0] == R2.EXPECT_CHANNEL[mdl], \
            f"channel drift for {mdl}: {homes} (frozen expects {R2.EXPECT_CHANNEL[mdl]} first)"
    print(f"  GATE channel OK (claude-opus-4-6 first-hit == "
          f"{R2.EXPECT_CHANNEL['claude-opus-4-6']!r}, as frozen)")


def gate_byte_identity(min_required: int = 3) -> dict:
    """Assemble every (arm, qid) ZH prompt with the FROZEN R2.build_prompt and
    assert sha256+chars equality against the frozen caches runs/<arm>/<qid>.json —
    the frozen assembly chain is unchanged; the EN swap is the single delta."""
    qs = R2.questions()
    stats = {}
    for arm in ARMS:
        checked = 0
        for q, d in qs:
            cache = P2 / "runs" / arm / f"{q['qid']}.json"
            if not cache.is_file():
                continue
            rec = json.loads(cache.read_text(encoding="utf-8"))
            p = R2.build_prompt(arm, d, q["question_zh"])
            got_sha = hashlib.sha256(p.encode()).hexdigest()
            assert got_sha == rec["prompt_sha256"], \
                f"BYTE-IDENTITY FAIL {arm}/{q['qid']}: sha {got_sha[:12]} != cached {rec['prompt_sha256'][:12]}"
            assert len(p) == rec["prompt_chars"], \
                f"BYTE-IDENTITY FAIL {arm}/{q['qid']}: chars {len(p)} != cached {rec['prompt_chars']}"
            checked += 1
        assert checked >= min_required, f"{arm}: only {checked} cached prompts checked (<{min_required})"
        stats[arm] = checked
        print(f"  GATE byte-identity OK ({arm}: {checked}/60 ZH cached prompt_sha256+chars matched)")
    return stats


def gate_leak_en(qen: dict) -> None:
    """A2 replica over the EN prompts: maximal-superset assembly
    (governance_informed) x 7 gold-side fields, none may appear."""
    qs = R2.questions()
    skipped = 0
    for q, d in qs:
        p = R2.build_prompt("governance_informed", d, qen[q["qid"]])
        fields = {"gold_sql": q.get("gold_sql"),
                  "windows": None if q.get("windows") is None
                  else json.dumps(q["windows"], ensure_ascii=False),
                  "windows_note": q.get("windows_note"), "notes": q.get("notes"),
                  "rewrite": None if q.get("rewrite") is None
                  else json.dumps(q["rewrite"], ensure_ascii=False),
                  "refusal_reason": q.get("refusal_reason"),
                  "gold_value": None if q.get("gold_value") is None
                  else str(q["gold_value"])}
        for k, v in fields.items():
            if v is None:
                continue
            s = v.strip() if isinstance(v, str) else str(v)
            if len(s) < 8:
                skipped += 1
                continue
            assert s not in p, f"LEAK FAIL: {q['qid']} EN prompt contains {k}"
    print(f"  GATE leak-EN OK (60x7 gold-side fields absent from EN prompts; {skipped} too-short skipped)")


# ---------------------------------------------------------------- estimate (0 calls)
def estimate(qen: dict) -> dict:
    qs = R2.questions()
    out = {"per_arm_chars": {}, "n_pairs": 0}
    for arm in ARMS:
        lens = [len(R2.build_prompt(arm, d, qen[q["qid"]])) for q, d in qs]
        out["per_arm_chars"][arm] = {"n": len(lens), "total": sum(lens),
                                     "min": min(lens), "max": max(lens)}
        out["n_pairs"] += len(lens)
    out["n_calls_full_s6_stage_b"] = out["n_pairs"]
    out["output_tokens_cap"] = out["n_pairs"] * 512
    return out


# ---------------------------------------------------------------- run (paid)
def run_calls(arm: str, qids: list[str], qen: dict) -> list[dict]:
    assert arm in ARMS, f"arm must be one of {ARMS}"
    qs = {q["qid"]: (q, d) for q, d in R2.questions()}
    for qid in qids:
        assert qid in qs, f"unknown qid {qid}"
        assert qid in qen, f"qid {qid} missing from frozen questions_en"
    results = []
    for qid in qids:
        q, d = qs[qid]
        cache = OUT_ROOT / arm / f"{qid}.json"
        if cache.exists():
            print(f"  [REFUSE-OVERWRITE] {arm}/{qid} cache exists — final, no call")
            results.append(json.loads(cache.read_text(encoding="utf-8")))
            continue
        # re-assert ZH byte identity against the frozen run of THIS (arm, qid)
        frozen = P2 / "runs" / arm / f"{qid}.json"
        if frozen.is_file():
            fr = json.loads(frozen.read_text(encoding="utf-8"))
            p_zh = R2.build_prompt(arm, d, q["question_zh"])
            assert hashlib.sha256(p_zh.encode()).hexdigest() == fr["prompt_sha256"], \
                f"BYTE-IDENTITY FAIL at call time: {arm}/{qid}"
        # THE SINGLE DELTA: question text = frozen English translation
        prompt = R2.build_prompt(arm, d, qen[qid])
        t_lo = len(TRACE)
        t0 = time.time()
        raw = RP.llm(R2.MODEL[arm], prompt)      # frozen protocol: 1 sample, retry on empty x3, 512 cap, temp unset
        latency = round(time.time() - t0, 3)
        attempts = len(TRACE) - t_lo
        pt, ct = _usage_from(TRACE[t_lo:])
        sql = RP.extract_sql(raw)
        db = str(d / "warehouse.duckdb")
        kind, value, verdict = R2.fetch_and_score(q, sql, db)
        rec = {"qid": qid, "system": arm, "kind": kind, "value": value,
               "verdict": verdict, "raw": raw[:RP.RAW_CAP], "sql": sql,
               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
               "prompt_chars": len(prompt), "empty_response": raw == ""}
        guarded_write(cache, json.dumps(rec, ensure_ascii=False, indent=1))
        append_log({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "arm": arm,
                    "qid": qid, "lang": "en", "latency_s": latency,
                    "attempts": attempts, "prompt_tokens": pt,
                    "completion_tokens": ct, "verdict": verdict,
                    "empty_response": raw == "", "prereg_sha256": PREREG_SHA})
        print(f"  CALL {arm}/{qid}: verdict={verdict} latency={latency}s "
              f"attempts={attempts} prompt_tok={pt} completion_tok={ct}")
        results.append(rec)
    return results


# ---------------------------------------------------------------- main
def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("assert-only", "estimate", "run"):
        print(__doc__)
        return 2
    mode = sys.argv[1]
    qen = questions_en()
    gate_pack_integrity()
    gate_channel()
    gate_byte_identity()
    gate_leak_en(qen)
    if mode == "assert-only":
        print("ASSERT-ONLY — zero LLM calls.")
        return 0
    if mode == "estimate":
        print(json.dumps(estimate(qen), ensure_ascii=False, indent=1))
        print("ESTIMATE — zero LLM calls.")
        return 0
    # run
    if len(sys.argv) < 3:
        raise SystemExit("run needs: <arm> <qid>... | --all")
    arm = sys.argv[2]
    rest = sys.argv[3:]
    if rest == ["--all"]:
        qids = [q["qid"] for q, _ in R2.questions()]
    else:
        qids = rest
    if not qids:
        raise SystemExit("run: no qids given (use explicit qids or --all)")
    run_calls(arm, qids, qen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
