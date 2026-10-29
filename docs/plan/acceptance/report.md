# 首期总验收报告 V1（v1.9.2）

> **报告版本**：V1（第一期验收）· 对应提示词版本：`v1.9.2` · 里程碑：v1.0.0 之前的最后一段
> **报告目录**：`docs/plan/acceptance/`（本文件 + `calls/` 45 个调用记录 + `screenshots/` 5 张截图）
> **结论**：18 条中 **14 ✅ / 4 ⚠️ / 0 ❌**；四项 ⚠️ 待用户明确接受后方可将 v1.0.0 标为通过。

验收时间：2026-10-18（Asia/Shanghai）。验收依据：需求 V3 第十二章；上一版 smoke 与本版首期验收表。真实请求的请求体、HTTP 状态与响应体保存在 `calls/`，图片证据保存在 `screenshots/`。密钥只检查是否配置，没有读取值、记录值或输出值。

## a. 验收环境

- 后端解释器：Python 3.11.16，路径为 `D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe`。pytest 全量复跑为 `152 passed, 2 warnings in 5.34s`，退出码 0。
- MySQL 3306 在监听；验收结束时 contest 共 4 行（3 published、1 archived）、rubric 5 行、dimension 25 行、constraint 16 行、paper_parent 302 行、review 270 行、review_dimension 1,340 行、review_session 293 行；Chroma 子块 338 条。计数包含历史 smoke、E2E 和本次验收记录，没有清理历史数据。
- 配置状态仅记录键名与是否配置：

  | 配置键 | 已配置 |
  |---|---|
  | `LLM_BASE_URL` | 是 |
  | `LLM_API_KEY` | 是 |
  | `LLM_MODEL` | 是 |
  | `EMBEDDING_BASE_URL` | 是 |
  | `EMBEDDING_API_KEY` | 是 |
  | `EMBEDDING_MODEL` | 是 |
  | `RERANK_BASE_URL` | 是 |
  | `RERANK_API_KEY` | 是 |
  | `RERANK_MODEL` | 是 |

  embedding 与对话 base URL 的 scheme 均为 HTTPS。真实 SiliconFlow rerank 请求返回 HTTP 200，排序下标为 `[1, 0]`。完整键状态（仅布尔值）见 `calls/35-config-source-audit.json`。
- 服务：Uvicorn 127.0.0.1:8077、Vite 127.0.0.1:5173。HTTP 请求使用 `curl --noproxy "*"`。本版没有改动前端、后端代码或 `.env`。
- 自动化环境门禁：用户要求的 pytest 前置复跑通过；上一版 build / Vitest / Playwright 仍以 v1.9.1 的记录为准，本次未改前端源码。页面行为另以当前 Vite 服务和 Playwright 做了真实页面检查。

## b. 18 条判定总表

