# 首期总验收报告 V2（v1.9.3）

> **报告版本**：V2（第二期验收 · v1.9.3 修复后复验）· 对应提示词版本：`v1.9.3`
> **上一版**：`report.md` = **V1**（第一期验收 · v1.9.2，14 ✅ / 4 ⚠️），**完整保留未覆盖**
> **报告目录**：`docs/plan/acceptance/`（本文件 + `report.md` + `calls/` 51 个调用记录 + `screenshots/` 7 张截图）
> **结论**：18 条 **全部 ✅ / 0 ⚠️ / 0 ❌**，首期验收收口；v1.0.0 标记通过。

## 阅读方式（重要）

本文件**前半部分（§a～§f）是 V1 的历史原文，原样保留作为证据链**，其中的判定表、环境数字与挂账清单反映的是**第一期验收当时**的状态，**不是当前结论**。

**当前结论以文末「# V2 修订记录（v1.9.3）」一节为准**：那里有本轮修复内容、复验范围与结果、以及更新后的 18 条判定总表。

| 你想知道什么 | 看哪里 |
|---|---|
| 当前是否达标、收口没有 | 文末「V2 修订记录」→ 18 条判定总表 + 挂账说明 |
| 第一期当时发现了什么问题 | 本文件 §b / §c / §f（V1 原文） |
| 每一项修复怎么验的 | 文末「V2 修订记录」→ 复验范围与结果表 |
| 某次真实调用的请求与响应 | `calls/` 下对应文件 |

---

## 以下为 V1 历史原文（2026-10-18 第一期验收，原样保留）

> **报告版本**：V1（第一期验收）· 对应提示词版本：`v1.9.2` · 里程碑：v1.0.0 之前的最后一段
> **结论**：18 条中 **14 ✅ / 4 ⚠️ / 0 ❌**；四项 ⚠️ 已由 v1.9.3 修复并复验通过（见文末 V2 修订记录）。

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

> ⚠️ **本节是 V1 第一期的判定原样保留，不是当前结论。** 其中 2.1 / 3.1 / 4.1 / 4.3 四项当时判 ⚠️，**已由 v1.9.3 修复并复验转为 ✅**。当前 18 条判定见文末「# V2 修订记录（v1.9.3）」的更新后总表。

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

> ⚠️ **本节为 V1 第一期的实测记录。** 其中"忽略板凳宽度"一行当时判 ⚠️（模型 quote=null），v1.9.3 接通链路后已转为 ✅，见文末 V2 修订记录。

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

> ⚠️ **本节是 V1 第一期的挂账，四项均已在 v1.9.3 解决**（F1～F4）。当前挂账状态见文末 V2 修订记录的「挂账说明」。

| 挂账 | 本次状态 | 建议补齐 |
|---|---|---|
|---|---|---|
| 板凳龙假设维度未引用“忽略板凳宽度” | 模型返回证据不足；已有非空检索证据，未调整 prompt。 | 后续版本检查维度检索证据呈现和模型选择；保留 quote 子串约束。 |
| 评分页没有量规原文 | 页面仍显示条文未由接口提供；原句定位可用。 | 规划返回 rubric dimension / band_text 的读取接口，再展示实际条文。 |
| 单篇评测差异页 | `/eval/:paperId` 显示缺口说明。 | 后续增加单篇 gold 对照接口与页面后再验。 |
| 历史存档不包含 change_list | 旧评审的 contest_id、rubric_version、维度和 quote 均可读；change_list 不持久化。 | 后续决定报告持久化字段与旧记录兼容方式，再补历史审查清单。 |

本报告为**第一期验收（V1）**，判定 14 条 ✅、4 条 ⚠️、0 条 ❌。按验收规则，四项 ⚠️ 需人明确接受后才能将 v1.0.0 标为通过；当前 `task_plan.md` 保持待接受，不写“首期验收收口”。

> 📌 **以上是 V1 当时的处置决定，已被 v1.9.3 的执行结果取代**：四项 ⚠️ 已全部修复并复验通过，v1.0.0 已收口。见下文 V2 修订记录。

**后续修订**：本报告如因代码修复而重新验收，版本号递增为 V2、V3……，旧版本保留不覆盖；每次修订须在 `docs/plan/findings.md` 记一条 Ruling 说明改了什么。


# V2 修订记录（v1.9.3）

> 前半部分完整保留 V1 历史报告；本节是本轮修订后的当前结论。原始 V1 文件仍保存在 `report.md`。

## 修订原因与变更

V1 的四项 ⚠️ 分别涉及板凳宽度证据未进入选档 prompt、评分页缺少量规条文、缺少单篇评测差异接口/页面、历史存档未保存 change_list。本轮接通 constraints 与 evidence_prompts，增加只读量规与单篇评测接口/页面，并为 review 增加 nullable change_list 字段。旧记录保持 NULL，不重算、不删除；读取时返回空数组及旧数据说明。

F2 采用 `GET /api/contests/{contest_id}/rubric`，避免改变现有 `/api/contests` 的响应形状。F3 默认使用 deterministic 系统结果，页面访问不触发模型批量调用；无 gold 时返回明确说明。F4 的 schema 迁移幂等新增 nullable 列，不回填历史记录。

## 复验范围与结果

