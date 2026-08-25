# S2 — 治理盲时态 SQL 双臂研究报告（deterministic，零 LLM）

- **Prereg**：`PREREG_poststudy_20260820.md` §S2，sha256
  `f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24`（运行时断言通过）。
- **执行环境**：一次性沙盒副本
  `…/scratchpad/poststudy-sandbox`（冻结证据零改动；所有产出仅落
  `poststudy_20260820/s2/`）。
- **产出**：`tsql_arms.py`（实现）、`tsql_ledger.json`（逐题账本，含双臂 SQL、
  原始输出、金标、双读法判定、窗推导与 windows 字段对账）、`tsql_summary.json`。
- **Import-disjointness 红线**（镜像校验器断言，启动时执行，原文输出）：
  > IMPORT-DISJOINTNESS OK: 165 loaded modules scanned; none originate from
  > impl/asof_compiler, impl/asof_verifier or impl/
- **冻结评分器**：import 沙盒 `pilot/run_pilot.py`
  （sha256 `fecda681ccce…` 断言通过）与 `pilot2/run_pilot2_arms.fetch_and_score`
  （§4.2 冻结分派：rowset {CA-Q5,CODE-Q4,DEB-Q5,TH-Q3}、string {CODE-Q6,TH-Q4}、
  其余数值；REL_TOL=0.005）。零 LLM 调用。
- **输入排除表（prereg 指名，代码强制）**：loader 在臂可见前剥除
  `gold_sql / gold_value / expected_kind / refusal_* / rewrite / pinned_version`；
  臂构建器额外不读 `question_zh / notes / windows_note / windows`——请求窗由
  非金标结构字段 + **最新已提交版本**（9 库全部为 v2，`commit_seq=2`）的
  binding/anchor/route 行重推，推得后在构建器之外与题面 `windows` 字段逐腿对账：
  **60 题 0 处失配**（CARD-Q3 的 cum 窗按约定记 `ok_cum_lo_omitted`：guard-free
  臂无 hull 探针故无左端点）。

## 0. NULL 边界规则与双读法（先行声明，不择优）

臂只输出原始 SQL 求值结果；空分母/空集聚合产生的裸 NULL 记为 `"NULL"`，
臂从不发出拒答声明。冻结评分器机械行为：NULL → kind `error` →
refusal 金标题记 `answered_should_refuse`（计错）。因该规则对"非 LLM 臂输出裸
NULL 是否算隐式拒答"存在解释空间，**两种读法全量计算、全量公布**：

- **读法 B（NULL 记隐式拒答得分；对论文更不利，本报告以此领衔）**
- **读法 A（冻结字面：NULL 记错）**

TSQL-W 在 refusal 金标题上产生 5 个裸 NULL：CARD-Q7、DEB-Q6、EF2-Q5、EF2-Q6、
F1-Q8（全部是空分母/空成员集自然塌缩）。TSQL-H 无任何 NULL。

## 1. 总量（60 题）

| 臂 | 读法 B（NULL 记拒答得分） | 读法 A（冻结字面） |
|---|---|---|
| **TSQL-W** | **23/60 = 0.383** | 28/60 = 0.467 |
| **TSQL-H** | **54/60 = 0.900** | 54/60 = 0.900 |

两臂均 60/60 作答、0 次拒答声明（P1 前件在两读法下同真）。

判定分类（读法 A）：TSQL-W = correct 32 / wrong_value 12 /
answered_should_refuse 15 / execution_error 1（CODE-Q5 日粒报表首格为日期串，
冻结数值通道 float() 失败）；TSQL-H = correct 6 / wrong_value 38 /
answered_should_refuse 15 / execution_error 1。

## 2. 分割计数（errors / n）

| 分割 | TSQL-W 读法 B | TSQL-W 读法 A | TSQL-H（两读法同） |
|---|---|---|---|
| value (33) | 6/33 | 6/33 | 27/33 |
| rewrite (12) | 7/12 | 7/12 | 12/12 |
| refusal (15) | 10/15 | 15/15 | 15/15 |

- **value 错题（W，两读法同）**：FIN-Q1、F1-Q1、W1-Q1（版本翻转离版侧）、
  F1-Q3（显式钉 v1 被排除表剥除→最新版误绑）、CODE-Q1（ver(T)=v1 而最新 v2
  分母剔除社区共有帖：0.69869 vs 金标 0.68085，rel 2.62%）、W1-Q3（ver(T)=v1
  而最新 v2 改指常住口径列：0.62134 vs 0.60753，rel 2.27%）。六错全部是
  **version-in-effect 误绑**——同窗同锚下仅"最新版≠当时生效版"即致错。
- **rewrite（W）**：5 道 hull-trim 题全对（CARD-Q5、EF2-Q4、FIN-Q6、F1-Q6、
  W1-Q4——请求窗直算在仓上与裁剪窗同值，prereg 预告的 freebies）；
  7 道治理改写题全错（CA-Q5、CODE-Q4、DEB-Q5、TH-Q3 粒度上卷；CODE-Q5 时间
  下限；CODE-Q6、TH-Q4 掩码呈现——臂输出原值/请求粒度行集）。
- **refusal 按理由（W，读法 B → 读法 A）**：OOV 2/4 → 4/4；AM 4/5 → 5/5；
  MC 1/3 → 3/3；DB 3/3 → 3/3。disclosure-blocked 三题在任何读法下全错
  （名录行集是实数行，不塌缩为 NULL）。
