# 校验器窗独立性报告 — `impl/asof_verifier/chk.py`

- 日期：2026-08-03
- 范围：**只处理"窗坐标 ω_r 从哪来"这一条独立性缺口**。证书/编译器/金标/题面**未改一字节**（`acceptance.py` 复跑后 `impl/certs/` 51 份聚合 sha 与改前完全一致：`2f778721a278292d393512eb8fcf2b98c2bce4f5`）。
- 起因：R1 评审确认的第②条要害 —— `chk.py` 旧代码 `explicit = q.get("windows")` 优先于域约定推导，而域约定分支只覆盖 rma / domestic_newprod / quality_voc；其余 **32/51 题**（email 6、aibuy 6、public:\* 20）若抽掉 `q['windows']` 即 `underivable`。而这些 `q['windows']` 是主会话**从证书里物化出来的**，对该 32 题构成"用证书自己的值核对证书"的真实循环。

---

## 1. 改了什么

全部改动都在 `impl/asof_verifier/chk.py` 一个文件内（净增 237 行：2591 → 2828）。零新增依赖（仍是 stdlib ∪ {duckdb}），`ci_check.py` 的 `shared_internal_roots=[]` 红线不变。仓内其他文件（编译器、证书、题面、种子、`forge.py`、`ci_check.py`、`acceptance.py`）**一个字节都没动**。

| # | 改动 | 位置 | 说明 |
|---|---|---|---|
| 1 | 新增 `domain_window_periods(gv, q, roles, prescribed, overrides, binding_row)` | chk.py ≈L860 | **唯一的窗推导入口**。输入只有 `G_v` 治理表 + `D` 数据 + q 的**非窗字段**（`domain` / `metric` / `as_of` / `params.as_of_prev`）。函数体内**不出现** `q['windows']`。原 rma / domestic_newprod / quality_voc 三支原样迁入，新增 email / aibuy / public:\* 三支。 |
| 2 | 新增 `declared_window_periods(q, roles)` | chk.py ≈L800 | 把**题面呈现的窗坐标**单独隔离成一个函数：`q['windows']`（单期 dict 或多期 list）+ rma 旧式 `num_window` / `den_window` / `delta_windows`。这四个字段自此被统一归类为 *declared 输入*，而不是"结构化意图的一部分"。 |
| 3 | 反转优先级 | `derive_expected_alpha` | 先跑域约定；declared 只在①推导失败（`window_source=declared`）或②推导成功但与题面呈现不符（`window_source=declared-override`）时进入，并在 V0 的 PASS 文案与 JSON 报告 `independence.window_source` 里**明写**。静默采纳的路径已不存在。 |
| 4 | 角色集 R(q) 改由登记表定，不再读题面角色键 | `derive_expected_alpha` | 旧码用 `q['windows']` 的键名（`{numerator,denominator}` vs `{atom}`）决定度量是不是比率型 —— 这等于让（由证书回填的）题面自己选verifier要核对的元数。现在只认 β_v：绑定行规定了至少一条腿 ⇒ 比率；否则**元数未登记**，读作 atomic 并在报告里标 `arity_source`。 |
| 5 | 新增 I2'(a) 弹性角色分支 | `check_V0` | β_v(m)↑ 时元数不可独立判定，但 MC(i) 证书可以合法地呈现 `{num,den}` 空指派。这类证书的**角色名不再核对**（如实标注），**窗坐标仍逐角色核对**到域约定推出的窗。仅影响 2 题（见 §5）。 |
| 6 | 新增开关 `--no-declared-windows` | `main` / `verify(..., allow_declared_windows=)` | 彻底拒绝读任何题面窗坐标。这是本报告"真实独立性"数字的来源。 |
| 7 | 报告新增 `independence` 段 | `verify` | `{declared_windows_allowed, alpha_status, window_source, window_source_detail, arity_source}`。纯描述性，不参与 verdict。 |

### 1.1 三条新域约定（逐字）

**email —— as-of 包络约定**（`domain-convention:email-asof-envelope`）
依据的登记事实：`gov_valid_time_anchor` 两行均为 `anchor_type=snapshot_effective_date` + `effective_date=dt` 的事件时锚，`coverage_mode=hull_right_open`（半开包络）；`gov_temporal_binding` 三行 `rule=same_valid_time_window`（两腿共用**一个**窗）。
规则：`as_of` 为日 d ⇒ 点时刻累积包络 `(-inf, d]`；为月 ⇒ 该月半开窗 `[m01, next-m01)`；为年 ⇒ 该年半开窗。绑定行 `rule` 若不是 `same_valid_time_window`，约定不适用 → 交回 declared（fail-open 到"declared"，绝不猜窗）。

