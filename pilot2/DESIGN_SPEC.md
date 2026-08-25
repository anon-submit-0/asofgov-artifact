# pilot2 · 公开证据基座设计规范（DESIGN_SPEC）

> 状态：设计冻结候选 v1.0（2026-08-04）。本文件是 pilot2 建库的唯一规范；建库工件落 `pilot2/`，与旧 `pilot/` 并存互不改写。
> 裁定依据：【作者裁定】论文证据基座只用公开渠道公开数据集；企业私有数据只作动机，不进结果表/图/artifact。
> 科学依据：B6 实测（`pilot/GOVERNANCE_ARM_RESULT.md`）——现公共轨绑定表自带 `select_expr`/`where_expr`、锚表自带 `snapshot_table`+`valid_from/valid_to`，治理知情臂 0/20 全对（退化查表）；企业轨 17/31 反差于素基线。**本规范的第一设计判据 = 非退化（§3）**。
> 冻结规范：`theory/C3_bitemporal_semantics.md`（双时态语义）、`C4_maximal_legal_rewrite.md`（披露门与最大合法改写）、`C5_pointintime_certificates.md`（时点证书）只读引用；实现工件 `impl/asof_compiler` / `impl/asof_verifier` 零共享红线延续。

---

## 0. 数据来源、出处与规模声明

| 源 | 本地路径 | 许可/出处 | 用法 |
|---|---|---|---|
| BIRD dev（dev_20240627） | `/Users/loctek/bench_data/dev_20240627/dev_databases/` | bird-bench.github.io，CC BY-SA 4.0，公开可下载 | 8 库主源；只读抽取到 pilot2 各域 warehouse |
| Spider dev | `/Users/loctek/bench_data/spider_data/`（database 目录符号链接已失效；`spider_val.parquet` 仅含题目无库内容） | Yale Spider，CC BY-SA 4.0 | 1 库（world_1）；表内容经既有本地抽取件 `pilot/public/warehouse.duckdb::country_v2026_01`（239 行，即 Spider dev 原始数据）承接，免联网；如需全库可另从官方渠道补 |

- **P6 规模条款**：最大实测规模由 `financial.trans` = **1,056,320 行**真实公开数据承担（≥10^5 达标，零合成）。全基座真实行数合计 ≈ 3.85M（§1 表逐库列明）。
- **authored 条款**：一切合成/扰动内容（world_1 历史行、各库治理版本轴、财务口径变更等）逐行携 `authored: true` 标注 + 生成规则 + 随机种子，**不计入**"真实数据规模"任何声明；论文如实分列 real / authored。
- 本文件全部实测数字由 §8 探针清单（P-1…P-15）SQL 复算，无手抄。

---

## 1. 选库（9 库，落在任务书 8–10 区间）

| # | domain（簇名） | 源 | 表数 | 实测总行数 | 最大表 | 时间承载列（实测跨度） | 选择理由（一句话） |
|---|---|---|---:|---:|---|---|---|
| 1 | `financial` | BIRD | 8 | 1,079,680 | trans 1,056,320 | trans.date 1993-01-01→1998-12-31；loan.date；account.date | **P6 规模旗舰**；日粒连续事件流，天然月窗；双路径口径比率实测 15.2×（P-3）；64/77 区当月零放贷（P-14）承载 MC(ii) |
| 2 | `card_games` | BIRD | 6 | 803,445 | legalities 427,907 | sets.releaseDate 1993-08-05→2021-03-19；rulings.date 2004-10-04→2021-02-05 | **running example 落点**：2017-02 裁定 2,161 条而当月零套牌发行（P-5/P-6），同月分母缺失结构与 rma SKU536-EOL 同构 |
| 3 | `codebase_community` | BIRD | 8 | 740,646 | postHistory 303,155 | posts.CreaionDate(原库拼写) 2009-02-02→2014-09-14；votes.CreationDate 2010-07-19→**2011-05-01**（P-11，天然窄锚） | **披露旗舰一**：users 携 DisplayName/Location/AboutMe/Age 真实 PII 形态列；votes 窄 hull 是"天然截断锚"，跨锚覆盖差异非人造 |
| 4 | `formula_1` | BIRD | 13 | 514,287 | lapTimes 420,369 | races.date 1950-05-13→2017-11-26 | **版本轴旗舰（关 RC-8）**：2009→2010 积分制真实变更（冠军单场 10→25 分，P-4）给跨版本语义变更以真历史原型；Brawn 车队 2009 有 34 条参赛、2010 为 0（P-4）= 实体 EOL |
| 5 | `debit_card_specializing` | BIRD | 5 | 423,050 | yearmonth 383,282 | yearmonth.Date 为 YYYYMM 月粒 token，21 个月 201112→201311（P-8） | **粒度/口径库**：月粒 strict_member 锚承载 AM(iii) 窗-粒度不可表达（全基座唯一）；CZK/EUR 双币混算实测 13.4×（P-9）复刻双路径口径模式 |
| 6 | `european_football_2` | BIRD | 7 | 222,796 | Player_Attributes 183,978 | Match.date 2008-07-18→2016-05-25；Player_Attributes.date 197 个离散快照日（P-7） | **strict_member 日期集锚**的真实原型（quality_voc 周锚的公开镜像）；2015-06 全联盟零比赛（P-13）承载 MC(ii)；双锚审计承载 AM(iv) |
| 7 | `california_schools` | BIRD | 3 | 29,941 | schools 17,686 | schools.OpenDate/ClosedDate 1850→2017，5,694 行有闭校日（P-10） | **真实 SCD-2 区间锚**（OpenDate/ClosedDate 点窗在效判定，as-of 2015-01-01 在效 10,629 校，P-12，镜像 NX-Q4 人口 126）；frpm 单一学年 2014-2015 快照（P-10）= 天然窄覆盖；K-12 vs Ages 5-17 双口径列并存于原始数据（P-10） |
| 8 | `thrombosis_prediction` | BIRD | 3 | 15,952 | Laboratory 13,908 | Laboratory.Date 1981-01-27→1999-03-04；Examination Date 1989-04-18→1998-04-17（P-15） | **披露旗舰二（医疗）**：Birthday/Diagnosis 天然敏感列，掩码/粒度/小胞条款全部有真实语义；双 hull 错位承载 AM(iv) |
| 9 | `world_1` | Spider | 1 表承接 + authored 历史 | 239 真实 + 20,076 authored（84 月 × 239 国） | country_history(authored) | authored 月度 effective_month 2020-01→2026-12 | **血缘簇**：与旧公共轨 PUB-W 连续，Spider+BIRD 双源主张成立；239 行真实国别数据 + 显式规则合成历史（§6.2），全部 authored 标注 |

