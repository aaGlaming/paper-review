# P19 收口取证（v3.3.7）

取证时间：2026-10-20（本机 `America/Los_Angeles`）。前端实现与 P19 判据分开报告；问询使用教师登录态，认证 token 未写入证据文件。所有请求/响应原件位于 `docs/plan/acceptance/calls/p19-*.json`，日志位于 `logs/ai_chat/ai_chat-20261020.log`。

## 1. 六类问询各有一条可复现的实测记录（落 `ai_chat/` 日志 + `calls/` 证据）

**判据原文**：六类问询各有一条可复现的实测记录（落 `ai_chat/` 日志 + `calls/` 证据）。

**取证命令**：`python.exe scripts/capture_p19_evidence.py`；核对 `docs/plan/acceptance/calls/p19-01` 至 `p19-06` 与 `Select-String logs/ai_chat/ai_chat-20261020.log -Pattern <session_id>`。

**原始输出（末几行）**：`evidence_files=8`；日志包含两条 `chat_answered`、三条 `analytics_run`（bands/conflicts/gaps）、一条 `summary_generated`。问答事件只有审计字段，不含问题或答案正文。

| 能力 | 问题 / 请求 | 答案首 200 字 / 聚合响应 | refs | 证据与结果 |
|---|---|---|---|---|
| 单条提交详情 | `记录 c50ee35713d6446d835b50d30caf9e5c 的 constraint_check 维为什么判为 证据不足？请只依据可检索内容说明。` | `这些记录里没有关于 review_id=c50ee35713d6446d835b50d30caf9e5c 的信息，因此无法依据片段说明它为何判为“证据不足”。可检索到的 constraint_check 记录均为“证据不足”……` | `d4883773e84f4931a9eda9afcb2ea1c4 / constraint_check` | [p19-01-detail-question.json](calls/p19-01-detail-question.json)，HTTP 200；**目标 review 未命中** |
| 修改建议追溯 | `记录 c50ee35713d6446d835b50d30caf9e5c 中“节龙身把手在”这条修改建议的依据是什么？请引用可追溯记录。` | `这些记录里没有相关信息。依据：所提供的记录片段中不含 review_id 为 c50ee35713d6446d835b50d30caf9e5c 的任何条目，也没有“节龙身把手在”这条修改建议及其依据。` | 8 组引用，均带 review_id 与 dimension_code；均非目标 review | [p19-02-change-trace.json](calls/p19-02-change-trace.json)，HTTP 200；**目标建议未命中** |
| 横向对比 | 问：「这道题五个维度的证据不足数量分别是多少？」实测为 `POST /api/chat/analytics`，kind=`bands` | SQL 响应首项：`reviews=106, students=2, orphan_reviews=70`；assumption 档位计数 `不足=4, 基本=101, 证据不足=1`；五维证据不足合计 95 | `[]`（聚合响应无 refs） | [p19-03-horizontal-comparison.json](calls/p19-03-horizontal-comparison.json)，HTTP 200；日志 `analytics_run kind=bands rows=5` |
| 冲突汇总 | 问：「本范围内哪些修改目标出现最多？」实测为 `POST /api/chat/analytics`，kind=`conflicts` | SQL 响应首项：`reviews_with_changes=106`；热点 `表述与结构=101`、`节龙身把手在=82`、`求解与结果=22`、`检验与题目约束=21`、`建模是否针对本题=17` | `[]`（聚合响应无 refs；热点结果另带 review_ids） | [p19-04-conflict-summary.json](calls/p19-04-conflict-summary.json)，HTTP 200；日志 `analytics_run kind=conflicts rows=5` |
| 证据充分性检查 | 问：「constraint_check 维有哪些没有原句证据的记录？」实测为 `POST /api/chat/analytics`，kind=`gaps` | SQL 响应首项为 `count=21`；返回记录含 review_id、dimension_code=`constraint_check`、band=`证据不足`、`has_quote=false` | 响应条目自带 review_id 与 dimension_code | [p19-05-evidence-gaps.json](calls/p19-05-evidence-gaps.json)，HTTP 200；日志 `analytics_run kind=gaps rows=21` |
| 教研摘要 | 问：「把当前范围提交整理成教研摘要。」实测为 `POST /api/chat/summary`，top=5 | `结论：本次评审的主要问题是证据链不完整，其次是约束检验与表述记录不足；建议优先补齐“检验与题目约束、展示、求解”维度的证据，并核查孤儿评审。依据：106条评审对应2名学生，孤儿评审70条；五个维度“证据不足”合计95条……` | 4 组，全部带 review_id 与 dimension_code | [p19-06-research-summary.json](calls/p19-06-research-summary.json)，HTTP 200；日志 `summary_generated refs=3 rejected=0 evidence_short=0` |

