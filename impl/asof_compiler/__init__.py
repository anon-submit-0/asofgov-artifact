#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asof_compiler — 统一 MLR（Maximal Legal Rewriting）编译器库。

对外接口：
    compile_question(q: dict, domain_dir: str|Path) -> envelope dict
        envelope = {"sql": "..."} | {"refusal": "<reason>"}，并携 "certificate"（C5 §6.2）。

规范：theory/{C3,C4,C5}（冻结，sha256 见 theory/FREEZE_SHA256_20260731.txt）。
纪律：纯 python3 + duckdb + stdlib；对 pilot/ 只读；不 import 现役编译器，
不 import 任何校验器侧代码（C5 要求 5.8 implementation-disjointness）。
"""
from __future__ import annotations

import pathlib

import duckdb

from .adapters import adapter_for
from .certificate import build_certificate, wellformed_errors
from .core import mlr_compile

__all__ = ["compile_question", "wellformed_errors"]


def compile_question(q: dict, domain_dir) -> dict:
    """编译一题：装配（adapters）→ MLR-Compile（core）→ 证书（certificate）→ 信封。

    一次编译在单个 read_only duckdb 连接内完成（SA 快照假定：探针读与出码
    引用同一快照；C4 §4.4 producer/consumer 注记）。
    """
    dir_path = pathlib.Path(domain_dir)
    adapter = adapter_for(q.get("domain", dir_path.name), dir_path)
    con = duckdb.connect(adapter.db, read_only=True)
    try:
        intent = adapter.intent(q, con)
        decision = mlr_compile(intent)
        cert = build_certificate(intent, decision, q)
    finally:
        con.close()
    if decision.status == "REFUSE":
        envelope = {"refusal": decision.reason}
    else:
        envelope = {"sql": decision.sql}
    envelope["certificate"] = cert
    return envelope
