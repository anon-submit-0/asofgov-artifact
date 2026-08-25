#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3 repetition-study harness (poststudy_20260820, PREREG §S3; sha256
f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24).

Design (zero design freedom where the prereg has spoken):
  * Imports the FROZEN modules (`pilot2/run_pilot2_arms.py` -> R2, which itself
    imports `pilot/run_pilot.py` -> RP). No prompt-assembly, call, extraction or
    scoring code is copied: prompts come from R2.build_prompt, calls from RP.llm
    (subprocess -> llmhub chat, max-tokens default 512, temperature unset, one
    sample, retry only on empty completion x3 = RP.llm(retries=2)), SQL
    extraction from RP.extract_sql, scoring from R2.fetch_and_score.
  * Arms: baseline_claude / governance_informed only (PREREG §S3). Reps: 2..5
    (rep1 := the frozen main-study run, reused, never re-run here).
  * Byte-identity gate: before any call, every assembled prompt is asserted
    equal to the frozen cache's record via prompt_sha256 + prompt_chars
    (the frozen cache schema stores the prompt's sha256 and length, not the
    prompt text itself — sha256 equality is the byte-identity oracle).
  * Write guard: REFUSES any write outside poststudy_20260820/ and REFUSES to
    overwrite an existing cache file (existing cache = final, frozen-runner
    semantics; it is skipped without an LLM call).
  * Cache schema: identical key set + serialization to the frozen runner
    (qid, system, kind, value, verdict, raw[:RAW_CAP], sql, prompt_sha256,
    prompt_chars, empty_response; json indent=1 ensure_ascii=False, utf-8).
    Call metadata (latency, token usage) goes to a SEPARATE side log
    (s3/call_log.jsonl), never into the cache record.

Usage:
  python3 rep_harness.py assert-only            # integrity + byte-identity, 0 calls
  python3 rep_harness.py estimate               # assemble 120 prompts, 0 calls
  python3 rep_harness.py run <arm> <rep> <qid> [<qid> ...]   # paid calls
  python3 rep_harness.py run <arm> <rep> --all               # full 60 (gated)
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
POSTSTUDY = (P2 / "poststudy_20260820").resolve()
S3 = POSTSTUDY / "s3"
OUT_ROOT = S3 / "runs_rep"
CALL_LOG = S3 / "call_log.jsonl"
PREREG_SHA = "f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24"

ARMS = ("baseline_claude", "governance_informed")
REPS = (2, 3, 4, 5)          # rep1 = frozen main-study run, reused not re-run


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
    if not str(rp).startswith(str(POSTSTUDY) + os.sep):
        raise SystemExit(f"[REFUSE] write outside poststudy_20260820/: {rp}")
    if rp.exists():
        raise SystemExit(f"[REFUSE] overwrite existing cache file: {rp}")
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(text, encoding="utf-8")


def append_log(obj: dict) -> None:
    rp = pathlib.Path(os.path.abspath(CALL_LOG))
    if not str(rp).startswith(str(POSTSTUDY) + os.sep):
        raise SystemExit(f"[REFUSE] log outside poststudy_20260820/: {rp}")
    rp.parent.mkdir(parents=True, exist_ok=True)
    with open(rp, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


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
    """A1 replica for the S3 model: first-hit channel must match frozen expectation."""
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
    """Assemble every (arm, qid) prompt with the FROZEN R2.build_prompt and assert
    sha256+chars equality against the frozen caches runs/<arm>/<qid>.json."""
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
        print(f"  GATE byte-identity OK ({arm}: {checked}/60 cached prompt_sha256+chars matched)")
    return stats


# ---------------------------------------------------------------- estimate (0 calls)
def estimate() -> dict:
    qs = R2.questions()
    man = json.loads((P2 / "prompt_pack/MANIFEST.json").read_text(encoding="utf-8"))
    out = {"per_arm_chars": {}, "n_pairs": 0}
    for arm in ARMS:
        lens = [len(R2.build_prompt(arm, d, q["question_zh"])) for q, d in qs]
        out["per_arm_chars"][arm] = {"n": len(lens), "total": sum(lens),
                                     "min": min(lens), "max": max(lens)}
        assert sum(lens) == man["prompt_totals"][arm], \
            f"estimate drift vs MANIFEST for {arm}"
        out["n_pairs"] += len(lens)
    out["chars_per_reppass_both_arms"] = sum(
        v["total"] for v in out["per_arm_chars"].values())
    out["reps"] = len(REPS)
    out["n_calls_full_s3"] = len(REPS) * out["n_pairs"]
    out["input_chars_full_s3"] = out["reps"] * out["chars_per_reppass_both_arms"]
    out["output_tokens_cap_full_s3"] = out["n_calls_full_s3"] * 512
    return out


# ---------------------------------------------------------------- run (paid)
def run_calls(arm: str, rep: int, qids: list[str]) -> list[dict]:
    assert arm in ARMS, f"arm must be one of {ARMS}"
    assert rep in REPS, f"rep must be in {REPS} (rep1 is the frozen run, reused)"
    qs = {q["qid"]: (q, d) for q, d in R2.questions()}
    for qid in qids:
        assert qid in qs, f"unknown qid {qid}"
    results = []
    for qid in qids:
        q, d = qs[qid]
        cache = OUT_ROOT / arm / f"rep{rep}" / f"{qid}.json"
        if cache.exists():
            print(f"  [REFUSE-OVERWRITE] {arm}/rep{rep}/{qid} cache exists — final, no call")
            results.append(json.loads(cache.read_text(encoding="utf-8")))
            continue
        prompt = R2.build_prompt(arm, d, q["question_zh"])
        # re-assert byte identity against the frozen run of THIS (arm, qid)
        frozen = P2 / "runs" / arm / f"{qid}.json"
        if frozen.is_file():
            fr = json.loads(frozen.read_text(encoding="utf-8"))
            assert hashlib.sha256(prompt.encode()).hexdigest() == fr["prompt_sha256"], \
                f"BYTE-IDENTITY FAIL at call time: {arm}/{qid}"
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
                    "rep": rep, "qid": qid, "latency_s": latency,
                    "attempts": attempts, "prompt_tokens": pt,
                    "completion_tokens": ct, "verdict": verdict,
                    "empty_response": raw == "", "prereg_sha256": PREREG_SHA})
        print(f"  CALL {arm}/rep{rep}/{qid}: verdict={verdict} latency={latency}s "
              f"attempts={attempts} prompt_tok={pt} completion_tok={ct}")
        results.append(rec)
    return results


# ---------------------------------------------------------------- main
def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("assert-only", "estimate", "run"):
        print(__doc__)
        return 2
    mode = sys.argv[1]
    gate_pack_integrity()
    gate_channel()
    gate_byte_identity()
    if mode == "assert-only":
        print("ASSERT-ONLY — zero LLM calls.")
        return 0
    if mode == "estimate":
        print(json.dumps(estimate(), ensure_ascii=False, indent=1))
        print("ESTIMATE — zero LLM calls.")
        return 0
    # run
    if len(sys.argv) < 4:
        raise SystemExit("run needs: <arm> <rep> <qid>... | --all")
    arm, rep = sys.argv[2], int(sys.argv[3])
    rest = sys.argv[4:]
    if rest == ["--all"]:
        qids = [q["qid"] for q, _ in R2.questions()]
    else:
        qids = rest
    if not qids:
        raise SystemExit("run: no qids given (use explicit qids or --all)")
    run_calls(arm, rep, qids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
