# ACCEPTANCE_REPORT — pilot2 全量验收（九公开库 · 60 题 · 双侧闭环）

日期：2026-08-04。范围：任务书六项验收（金标 / 证书两轨+披露类首验 / 伪造族 F1–F4 /
代价重测 / 规模数字 / ci 零交集）+ 泄漏闸复跑。一切数字由本次验收现场复算；
命令均可复跑（§8）。前置基线：`pilot2/BUILD_REPORT.md`（建仓）、`impl/PORT_REPORT.md`（移植）。

## 0. 终局判定矩阵

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 金标验收（编译器 vs 冻结金标） | **60/60 全过**，良构自检 0 错 | `acceptance_pilot2.py` 实跑；证书 60 份重发射逐字节稳定（聚合 sha1 `60dbd2560450f157cb57b2e7b8bb94501801edcd` = PORT 基线） |
| 2 | 证书验收（独立校验器常规轨） | **ACCEPT 60/60**（window_source: derived 50 / declared 8 / declared-override 2） | `runall.py p2` 实跑 |
| 2′ | 严格轨 `--no-declared-windows` | **ACCEPT 50/60**；10 个 REJECT 全部 V0、恰为呈现窗坐标题（8×window_request + 2×cross_window），fail-closed | 逐题清单 §2.2 |
| 2″ | 披露类证书首次验收 | DB 拒答×3 / 粒度上卷×5 / 掩码×2 / 离对角×1 全部重演闭环（V5 Π+条款独立重算、V6b 笔录重执行） | §2.3 |
| 3 | 伪造族（新基座全套） | **30/30 REJECT 且拒因命中**（F1×6 F2×5 F3×9 F4×10）；10 个真证书基座全 ACCEPT；老族 16/16 + aux symdiff-57 复算 PASS | `forge_p2.py` / `forge.py` 实跑 |
| 4 | 代价重测（认输轴更新） | 60 证书冷校验总 **7.60 s**；warm 校验/回答比中位 **17.7×**（p90 36.1×）；证书中位 **2,600 B** | `impl/cost_p2.json` |
| 5 | 规模数字 | Σreal **3,830,036** 行（trans **1,056,320 ≥ 10⁵** 零合成 → P6）；gov 种子 **847** 行；版本 **2/库 ×9**；策略实例 **18** 行 | §5，全部由仓库现查，provenance 零失配 |
| 6 | ci_check 零交集 | **PASS**：failures=[]、shared_internal_roots=[]（含新增 forge_p2.py 后复跑） | §6 |
| 6′ | pilot2 泄漏闸 | leak_check **PASS**（n=60, problems=0, inter=[]） | §6 |

## 1. 金标验收（60/60）

`python3 impl/asof_compiler/acceptance_pilot2.py` → `questions=60, gold_match=60/60,
certificates_written=60 → impl/certs2, wellformed_selfcheck_errors=0, ACCEPTANCE-P2: ALL OK`。

构成与规格逐格全同（由 questions.json 金标侧现场重 tally）：

| 轴 | 分布 |
|---|---|
| expected_kind | value 33 / rewrite 12 / refusal 15 |
| 决策 | ANSWER 33 / REWRITE 12 / REFUSE 15（SQL 出码 45 = 33+12） |
| 拒因 | out-of-validity 4 / anchor-mismatch 5 / missing-caliber 3 / disclosure-blocked 3 |
| 拒因子型 | am_i 1, am_ii 2, am_iii 1, am_iv 1（四子型全）；mc_i 1, mc_ii 2（两型全） |
| rewrite kind | granularity_rollup 5 / hull_trim 5 / mask 2 |
| 簇预算 | fin 8 / f1 8 / card 7 / code 7 / deb 7 / ca 6 / ef2 6 / th 6 / w1 5 |

证书重发射幂等：本次两轮 `acceptance_pilot2.py` 重写 60 份后
`cat [A-Za-z]*.json | shasum -a 1` = `60dbd2560450f157cb57b2e7b8bb94501801edcd`，与 PORT_REPORT
冻结值逐字节一致（AppleDouble `._*` 过滤口径同 PORT §0）。

## 2. 证书验收（独立校验器）

### 2.1 四轨总表（`python3 impl/asof_verifier/runall.py`）

