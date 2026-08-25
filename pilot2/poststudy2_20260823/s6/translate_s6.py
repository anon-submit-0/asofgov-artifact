# -*- coding: utf-8 -*-
"""S6 Stage A translation driver (PREREG_poststudy2_20260823.md sha
838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669).

Translates each of the 60 `question_zh` to English with llmhub
(claude-opus-4-6) under a fixed gold-invariant instruction. The model sees
ONLY the Chinese question text — no structured fields, no gold-side fields.
Raw outputs land append-only under s6/translation_raw/{qid}.json; existing
files are never overwritten (resume-safe). Not a scored arm: zero scored
calls, translations only.
"""
import glob
import json
import os
import subprocess
import sys
import time

ROOT = "/Volumes/SSD 1/explore_opportunity_cc/pilot2"
S6 = os.path.join(ROOT, "poststudy2_20260823", "s6")
RAW = os.path.join(S6, "translation_raw")
LLMHUB = os.path.expanduser("~/.claude/skills/llmhub/bin/llmhub.py")
MODEL = "claude-opus-4-6"

INSTRUCTION = """You are translating one Chinese benchmark question about temporal (as-of / bitemporal) data-governance queries into English. This must be a GOLD-INVARIANT translation:
1. Preserve EVERY date, number, and identifier EXACTLY as written in the source (e.g. 1997-06-15, 2014-2015, Id=22047, GOT≥60, v1). Do not reformat ISO dates. Render a Chinese year-month like "2017 年 2 月" as "February 2017".
2. Preserve the declared-at phrasing: "以 X 为声明时点" -> "With X as the declaration instant," (keep the declaration-time concept explicit).
3. Keep every "as-of" token exactly as it appears: "as-of 2015-04-15" stays "as-of 2015-04-15"; "as-of 2013-08 月粒" stays "as-of 2013-08 at month granularity".
4. Preserve window semantics exactly: "所在月窗" -> "the containing month window"; "所在年窗" -> "the containing year window"; "单日窗" -> "single-day window"; "月粒" -> "month granularity"; "日粒" -> "daily granularity"; "自然年" -> "calendar year"; "学年" -> "school year"; "赛季" -> "season"; "区间" -> a range/interval phrase keeping both endpoint dates verbatim.
5. Translate the metric alias by meaning as a metric-like noun phrase (e.g. "问题贷款率" -> "problem loan rate"); do not expand it into a formula or definition.
6. Preserve version-pin phrasing: "显式钉定治理版本 v1" -> "explicitly pinning governance version v1".
7. Preserve "按当时生效口径" -> "under the caliber in effect at that time"; "按当时默认口径" -> "under the default caliber at that time"; "按现行披露策略呈现" -> "presented under the current disclosure policy"; "治理路由口径" -> "governance-routed caliber"; "按当前轮替口径" -> "under the current rotation caliber"; "按当时生效积分口径" -> "under the points caliber in effect at that time"; "按当时生效人口口径" -> "under the population caliber in effect at that time".
8. ADD NOTHING: no explanations, no window endpoint dates that are not in the source, no SQL, no answers, no notes.
Output ONLY the English translation as a single line.

Chinese question: """


def call_llmhub(prompt, max_tokens=400, timeout=180):
    p = subprocess.run(
        [sys.executable, LLMHUB, "chat", "--model", MODEL,
         "--max-tokens", str(max_tokens), "--timeout", str(timeout),
         "--prompt", prompt],
        capture_output=True, text=True, timeout=timeout + 60)
    return p.stdout.strip(), p.stderr.strip(), p.returncode


def main():
    os.makedirs(RAW, exist_ok=True)
    questions = []
    for f in sorted(glob.glob(os.path.join(ROOT, "domains", "*", "questions.json"))):
        for q in json.load(open(f)):
            questions.append({"qid": q["qid"], "domain": q["domain"],
                              "question_zh": q["question_zh"]})
    assert len(questions) == 60, len(questions)

    n_done = n_new = n_fail = 0
    for q in questions:
        out_path = os.path.join(RAW, q["qid"] + ".json")
        if os.path.exists(out_path):  # append-only resume: never overwrite
            n_done += 1
            continue
        prompt = INSTRUCTION + q["question_zh"]
        text, err, rc, attempts = "", "", -1, []
        for attempt in range(1, 4):  # retry only on empty, x3
            text, err, rc = call_llmhub(prompt)
            attempts.append({"attempt": attempt, "rc": rc,
                             "stderr_head": err.splitlines()[:2]})
            if rc == 0 and text:
                break
            time.sleep(2)
        rec = {"qid": q["qid"], "domain": q["domain"],
               "question_zh": q["question_zh"], "model": MODEL,
               "instruction_sha_note": "fixed INSTRUCTION in translate_s6.py",
               "question_en_raw": text, "attempts": attempts,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if not (rc == 0 and text):
            n_fail += 1
            rec["empty_after_retries"] = True
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1)
        os.rename(tmp, out_path)
        n_new += 1
        print(f"[{q['qid']}] {'OK' if text else 'EMPTY'} :: {text[:90]}",
              flush=True)
    print(f"done: existing={n_done} new={n_new} empty_fail={n_fail}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
