# 集成收官报告 — as-of 编译器 × 独立证书校验器（C3/C4/C5 冻结规范）

- 日期：2026-08-02
- 规范权威：`theory/{C3_bitemporal_semantics,C4_maximal_legal_rewrite,C5_pointintime_certificates}.md`（冻结只读，sha256 见 `theory/FREEZE_SHA256_20260731.txt`）。**实现服从规范；确信规范有误处不改规范，记入 §4 偏离清单。**
- 制品：`impl/asof_compiler/`（编译器，产证书）、`impl/asof_verifier/`（独立校验器，零 import 编译器）、`impl/certs/`（51 份证书信封）、`impl/asof_verifier/forge_out/`（伪造族）。
- 本轮数据/规格补丁脚本（幂等、可复跑）：`impl/seed_patch_20260802.py`、`impl/question_spec_patch_20260802.py`。

---

## 1. 验收矩阵

| # | 关口 | 命令 | 结果 |
|---|---|---|---|
| ① | 独立校验 51 题 | `python3 /tmp/drive.py`（逐题 `asof_verifier/chk.py`） | **ACCEPT 51/51**（起点 26/51） |
| ② | 伪造族 + BASE | `python3 asof_verifier/forge.py` | **PASS：3 BASE 全 ACCEPT；16 伪造全 REJECT 且逐条命中预期检查项**（含要求的 F1a–d / F2a–e 九族） |
| ③ | 金标 + 现役等价性 | `python3 asof_compiler/acceptance.py` | **gold 51/51、legacy 51/51**（`sql_bytes_equal=27`；REWRITE 题按 w\* 出码后逐字节相等数下降，值与分支全等），良构自检 0 错 |
| ④ | 认证循环红线 | `python3 asof_verifier/ci_check.py` | **PASS：`shared_internal_roots=[]`**，校验器 import 根 ⊆ stdlib ∪ {duckdb} |

### 1.1 ① 的逐题矩阵（dec 分布：ANSWER 27 / REWRITE 10 / REFUSE 14）

| 域 | 题数 | dec 分布 | 拒答理由分布 | 校验 |
|---|---|---|---|---|
| rma | 6 | ANSWER 4 / REFUSE 2 | MC 1、AM 1 | 6/6 ACCEPT |
| quality_voc | 6 | ANSWER 4 / REFUSE 2 | AM 1、MC 1 | 6/6 ACCEPT |
| domestic_newprod | 7 | ANSWER 1 / REWRITE 4 / REFUSE 2 | AM 1、OOV 1 | 7/7 ACCEPT |
| email | 6 | ANSWER 1 / REWRITE 3 / REFUSE 2 | AM 1、MC 1 | 6/6 ACCEPT |
| aibuy | 6 | ANSWER 1 / REWRITE 3 / REFUSE 2 | MC 2 | 6/6 ACCEPT |
| public（4 库） | 20 | ANSWER 16 / REFUSE 4 | OOV 4 | 20/20 ACCEPT |

### 1.2 ② 的伪造族逐条（拒因合理性）

| 伪造 | 攻击面 | 命中 | 拒因（首条） |
|---|---|---|---|
| F1a wrong-month ANSWER | 整体一致的错月窗 | V0 | 角色窗 [2026-04-01,2026-05-01) ≠ 重导出 [2026-05-01,2026-06-01) |
| F1b empty-denominator ANSWER | 该拒不拒 | V6c | 重执行 μ_den=NULL ∈ 𝒵，MC(ii) 成立却出应答 |
| F1c window-shift MC | 拒答窗挪移 | V0 | 同 F1a 的 α 失配 |
| F1d fake window-pair AM | 伪造窗对 | V0 | 分母窗非 q 的请求窗 |
| F2a delete ν | 版本坐标缺失 | V1 | 无 graph_pin（version-swap 面） |
| F2b delete α | 锚指派缺失 | V0 | 两角色均缺失于证书 α |
| F2c delete ρ | caliber-blind 替换 | V4 | 比率型应答无路由路径 ρ |
| F2d delete δ | 披露洗白 | V5 | 无 disclosure 段 |
| F2e delete witness | 不可证伪拒答 | V6b | 拒答无见证 |
| F3a dangling ν | 钉不存在版本 | V1 | 版本在 gov_semantic_graph_version 0 行 |
| F3b ungoverned unmarked | D5 缺标 | V5 | 缺 ungoverned-disclosure 标注 |
| F3c sum(rate) | ratio-of-sums 不变式 | V6a | 对 rate 列聚合 |
| F3d fake-pair witness | 见证载荷造假 | V6b | AM(ii) 载荷窗对非 q 的请求窗对 |
| F3e alien table | 闭包外读表 | V6a | ods_erp_or_order 不在认证闭包 |
| **F3f narrowed MC probe（本轮新增）** | 探针窗收窄骗 μ_den=∅ | V6b | 探针窗 [2026-05-02,05-03) ≠ 认证窗，且 D 上 marker 行数 (5,1) vs (81,26) 不同 |
| **F3g self-declared override（本轮新增）** | 证书自签改锚豁免 | V0 | 锚 'sales_event_time' ≠ 重导出 'rma_event_time'（q 未声明 ā） |