| 修复 | 复验 | 结果与证据 |
|---|---|---|
| F1 / §12.2 第 1 条 | bench-dragon 真实模型 resume，并与 V1 assumption 输出对照 | ✅ constraints 与 evidence_prompts 已到达 prompt。V1 assumption 为“证据不足”、quote=null；本轮为“不足”，引用原句：“为简化计算，本文忽略板凳宽度，把每节板凳视为刚体连杆，只保留两端把手孔中心的位置关系；”。完整响应见 `calls/11-resume-bench-dragon.json` 与 `calls/v193-02-resume-bench-dragon.json`。模型仍自行判档，未调整 prompt 引导结果。圆弧缺项仍判“不足”。 |
| F2 / §12.3 第 1 条 | rubric API、评分页与截图 | ✅ 五维各四档由接口返回并显示；见 `calls/v193-03-rubric.json`、`screenshots/v193-rubric-scoring.png`。 |
| F3 / §12.4 第 1 条 | 有 gold 单篇接口、页面及无 gold 演示稿空态 | ✅ eval-01 返回五维差异；演示稿明确说明无 gold。见 `calls/v193-04-eval-paper.json`、`screenshots/v193-single-eval.png`。 |
| F4 / §12.4 第 3 条 | 新记录与 V1 历史记录读取 | ✅ 新记录返回 3 条 change_list；旧记录 `2525dc7818854d2e836d14aa319a6552` 返回空数组及“该记录为旧数据，未保存审查清单”。见 `calls/v193-05-new-review-archive.json`、`calls/v193-06-old-review-archive.json`。 |

## 更新后的 18 条判定总表

| 条目 | 判定 | 依据 |
|---|---|---|
| 1.1 | ✅ | 沿用 V1：三道赛题及约束核验通过。 |
| 1.2 | ✅ | 沿用 V1；本轮另补 published 量规接口证据。 |
| 1.3 | ✅ | 沿用 V1：样例与默认评测统计通过。 |
| 2.1 | ✅ | 规则类必现点通过；本轮板凳宽度原句已进入 assumption quote，圆弧缺项仍判“不足”。 |
| 2.2 | ✅ | 沿用 V1：种植样例规则核验通过。 |
| 2.3 | ✅ | 沿用 V1：烟幕样例规则核验通过。 |
| 3.1 | ✅ | 量规接口返回五维四档，评分页显示真实条文。 |
| 3.2 | ✅ | 沿用 V1：排除项及前端表格通过。 |
| 3.3 | ✅ | 沿用 V1：change_list 上游关联及建议展示通过。 |
| 3.4 | ✅ | 沿用 V1：受控词扫描通过。 |
| 4.1 | ✅ | 有 gold 的单篇差异接口与页面可用；无 gold 篇目有明确说明。 |
| 4.2 | ✅ | 沿用 V1：六步进度展示及非定时器核验通过。 |
| 4.3 | ✅ | 新记录保存 change_list；旧记录兼容说明可读，未重算、未删除。 |
| 5.1 | ✅ | 沿用 V1：fixture-extra 导入、发布及评审通过。 |
| 5.2 | ✅ | 沿用 V1：坏包拒绝且既有题目不受影响。 |
| 5.3 | ✅ | 沿用 V1：量规版本发布与旧记录版本保持通过。 |
| 5.4 | ✅ | 沿用 V1：归档后题目消失、既有评审仍可读。 |
| 5.5 | ✅ | 沿用 V1：端点、配置 scheme 与本地模型关键词检查通过。 |

## 自动门禁与数据状态

| 命令 | 退出码 | 最后一行 |
|---|---:|---|
| `$env:PYTEST_DEBUG_TEMPROOT='.pytest_tmp'; & 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe' -m pytest backend/tests -q` | 0 | `159 passed, 2 warnings in 14.00s` |
| `npm run build` | 0 | `✓ built in 690ms`（有 bundle 体积提示） |
| `npx vitest run` | 0 | `Tests 110 passed (110)` |
| `npx playwright test` | 0 | `43 passed (48.5s)` |

MySQL 复验后行数：contest 4、rubric 5、dimension 25、constraint 16、paper_parent 376、review 297、review_dimension 1,475、review_session 321。计数包含自动化测试新增评审；本轮 schema migration 前后 review 行数一致，旧记录未批量更新或删除。

## 缺陷修复与范围核对

- F1：接通 constraints 与 evidence_prompts 的传递，补充单测和集成测试。
- F2/F3：新增只读路由、API 类型/封装、量规展示与单篇差异表；无量规数据时仍保留占位说明。
- F4：`Review.change_list` 为 nullable JSON；schema 幂等新增列；旧 NULL 记录读取时返回空数组和说明。
- 冻结文件 `backend/tests/graph/test_interrupt.py`、`backend/tests/retrieve/test_rerank_cap.py` 未修改；`backend/app/report/evaluation.py`、`.env`、`backend/requirements.txt` 未修改。

## 挂账说明

18 条均为 ✅。bench-dragon assumption 维模型判为“不足”而非“充分”，但已引用忽略板凳宽度的原句；这是模型判档结果，不构成链路缺陷。圆弧缺项同样按真实模型输出记录，不通过调整 prompt 追求目标答案。单篇页面默认采用 deterministic 结果；若后续需要模型级单篇对照，应另行定义显式触发方式。
