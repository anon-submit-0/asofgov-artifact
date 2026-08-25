# S3 SMOKE — 复现研究 harness + 2 次冒烟调用（到此为止，全量 k-run 由编排器把关）

- 日期：2026-08-20（本文件与全部产出仅落 `poststudy_20260820/s3/`，冻结证据零触碰）
- 治理预注册：`PREREG_poststudy_20260820.md`
  sha256 = `f2fb136ae3ecdbce29ed7b2632df4f0d3e0b2fde07889bb31c68dd4ac8aace24`（已现场复核）
- 执行体：`s3/rep_harness.py`；缓存：`s3/runs_rep/<arm>/rep<k>/<qid>.json`；旁路日志：`s3/call_log.jsonl`

## 1. 提示装配的精确语义（读冻结代码所得，非猜测）

冻结运行器 `pilot2/run_pilot2_arms.py` 的 `build_prompt(arm, d, question_zh)`：

```
prompt = RP.PROMPT.format(schema=prompt_pack/<db>.schema.txt,
                          extra=EXTRA[arm],
                          question=q["question_zh"])
```

- `RP.PROMPT` 来自冻结的 `pilot/run_pilot.py`（text-to-SQL 指令 + REFUSE 许可 +
  `## Schema（含行数注记）\n{schema}\n{extra}\n## 问题\n{question}\n\nSQL:`）。
- **baseline_claude**：`extra = ""`（纯 schema 包 + 题干）。
- **governance_informed**：`extra = RP.TRIVIAL_V2_NOTE + prompt_pack/<db>.gov.txt`
  （usage 指令 = TRIVIAL_V2_NOTE「先查锚表、依绑定规则落窗、分子分母同窗、无同窗数据则 REFUSE」，
  后接该库 gov_* 十表全量导出块）。
- 两臂模型均 `claude-opus-4-6`；`EXPECT_CHANNEL` 冻结为 `tuzi`（首命中）。

## 2. Harness 设计（`rep_harness.py`）

- **零复制**：importlib 加载冻结件 `run_pilot2_arms.py`（R2）与其内嵌 `run_pilot`（RP）。
  装配= `R2.build_prompt`；调用= `RP.llm`（子进程 → `~/.claude/skills/llmhub/bin/llmhub.py chat
  --model M --prompt P`，max-tokens 默认 512，temperature 不下发，单样本，仅空响应重试 ×3
  = `retries=2`，子进程 timeout 180s）；抽取= `RP.extract_sql`；评分= `R2.fetch_and_score`
  （冻结 scorer 语义原文：REL_TOL=0.5%、rowset/string 分派、refusal 分类学）。
- **观测不改协议**：仅包裹 `subprocess.run` 记录墙钟/attempt 数/llmhub stderr 的
  usage 行（`[model | prompt=N completion=M]`）；argv/env/timeout 一字未动。
  latency/token 只进 `call_log.jsonl`，缓存记录保持冻结 schema 原样
  （qid/system/kind/value/verdict/raw≤2000/sql/prompt_sha256/prompt_chars/empty_response，
  `json.dumps ensure_ascii=False indent=1` utf-8）。
- **写守卫**（已实测触发）：
  - 目标路径 resolve 后必须在 `poststudy_20260820/` 内，否则 `[REFUSE]`（实测 `/tmp/evil.json` 被拒）。
  - 已存在缓存文件一律拒绝覆盖（终局语义；实测重跑同 qid 打印 `[REFUSE-OVERWRITE]` 且零调用）。
  - rep 只允许 2..5（rep1 := 冻结主研究运行，复用不重跑；实测 rep=1 被断言拒绝）。
- 模式：`assert-only`（零调用门检）/ `estimate`（零调用 120 提示装配）/
  `run <arm> <rep> <qid>...|--all`（付费；`--all` 供编排器把关后的全量 rep 用）。

## 3. 完整性与逐字节一致性断言（全部 PASS）

- **prompt_pack vs MANIFEST**：18 文件（9 库 × schema/gov）chars+sha256 全等 → PASS。
- **渠道**：channels.json 中 `claude-opus-4-6` 首命中渠道 = `tuzi` == 冻结 `EXPECT_CHANNEL` → PASS。
- **逐字节一致性**：冻结缓存 schema 存 `prompt_sha256`+`prompt_chars`（不存提示原文），
  故以 sha256 为逐字节判据：对 **两臂全部 60/60 缓存**（合计 120，远超要求的 ≥3）
  重新装配并断言 sha256 与 chars 全等 → **120/120 PASS**。每次付费调用前对该 (arm,qid)
  再断言一次（call-time re-assert）。
