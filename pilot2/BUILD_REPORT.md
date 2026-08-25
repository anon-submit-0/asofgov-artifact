# pilot2 BUILD_REPORT — 公开证据基座建仓与出题

> 生成：2026-08-04T03:29:44Z，由 `build/make_report.py` 自工件汇编（可复算）。
> 规范：`pilot2/DESIGN_SPEC.md`（唯一事实来源）。数据源：BIRD dev（CC BY-SA 4.0，本地 `/Users/loctek/bench_data/dev_20240627/`）+ Spider dev（world_1 经旧公共轨抽取件承接）。
> 建库全链确定性+幂等：整链重跑后 questions.json + gov_seed 全量 sha256 逐字节一致（实测两轮同哈希）。

## 1. 逐库行数（源 + authored 放大）

| # | 域 | 源 | 表数 | 真实行数 | authored 行数 | 最大表 | 治理版本 |
|---|---|---|---:|---:|---:|---|---|
| 1 | `financial` | BIRD | 8 | 1,079,680 | 0 | trans 1,056,320 | v1+v2 |
| 2 | `card_games` | BIRD | 6 | 803,445 | 0 | legalities 427,907 | v1+v2 |
| 3 | `codebase_community` | BIRD | 8 | 740,646 | 0 | postHistory 303,155 | v1+v2 |
| 4 | `formula_1` | BIRD | 14 | 514,287 | 18 | lapTimes 420,369 | v1+v2 |
| 5 | `debit_card_specializing` | BIRD | 5 | 423,050 | 0 | yearmonth 383,282 | v1+v2 |
| 6 | `european_football_2` | BIRD | 7 | 222,796 | 0 | Player_Attributes 183,978 | v1+v2 |
| 7 | `california_schools` | BIRD | 3 | 29,941 | 0 | schools 17,686 | v1+v2 |
| 8 | `thrombosis_prediction` | BIRD | 3 | 15,952 | 0 | Laboratory 13,908 | v1+v2 |
| 9 | `world_1` | Spider(承接) | 2 | 239 | 20,076 | country_history 20,076 | v1+v2 |
| Σ | 9 库 | | | **3,830,036** | 20,094 | | 9×2 版本 |

- P6 规模条款：`financial.trans` 1,056,320 行真实公开数据（≥10^5 零合成）。
- authored 层仅两处：`formula_1.points_scheme`（18 行，真实历史积分制的关系原子化）与 `world_1.country_history`（20,076 行 = 239 国 × 84 月，§6.2 确定性规则，行携 authored 标志；生成规则全文入各库 provenance.json）。真实/authored 分列，不计入规模主张。

## 2. 种子统计（gov_* 十表，双版本全量并存）

| 域 | version | node | metric | measure | alias | routing | anchor | binding | gran_edge | disclosure | 计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `financial` | 2 | 16 | 16 | 22 | 16 | 10 | 6 | 18 | 4 | 0 | 110 |
| `card_games` | 2 | 12 | 16 | 22 | 16 | 12 | 4 | 18 | 2 | 0 | 104 |
| `codebase_community` | 2 | 16 | 16 | 20 | 16 | 14 | 6 | 14 | 6 | 8 | 118 |
| `formula_1` | 2 | 28 | 16 | 16 | 16 | 20 | 2 | 16 | 4 | 0 | 120 |
| `debit_card_specializing` | 2 | 10 | 10 | 12 | 10 | 12 | 4 | 12 | 6 | 2 | 80 |
| `european_football_2` | 2 | 14 | 14 | 19 | 14 | 8 | 6 | 18 | 2 | 0 | 97 |
| `california_schools` | 2 | 6 | 10 | 12 | 10 | 4 | 4 | 10 | 6 | 2 | 66 |
| `thrombosis_prediction` | 2 | 6 | 12 | 14 | 12 | 8 | 4 | 12 | 6 | 6 | 82 |
| `world_1` | 2 | 4 | 12 | 14 | 12 | 8 | 2 | 12 | 4 | 0 | 70 |
| **Σ** | 18 | 112 | 122 | 151 | 122 | 96 | 38 | 130 | 40 | 18 | **847** |

