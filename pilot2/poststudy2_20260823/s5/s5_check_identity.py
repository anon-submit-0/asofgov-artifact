#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s5_check_identity.py — evidence for the 1x compile-identity claim.

Recompiles the 8 financial questions on the 1x substrate with the frozen
compiler and compares each envelope json (sort_keys) against the frozen
impl/certs2/<qid>.json. Writes s5_identity_check.json.
"""
import datetime as dt
import json
import pathlib
import sys

S5 = pathlib.Path(__file__).resolve().parent
IMPL = pathlib.Path("/Volumes/SSD 1/explore_opportunity_cc/impl")
sys.path.insert(0, str(IMPL))
from asof_compiler import compile_question  # noqa: E402

d = S5 / "work" / "rowscale" / "scale_100" / "financial"
qs = json.loads((d / "questions.json").read_text(encoding="utf-8"))
rows = []
for q in qs:
    env = compile_question(q, d)
    frozen = json.loads((IMPL / "certs2" / ("%s.json" % q["qid"]))
                        .read_text(encoding="utf-8"))
    same = (json.dumps(env, sort_keys=True, default=str)
            == json.dumps(frozen, sort_keys=True, default=str))
    rows.append({"qid": q["qid"], "identical_to_frozen": same})
out = {
    "schema": "asofgov/s5_identity_check.v1",
    "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    "generator": "pilot2/poststudy2_20260823/s5/s5_check_identity.py",
    "substrate": "work/rowscale/scale_100/financial (byte copy of sandbox "
                 "financial warehouse)",
    "per_question": rows,
    "all_identical": all(r["identical_to_frozen"] for r in rows),
}
(S5 / "s5_identity_check.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("all_identical =", out["all_identical"])