| 条目 | 判定 | 依据 | 证据 |
|---|---|---|---|
| 1.1 | ✅ | 三道赛题均 published；约束有 check_type 与 params。 | `01-contests.json`, `10-database-rubric-audit.json` |
| 1.2 | ✅ | 三个当前 published 量规各有五维，每维四档说明；按数据库验收。 | `10-database-rubric-audit.json` |
| 1.3 | ✅ | 样例 15 条，其中演示 3 条；默认评测统计 corpus 15、gradable 12。 | `02-samples.json`, `03-eval-deterministic.json` |
| 2.1 | ⚠️ | 412/386 规则冲突和页面两处定位通过；圆弧缺项维度为“不足”；模型没有为“忽略板凳宽度”给出 quote。 | `11-resume-bench-dragon.json`, `36-playwright-ui-validation.json` |
| 2.2 | ✅ | 种植样例包含豆类 / 半价情形缺口和 1286 / 974 金额冲突。 | `13-resume-planting.json` |
| 2.3 | ✅ | 烟幕样例命中时长冲突、缺失引用和速度越界；本样例明确写有 3 m/s 下沉，静止云团的条件未触发。 | `15-resume-smoke.json`, `36-playwright-ui-validation.json` |
| 3.1 | ⚠️ | 五维卡片与原句定位可用；卡片仍显示“量规条文由后端提供，当前接口未给出”的占位说明，不能打开实际条文。 | `36-playwright-ui-validation.json`, `screenshots/03-scoring-real-report.png` |
| 3.2 | ✅ | 评审 score.excluded 有排除项；评分页表格行数与该次结果一致。 | `13-resume-planting.json`, `36-playwright-ui-validation.json` |
| 3.3 | ✅ | 种植评审 4 条 change_list 均含 upstream_id，建议页展示 4 条及 4 个上游编号。 | `13-resume-planting.json`, `36-playwright-ui-validation.json` |
| 3.4 | ✅ | 五个已渲染页面、保存的 API 响应及 render_change_list 输出，六项受控词扫描均为 0。 | `36-playwright-ui-validation.json`, `37-sensitive-content-scan.json` |
| 4.1 | ⚠️ | 显式模型评测有三项指标；单篇页面仍只有缺口说明，没有单篇差异接口。 | `16-eval-model.json`, `36-playwright-ui-validation.json` |
| 4.2 | ✅ | 解析页实际报告状态为 done，六步均显示完成；views 下没有定时器调用。 | `36-playwright-ui-validation.json` |
| 4.3 | ⚠️ | v1.9.1 历史记录仍为量规 v1 且有原句；存档响应不含 change_list。 | `31-recheck-v191-review.json` |
| 5.1 | ✅ | fixture-extra 导入、发布后显示为第四题，并完成五维模型预审。 | `20-import-fixture.json`–`24-resume-fixture-review.json` |
| 5.2 | ✅ | fixture-extra 处于 published 时提交无 BOM 的坏包，权重和为 99，返回 400、filename=`rubric.json`、field=`dimensions.weight`；四题仍 published。 | `40-republish-fixture-for-atomicity.json`–`42-contests-preserved-after-invalid.json` |
| 5.3 | ✅ | A 题量规 v2 发布成功，新评审 rubric_version=2，旧 smoke 记录仍为 1。 | `27-draft-rubric-A-v2.json`–`31-recheck-v191-review.json` |
| 5.4 | ✅ | fixture-extra 归档后列表只剩三道 published 题，原评审记录仍返回 200。 | `32-archive-fixture.json`–`34-get-fixture-review-after-archive.json` |
| 5.5 | ✅ | 对话、嵌入与重排端点在唯一模型客户端中；两个要求的 base URL 为 HTTPS；本地运行时扫描为 0。 | `11-live-rerank.json`, `35-config-source-audit.json` |

## c. 三篇演示必现结果实测表

| 样例 | 必现点 | 实测 | 判定 / 证据 |
|---|---|---|---|
| bench-dragon | 412 s 与 386 s 冲突；页面分别定位 | change_list 有两条 evidence；页面点击后两处 mark 均精确匹配。字符偏移为 175 与 699；屏幕坐标约为 (681.39, 916.05) 与 (334.64, 1126.41)。 | ✅ `11-resume-bench-dragon.json`; `screenshots/02-consistency-located.png` |
| bench-dragon | “忽略板凳宽度”进入假设维度 quote | 模型输出：`band=证据不足; status=证据不足; quote=null; reason=模型在给定证据里没有找到可引用的原句`。输入假设章节确实含该原句，模型虽收到父块证据仍未引用。 | ⚠️ `11-resume-bench-dragon.json` |
| bench-dragon | 未讨论相切圆弧约束时降为证据不足或不足 | constraint_check 输出“不足”，quote 为“未出现相互穿模的情况”；change_list 同时列出圆弧条件未提及。 | ✅ `11-resume-bench-dragon.json` |
| planting | 豆类与 50% 降价 / result1_2 情形缺口 | change_list 分别含 `cumcm-2024-C-legume-three-years` 与 `cumcm-2024-C-half-price`。 | ✅ `13-resume-planting.json` |
| planting | 摘要与汇总表 1286 万元 / 974 万元冲突 | 数字冲突项 evidence 同时保存两数。 | ✅ `13-resume-planting.json` |
| smoke | 22.4 s 与 18.6 s 冲突 | change_list evidence 同时保存两数。 | ✅ `15-resume-smoke.json` |
| smoke | 引用 [12] 缺失 | change_list 有引用缺失项，evidence 为 `[12]`。 | ✅ `15-resume-smoke.json` |
| smoke | 160 m/s 越界 | change_list 有 `cumcm-2025-A-uav-speed` 越界项，evidence 为 `160 m/s`。 | ✅ `15-resume-smoke.json` |
| smoke | 静止云团且无 3 m/s 下沉时不得充分 | 此演示稿假设明确写了起爆后以 3 m/s 下沉，因此静止云团条件不适用；模型 constraint_check 为“不足”。 | 条件未触发 `data/samples/smoke.md`; `15-resume-smoke.json` |

