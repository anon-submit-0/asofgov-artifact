# PREREG · pilot2 LLM 臂全集（8 臂 × 60 题，公开基座终局实证）

> **状态：FROZEN 2026-08-04，写于任何针对 pilot2 的 LLM 调用之前。**
> 本文件写就时 `pilot2/runs/` 目录**不存在**，8 个 LLM 臂一次调用也未发生；
> 本预注册阶段（含提示物料打包、泄漏审计、哈希冻结）**LLM 调用次数 = 0**。
> 任务来源：作者裁定"论文只用公开数据证据"后，重跑 LLM 各臂——论文实证节最后一块。
> 冻结的目的：8 臂结果直接决定论文 Table 2 与头条对照；若不先写死"每臂喂什么 /
> 怎么评分 / 三种结果各自怎么改写论文"，事后任何调整都等于调参到想要的结论。
>
> **上游冻结面（本协议只读引用，不改一字节）**：`pilot2/DESIGN_SPEC.md`（基座规范）、
> `pilot2/BUILD_REPORT.md`（建仓）、`pilot2/ACCEPTANCE_REPORT.md`（验收：编译器金标 60/60、
> 校验器 ACCEPT 60/60、严格轨 50/60、30 伪造全拒、certs2 已在册）、
> `pilot/PREREG_governance_arm.md`（B6 原协议——本文件 §3 是其 ND-4 重挂）。
> **本文件与工件冲突时以工件为准**：§2/§3 的装配行为由
> `prompt_pack/build_prompt_pack.py` 定义并已产出冻结包，本文是其可读镜像。

---

## 0. 冻结基线与哈希（全部由本机 sha256 复算，非手抄）

| 工件 | sha256 |
|---|---|
| `pilot/run_pilot.py`（冻结 runner，**本轮不修改一个字节**；与 B6 §0 冻结值逐字节一致） | `fecda681ccce203fa08e1a8b28a8ff722093a50ce656c62e86d921b5949309ef` |
| `~/.claude/skills/llmhub/bin/llmhub.py`（与 B6 冻结值一致） | `f3dba7e05b2c089ebd1675b1e7b075c3813136c974192b791db27c68506c1847` |
| `~/.claude/skills/llmhub/channels.json`（与 B6 冻结值一致） | `d8d49e05decee5f517f41ee92f123a5a8560637bb49fe4b48e80fab8c4d9b127` |
| `pilot2/prompt_pack/build_prompt_pack.py`（本次新增并冻结） | 见 `FREEZE_pilot2_arms.json` |
| `pilot2/prompt_pack/MANIFEST.json` | `c3618be218d922a62fa05d439c37c46ff48bd40a0c6373ae104e36ad48b51009` |
| 9 库 `questions.json` + 90 份 `gov_seed/*.jsonl` **排序串接聚合** | `d3258d3e83d0d2d01555382283be754a7353087b1d76d0e39a046bc67bad0e68`（= 建仓自报整链值，逐字节复现；配方：`cat $(ls domains/*/questions.json domains/*/gov_seed/*.jsonl \| sort) \| shasum -a 256`） |
| 9 库 `warehouse.duckdb`、9+90 份逐文件哈希、18 份 prompt_pack 包 | 逐项见 `pilot2/FREEZE_pilot2_arms.json` |
| 本协议自身 | 写入 `FREEZE_pilot2_arms.json`（该文件在本文最后一次编辑之后生成，用作篡改留痕：本文此后若被修改，该项即不再匹配） |

> **完整哈希清单一律以 `pilot2/FREEZE_pilot2_arms.json` 为准**——脚本生成，不经人手转抄；
> 该 JSON 亦记录 `llm_calls_at_generation_time = 0` 与 `runs_dir_exists_at_freeze = false`。
>
> 对照锚点（全部取自已冻结的 `ACCEPTANCE_REPORT.md`，本轮**不重跑不重评**）：
> mechanism（确定性编译器，certs2）金标 60/60、校验器 ACCEPT 60/60 → **error_rate = 0/60**；
> 题集构成 value 33 / rewrite 12 / refusal 15；拒因 OOV 4 / AM 5 / MC 3 / DB 3；
> 簇预算 fin 8 / f1 8 / card 7 / code 7 / deb 7 / ca 6 / ef2 6 / th 6 / w1 5（9 簇 = 60 题）。
> 旧 pilot（51 题企业+旧公共轨）的全部数字自本轮起**只作动机与附录**，不进结果表。

---

## 1. 臂表与逐臂参数 —— 一切与 B6/旧协议一致处直说继承

### 1.1 臂表（8 个 LLM 臂 × 60 题 = 480 次入账调用；mechanism 零调用）

