#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""certificate.py — C5《时点证书与独立校验》定义 5.1/5.2 的证书构造器。

规范来源（只读，冻结）：C5_pointintime_certificates.md
  定义 5.1 绑定四元组 B=⟨α, ν(含 offdiag), ρ, δ(dec,Π,h_ctx,g,μ*)⟩
  定义 5.2 时点证书（应答证书携裁剪痕迹 cut trace + ≺_det 键；拒答证书携见证 + slice-major CT 附表）
  定义 5.3 四类拒答见证（MC 双见证 / AM 四条款载荷（(iii) 携 (binding_id, g^cmp, W, 失配边界点)）/
           OOV 按锚声明 coverage_mode / DB 探针笔录）
  定义 5.4 良构不变量 I1–I4 与 I2′ 三类退化变体
  §6.2 最小 schema（cert_version=c5.v1 信封）
  裁决 D5：无披露策略登记域 δ 段必标 ungoverned-disclosure（≠检查通过）

本模块仅组装 dict（C5 §6.3 "共通" 行：`_cert()` 构造辅助不含判定）；判定全部在
core.mlr_compile。纯 stdlib。证书是编译器侧制品——本库不含、也不 import 任何
校验器侧代码（C5 要求 5.8 implementation-disjointness 红线）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from .core import Decision, Intent

CERT_VERSION = "c5.v1"