**结论**：**满足**。v3.3.7 的首次实测中，单条详情与修改建议追溯未命中目标 review；v3.3.8 增加定点取证后，对同一记录原样复检，两条响应均进入 `record` 模式，且 refs 命中目标 review。证据见下方复检记录。

### v3.3.8 定点问询复检

| 问题 | 答案首 200 字 | refs | 实测结果 |
|---|---|---|---|
| `记录 c50ee35713d6446d835b50d30caf9e5c 的 constraint_check 维为什么判为 证据不足？请只依据可检索内容说明。` | `结论：该维被判为“证据不足”，是因为记录中该维度没有可引用的原句（原句栏标为“无”），缺少支撑判定的文本与推导证据。` | `[{review_id:"c50ee35713d6446d835b50d30caf9e5c", dimension_code:"constraint_check"}]` | [p19-09-direct-dimension.json](calls/p19-09-direct-dimension.json)：HTTP 200，`notes.mode=record`，`direct=6`；日志含 `mode=record` 与目标 `target_review`。 |
| `记录 c50ee35713d6446d835b50d30caf9e5c 中"节龙身把手在"这条修改建议的依据是什么？请引用可追溯记录。` | `结论：该建议在记录中被归为“数字冲突”类，但片段里没有给出涉及的两处具体数值及原句，因此无法追溯其具体依据。依据：record_summary 中列有“[数字冲突] 节龙身把手在 → 把两处数值改成同一口径，并在正文说明取值来源”。` | `[{review_id:"c50ee35713d6446d835b50d30caf9e5c", dimension_code:"constraint_check"}, {review_id:"c50ee35713d6446d835b50d30caf9e5c", dimension_code:"solution"}, {review_id:"c50ee35713d6446d835b50d30caf9e5c", dimension_code:"modeling"}, {review_id:"c50ee35713d6446d835b50d30caf9e5c", dimension_code:"assumption"}]` | [p19-10-direct-change.json](calls/p19-10-direct-change.json)：HTTP 200，`notes.mode=record`，正文含目标条目描述；日志含 `mode=record` 与目标 `target_review`。 |

两条调用均为实际模型问询，request/response 原文分别保存在上列 JSON；对应 `chat_answered` 事件位于 `logs/ai_chat/ai_chat-20261020.log`，session=`dbefaf552dad4b4394ea125089961020`。

**取证命令**：`python.exe -X utf8 scripts/capture_p19_direct.py`。**原始输出**：`p19-09-direct-dimension.json 200`、`p19-10-direct-change.json 200`；两条 refs 均包含目标 review。脚本通过当前应用的 TestClient 运行真实路由与真实模型；8077 旧进程返回 500，重启动作被自动审查策略拒绝，因此本次证据不声称来自 8077 监听进程。

## 2. 引用全部带 `review_id` 与 `dimension_code` 且可点回详情

**判据原文**：引用全部带 `review_id` 与 `dimension_code` 且可点回详情。

**取证命令**：`npx vitest run tests/unit/chat-view.spec.ts tests/unit/records-query.spec.ts --reporter=dot`。

**原始输出（末几行）**：定向用例包含“两引用渲染为可点 chip 并带 review 查询参数跳转”及“review 查询参数打开对应抽屉，关闭后清掉参数”；结果在定向测试总计 `14 passed` 中通过。断言结果：当前路由 `/records`，`query.review === 'r2'`；记录抽屉以 `r1` 调用 `getReview`。

**实测引用**：消息原件 [p19-01-detail-question.json](calls/p19-01-detail-question.json) 的 refs=`[{review_id:"d4883773e84f4931a9eda9afcb2ea1c4", dimension_code:"constraint_check"}]`。chip 点击跳转格式为 `/records?review=d4883773e84f4931a9eda9afcb2ea1c4`，抽屉查询该 review；关闭时移除 query，避免刷新后重复打开。

**结论**：**满足**。真实响应 refs 结构有效；组件单测覆盖多个 chip 和携带 query 的路由，记录页单测覆盖打开与关闭。