| 臂 | 模型 | 渠道（llmhub 注册表首命中；跑前 A1 断言） | `{extra}` 槽位 |
|---|---|---|---|
| `baseline_claude` | `claude-opus-4-6` | `tuzi`（`['tuzi','tokens1688']` 首位） | `""` |
| `baseline_qwen` | `qwen3-coder-next` | `gateway` | `""` |
| `baseline_deepseek` | `deepseek-3.2` | `gateway` | `""` |
| `baseline_minimax` | `minimax-m2.5` | `gateway` | `""` |
| `trivial_claude` | `claude-opus-4-6` | `tuzi` | `TRIVIAL_NOTE`（115 字符，sha16 `c3dee63a1f45c5a9`） |
| `trivial_v2` | `claude-opus-4-6` | `tuzi` | `TRIVIAL_V2_NOTE`（226 字符，sha16 `6de5f288aa4448fb`） |
| `trivial_v3` | `claude-opus-4-6` | `tuzi` | `TRIVIAL_V3_NOTE`（187 字符，sha16 `775f3f5dda2611eb`） |
| `governance_informed` | `claude-opus-4-6` | `tuzi` | `TRIVIAL_V2_NOTE + <db>.gov.txt`（§3；ND-4 重挂） |
| `mechanism` | 确定性编译器 | —（零 LLM 调用） | —（结果 = certs2 验收，§0 锚点） |

三个提示变体的 note 文本**逐字节继承** `run_pilot.py` 顶部常量（不为 pilot2 改写一字——
它们提到的 `gov_valid_time_anchor` / `gov_temporal_binding` 表在 pilot2 十表中同名存在，
语义兼容）。臂名与旧 pilot 完全一致，论文表格逐列可对映。

### 1.2 公共参数（8 个 LLM 臂逐项相同；除标注外全部继承自 `run_pilot.llm()` 与 llmhub 缺省）

| 项 | 取值 | 继承性 |
|---|---|---|
| 调用方式 | `source .work/env.sh` 后 `python3 ~/.claude/skills/llmhub/bin/llmhub.py chat --model <M> --prompt <P>`，经 `run_pilot.llm()` **import 原样调用** | 与 B6 逐字节相同 |
| temperature | **不发送**（请求体只含 `model` / `max_tokens` / `messages`，llmhub.py `call()` 实测如此），由渠道默认值决定 | 继承 |
| max_tokens | **512**（llmhub `chat` 缺省；不传 `--max-tokens`） | 继承 |
| HTTP 超时 | **60 s**（llmhub 缺省 `--timeout`） | 继承 |
| 子进程超时 | **180 s**（`run_pilot.llm()` 的 `subprocess.run(timeout=180)`） | 继承 |
| 重试 | `retries=2` → 最多 **3 次尝试**；仅在输出为空（超时/空文本）时重试，**不因内容不满意重试** | 继承 |
| 空响应 | 三次仍空 → `raw=""` → `kind="no_sql"` → 计错 | 继承 |
| 并发 | 臂内 `ThreadPoolExecutor(max_workers=4)`；臂间**串行**，顺序 = §1.1 表序（素基线 4 → 变体 3 → 治理臂） | 继承（臂序为本轮新冻结项） |
| 回合数 | **单回合**：首个响应即终局，无执行反馈、无修复轮 | 继承 |
| 提示模板 | `run_pilot.PROMPT` 原样（217 字符，sha16 `4a2aaf1d0b010c56`，含"可拒答"条款；所有臂共享同一模板与同一拒答许可——公平性条款） | 继承 |
| 题目集与枚举序 | `pilot2/domains/` 下 `sorted()` 9 目录 × 各自 `questions.json` 数组序（60 题；无 `public/` 目录） | 结构继承，题集为 pilot2 |
| 数据库 | 各域 `warehouse.duckdb`，`duckdb.connect(read_only=True)`，经 `run_pilot.run_sql()`（数值金标）或 §4.2 行集取数（6 道非数值金标） | 继承 + §4.2 扩展 |
| 响应缓存 | `pilot2/runs/<arm>/<qid>.json`：`{qid, system, kind, value, verdict, raw[:2000], sql, prompt_sha256, prompt_chars, empty_response}`——**prompt_sha256/prompt_chars 对全部 8 臂记录**（B6 只对治理臂记，本轮推广到所有臂；不改变任何评分） | 继承 + 留痕推广 |
| RAW_CAP / REL_TOL | 2000 / 0.005 | 继承 |
| 运行器 | `pilot2/run_pilot2_arms.py`（运行阶段新写）：**import `run_pilot`，不复制其任何函数**；只提供 pilot2 路径装配、§4.2 扩展评分、`runs/` 写入 | 结构同 `run_gov_arm.py` |
| 调用预算 | **480 次入账**（8×60）；另许每个不同模型 ≤1 次两字连通性探针（≤4 次，不写任何缓存）；重试不增加入账题数 | B6 同款探针条款 |

**不得触碰**：旧 `pilot/runs/`、`pilot/pilot_summary.json`、`pilot/runs_gov/`、`impl/certs2/`、
`pilot2/domains|build|ci|prompt_pack/` ——全部只读（§7 A6 跑后哈希断言）。
磁盘纪律：一切写盘在 `/Volumes/SSD 1/explore_opportunity_cc` 下，每个 shell 先 `source .work/env.sh`。

---

## 2. 素基线与变体的 prompt 装配（含禁投字段清单）