| 轨 | ACCEPT | window_source |
|---|---|---|
| p2 / declared-ok | **60/60** | derived 50, declared 8, declared-override 2 |
| p2 / no-declared-windows | **50/60** | derived 52, （拒于窗推导前）8 |
| old51 / declared-ok（回归） | 51/51 | derived 49, declared-override 2 |
| old51 / no-declared-windows（回归） | 49/51 | derived 51 |

老轨两数与移植前 INDEPENDENCE/PORT 基线一致，回归不破。

### 2.2 严格轨 10 题逐题（全部 V0 拒，fail-closed 属设计后果）

8×window_request：CARD-Q5、DEB-Q5、DEB-Q7、EF2-Q2、EF2-Q4、FIN-Q6、F1-Q6、W1-Q4
（拒详情均为 I2′(b) 非退化变体缺失——`range_request` 登记语义把呈现窗当声明输入，独立推导如实弃权）；
2×cross_window：FIN-Q8（num 窗 [1997-05,1997-06) ≠ 推导 [1997-01,1998-01)）、W1-Q5（den 窗
[2026-04,2026-05) ≠ 推导 [2026-05,2026-06)）。与 PORT §4 裁定 4 预言集完全一致。

### 2.3 披露类证书首次验收（逐张核对校验器 check 明细）

| 路径 | 证书 | 校验器重演闭环（实测 check 详情） |
|---|---|---|
| 披露门 DISCLOSURE-BLOCKED | CODE-Q7 / TH-Q5 / TH-Q6 | V5 PASS：Π 独立重算（code=[pi1,pi2]；th=[pi1,pi2,pi3]），REFUSE 条款重演委派 V6b；V6b PASS：¬OOV/¬AM 先行重演 + 阻断策略在册核验 + SUPPMIN 笔录 SQL **重执行**低于阈值（实体粒 observed=1 < k：code 5 / th 10）+ U_min=∅ 断言 |
| 粒度爬升 REWRITE | CODE-Q4（user→reputation_band, 胞 13≥5）、CA-Q5（school→county）、TH-Q3（→all 顶级豁免）、DEB-Q5（Segment→all，v2 治下 k=20>16）、CODE-Q5（time_floor day→month） | V5 PASS："k/lattice, mask and time-floor clauses re-established from (G_v, D)"——`_p2_min_cell` 不读证书笔录、自装胞普查 SQL 逐级重算，同时压最小性与合法性两向 |
| 掩码闭包 REWRITE | CODE-Q6（Location generalize_last_component）、TH-Q4（Birthday year_only@v2 掩码升级） | V5 PASS：μ* 覆盖 mask_class + 产出 SQL 掩码变换签名双查；V0 把 μ*≠id 计入 REWRITE 合法收窄轴 |
| 离对角版本钉 | F1-Q3（pinned v1, ver(declared_at)=v2） | V1 PASS："off-diagonal read explicitly committed: pinned 'v1', ver(T)='v2'" |

## 3. 伪造族（新基座全套 + 老族回归）

新增校验器侧 `impl/asof_verifier/forge_p2.py`（仅 import chk；输出 `forge_p2_out/`）。
与老 forge.py 的手搭基座不同，p2 基座直接取 **10 张真编译器证书**（FIN-Q1、F1-Q3、CARD-Q7、
EF2-Q6、CA-Q5、CODE-Q4、CODE-Q6、CODE-Q7、TH-Q4、TH-Q5），未变异全 ACCEPT——每个 REJECT
钉在变异本身。**FORGE-P2: PASS (10 bases, 30 forgeries)**：