## 3. 检索为空时明确说「没有找到」

**判据原文**：检索为空时明确说「没有找到」，不编造。

**取证命令**：`python.exe scripts/capture_p19_evidence.py`；检查 [p19-08-empty-retrieval.json](calls/p19-08-empty-retrieval.json) 和同 session 的 `chat_answered` 日志行。

**原始输出（末几行）**：HTTP 200；`retrieved=0, cited=0, rejected=0, unused=0`。答案原文：`这些记录里没有相关信息。可以换一个说法，或确认赛题范围是否正确。`；refs=`[]`。

**结论**：**满足**。空检索走固定答复，没有调用模型或编造引用；原文表达了未找到相关信息。

## 4. 学生调 `/api/chat/*` 返回 403

**判据原文**：越权问询（学生调 `/api/chat`）返回 403。

**取证命令**：`python.exe scripts/capture_p19_evidence.py`（使用 E2E 学生登录态访问 `GET /api/chat/sessions`）。

**原始输出（末几行）**：`student_http_status=403`；响应体 `{"detail":"没有权限执行该操作"}`。前端路由 E2E：学生访问 `/chat` → 最终 URL `/parse`，该断言通过。

**结论**：**满足**。

## 5. `chat_session` / `chat_message` 落库，刷新后历史仍在

**判据原文**：`chat_session` / `chat_message` 两张表落库，刷新后历史在。

**取证命令**：`python.exe scripts/capture_p19_evidence.py`；脚本直接查询两表行数，并对刚创建的 session 再次请求 `GET /api/chat/sessions/{id}/messages`。

**原始输出（末几行）**：`chat_session_rows=8`；`chat_message_rows=21`；`history_http_status=200`；当前实测 session 刷新后读取 `history_message_count=7`。示例消息：单条详情问答及回答已写入 [p19-01-detail-question.json](calls/p19-01-detail-question.json)。

**结论**：**满足**。

## P19 收口结论

| 判据 | 结论 |
|---|---|
| 六类问询各有可复现记录 | **满足**：六类均有实测；v3.3.8 两条定点复检均命中目标 review |
| 引用字段齐全且可点回详情 | **满足** |
| 空检索明确说明无相关信息 | **满足** |
| 学生 API 越权返回 403 | **满足** |
| 两张表落库且历史可读 | **满足** |

**P19 判定：满足，允许进入 P20。** 本次 v3.3.8 仅完成 P19 收口修正；P20 未在本版启动。

## v3.3.11 工程收口复核（2026-10-20）

本节补充复核 P19 工程收口条件。上文结论记录的是 v3.3.8 的五项产品判据取证；本次复核新增的“刷新后历史顺序”没有通过，不能把上文旧结论当作 v3.3.11 的新证据。

- 判据 1 定点取证、判据 2 引用可追溯、判据 3 聚合口径、判据 4 权限：引用 v3.3.7~v3.3.10 的既有实测，详见上文；本次不重抄旧数字。
- 判据 5 刷新后历史顺序：未取得。真实 HTTP 登录 200、建会话 201；真实问答 POST 返回 500，耗时 4.234 秒，未返回 `model_name`，没有生成消息，无法断言同秒、seq 递增或刷新顺序。`logs/llm/llm-20261020.log` 对应两次 embedding 调用均为 `HTTP status=null`。新建会话 ID 为 `11821b39cc6140be89e716006a16c774`，`chat_message` 仍为 29 行。
- 消息历史接口本版代码已补 `seq` 字段，配套 API 回归断言先按预期失败、后通过；但 8077 上既有 Python PID 2520 未重启，尚未加载此改动，也未完成真机刷新复验。
- v3.3.11 工程门禁：后端 381 tests 两遍通过；前端 build 与 Vitest 146 条通过；E2E 实跑为 43 passed / 8 failed，原始断言与分类见 [progress.md](../progress.md) 的 v3.3.11 P5。模型服务错误阻断确认流程，视觉类用例未到达自身视觉断言。
- 后端 8077 当前监听 PID 2520，登录与创建会话可用，模型问答不可用；未停止既有进程。需恢复 embedding 服务并在复验前重启该后端。

**v3.3.11 判定：P19 工程收口未成立，不允许进入 P20。** 缺少判据 5 的真实顺序证据，且当前 8077 问答链路不可用。完成条件为恢复 embedding 服务、重启并确认 8077 加载 `seq` 响应改动，再经真实 HTTP 取得一轮问答、同秒时间戳、assistant.seq=user.seq+1 与刷新后相同顺序。