另：三篇均由真实 API 创建并 resume，HTTP 分别为 201 / 200，source=model、model_name=deepseek-flash，各维 chat_calls=1。页面复核用这些真实响应写入浏览器会话后读取，不重复发起模型评审；五维卡片 5 张、引用按钮 5 个。评分页实际显示 1 条排除项，建议页 4 条建议均显示上游编号。截图与坐标记录见 `screenshots/` 及 `36-playwright-ui-validation.json`。

## d. 三项评测指标

| 指标 | 真实模型（force=model） | deterministic 基线 | 口径 |
|---|---:|---:|---|
| 档位一致率 | 13 / 60 = 21.67% | 26 / 60 = 43.33% | 有 gold 的维度中，系统档位与 gold 相同的数量 |
| 引用精确匹配率 | 27 / 27 = 100% | 60 / 60 = 100% | 有引用的维度中，原句逐字位于引用父块中的比例；两条路径给出 quote 的分母不同 |
| 证据不足命中情况 | 2 / 2 = 100% | 0 / 2 = 0% | gold 判证据不足的维度中，系统也判证据不足的数量 |

真实评测：`GET /api/eval/summary?force=model` 返回 HTTP 200、source=model、corpus_papers=15、gradable_papers=12。完整响应见 `16-eval-model.json`。普通 `/api/eval/summary` 未触发真实评测，仍返回 deterministic，见 `03-eval-deterministic.json`。

## e. 发现的缺陷与最小化修复记录

- 未发现需要修改后端实现的真实规则缺陷；无需代码修复，也未对 prompt 作引导性修改。板凳宽度问题属于模型从已检索证据中未选出原句，作为 ⚠️ 留账。
- 量规条文、单篇评测差异和存档 change_list 缺口属于既有接口 / 页面能力边界，本版严格按验收做记录，没有修改前端或后端。
- 验收工具层有两次失败输入，均保留原始证据：calls 04–09 是 PowerShell 原生参数转义丢失 JSON 引号，得到 422；call 25 是临时文件 BOM 导致 JSON 解析错误。改用 UTF-8 无 BOM 临时请求后，calls 10–15 完成真实模型调用；call 41 在四题均 published 时正确触发 `dimensions.weight` 权重和校验，call 42 证实列表未变；calls 43–45 将 fixture-extra 恢复为 archived 并复查评审记录可读。它们不是产品代码缺陷。
- 真实 SiliconFlow rerank 独立调用返回 HTTP 200、排序 `[1, 0]`；真实 embedding 在评审索引建立中成功写入 Chroma。本次没有修改代码。

## f. 挂账清单

| 挂账 | 本次状态 | 建议补齐 |
|---|---|---|
| 板凳龙假设维度未引用“忽略板凳宽度” | 模型返回证据不足；已有非空检索证据，未调整 prompt。 | 后续版本检查维度检索证据呈现和模型选择；保留 quote 子串约束。 |
| 评分页没有量规原文 | 页面仍显示条文未由接口提供；原句定位可用。 | 规划返回 rubric dimension / band_text 的读取接口，再展示实际条文。 |
| 单篇评测差异页 | `/eval/:paperId` 显示缺口说明。 | 后续增加单篇 gold 对照接口与页面后再验。 |
| 历史存档不包含 change_list | 旧评审的 contest_id、rubric_version、维度和 quote 均可读；change_list 不持久化。 | 后续决定报告持久化字段与旧记录兼容方式，再补历史审查清单。 |

本报告为**第一期验收（V1）**，判定 14 条 ✅、4 条 ⚠️、0 条 ❌。按验收规则，四项 ⚠️ 需人明确接受后才能将 v1.0.0 标为通过；当前 `task_plan.md` 保持待接受，不写“首期验收收口”。

**后续修订**：本报告如因代码修复而重新验收，版本号递增为 V2、V3……，旧版本保留不覆盖；每次修订须在 `docs/plan/findings.md` 记一条 Ruling 说明改了什么。