- 非退化 schema 法（§3.1）：绑定登记十表零禁字段（ND-2 实测 90 文件 847 行 0 命中）；覆盖域不物化（锚只登记 effective_col/vf_col/vtc_col 列名指针 + coverage_mode，hull/日期集一律对 D 现算）；口径 = (col,op,value) 谓词原子；版本内容差异只经 measure_def/alias/policy 的版本戳行表达（如 fin 问题贷款 status{B,D}→{D}、f1 积分映射 PS2009→PS2010、w1 度量列 population→population_resident、debit k 10→20、th 掩码 年月→仅年、ef2 平局权重行 v2 删除、code 分母加社区帖排除原子、ca 口径列 K-12→5-17、card 轮替清单值集换代）。
- 干扰行密度（ND-3）：路径 B 全题触达 363/847 行，全局干扰占比 **57.1%**（阈值 ≥30%，逐库 45.5%–60.8%）。

## 3. 题分布矩阵（库 × 判定类，60 题）

| 簇 | ANSWER | REWRITE | REFUSE | 计 | REFUSE 明细 |
|---|---:|---:|---:|---:|---|
| `financial` | 5 | 1 | 2 | 8 | out-of-validity; anchor-mismatch/am_ii |
| `card_games` | 4 | 1 | 2 | 7 | missing-caliber/mc_i; missing-caliber/mc_ii |
| `codebase_community` | 3 | 3 | 1 | 7 | disclosure-blocked |
| `formula_1` | 5 | 1 | 2 | 8 | out-of-validity; missing-caliber/mc_ii |
| `debit_card_specializing` | 4 | 1 | 2 | 7 | out-of-validity; anchor-mismatch/am_iii |
| `european_football_2` | 3 | 1 | 2 | 6 | out-of-validity; anchor-mismatch/am_iv |
| `california_schools` | 4 | 1 | 1 | 6 | anchor-mismatch/am_i |
| `thrombosis_prediction` | 2 | 2 | 2 | 6 | disclosure-blocked; disclosure-blocked |
| `world_1` | 3 | 1 | 1 | 5 | anchor-mismatch/am_ii |
| **Σ** | **33** | **12** | **15** | **60** | OOV×4 + AM×5(i/ii×2/iii/iv 全子型) + MC×3(i/ii×2 全两型) + DISCLOSURE-BLOCKED×3 |

- 分布兑现 §4.1：ANSWER 33 (55%) / REWRITE 12 (20%: 上卷×5[code 实体+code 时间+debit+ca+th] + hull 裁剪×5[fin,card,f1,ef2,w1] + 掩码降级×2[code,th]) / REFUSE 15 (25%)。
- RC-8 flip 对×4（同题双 T 异值实测）：FIN-Q1/FIN-Q2 = 0.13675213675213677 vs 0.08547008547008547；F1-Q1/F1-Q2 = 100.0 vs 252.0；CA-Q1/CA-Q2 = 0.37985585826806795 vs 0.37804549460887515；W1-Q1/W1-Q2 = 4068933086 vs 4313069067。
- 离对角显式钉×1：F1-Q3（T=2017-06-01 钉 p=v1，路径 B offdiag 标记实测 True；无钉对照实验=252/False——GOLD-1 镜像成立）。多期 delta×1：F1-Q4（2010−2009 = −38.0）。
- 双路径口径对照值（aware 进金标、blind 只入 notes）：fin 罚息率 0.14310% vs 2.17426%（15.19×）；code 采纳率 0.68085 vs 0.29038（2.34×）；debit 双币 CZK 15,626.14 / EUR 1,166.15（13.4×）。

## 4. 金标双人规则（路径 A 直算 SQL vs 路径 B 治理链推导）