### 2.1 装配式（对 8 个臂统一，唯一变量是 `{extra}`）

```
prompt = run_pilot.PROMPT.format(
    schema  = prompt_pack/<db>.schema.txt,     # 本域全部题共享，逐字节相同
    extra   = §1.1 表列值,                      # ""|NOTE|V2|V3|V2+gov
    question= q["question_zh"])                 # 题面唯一入口，逐字原样
```

### 2.2 schema 包（`<db>.schema.txt`，已产出冻结）

从该域 `warehouse.duckdb` 确定性导出：`main` schema **全部表**（业务表 + gov_* 十张登记表）
按表名字典序，每表一行 `CREATE TABLE main."<t>"("<c>" <TYPE>, …);`（标识符一律双引号，
列按物理序）+ 一行行数注记 `-- rowcount main."<t>" = N`，文件头两行来源注释。
**gov_* 表入 schema 是继承而非新让利**：旧 pilot 的 `schema.txt` 同样列出治理表，
素基线在两代基座下拥有同等的"自行 SQL 查询治理表"权利（单回合内）。
9 份尺寸 2,833–7,371 字符，哈希见 `MANIFEST.json`。

### 2.3 禁投字段清单（A2 泄漏闸，适配 pilot2 字段分区）

pilot2 `questions.json` 的 26 个字段按 `ci/leak_check.py` 冻结分区为评测可见集（16）
与金标侧集（10），两集不交。**进入提示的只有 `question_zh` 一个字段**；其余逐条：

**(a) 金标侧 10 字段 —— 一律不得进入提示、不得参与选行、不得影响任何分支**：

1. `gold_value` —— 金标值
2. `gold_sql` —— 金标 SQL
3. `expected_kind` —— 应答/应改写/应拒
4. `refusal_reason` —— 拒因类（out-of-validity / anchor-mismatch / missing-caliber / disclosure-blocked）
5. `refusal_subtype` —— 拒因子型（am_i–iv / mc_i–ii）
6. `rewrite` —— 改写金标（kind / requested / effective）
7. `windows` —— 显式窗口坐标 ω_r（C3 A5 一等字段，只供校验器比对）
8. `windows_note`
9. `notes` —— 建仓注记（含双路径 blind 值等）
10. `metric` —— σ 的指标键（pilot2 把它划入金标侧；**也不得用作治理包选行谓词**，§3.2）

**(b) 评测可见但非题面的 15 字段 —— 不得以独立字段形式注入提示**：
`qid, domain, as_of, declared_at, metric_alias, scope, pinned_version, cross_window,
anchor_override, window_request, requested_granularity, requested_time_gran,
presentation, ctx_role, periods`。
这些是编译器/校验器消费的结构化意图 σ 与机器侧登记；声明时点/as-of/跨窗祈使/钉版本等
信息**本来就写在 `question_zh` 的自然语言里**，那是 8 臂共见的同一段文本——LLM 臂只许
从题面自然语言里读它们，与 mechanism 读结构化 σ 形成"同信息、异形态"的公平对照
（继承 B6 §2.5 第 10 条的裁定）。

**(c) 环境侧禁投**：`impl/certs2/*`（证书）、`impl/asof_compiler/*`（含 QSPEC/适配器）、
旧 pilot 任何 `runs*/`、任何既有臂表现摘要、`pilot2/build/questions_def.py` 等出题定义件。

### 2.4 A2 字符串级泄漏断言（**已于冻结前实跑，跑时复跑**）

对每题以**最大超集提示**（governance_informed 的完整装配）做逐字符串比对：
`gold_sql`、`json.dumps(windows)`、`windows_note`、`notes`、`json.dumps(rewrite)`、
`refusal_reason`、`str(gold_value)` 不得出现；长度 <8 的串跳过并记录
（单个数字如 `16` 当然会出现在行数注记里，非泄漏——B6 同款护栏）。
**2026-08-04 冻结前实测：60 题 × 7 字段命中 0；数值金标字面（≥8 位）弱检查命中 0**；
短串跳过 22 项（全部为数值金标短字面），如实记录于本条。
**较 B6 的强化**：`refusal_reason` 本轮**列入**断言——pilot2 种子经 ND-2 闸保证
不含裁定类别 token（grep 四类拒因串于 90 份种子 = 0 命中，冻结前实测），
故不存在 B6 时"治理 note 原文即含 REFUSE 判据"的豁免理由。

---

## 3. 治理知情臂：治理包构建规则（ND-4 —— B6 原协议重挂 pilot2）

**重挂声明**：臂定义、唯一变量（`extra = TRIVIAL_V2_NOTE + 治理块`）、二因子对照读法
（`trivial_v2 − baseline_claude` = 指令；`governance_informed − trivial_v2` = 治理内容）、
评分与"只跑一次"纪律全部继承 `pilot/PREREG_governance_arm.md` §1/§4/§6；
本节只重定义**治理块的来源与序列化**（旧包读企业 warehouse 的 gov 表，新包读 pilot2 种子）。

### 3.1 来源与打包单位