- 未入选说明：superhero / toxicology / student_club 无时间列或规模过小且无独有现象；thrombosis 虽 <10^5 但披露语义不可替代；california_schools <10^5 但真实 SCD-2 区间锚不可替代。规模主张由 financial/card_games/codebase/formula_1/debit 五库（均 >4×10^5）承担。
- 簇数 = **9**（≥8 达标，改善 bootstrap 区间宽度；对照 B6 的 6 簇）。
- 可选扩展位（不承诺）：Spider `wta_1`（rankings 带 ranking_date），须联网官方重下 database 目录后按本规范增补为第 10 簇；不可得则维持 9 簇。

---

## 2. 现象组合：冻结规范全现象 → 库映射

### 2.1 总矩阵（●=承载题目，○=种子具备但不出题）

| 现象（冻结规范坐标） | fin | card | code | f1 | debit | ef2 | ca_sch | thromb | w1 |
|---|---|---|---|---|---|---|---|---|---|
| 版本轴 ≥2 已提交版本（C3 §2.3/A3） | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| 跨版本语义变更（关 RC-8） | ●status集 | ●轮替表 | ●分母排除 | ●积分映射 | ●k阈值 | ●平局权重 | ●默认口径 | ●掩码强度 | ●人口重定基 |
| 有效时间锚 hull（C3 定义3.3） | ● | ● | ● | ● | ○ | ○ | ○ | ● | ● |
| 有效时间锚 strict_member（裸日期集/区间） | ○ | ○ | ○ | ○ | ●月集 | ●快照日集 | ●SCD-2区间+单学年 | ○ | ○ |
| OOV 覆盖缺口（定义3.14；覆盖域不写入种子） | ●1999-06 | ○ | ○1992? 不出题 | ●1949-05 | ●201312 | ●快照间隙 | ○ | ○2000-06 备选 | ○ |
| AM(i) 改锚/未注册锚（定义3.7/3.8(i)） | ○ | ○ | ○LasActivityDate | ○ | ○ | ○ | ●“按特许授权日” | ○ | ○ |
| AM(ii) 跨窗（rma_q6 直系） | ●5月/4月 | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ●5月/4月 |
| AM(iii) 窗-粒度不可表达（定义3.8(iii)） | ○ | ○ | ○ | ○ | ●周窗×月锚 | ○ | ○ | ○ | ○ |
| AM(iv) 锚对不相容审计（定义3.8(iv)） | ○ | ○ | ○votes窄hull | ○ | ○ | ●比赛日×快照日 | ○ | ○检查日×化验日(素材) | ○ |
| MC(i) 路由/绑定缺失（定义3.16(i)） | ○ | ●collector_premium | ○ | ○ | ○price_margin | ○ | ○ | ○ | ○ |
| MC(ii) 同窗分母空（μ_den≤0，探针专属） | ○64区 | ●2017-02 主例 | ○ | ●Brawn 2010-05 | ○ | ○2015-06 | ○ | ○ | ○ |
| caliber 路由 + 双路径比率公开复刻 | ●15.2× | ○ | ●采纳率两分母 | ●两路径 | ●13.4× | ○ | ●K12/5-17 | ○ | ●洲/全球 |
| 披露策略 D_v 非空（C4 定义4.3） | – | – | ● | – | ● | – | ● | ● | – |
| ungoverned-disclosure 诚实标注（D5） | ● | ● | – | ● | – | ● | – | – | ● |
| DISCLOSURE-BLOCKED 拒答（S-M2） | – | – | ●1 | – | – | – | – | ●2 | – |
| REWRITE 粒度上卷（D2(i)+A4.3） | – | – | ●2 | – | ●1 | – | ●1 | ●1 | – |
| REWRITE 掩码呈现降级 | – | – | ●1 | – | – | – | – | ●1 | – |
| REWRITE hull 边缘裁剪（定义4.8(ii)豁免） | ●1 | ●1 | – | ●1 | – | ●1 | – | – | ●1 |
| 离对角显式钉版本（S-V + C5 offdiag） | ○ | ○ | ○ | ●1 题 | ○ | ○ | ○ | ○ | ○ |
| 多期 delta（推论3.17′ 期序×守卫序） | ○ | ○ | ○ | ●1 题 | ○ | ○ | ○ | ○ | ○ |