F3f/F3g 是本轮**为自己新放宽/新增的两条校验路径**配的攻击用例：F3f 钉住 §2.7 的探针窗语义放宽不产生新洞；F3g 钉住 V0 的改锚豁免不能由证书自签获得。

辅助：`aux symdiff-57 audit: PASS` — 校验器侧独立实现的对称差审计复演冻结值 57。

---

## 2. 逐族修复记录

### 2.0 主会话已修 11 处（汇总；由代码内修复标记 + 交接说明重建，未作臆测）

| # | 修复 | 落点 | 证据 |
|---|---|---|---|
| M1 | 51 题全部补 `q["windows"]` + `windows_note`（兑现 C3 A5：ω⃗ 显式全函数呈现，作为编译器/校验器**共同输入**，不违零共享实现红线） | 6 份 questions.json | 各题 `windows_note` 字段 |
| M2 | REWRITE 题的 `q["windows"]` 从**生效窗**改回**请求窗**（据证书 cut_trace） | questions.json | 交接说明；NX-Q5/Q6 本轮补齐同批遗漏项 |
| M3 | V5 的 D5 规则由「禁一切 REWRITE」改为只禁 `REFUSE(DB)`（依 C4 定稿 dec 映射：窗/粒度收窄属绑定层现象，无策略域同样可发生） | chk.py check_V5 | 该分支注释 |
| M4 | quality_voc 种子补 `binding_role` 机器可读列（C5 V3 正/负例行判别） | quality_voc 仓 | `gov_temporal_binding.binding_role` 列存在；chk.py `resolve_binding_row` 的 `neg_cols` 分支 |
| M5 | 证书落盘改为 §6.2 **完整信封** `{sql|refusal, certificate}`（只落证书体会让 V5 的 I4 决策—产出匹配全线拒） | acceptance.py | 该处注释「集成实测：V5 I4 全线拒」 |
| M6 | 窗 JSON 改为 §6.2 规范扁平形 `{kind, lo, hi_excl}`（原嵌套 `intervals` 形属 schema 偏离） | core.Window.to_json | 该 docstring |
| M7 | 证书 α 的期坐标改 0 起，与 DEN_POP 笔录 `period` 同轴（原 +1 写法与笔录错位） | certificate.py | 该处注释 |
| M8 | `join_keys` 等 G_v 列的 JSON 解码（`_listify`），与 V4 逐字段重查一致 | adapters.py | 该 docstring |
| M9 | email/aibuy 仓补 A 原语表（`gov_valid_time_anchor`/`gov_temporal_binding`，agent-authored 版式补齐） | 两仓 | aibuy `warehouse.duckdb.bak` 无该两表、现仓有 |
| M10 | email 锚补 `coverage_mode` 列并声明 `hull_right_open`（D3 逐锚版本化属性） | email 仓 | 该列存在且取值 |
| M11 | 证书发射 `declared_override` / `unregistered_reference` 机器可读记录（V0 豁免凭据、C3 定义 3.7 RefA_v 支） | certificate.py `_anchor_entries` | 该两分支 |

### 2.1 [V0 ×3] AIBUY-Q1/Q2/Q3 — 原子度量无可解析的规定锚