- 来源 = `pilot2/domains/<db>/gov_seed/*.jsonl` **十表全量**（DESIGN_SPEC §3.1 schema 法登记表；
  jsonl 即种子真源，与 warehouse 内 gov_* 表已由验收对账 847 = 847 行）。
- 打包单位是**库（目录）**，不是题目：同库所有题拿到逐字节相同的治理块，
  与 schema 包共享方式一致。域越界守卫：任何带 `domain` 字段的行其值必须等于目录名，
  否则打包器 `SystemExit`（实测：零越界）。
- **不按 `metric`/`metric_alias` 选行**（继承 B6 §2.1 裁定）：按题选行等于把 σ 的路由能力
  搬进本臂；路由留给模型在 122 条 metric、130 条绑定行里自己做——比按题喂更难，
  偏差方向对我方不利。

### 3.2 块清单与固定序（P0→P9 = 解析链序；截断丢块从 P9 反向开始）

| 序 | 登记表 | 内容（全部为 DESIGN_SPEC §3.1 白名单语汇：标识符/列名指针/闭枚举/谓词原子/披露参数/commit 元数据） |
|---|---|---|
| P0 | `gov_semantic_graph_version` | 版本轴：`(committed_at, commit_seq)` 全序，T→ver(T) 的唯一依据 |
| P1 | `gov_metric_alias` | 表面词→metric（**随版本变**，取错版本即撞干扰行） |
| P2 | `gov_metric` | 指标登记 |
| P3 | `gov_measure_def` | 度量/谓词关系原子（口径本体；无可粘贴 SQL） |
| P4 | `gov_caliber_routing` | 口径路由（via 对象 + join 键列名 + 归因对齐） |
| P5 | `gov_valid_time_anchor` | 有效时间锚：`effective_col`/`vf_col`/`vtc_col` **列名指针** + `coverage_mode`（**无覆盖区间字面量**——覆盖域不物化公理） |
| P6 | `gov_temporal_binding` | 绑定规则（腿→锚 + `rule_id` 如 `same_valid_time_window`） |
| P7 | `gov_semantic_node` | 节点→物理表 |
| P8 | `gov_granularity_edge` | 粒度格（实体/时间轴上卷边） |
| P9 | `gov_disclosure_policy` | 披露策略（π/k/mask/γ；非治域文件为空 → 块如实呈现 `rows=0`） |

### 3.3 序列化（逐字节确定；`build_prompt_pack.py` 为准）

```
\n## 治理元数据（本库 gov_* 登记表全量导出；与具体问题无关，同库所有问题看到的内容完全相同）\n
-- 来源：<db>/gov_seed/*.jsonl（DESIGN_SPEC §3.1 十表 schema 法）；版本轴见 gov_semantic_graph_version\n
-- 每个块 = 一张登记表，一行一个 JSON 对象，行按文本字典序排列\n
\n-- TABLE <t>  (rows=<n>)\n<行…>\n …（块按 P0→P9）
```

行渲染 `json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)`，行按文本字典序
`sorted()`；重跑打包器已验证**逐字节一致**。

### 3.4 截断规则 GOV_CAP（确定性，非临场判断；继承 B6 §3 全文）

`GOV_CAP = 32000`（只约束治理块；schema 与 TRIVIAL_V2_NOTE 不计入）。超限时先整块丢弃
最低优先级（P9→P1，记 `dropped_blocks`），只剩一块仍超限则按既定字典序保留整行至
`GOV_CAP − 表头 − 300`，末尾追加固定标记
`-- [TRUNCATED@GOV_CAP=32000] dropped_blocks=[…]; kept_lines_in_last_block=<k>/<N>`。
**实测：9 库全部未触发**（最大 `codebase_community` 23,132 字符 = 上限的 72.3%；
`MANIFEST.json` 9 项 `truncated` 全 `false`）。上限继承 B6 数值且仍留 ≥27% 余量，
选定依据是本地输入尺寸，与任何模型输出无关。

### 3.5 实测包尺寸与提示长度（`MANIFEST.json`；§7 A4 断言基准）

| 库 | 治理块字符 | 块数 | schema 字符 | 治理臂提示 min–max |
|---|---:|---:|---:|---|
| california_schools | 12,530 | 10 | 4,946 | 17,941–17,970 |
| card_games | 18,295 | 10 | 5,194 | 23,949–24,029 |
| codebase_community | 23,132 | 10 | 4,660 | 28,256–28,279 |
| debit_card_specializing | 15,932 | 10 | 3,458 | 19,854–19,886 |
| european_football_2 | 17,438 | 10 | 7,371 | 25,279–25,317 |
| financial | 19,211 | 10 | 3,825 | 23,505–23,523 |
| formula_1 | 21,416 | 10 | 5,236 | 27,122–27,163 |
| thrombosis_prediction | 16,034 | 10 | 3,892 | 20,390–20,415 |
| world_1 | 12,874 | 10 | 2,833 | 16,176–16,181 |

60 题提示总长（字符）：素基线四臂各 **292,332**；trivial_claude **299,232**；
trivial_v2 **305,892**；trivial_v3 **303,552**；governance_informed **1,372,803**。
逐包 sha256 见 `MANIFEST.json` / `FREEZE_pilot2_arms.json`。

