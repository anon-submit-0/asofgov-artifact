# PORT_REPORT — pilot2 九公开库双侧移植（编译器 + 独立校验器）

日期：2026-08-04。范围：把 impl/ 的 MLR 编译器与 C5 独立校验器接到 pilot2 的九个公开库
（gov_* 十表双版本种子 + 60 题冻结金标），首次真实触发披露门/粒度爬升/掩码闭包路径；
企业轨 51 题全部保留且回归不破。规范权威：theory/{C3,C4,C5}（冻结只读）。

## 0. 终局判定（全部可复算）

| 关口 | 命令 | 结果 |
|---|---|---|
| pilot2 编译器金标 | `python3 asof_compiler/acceptance_pilot2.py` | **gold 60/60**（含拒因子型 mc_i/mc_ii/am_i–iv 全对齐 + rewrite kind 对齐），良构自检 **0** 错，证书 60 份 → `impl/certs2/`（聚合 sha1 `60dbd2560450f157cb57b2e7b8bb94501801edcd`） |
| pilot2 独立校验 | `python3 asof_verifier/runall.py p2` | **ACCEPT 60/60**（window_source：derived 50 / declared 8 / declared-override 2） |
| pilot2 严格无声明窗 | 同上 `--no-declared-windows` 轨 | **ACCEPT 50/60**；10 个 REJECT 全部是题面呈现窗坐标的题（8×window_request：CARD-Q5/DEB-Q5/DEB-Q7/EF2-Q2/EF2-Q4/FIN-Q6/F1-Q6/W1-Q4 + 2×cross_window：FIN-Q8/W1-Q5），全部由 V0 拒——`window_gran=range_request` 与跨窗祈使按登记语义就是"声明输入"，fail-closed 与老轨协议一致 |
| 企业轨回归（编译器） | `python3 asof_compiler/acceptance.py` | **gold 51/51、legacy 51/51（sql_bytes_equal=27）**、良构 0 错——与移植前逐字节同 |
| 企业轨证书字节稳定 | 划痕副本回退本次全部编译器改动重出 51 份对比 | **51 份 .json 逐字节一致**（聚合 sha1 `22cf91881af778dfa4ff39097f08a6b30015e930`，改前=改后；此前报告引用的 `2f7787…` 系 macOS `._*` AppleDouble 资源叉混入聚合所致，非内容差异） |
| 企业轨回归（校验器） | `python3 asof_verifier/runall.py old51` | **ACCEPT 51/51**；`--no-declared-windows` **49/51**——两轨数字与移植前 INDEPENDENCE_REPORT 基线逐题一致 |
| 伪造回归（老族） | `python3 asof_verifier/forge.py` | **PASS（3 基×16 伪造全拒 + aux symdiff-57 复算）** |
| 伪造新增（p2 变异电池） | scratch `mutate_p2.py`（13 变异） | **13/13 REJECT**：窗+1d→V0、版本换轨→V1、离对角标记删除→V1、细粒度伪 REWRITE→V0、细粒度伪 ANSWER→**V5（k 条款独立重算 min cell 1<5）**、掩码闭包删除→V0、MC(ii) observed 篡改→V6b、AM(iv) symdiff_count 篡改→V6b、Π 清空→V5、metric 换名→V0（别名重解析）、路由删除→V4、裁剪痕迹隐藏→V0 |
| 零共享红线 | `python3 asof_verifier/ci_check.py` | **PASS：failures=[]、shared_internal_roots=[]**（校验器 import 根 ⊆ stdlib∪{duckdb}；两侧零交集） |
| pilot2 侧闸（未触碰的哨兵） | `python3 pilot2/ci/leak_check.py` | PASS（n=60, problems=0, inter=[]）——本任务未写 pilot2/ 任何文件 |

## 1. 编译器侧改动清单（impl/asof_compiler/）