**aibuy —— as-of 累积窗约定**（`domain-convention:aibuy-asof-{cumulative|point}[来源]`）
依据的登记事实：锚为日粒事件时锚；`as_of` 必须是日坐标，否则不推。
规则：默认 `(-inf, d]`；登记行若登记了单日窗则取 `[d, d+1)`。窗规则的查表顺序：机器可读列（`window_rule`/`window_kind`/`request_window`，**当前种子一个都没有**）→ `rule` 值 → `note` 散文里的白名单 token（`single-day window` / `cumulative as-of window` / `单日窗` / `累积窗`）。命中散文时来源标 `registry-note`，命中不了标 `domain-default`。

**public:\* —— 点窗 + 快照锚有效期选表约定**（`domain-convention:public-asof-point`）
依据的登记事实：`gov_valid_time_anchor` 是**区间登记**型（每个版本快照一行，带 `valid_from`/`valid_to`/`snapshot_table`，**无** `effective_date` 列），`gov_temporal_binding.binding_rule` 登记"取 valid_from<=as_of<=valid_to 的快照表；无命中则拒答 out-of-validity"。
规则：区间登记的快照锚只容许点时刻读法 ⇒ 请求窗 = as-of 点 `[d, d+1)`；**哪张快照**实现它是覆盖问题（V2/OOV），不是窗问题。若 `gov_valid_time_anchor` 里查不到任何区间登记行，约定不适用。

---

## 2. 两种模式的验收数字（全部可复算）

| 模式 | 命令 | ACCEPT | window_source 分布 |
|---|---|---|---|
| 常规（允许 declared 兜底） | 见 §6 | **51 / 51** | `derived` 49、`declared-override` 2 |
| **严格 `--no-declared-windows`** | 见 §6 | **49 / 51** | `derived` 51（全部题都推出了窗；2 题推出的窗与证书不符 → REJECT） |

**改前基线**（同一套证书、同一批题，把 `q['windows']`/`num_window`/`den_window`/`delta_windows` 抽掉后跑旧推导 + 旧 V0，脚本 `old_baseline.py`）：**ACCEPT 16 / 51**。
即：**独立可核的窗坐标从 16/51 提到 49/51**；旧码下 32 题连推导都进不去（V0 直接 `no spec-anchored window convention for domain …`），另 2 题推导与题面不符、1 题角色集不符。

### 2.1 证伪测试（证明严格模式真的没在读题面）
`strip_and_run.py` 把六份 `questions.json` 里的 `windows` / `windows_note` / `num_window` / `den_window` / `delta_windows` **物理删除**（共删 102 个字段）后写到临时副本，再拿**未改动的证书**跑严格模式：结果 **ACCEPT 49/51**，与直接加 `--no-declared-windows` 的结果**逐题一致**。

两条静态断言（可 `grep` / AST 复核）：
- `grep -c 'qid *==' asof_verifier/chk.py` → **0**：推导器里没有任何逐题分支。
- AST 扫描 `domain_window_periods` / `registry_window_rule` / `derive_expected_alpha` 三个函数体，字符串字面量里**不出现** `windows` / `num_window` / `den_window` / `delta_windows` 任一键名（唯一读取点是被 `allow_declared` 闸住的 `declared_window_periods`，chk.py L762/792/800）。

### 2.2 有齿测试（证明新约定不是复读机）
`window_mutation_probe.py` 把每份证书 α 里的每个角色窗整体 **+1 天**，再跑严格模式：**51/51 全部 REJECT，全部由 V0 拒**，逐域 rma 6 / quality_voc 6 / domestic_newprod 7 / email 6 / aibuy 6 / public 20。新约定对窗坐标有实际约束力，不是恒真检查。

### 2.3 无回归
| 关口 | 命令 | 结果 |
|---|---|---|
| 常规全量 51 题 | `python3 /tmp/drive.py` | ACCEPT **51/51**（与改前同） |
| 伪造族 + BASE | `python3 asof_verifier/forge.py` | **PASS：3 BASE 全 ACCEPT，16 伪造全 REJECT 且逐条命中预期检查项**；`aux symdiff-57 audit: PASS` |
| 金标 + 现役等价性 | `python3 asof_compiler/acceptance.py` | gold **51/51**、legacy **51/51**（`sql_bytes_equal=27`）、良构自检 **0** 错、证书 51 份重出后 sha 不变 |
| 认证循环红线 | `python3 asof_verifier/ci_check.py` | PASS，`shared_internal_roots=[]` |