### 2.2 逐库现象细则（含实测锚定）

**1) financial** — 锚：`trans.date`（日粒快照锚，hull 1993-01-01→1998-12-31，P-2）、`loan.date`、`account.date`。版本轴：v1 问题贷款口径 `status∈{B,D}`，v2 变更为 `{D}`（核销政策后口径，authored，flip 实例建库时以两版本同题异值钉定）。双路径比率复刻（rma 16.2%vs3.8% 的**模式**）：`penalty_trans_rate` 1997 全年 caliber-aware（分母=窗内全部交易，经 account 路由 scoped）= **0.1431%**，caliber-blind（分母=受罚账户自指交易集）= **2.1743%**，**15.2×**（P-3；方向与 rma 相反——blind 高估，如实报告，模式=同一 (m,s,T) 两路由产出量级差）。AM(ii)：镜像 rma_q6 祈使句"分子取 1997-05、分母取 1997-04"。OOV：as-of 1999-06（hull 右外）。REWRITE hull 裁剪：请求窗 1998-07→1999-06 裁至 1998-12-31，证书披露被裁端点。MC(ii) 素材（○）：1997-05 全行 16 笔放贷、64/77 区零放贷而同月交易活跃（样本区 234 笔交易，P-14）。披露：D_v=∅，证书 `ungoverned-disclosure`。

**2) card_games** — 锚：`sets.releaseDate`（发行快照锚）、`rulings.date`（裁定快照锚）（P-5）。**running example**：`ruling_intensity = 同月裁定数 / 同月新发行印刷数`，as-of 2017-02：分子 2,161、分母 0（当月零套牌发行，P-6）→ MC(ii)，§5 详述。MC(i)：注册 metric `collector_premium`（保留卡溢价）路由 `dst_caliber='none'` reference-only（无成本侧数据）。版本轴：v1/v2 "当前轮替合法套牌清单"变更（authored，镜像真实 Standard 轮替）。REWRITE hull 裁剪：裁定窗请求 2020-10→2021-06 裁至 2021-02-05。披露：ungoverned。

**3) codebase_community** — 锚：`posts.CreaionDate`（**原库如此拼写**，hull 2009-02-02→2014-09-14，P-11）、`users.CreationDate`、`votes.CreationDate`（hull 2010-07-19→**2011-05-01**，天然窄锚，P-11——vote 类指标 2011-05 后覆盖真空，天然 OOV/审计素材，非人造）。**披露旗舰**：D_v 含 ≥3 条策略——π1: `users.{DisplayName,Location,AboutMe}` 掩码 `generalize`，carry 闭包沿 `posts.OwnerUserId→users.Id`（`posts.OwnerDisplayName` 为携出列）；π2: 用户级统计粒度下限 `reputation_band`（实体格 user→reputation_band→all 三级）+ 小胞 k=5；π3: `users.Age` 仅十岁段呈现。DISCLOSURE-BLOCKED×1："列出 2013-06 前十答题者的 DisplayName+Location 原值"（刚性呈现属性被闭包送 ⊤_M → DB）。REWRITE 上卷×2：用户级→声望段（k=5 小胞探针实测驱动）；日粒→月粒。REWRITE 掩码×1：Location 泛化呈现作答。caliber 双分母：`accepted_rate` aware=采纳答案/窗内新提问 vs blind=采纳/窗内答案（两值同 SQL 框架可复算）。版本轴：v2 分母排除社区共有帖（CommunityOwnedDate 非空）。AM(i) 素材：题面点名"按 LasActivityDate 开窗"（未注册锚引用）。