- 症状：`role atom: no prescribed anchor derivable yet certificate pins 'recommendation_snapshots.created_at'`。
- 根因：aibuy 的原子登记行 `numerator/denominator_anchor` 皆 NULL，`metric → 原子锚` 的映射只活在 `compiler.BINDINGS` 字典（C5 §6.3 点名的「编译器内字典」缺口）；C3 定义 3.4 明文要求 **A_v 携带锚指派（原子型 m ↦ a_m）**。
- 修复：**数据侧**（P2）给 `gov_valid_time_anchor` 补 `metrics` 归属列（只登记原子型；比率两腿仍只由 β_v 给出，「两腿皆有才算 ratio」判据未被触碰）；**校验器侧**新增 `_anchor_metrics()` 与 `resolve_atomic_anchor` 的 `registered-assignment` 分支（置于 declared 之后、闭包推导之前——登记优先于推导）。
- 复跑：26 → 27 → …（无既有题回归；③④ 同批复核）。

### 2.2 [V6a ×7] EMAIL-ASOF-01/02/04、NX-Q1/Q2/Q3/Q5 — REWRITE 的 SQL 缺 w\* 下界

- 症状：`time predicate denotation [-inf, hi) ⊄ certified window [lo, hi)`。
- 根因：**编译器缺陷**。累计请求窗经 hull 边裁剪后证书记 w\*=[lo,hi)（并记 cut_trace、dec=REWRITE），但出码仍用请求窗的上界谓词。数据里本无更早行，值不变，但**证书主张的下界在语法上不可核验**——正是 F1c 型「窗挪移」的落点。
- 修复：**编译器侧** `_bound_pred()` + email/nx/aibuy 三域出码改从 bound 的 w\* 落谓词；w\*=w0（未裁剪）时保留现役模板逐字节形态，把 ③ 的 `sql_bytes_equal` 损失限制在真正被裁剪的题上。
- 复跑：③ 仍 51/51 gold + 51/51 legacy（值与分支全等），`sql_bytes_equal=27`——逐字节相等只在未被裁剪（w\*=w0）的题上保留，被裁剪的题按认证窗出码故与现役模板不再逐字节相同。

### 2.3 [V4/V6c ×1] AIBUY-Q4 — 比率型无 caliber 路由 ρ

- 查证：`reco_items_per_snapshot_asof` 的两腿在 β_v 中皆有锚（属真比率型），但 `gov_caliber_routing` 全域仅 1 行（profile 口径），故 C3 (b2)「比率型要求 R_v(m)↓ 且可重算」字面失败；原实现以 spec_deviation 免除该要求。
- 判定：**应有路由**。该比率的分母人口经 `snapshot_id` 的 FK 恒等归因到快照头，是结构性口径而非「率值口径」；与 AIBUY-Q5 的 grounding **率值**无分母人口口径是两回事。
- 修复：**数据侧**（P3/P4）给 `gov_caliber_routing` 补 `metric` 归属列（R_v 落为机器可读部分映射）并登记 `reco_item_to_snapshot` 恒等路由行；**编译器侧**证书补 ρ、删除对应 deviation；**校验器侧** V4 新增「所引路由的 metric 归属须等于 q.metric」（有归属列时才施加）。
- 连带：AIBUY-Q5 的 MC(i) 见证探针由 `%reco%` 模糊匹配改为 `metric='reco_grounding_coverage_rate'` 精确查键（新增的 reco 路由行不会伪造出「本度量有率值口径」）；V6b 的 MC(i) 重演同步改为按归属列查键，仅在无该列的种子上退回散文匹配。金标 AIBUY-Q5 = missing-caliber 不变。

### 2.4 [V6b ×2] AIBUY-Q5 / AIBUY-Q6 — 守卫序报告不一致