- 封样运行：**60/60 一致，不一致 0**（类别+拒因/子型+数值(容差1e-9)+改写描述+窗结构五重比对）。
- 开发期不一致计数（如实报告，修复后清零）：运行时发现 3 处——①采纳判定自连接 hop 被去重逻辑吞掉（殃及 code 三题分子）；②周窗请求在无 as_of 时崩溃 → 加 AM(iii) 前置判定；③跨锚比率的守卫序（EF2-Q6 先误判 OOV）→ 锚对审计先于逐腿覆盖裁定。写种子期自查 2 处——ca v2 分子列名、card 轮替计数缺路由行。
- 路径 B 仅凭 G_v+D+题面可见字段独立复算（运行时投影断言 + 静态 leak 闸），与路径 A import 零交集（A=∅, B={json,datetime}）。
- 阴性对照（证伪『平凡一致』）：FIN-Q1@T=1998-09-15 → 0.08547（版本敏感）；DEB-Q5@v1(k=10) → ANSWER [['LAM',26.069]]（RC-7×RC-8 交互：同题 v1 治下 ANSWER/v2 治下 REWRITE 实测）；F1-Q3 去钉 → 252/offdiag=False；EF2-Q2@v1 → 0.55395（平局半胜权重行生效）。

## 5. CI 闸（非退化验收 §3.2 + §6.4）

- **ND-1 见证对 8/8 全翻转**（增行见证：治理种子逐字节不动，仅 D 变）：
  - FIN-Q7: OOV: 向 1999-06 插入一笔交易 → hull 右移，月窗部分覆盖 → ('refusal', 'out-of-validity', None, None) ⇒ ('rewrite', None, None, 'hull_trim')
  - F1-Q7: OOV: 向 1949-05 插入一场赛事 → hull 左移 → ('refusal', 'out-of-validity', None, None) ⇒ ('rewrite', None, None, 'hull_trim')
  - DEB-Q6: OOV(strict_member): 月集补入 201312 → ('refusal', 'out-of-validity', None, None) ⇒ ('value', None, None, None)
  - EF2-Q5: OOV(strict_member): 快照日集补入 2013-12-25 → ('refusal', 'out-of-validity', None, None) ⇒ ('value', None, None, None)
  - CARD-Q7: MC(ii): 向 2017-02 插入一套牌+一印刷 → 分母质量翻正 → ('refusal', 'missing-caliber', 'mc_ii', None) ⇒ ('value', None, None, None)
  - F1-Q8: MC(ii): 向 2010 赛季插入一条 brawn 参赛记录 → 分母翻正 → ('refusal', 'missing-caliber', 'mc_ii', None) ⇒ ('value', None, None, None)
  - EF2-Q6: AM(iv): 向 2013-12-01 插入一行快照 → 锚对实现集一致，审计通过 → ('refusal', 'anchor-mismatch', 'am_iv', None) ⇒ ('value', None, None, None)
  - DEB-Q5: REWRITE(小胞): LAM×EUR 胞 16→20 = k(v2) → 上卷判定翻回 Segment 级 ANSWER → ('rewrite', None, None, 'granularity_rollup') ⇒ ('value', None, None, None)
- **ND-2** 禁字段+SQL 片段扫描：90 文件 847 行 **0 命中**。
- **ND-3** 干扰行占比 **57.1%** ≥ 30%。
- **A2 泄漏比对**：60 题字段分区无交集、金标字面不入题面、路径 B 源码零金标 token —— PASS。
- **ND-4（预注册，未跑）**：B6 治理知情臂协议原样重挂 pilot2 公共轨，预测其错误率 >0%（对照旧公共轨 0/20 退化查表）。此为设计有效性的事后检验，登记于此待独立执行。
- expect_close 规格常量回归：7/7 在容差内（0.0014310 / 16 / 2161 / 34 / 15626.14 / 1166.15 / 10629）。

## 6. 与设计规格的实测偏差（如实清单）