def ctx_hash(ctx: Optional[dict]) -> str:
    """δ.h_ctx：请求语境哈希。pilot 无 ctx → 空语境哈希（C5 定义 5.1：
    无披露策略登记的域取空语境哈希；有策略域本轮亦为空 ctx，角色分支不命中）。"""
    canon = json.dumps(ctx or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _anchor_entries(intent: Intent, decision: Decision) -> list:
    """α：role → (anchor id + 窗)。窗记 w*（认证窗）；被裁剪时并记请求窗（cut trace 同步）。
    I2′(a)：无锚可指的角色记显式空指派（空指派是内容物，不是缺字段）。"""
    out = []
    for period in intent.periods:
        for leg in period.legs:
            # 证书窗：应答/改写证书记 w*（C4 定义 4.8(ii)/dec 映射：REWRITE 携被裁窗）；
            # 拒答证书记请求窗 w0——守卫在候选指派 α_{q,v}（角色窗=ω_r(T)）上求值，
            # w*=∅ 等裁剪事实入 witness（§6.2 witness.requested/validity），不改写 α 的窗。
            if decision.status == "REFUSE":
                win = leg.window
            else:
                win = leg.w_star if leg.w_star is not None else leg.window
            ent = {
                "role": leg.role,
                "anchor_id": leg.anchor_id,
                "registered": leg.registered,
                "coverage_mode": leg.coverage_mode,
                "granule": leg.granule,
                "window": win.to_json(),
            }
            if len(intent.periods) > 1:
                # 期坐标 0 起（C3 推论 3.17′ 角色×期展开：期 0 即基角色；与探针笔录
                # DEN_POP.period 同轴——先前 +1 写法与笔录错位，属证书构造缺陷，已修）
                ent["period"] = period.index
            if decision.status != "REFUSE" and leg.w_star is not None \
                    and leg.w_star != leg.window:
                ent["window_requested"] = leg.window.to_json()
            if leg.anchor_id is None:
                # I2'(a)：显式空指派是内容物——须记录角色与度量 id（C5 定义 5.4）
                ent["explicit_empty_assignment"] = True
                ent["empty_assignment"] = True
                ent["metric"] = intent.metric
            if leg.declared_override:
                ent["declared_override"] = True  # V0 豁免凭据：题面改锚声明机器可读入证书
            if not leg.registered and leg.anchor_id is not None:
                ent["unregistered_reference"] = True  # C3 定义 3.7 RefA_v 支
            out.append(ent)
    return out


def build_certificate(intent: Intent, decision: Decision, q: dict) -> dict:
    """构造 C5 §6.2 信封中的 certificate 对象。"""
    dec = decision.status if decision.status != "ANSWER" else "ANSWER"
    graph = intent.graph

    # ---- ν：图版本钉（含离对角标记；pilot 缺省对角 ⊛ → ver(T) 平凡对角，off_diagonal=null）----
    graph_pin = {
        "domain": graph.get("domain"),
        "graph_version": graph.get("graph_version"),
        "commit_id": graph.get("commit_id"),
        # 行 2a 离对角显式承诺（pilot2 真实版本轴；旧域恒 None → 对角缺省不变）
        "off_diagonal": intent.off_diagonal,
    }
    if graph.get("table_absent"):
        graph_pin["version_table_absent"] = True

    # ---- δ：披露决策段（D5 缺席语义）----
    dis = intent.disclosure
    disclosure = {
        "decision": dec,
        "policy_ids": decision.policy_ids,
        "policy_table_present": dis.policy_table_present,
        "ungoverned_disclosure": (not dis.policy_table_present),
        "granularity": decision.grain if decision.grain != "requested" else intent.g0,
        "mask_closure": decision.mask_closure,   # μ*（引理 4.15；pilot 聚合产出 S_raw=∅ → []）
    }

    cert = {
        "cert_version": CERT_VERSION,
        "question": {
            "qid": intent.qid,
            "domain": intent.domain,
            "metric": intent.metric,
            "metric_kind": intent.metric_kind,
            "as_of": q.get("as_of"),
        },
        "graph_pin": graph_pin,                                  # ν
        "ctx_hash": ctx_hash(None),                              # δ.h_ctx（空语境）
        "anchors": _anchor_entries(intent, decision),            # α
        "binding": (dict(intent.binding) if intent.binding else None),
        "routing": list(intent.route or []),                     # ρ（原子度量允许 ⟨⟩）
        "disclosure": disclosure,                                # δ 其余分量
        "probes": decision.probes,                               # 探针笔录（μ_den/SUPPMIN/覆盖/审计）
        "det_order": decision.det_order,                         # ≺_det 键声明（定义 4.11）
    }
    if decision.deviations:
        cert["spec_deviations"] = decision.deviations
    if decision.notes:
        cert["notes"] = decision.notes

    if decision.status == "REWRITE":
        # 定义 5.2 应答证书裁剪痕迹：保留/被裁 slice 集 + 逐 slice CT + ≺_det 键
        cert["rewrite"] = {
            "kept_slices": decision.kept_slices,
            "cut_trace": decision.cut_trace,
            "ct": decision.ct,  # 被裁 slice 原因表（本轮无被裁 slice，窗裁剪记 cut_trace）
            "det_order": decision.det_order,
        }
    if decision.status == "REFUSE":
        # 定义 5.2 拒答证书：r/w 取首失败 slice（slice-major），完整 CT 附表随证书
        cert["refusal"] = {
            "reason": decision.reason,
            "witness": decision.witness,
            "ct": decision.ct,
            "slices_pass": decision.slices_pass,  # 透明附注：通过构件（非 CT 陪域内容）
            "composition": "slice-major(≺_det slice 序取首失败 slice; slice 内守卫序 OOV→AM→MC)",
        }
    return cert


def wellformed_errors(cert: dict, envelope: dict) -> list:
    """定义 5.4 良构不变量的编译器侧自检（I1 版本封闭为构造性保证——本库一切治理对象
    读自 ν 所钉快照；此处机检 I2/I4 与 REWRITE/REFUSE 形制）。
    注意：这只是 producer 自检，不是 C5 §3 独立校验器（红线：校验器另行独立实现）。"""
    errs = []
    dec = cert["disclosure"]["decision"]
    # I4 决策—产出匹配
    if dec in ("ANSWER", "REWRITE") and "sql" not in envelope:
        errs.append("I4: 应答型 dec 但信封无 sql")
    if dec == "REFUSE" and "refusal" not in envelope:
        errs.append("I4: REFUSE dec 但信封无 refusal")
    if dec == "REFUSE":
        r = cert.get("refusal") or {}
        if not r.get("witness"):
            errs.append("I4/定义5.3: 拒答证书缺见证")
        if not r.get("ct"):
            errs.append("定义5.2: 拒答证书缺 CT 附表")
        if r.get("reason") not in ("missing-caliber", "anchor-mismatch",
                                   "out-of-validity", "disclosure-blocked"):
            errs.append("定义5.2: 拒答 reason 不在四类枚举内")
    # I2 角色覆盖（含 I2' 放宽：显式空指派/无窗记录仍是内容物）
    if not cert.get("anchors"):
        errs.append("I2: anchors 段为空（应至少含显式空指派）")
    if dec == "REWRITE" and not (cert.get("rewrite", {}).get("cut_trace")
                                 or cert.get("rewrite", {}).get("ct")):
        errs.append("定义5.2: REWRITE 证书缺裁剪痕迹")
    # V6c 前置：比率型应答证书须携分母人口探针笔录
    if dec in ("ANSWER", "REWRITE") and cert["question"]["metric_kind"] in ("ratio", "scoped_ratio"):
        if not any(p.get("kind") == "DEN_POP" for p in cert.get("probes", [])):
            errs.append("V6c 前置: 比率型应答证书缺 DEN_POP 探针笔录")
    # D5：缺席域必标 ungoverned-disclosure
    if not cert["disclosure"]["policy_table_present"] and not cert["disclosure"]["ungoverned_disclosure"]:
        errs.append("D5: 无策略登记域缺 ungoverned-disclosure 标注")
    return errs
