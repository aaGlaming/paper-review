# P25 细则：评审耗时基线与等待可见（v3.9.0）

## 一、目标与边界

P25 只做三件事：测量当前实现三次完整评审的耗时、让用户看见确认请求已等待多久、逐条判定八条长期失败的 E2E 用例。测量按实际响应标为模型路径或确定性路径；两类数据分开统计。

本阶段不并行化评审图，不改 `chat_calls` 语义，不加入异步队列或后台任务，不恢复三分钟验收。提示只报告真实经过时间，不据此点亮任何评审步骤。P25 不承诺把评审变快。

## 二、现状证据

- `frontend/src/views/论文解析.vue:258` 在点击确认后设置 `phase.value = 'running'`；`:260` 随后调用同步 `resumeReview()`；`:264-267` 只有拿到报告后才更新 `report`、点亮完成索引并切到 `done`。因此请求期间前端得不到后端中间步骤。
- `frontend/src/components/StageTracker.vue` 当前只展示运行 badge 与静态说明，没有已等待时长。其注释禁止用定时器伪造步骤进度；本版新增计时只计算经过秒数，不更改 `reachedIndex` 或步骤状态。
- 现有八条失败的正向 `confirmed-card` 等待都使用 Playwright 默认 5 秒：`consistency.spec.ts:15`、`parse.spec.ts:39`、`parse.spec.ts:83`、`scoring.spec.ts:22`、`sketch-fix.spec.ts:13`、`sketch-fix.spec.ts:43`、`suggestions.spec.ts:14`、`visual.spec.ts:33`。P24 E2E 逐条记录它们因 `confirmed-card` 未在默认等待内出现而失败。
- `frontend/tests/e2e/parse.spec.ts:34` 的 `toHaveCount(0)` 是确认前负向断言，验证尚未确认时结果卡不存在；它必须保持短等待，不能替换成 60 秒等待。`:46` 是刷新后检查已存结果即时恢复，不属于八条“确认请求完成”的等待；本版不扩大等待范围。

## 三、基线口径

- 历史模型口径：`docs/plan/acceptance/report-V3.md:115` 记录 v1.0.4 十篇完整链路合计 233.6 秒、平均 23.4 秒、最大 36.6 秒；这是历史参考，不是 P25 新测量。
- 历史确定性口径：`docs/plan/progress.md` 的 v3.6.0 live 记录一条 `source=deterministic` resume 为 7,284 ms。它来自不调用模型的链路，不得与模型耗时合并，也不是本版三次测量。
- 本版测量口径：各做三次“创建评审 → 提交确认 → 收到完整报告”，逐次记录总 wall time、响应 `source`（等价模式）、报告 `chat_calls` 总数，以及 `logs/llm/` 是否出现该评审的真实 `llm_call`。模型出口可用时报告模型组；模型出口不可用时报告确定性组或失败记录，不将它们混成平均数。三次完成后报告中位数与最大值，不因失败额外重试。

## 四、可证伪判据

1. P24 前置报告、CORS 符号、compose UNVERIFIED 与 472 tests 收集数均通过精确二值检查；命令与输出写入 progress。
2. 三次完整链路均有逐次耗时、模式、`chat_calls` 与 LLM 日志证据；失败样本也保留在表内，模型与确定性分组独立计算。
3. 确认请求处于 `running` 时，`stage-elapsed` 每秒增长；超过 20,000 ms 后 `stage-slow-hint` 显示实际秒数；离开 running 后两个钩子隐藏。由三个 Vitest 行为用例证明。
4. 失败状态保留“停在：等待服务返回”，并能看到失败时已等待秒数；步骤不会因计时器而变化。
5. 八处确认请求后的正向等待使用具名 `waitForConfirmed(page)` 与 `CONFIRM_WAIT_MS=60_000`；parse 的负向 `toHaveCount(0)` 保持短等待。
6. 全量 Playwright 逐条记录八条结果。若有任一变绿，抽查 consistency 业务断言：冲突数至少 1、`412 s` 与 `386 s` 可见、无“总分 0”。不通过的用例按结果写明修复、等待策略调整或书面豁免，不以“网络抖动”概括。
7. 后端 pytest 两遍数字一致；build、Vitest、Playwright、容器静态检查、日志与文档编码检查的命令、退出码、末行写入 progress；E2E 前后复核 review 行数。

## 五、遗留与移交

- P26 报告原样继承 P25 的三次耗时分组与八条 E2E 最终状态；不得把模型与确定性路径合并。
- P26 继续承接 P24 遗留：镜像从未构建、`frontend/` 无 Dockerfile、Chroma tag 未验证、chromadb 镜像预期 ≥1GB。
- 八条 E2E 的逐条处置由本版作出，后续不再写“移交 P25”或“沿用上版”。
- 若耗时仍高，后续版本可单独提出图内并行化；这不属于 P25。