| 族 | 伪造（基座） | 期望→实测 |
|---|---|---|
| F1a | 整年错窗 ANSWER（FIN-Q1→1995，SQL+α+探针连贯移） | V0 ✓ |
| F1b | 空分母拒答翻转成 ANSWER（CARD-Q7，DEN_POP 记 490 谎值） | V6c ✓（重执行 μ_den=0∈𝒵） |
| F1c | MC 拒答窗移位（CARD-Q7→2016-12 同为空月，重演自洽） | V0 ✓（α 非 α_{q,v}） |
| F1d | 同窗比率捏造 AM(ii) 窗对拒答（FIN-Q1） | V0 ✓ |
| F1e | 离对角承诺标记删除（F1-Q3） | V1 ✓（GOLD-1 零痕迹镜像） |
| F1f | 版本换轨（FIN-Q1 ν→v2，ver(declared_at)=v1） | V1 ✓ |
| F2a | 删 ν（FIN-Q1） | V0 ✓ **且断言 V1 同失**（p2 别名层随版本作用域，V0 别名重解析先失；V1 以经典 "graph_pin missing" 同报） |
| F2b | 删 α | V0 ✓ |
| F2c | 删 ρ | V4 ✓ |
| F2d | 删 δ | V5 ✓ |
| F2e | 删拒答见证（CARD-Q7） | V6b ✓ |
| F3a | 悬空版本钉 v9 | V0 ✓ **且断言 V1 同失**（"0 row(s)"） |
| F3b | 无策略域漏 D5 标注 | V5 ✓ |
| F3c | sum(rate) 形（AVG 日率） | V6a ✓ |
| F3d | AM(iv) 载荷窗造假（EF2-Q6 num→2013-11-30） | V6b ✓ |
| F3d2 | AM(iv) symdiff_count 篡改（1→3） | V6b ✓ |
| F3e | 域外表（FIN-Q1 SQL 读 "card"） | V6a ✓ |
| F3f | 证书自颁改锚豁免（→A-FIN-TRANS + declared_override） | V0 ✓ |
| F3g | 路由 hop via_table 篡改（→trans） | V4 ✓ |
| F3h | 别名层度量替换（→fin.penalty_trans_rate） | V0 ✓ |
| **F4a** | **细粒度伪 ANSWER**（CA-Q5 school 粒直答，剥上卷痕迹） | **V5 ✓**（k 条款独立重算：认证粒 min cell 1<10） |
| **F4b** | **伪造上卷痕迹·过卷**（CODE-Q4 band→all，band 本已合法 13≥5） | **V5 ✓**（SelectMin 最小性两向压制） |
| **F4c** | **伪造 SUPPMIN 笔录**（CODE-Q7 笔录 SQL→SELECT 999） | **V6b ✓**（重执行 999≥阈值，拒答不重演） |
| **F4d** | **策略集 Π 清空**（CA-Q5 policy_ids=[]） | **V5 ✓**（Π 独立重导出≠[]） |
| **F4e** | **受治域谎报无治理**（CODE-Q6 全洗白+原值列直出） | **V5 ✓** |
| **F4f** | **DB 见证阻断集清空**（CODE-Q7 blocking=[]） | **V6b ✓** |
| **F4g** | **DB 见证引用未登记策略**（TH-Q5 +th.pi99） | **V6b ✓** |
| **F4h** | **掩码闭包缺项**（CODE-Q6 μ*=[] 而 dec=REWRITE） | **V0 ✓**（C4 Def 4.10 映射：无收窄轴则须 ANSWER，静默收窄面封死） |
| **F4i** | **掩码变换剥除**（μ* 仍宣称，SQL 原值直出 Location） | **V5 ✓**（掩码签名双查） |
| **F4j** | **掩码强度降级**（TH-Q4@v2 year_only→year_month） | **V5 ✓**（版本化掩码语义重演） |

老族回归：`forge.py` → **PASS（3 基座 + 16 伪造全拒）**，aux symdiff-57 独立复算 PASS。

**实测边界（诚实披露）**：DB 见证 `blocking_policy_ids` **部分缺项**（删 code.pi2 仅留
code.pi1，非清空）当前 ACCEPT——该字段在非空+全在册之外的完备性不承载判定（拒答本身
及拒因均仍正确，δ.Π 另由 V5 独立重算钉住）；候选加固：V6b 将引用集与独立重算的阻断集
对账。列入 §7 待办。

## 4. 代价重测（`impl/cost_p2.json`，认输轴数字更新）

`python3 impl/measure_cost.py --pilot pilot2 --certs impl/certs2 --out impl/cost_p2.json`
（measure_cost.py 增 `--pilot/--certs` 形参，缺省行为与老语料逐字节同路径；老 `impl/cost.json` 未触碰）。