F1a / F1c / F1d 三个窗类伪造（都建在 rma 上，rma 改前就有域约定）现在明确是**与域约定推出的窗**比对后被拒的，拒因文案 `role numerator: window [2026-04-01, 2026-05-01) ≠ derived [2026-05-01, 2026-06-01)`；改前这条比对走的是题面窗（该域两者恰好相同）。F3d 的 AM(ii) 见证窗对仍与 `rma_q6` 的 `declared-override` 窗对比，属 §4 记录的 2 题之一。

---

## 3. 逐题 window_source（51 题全表）

`conv` 列是实际生效的约定标识；`strict` 列是 `--no-declared-windows` 下的判定。

| qid | domain | 常规 | window_source | 严格 | 约定 |
|---|---|---|---|---|---|
| EMAIL-ASOF-01…06 | email | ACCEPT | derived | ACCEPT | `email-asof-envelope` |
| AIBUY-Q1, Q2 | aibuy | ACCEPT | derived | ACCEPT | `aibuy-asof-cumulative[registry-note]` |
| AIBUY-Q3 | aibuy | ACCEPT | derived | ACCEPT | `aibuy-asof-point[registry-note]` |
| AIBUY-Q4, Q5, Q6 | aibuy | ACCEPT | derived | ACCEPT | `aibuy-asof-cumulative[domain-default]` |
| PUB-W-01…05, PUB-C-01…05, PUB-E-01…05, PUB-O-01…05 | public:\*（4 库 20 题） | ACCEPT | derived | ACCEPT | `public-asof-point` |
| NX-Q1…Q7 | domestic_newprod | ACCEPT | derived | ACCEPT | `domestic_newprod-cumulative` |
| QVOC-01, 02, 04, 05, 06 | quality_voc | ACCEPT | derived | ACCEPT | `quality_voc-daypoint` |
| QVOC-03 | quality_voc | ACCEPT | derived | ACCEPT | `quality_voc-month` |
| rma_q1, q2, q4, q5 | rma | ACCEPT | derived | ACCEPT | `rma-month` |
| **rma_q3** | rma | ACCEPT | **declared-override** | **REJECT** | `rma-month`（推出单期 2026-05，题面呈现双期 2026-03 \| 2026-05） |
| **rma_q6** | rma | ACCEPT | **declared-override** | **REJECT** | `rma-month`（推出两腿同窗 2026-05，题面呈现分母腿 2026-04） |

---

## 4. 仍需 declared 输入的题目（2 题）+ 缺的是哪条治理登记

| qid | 缺什么 | 为什么不能靠约定补 | 缺的登记 |
|---|---|---|---|
| `rma_q3` | **期序**（要对比哪两个月：2026-03 vs 2026-05） | 域约定只能从 `as_of=2026-05` 推出**单期**当月窗。"和三月比"这件事只写在题面自然语言里；`rma_q1`（同 metric、同 as_of、不同 SKU）与它在 (G_v, D, as_of, metric, domain) 上**完全同构**，任何只看这四项的规则都无法区分二者。 | 结构化题面规格 κ：需要一个 `delta_periods` 之类的**机器可读期序字段**（现役编译器把它藏在 `adapters.py` 的 `QSPEC` 字典里，自记为缺口 **G-2**"κ 的退化解析"）。 |
| `rma_q6` | **分母腿的异窗承诺**（分子 2026-05、分母 2026-04） | 这正是该题要测的 AM(ii) 跨窗错配：请求本身**故意**违反 `same_valid_time_window`。域约定按登记的 rule 推出两腿同窗；"用四月的分母"是用户意图，不是治理约定。 | 同上 κ（`QSPEC` 里的 `num_window`/`den_window`，同属 G-2）。另外 C4 定义 4.6 的"刚性窗承诺"目前没有对应的题面字段格式。 |

**没有为这两题硬造约定。** 可以造出一条"若 metric 是 problem_rate 且 SKU=EC1-BLK 则双期"的规则让数字变成 51/51，那是把证书的值搬进推导器换个地方藏，与本轮目标相反。

同时如实记：这两题在**常规模式**下仍然是用题面窗过的（`declared-override`），而它们的题面窗与本轮所有其他题的题面窗一样，是主会话从证书物化出来的。**对这 2 题，循环没有被打破，只是被标注出来了。**

---

## 5. 另一条如实降调：2 题的**角色元数**不可独立判定

