#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.py — C4《披露门下的最大合法改写》算法 MLR-Compile（行 1–25）的忠实引擎实现。

规范来源（只读，冻结 sha256 见 theory/FREEZE_SHA256_20260731.txt）：
  C4_maximal_legal_rewrite.md   §4.4 算法行 1–25、§4.2 定义 4.6–4.11、§4.3 引理 4.12–4.17
  C3_bitemporal_semantics.md    §5 守卫链（定义 3.14–3.16、注记 3.18′ 报告序 OOV→AM→MC、
                                推论 3.17′ 期序×守卫序）、定义 3.7 未注册锚约定、D7 点窗、D8
  C5_pointintime_certificates.md 定义 5.2 slice-major CT、定义 5.3 见证形制

引擎层持有算法结构（枚举序、守卫序、CT、≺_det、dec 映射）；一切数据访问
（覆盖探针、规则审计条款(iv)、μ_den 质量探针、SUPPMIN）经 adapter 回调注入，
本模块不含任何 SQL 与领域词汇。纯 python3 stdlib。

对照条目（行号 → 本文件落点）：
  行 1–2b  版本轴解析与对角闸门/承诺剔空     -> mlr_compile() 步骤 V（pilot 单版本、⊛ 缺省，
           commit map 为标签（C3 G1）→ ver(T) 对角线缺省解析退化为唯一在位版本；
           结构闸门保留：显式钉不存在版本 → AM(i) 类比（行 2b））
  行 5–6   AdmBindings / 注册层缺失 MC(i)、κ 剔空 AM(i) -> intent.mc_missing / kappa_empty
  行 7     slice 枚举（版本×锚指派，注册序）   -> periods × slices 循环
  行 8–9   w* = w0 ⊓ Env 逐 leg 结构裁剪 + 覆盖检查（逐锚 coverage_mode，D3；
           hull-edge 豁免 + 裁剪痕迹；rigid strict_member 越界 → OOV）
  行 10    完整规则谓词 P_rule 条款 (i)–(iv)（D8 未注册锚 → AM(i)；(iv) 经 I 审计）
  行 11    质量探针 μ_den ≤ 0 → MC(ii)（D1/D4；探针笔录记 observed）
  行 12–14 GrainFrontier（推论 4.17 退化：Γ 单点；D5 无策略域恒 ANSWER+ungoverned）
           + 掩码闭包 μ*（引理 4.15）
  行 15    Front 空 → REFUSE⟨CT⟩（slice-major：≺_det slice 序首失败 slice，
           slice 内守卫序 OOV→AM→MC；多期按 3.17′ 期序×守卫序）
  行 16    SelectMin_{≺_det}（版本新→注册序→ℓ_Γ；pilot 每 slice 单候选，序键仍入证书）
  行 17    ANSWER⟨plan, cert⟩；dec 映射：任一 leg w*≠w0 或 g≠g0 → 证书层 REWRITE+cut trace
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# 拒答原因 token（跨章统一拼写，C4 定义 4.10 / C5 定义 5.2）
# ---------------------------------------------------------------------------
OOV = "out-of-validity"
AM = "anchor-mismatch"
MC = "missing-caliber"
DB = "disclosure-blocked"

GUARD_ORDER = (OOV, AM, MC, DB)  # D2 报告序（DB 恒居绑定层三类之后，行 13）


# ---------------------------------------------------------------------------
# 窗代数（C3 定义 3.2 日历窗代数的日粒实现；A4.4(ii) 封顶）
# 窗 = 有限个半开日区间 [lo, hi) 之并；lo=None → -inf，hi=None → +inf。
# ---------------------------------------------------------------------------
_DAY = datetime.timedelta(days=1)


def _d(x) -> Optional[datetime.date]:
    if x is None or isinstance(x, datetime.date):
        return x
    return datetime.date.fromisoformat(str(x)[:10])