1. **CARD-Q4 Kytheon**：规格 P-5 记 2015-06 裁定 16 条；实测 ORI 印次（双面牌全名）36 条（P-5 计数未含双面合名与逐印次重复）。金标取实测 36。
2. **EF2-Q3**：规格叙述 2015-06 快照 2,184 条；实测 Player_Attributes 月窗 681 条。金标取实测。
3. **debit 小胞位点**：规格写『客户级→Segment 上卷』；实测数据在 (LAM×EUR×2012-08) 段级胞=16 恰落 [10,20)，故 REWRITE 题落在段级胞上（v1 ANSWER/v2 上卷至 all）——RC-7×RC-8 交互因此可实测，客户级请求上卷仍由 k 机制自然覆盖（胞=1）。
4. **th/ca 上卷终点**：th 1997 异常患者仅 2 人 → 链式上卷 patient→cohort→sex→all（顶级豁免）；ca Alameda 存在 1-2 校小区 → school→district→county。均为『上卷改变小胞判定』的真实见证。
5. **f1 v1 积分映射**：规格速记 10-6-4-3-2-1；实现取 2009 真实口径 10-8-6-5-4-3-2-1（前八名），冠军单场 10 vs 25 的原型结论不变（flip 100 vs 252）。
6. **w1 重定基表达**：§6.2 字面『2026-07 起亚洲行 ×1.06』；实现为平行度量列 population_resident（全月序亚洲 ×1.06 半上取整，authored 数据行）+ v2 measure_def 版本戳行改指该列——否则同 as_of 的双 T flip 语义不成立；版本差异仍『经登记行+数据行表达、解析须过 ver(T)』。
7. **fin flip 窗**：取 1996 自然年（16/117 vs 10/117），规格未钉具体窗。
8. **题面格式**：兼容旧 pilot 全部字段，新增 declared_at/pinned_version/cross_window/anchor_override/window_request/requested_granularity/presentation 等题面显式声明字段（§3.4 允许）。

## 7. 封卷条件状态（§6.4）

| 条件 | 状态 |
|---|---|
| ND-1 见证对物化断言 | ✅ 8/8 翻转 |
| ND-2 零命中 | ✅ |
| ND-3 ≥30% | ✅ 57.1% |
| 60 题双路径复核 | ✅ 60/60（本任务的双人规则：直算 SQL vs 治理链推导） |
| RC-7（4 库 D_v 非空 + 3 DB 拒答 + 5 上卷 REWRITE） | ✅ code/debit/ca/th 策略非空；DB×3；上卷×5 |
| RC-8（9 库双版本 + 4 组同题双 T flip 实测相异） | ✅ |
| A2 泄漏比对 | ✅ |
| impl/asof_compiler+asof_verifier 正式对接 60/60 双绿 | ⏳ 后续（本报告的路径 B 为 pilot2 本地独立实现，非 impl 正式校验器；对接与 B6 重挂为封卷前置） |
| ND-4 治理知情臂重跑 | ⏳ 预测已登记（错误率 >0%），待独立执行 |

### 工件索引
```
pilot2/domains/<db>/warehouse.duckdb     # 9 库（源表原值 + authored 层 + gov_* 十表）
pilot2/domains/<db>/gov_seed/*.jsonl     # 十表种子（ND-2 扫描对象）
pilot2/domains/<db>/questions.json       # 60 题（题面可见字段 + 金标侧字段）
pilot2/domains/<db>/provenance.json      # 源 sha256 / 抽取法 / real-authored 分列 / 种子行数
pilot2/build/{build_all,extract_<db>,seeds_def,questions_def,synth_rules,lib_build}.py
pilot2/build/govchain_resolver.py        # 路径 B（治理链推导，与路径 A 零共享）
pilot2/build/dualpath_check.py           # 双人规则比对（dualpath_report.json）
pilot2/ci/{nondegeneracy_gate,witness_pairs,leak_check}.py + 各报告 json
```