`AIBUY-Q5`（`reco_grounding_coverage_rate`）与 `QVOC-06`（`complaint_rate_global_recompute`）都是 MC(i) 拒答：治理图里**没有登记这两个度量的率值口径**（前者绑定行两腿锚皆 NULL，后者根本没有绑定行）。于是 β_v(m)↑，verifier 无法从 G_v 判断该度量是原子型还是比率型，而证书按 I2'(a) 呈现 `{numerator, denominator}` 空指派。

处理：这 2 题的**角色名不核对**（V0 文案明写 `arity NOT independently checked (β_v(m)↑, I2'(a) elastic role set)`），**窗坐标照常核对**。其余 49 题的角色集全部由 β_v / 登记行判定并严格核对（多一个角色即 REJECT，见伪造族 F2b）。

这不是本轮新引入的弱化：改前该坐标是从 `q['windows']` 的键名读的，也就是从证书回填值读的 —— 现在只是把"读不出来"如实说出来了。

---

## 6. 复算方式

```bash
cd "/Volumes/SSD 1/explore_opportunity_cc/impl"

# 单题（新开关）
python3 asof_verifier/chk.py --cert certs/EMAIL-ASOF-01.json \
    --questions ../pilot/domains/email/questions.json --qid EMAIL-ASOF-01 \
    --db ../pilot/domains/email/warehouse.duckdb --no-declared-windows
# 输出首行后新增：window_source=derived  arity_source=beta_v(...)

# 全量两模式 / 证伪 / 有齿 / 改前基线（脚本在本轮 scratchpad，可原样重建）
python3 drive2.py                 # 常规      -> ACCEPT 51/51
python3 drive2.py --strict        # 严格      -> ACCEPT 49/51
python3 strip_and_run.py <dir> --strict   # 物理删窗字段后 -> ACCEPT 49/51
python3 window_mutation_probe.py  # 窗+1天    -> 51/51 全 REJECT(V0)
python3 old_baseline.py           # 改前基线  -> 16/51

# 回归四关
python3 /tmp/drive.py ; python3 asof_verifier/forge.py
python3 asof_compiler/acceptance.py ; python3 asof_verifier/ci_check.py
```

脚本位置（本轮产出，非仓内制品）：
`/private/tmp/claude-502/-Volumes-SSD-1-explore-opportunity-cc/e84860c5-a95a-456e-9d2c-eda7b795ebc7/scratchpad/{drive2,strip_and_run,window_mutation_probe,old_baseline,probe_derive}.py`
**建议**：把 `drive2.py --strict` 与 `window_mutation_probe.py` 固化进 `forge.py` / CI，否则本报告的 49/51 与 51/51-有齿 两个数字下次没人复跑。

---

## 7. 独立性边界陈述（供论文直接引用）

> **中文（如实版）**
> 独立校验器与编译器不共享任何工程内部模块（`ci_check.py` 机器断言：两侧 import 根交集为空，校验器依赖 ⊆ stdlib ∪ {duckdb}），窗算术、覆盖计算、守卫谓词与对称差审计均按规范文本另写一份。角色窗 ω_r 由**域的 as-of 约定**在 (G_v, D, q 的非窗字段) 上重新推出：51 题中 **49 题**的窗坐标在 `--no-declared-windows` 模式下（该模式拒绝读取题面提供的任何窗坐标）被独立推出并逐坐标核对通过；把题面里的窗字段物理删除后复跑，结果逐题一致。**其余 2 题（`rma_q3` 的双期期序、`rma_q6` 的故意异窗分母）的窗坐标来自题面呈现，校验器对这 2 题不构成独立核对**：它们的期序/异窗承诺只存在于问题的自然语言中，本试点的结构化题面规格（κ）尚未把它登记为机器可读字段（缺口 G-2）。另有 2 题（`AIBUY-Q5`、`QVOC-06`）因治理图未登记其率值口径（β_v(m)↑），其**角色元数**不可独立判定，校验器只核对窗坐标而不核对角色名。域的 as-of 约定本身写在校验器代码里（与 rma/quality_voc/domestic_newprod 三域同级），G_v 目前**没有**承载它的机器可读列；aibuy 的"单日窗 vs 累积窗"判别当前读自 `gov_temporal_binding.note` 的登记散文，这是登记缺口而非设计选择。