| 文件 | 改动 | 规范落点 |
|---|---|---|
| `adapters_pilot2.py`（**新增**，~900 行） | 九库一份的通用适配器 `Pilot2Adapter`：gov_* 十表装载（`P2Gov`）→ `ver(declared_at)` 版本解析（timestamps 提交映射 + `pinned_version` → 离对角承诺 / 未提交钉 OOV / 前治理期 OOV）→ 别名→metric_id（映射随版本变；查无→MC(i)）→ `_LegAsm` 度量/腿/口径装配（谓词原子 + 路由 hop 树程序化拼 SQL，自连接只承载连接语义）→ 逐锚窗现算（hull=min/max、strict_member=distinct 集、token 粒（YYYYMM/YYYY-MM/学年）映射日历日空间、SCD-2 D7 点窗在效探针、cum_day 包络）→ 守卫材料（AM(i) 改锚查无、AM(ii) 跨窗分腿、AM(iii) 周窗×月粒 g^cmp、AM(iv) `window_realization_symdiff` 对子审计、MC(i) dst_caliber='none'、MC(ii) μ_den 腿标量探针）→ 披露装配（见 §3）。出码谓词统一 `substr(CAST(col AS VARCHAR),1,10)` 日粒形 / token 等值形；裁剪后按 w* 回落谓词（V6a 指称一致） | C4 行 1–25 全链、C3 定义 3.2–3.8、D7/D8 |
| `core.py` | 向后兼容扩展：`Intent.off_diagonal`（行 2a 离对角承诺）、`Intent.am_precheck`（跨锚对审计先于逐腿覆盖的裁定支）、`Disclosure.{lattice, legal_at, mask_obligations, block}`、`_grain_frontier` 非退化分支（Γ 链逐级 Legal 求值 + SUPPMIN 笔录 + U_min=∅ → DB 见证；按 intent 记忆化防笔录重复）、dec 映射扩展 `g≠g0 ∨ μ*≠id → REWRITE`（上卷/掩码痕迹入 cut_trace）、REFUSE(DB) 携 δ.Π | C4 行 12–14、引理 4.15/4.16、定义 4.10 |
| `certificate.py` | `graph_pin.off_diagonal` 从 intent 落字（旧域恒 None，字节不变） | C5 定义 5.1 ν.offdiag |
| `adapters.py` | `adapter_for` 前置 pilot2 域名分派（4 行；旧域路径未动） | — |
| `acceptance_pilot2.py`（**新增**） | 60 题三关验收：金标（标量 1e-9 / 字符串全等 / 报表逐胞 / 拒因 token+子型 / rewrite kind）、证书落盘 `certs2/`、良构自检 | — |

未动：`acceptance.py`、五生产域与 public 适配器逐字节未变；`pilot/`、`pilot2/`、`theory/` 零写入。

## 2. 校验器侧改动清单（impl/asof_verifier/chk.py + runall.py）

全部改动只依赖 stdlib+duckdb，不 import 编译器与 pilot2/build（路径 B）；窗算术/覆盖/审计/胞普查全部独立实现。