| 量 | pilot2（60 证书=45 SQL+15 拒答） | pilot-51 基线（cost.json, 2026-08-03） |
|---|---|---|
| 校验冷总时 | **7.60 s**（60 进程） | 5.04 s（51 进程） |
| 校验冷 med/p90/max | 0.1158 / 0.1438 / 0.2877 s | 0.0965 / 0.1067 / 0.1156 s |
| 冷进程地板（import duckdb） | 0.0526 s | 0.0521 s |
| 校验热 med/p90/max | **0.01696 / 0.04594 / 0.17838 s** | 0.00615 / 0.01199 / 0.02132 s |
| 回答热 med | 0.00131 s | 0.00024 s |
| 比值(热) med/p90/max | **17.7× / 36.1× / 44.4×**（n=45） | 22.0× / 43.4× / 77.9×（n=37） |
| 比值(冷) med/max | 1.79× / 4.40× | 1.47× / 1.72× |
| 证书字节 med/min/max | **2,600 / 1,760 / 4,725 B** | 3,106 / 1,587 / 5,214 B |
| SQL 字节 med/min/max | 204 / 88 / 810 B | — |

注：① 60 张测量期全 ACCEPT；② p2 无 `symdiff_audit` 全集扫描证书（AM(iv) 均为窗限
`window_realization_symdiff`，受请求窗界定——Prop 5.11 声明的全扫逃逸类在 p2 未被实例化，
scan-amplification 表为空；老语料 cost.json 仍是该类的参考件）；③ 热校验尾部
（CODE-Q1/Q2 ≈0.18 s、CODE-Q4 0.107 s）来自大表（posts 92,987 行自连接）上的覆盖/胞普查
重演，与 Prop 5.11 的治理表项界一致。

## 5. 规模数字（RC-7 / RC-8 / P6 证据；全部由仓库现查，provenance 零失配）

### 5.1 逐库行数（real=BIRD/Spider 原值拷贝；authored=治理所需最小作者件）

| 库 | real 行 | authored 行 | 最大真实表 | 版本行(distinct) | 策略实例行(ids) |
|---|---:|---:|---|---|---|
| financial | **1,079,680** | 0 | **trans 1,056,320** | 2 (2) | 0 |
| card_games | 803,445 | 0 | legalities 427,907 | 2 (2) | 0 |
| codebase_community | 740,646 | 0 | postHistory 303,155 | 2 (2) | 8 (4) |
| formula_1 | 514,287 | 18 | lapTimes 420,369 | 2 (2) | 0 |
| debit_card_specializing | 423,050 | 0 | yearmonth 383,282 | 2 (2) | 2 (1) |
| european_football_2 | 222,796 | 0 | Player_Attributes 183,978 | 2 (2) | 0 |
| california_schools | 29,941 | 0 | schools 17,686 | 2 (2) | 2 (1) |
| thrombosis_prediction | 15,952 | 0 | Laboratory 13,908 | 2 (2) | 6 (3) |
| world_1 | 239 | 20,076 | country 239 | 2 (2) | 0 |
| **Σ** | **3,830,036** | **20,094** | | **18 行 / 9×2** | **18 行 / 9 ids** |

- **P6**：financial.trans 1,056,320 行 ≥ 10⁵ 且 authored=0（零合成承接 BIRD 原值；
  provenance 源 sha256 在册）。authored 全账：w1 country_history 20,076 = 239×84 月 +
  f1 points_scheme 18（真实历史积分口径的关系原子化），逐表与 provenance.json 声明
  比对**零失配**。
- **gov_* 种子 847 行**（DB 现查=种子文件行数=847，90 文件）：version 18 / node 112 /
  metric 122 / measure_def 151 / alias 122 / routing 96 / anchor 38 / binding 130 /
  gran_edge 40 / disclosure 18。
- **RC-7（版本轴非平凡）**：9 库各 2 提交版本（timestamps 提交映射，ver(declared_at)
  首次非平凡）；离对角承诺 F1-Q3（pinned v1 @ ver(T)=v2）由 V1 重演、其删标即拒由
  F1e 伪造实证。
- **RC-8（治理变更翻转值）**：4 组同题双 T flip 全部落在本次 60/60 金标实跑内——
  FIN-Q1/FIN-Q2（同 as_of=1996-06-30，declared_at 1997-06-15 vs 1998-09-15）＝
  0.13675213675213677 vs 0.08547008547008547；F1-Q1/F1-Q2 ＝ 100.0 vs 252.0（2009 积分
  10-8-6-5-4-3-2-1 vs 2010 25-18-…）；CA-Q1/CA-Q2 ＝ 0.37985585826806795 vs
  0.37804549460887515；W1-Q1/W1-Q2 ＝ 4,068,933,086 vs 4,313,069,067（×1.06 常住口径）。