### 3.6 已知让利与机理声明（跑前写死，论文必须披露）

- **结构上已消除的旧让利**：pilot2 种子经 ND-2 不含 `select_expr`/`where_expr`/
  `snapshot_table`/覆盖区间字面量/裁定类别 note——B6 时代 public 簇"绑定给表达式、
  锚给快照表"的退化查表路径**不可表达**；这正是 ND-4 要检验的设计主张。
- **仍然让利的部分（刻意，如实自曝）**：绑定规则、锚列名指针、版本轴、别名映射、
  谓词原子、披露参数（k 值/掩码类/粒度格）全部原样给出，并配 `TRIVIAL_V2_NOTE` 显式
  使用指令。治理臂成绩应读作"上下文内治理 + 指令"的**上界**，不是未调优对手。
- **机理预测的依据**（DESIGN_SPEC §3.3）：正确作答须走通版本解析→别名→度量→路由→
  锚/窗推导的 4–6 步符号间接解析（每步有版本过滤与 ND-3 干扰行，全库占比 57.1%），
  以及对 OOV 判空/MC(ii) 分母质量/披露小胞 k 计数/AM(iv) 对称差的**数据探针**——
  后者在单回合无执行下原理上不可判（ND-1 见证对 8/8 已物化：同种子异数据翻转标签）。

---

## 4. 评分 —— 对全部 9 臂（8 LLM + mechanism）统一，不为任何臂另立标准

### 4.1 判定链（继承，import 不复制）

`is_refusal()`（2026-08-03 修复版：剥围栏、容前置散文 ≤6 行、装饰符/全半角冒号/任意大小写）
→ `extract_sql()` → REFUSE / 第一条语句执行（read_only）/ 无 SQL；六分类 verdict：
`correct | wrong_value | execution_error | answered_should_refuse | refused_should_answer | no_sql`。
LLM 臂拒答**不要求理由匹配**（继承；mechanism 的理由匹配已在 certs2 验收里完成）。

### 4.2 金标形态分派（本轮唯一评分扩展；60 题逐题冻结，运行期不得改派）

pilot2 金标三形态。数值金标沿用 `run_pilot.score()` 原文；新增两形态只覆盖 **6 道题**：

| 形态 | 题数 | 题号 | 取数 | 判对规则 |
|---|---:|---|---|---|
| 数值（value 33 + rewrite 6） | 39 | 其余全部 | `run_pilot.run_sql()` 首行首列 | `run_pilot.score()` 原文：gold==0 时 `abs≤1e-9`，否则相对误差 ≤ REL_TOL=0.005 |
| 行集（rewrite/rollup） | 4 | CA-Q5, CODE-Q4, DEB-Q5, TH-Q3 | `fetchall()` 全行 | **多重集合相等，行序无关**；逐格：可数值化格按 REL_TOL 比，其余格 `str.strip()` 精确等；行元数须一致。**宽赦条款**：金标恰 1 行且恰 1 个数值格时，返回 1×1 标量命中该数值亦判对 |
| 字符串（rewrite/mask） | 2 | CODE-Q6, TH-Q4 | 首行首列 | 双方可数值化则按 REL_TOL 比（TH-Q4 "1934"），否则 `str.strip()` 精确等（CODE-Q6 "UK"） |

**数值化谓词**（冻结）：`float(str(x))` 成功即数值。取数异常 → `execution_error`；
空行集 → `execution_error`；`REFUSE` 于非 refusal 题 → `refused_should_answer`。
缓存重评分（`rescore_cached` 语义）对 6 道扩展题由 `run_pilot2_arms.py` 以同一分派
实现——评分是缓存 raw 的纯函数，修分永不重询模型。

**让利声明（跑前写死，论文披露）**：
(a) rewrite 12 题**不要求 LLM 宣告改写**——只按改写后金标值判对；mechanism 则须出具
含改写披露的证书才算数（certs2 已验）。方向 = 加强对手。
(b) 行集宽赦条款使朴素全局聚合在 DEB-Q5/TH-Q3/CA-Q5 上无标签也可判对。方向同上。
(c) **hull_trim 5 题（CARD-Q5, EF2-Q4, FIN-Q6, F1-Q6, W1-Q4）对朴素作答者天然易**：
hull 外无数据行，朴素全窗聚合与裁剪窗聚合数值相等。此为如实预告，不改题不改分——
但 §4.4 的按形态分片报告为**强制**，头条数字不得被这 5 题的白送分粉饰。

### 4.3 拒答统计（pilot2 分母）

- `correct_refusals` = #{expected_kind=refusal 且 verdict=correct}，**分母 15**；
  按拒因分报 OOV 4 / AM 5 / MC 3 / DB 3。
- `over_refusals_on_answer_questions` = #{expected_kind≠refusal 且 verdict=refused_should_answer}，
  **分母 45**（= value 33 + rewrite 12）。
- `coverage.answered` = #{kind∈{value,error}}/60；`coverage.refused` = #{kind=refuse}/60。