- **AIBUY-Q5**（`AM holds before MC`）：**校验器缺陷**。C3 定义 3.15 明文 `AM ⟺ β_v(m)↓ ∧ ¬P_rule`；该题绑定行两腿锚皆 NULL（β_v↑），校验器却拿 `prescribed=None` 去跑条款 (i) 的锚保真比较，凭空判 AM 成立。修：新增 `_beta_prescribes()`，β_v↓ 要求**两腿规定锚在册**（C3 定义 3.10(b2) 字面），否则 AM 守卫真空为假、由 MC(i) 捕获。**未改金标、未改证书。**
- **AIBUY-Q6**（`OOV holds before MC`）：**规范理解分歧**（详见 §5-D1）。数据事实：`ods_pg_user_profile_signal` 全 71 行 `recorded_at=2026-06-04`，按缺省 hull 读法覆盖域 = [2026-06-04,2026-06-05)，与请求窗 (-inf,2026-06-01) 交空 → 逐字读 C3 定义 3.14 应判 OOV；而 **C4 §4.4 标签归一注记 / G-10 明文钉定金标 AIBUY-Q6 = missing-caliber(MC(ii))**。规范冻结、金标优先，故不改金标；改由 D3 授权的**逐锚 coverage_mode** 承载：数据侧（P1）为该锚登记 `coverage_mode='hull_left_open'`（(-inf,max]），使窗落在覆盖域内、由 μ_den≤0 判 MC(ii)。该 mode 是对 C3 定义 3.3 `cm_a∈{hull,strict_member}` 的实现扩展，与 email 已在案的 `hull_right_open` 同族，记 DEVIATION-1（§4）。编译器侧同步：aibuy adapter 改为**读治理表**装配锚/覆盖（不再 Env=⊤），deviation 文本更正（原文称「实查无 A 表」已是事实错误）。

### 2.5 [V0 ×6 / V3 ×1] 问题规格呈现层（σ 的 ω⃗ 与 ā）

| 题 | 症状 | 判定 | 修复（`question_spec_patch_20260802.py`） |
|---|---|---|---|
| PUB-C/E/O/W-05 | 角色窗月窗 ≠ 重导出点窗 | 规格笔误（同域 01–04 与 PublicAdapter 均为 as-of 点窗） | windows 改点窗 |
| EMAIL-ASOF-05 | 分母锚 ≠ β_v 规定锚且无机读改锚记录 | ā 只活在 metric 后缀 `@message_denominator` 字符串里 | 补 `params.denominator_anchor` |
| NX-Q6 | 分子锚 ≠ 规定锚；分母窗为生效窗 | 同上（ā 只活在题面中文）；M2 同批遗漏 | 补 `params.numerator_anchor`（未注册锚引用，D8）+ 窗改请求窗 |
| NX-Q5 | dec=REWRITE 但每个坐标都等于请求 | 同 M2 遗漏（windows 记了生效窗，使裁剪不可见） | atom 窗改请求窗 |
| NX-Q7 | 证书 α 携 q 角色集之外的 numerator | 比率型 R(q)={num,den}，规格只呈现了 den | 补 numerator 角色窗 |
| QVOC-04 / rma_q3 | 期 0 窗失配 + 携 `#1` 期角色 | delta 题的 ω⃗ 未按 C3 定义 3.6「角色×期展开」呈现 | windows 改**期序列表**（QVOC-04=[as_of, as_of_prev]；rma_q3=[2026-03, 2026-05]） |

配套（校验器侧强化，非放宽）：V0 新增「q 声明 ā（且与规定锚不同）时，证书必须携机器可读 `declared_override` 记录」——兑现 C5 V0「豁免仅凭证书记录」的另一半；`cert_alpha` 承认 `unregistered_reference` 拼写为 RefA_v 支（V2 仍反查该声明真伪，见 F3g）。

### 2.6 [V3 ×2] NX-Q4 / QVOC-03 — 绑定行引用

- **NX-Q4**：`binding row 'model_mismatch_rate_align' governs metric 'model_mismatch_rate'`。**编译器缺陷**：原子度量 `product_versions_valid_asof` 借引了**另一度量**的绑定行来取锚。修：原子型不再写 binding 段（β_v 对原子型可缺省，C3 定义 3.4），锚来源改由 A_v 的锚指派登记承担（P5）。
- **QVOC-03**：`β_v(m) is defined but the certificate cites no binding_id`。原实现把 `avg_handle_hours` 当比率型却无绑定行，以 spec_deviation 跳过「比率型 β↑ → MC(i)」。查证 `gov_caliber_routing['reissue_sla_self'].note` 已明文「Σ小时/Σ工单，同口径自洽，时间基准=rma_create_date」——即两腿同锚同窗的 svw 绑定，只是**没落成登记行**。修：数据侧（P6）登记 `avg_handle_hours_align`，编译器改为查键引用 + 规则审计，**该偏离随登记消解**。