**4) formula_1** — 锚：`races.date`（hull 1950-05-13→2017-11-26，P-4）。**版本轴旗舰（关 RC-8）**：治理版本 v1 积分口径 `points_map_pre2010`（10-6-4-3-2-1）commit 于 t1，v2 `points_map_2010`（25-18-15-…）commit 于 t2（合成 commit 时戳协议见 §6.1）；`driver_season_points` 经 `results.positionOrder × 在位 points_map` 重算——同一 (σ=2009 赛季, 窗) 在 T<t2 与 T≥t2 两个声明时点下答案不同（真实原型实测：冠军单场 10 vs 25 分，P-4），**同题双 T 的 ANSWER 对是 RC-8 的正面证据**；"用最新口径回算 2009"不带显式钉 = GOLD-1 禁形（对角线缺省下不可表达），带显式钉 p=v2 = 合法离对角 ANSWER + 证书 offdiag 标记（C5 V1 核验）——**离对角题 1 道**。MC(ii)：Brawn 车队 2009 参赛 34 条、2010 零条（P-4），`points_per_entry`(brawn, 2010-05) 同窗分母空。OOV：as-of 1949-05（hull 左外）。多期 delta×1：2009 vs 2010 车手积分差（两期均可绑定，推论 3.17′ 声明期序）。REWRITE hull 裁剪：窗 2017-10→2018-03 裁至 2017-11-26。披露：ungoverned。

**5) debit_card_specializing** — 锚：`yearmonth.Date`（**月粒 strict_member 集**：21 个月 201112→201311，P-8）、`transactions_1k.Date`（仅 2012-08-23→26 四日，P-8）。**AM(iii) 全基座唯一实例**："2013-03-04 起一周"的周窗请求落在月粒锚上（周⋢月，W∉W_g^cmp，C3 定义3.8(iii)）。双路径口径复刻二：`avg_consumption` 2013-08 per-currency aware CZK=15,626.14 / EUR=1,166.15 vs blind 混币合并（13.4× 失真，P-9）。OOV：as-of 2013-12（201312 ∉ 月集，strict_member 判空）。披露：D_v 含客户级消费 k=20 小胞 + 实体格 customer→Segment(SME/LAM/KAM)→all；REWRITE 上卷×1（客户级→Segment）。版本轴：v2 将 k 阈值 10→20（**披露策略也是版本内容**：同题在 v1 治下 ANSWER、v2 治下 REWRITE——RC-7×RC-8 交互实例）。MC(i) 素材：`price_margin`（无成本数据路由 none）。

**6) european_football_2** — 锚：`Player_Attributes.date`（**strict_member 快照日集**，197 个离散日 2007-02-22→2016-07-07，P-7；quality_voc 周锚公开镜像）、`Match.date`（hull 2008-07-18→2016-05-25）。OOV：as-of 落在快照间隙（strict_member 判空；建库时从 197 日集的实测空隙钉定具体日期）。AM(iv)：`rating_weighted_win_rate` 的比赛日锚×快照日锚做锚对相容审计（两锚有效域对称差实测非空 → 审计失败见证）。MC(ii) 素材：2015-06 全联盟零比赛（P-13，休赛月），窗内快照 2,184 条仍在（另一锚有事实而分母锚空）。版本轴：v2 `win_rate` 平局权重 0.5→0。REWRITE hull 裁剪：窗 2016-03→2016-08 裁至 2016-05-25。披露：ungoverned。

**7) california_schools** — 锚：`schools.OpenDate/ClosedDate`（**真实 SCD-2 区间锚**，vf≤d<vtc 点窗在效判定，5,694 行有闭校日，P-10；as-of 2015-01-01 在效人口 10,629，P-12——NX-Q4 人口 126 的公开镜像）、`frpm."Academic Year"`（单元素日期集 2014-2015，P-10，strict_member 窄覆盖）。双注册口径：`free_meal_rate` K-12 版与 Ages 5-17 版并存于原始列（全域实测 0.49974 vs 0.49904，P-10；全域几乎不分离、实体粒度分离——如实报告，其角色是**路由选择**而非量级差旗舰）。版本轴：v2 默认口径 K-12→5-17 切换（语义变更 flip 实例）。AM(i)：题面点名"按特许授权日期开窗"（治理图查无此锚 → 未注册锚引用，定义 3.7 约定）。披露：D_v 含校级小胞 k=10 + 实体格 school→district→county；REWRITE 上卷×1（校级→区级）。

**8) thrombosis_prediction** — 锚：`Laboratory.Date`（hull 1981-01-27→1999-03-04，P-15）、`Examination."Examination Date"`（hull 1989-04-18→1998-04-17）。**披露旗舰二（医疗）**：π1: `Patient.Birthday` 掩码 `generalize`（仅出生年）；π2: 患者级化验结果粒度下限 cohort（sex×出生十年段）+ k=10；π3: `Diagnosis` 自由文本仅大类呈现。DISCLOSURE-BLOCKED×2："列出患者 ID+生日+诊断原值"、"列出 1997 年异常化验患者名单（患者级行呈现）"。REWRITE 上卷×1（患者级→cohort）+ 掩码×1（生日→年）。AM(iv)：检查日锚×化验日锚双 hull 错位审计（1989-04-18 前化验有、检查无）。`abnormal_lab_rate` 比率型（异常化验/窗内全部化验，routed）。版本轴：v2 掩码强度 partial→generalize。