### 4.4 统计与对照（跑前写死）

- **簇自助**：**9 簇**（= 9 库）整簇有放回重采样，`B=2000`，每臂各自新建
  `random.Random(20260731)` → 各臂抽样序列**逐次相同**（公共随机数，配对比较友好；
  与 B6 单臂做法一致的种子纪律）。CI95 = 排序后 `[rates[49], rates[1949]]`。
- **强制分片报告**：逐簇（9）× 逐金标形态（value/rewrite/refusal）× 逐拒因（4）——
  三张分片表全部落 `pilot2_arms_summary.json`，不许只报总数（§4.2(c) 与 §3.6 的原因）。
- **对照参考** = `baseline_claude`；对每臂报 `elim_<arm>` = 该臂答对的 reference 错题比例；
  对 `governance_informed` 另报与 `baseline_claude`、`trivial_v2` 的配对不一致计数
  b/c（**只报计数，不报 p 值**；n=60、9 簇，不主张显著性）。
- **mechanism 0/60 直接取自 certs2 验收**，本轮零调用零重评；`elim_mechanism = 1.0` 恒等。
- **公开基座三判据（新预注册的描述性判据，不是旧 A/B/C 闸的重跑**——旧闸裁定
  已冻结于旧 pilot，不因本轮任何结果变更）：
  - **A′**：min(4 个素基线 error_rate) ≥ 0.30；
  - **B′**：mechanism error_rate = 0 且 elim = 1.0（已由 certs2 保证，只作陈列）；
  - **C′**：max(3 个 trivial 变体 elim) < 0.40（0.40 = 冻结 C 判据同一条线）。
- 汇总产物：`pilot2/pilot2_arms_summary.json`（唯一新增汇总文件；含逐题表、
  空响应计数、prompt 字符账、scorer 溯源三元组 run_pilot.py sha / REL_TOL / RAW_CAP）。

---

## 5. 预测（跑前写下：逐臂点预测 + 三情形机械判定 + 论文改写）

### 5.1 逐臂点预测与 80% 区间（错误数 /60）

| 臂 | 点预测 | 80% 区间 | 依据摘要 |
|---|---|---|---|
| `baseline_claude` | **25（41.7%）** | 18–32 | 15 拒答题多数漏拒（预测 correct_refusals 3/15，区间 1–6）+ 版本 flip 8 题错约半 + 口径路由/披露题散错 |
| `baseline_qwen` | 30 | 22–38 | 旧基座上与 claude 相近偏弱 |
| `baseline_deepseek` | 31 | 23–39 | 旧基座 0.529 的相对位次外推 |
| `baseline_minimax` | 36 | 27–45 | 旧基座 0.686 最弱位次外推 |
| `trivial_claude` | 25 | 18–33 | 一行提示在新基座边际益小 |
| `trivial_v2` | 24 | 17–32 | 指令臂略优于素基线 |
| `trivial_v3` | 25 | 18–33 | 通用示例迁移弱 |
| `governance_informed` | **14（23.3%）** | 8–22 | 见 5.2 分解 |
| `mechanism` | **0（已定）** | — | certs2 60/60（非预测，锚点） |

判据预测：**A′ PASS**（min 素基线 ≥ 0.30；点预测 25/60=41.7%）；**C′ PASS**（trivial
elim 点预测 ≈0.15，区间 0.05–0.35）。若 A′ 实测 FAIL，处置见 §5.4(iv)。

### 5.2 治理臂分解预测（三数自洽：任一被推翻，另两个须同时被推翻）

- `elim_gov` 点 **0.55**（区间 0.35–0.75）⇒ 修掉 baseline_claude 约 25 错中的 ~14 道
  ⇒ 残留 ~11；新引入错（"爱拒答"）~3（`over_refusals` 由素基线的 ~1/45 升至 ~4/45，
  区间 1–9）⇒ **E_gov = 14**。
- `correct_refusals` 点 **9/15**（区间 6–12）：元数据可判 5 题（CA-Q6 AM(i)、FIN-Q8/W1-Q5
  AM(ii)、DEB-Q7 AM(iii)、CARD-Q6 MC(i)）预期大多修复；探针专属 7 题见下。
- **决定性探针集（元数据不可判、ND-1 见证对已物化）= 7 题**：
  OOV×4 {FIN-Q7, F1-Q7, DEB-Q6, EF2-Q5}（覆盖域不物化，判空须对 D 现算）、
  MC(ii)×2 {CARD-Q7, F1-Q8}（同窗分母质量，`_den_present()` 型探针）、
  AM(iv)×1 {EF2-Q6}（锚对对称差审计）。**预测治理臂在其中答错 ≥3/7**（区间 3–6）；
  DISCLOSURE-BLOCKED 3 题不入决定集（策略在册即强提示 REFUSE，属半让利位点）。
- 按簇错误数点预测（合计=14 自洽）：fin 2/8、f1 2/8、card 2/7、code 2/7、deb 2/7、
  ca 1/6、ef2 2/6、th 1/6、w1 0/5。