### 2.7 [V6c ×1] QVOC-03 探针窗 — 粗粒度对象的标记语义

- 症状：`probe window denotation [2026-05-01,2026-05-02) != certified window [2026-05-01,2026-06-01)`。
- 根因：**校验器过严**。C3 定义 3.3 快照锚 `vt_a(r)=gr_{g_a}(r.eff)`：月粒 roll-up（`dws_reissue_category_1m`）以月初日**标记整个月粒元**，故 `dt = DATE '2026-05-01'` 在该对象上**就是**五月窗；逐字的指称集相等是语法代理，在粗粒对象上过强。
- 修复：`validate_probe_sql` 保留「不得越出认证窗」（w_subset 硬闸），失配时改判语义等价——`_same_marker_rows()` 从 D **重查**两窗选中的行数/标记数是否相同（C5 §3.2(2) 明文授权重查，且比语法更强）。F3f 伪造证明该放宽不产生新洞。

### 2.8 [V6a ×2] rma_q3 / rma_q4 — 闭包与 SQL 扫描

- **rma_q3**：`table 'n' outside the certified closure`。**校验器缺陷**：块分解把 `FROM (SELECT …) n, (SELECT …) d` 的派生表相关名当成了表名。修：新增 `subquery_aliases()` 并入 CTE 排除集（V6a 与探针校验共用）。
- **rma_q4**：`table 'dim_problem_type' outside the certified closure`。**数据登记缺口**：该一致性维在 `gov_semantic_node` 已登记为 DIM 节点，但没有任何边把它连到事实对象；校验器的 `dimension_objects()` 只认 `dimension_of` 边（「登记入 G_v 才算认证，而非自由联结」）。修：数据侧（P7）补 `dimension_of` 边（C3 定义 3.4 的 `EdgeTy ⊇ {…}` 允许扩展类型）。

### 2.9 崩溃项（无族）

- NX-Q4 的 V6a 抛 `NameError: scd2_point_predicate is not defined`——**校验器缺陷**（函数被引用但从未定义；`verify()` 的 try 把崩溃计为失败，故未静默通过）。修：按 C3 定义 3.3 区间锚 + D7 点窗语义实现 `vf <= d < vtc` 的结构性复演。

---

## 3. 数据侧变更 provenance（`impl/seed_patch_20260802.py`，幂等可复跑）

原则：**只补登记，不改事实数据表，不改金标**。每条补的都是「已经在 note / domain_config / 编译器字典里说过、但机器不可读」的治理内容物。各仓改前副本留在 `warehouse.duckdb.bak`。

| ID | 仓 | 变更 | 依据 / provenance | 风险面 |
|---|---|---|---|---|
| P1 | aibuy | `gov_valid_time_anchor += coverage_mode`；reco 两锚 = `hull`，`user_profile_signal.recorded_at` = `hull_left_open` | C3 定义 3.3 `cm_a` + 裁决 D3（覆盖方式是锚的版本化属性）；取值由 C4 §4.4 标签归一注记钉定的金标 AIBUY-Q6=MC(ii) 反推 | `hull_left_open` 非 C3 枚举值 → DEVIATION-1 |
| P2 | aibuy | `gov_valid_time_anchor += metrics`（原子度量归属） | C3 定义 3.4「A_v 携锚指派：原子型 m↦a_m」；取值 = 现役 `compiler.py BINDINGS` / domain_config DWD date_field 的等价物 | 只登记原子型，比率两腿仍只经 β_v |
| P3 | aibuy | `gov_caliber_routing += metric`（R_v 归属） | C3 定义 3.4「R_v：metric→caliber 路由（部分映射）」；C5 §6.3 点名 METRIC_CALIBER 是编译器内字典的缺口 | 仅 aibuy 仓落列，校验器对无该列的仓退回原行为 |
| P4 | aibuy | `+ 行 reco_item_to_snapshot`（FK 恒等路由，join_keys=[snapshot_id]） | 绑定行 note 原文「single time source (FK carry), identity routing」+ `gov_semantic_edge` 已登记 `ods_pg_recommendation_snapshots → dwd_aibuy_reco_item_di normalize_of` | 与 grounding 率值口径无关，AIBUY-Q5=MC(i) 保持 |
| P5 | domestic_newprod | `gov_valid_time_anchor += metrics`（scd2→product_versions_valid_asof；prodorder_order_date→online/offline_group_order_cnt） | 同 P2；取值 = `adapters.TEMPLATES['anchor']` 硬编码的等价物 | 同 P2 |
| P6 | quality_voc | `gov_temporal_binding += 行 avg_handle_hours_align`（两腿 rma_create_date，svw，binding_role=positive） | `gov_caliber_routing['reissue_sla_self'].note` 原文「均值时效=Σ处理小时/Σ工单，同口径自洽；时间基准=rma_create_date」 | 使 QVOC-03 的旧 spec_deviation 消解 |
| P7 | rma | `gov_semantic_edge += dimension_of(dim_problem_type → dws_rma_problemtype_1d)` | `gov_semantic_node` 已登记该 DIM 节点；rma_q4 的 scope 谓词 `lvl1_name='Quality'` 经该维解析（C3 定义 3.6 的 s） | 新边类型，C3 `EdgeTy ⊇` 允许 |