**9) world_1** — 承接旧 PUB-W 簇（血缘），**全面去退化重铸**：authored 月度历史表 `country_history(code, effective_month, population, gnp, authored=true)` 2020-01→2026-12（§6.2 生成规则），快照锚 `effective_month`（hull 2020-01→2026-12）。版本轴：v2 于 2026-07 亚洲人口重定基 ×1.06 半上取整（承旧轨语义变更，但**登记表不再携带 snapshot_table/valid_from/valid_to**——版本差异体现为 `gov_measure_def` 中 rebase 规则行的版本戳 + 数据行的 effective_month，解析须过 ver(T)）。`population_share = 洲人口/全球人口` 比率 + 洲/全球两级路由。AM(ii)：祈使句"分子取 2026-05、分母取 2026-04"。REWRITE hull 裁剪：窗 2026-10→2027-03 裁至 2026-12。披露：ungoverned。

### 2.3 全局覆盖核对（对任务书清单逐项）

- 版本轴：9/9 库 ≥2 已提交治理版本；跨版本语义变更 9 处（每库 1 处，其中 formula_1/financial/world_1/ca_schools 四处配**同题双 T 异值**的 ANSWER 对作 flip 见证）→ **RC-8 关闭**。
- 有效时间锚：hull 与 strict_member 两 mode 均有多库实例；OOV 覆盖缺口 4 题 + 版本轴缺位素材（T<t1 归 OOV，G7）种子具备。
- 跨锚错配 AM：四种见证形态 (i)(ii)(iii)(iv) 全部有题（5 题：ca_sch/fin/w1/debit/ef2）。
- caliber 路由：9 库全配路由行；**双路径比率公开复刻 2 处实测**（financial 15.2×、debit 13.4×，均可复算；rma 4.2× 的模式而非数据）。
- 缺口径 MC 两型：MC(i) 1 题 + 种子素材 2 处；MC(ii) 2 题 + 素材 2 处（探针专属，元数据零记载）。
- 披露策略带实例：4 库 D_v 非空（每库 ≥3 条 policy，policy_ids 非空）；掩码闭包（carry 闭包沿声明 join 边）；粒度格非退化（≥3 级实体轴 ×2 库 + 时间轴 day→month→…；上卷改变小胞判定结果，见证对实测）；DISCLOSURE-BLOCKED 3 题（≥2 达标）；REWRITE 粒度上卷 5 题（≥3 达标）→ **RC-7 关闭**。其余 5 库 `ungoverned-disclosure` 诚实标注（D5）。
- hull 裁剪 REWRITE：5 题。
- 离对角/多期：各 1 题（formula_1）。

---

## 3. 非退化规则（本规范的宪法条款）

### 3.1 绑定登记表 schema 法（写死）

pilot2 的 gov_seed 固定为 10 张登记表：`gov_semantic_graph_version` / `gov_semantic_node` / `gov_metric` / `gov_measure_def` / `gov_metric_alias` / `gov_caliber_routing` / `gov_valid_time_anchor` / `gov_temporal_binding` / `gov_granularity_edge` / `gov_disclosure_policy`。

**禁止字段（黑名单，ci 硬闸）**：任何登记表不得含
`select_expr` / `where_expr` / `sql` / `sql_template` / `expr` / `filter_sql` / `snapshot_table`（时间解析直指物理快照表）/ 快照锚与日期集锚的 `valid_from`,`valid_to` 覆盖区间字面量 / `gold_*` / 点名题目裁定类别的 note 文本。
**字符串值级禁令**：一切种子字符串值不得匹配 `/\b(SELECT|FROM|WHERE|GROUP BY|JOIN)\b|SUM\(|COUNT\(|AVG\(/i`。

**允许字段（白名单语汇）**：标识符与引用（`*_id`、node/anchor/metric/policy 引用）、**列名 token**（`effective_col`、`vf_col`/`vtc_col`、join 键列名）、闭枚举 token（`anchor_type∈{snapshot_effective_date, scd_type2, date_set}`、`coverage_mode∈{hull,strict_member}`、粒度 token、`rule_id`（如 `same_valid_time_window`）、measure 词（`count` | `sum:<col>` | `filter:<pred_id>`））、结构化谓词原子（`gov_measure_def.pred`: 三元组 (列名, op∈{=,in,<,≥}, 值集)——口径定义本身是治理内容，以关系原子而非可粘贴 SQL 存在）、披露参数（γ 粒度 token、k 整数、mask_class）、commit 元数据（`graph_version`、`committed_at` 真时戳、`commit_seq` 平局细化、`change_note` 人类语义描述）。