| 块 | 改动 |
|---|---|
| `Gv` 十表规范化 | `is_p2` 结构探测（gov_metric 在表即 p2）；`rows()` 认 `graph_version` 版本列 + JSON 列解码；`version_rows()` 归一 version/committed_at（真时间戳 → `commit_map()` 天然 timestamps 模式，ver(T) 首次非平凡）；`anchors()` 联 `gov_semantic_node` 归一为旧访问形（semantic_object/effective_date/coverage_mode/granularity/vf/vtc）；`bindings()` 把逐腿行合成组合视图（`binding_id="N|D"`，`binding_by_id` 按集合匹配）；`routings()` 归一 hop 行（caliber_key=routing_id、via_table、join_keys、metric/leg/hop_seq/节点对）；新增 `metric_row/measures/gran_edges/aliases_map/node_table` 访问器 |
| 窗约定（工程纪律③） | `p2_window_periods`：只依据 G_v（逐腿 window_gran + 锚 granularity + point_in_effect 规则）+ D（cum_day 包络对 D 现算）+ 题面非窗字段（as_of / delta 的 periods 年表）推导 ω_r；`range_request` 登记的就是"呈现窗即坐标"→ 归 declared（`--no-declared-windows` 下如实 fail-closed）；attribute 度量判为非时态（无腿窗可推，α 持 I2'(a) 空指派）。`declared_window_periods` 扩展 p2 呈现三拼法（windows 的 num/den 别名、`cross_window` 月 token 对、`window_request` day_range/week/month_token_range）；window_source∈{derived, declared, declared-override} 标注与开关语义原样沿用 |
| 版本轴 V1 | ver(T) 的 T 改取 `declared_at`（缺省回落 as_of，老轨不变）；离对角证书重演 `off_diagonal={pinned, ver_as_of}` 与 ver(T) 对账（F1-Q3 镜像 GOLD-1：无标记的离对角读零痕迹即拒） |
| V0 | 新增别名层重解析（alias@v → metric_id 必须等于证书钉的 metric；金标 q.metric 同步对账）；REWRITE 收窄映射扩展到 g 轴与 μ*（窗收窄 ∨ 粒度上卷 ∨ 掩码呈现降级三者其一）；非时态角色窗跳过比对；p2 的 ā 字符串改锚按"主腿"（比率=分子，否则 atom）约定展开 |
| SQL 原子扫描（V6a/探针） | 新增 `substr(CAST(col AS VARCHAR),1,10)` 日粒原子、`CAST(col AS VARCHAR)` 与裸列的日历 token 原子（YYYYMM/YYYY-MM/YYYY-YYYY → 粒元日窗展开）、带空格引号列名（"Academic Year"/"Examination Date"）、引号表名；渐进遮蔽防重复计数 |
| 守卫重演 | `anchor_coverage`：token 粒锚的覆盖域按粒元日窗并集/包络现算，VARCHAR 时间戳截 [:10]，SCD-2 NULL 终止列读开区间 [vf,+inf)（D7）；新增 `p2_realization_days`（hull=窗∩[hmin,hmax] 日历日，strict=窗∩标记日）；`replay_svw` 条款 (iv) 新模式 `window_realization_symdiff`；`replay_oov` 对子豁免规则（见 §4 裁定 2）；V6b AM(iv) 新模式见证重演（窗对防伪 + 实现集重算 + 判别日/计数核账）；`den_closure`/`allowed_tables` 扩到 G_v 登记的度量节点、谓词节点与路由 hop 表（一律 re-query G_v，不信证书）；scope 字面量取 q.scope 值 |
| V4 | p2 hop 行逐字段重演（metric/leg/hop_seq/节点对/join_keys/via_table）+ I3 邻接改为逐腿 hop 树可达性（老轨口径链检查保留） |
| **V5 完整披露重演（C5，首次非空策略集）** | `_check_V5_p2`：Π 独立重算（掩码策略=受保护列被呈现〔attribute 值读 / roster 原值行〕、k 策略=其节点的实体粒呈现、time_floor=时间轴报表细于下限的请求）与证书逐一对账；**k/格条款**：对 lattice_levels 链上证书粒度之前的每一细级独立重算 SUPPMIN（`_p2_min_cell`：从 gov_measure_def 谓词 + 路由 hop + 粒度格边〔band CASE/分组列/decade 派生〕+ 推导窗 + scope-drop 键自装 SQL 对 D 群查），细级必须非法、认证级必须合法（'all'+k_exempt_top 按登记豁免）——认证粒度必须是 ≺ 最小合法级；**掩码条款**：μ* 覆盖 mask_class 且产出 SQL 携对应掩码变换签名（year_only=substr(,1,4)、year_month=substr(,1,7)、generalize_last_component=regexp_extract '([^,]+)$'），呈现降级必为 REWRITE；**时间下限条款**：δ.g=登记下限且 dec=REWRITE；REFUSE(DB) 的条款重演归 V6b 见证（阻断策略在册 + SUPPMIN 笔录重执行低于阈值 + U_min=∅ 断言），V5 钉 Π 与注解。老域（aibuy/email applied_tables 版式）替换前逻辑原样保留 |
| `runall.py`（**新增**） | 双语料批量校验驱动（old51 + p2 × 默认/严格两轨），校验器侧文件，只 import chk |