### 5.3 情形机械判定表（E = governance_informed 错误数/60；不许事后解释）

| 判定 | 条件 | 情形 |
|---|---|---|
| **ND-4 FAIL** | E = 0 | 基座缺陷：新种子仍退化 |
| **(ii) 近退化** | 1 ≤ E ≤ 2 | ND-4 名义通过但设计意图未达，按缺陷处理 |
| **(i) 显著改善但远大于 0** | E ≥ 3 且 elim_gov ≥ 0.40 | 预期最可能 |
| **(iii) 未见实质改善** | E ≥ 3 且 elim_gov < 0.40 | — |

0.40 即冻结 C 判据同一条线（`run_pilot.py` 第 334 行），与 B6 §5.3 同尺。

### 5.4 三情形（+一应急）各自怎么改写论文（防叙事漂移；先写死后看数）

**(i) 显著改善但仍远大于 0 —— 预期最可能**
1. Table 2 以 pilot2 四组呈现（plain ×4 / prompt-variant ×3 / governance-informed / compiler），
   企业 51 题全部数字退出结果节，只留动机段（作者裁定的执行落点）。
2. 头条重述："0% vs X%（治理知情后）于 60 题公开基座"；A′ 成立则保留"前沿模型
   在治理绑定上系统性失败"的限定表述（限定语=未获治理内容的臂）。
3. **新增按族分解图/表**（本轮科学承重）：残余错误按 OOV/AM/MC(i)/MC(ii)/DB/值题分族，
   决定性探针集 7 题逐题列裁定——把"探针类判断提示层原理上够不着（ND-1）"摆成可核结论。
4. ND-4 作为**基座有效性证据**入 §评测方法：治理知情臂 >0% 错误 ⇒ pilot2 修复了旧公共轨
   0/20 退化（引 B6 数字作对照），"非退化是设计出来的且被对抗性检验过"。
5. 数字门与红线脚本同步换 pilot2 数字；旧"无对照臂见过治理内容"表述已在 B6 后删改，
   本轮确认不回潮。

**(ii) 近退化（E ≤ 2，含 E=0 的 ND-4 FAIL）—— 必须如实报告的基座缺陷**
1. **禁止庆祝**：这不是"LLM 很强"的证据，而是 pilot2 种子仍在泄漏标签可判性——
   与 B6 公共轨 0/20 同病。论文**不得**以 pilot2 治理臂数字支撑"提示层不够"的主张。
2. 立即做逐题根因剖检（哪些题、哪张登记表、哪行种子代答了标签）并写入
   `pilot2_arms_summary.json.nd4_postmortem`；结果节改以 mechanism 证书支柱 +
   素基线/变体对照为主，治理臂数字降级为"基座局限"段如实披露。
3. 唯一允许的后续：**另行预注册**修订种子后的重建重跑（新协议新冻结），本轮数字保留在案。
4. 摘要与贡献重排：证书可核验性提为第一贡献；"绑定正确性 LLM 不可达"降格为
   "在非退化性可验证的前提下开放"。

**(iii) 未见实质改善（E ≥ 3 且 elim < 0.40）**
1. 按原样报告，头条不变；**必须自查并在文中列出三个替代解释**：
   (a) 长上下文稀释（治理臂提示 16k–28k 字符，报逐题长度与错误的相关）；
   (b) 传输故障（`empty_responses` 计数与 §6 作废规则）；
   (c) 顺从性（AM(ii) 祈使句两题的逐题裁定）。
2. 只可写"在本协议（单回合、512 输出上限、库级全量治理内容+指令）下无效"，
   不得外推为"提示工程永远无效"。
3. ND-4 仍按 E>0 判为基座非退化成立，(iii) 与 (i) 的差异只改变"治理内容在上下文里
   有多大用"的措辞档位，不改变机制主张。

**(iv) 应急：A′ FAIL（min 素基线 < 0.30）**
不重跑、不换 prompt、不换模型。论文把"前沿系统性失败"降档为实测错误率区间陈述，
并把重心移到 refusal/rewrite 分片（预测素基线 correct_refusals ≤ 6/15——该分片几乎
不可能与 A′ 同时翻车；若连它也翻车，如实报告并承认公开基座上素基线已够用，
主张退守证书可核验性）。

### 5.5 页面预算

pilot2 数字**替换**同位置旧数字（Table 2 / 摘要 / §8 文本），零新增页面；
按族分解表替换旧企业逐题附录的等量篇幅。不得压缩认输面（F 族/让利表）腾地方。

---

## 6. 只跑一次（继承 B6 §6，臂级适配）

1. **每臂只跑一次**。不得因结果不合意重跑、换提示、换模型、换渠道、调温度、加轮次、
   改截断、改选行、改评分分派。
2. **缓存只写不删**：`pilot2/runs/<arm>/<qid>.json` 一旦写入即终局；删除后重跑 = 换汤重试，
   明令禁止。断点续跑只补**从未写入**的 qid。