**覆盖域不物化公理**：锚的覆盖域 Cov_v(a) 是数据的函数——hull 锚 = min/max(effective_col)，strict_member 锚 = distinct 日期集/区间并——**只能从 D 现算，任何登记表不得记载**。（旧公共轨 PUB-*-05 的 OOV 标签可从锚表 `valid_from/valid_to` 直读，这是 0/20 退化的第二根源，与 select_expr 并列。）scd_type2 锚登记 `vf_col/vtc_col` 列名（合法：这是解释函数的指针，区间本身仍在 D 中）。

### 3.2 非退化的形式判据（可机检）

**判据 ND-1（标签的元数据不可决定性）**：对每道金标 ∈ {REFUSE(OOV/AM(iv)/MC(ii)), REWRITE(小胞驱动上卷)} 的题 q，构造**见证对**：两个与全量种子逐字节一致但内容不同的数据实例 D₁,D₂（如向分母窗插入/删除一行、向 effective_col 增删一个日期），使编译器裁定 label(q,G,D₁) ≠ label(q,G,D₂)。见证对由建库脚本 `ci/witness_pairs.py` 物化并断言——**证明把治理内容整层喂给任何无执行系统，该题标签在信息论意义上不可判**。（AM(i)(ii)(iii) 与 MC(i) 的标签可由元数据+题面判定——这是理论本身的刻画（命题 3.18 前三行不触 D），不视为退化；退化的定义是**本可需要探针的判断被元数据代答**。）
**判据 ND-2（禁字段闸）**：`ci/nondegeneracy_gate.py` 对全部 gov_seed 做黑名单字段名 + SQL 片段正则扫描，零命中方可绿灯。
**判据 ND-3（干扰行密度）**：每张登记表含不在任何金标解析路径上的兄弟行（近似别名、被 v2 取代的 v1 行、reference-only 路由、失效绑定），全库干扰行占比 ≥30%——"grep 种子撞词"策略在版本过滤缺失时命中错行。
**判据 ND-4（B6 复测预测，非闸门）**：治理知情臂协议原样重跑于 pilot2 公共轨，预注册预测其错误率 >0%（对照旧公共轨 0/20）；此为设计有效性的事后检验。

### 3.3 机理论证：治理知情 LLM 为什么仍难（≥2 步间接性论证）

把 pilot2 任一域的整层治理内容 + 题面交给单回合无执行的 LLM，落出正确 SQL/标签须走通：

1. **版本解析**（1 步）：T → ver(T)，经 `gov_semantic_graph_version` 的 (committed_at, commit_seq) 全序；每库 ≥2 版本且登记行全部双版本并存（无 `is_current` 捷径字段），取错版本即撞 ND-3 干扰行。
2. **别名→度量解析**（1 步）：题面自然语（如"问题贷款率"）→ `gov_metric_alias` → metric_id，**别名映射随版本变**（语义变更库中同一表面词在 v1/v2 指向不同 measure_def）。
3. **度量→腿→口径装配**（1–2 步）：metric → (num_node, den_node) + `gov_caliber_routing`（via 对象 + join 键列名 + 归因对齐）+ `gov_measure_def` 谓词原子——须自行把关系原子**组装**为 SQL，无一处可粘贴。
4. **腿→锚→窗推导**（1–2 步）：`gov_temporal_binding` 给锚引用与 rule_id；`gov_valid_time_anchor` 给 effective_col/粒度/coverage_mode；ω_r(T) 按规则+粒度**现算**（种子不存窗）。
5. **数据探针（无执行则不可判）**：OOV 覆盖判空、MC(ii) 分母质量 μ_den≤0、披露小胞 k 计数、AM(iv) 锚对对称差审计——四类判断是 D 的函数（C3 命题 3.18 判定程序的数据触达行）。**B6 已实测此缺口**：17 个残余错误中 13 个（76.5%）恰是"某 valid-time 窗内有没有行"的两向误猜；编译器以 `_den_present()` 探针真跑而胜出。

步骤 1–4 构成 **≥2 步（实际 4–6 步）符号间接解析**，每步有版本过滤与干扰行；步骤 5 对四类标签判断**原则上**要求执行。两层合起来即"治理内容整层喂给 LLM 也无法退化为查表"的机理保证：旧公共轨的失败模式（绑定行→粘贴、锚行→查区间）在 schema 法下**不可表达**。

### 3.4 题面规格与泄漏纪律（承 B6 协议 A2）

`questions.json` 评测可见字段 = {qid, domain, question_zh, as_of, scope tokens, 题面显式声明的跨窗/改锚/钉版本字段, 披露语境 ctx(role)}；金标侧字段 = {expected_kind, refusal_reason, refusal_subtype, gold_sql, gold_value, windows, windows_note, notes} 一律不入提示（A2 式逐字段泄漏比对沿用）。`windows` 仍为问题规格一等字段（C3 A5 的 ω_r 显式呈现），但**校验器窗推导只准依据 G_v 治理表 + D 数据 + q 的非窗字段**（冻结工程纪律③），推得后与证书 α 比对；编译器与校验器零共享实现（`ci_check.py` import 零交集断言延续，红线②）。

---

## 4. 题集预算（60 题，硬界 55–65）