## 3. 首次触发的披露路径说明（任务要求项）

pilot2 之前，D_v 非空域（aibuy/email）从未在金标上触发披露分支（Π 恒空、Γ 单点、μ*=∅）。本次三条 C4 路径首次被真实数据走通，且每条都有校验器的独立重演闭环：

1. **披露门 → DISCLOSURE-BLOCKED（C4 行 12–13 U_min=∅，S-M2 ⊤_M 封顶）**：CODE-Q7 / TH-Q5 / TH-Q6。
   名录/原值行呈现刚性 + 实体节点掩码/k 策略触及 → adapter 预判 `Disclosure.block` 携 DB 见证
   （blocking_policy_ids=掩码∪k、实体粒 SUPPMIN 笔录 observed=1 < k∈{5,10}、u_min_empty）；
   core 行 12–13 在守卫序 OOV→AM→MC 之后落 ⊥_DB。校验器 V6b 执行笔录 SQL、比对阈值、
   核 U_min 断言；V5 重算 Π（CODE=\[pi1,pi2\]、TH=\[pi1,pi2,pi3\]）。
2. **粒度爬升（引理 4.16 Legal(ℓ) 逐级求值 + SelectMin 最小合法级）→ REWRITE(granularity_rollup)**：
   CODE-Q4（user→reputation_band，band 胞 13/43/52/21 ≥ k=5）、CA-Q5（school→district→county，county=98≥10）、
   TH-Q3（patient→cohort→sex→all 三级连败后顶级豁免，链式小胞见证）、DEB-Q5（Segment→all，LAM×EUR=16<k=20 —— v2 治下
   k 阈值 10→20 的 RC-7×RC-8 交互位点）、CODE-Q5（time_floor：day→month 时间轴下限）。
   编译器逐级 SUPPMIN 探针入笔录；校验器 `_p2_min_cell` **不读笔录**、自装胞普查 SQL 重算每级 min cell，
   同时压最小性（细级已合法而证书仍上卷 → REJECT）与合法性（认证级 min<k → REJECT）两个方向。
3. **掩码闭包 μ*（引理 4.15）→ REWRITE(mask 呈现降级)**：CODE-Q6（Location 'Durham, UK' → 'UK'，
   generalize_last_component，carry 闭包沿 OwnerUserId 在种子具备）、TH-Q4（Birthday 1934-02-13 → '1934'，
   v2 掩码强度 year_month→year_only 的版本语义变更叠加）。编译器把掩码义务落 `mask_obligations` →
   μ* 入证书 + 掩码变换直接编译进产出 SQL；校验器 V5 对 μ* 覆盖 + SQL 掩码签名双查，V0 把 μ*≠id 计入
   REWRITE 合法收窄轴。

## 4. 移植期裁定（两侧一致实现、非规范字面）