问题规格补丁（`impl/question_spec_patch_20260802.py`）只动 `windows` / `params`（σ 的 ω⃗ 与 ā 呈现），**未动** `as_of`/`metric`/`gold_sql`/`gold_value`/`refusal_reason`；原文件副本留 `questions.json.bak`。

---

## 4. 规范偏离清单（deviations）

| ID | 偏离 | 范围 | 理由 / 冲突源 | 现载体 |
|---|---|---|---|---|
| **DEVIATION-1** | `coverage_mode` 取半开包络 `hull_right_open` (email) / `hull_left_open` (aibuy)，超出 C3 定义 3.3 的 `cm_a∈{hull,strict_member}` | email 6 题、aibuy 6 题 | hull 的字面读法把 EMAIL-ASOF-06 判 OOV、把 AIBUY-Q6 判 OOV，与 **C4 §4.4 标签归一注记 / G-10 钉定的金标（两题皆 MC(ii)）** 直接冲突。规范冻结优先，故以 D3 授权的逐锚版本化属性承载该读法，并显式记为偏离 | 证书 `spec_deviations`（12 题）+ chk.py `COVERAGE_MODES` 注释 |
| **DEVIATION-2** | aibuy 的 A 原语行是集成期 agent-authored 补登记，非上游 gov_seed 生产产出（email 同型，M9） | aibuy 6 题 | v2026.06.23 源 gov_seed 无 A 文件；无 A 表则 V1 对该域恒假（C5 缺口 G7 缺席语义） | 证书 `spec_deviations`（6 题） |
| **DEVIATION-3** | public 仓无 `gov_semantic_graph_version` / `gov_caliber_routing` / `gov_disclosure_policy`：graph_pin 记 `version_table_absent`，版本轴取单一合成在位版本；绑定行无 rule 列，规则记 `asof-snapshot-selection` | public 20 题 | 扰动库按 C5 缺口 G7 的缺席语义处理 | 证书 `spec_deviations`（20 题） |
| **DEVIATION-4** | 公理 5.0 的「真 typed-commit 标识」在五域种子上仍与版本号双写（`committed_at ≡ 版本标签`），无区分力 | 全域 | C5 公理 5.0 现状注记 / C3 缺口 G1 已在案；本轮未造合成 commit 序 | 未改（承继缺口） |
| **DEVIATION-5** | `Q_tmpl` 模板类无形式定义；rma_q3 的差分模板在 C5 定理 5.10(b) 覆盖范围之外（多期推广= 缺口 G6） | rma_q3 / QVOC-04 | C5 定理 5.10(b) 现状看护条款 | 未改（承继缺口） |

**本轮消解的旧偏离两条**：① QVOC-03「比率型 β↑ 却按原子型放行」→ 经 P6 登记消解；② AIBUY-Q4「免除 R_v(m) 要求」→ 经 P3/P4 登记消解。

---

## 5. 两个独立实现首次对表暴露的分歧（C5 章实证素材）

