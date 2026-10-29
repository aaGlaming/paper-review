# Phase-3 P23：gold 样本校准与评测呈现

## 一、目标与范围

校准现有 gold 文件与赛题 rubric 维度码的一致性，明确评测 `source` 的两种含义，并避免小分母指标以百分比呈现出过度确定的观感。本阶段维持 12 篇 gold，不扩充分母；不改评分链路，不改 `rate` 计算，不运行模型评测，也不把系统输出回填为 gold。

## 二、证据来源与缺口

**缺口先行：需求原文里关于“评测样本量”的要求不在仓库内。** 下列细则是按现存计划与代码推导的工程决策，不冒充需求原文；若取得原文，应重新校准。

- `docs/version/Phases/Phase-3/Phase-3-plan.md` §8 的 P23 行规定维持 12 篇、可选补 1 篇；§8.1 决定不强制从 12 补到 15。
- `docs/plan/progress.md` v3.7.0 记录了 12 篇 gold 的实测分布、候选分布与 `model` / `deterministic` 两个 source 的历史结果；v3.7.1 只记录 P0 复核。
- `backend/app/report/evaluation.py` 的 `summarize_eval()` 按 `matched / total` 计算原始 rate，返回 source 与分母；`run_eval()` 的模型入口仅接收 `chat`，确定性入口不调用模型。
- `backend/app/review/samples.py` 校验样本的必需元数据与 gold 字段；`data/samples/eval/README.md` 声明样本来源为自建评测稿、数值为构造值。
- 候选 SQL 的历史结果用于排序人工复核，不是标注：系统判“证据不足”但同赛题同维度的 gold 多数为其他档位，共 136 条候选。

## 三、现状证据

12 篇 × 每篇 5 维 = 60 个 gold 维度项；档位分布为：基本 26、充分 20、不足 12、证据不足 2。赛题样本分布为 4/4/4；`expected_findings` 合计 26 条。`scripts/check_eval_gold.py` 与 `backend/tests/report/test_eval_gold.py` 持续核验必填字段、档位集合及 gold 维度码与对应 rubric 完全对齐。

## 四、决策一：本轮不补那 1 篇

P23 的“可选补 1 篇”不是必须执行。本轮不新增 gold：v3.7.0 候选命中共 136 条，其中 2024-A 为 133、2024-C 为 3、2025-A 为 0，候选维度集中在 `constraint_check`。现有样本已是 4/4/4；从 2024-A 补 1 篇会变成 5/4/4，破坏赛题均衡。若要保持均衡，就需要同时补 2025-A，但该赛题当前没有候选，本轮物理上做不到。即使只把“证据不足”从 2 条补到 4 条，也仍只有三个取值级别；改变分母数字没有增加新的信息级别。因此不把系统候选当作人工标签，也不创建样本文件。

回滚条件：若后续获得人工标注依据，且候选分布达到报告第三节列明的条件，可另版增加样本并重新计算分母。

## 五、决策二：分母不动，把呈现降下来

新增工程阈值 `LOW_SAMPLE_THRESHOLD = 5`，定义在 `backend/app/report/evaluation.py` 模块级。它是呈现阈值，不是统计阈值：当 `0 < total < LOW_SAMPLE_THRESHOLD` 时 `low_sample=true`；分母达到 5 时为 false；`total == 0` 时仍为 false，并保留 `rate=None` 与 `no_samples` 语义。`rate` 本身不改变。

前端 `MetricCard.vue` 对 `low_sample=true` 显示“样本过少”、保留 `matched / total`、说明实际分母并隐藏折线；不改评测页结构、来源显示或 `caliber` 文案。阈值可在上述模块常量处调整，属于工程决策，不是需求原文给出的统计结论。

## 六、判据

1. gold 文件仍为 12 篇、60 个维度项、分布 26/20/12/2 与 4/4/4，`expected_findings` 总数 26；用 `scripts/check_eval_gold.py` 与 `backend/tests/report/test_eval_gold.py` 复核，且 gold 文件哈希前后不变。
2. 两个 source 原始 rate 不被阈值改写；后端测试证明 2/2 的分母标记为小样本、26/60 不标记，分母 0 时 `low_sample=false` 且 `rate=None`。
3. 前端测试证明小样本卡不显示百分号、保留分数、显示动态分母说明且不绘制折线；正常 26/60 卡仍显示 43.3%。
4. `pytest backend/tests -q` 两遍结果完全一致；Vitest、build、Playwright、日志与文档编码检查命令及结果写入对应版本 progress。Playwright 既有 `confirmed-card` 超时逐条列明，不归为本版新增失败。
5. 不请求模型评测 API，不写 gold，不改评分图或 Chroma；评测来源说明继续注明 `run_eval()` 不注入 `agent_runner`。

## 七、遗留与移交

- “证据不足” gold 分母仍为 2；本版只把指标呈现为“样本过少”，没有消除样本稀缺。
- `source=model` 的 13/60 来自历史单次记录 `docs/plan/acceptance/calls/16-eval-model.json`，本轮不重跑模型，也不把历史记录称为本轮实测。
- `run_eval()` 不注入 `agent_runner`，因此不度量工具调用、`critique` 降档或预算终止；Agent 行为由轨迹证据单独核验。
- 八条 `confirmed-card` 超时交给 P25 收口；P25 必须逐条选择并署名：修复、调整等待策略或书面豁免。
- P24 按 §8.1 只交付非验收骨架与草案；P26 回归首期 18 条与三期八条。

## 八、拆版表

| 版本 | 范围 | 判定 |
|---|---|---|
| v3.7.0 | gold 只读体检、口径说明、候选与补样本规则 | 已执行 |
| v3.7.1 | P0 环境与解释器复核 | 仅 P0 已执行；P1～P4 未做 |
| v3.7.2 | 本细则、`low_sample` 后端字段、指标卡呈现与 P23 收口报告 | 本版收口 |

本阶段不设 v3.7.3。