1. **AM(iv) 审计模式**：p2 的锚对相容审计是**窗限实现集**对称差（`window_realization_symdiff`，对请求窗对求值：hull 锚=窗∩包络日历日、strict 锚=窗∩标记日、token 窗不参与），非老轨的全集 `symdiff_audit`。EF2-Q6 实测：当日比赛日实现 {2013-12-01} vs 快照日实现 ∅。
2. **对子先于单腿**（承 pilot2 建仓裁定"审计先于逐腿覆盖裁定"）：跨锚 svw 比率的实现集失配不化归单腿 OOV——编译器 `am_precheck` 在覆盖前出条款 (iv) 见证；校验器 `replay_oov` 对同一对子角色按对级判空（两腿同空才是 OOV，混合即审计辖区），否则 EF2-Q6 会被 ¬OOV 前置误杀。
3. **roster 触及集**：raw_rows 呈现触及实体节点的 `mask`+`k_threshold` 策略；`present_only`（code.pi3 decade_band）只辖单属性呈现——与建仓路径 B 的封顶集一致（否则 Π 对不上冻结金标结构）。
4. **`range_request` 即声明窗**：登记行把窗形交给题面 → 独立推导如实弃权（declared/declared-override 标注），严格轨 10 题 fail-closed 是设计后果不是缺陷。
5. **SCD-2 证书 coverage_mode 落 G_v 声明值**（CA 锚登记 hull）：在效判定仍是 D7 的 vf≤d<vtc 成员探针，但 α 呈现与 D3"mode 是锚的版本化属性"对齐（校验器对声明重演，证书不得自造 mode）。
6. **空策略集域的 D5 语义**：gov_disclosure_policy 在库存在但该域零行（fin/card/f1/ef2/w1）按"无策略登记域"处理 → 证书标 `ungoverned-disclosure`（C5 G7 absent-vs-empty 的移植取值；校验器 governed 判据=策略行非空，两侧一致）。
7. **（2026-08-07 追补，R4-TC-R4-3b）`window_realization_symdiff` 不可重演即 fail-closed**：`chk.py` 条款 (iv) 里 `p2_realization_days` 返回 `None`（token 粒 / 窗跨度 >400 天 / 表列缺失，即审计辖域之外）的分支原先只 `details.append` 后**落到 PASS**——等于把"重演不了"当成"重演通过"，与同一函数 `interval_containment` 分支（返回 `(None, "(iv)", …)`）自相矛盾，也与本条款开头刚强制的 C3 §2 不变式（异锚行不得以 trivial 成员交差）不一致。现改为 `return (None, "(iv)", "realization audit not applicable: window/granularity outside the audit's domain")`；两处调用点对 `passed is None` 本就 fail-closed。**回归证据**：改前/改后 `runall.py all` 逐值相同（p2 默认轨 60/60、严格轨 50/60、window_source 分布一致；old51 46/51 与 45/51 亦不变），`forge_p2.py` 仍 10 基座 ACCEPT + 30 伪造全拒；老 `forge.py` 的 FAIL 清单（3 基座 16 伪造中 7 例 MISMATCH）改前改后**逐行相同**，属退役企业轨既有状态，与本次改动无关。本稿全部证书学数字不受影响。

## 5. 诚实边界

- **ND-4（治理知情臂原协议重挂）不在本任务内**，预注册仍待执行；本报告的"校验"是证书学意义的 V0–V6c，不是评测臂。
- 严格轨 50/60 的 10 题按 §4 裁定 4 fail-closed；若后续给 range_request 语义补机器可读窗形登记列，可再收窄。
- 变异电池 13 例覆盖每类新检查各≥1 落点，非逐题×逐字段全笛卡尔；老 forge 三基座未对 p2 重建基座（p2 电池以真证书变异替代）。
- `_p2_min_cell` 的胞普查与编译器 `legal_at` 是同一登记语义的两次独立实现（互不 import、结构不同：校验器自装 SQL 且不读证书笔录），但同语义双写的"共同祖先"是 gov_* 登记本身——这正是 C5 允许的公共输入面（要求 5.8 约束的是实现工件不相交，ci_check 持续机检）。
- 未走到的防御路径（无金标实例，代码存在但未被 60 题激发）：ver(T)↑ 前治理期 OOV、pinned_version_uncommitted、p2 别名缺失 MC(i) 的证书侧（编译器路径在、校验器对该形未过题）；F1-Q4 delta 期窗若遇 hull 裁剪，本移植按 REWRITE 处理而建仓路径 B 判 OOV——60 题无此位点，留档待裁。
- macOS AppleDouble `._*` 文件会污染目录聚合 sha，本报告一切 sha 已按 `[A-Za-z]*.json` 过滤口径计（§0 表内注明）。

## 6. 复跑清单

```bash
cd "/Volumes/SSD 1/explore_opportunity_cc/impl"
python3 asof_compiler/acceptance.py            # 老 51：gold/legacy/良构
python3 asof_compiler/acceptance_pilot2.py     # 新 60：gold+子型+rewrite kind/良构
python3 asof_verifier/runall.py                # 两语料 × 默认/严格 四轨 ACCEPT 计数
python3 asof_verifier/forge.py                 # 老伪造族 16 全拒
python3 asof_verifier/ci_check.py              # 零共享红线
```