@dataclass(frozen=True)
class Window:
    """有限区间并（规范形：已排序、两两不交、相邻已合并）。kind 仅为呈现标签。"""

    ivs: tuple  # tuple[(lo|None, hi|None), ...]
    kind: str = "interval"

    # -- 构造子 ------------------------------------------------------------
    @staticmethod
    def month(ym: str) -> "Window":
        y, m = int(ym[:4]), int(ym[5:7])
        lo = datetime.date(y, m, 1)
        hi = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
        return Window(((lo, hi),), "month")

    @staticmethod
    def year(yy: str) -> "Window":
        y = int(yy)
        return Window(((datetime.date(y, 1, 1), datetime.date(y + 1, 1, 1)),), "year")

    @staticmethod
    def point(day) -> "Window":
        day = _d(day)
        return Window(((day, day + _DAY),), "point")

    @staticmethod
    def cumulative_to(day) -> "Window":
        """累计窗 (-inf, day]（C3 定义 3.2：domestic_newprod/email/aibuy 快照类）。"""
        day = _d(day)
        return Window(((None, day + _DAY),), "cumulative")

    @staticmethod
    def interval(lo, hi_excl, kind: str = "interval") -> "Window":
        return Window(((_d(lo), _d(hi_excl)),), kind)

    @staticmethod
    def empty() -> "Window":
        return Window((), "empty")

    # -- 谓词与运算 ----------------------------------------------------------
    def is_empty(self) -> bool:
        return not self.ivs

    def intersect(self, other: "Window", kind: Optional[str] = None) -> "Window":
        out = []
        for lo1, hi1 in self.ivs:
            for lo2, hi2 in other.ivs:
                lo = lo1 if lo2 is None else (lo2 if lo1 is None else max(lo1, lo2))
                hi = hi1 if hi2 is None else (hi2 if hi1 is None else min(hi1, hi2))
                if lo is None or hi is None or lo < hi:
                    out.append((lo, hi))
        out.sort(key=lambda p: (p[0] is not None, p[0] or datetime.date.min))
        merged = []
        for lo, hi in out:
            if merged and _le(lo, merged[-1][1]):
                merged[-1] = (merged[-1][0], _max_hi(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        return Window(tuple(merged), kind or self.kind)

    def __eq__(self, other) -> bool:  # 逐分量相等（定义 4.7 窗代数约定）
        return isinstance(other, Window) and self.ivs == other.ivs

    def __hash__(self):
        return hash(self.ivs)

    def subset_of(self, other: "Window") -> bool:
        return self.intersect(other) == Window(self.ivs, self.kind)

    def to_json(self) -> dict:
        """C5 §6.2 canonical flat window object {"kind", "lo", "hi_excl"}
        (lo/hi omitted when unbounded). The former nested "intervals" list was a
        schema deviation (fixed at integration); the multi-interval fallback is
        kept for completeness but never occurs in the pilot (A4.4(ii) 单区间)."""
        if len(self.ivs) == 1:
            lo, hi = self.ivs[0]
            out = {"kind": self.kind}
            if lo is not None:
                out["lo"] = lo.isoformat()
            if hi is not None:
                out["hi_excl"] = hi.isoformat()
            return out
        return {
            "kind": self.kind,
            "intervals": [
                {"lo": None if lo is None else lo.isoformat(),
                 "hi_excl": None if hi is None else hi.isoformat()}
                for lo, hi in self.ivs
            ],
        }

    def brief(self) -> str:
        if not self.ivs:
            return "(empty)"
        return "+".join(
            f"[{lo.isoformat() if lo else '-inf'},{hi.isoformat() if hi else '+inf'})"
            for lo, hi in self.ivs
        )


def _le(lo, hi_prev) -> bool:
    if lo is None:
        return True
    if hi_prev is None:
        return True
    return lo <= hi_prev


def _max_hi(a, b):
    if a is None or b is None:
        return None
    return max(a, b)


# ---------------------------------------------------------------------------
# 覆盖检查结果（行 8–9；adapter 覆盖探针的返回类型）
# ---------------------------------------------------------------------------
@dataclass
class CovResult:
    mode: str                    # 'hull' | 'strict_member' | 'none'（none=无覆盖约束，装配注记）
    bound: Window                # w*_ℓ = w0,ℓ ⊓ Env
    empty: bool
    w0_subset_val: bool          # w0,ℓ ⊆ val（rigid strict_member 检查用）
    env_brief: str               # Env 摘要（证书/见证用）
    probe: Optional[dict] = None # 探针笔录条目
    deviation: Optional[str] = None


# ---------------------------------------------------------------------------
# 意图 IR（定义 4.6 查询意图 q=⟨m,σ,g0,w0,κ⟩ 的实例化；adapter 产出）
# ---------------------------------------------------------------------------
@dataclass
class Leg:
    role: str                          # 'numerator' | 'denominator' | 'atom'
    anchor_id: Optional[str]           # 本次指派的锚（含 ā 改锚；None → I2'(a) 显式空指派）
    registered: bool                   # 锚 ∈ A_v ?（False → C3 未注册锚约定/D8）
    required_anchor_id: Optional[str]  # 规定锚 a*_role（β_v/A_v）
    window: Window                     # w0,ℓ（请求窗）
    rigid_window: bool = False         # κ 窗坐标刚性?
    granule: str = "day"               # 标记粒度（'day'|'week'|'month'|'itv'；标签表示）
    coverage: Optional[Callable[["Leg"], CovResult]] = None  # None → 不参与 Cov/OOV
    declared_override: bool = False    # ā 声明改锚?
    # -- 编译期填充 --
    w_star: Optional[Window] = None
    coverage_mode: Optional[str] = None
    cuts: list = field(default_factory=list)


@dataclass
class Period:
    index: int
    label: str
    legs: list                                     # list[Leg]
    den_probe: Optional[Callable[[dict], dict]] = None
    # den_probe(bound_windows_by_role) -> {'sql','observed','mu_den'}；None → 原子型（无行 11）


@dataclass
class RuleAudit:
    """行 10 完整规则谓词 P_rule 条款 (i)–(iv) 的判定材料。"""
    binding_id: Optional[str]
    rule: Optional[str]
    adm_check_mode: str = "trivial_true"   # trivial_true | symdiff_audit | interval_containment
    g_cmp: str = "day"                     # 条款 (iii) 比较粒度（缺省 g_n ⊓ g_d）
    # (iv) 审计执行器：() -> {'ok','sql','observed','discriminant',...}；None → 平凡真
    adm_audit: Optional[Callable[[], dict]] = None
    # AM(i) 判别元材料（错配锚对对称差等，C3 原型对照）：(declared_pair) -> dict | None
    mismatch_material: Optional[Callable[[], dict]] = None


@dataclass
class Disclosure:
    policy_table_present: bool
    policies: list = field(default_factory=list)    # 策略行 dict（含 policy_id/min_grain/k/mask...）
    touched: list = field(default_factory=list)     # 被触及策略 id（P̄_π ∩ R(q) ≠ ∅，adapter 静态计算）
    role_hit: list = field(default_factory=list)    # D1 角色命中策略 id（pilot 空 ctx → 恒空）
    suppmin_probe: Optional[Callable[[str], dict]] = None  # SUPPMIN_π 探针（k>0 且被触及时）
    # ---- pilot2（真实非退化披露域）扩展：C4 行 12–14 的非单点 Γ ----
    # lattice: ↑g0 的粒度爬升链（请求级在首；由 G_v 的 lattice_levels ∩ 请求级截断，
    #          gov_granularity_edge 落每级的分组表达）。None → 退化单点（旧域路径）。
    lattice: Optional[list] = None
    # legal_at(level) -> {"ok": bool, "exempt": bool, "probe": {...} | None}
    #   Legal(ℓ) 的引理 4.16 求值闭包（k 小胞条款 SUPPMIN_π(ℓ) ≥ k_π 对 D 探针；
    #   顶层 k_exempt_top 豁免记 exempt）。仅 lattice 非空时使用。
    legal_at: Optional[Callable[[str], dict]] = None
    # 掩码义务 μ*（引理 4.15）：S_raw ∩ P̄_π ≠ ∅ 时逐属性的 ∨μ_π 记录
    # [{"attributes":[...], "mask": mask_class, "policy_id": ...}]；非空 → dec=REWRITE。
    mask_obligations: list = field(default_factory=list)
    # 名录/原值行呈现的刚性闭包封顶（S-M2 ⊤_M）：adapter 预判 U_min=∅ 时携 DB 见证
    block: Optional[dict] = None


@dataclass
class Intent:
    qid: str
    domain: str
    metric: str
    metric_kind: str                    # 'atomic' | 'ratio' | 'scoped_ratio'
    graph: dict                         # {'domain','graph_version','commit_id',['table_absent']}
    periods: list                       # list[Period]（声明期序，推论 3.17′）
    combine: str = "single"             # 'single' | 'delta'
    binding: Optional[dict] = None      # {'binding_id','rule','adm_check_mode','numerator_anchor','denominator_anchor'}
    rule_audit: Optional[RuleAudit] = None
    route: Optional[list] = None        # ρ：路由边 dict 列表（[] 允许：原子/装配缺省）
    g0: str = "requested"
    disclosure: Disclosure = field(default_factory=lambda: Disclosure(False))
    emit_sql: Optional[Callable[[dict], str]] = None   # bound → plan SQL（C3 出码，adapter 模板）
    # -- 前置哨兵（行 2a/2b、行 5–6、I2' 退化变体） --
    oov_parse: Optional[dict] = None    # as-of 不可解析（I2'(b)）→ OOV 见证载荷
    oov_scope: Optional[dict] = None    # 请求窗/主体不可落锚（aibuy 会话缺失形）→ OOV
    mc_missing: Optional[dict] = None   # MC(i)：metric/路由/绑定注册缺失 → 见证载荷
    kappa_empty: Optional[dict] = None  # AM(i) 类比：版本/锚承诺剔空（行 2b/6）
    version_pin: Optional[str] = None   # 显式钉版本（⊛=None，对角缺省）
    # 离对角显式钉（行 2a：p ≠ ver(T) 且 p ∈ 可解析版本集时的承诺标记；C5 定义 5.1 ν.offdiag）。
    # pilot2 版本轴真实（committed_at 时间戳全序）；adapter 解析 ver(declared_at) 后落此标记。
    off_diagonal: Optional[dict] = None
    # 跨锚对审计前置（pilot2 裁定：same_valid_time_window 双锚比率的实现集审计
    # 先于逐腿覆盖裁定——锚对不相容是"对子"的失配，不化归为单腿 OOV；仅当两腿
    # 实现集同空才回落单腿覆盖 OOV。命中即 REFUSE AM，载荷为条款 (iv) 见证。
    am_precheck: Optional[dict] = None
    deviations: list = field(default_factory=list)
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 判定结果
# ---------------------------------------------------------------------------
@dataclass
class Decision:
    status: str                         # 'ANSWER' | 'REWRITE' | 'REFUSE'
    sql: Optional[str] = None
    reason: Optional[str] = None        # 拒答 token
    witness: Optional[dict] = None      # 首失败 slice 见证（slice-major）
    ct: list = field(default_factory=list)          # 完整逐 slice 原因表（附表）
    slices_pass: list = field(default_factory=list)
    probes: list = field(default_factory=list)      # 探针笔录
    bound: dict = field(default_factory=dict)       # period.index -> {role: Leg}
    cut_trace: list = field(default_factory=list)
    kept_slices: list = field(default_factory=list)
    grain: str = "requested"
    mask_closure: list = field(default_factory=list)
    policy_ids: list = field(default_factory=list)
    det_order: dict = field(default_factory=dict)
    deviations: list = field(default_factory=list)
    notes: list = field(default_factory=list)


DET_ORDER = {
    # 定义 4.11：≺_det 三键（版本新者先、绑定注册序、ℓ_Γ 声明线性扩张）。
    # pilot 每 slice 单候选，键序仍写入证书以可审计（定理 4.19(c)）。
    "keys": ["version_desc", "binding_registration(binding_id)", "ell_gamma"],
    "ell_gamma_id": "pointwise-g0(pilot degenerate lattice)",
}


def _slice_id(intent: Intent, period: Period) -> str:
    core = intent.binding["binding_id"] if intent.binding else (
        intent.periods[0].legs[0].anchor_id if intent.periods and intent.periods[0].legs
        and intent.periods[0].legs[0].anchor_id else intent.metric)
    s = f"({intent.graph.get('graph_version') or '-'},{core})"
    if len(intent.periods) > 1:
        s += f"@p{period.index + 1}"
    return s


# ---------------------------------------------------------------------------
# 行 10：完整规则谓词 P_rule 条款 (i)–(iv)
# ---------------------------------------------------------------------------
def _rule_check(intent: Intent, period: Period, probes: list):
    """返回 None（通过）或 (AM, witness)。条款序 (i)→(ii)→(iii)→(iv)（C5 定义 5.3 见证形制）。"""
    ra = intent.rule_audit
    legs = {l.role: l for l in period.legs}

    # ---- 条款 (i) 锚保真（含 D8 未注册锚：原子型同判 AM(i)；C3 定义 3.7 未注册锚约定）----
    for leg in period.legs:
        if leg.anchor_id is not None and not leg.registered:
            w = {
                "type": "anchor-override",
                "clause": "(i)",
                "role": leg.role,
                "declared_anchor": leg.anchor_id,
                "required_anchor": leg.required_anchor_id,
                "assertion": "A_v 查无此锚（未注册锚引用；D8：与度量型别无关，同判 AM(i)）",
            }
            return AM, w
        if leg.declared_override and leg.required_anchor_id is not None \
                and leg.anchor_id != leg.required_anchor_id:
            w = {
                "type": "anchor-override",
                "clause": "(i)",
                "role": leg.role,
                "declared_anchor": leg.anchor_id,
                "required_anchor": leg.required_anchor_id,
                "assertion": "ā 改锚 ≠ 规定锚（svw 条款 (i) 锚保真违背）",
            }
            if ra and ra.mismatch_material:
                m = ra.mismatch_material()
                if m:
                    if m.get("probe"):
                        probes.append(m["probe"])
                    w["discriminant"] = {k: v for k, v in m.items() if k != "probe"}
            return AM, w

    if ra is None or ra.rule is None:
        return None  # β_v(m) 缺省（原子型）：无跨腿规则可审（C3 定义 3.4 缺失约定）

    if ra.rule == "same_valid_time_window":
        # ---- 条款 (ii) 同窗：W_n = W_d（逐分量相等，定义 4.7）----
        n, d = legs.get("numerator"), legs.get("denominator")
        if n is not None and d is not None and n.window != d.window:
            return AM, {
                "type": "window-pair",
                "clause": "(ii)",
                "num_anchor": n.anchor_id, "num_window": n.window.to_json(),
                "den_anchor": d.anchor_id, "den_window": d.window.to_json(),
                "assertion": "W_num != W_den（same_valid_time_window 条款 (ii) 违背）",
            }
        # ---- 条款 (iii) 窗-粒度可表达：W ∈ W_{g^cmp}（C5 定义 5.3 (iii) 载荷）----
        shared = (n or d or period.legs[0]).window
        bad = _granule_misalignment(shared, ra.g_cmp)
        if bad is not None:
            return AM, {
                "type": "window-grain-inexpressible",
                "clause": "(iii)",
                "binding_id": ra.binding_id,
                "g_cmp": ra.g_cmp,
                "window": shared.to_json(),
                "mismatch_boundary_point": bad,
                "assertion": f"W ∉ W_(g_cmp={ra.g_cmp})：边界点 {bad} 不落粒元边界",
            }
        # ---- 条款 (iv) 锚对相容审计（经 I 数据访问；adm_check_mode 机器可读）----
        if ra.adm_audit is not None:
            a = ra.adm_audit()
            if a.get("probe"):
                probes.append(a["probe"])
            if not a["ok"]:
                return AM, {
                    "type": "validity-set-symdiff" if ra.adm_check_mode == "symdiff_audit"
                            else "anchor-pair-incompatible",
                    "clause": "(iv)",
                    "adm_check_mode": ra.adm_check_mode,
                    **{k: v for k, v in a.items() if k not in ("ok", "probe")},
                }
    return None


def _granule_misalignment(w: Window, g_cmp: str):
    """条款 (iii)：W 的每个极大区间端点须落 g_cmp 粒元边界。

    pilot 标签表示约定：week/month 标记粒度锚的请求窗以标签日呈现（单标签窗按构造
    对齐其粒元，C3 定义 3.2 注），故 'day'/'label' 恒对齐；'month' 校验月边界。
    返回首个失配边界点（ISO 字符串）或 None。
    """
    if g_cmp in ("day", "label", "week", "itv"):
        return None
    if g_cmp == "month":
        for lo, hi in w.ivs:
            if lo is not None and lo.day != 1:
                return lo.isoformat()
            if hi is not None and hi.day != 1:
                return hi.isoformat()
    return None


# ---------------------------------------------------------------------------
# 行 12–14：GrainFrontier（推论 4.17 退化）+ 掩码闭包 μ*（引理 4.15）
# ---------------------------------------------------------------------------
def _grain_frontier(intent: Intent, probes: list):
    """返回 (u_min: list, mask_closure: list, policy_ids: list, db_witness | None)。

    D5（缺席域披露语义）：D_v=∅ → 无约束恒 ANSWER，行 12 一步返回 {g0}，
    证书 disclosure 段标注 ungoverned-disclosure（由 certificate 层落字段）。
    Γ 每题单点（pilot 退化：↑g0 = {g0}）；Legal(g0) 按引理 4.16 三条款于
    touched_D2 上求值（D1 角色命中豁免——pilot 空 ctx，role_hit 恒空）。
    """
    dis = intent.disclosure

    # ---- pilot2 非退化路径：真实 Γ 链（引理 4.16 逐级 Legal 求值 + 掩码闭包） ----
    # 结果按 intent 记忆化：行 12–13（逐 slice）与行 16–17（出码前）各调用一次，
    # 探针笔录只落一次（C5 探针笔录与重演一一对应）。
    if dis.block is not None or dis.lattice is not None or dis.mask_obligations:
        cached = getattr(intent, "_frontier_cache", None)
        if cached is not None:
            return cached
        if dis.block is not None:
            # 名录/原值行呈现的刚性封顶（S-M2）：掩码/小胞策略触及且呈现不可降级 → U_min=∅
            for pr in dis.block.get("probe_transcript") or []:
                if pr.get("sql"):
                    probes.append({"kind": "SUPPMIN", **{k: pr[k] for k in pr
                                                         if k != "assertion"}})
            res = ([], [], list(dis.touched), dict(dis.block))
            intent._frontier_cache = res
            return res
        mask = list(dis.mask_obligations)
        if dis.lattice:
            transcript = []
            chosen = None
            for lvl in dis.lattice:
                r = dis.legal_at(lvl) if dis.legal_at else {"ok": True}
                if r.get("probe"):
                    probes.append(r["probe"])
                    transcript.append({k: r["probe"].get(k) for k in
                                       ("policy_id", "level", "sql", "observed", "threshold")})
                if r.get("ok"):
                    chosen = lvl
                    break
            if chosen is None:
                res = ([], [], list(dis.touched), {
                    "type": "empty-legal-rewrite",
                    "blocked_slices": [_slice_id(intent, intent.periods[0])],
                    "blocking_policy_ids": list(dis.touched),
                    "probe_transcript": transcript,
                    "u_min_empty": True,
                    "assertion": "Γ 链逐级 Legal 求值全败（k 小胞条款）：U_min = ∅ → DB",
                })
                intent._frontier_cache = res
                return res
            res = ([chosen], mask, list(dis.touched), None)
            intent._frontier_cache = res
            return res
        res = ([intent.g0], mask, list(dis.touched), None)
        intent._frontier_cache = res
        return res

    if not dis.policy_table_present or not dis.touched:
        return [intent.g0], [], [], None

    touched = [p for p in dis.policies if p["policy_id"] in dis.touched]
    mask = []
    for p in touched:
        # D2 粒度条款：γ_π ⪯ g0（单点格：按 min_grain 标签与 g0 声明的粒度轴比对）
        mg = p.get("min_grain")
        if mg and not _grain_ok(mg, intent.g0):
            return [], [], [p["policy_id"] for p in touched], {
                "type": "empty-legal-rewrite",
                "blocked_slices": [_slice_id(intent, intent.periods[0])],
                "blocking_policy_ids": [p["policy_id"]],
                "probe_transcript": [],
                "u_min_empty": True,
                "assertion": f"粒度条款失败：min_grain={mg} 不粗于等于 g0={intent.g0}（Γ 单点，无上卷可用）",
            }
        # D2 小胞条款：SUPPMIN_π(g0) >= k_π（k null → 0 真空）
        k = p.get("k_threshold")
        if k and dis.suppmin_probe is not None:
            s = dis.suppmin_probe(p["policy_id"])
            probes.append({"kind": "SUPPMIN", "policy_id": p["policy_id"],
                           "sql": s.get("sql"), "observed": s.get("observed")})
            if (s.get("observed") or 0) < k:
                return [], [], [p["policy_id"] for p in touched], {
                    "type": "empty-legal-rewrite",
                    "blocked_slices": [_slice_id(intent, intent.periods[0])],
                    "blocking_policy_ids": [p["policy_id"]],
                    "probe_transcript": [{"kind": "SUPPMIN", "policy_id": p["policy_id"],
                                          "observed": s.get("observed"), "threshold": k}],
                    "u_min_empty": True,
                }
        # D2 掩码条款（引理 4.15 闭包）：S_raw ∩ P̄_π 逐属性取 ∨μ_π；
        # pilot 全部产出为聚合标量，S_raw=∅ → 无掩码义务（μ* 空并取 id）。
        if p.get("mask_class") and p.get("raw_presented"):
            mask.append({"attributes": p["raw_presented"], "mask": p["mask_class"],
                         "policy_id": p["policy_id"]})
    return [intent.g0], mask, [p["policy_id"] for p in touched], None


def _grain_ok(min_grain: str, g0: str) -> bool:
    # 单点格退化：g0 标签包含策略粒度轴（如 g0='session_id×asof' ⊇ min_grain='session_id'）
    return min_grain in g0


# ---------------------------------------------------------------------------
# 主编译：MLR-Compile 行 1–25
# ---------------------------------------------------------------------------
def mlr_compile(intent: Intent) -> Decision:
    probes: list = []
    ct: list = []
    slices_pass: list = []
    notes = list(intent.notes)
    deviations = list(intent.deviations)

    # ===== 行 1–2b：版本轴 =====
    # V_res：能解析 T 的版本集（逐版本在位区间 ∩ T）。pilot：commit map 为版本标签
    # （C3 G1，C5 公理 5.0 现状注记），单版本在位区间取 [t1=-inf, +inf) → ver(T) 平凡
    # （C3 定义 3.5 "pilot 单版本时 ver 平凡"），行 2a 对角闸门结构上不可触发。
    if intent.version_pin is not None and intent.version_pin != intent.graph.get("graph_version"):
        # 行 2b：显式钉不存在版本 → 版本承诺剔空，AM(i) 类比（D1）
        w = {"type": "version-commitment-empty",
             "pinned": intent.version_pin,
             "available": [intent.graph.get("graph_version")],
             "assertion": "钉不存在的版本号：版本承诺剔空可解析版本集（AM(i) 类比，行 2b）"}
        return Decision("REFUSE", reason=AM, witness=w,
                        ct=[{"slice": "(*,*)", "reason": AM}], probes=probes,
                        det_order=DET_ORDER, deviations=deviations, notes=notes)

    # ===== I2'(b)：as-of 不可解析 → OOV 退化变体（C5 定义 5.4）=====
    if intent.oov_parse is not None:
        w = {"type": "asof-unparseable", **intent.oov_parse,
             "assertion": "as-of 串不可解析为窗代数元素（A5 全函数呈现的 ↑ 哨兵；I2'(b)）"}
        return Decision("REFUSE", reason=OOV, witness=w,
                        ct=[{"slice": "(*,*)", "reason": OOV}], probes=probes,
                        det_order=DET_ORDER, deviations=deviations, notes=notes)
    # 请求窗/主体不可落任何有效锚域（aibuy 会话主体缺失形）→ OOV
    if intent.oov_scope is not None:
        w = {"type": "window-outside-validity", **intent.oov_scope}
        return Decision("REFUSE", reason=OOV, witness=w,
                        ct=[{"slice": "(*,*)", "reason": OOV}], probes=probes,
                        det_order=DET_ORDER, deviations=deviations, notes=notes)

    # ===== 行 5–6：AdmBindings；注册层缺失 → MC(i)（守卫链上 OOV/AM 真空约定先行成立）=====
    # C3 定义 3.14 真空约定：对象不可指的支按假处理——metric/路由/绑定缺失时无锚可评
    # OOV、无规则可评 AM，守卫域上 MC(i) 首个成立（注记 3.18″ 第 1 条走位）。
    if intent.mc_missing is not None:
        if intent.mc_missing.get("probe"):
            probes.append(intent.mc_missing["probe"])
        w = {"type": "routing-lookup",
             **{k: v for k, v in intent.mc_missing.items() if k != "probe"}}
        return Decision("REFUSE", reason=MC, witness=w,
                        ct=[{"slice": f"({intent.graph.get('graph_version') or '-'},*)",
                             "reason": MC}],
                        probes=probes, det_order=DET_ORDER,
                        deviations=deviations, notes=notes)
    if intent.kappa_empty is not None:
        w = {"type": "commitment-empty", **intent.kappa_empty,
             "assertion": "κ 承诺剔空 A_adm/V_adm（AM(i)，行 2b/6）"}
        return Decision("REFUSE", reason=AM, witness=w,
                        ct=[{"slice": f"({intent.graph.get('graph_version') or '-'},*)",
                             "reason": AM}],
                        probes=probes, det_order=DET_ORDER,
                        deviations=deviations, notes=notes)
    if intent.am_precheck is not None:
        # 跨锚对 window_realization_symdiff 审计失败（对子级失配先于逐腿覆盖；
        # 见 Intent.am_precheck 注）：条款 (iv) 见证直出。
        p = dict(intent.am_precheck)
        if p.get("probe"):
            probes.append(p.pop("probe"))
        w = {"type": "validity-set-symdiff", "clause": "(iv)", **p}
        return Decision("REFUSE", reason=AM, witness=w,
                        ct=[{"slice": f"({intent.graph.get('graph_version') or '-'},"
                                      f"{(intent.binding or {}).get('binding_id') or '*'})",
                             "reason": AM}],
                        probes=probes, det_order=DET_ORDER,
                        deviations=deviations, notes=notes)

    # ===== 行 7–14：slice 枚举（pilot：单版本 × 单绑定指派；多期为分段构件，3.17′）=====
    failures = []   # (period_index, slice_id, reason, witness)
    bound: dict = {}
    for period in intent.periods:
        sid = _slice_id(intent, period)
        outcome = None

        # ---- 行 8–9：w* = w0 ⊓ Env，逐 leg（逐锚 coverage_mode，D3）----
        for leg in period.legs:
            if leg.coverage is None:
                # 未注册锚引用不参与 Cov/OOV（C3 定义 3.7 未注册锚约定）；
                # 或 A 原语缺席装配（Env=⊤，adapter 已记 deviation）
                leg.w_star = leg.window
                continue
            cov = leg.coverage(leg)
            leg.w_star = cov.bound
            leg.coverage_mode = cov.mode
            if cov.probe:
                probes.append(cov.probe)
            if cov.deviation and cov.deviation not in deviations:
                deviations.append(cov.deviation)
            if cov.bound != leg.window and not cov.empty:
                leg.cuts.append({
                    "period": period.index, "role": leg.role, "anchor_id": leg.anchor_id,
                    "requested": leg.window.to_json(), "bound": cov.bound.to_json(),
                    "cut": f"coverage-{cov.mode}: {leg.window.brief()} -> {cov.bound.brief()}",
                })
            if cov.empty or (leg.rigid_window and cov.mode == "strict_member"
                             and not cov.w0_subset_val):
                outcome = (OOV, {
                    "type": "window-outside-validity",
                    "anchor_id": leg.anchor_id,
                    "role": leg.role,
                    "coverage_mode": cov.mode,
                    "requested": leg.window.to_json(),
                    "validity": cov.env_brief,
                    "validity_probe_sql": (cov.probe or {}).get("sql"),
                    "observed": (cov.probe or {}).get("observed"),
                    "assertion": "W ∩ Cov_v(a) = ∅（锚覆盖域真空）" if cov.empty
                                 else "刚性窗越出 strict_member 有效标记集（行 9）",
                })
                break

        # ---- 行 10：完整规则谓词 P_rule 条款 (i)–(iv) ----
        if outcome is None:
            r = _rule_check(intent, period, probes)
            if r is not None:
                outcome = r

        # ---- 行 11：质量探针 μ_den ≤ 0 → MC(ii)（D1/D4；A4.4(iii)）----
        if outcome is None and period.den_probe is not None:
            bw = {leg.role: leg.w_star for leg in period.legs}
            p = period.den_probe(bw)
            probes.append({"kind": "DEN_POP", "role": "denominator",
                           "period": period.index, "sql": p.get("sql"),
                           "observed": p.get("observed")})
            mu = p.get("mu_den")
            if mu is None or mu <= 0:
                outcome = (MC, {
                    "type": "empty-denominator-probe",
                    "probe_sql": p.get("sql"),
                    "observed": p.get("observed"),
                    "assertion": "μ_den ≤ 0（或空/NULL）：同窗分母质量空，MC(ii)（D4 加宽谓词）",
                })

        # ---- 行 12–13：GrainFrontier / DB ----
        refuse_pol_ids = []
        if outcome is None:
            u_min, mask, pol_ids, dbw = _grain_frontier(intent, probes)
            if dbw is not None:
                outcome = (DB, dbw)
                refuse_pol_ids = pol_ids  # δ.Π 于 DB 拒答仍指被触及策略集（C5 定义 5.1）

        if outcome is not None:
            failures.append((period.index, sid, outcome[0], outcome[1], refuse_pol_ids))
            ct.append({"slice": sid, "reason": outcome[0]})
        else:
            slices_pass.append(sid)
            bound[period.index] = {leg.role: leg for leg in period.legs}

    # ===== 行 15：Front 空 → REFUSE（期序×守卫序，3.17′；slice-major，C5 定义 5.2）=====
    if failures:
        first = failures[0]  # 声明期序首失败期；slice 内首因即守卫序（检查次序=报告序，D2）
        return Decision("REFUSE", reason=first[2], witness=first[3], ct=ct,
                        slices_pass=slices_pass, probes=probes,
                        policy_ids=list(first[4] or []),
                        det_order=DET_ORDER, deviations=deviations, notes=notes,
                        bound=bound)

    # ===== 行 16–17：SelectMin_{≺_det} + 出码；dec 映射（定义 4.10）=====
    u_min, mask, pol_ids, _ = _grain_frontier(intent, probes)
    grain = u_min[0] if u_min else intent.g0   # SelectMin：Γ 链首个合法级（单点域 = g0）
    intent.chosen_grain = grain                # 出码闭包读（报表 SQL 依最终粒度落分组表达）
    sql = intent.emit_sql(bound) if intent.emit_sql else None
    cut_trace = [c for per in bound.values() for leg in per.values() for c in leg.cuts]
    if grain != intent.g0:
        # 定义 4.10 dec 映射：g ≠ g0 → REWRITE；上卷痕迹与窗裁剪同入 cut trace（定义 5.2）
        cut_trace.append({"kind": "granularity_rollup",
                          "requested_level": intent.g0, "effective_level": grain,
                          "policy_ids": pol_ids})
    for m in mask:
        cut_trace.append({"kind": "mask_presentation", **m})
    rewrite = bool(cut_trace)  # 任一 leg w*≠w0 ∨ g≠g0 ∨ μ*≠id → 证书层 REWRITE
    return Decision("REWRITE" if rewrite else "ANSWER", sql=sql, ct=[],
                    slices_pass=slices_pass, probes=probes, bound=bound,
                    cut_trace=cut_trace, kept_slices=slices_pass,
                    grain=grain, mask_closure=mask, policy_ids=pol_ids,
                    det_order=DET_ORDER, deviations=deviations, notes=notes)
