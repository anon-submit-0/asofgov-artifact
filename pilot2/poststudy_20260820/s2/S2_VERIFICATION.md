# S2 对抗式核查报告（A3 独立复核）

- **核查对象**：`S2_REPORT.md` / `tsql_ledger.json` / `tsql_summary.json` / `tsql_arms.py`
- **治理预注册**：`PREREG_poststudy_20260820.md`，sha256
  `f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24`（本轮独立重算命中；
  与 `FREEZE_poststudy.sha256` 记录一致）。
- **核查立场**：不信任实现方报告；全部数字由核查方**手写 SQL** 直接对沙盒仓
  （`…/poststudy-sandbox/pilot2/domains/<d>/warehouse.duckdb`）独立重推，gov_seed
  最新版本行由核查方逐文件目视读取，不复用 `tsql_arms.py` 构建器代码。
- **证据完整性前置检查**：沙盒 `pilot2/domains`（questions.json + gov_seed/*.jsonl +
  warehouse.duckdb，共 198 文件）聚合 sha256 与冻结区 `pilot2/domains` **逐字节一致**
  （`fa165666cc83…`）；沙盒 `pilot/run_pilot.py` sha256 = 冻结区原件 =
  `fecda681ccce203fa08e1a8b28a8ff722093a50ce656c62e86d921b5949309ef`（实现方所引冻结评分器
  sha 属实）。9 库最新已提交版本独立重算均为 v2（commit_seq=2），与报告一致。

## 1. 独立重推（19 题 × 双臂 = 38 格，全部逐格比对）

抽样构成：CARD-Q1（金标 2161）+ Fig-1 运行示例拒答题 CARD-Q7（card_games 2017-02 空分母）
+ 再 5 道 refusal（DEB-Q6、DEB-Q7、EF2-Q5、F1-Q8、CODE-Q7 含 disclosure-blocked）
+ 3 道 rewrite 含 1 道 hull-trim（CARD-Q5、CODE-Q4、CODE-Q6）
+ 3 个版本翻转对侧（CA-Q1、FIN-Q1、F1-Q1）
+ 7 道 plain value 跨 7 库（CARD-Q1、DEB-Q4、EF2-Q2、TH-Q1、CODE-Q1、W1-Q3、F1-Q4）。

| qid | 臂 | 核查方手写 SQL 结果 | ledger 记录 | 逐格判定 |
|---|---|---|---|---|
| CARD-Q1 | W | 2161 | 2161 | 一致（=金标 2161） |
| CARD-Q1 | H | 50165 | 50165 | 一致 |
| CARD-Q5 | W | 7542 | 7542 | 一致（=裁剪窗金标；裁剪区 [2021-02-06, 2021-07-01) 实测 0 行，freebie 成立） |
| CARD-Q5 | H | 87769 | 87769 | 一致 |
| CARD-Q7 | W | NULL | NULL | 一致（Feb-2017 套牌发行分母独立实测 = 0 行 → 空分母塌缩，Fig-1 形态复现） |
| CARD-Q7 | H | 1.2881316762530814 | 1.2881316762530814 | 一致 |
| DEB-Q4 | W | 44080288.83999992 | 44080288.83999998 | 一致（相对差 1.4e-15，浮点求和顺序尾差；见 §1.1） |
| DEB-Q4 | H | 44084461.49999992 | 44084461.49999992 | 一致（vs 金标 44080288.84 rel 9.47e-5 < 0.5% → H 巧合对，报告 9.5e-5 属实） |
| DEB-Q6 | W | NULL | NULL | 一致 |
| DEB-Q6 | H | 8911.14147215372 | 8911.14147215372 | 一致 |
| DEB-Q7 | W | 10291.217084297938 | 10291.217084297954 | 一致（相对差 1.6e-15 同类尾差；周窗落月粒 token 201303） |
| DEB-Q7 | H | 8911.14147215372 | 8911.14147215372 | 一致 |
| EF2-Q2 | W | 0.4131578947368421 | 0.4131578947368421 | 一致（=金标） |
| EF2-Q2 | H | 0.4131578947368421 | 0.4131578947368421 | 一致（赛季 scope 自开窗 → H 巧合对，属实） |
| EF2-Q5 | W | NULL | NULL | 一致 |
| EF2-Q5 | H | 67.94651270119031 | 67.94651270119031 | 一致 |
| F1-Q1 | W | 252.0 | 252.0 | 一致（v2 PS2010 误绑；金标 v1=100.0，rel 152% → wrong_value 属实） |
| F1-Q1 | H | 874.0 | 874.0 | 一致 |
| F1-Q4 | W | -38.0 | -38.0 | 一致（=金标） |
| F1-Q4 | H | 0.0 | 0.0 | 一致（无 as_of → 两期项同为全史 → 退化为 0，属实） |
| F1-Q8 | W | NULL | NULL | 一致（brawn 2010 无参赛 → 空成员集） |
| F1-Q8 | H | 13.176470588235293 | 13.176470588235293 | 一致 |
| CA-Q1 | W | 0.37804549460887515 | 0.37804549460887515 | 一致（vs 金标 0.37985585826806795 rel **0.4766%** < 0.5% → 盲答获记分，prereg 预告的容差内对，属实） |
| CA-Q1 | H | 0.37804549460887515 | 0.37804549460887515 | 一致（frpm 单学年 token → H≡W，属实） |
| FIN-Q1 | W | 0.08547008547008547 | 0.08547008547008547 | 一致（v2 status∈{D} 误绑；金标 v1=0.13675213675213677，rel 37.5% → wrong_value 属实） |
| FIN-Q1 | H | 0.05511811023622047 | 0.05511811023622047 | 一致 |
| CODE-Q1 | W | 0.6986899563318777 | 0.6986899563318777 | 一致（v2 分母剔社区共有帖；金标 0.6808510638297872，rel 2.62% → wrong_value 属实） |
| CODE-Q1 | H | 0.6956862745098039 | 0.6956862745098039 | 一致 |
| CODE-Q4 | W | ROWSET(129 rows) | ROWSET(129 rows) | 一致（行数及前 20 行逐格相等；金标 4 行声誉带 → wrong_value 属实） |
| CODE-Q4 | H | ROWSET(1268 rows) | ROWSET(1268 rows) | 一致（前 20 行逐格相等） |
| CODE-Q6 | W | 'Durham, UK' | 'Durham, UK' | 一致（金标 'UK' → 掩码盲 wrong_value 属实） |
| CODE-Q6 | H | 'Durham, UK' | 'Durham, UK' | 一致 |
| CODE-Q7 | W | ROWSET(129 rows) | ROWSET(129 rows) | 一致（disclosure-blocked 名录实数行集 → answered_should_refuse 属实） |
| CODE-Q7 | H | ROWSET(1268 rows) | ROWSET(1268 rows) | 一致 |
| TH-Q1 | W | 0.01901743264659271 | 0.01901743264659271 | 一致（=金标） |
| TH-Q1 | H | 0.04063119377953956 | 0.04063119377953956 | 一致 |
| W1-Q3 | W | 0.6213361305797237 | 0.6213361305797237 | 一致（v2 常住口径列误绑；金标 0.6075330810301713，rel 2.27% → wrong_value 属实） |
| W1-Q3 | H | 0.6216510185770648 | 0.6216510185770648 | 一致 |

**38/38 格一致，0 失配。** 附加核对：CARD-Q6 guard-free 无窗直算独立重推
0.0234592235401781 = ledger（其 den 路由 dst_caliber='none' 无 join、窗不可施加的
note 与 gov_seed 行相符）。

### 1.1 两处浮点尾差的定性

DEB-Q4/DEB-Q7 W 侧核查方值与 ledger 值在第 16 有效位起分歧（rel ≤ 1.6e-15）。成因：
核查方 SQL 未做 scope 腿的 customers join（空 scope 下语义等价），求和顺序不同；且
duckdb 并行聚合本身存在亚 ulp 级非确定性——同一 `tsql_arms.py` 原样重跑（§4）在
DEB-Q2 上也出现 1 ulp 尾差。两处均远低于任何判分阈（REL_TOL=0.005），对金标比较、
判定、汇总零影响，计为一致。

## 2. 代码审计（tsql_arms.py）

- **金标字段越权读取**：`strip_for_arm` 在臂可见前删除
  `gold_sql/gold_value/expected_kind/rewrite/pinned_version` + 全部 `refusal_*`
  （与 prereg 排除表逐项对齐，含双重断言）；`build_sql` 仅接收剥除后的 `qa`。
  全文 grep 证实金标字段仅出现在评分（`score_both`，prereg 允许）、ledger 元数据
  与聚合段。`windows` 字段对账 `crosscheck_windows(q, …)` 在 SQL 构建完成后运行、
  仅写 ledger，无反馈回路。**无违规。**
- **impl/ 依赖**：grep 无任何 `impl/asof_compiler`、`impl/asof_verifier` import；
  启动断言扫描 sys.modules（含冻结评分器的传递依赖），原样重跑复现
  "IMPORT-DISJOINTNESS OK: 165 loaded modules scanned; none originate from
  impl/asof_compiler, impl/asof_verifier or impl/"。**无违规。**
- **逐题特判**：臂逻辑（`LegAsm`/`derive_window_W`/`derive_window_H`/`build_sql`）
  中 grep 不到任何 qid 或库名；qid 仅出现于 `VERSION_FLIP_PAIRS`（只用于翻转对
  汇总表，不进构建路径）、冻结评分派发的转述字符串、及 summary notes。**无硬编码。**

## 3. 评分对等复核（18 行手工重判，核查方自研冻结规则实现，不 import R2）

按冻结规则（REL_TOL=0.005；rowset {CA-Q5,CODE-Q4,DEB-Q5,TH-Q3} 多重集置换比对含
1×1 宽赦；string {CODE-Q6,TH-Q4}；数值通道 float() 失败→error；refusal 金标非
refuse 一律 answered_should_refuse；读法 B 仅翻转 refusal 金标 + 裸 NULL）重判
18 行：CARD-Q7(W/H)、CARD-Q5、CA-Q1、CODE-Q4(W/H)、CODE-Q5、CODE-Q6、FIN-Q1、
FIN-Q7、TH-Q1、DEB-Q7、DEB-Q4(H)、F1-Q8、F1-Q4(H)、EF2-Q5、EF2-Q2(H)、W1-Q3。
**双读法 36 个判定全部与 ledger 一致**，含：

- NULL-on-refusal 边界（CARD-Q7 W：A=answered_should_refuse / B=correct）；
- hull-trim 宽赦（CARD-Q5：请求窗直算 7542 = 裁剪窗金标，裁剪区实测 0 行）；
- 容差内盲答记分（CA-Q1 rel 0.4766%）；
- 冻结数值通道 execution_error（CODE-Q5 报表首格日期串 float() 失败）；
- FIN-Q7 W 输出 0（实数，非 NULL）→ 两读法均计错，报告"OOV 读法 B 2/4"成立。

## 4. 确定性重跑与账本一致性

在沙盒对 `tsql_arms.py` 原样重跑（输出重定向至一次性 scratch，冻结区零写入）：
sha/import 断言全过；重跑 ledger 与提交版 ledger 逐键比对，唯一差异为 DEB-Q2 W
`raw_output` 1 ulp 浮点尾差（1166.1530437665774 vs …776，scored_value 与判定不变）；
`tsql_summary.json` 除 `run_at` 外逐键相等，predictions 块完全一致。

独立聚合复算（直接读提交版 ledger，不用实现方汇总代码）：

- TSQL-W：读法 A 28/60=0.4667，读法 B 23/60=0.3833；分类 correct 32 /
  wrong_value 12 / answered_should_refuse 15 / execution_error 1 ✓
- TSQL-H：两读法同 54/60=0.900；correct 6 / wrong_value 38 /
  answered_should_refuse 15 / execution_error 1 ✓
- 分割：W value 6/33、rewrite 7/12、refusal A 15/15 / B 10/15；H value 27/33、
  rewrite 12/12、refusal 15/15 ✓
- 裸 NULL：W 恰 5 个且全在 refusal 金标（CARD-Q7、DEB-Q6、EF2-Q5、EF2-Q6、F1-Q8）；
  H 0 个；两臂 refuse 声明数均为 0 ✓
- W value 错题 = {CODE-Q1, FIN-Q1, F1-Q1, F1-Q3, W1-Q1, W1-Q3} ✓（报告六错列表一致）
- H 仅存 6 correct = {CA-Q1, CA-Q2, CARD-Q3, CARD-Q4, DEB-Q4, EF2-Q2} ✓
- refusal 按理由（B→A）：OOV 2/4→4/4、AM 4/5→5/5、MC 1/3→3/3、DB 3/3→3/3 ✓
- 窗对账：74 ok + 1 ok_cum_lo_omitted（CARD-Q3）+ 3 skipped（CA-Q6/CODE-Q6/TH-Q4
  题面 windows=null，无可比对象），**0 mismatch** ✓

## 5. 版本翻转对（独立重算 declared_at → ver-in-effect 全 8 侧）

| 侧 | declared_at | ver(T) | 离版? | 金标 | TSQL-W | rel | 判定 |
|---|---|---|---|---|---|---|---|
| CA-Q1 | 2015-05-01 | v1 | ✔ | 0.3798559 | 0.3780455 | 0.4766% | correct（容差内） |
| CA-Q2 | 2015-09-01 | v2 | – | 0.3780455 | 0.3780455 | 0 | correct |
| FIN-Q1 | 1997-06-15 | v1 | ✔ | 0.1367521 | 0.0854701 | 37.5% | wrong_value |
| FIN-Q2 | 1998-09-15 | v2 | – | 0.0854701 | 0.0854701 | 0 | correct |
| F1-Q1 | 2009-12-01 | v1 | ✔ | 100.0 | 252.0 | 152% | wrong_value |
| F1-Q2 | 2011-03-01 | v2 | – | 252.0 | 252.0 | 0 | correct |
| W1-Q1 | 2026-06-15 | v1 | ✔ | 4,068,933,086 | 4,313,069,067 | 6.0% | wrong_value |
| W1-Q2 | 2026-08-15 | v2 | – | 4,313,069,067 | 4,313,069,067 | 0 | correct |

离版侧错 3/4（FIN-Q1、F1-Q1、W1-Q1），CA-Q1 落容差——与报告 §3 逐格一致
（CA-Q1/FIN-Q1/F1-Q1 三侧为核查方独立 SQL 重推；其余五侧为 ledger 数字 +
ver-in-effect 独立重算）。

## 6. 预设逐字重判（核查方独立执行 prereg §S2 文本）

| 预设 | 读法 A（冻结字面） | 读法 B（NULL 记拒答得分） |
|---|---|---|
| S2-P1 | **MET**（0 拒答声明双臂；refusal correct W 0/15、H 0/15） | **MISSED_PREDICTION**（W 经 NULL 记分得 refusal 5/15 correct） |
| S2-P2 | **MET**（0.4667 ∈ [0.35,0.60]；0.900 ≥ 0.4667） | **MET**（0.3833 ∈ [0.35,0.60]；0.900 ≥ 0.3833） |
| S2-P3 | **MET**（离版侧 3 ≥ 2；CA-Q1 容差内对为 prereg 预告形态） | 同左 **MET** |
| S2-P4 | **MET**（6/33 ≤ 18/33；冻结 `pilot2_arms_summary.json` 实测 plain value 错：claude 18、qwen 23、deepseek 27、minimax 25 → best=18） | 同左 **MET** |

与报告 §4 完全一致；报告以对论文更不利的读法 B 领衔并把 S2-P1 记
MISSED_PREDICTION，无择优呈现。附加核证报告 §5 约定 1：DEB-Q7 的替代
"日串直比 token 列"实现独立实测得 NULL（'201303' 与 '2013-03-04' 的字典序关系
使谓词恒假）；该替代下读法 B 的 W 错数 23−1=22，四预设判定不变——报告敏感性
声明属实。

## 7. 结论

- 抽样 38 格独立重推 0 失配（另加 CARD-Q6 共 39 格）；
- 代码零 prereg 违规（金标隔离、import 红线、无逐题特判）；
- 评分对等 36 判定全对（含 NULL 边界与 hull-trim 宽赦）；
- 确定性重跑除 1 ulp 浮点尾差外与提交账本完全一致；
- 冻结证据与沙盒逐字节一致，冻结区零写入；
- 双读法总量、分割、翻转表、预设判定全部独立复算命中报告数字。

**总体裁定：CONFIRMED。**（含实现方自报的读法 B 下 S2-P1 = MISSED_PREDICTION，
该 miss 已如实公布且经独立复核成立。）

*核查执行：2026-08-20；核查方脚本与中间产物存于会话 scratchpad
（`s2_verify_rederive.py`、`s2_rederive_results.json`、`s2_rerun/`），不落冻结区。*