### 4.1 金标分布（目标 ANSWER≈55% / REWRITE≈20% / REFUSE≈25%）

| 金标 | 数 | 占比 | 构成 |
|---|---:|---:|---|
| ANSWER | 33 | 55% | 含：跨版本同题双 T 对 ×4 对（8 题，RC-8 flip 见证）、双路径 caliber-aware 值题、原子/比率常规、离对角显式钉 ×1、多期 delta ×1 |
| REWRITE | 12 | 20% | 粒度上卷 ×5（code×2, debit, ca_sch, thromb）＋ hull 裁剪 ×5（fin, card, f1, ef2, w1）＋ 掩码呈现降级 ×2（code, thromb） |
| REFUSE | 15 | 25% | OOV ×4（fin, f1, debit, ef2）＋ AM ×5（i: ca_sch；ii: fin, w1；iii: debit；iv: ef2 比赛日锚×快照日锚审计失败；thromb 双 hull 错位留作种子素材不出题）＋ MC ×3（i: card；ii: card 主例, f1）＋ DISCLOSURE-BLOCKED ×3（code×1, thromb×2） |

四类拒因（OOV/AM/MC/DB）全部有实例；AM 四子型 (i)(ii)(iii)(iv) 全覆盖；MC 两型全覆盖 → 任务书拒答谱系达标。

### 4.2 簇预算（簇 = 库，9 簇）

| 簇 | financial | card_games | codebase | formula_1 | debit | ef2 | ca_schools | thrombosis | world_1 | Σ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ANSWER | 5 | 4 | 3 | 5 | 4 | 3 | 4 | 2 | 3 | 33 |
| REWRITE | 1 | 1 | 3 | 1 | 1 | 1 | 1 | 2 | 1 | 12 |
| REFUSE | 2 | 2 | 1 | 2 | 2 | 2 | 1 | 2 | 1 | 15 |
| 计 | 8 | 7 | 7 | 8 | 7 | 6 | 6 | 6 | 5 | **60** |

每簇 5–8 题；簇自助 bootstrap 沿用 B=2000, seed=20260731，9 簇对照 B6 的 6 簇收窄区间。金标全部由编译器跑通 + 独立校验器复核后冻结（60/60 双绿才封卷）。

---

## 5. running example 移植清单：rma SKU536-EOL → card_games

| 结构要件 | 旧（企业，只作动机叙事） | 新（公开，进结果表/图） |
|---|---|---|
| 度量 | `problem_rate = 问题件数/同月销量` | `ruling_intensity = 同月裁定条数 / 同月新发行印刷数` |
| 实例 | SKU536-EOL，as-of 2026-05 | **card_games 全域，as-of 2017-02** |
| 分子（另一锚上仍有事实） | 问题件 7 | 裁定 **2,161** 条（rulings.date ∈ 2017-02，P-6） |
| 同月分母缺失 | 同月销量 0（EOL 后退货仍至） | 同月发行套牌 **0** → 新发行印刷数 0（P-6；停发月裁定仍至） |
| 裁定 | ⊥_MC（MC(ii)，μ_den≤0） | 同 ⊥_MC（MC(ii)）；守卫序 OOV→AM→MC 走位一致 |
| 锚对 | rma_event_time × sales_event_time | rulings.date × sets.releaseDate（绑定 rule `same_valid_time_window`） |
| 口径路由 | problem→sales scoped 分母 | rulings→cards→sets（uuid/setCode 连接键）scoped 分母 |
| 探针 | `_den_present()` 同窗销量探测 | 同型探针：同窗 `sets.releaseDate` 计数（元数据零记载，ND-1 见证对：向 2017-02 插入一行 sets 即翻转标签） |
| 卫星实例（实体粒） | — | Kytheon（ORI，发行 2015-07-17）：2015-06-22 先行裁定 16 条而当月印刷 0（P-5，生命周期**前沿**）；Renegade Rallier（PRM 2002-06-24 发行）2017-02-09 裁定 10 条（生命周期**后沿**）——月界两向皆备 |
| 论文用法 | 摘要/引言可叙述 rma 动机**不带数字** | 图表/artifact 只用 card_games 实例（作者裁定合规） |

迁移完备性：同月分母缺失 ✓、分子正质量 ✓（旧例 7，新例 2,161，更尖锐）、双锚绑定 ✓、scoped 路由 ✓、MC(ii) 判类 ✓、探针专属性 ✓（ND-1 见证对物化）。

---

## 6. 构建协议

### 6.1 版本轴合成（关 C3 G1）
commit map 按 (提交日期, commit_seq) 字典序嵌入离散 𝕋（定义 3.5 平局细化），严格单调、版本号不复用、append-only（A3/D6：回滚=重提交）。每库 v1 commit 于数据跨度中段之前、v2 于其后，保证两侧均有可出题的 T；`committed_at` 为**真时戳**（修复现种子"标签双写"缺陷，C5 公理 5.0 现状注记）。版本内容差异只经登记行（measure_def/routing/alias/policy 的版本戳行）表达。