> **English (honest version)**
> The verifier shares no project-internal module with the compiler (mechanically asserted: empty intersection of import roots; verifier dependencies ⊆ stdlib ∪ {duckdb}), and re-implements window arithmetic, coverage, guard predicates and the symmetric-difference audit from the specification text. Role windows are re-derived from the domain's as-of convention over $(G_v, D)$ and the question's non-window fields. Under `--no-declared-windows`, which refuses every window coordinate presented by the question, **49 of the 51** certificates verify against independently derived windows, and physically deleting the window fields from the question files reproduces that result question by question. For the remaining **2** (`rma_q3`'s two-period comparison, `rma_q6`'s deliberately misaligned denominator leg) the window coordinate comes from the presented question and the check is *not* independent: those commitments live only in the natural-language question, and the pilot's structured question spec does not register them machine-readably. For 2 further questions the metric's *arity* is not registered in $G_v$ ($\beta_v(m)\uparrow$), so the verifier checks their windows but not their role names. The domain conventions themselves live in verifier code — at the same level as the three domains that already had one — because $G_v$ carries no machine-readable column for them; for one aibuy metric the day-vs-cumulative rule is currently recovered from the registry row's prose note, which we record as a registration gap.

### 7.1 论文两处不实陈述的修订建议

| 位置 | 现文 | 问题 | 建议 |
|---|---|---|---|
| `sections/07-system.tex:61` | "It consumes certificate *contents*, never compiler internals: **no question specification objects**, no templates, no call into the compilation entry point." | 校验器**必须**读结构化问题 q（`Chk(C,G_v,D,ctx)` 的 q 就是 questions.json 行），旧码还从 q 读窗坐标。"no question specification objects" 与签名自相矛盾且不实。 | 改为："It consumes the certificate, the structured question, and $(G_v,D,\ctx)$ — never compiler internals: no templates, no shared module, no call into the compilation entry point. The question is read for its *intent* fields (domain, metric, as-of, scope parameters); its window coordinates are re-derived from the domain's registered as-of convention rather than consumed, and the `--no-declared-windows` mode reports how much of the corpus verifies without reading them at all（49/51）." |
| `sections/06-certificates.tex:82` | "**V0** the anchor assignment role by role, **through an independently written window arithmetic**" | 窗**算术**确实是另写的（`w_norm/w_eq/w_subset/w_hull` 等），这半句为真；但读者会读成"窗**值**也是独立推出的"，而改前 32/51 题的窗值直接取自 q。 | 改为："**V0** the anchor assignment role by role, through an independently written window arithmetic **and an independent re-derivation of each role window from the domain's registered as-of convention** (Sec.~\ref{sec:eval}: 49/51 under `--no-declared-windows`; the 2 exceptions are questions whose window commitment is stated only in natural language)" |

---

### 7.2 一条必须一并说出的作者性限制

本轮三条新域约定是**在本会话内、在能看到证书与金标的情况下**写的。因此"独立"在本文里只能是**机器可检验的那一层**：

- 可机器检验、且已检验：运行期不读证书、不读题面任何窗坐标（§2.1 物理删字段复跑逐题一致）；约定按域统一、不含逐题分支（代码里 6 个域分支、0 处 qid 判别，可 `grep -c 'qid ==' chk.py` 核 = 0）；约定对窗坐标有约束力（§2.2 全部 +1 天变异被拒）。
- **不可**机器检验、因而**不主张**：约定的"盲写性"。写的人见过被检验的制品，理论上可能无意识地朝制品调参。唯一能压制这一点的是"一条约定管一个域、不为个别题开口子"这条自律，以及 §4 里两题**宁可 REJECT 也不补规则**的处理 —— 补一条规则就能凑到 51/51，本轮明确没补。

论文若要主张更强的独立性，需要的是**换人/换时序**（约定先于制品冻结、或由不接触制品的第三方另写），而不是再改代码。

---

## 8. 遗留 / 建议

1. **把约定登记进 G_v**：给 `gov_temporal_binding` 加 `window_rule`（`point` / `cumulative` / `granule`）与 `metric_kind`（`atomic` / `ratio` / `scoped_ratio`）两列，`chk.py` 的查表顺序已经预留（机器可读列优先），加列即可让 aibuy 的 `registry-note` 与 2 题的 `arity 未登记` 一并消失。
2. **补 κ 的机器可读期序/刚性窗字段**，`rma_q3`/`rma_q6` 才可能进入 `derived`。在那之前，论文不应把这 2 题算进"独立核对"的分母。
3. **把严格模式与有齿测试固化进 CI**（见 §6）。
4. 本轮**未触碰**评审的第①条（`run_pilot.py` 的 `extract_sql` 围栏顺序）与第③条（披露支柱零实例），二者由其他线负责。