> 口径：把两套独立实现（编译器 `asof_compiler` / 校验器 `asof_verifier`，CI 断言零共享内部模块）首次对同一 51 题对表时**判读不一致**的每一处逐条记录。分类三值：**［规范理解分歧］**＝两侧各自读规范但读法不同（规范文本在该点欠定或两处措辞可分歧）；**［实现缺陷］**＝规范无歧义，一侧写错；**［数据登记缺口］**＝两侧读法一致，但治理内容物没落成机器可读登记，使校验侧无法从 (q,G_v) 重导出。

| # | 分歧点 | 编译器侧读法 | 校验器侧读法 | 谁对 | 分类 | 落点 |
|---|---|---|---|---|---|---|
| D1 | **AIBUY-Q6 的首成立守卫** | 覆盖域不参与（Env=⊤），直接落 μ_den≤0 → MC(ii) | 按缺省 hull 求 Cov=[2026-06-04,06-05)，与请求窗交空 → OOV 先成立 | 规范（C4 §4.4/G-10 钉 MC(ii)）— 两侧各对一半：编译器结论对、依据缺；校验器依据对、与冻结金标冲突 | ［规范理解分歧］C3 定义 3.14 的覆盖域算法 vs C4 标签归一注记的金标钉定 | P1 登记 `hull_left_open`；DEVIATION-1 |
| D2 | **β_v(m)↓ 的判据** | 绑定行存在即视作有绑定（哪怕两腿锚 NULL） | 曾拿 `prescribed=None` 跑条款 (i)，凭空判 AM | 规范：C3 定义 3.10(b2)「两腿规定锚在册」才算 β_v↓；定义 3.15 以 β_v↓ 为 AM 前提 | ［规范理解分歧］「绑定行在册」≠「β_v(m)↓」，两处措辞可分歧 | chk.py `_beta_prescribes()` |
| D3 | **原子度量的规定锚从哪来** | 编译器字典 `BINDINGS`/`TEMPLATES['anchor']` | 只认 A_v/β_v 与继承闭包，判「无可解析规定锚」 | 校验器（C3 定义 3.4：A_v 携锚指派） | ［数据登记缺口］ | P2/P5 `metrics` 列 + chk.py registered-assignment 分支 |
| D4 | **比率型是否必须携 ρ** | 同锚同窗计数比可免（写进 deviation） | C3 (b2) 字面：比率型要求 R_v(m)↓ 且可重算 | 校验器 | ［数据登记缺口］（R_v 未落机器可读归属；结构性恒等路由未登记） | P3/P4 + 证书补 ρ |
| D5 | **avg_handle_hours 的型别** | 比率型但无绑定行，以 deviation 放行 | 比率型 β↑ → 应判 MC(i)（与金标值题冲突） | 规范（两侧读法其实一致，缺的是登记） | ［数据登记缺口］绑定只写在 routing note 散文里 | P6 登记行 |
| D6 | **REWRITE 的 SQL 是否必须写下界** | 值不变即可，出码仍用请求窗上界 | C5 V6a：时间谓词指称集 ⊆ 认证窗，下界不可核验即失配 | 校验器 | ［实现缺陷］（编译器侧） | `_bound_pred()` 三域出码 |
| D7 | **原子题能否借引别的度量的绑定行** | 借 `binding_ref` 取锚 | V3 逐 id 查键：该行治理的不是本题 metric | 校验器 | ［实现缺陷］（编译器侧） | nx adapter 原子型不写 binding 段 |
| D8 | **探针窗的上界写法** | `recorded_at < (DATE 'd' + INTERVAL 1 DAY)` | 语法层不可解 → 指称集读作 ⊤ → 探针窗留白 | 校验器 | ［实现缺陷］（编译器侧：证书主张须可被语法核验） | aibuy 探针改字面窗谓词 |
| D9 | **粗粒对象上的探针窗相等性** | 月表 `dt = 月初日` 即整月 | 逐字指称集相等 → 判失配 | 编译器（C3 定义 3.3 `vt_a(r)=gr_{g_a}(r.eff)`） | ［规范理解分歧］窗代数的「标记值空间 vs 粒元空间」在 C3 未逐字给出投影规则 | chk.py `_same_marker_rows()`（保留不得越窗硬闸）+ F3f |
| D10 | **派生表相关名算不算触达对象** | — | `FROM (SELECT …) n` 的 `n` 被当表名 | 编译器 | ［实现缺陷］（校验器侧 SQL 扫描） | `subquery_aliases()` |
| D11 | **一致性维联结算不算越闭包** | 直接联结 `dim_problem_type` 解析 scope 谓词 | 认闭包（α ∪ 继承 ∪ 发布节点 ∪ 已登记维 ∪ ρ via），该维无边 → 越界 | 校验器（「登记入 G_v 才算认证」） | ［数据登记缺口］ | P7 `dimension_of` 边 |
| D12 | **区间锚点窗谓词的复演** | 出 `vf <= d AND vt > d` | 该复演函数**根本没实现**（NameError） | 编译器 | ［实现缺陷］（校验器侧） | `scd2_point_predicate()` |
| D13 | **改锚声明 ā 的载体** | 从题面中文/metric 后缀正则解析，证书记 `declared_override` | σ 里查无 ā，判「锚 ≠ 规定锚」 | 规范（C3 定义 3.6：ā 是 σ 的分量，须机器可读呈现） | ［规范理解分歧］C5 V0 只说「须以机器可读记录在**证书**内」，未说 q 侧也须呈现；只凭证书自记会让豁免变成自签许可（见 F3g） | 问题规格补 `params.*_anchor` + V0 双向核对 |
| D14 | **delta 题的 ω⃗ 呈现形** | 期序由编译器 QSPEC/params 内部展开 | 只见单期 windows，判期 0 窗失配 + 多余 `#1` 角色 | 规范（C3 定义 3.6 角色×期展开 / 推论 3.17′） | ［数据登记缺口］（规格呈现层缺口） | windows 改期序列表 |
| D15 | **未注册锚引用的证书拼写** | `anchor_id` + `unregistered_reference: true` | 只认 `anchor_ref` 键 | 两侧皆可（C5 §6.2 未钉该拼写） | ［规范理解分歧］schema 欠定 | cert_alpha 承认两种拼写；V2 反查声明真伪 |