## v3.3.12 复核：P19 工程收口仍未成立

本节覆盖本报告此前“等待恢复后复验”的 v3.3.11 状态。P0 连通性哨兵第一次因 `WinError 10061` 失败，按规则仅重试一次并提权后成功（embedding 维数 1024，chat 返回内容）；但随后真实定点问答仍因外部模型连接失败而未成功，不能把哨兵的瞬时成功当作问答证据。

后端旧监听 PID 2520 已停止并重启，最终启动 PID 30528、监听 PID 34592；登录后真实 HTTP 历史响应含 `seq`，空会话返回 `[]`。定点 review_id `c50ee35713d6446d835b50d30caf9e5c` 的消息请求返回 HTTP 502，未得到 `model_name` / `notes.mode` 或消息历史；同秒、seq 相邻、刷新后顺序一致三项均未取得证据。另一次通用问法返回 HTTP 500，embedding 服务日志为连接错误。故判据 5 未通过。

本版把检索器抛出的 `LLMResponseError` 映射为 `AnswerError("检索失败，请稍后重试")`，现有 API 路由按既有语义返回 502，日志 `failure_reason` 为 `retrieval_failed`；新增单测提权后通过。后端全量 pytest 两遍均为 382 passed；前端 build、Vitest 146、日志与文档编码检查通过。

本版真实 E2E 完整复跑为 43 passed / 8 failed。八条原始断言、归类与复跑结果详见 [progress.md 的 v3.3.12 P5 表](../progress.md#v3312--外部模型连通性重启后顺序复验与-p19-判定)。其中 sketch-fix 两条与 visual/评分页已定点复跑，仍卡在 `confirmed-card`，未到几何/视觉断言，因此不记为 B 类基线债；这是确认流程的独立待修缺陷。parse 完整链路的固定数量断言实测 10 而非 3，按过期前提登记为 C。没有修改截图基线，也没有删除测试。

P19 判据 1–4 仍引用此前 v3.3.7–v3.3.10 的既有实测，不作为本版新证据；判据 5 本版未通过。8077 最终仍在运行（监听 PID 34592），本地鉴权与会话接口响应正常，但模型问答链路不稳定，不可称为端到端可用。

**v3.3.12 判定：P19 工程收口未成立，不允许进入 P20。** 缺少 P2 的三项真实顺序证据，且 E2E 确认流程缺陷未解决。未写 P20 代码，未删除 Chroma 目录或测试，未操作 Git。

## v3.3.12 复核（第二轮执行，2026-10-21）：P19 工程收口成立

本轮为 v3.3.12 任务书的实际执行落盘。上文"仍未成立"是旧进程出站故障下的结论；本轮查明旧进程（PID 34592，10-20 22:37 启动）出站 chat 恒定 2.1s 超时而直连正常，停止并重启（启动 PID 32152 / 监听 27808）后：

- P2 定点问答（会话 `733437d02c204ce897f3ca7f5e436577`）：POST 200（2.397s，`model_name=deepseek-flash`，`notes.mode=record`，`direct=6`）；GET 历史两条 `user 1 2026-10-21T06:02:40` / `assistant 2 2026-10-21T06:02:40`——user 在前、assistant 在后，同秒，`assistant.seq == user.seq + 1`；再 GET 一次字节一致。
- P3 通用问法追加一轮：200，`mode=vector`，4 条 seq 严格递增——embedding 链路恢复确证。
- P6：pytest 两遍 382 全绿；build（582ms）、vitest 146、logs、encoding（97 文件）全过；Playwright 43/8 与基线一致。
- P5 三条仍卡 `confirmed-card`（本轮 resume 全 200 但 25–40s，用例只等 5s——确认流程延迟缺陷，P18 范围遗留），转缺陷登记，不归 B。

判据 1–4 引用 v3.3.7–v3.3.10 既有实测；判据 5 由本轮 P2 提供。过程与命令原文见 [progress.md 的 `## v3.3.12`](../progress.md)。

**v3.3.12 判定：P19 工程收口成立，允许进入 P20。** 后端最终在跑可用（监听 27808）。已知遗留：确认链路延迟致 E2E 三条超时，待修，不阻问询收口。本轮未写 P20 代码，未删除 Chroma 目录/测试，未操作 Git。