- **冻结面复核**：FREEZE_pilot2_arms.json 131/132 一致；唯一差异 `PREREG_pilot2_arms.md`
  为其 §8 已披露的 2026-08-04 事后追记（冻结哈希 `86e6a42e…` 留痕机制照常），
  与本次工作无关、跑前跑后一致。跑后 `runs/*/CARD-Q1.json` sha 抽查不变。

## 4. 网关健康检查（2026-08-20 14:3x）

- `llmhub list`：`tuzi` 渠道 `claude-opus-4-6` ★首选，历史状态 OK；
  `gateway` 渠道全部 claude-* 仍 http400（与冻结偏离记录一致）。
- `llmhub probe claude-opus-4-6`（探针 timeout=35s）：
  - `tuzi`：**两次探针均 35s 超时** —— 后经冒烟证实为高延迟而非宕机（真实调用 41s 成功），
    探针 35s 上限短于当前 tuzi 时延。
  - `tokens1688`（同名模型第二渠道，非冻结路径）：首探 OK，复探
    `http403 token quota is not enough（余额 ¥0.000715）`——该备选渠道**配额已尽**；
    但协议冻结在 tuzi 首命中，不构成偏离，仅意味着**无备胎**。
- 结论：为 claude-opus-4-6 服务的实际渠道 = **tuzi**，与冻结运行期望一致。

## 5. 冒烟结果（恰好 2 次付费调用，均 rep2 / CARD-Q1）

| arm | verdict | value vs gold | latency | attempts | prompt_tok | completion_tok | prompt_sha256 == rep1? |
|---|---|---|---|---|---|---|---|
| baseline_claude | **correct** | 2161.0 == 2161 | 41.156 s | 1 | 2200 | 36 | ✓ `17e63233…` |
| governance_informed | **correct** | 2161.0 == 2161 | 176.333 s | 3（前 2 次空/超时） | 9885 | 41 | ✓ `7c5046e0…` |

- 评分走冻结 scorer 原文（CARD-Q1 为数值金标，`RP.run_sql`+`RP.score`，REL_TOL 0.5%）。
- 与 rep1（冻结主研究）对照：两臂 rep1 CARD-Q1 也均 correct → 本题 rep1/rep2 零翻转。
- **运维警示（非偏离）**：gov 臂 ~24k 字符提示在当前 tuzi 时延下逼近 llmhub chat 的
  60s 内层超时，本次 3 attempts 才拿到补全。全量 k-run 若维持该时延，gov 臂将大量
  触发协议内重试（仍属"仅空响应重试 ×3"），且存在整臂 `empty≥3` 触发冻结 §6.4
  作废条款的现实风险；建议编排器择低峰时段并预留 ~3× 墙钟。

## 6. 全量 S3 成本估计（零调用装配 120 提示 + 冒烟实测换算率）

- 装配核对：baseline 60 题共 292,332 chars、gov 60 题共 1,372,803 chars，
  与 MANIFEST `prompt_totals` 精确相等（断言 PASS）。单 rep 双臂 1,665,135 chars。
- 实测换算率（llmhub 计费口径）：baseline 2200/5449 = **0.4037 tok/char**；
  gov 9885/23970 = **0.4124 tok/char**。
- **480 次调用（4 reps × 2 arms × 60 qids）**：
  - 输入：baseline ≈ 118,027 tok/rep、gov ≈ 566,131 tok/rep →
    **合计 ≈ 2,736,633 input tokens**（≈2.74M）。
  - 输出：硬上限 480 × 512 = **245,760 tokens**；按冒烟实测（36/41 tok）
    期望 **≈ 18,500 tokens**。
  - 重试通胀警示：超时空响应的重试会重发同一提示（gov 冒烟 3 attempts）；
    若 tuzi 对中断请求计费，gov 侧实际计费输入可达上表 ~2–3×，上界
    ≈ 3 × 2.26M（gov）+ 0.47M（base）。协议本身无从压低此项（冻结）。

## 7. 状态

**SMOKE 完成，STOP。** 已写盘：`rep_harness.py`、`runs_rep/{baseline_claude,governance_informed}/rep2/CARD-Q1.json`、`call_log.jsonl`、本文件。未发出第 3 次调用；rep2 其余 59+59 题与 rep3–rep5 全部留待编排器放行。