**计数**：15 条分歧中，［规范理解分歧］5（D1/D2/D9/D13/D15）、［实现缺陷］5（D6/D7/D8/D10/D12，其中编译器侧 3、校验器侧 2）、［数据登记缺口］5（D3/D4/D5/D11/D14）。

**可写进 C5 的三条观察**：
1. **「零共享实现」确实抓到了单侧实现无法自证的错**：5 条实现缺陷里，编译器侧 3 条（D6/D7/D8）全部是「值对、证书主张不可核验」型——单跑金标（③ 一直 51/51）永远暴露不出来，只有独立重演才会失败。这正是 C5 §3.2 认证循环红线的实证。
2. **最大的一类不是 bug 而是登记缺口（5/15）**：治理内容物写在 note 散文、domain_config 注释、编译器字典里时，编译器「知道」而校验器「查不到」。C5 §6.3 已点名的 METRIC_CALIBER/METRIC_ANCHORS 缺口，在对表时表现为 V0/V4 的系统性拒绝。**证书可核验性反过来成了治理登记完备性的度量**。
3. **规范理解分歧集中在「守卫谓词的对象在何种情形下不可指」（D1/D2/D9）**：C3 的真空约定给了三值→二值的形式化，但「覆盖域怎么算」「β_v↓ 怎么判」「标记值 vs 粒元」这三处的算法层读法仍可分歧，且分歧会**改变拒答类**（OOV vs MC）——这是拒答语义作为一等值时最实际的风险面，值得在 C5 里单独立一节。

---

## 6. 复跑方式（全绿基线）

```bash
cd "/Volumes/SSD 1/explore_opportunity_cc/impl"
python3 seed_patch_20260802.py            # 数据登记（幂等）
python3 question_spec_patch_20260802.py   # 规格呈现（幂等）
python3 asof_compiler/acceptance.py       # ③ gold 51/51 + legacy 51/51 + 重出 certs/
python3 /tmp/drive.py                     # ① ACCEPT 51/51
python3 asof_verifier/forge.py            # ② 3 BASE ACCEPT + 16 伪造 REJECT
python3 asof_verifier/ci_check.py         # ④ shared_internal_roots = []
```

单题详查：

```bash
python3 asof_verifier/chk.py --cert certs/<qid>.json \
  --questions <domain_dir>/questions.json --qid <qid> \
  --db <domain_dir>/warehouse.duckdb --json
```