- **TSQL-H 仅存的 6 个 correct** 全是巧合覆盖：CA-Q1/CA-Q2（frpm 仅一个学年
  token，截尾=单窗）、CARD-Q3（cum 语义本就 ≤ as_of，H≡W）、CARD-Q4（该卡全部
  裁定恰在 as_of 前月内）、DEB-Q4（201112 尾量极小：44,084,461.5 vs
  44,080,288.84，rel 9.5e-5 落容差内）、EF2-Q2（赛季 scope 列本身完成了开窗）。

## 3. 版本翻转对照表（4 对；TSQL-W，最新版绑定）

| 对 | 题 | ver(T) | 离版侧 | 金标 | TSQL-W 值 | rel diff | 判定 |
|---|---|---|---|---|---|---|---|
| CA | CA-Q1 | v1 | ✔ | 0.3798559 | 0.3780455 | **0.477%（<0.5% 容差）** | correct（盲答获记分） |
| CA | CA-Q2 | v2 | – | 0.3780455 | 0.3780455 | 0 | correct |
| FIN | FIN-Q1 | v1 | ✔ | 0.1367521 | 0.0854701 | 37.5% | **wrong_value** |
| FIN | FIN-Q2 | v2 | – | 0.0854701 | 0.0854701 | 0 | correct |
| F1 | F1-Q1 | v1 | ✔ | 100.0 | 252.0 | 152% | **wrong_value** |
| F1 | F1-Q2 | v2 | – | 252.0 | 252.0 | 0 | correct |
| W1 | W1-Q1 | v1 | ✔ | 4,068,933,086 | 4,313,069,067 | 6.0% | **wrong_value** |
| W1 | W1-Q2 | v2 | – | 4,313,069,067 | 4,313,069,067 | 0 | correct |

离版侧错 **3/4**；CA 对恰为 prereg 预告的"容差内对"（0.477% < 0.5%）。

## 4. 预设判定（S2-P1…P4，逐字执行）

| 预设 | 读法 B（领衔，对论文更不利） | 读法 A（冻结字面） |
|---|---|---|
| **S2-P1** 两臂 60/60 作答（零拒答）→ refusal 0/15 correct | **MISSED_PREDICTION**：作答前件成立（0 次拒答声明），但 5 个裸 NULL 获隐式拒答记分 → TSQL-W refusal **5/15** correct（TSQL-H 0/15） | **MET**：0 拒答声明；W 0/15、H 0/15 |
| **S2-P2** TSQL-W 总错 ∈ [0.35, 0.60] 且 TSQL-H ≥ TSQL-W | **MET**：0.383 ∈ [0.35,0.60]；0.900 ≥ 0.383 | **MET**：0.467 ∈ [0.35,0.60]；0.900 ≥ 0.467 |
| **S2-P3** 4 个离版侧 ≥2 错（一对或落容差内） | **MET**（与读法无关）：3/4 错（FIN-Q1、F1-Q1、W1-Q1）；CA-Q1 落容差获记分 | 同左 **MET** |
| **S2-P4** TSQL-W value（n=33）错 ≤ 最优 plain LLM 基线 value 错 | **MET**（与读法无关）：6/33 ≤ 18/33（baseline_claude；qwen 23、deepseek 27、minimax 25，冻结 `pilot2_arms_summary.json`） | 同左 **MET** |

**结论行**：读法 A 下 4/4 MET；读法 B 下 3/4 MET、S2-P1 计 MISSED。
S2-P1 的失手形态本身有利于论文叙事的反面被完整公布：即使把裸 NULL 慷慨地记
为隐式拒答，治理盲臂在 15 道 refusal 题上也只到 5/15，且三类中 disclosure-
blocked 0/3、跨窗祈使（AM(ii)）0/2、未注册锚（AM(i)）0/1——需要"元数据判定"
而非"空集塌缩"的拒答一个都拿不到。

## 5. 实现约定（全部录入 ledger，供 A3 复核）

1. **窗实现粒元规则**：请求窗一律实现在锚的原生粒元上——日窗落 token 锚时化为
   覆盖该窗的 token 区间。DEB-Q7 的周窗请求（AM(iii) 金标）因此落到
   `Date='201303'` 得数（两读法下均 answered_should_refuse）。替代的"日串直比
   token 列"实现会得 NULL，仅在读法 B 下会把 DEB-Q7 翻为 correct——即便按该
   替代实现，读法 B 的 W 错数为 22/60，各预设判定不变。
2. **CARD-Q6**（collector_premium）：两腿锚节点 card.sets 在最新版 route 行中
   不可达（den 路由 dst_caliber='none' 且无 join），guard-free 臂无窗聚合直接
   出数——refusal 金标，判定不受影响；已记 ledger note。
3. **cum 窗**：guard-free 无 hull 探针，cum 只有右端（≤ as_of）；与题面
   windows 字段的对账按 `ok_cum_lo_omitted` 记录（CARD-Q3）。
4. **delta（F1-Q4）**：W 按期序各取年窗（v2 度量）→ −38 correct；H 无 as_of
   故两期项同为全史 → 0，wrong_value。
5. **attribute（CODE-Q6、TH-Q4）**：非时态，两臂同 SQL，输出未掩码原值
   （'Durham, UK'、'1934-02-13'）→ 均 wrong_value（披露盲失败形态）。

## 6. 复核抽样（本轮内部；A3 将独立重推）

13 行（9×W + 4×H）手写 SQL 独立重算与 ledger 全等（见运行日志）；5 个 W 侧
NULL 逐题确认为空分母/空成员集塌缩。窗对账 60 题 0 失配。

*生成：2026-08-20，`tsql_arms.py`（本目录）一次运行产出；冻结区无写入。*