### 6.2 authored 内容规则
world_1 历史：`population(code, m) = round(P₀(code) × (1+g(code))^(m−m₀))`，g(code) 由 code 的 SHA1 前 8 位映射到 [−0.4%, +0.8%] 月增长率（种子 20260731），2026-07 起亚洲行 ×1.06 半上取整（v2 语义变更）；GNP 同法。所有合成行 `authored=true`；各治理版本行、财务 status 口径 v2 等 authored 判据同标。真实/authored 行数分列入 `provenance.json`。

### 6.3 目录布局（与旧 pilot 并存）
```
pilot2/
  DESIGN_SPEC.md                    # 本文件
  domains/<db>/warehouse.duckdb     # 自 BIRD/Spider 只读抽取 + authored 层
  domains/<db>/gov_seed/*.jsonl     # §3.1 十表
  domains/<db>/questions.json       # §3.4 字段纪律
  domains/<db>/provenance.json      # 源、抽取 SQL、sha256、real/authored 行数
  build/  (extract_<db>.py, synth_rules.py, probes.py)
  ci/     (nondegeneracy_gate.py, witness_pairs.py, leak_check.py)
```
工程红线：不动 `theory/` 与 `pilot/domains/`；编译器/校验器零共享（ci_check.py 零交集）；校验器窗推导仅 G_v+D+q 非窗字段；一切数字可复算（§8 探针 + 建库脚本全部落 build/）。

### 6.4 验收清单（封卷条件）
1. ND-1 见证对全部物化断言通过；ND-2 零命中；ND-3 ≥30%。
2. 60 题编译器金标 = 独立校验器复核 60/60。
3. RC-7：4 库 policy_ids 非空 + 3 DB 拒答 + 5 上卷 REWRITE 实测。
4. RC-8：9 库双版本 + 4 组同题双 T flip 值实测相异。
5. A2 泄漏比对通过；B6 协议可原样重挂 pilot2（ND-4 预测登记后再跑）。

---

## 8. 探针清单（全部数字的复算源；SQLite 只读，路径见 §0）

| # | 库 | SQL（缩写） | 实测 |
|---|---|---|---|
| P-1 | 全部 | 逐表 COUNT(*) | §1 行数列 |
| P-2 | financial | MIN/MAX(trans.date), COUNT | 1993-01-01→1998-12-31, 1,056,320 |
| P-3 | financial | 1997 全年 k_symbol='SANKC. UROK' 计数 ÷ 全交易计数 vs ÷ 受罚账户交易计数 | 0.14310% vs 2.17426%（15.19×） |
| P-4 | formula_1 | races MIN/MAX；brawn 2009/2010 results 计数；MAX(points) by year 2009/2010 | 1950-05-13→2017-11-26；34/0；10.0/25.0 |
| P-5 | card_games | sets.releaseDate、rulings.date MIN/MAX；Kytheon 裁定日与 ORI 发行日 | 1993-08-05→2021-03-19；2004-10-04→2021-02-05；2015-06-22 vs 2015-07-17 |
| P-6 | card_games | 2017-02 rulings 计数；2017-02 sets 计数（另 2015-06: 1,066/0） | **2,161 / 0** |
| P-7 | european_football_2 | COUNT(DISTINCT PA.date), MIN, MAX | 197, 2007-02-22→2016-07-07 |
| P-8 | debit | COUNT(DISTINCT ym.Date), MIN, MAX；trans1k MIN/MAX(Date) | 21, 201112→201311；2012-08-23→26 |
| P-9 | debit | 2013-08 AVG(Consumption) by Currency | CZK 15,626.14 / EUR 1,166.15 |
| P-10 | california_schools | OpenDate MIN/MAX、ClosedDate 非空数；frpm DISTINCT 学年；K-12 与 5-17 全域率 | 1850→2017，5,694；{2014-2015}；0.49974 / 0.49904 |
| P-11 | codebase_community | posts.CreaionDate、users/votes.CreationDate MIN/MAX | posts 2009-02-02→2014-09-14；votes 2010-07-19→2011-05-01 |
| P-12 | california_schools | OpenDate≤d<ClosedDate(或空) 在效计数 @2015-01-01 | 10,629 |
| P-13 | european_football_2 | Match 按月计数 2015-06..08 | 2015-06 **0**、2015-07 37、2015-08 347 |
| P-14 | financial | 1997-05 放贷总数；零放贷区数/77；样本零放贷区同月交易数 | 16；64；234 |
| P-15 | thrombosis | Laboratory.Date、Examination Date MIN/MAX | 1981-01-27→1999-03-04；1989-04-18→1998-04-17 |

> 附注：codebase_community 的 `CreaionDate`/`LasActivityDate` 为 BIRD 原库拼写，如实沿用不修；EOL-tag 备选 running example（标签停更而答案仍至）经全表 LIKE 扫描代价过高未在设计期钉定，card_games 主例已验证充分，该备选降级为建库期可选素材。