- **RC-7×RC-8 交互**：DEB-Q5 v2 治下 k 10→20 → Segment 胞 16<20 上卷 REWRITE（本次
  金标+V5 重算双验）；建仓阴性对照 v1 治下同题 ANSWER [['LAM', 26.069]]（BUILD_REPORT）。
- **双路径口径对照**（建仓冻结证据，aware 进金标/blind 只入 notes）：fin 罚息率
  0.14310% vs 2.17426%（15.19×）；code 采纳率 0.68085 vs 0.29038（2.34×）；debit 双币
  CZK 15,626.14 vs EUR 1,166.15（13.4×）。dualpath_report.json：n=60, agree=60, mismatch=0。

## 6. CI 闸复跑

- `python3 impl/asof_verifier/ci_check.py` → **CI-CHECK: PASS**，`failures=[]`、
  `shared_internal_roots=[]`；校验器文件集now={chk, forge, ci_check, runall, **forge_p2**}，
  import 根 ⊆ stdlib ∪ {duckdb} ∪ 校验器自身模块；A2/A4 无 compiler/pilot 向
  sys.path/动态 import 逃逸。零共享红线在新增伪造件后继续成立。
- `python3 pilot2/ci/leak_check.py` → **PASS**（n=60, problems=0, importsA=[],
  importsB=[datetime,json], inter=[]）。
- 建仓期 ND 闸证据未动（ci/nondegeneracy_report.json：ND-2 90 文件 847 行 0 命中、
  ND-3 干扰行 57.1%；ci/witness_report.json：ND-1 见证对 8/8）。
- 冻结面纪律：本任务对 `theory/`、`pilot/`、`pilot2/domains/`、`pilot2/build/`、
  `pilot2/ci/`（除 leak_report.json 为 leak_check 自身重写）零写入；pilot2/ 新增仅本报告。
  内容级幂等交叉核：certs2 重发射聚合 sha1 与 PORT 冻结值同；gov 种子文件↔库行数同 847。
  （建仓自报的整链 sha256 `d3258d3e…` 属建仓脚本内部配方；本验收另立可复算配方：
  9×questions.json + 90×gov_seed.jsonl 排序串接 sha256 = `ae097d058e6200d98a16fe971aa19e8bc8b5e9d1c123b6a1835da44bd3aba3ac`，供后续对账。）

## 7. 诚实边界与待办

1. **DB 见证阻断集部分缺项 ACCEPT**（§3 边界）：非空+全在册即过；候选加固为 V6b 与
   独立重算阻断集对账。不影响判定正确性（决策与拒因均由其他检查独立钉住）。
2. **严格轨 50/60 属登记语义设计后果**：`range_request`/跨窗祈使把呈现窗当声明输入；
   若补机器可读窗形登记列可再收窄（承 PORT §4 裁定 4）。
3. **ND-4（治理知情臂原协议重挂 pilot2）预注册仍待执行**——本报告是证书学 V0–V6c 验收，
   不是评测臂结论。
4. **未激发的防御路径**（60 题无位点，代码在）：ver(T)↑ 前治理期 OOV、
   pinned_version_uncommitted、p2 别名缺失 MC(i) 证书侧；F1-Q4 型 delta 期窗 hull 裁剪的
   REWRITE-vs-OOV 裁定分歧继续留档。
5. **Prop 5.11 全扫逃逸类在 p2 未实例化**（AM(iv) 均窗限模式）；该类代价证据以老语料
   cost.json 为准。
6. 伪造电池为族级覆盖（每类检查面≥1 落点、30 例），非逐题×逐字段全笛卡尔。

## 8. 复跑清单

```bash
cd "/Volumes/SSD 1/explore_opportunity_cc/impl"
python3 asof_compiler/acceptance_pilot2.py      # §1 金标 60/60 + 证书重发射
python3 asof_verifier/runall.py                 # §2 四轨（old51+p2 × 默认/严格）
python3 asof_verifier/forge_p2.py               # §3 新基座 10 基 + 30 伪造
python3 asof_verifier/forge.py                  # §3 老族 3 基 + 16 伪造 + symdiff-57
python3 measure_cost.py --pilot "../pilot2" --certs certs2 --out cost_p2.json   # §4
python3 asof_verifier/ci_check.py               # §6 零共享红线
python3 ../pilot2/ci/leak_check.py              # §6 泄漏闸
```