3. **空响应即错误**（3 次尝试仍空 → no_sql 计错）。
4. **臂级作废条款**：某臂空响应 ≥ 3 题（≥5%）判传输故障，**该臂整臂作废重跑**并在
   论文与本文件追记披露两次运行；不许只重跑失败题；其余臂不受牵连。
5. 本文件冻结后若需修改 §1–§4 任一条，必须在 §8 追记标注时间、内容、当时是否已见
   任何模型输出；见输出后的修改一律视为调参并须在论文披露。

---

## 7. 运行阶段验收断言（跑前 A0–A4/A7 全过才发第一次调用；跑后 A5/A6/A7 复验）

| # | 断言 | 失败处置 |
|---|---|---|
| A0 | `FREEZE_pilot2_arms.json` 全部 sha256 复算一致（runner/llmhub/channels/9 questions/90 seeds/9 warehouses/18 包/MANIFEST/本协议） | 中止；如实报告漂移 |
| A1 | 渠道解析：`claude-opus-4-6→tuzi`（首命中）、`qwen3-coder-next/deepseek-3.2/minimax-m2.5→gateway` | 中止（渠道变 = 对手变） |
| A2 | §2.4 泄漏断言复跑：60 题 × 7 字段 × 最大超集提示，0 命中 | 中止 |
| A3 | `build_prompt_pack.py` 重建与冻结包逐字节一致（18 份 sha256） | 中止 |
| A4 | 逐臂提示总长与逐库 min–max 与 §3.5/MANIFEST 精确相等（8 臂：292,332×4 / 299,232 / 305,892 / 303,552 / 1,372,803） | 中止 |
| A5 | 运行器 import `run_pilot`（不复制函数）；`run_pilot.py` sha256 跑后不变 | 中止 |
| A6 | 写入路径只有 `pilot2/runs/**` 与 `pilot2/pilot2_arms_summary.json`；`pilot/`、`impl/`、`pilot2/{domains,build,ci,prompt_pack}/` 跑后 sha256/mtime 零变动 | 中止 |
| A7 | 60 题、qid 唯一；expected_kind 计数 = value 33 / rewrite 12 / refusal 15；拒因计数 4/5/3/3；9 目录 | 中止 |

**产出物**（新增，不覆盖任何既有文件）：`pilot2/run_pilot2_arms.py`、
`pilot2/runs/<8 臂>/<qid>.json`（480 份）、`pilot2/pilot2_arms_summary.json`。

---

## 8. 追记

*（留白。冻结后的任何偏离写在这里，注明时间、内容、当时是否已见模型输出。）*

- 2026-08-04 预注册写就；`prompt_pack/` 18 包 + MANIFEST 生成并二次重建验证逐字节一致；
  A2 泄漏审计 60×7 零命中（含数值弱检查零命中）；ND-2 拒因 token 于种子 grep 零命中；
  `runs/` 不存在；**LLM 调用次数：0**。

- 2026-08-04 14:1x 追记（**写于全部 480 份缓存终局、结果已见之后**；由汇总代理执行；
  本条不改 §1–§7 任何一字，仅披露。本追记使本文件现哈希偏离 FREEZE 内自哈希——
  冻结字节哈希 `86e6a42e…` 仍在 FREEZE_pilot2_arms.json，diff 仅本节，篡改留痕机制照常工作）：
  1. **trivial_v2 整臂作废重跑**（§6.4 执行，见输出后依条款行事）：run1 空响应 4 题
     （F1-Q1/FIN-Q2/W1-Q2/W1-Q3）≥3 阈 → 作废，原样保留于
     `runs/trivial_v2__VOID_RUN1_2026-08-04/`（61 份，含 VOID_DISCLOSURE.json）；
     run2 空响应 0 为有效运行。两次运行（27/33 与 25/35）论文双披露。
  2. **A 组中断与续跑**（§6.2 条款内）：A 组运行器 13:12 后失联（baseline_claude
     21/60 已写盘，成因不可远程判定），13:46 由汇总代理以冻结运行器断点续跑
     （跑前 A0–A4/A7 全 PASS 后发首调；只补从未写入 qid，缓存零删除零重询），
     14:08 四臂完成 exit 0；全程输出存 `runs/_groupA_resume_20260804_1346.log`。
  3. **连通性探针**：汇总阶段对 qwen3-coder-next/deepseek-3.2/minimax-m2.5 各做
     1 次两字探针（不写缓存不入账）；无法查证 A 组中断前是否已各做 1 次，
     单模型累计可能为 2（条款字面"每模型 ≤1"），如实存疑。
  4. **汇总阶段新增写盘（A6 清单之外，冻结面零触碰，跑后 --dry A0/A3 复验 PASS）**：
     `make_pilot2_summary.py`、`pilot2_arms_summary.json`（§4.4 指名件）、
     `pilot2_summary.json`（旧结构对齐版）、`ARMS_REPORT.md`、上述续跑日志。
  结果速记（详见 ARMS_REPORT.md）：E_gov=28>0 → **ND-4 PASS**；elim_gov=0.361<0.40 →
  情形 **(iii)**；A′ PASS（min 素基线 0.600）；C′ PASS（max trivial elim 0.222）。
