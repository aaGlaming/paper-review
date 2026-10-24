# paper-review 项目技术文档

> 本文基于项目代码、配置、依赖和现有文档整理。凡是当前代码没有实现或无法确认的内容，均标注为“代码中未体现”或“设计建议”，不把设计建议描述成现成功能。

- 项目事实基线：[项目事实清单](../../项目事实清单.md)
- 总体架构图：[system-architecture.mmd](archify/system-architecture.mmd)
- 主要入口：`backend.app.api.app:app`
- 当前服务形态：FastAPI + Vue 单体应用，MySQL 持久化，Chroma 本地持久化，模型服务通过 HTTP 调用

## 1. 项目概述与定位

### 1.1 产品定位

paper-review 是竞赛论文预审工作台。用户提交一篇论文，系统解析章节，绑定已发布的赛题量规，逐维检索证据、选择档位、执行一致性检查，并输出可回溯的修改清单。每个有证据的维度必须附一条能在正文父块中逐字找到的连续原句。来源：`README.md` 项目简介；`backend/app/scoring/selection.py:parse_scoring_json`、`apply_mention_guard`；`backend/app/report/change_list.py`。

它的核心是 **Agent 工作流**，不是单纯的增强型 Chat：

1. 主业务入口是 `POST /api/reviews` 和 `POST /api/reviews/{review_id}/resume`，对应 LangGraph 的 `parse → confirm → retrieve → score` 状态图。
2. `score` 阶段按顺序运行证据 Agent、题目匹配 Agent、论证结构 Agent、主评审 Agent 和核验 Agent。
3. `/api/chat/*` 是独立的记录级问询功能：它检索已保存的评审记录并生成带引用回答，不承担主评审状态机。

来源：`backend/app/graph/review_graph.py:build_review_graph`；`backend/app/agent/runner.py:make_agent_runner`；`backend/app/agent/specialists.py`；`backend/app/api/chat_routes.py`。

### 1.2 功能边界

当前明确保证的边界：

- 不输出奖项、名次和获奖概率。来源：`README.md` 三条硬边界；`backend/app/report/change_list.py` 的禁止词规则。
- 只对已发布量规且有维度的赛题执行评分；缺少可评量规时接口返回 422。来源：`backend/app/api/routes.py:_load_evaluable_inputs`、`create_review_endpoint`、`resume_review_endpoint`。
- 论文章节必须先经过人工确认，确认前不进入评分。来源：`backend/app/graph/review_graph.py:_confirm_node`；`backend/app/api/routes.py:resume_review_endpoint`。
- 只在线接收 `.md` 和 `.docx`；PDF/OCR 要在系统外转换。来源：`backend/app/api/routes.py:upload_markdown_endpoint`；`data/README.md`；`scripts/pdf_to_md.py`。
- 引用校验是连续子串校验；引用不成立时保留档位但不进入有效加权，`证据不足` 不换算分数。来源：`backend/app/scoring/selection.py`；`backend/app/scoring/aggregate.py:weighted_sum`。

当前没有实现或无法从代码确认的边界：

- 选错题的内容级判定没有作为主评审结论实现；题目匹配 Agent 只写入 `topic_fit`，不改维度档位。来源：`backend/app/agent/specialists.py:run_topic_fit_agent`；`backend/app/agent/tools.py:submit_topic_fit`。
- 不支持多租户、跨副本共享 LangGraph 检查点或外部业务系统集成。代码中未体现租户模型、分布式 checkpoint、消息队列或业务系统适配器。
- 不存在 MCP 工具服务器、API Gateway 或厂商模型 SDK 接入；工具注册是本地 `StructuredTool`，模型出口是项目自己的 `httpx` 客户端。来源：`backend/app/agent/tools.py:build_tools`；`backend/app/llm/client.py`。

## 2. 系统总体架构

### 2.1 分层架构

总体关系见 [system-architecture.mmd](archify/system-architecture.mmd)。代码对应的分层如下：

| 层 | 主要模块 | 职责 | 外部依赖 |
|---|---|---|---|
| 前端接入层 | `frontend/src/main.ts`、`frontend/src/router/index.ts`、`frontend/src/views` | 登录、配置、论文输入、章节确认、评分展示、问询、评测和大屏 | Browser、Vite/Nginx |
| HTTP/API 层 | `backend/app/api/app.py`、`backend/app/api/*.py` | FastAPI 应用装配、CORS、认证依赖、路由、健康检查、指标输出 | FastAPI、SQLAlchemy、MySQL、Chroma |
| 评审编排层 | `backend/app/graph/review_graph.py`、`backend/app/agent/runner.py` | 状态图、人工中断、专项 Agent 顺序、主评审和核验 | LangGraph、LangChain |
| Agent 工具层 | `backend/app/agent/tools.py`、`specialists.py`、`verifier.py` | 工具白名单、schema、证据规则、结果提交、降档核验 | Pydantic、LangChain tools |
| 检索层 | `backend/app/retrieve/parent_child.py`、`three_route.py`、`rerank.py` | 父子块、向量召回、MySQL 回退、三路合并、可选 rerank | Chroma、MySQL、Embedding/Rerank HTTP 服务 |
| 规则与报告层 | `backend/app/review`、`backend/app/scoring`、`backend/app/report` | 一致性发现、引用校验、加权合计、修改清单、评测、存档 | MySQL |
| LLM 调用层 | `backend/app/llm/client.py`、`backend/app/agent/chat_model.py` | Chat、tool calling、embedding、rerank 的 OpenAI-compatible HTTP 适配 | `httpx`、外部模型服务 |
| 持久化与观测层 | `backend/app/importing/db.py`、各模块 models、`observability`、`agent/trace.py` | MySQL 表、Chroma 本地目录、JSON 日志、Prometheus 文本指标、Agent 轨迹 | MySQL 8.4、文件卷 |

### 2.2 数据与依赖关系

- MySQL 保存赛题目录、约束、量规、评审、评审会话、父块全文、问询消息、产物和 Agent 轨迹。ORM 定义分布在 `backend/app/importing/models.py`、`report/models.py`、`retrieve/models.py`、`chat/models.py`、`agent/trace.py`。
- Chroma 保存论文/量规/扣分点等 child 文本、向量和元数据；父块全文不进入 Chroma，而从 MySQL 回取。来源：`backend/app/retrieve/parent_child.py:build_children`、`search_children_then_parents`。
- 业务模型服务、Embedding 服务和 Rerank 服务只通过 `backend/app/llm/client.py` 的 HTTP 请求访问；代码未引入厂商 SDK。
- Compose 提供 `frontend`、`backend`、`mysql` 三个服务以及 `mysql_data/chroma_data/app_logs/uploads` 卷。来源：`compose.yaml`。

### 2.3 关键取舍

| 取舍 | 为什么这样做 | 替代方案 | 当前状态 |
|---|---|---|---|
| LangGraph 状态图 | 需要在章节确认处暂停并从同一 `thread_id` 恢复 | 普通函数串联、工作流编排平台 | 已实现；`InMemorySaver` 只在进程内，快照由 MySQL 辅助恢复 |
| Chroma + MySQL 父子块 | 向量召回需要短 child，逐字引用需要完整父块 | 只存向量片段、直接使用 MySQL LIKE、外部向量数据库 | 已实现；无向量时使用 MySQL 父块回退 |
| 本地函数工具而非 MCP | 当前工具只服务本应用的固定 Agent 白名单，调用和审计都在同一进程/数据库内 | MCP Server、远程工具网关、统一 API Gateway | 已实现本地注册；代码没有规模阈值或正式 ADR，不能声称“已证明规模未到” |
| 环境变量驱动模型 | 兼容不同 OpenAI-style 服务，不把 provider 写死 | 厂商 SDK、模型路由网关、每个角色独立模型 | 已实现；实际 provider/model 值由运行时配置决定 |
| 显式建表而非启动迁移 | 依赖清单没有 Alembic，避免应用启动隐式改库 | Alembic/Flyway、启动时自动迁移 | 已实现；部署时需显式执行各 `create_*_schema` |

## 3. 核心流程详解

### 3.1 请求入口与路由

#### 3.1.1 创建评审

| 步骤 | 输入 | 输出 | 失败点 |
|---|---|---|---|
| HTTP 认证 | Bearer token、`paper_text` 或 `sample_id`、可选 `contest_id` | 当前用户和请求体 | 缺 token/无效 token 401；权限不足 403 |
| 量规门禁 | `contest_id` | 已发布 rubric、dimensions、constraints | 赛题不存在、无已发布量规或无维度 422 |
| 解析 | Markdown 文本 | `sections[]`，含标题、类型、层级、正文 | 空文本、非法 sample id、上传格式/大小错误 |
| 状态图创建 | `paper_text`、`review_id` | `ReviewState` 检查点，状态 `待确认` | 图创建异常；会话快照写库失败 |
| 响应 | `review_id`、章节树、状态 | 前端进入确认页 | 评分字段此时不返回 |

来源：`backend/app/api/routes.py:create_review_endpoint`、`_resolve_paper_text`、`_load_evaluable_inputs`；`backend/app/graph/review_graph.py:_parse_sections`、`create_review`。

#### 3.1.2 确认并继续

1. `POST /api/reviews/{review_id}/resume` 读取 `ReviewSession`；如果当前进程没有检查点，`_restore_snapshot` 把快照写回 `parse` 节点，确保下一节点仍是 `confirm`。
2. 提交确认后的章节树；模型配置齐全时 `_prepare_review_index` 建父块、child 和向量索引，随后装配 Agent runner；不满足模型配置时走确定性结构回退。
3. 状态图执行 retrieve/score；完成后运行一致性检查、修改清单构建和 MySQL 存档。

来源：`backend/app/api/routes.py:resume_review_endpoint`、`_restore_snapshot`、`_prepare_review_index`；`backend/app/graph/review_graph.py:resume_review`。

#### 3.1.3 其他入口

- `/api/uploads`：只接受 `.md/.docx`，保存原文件并创建同样的待确认评审。来源：`backend/app/api/routes.py:upload_markdown_endpoint`。
- `/api/chat/*`：会话、消息、记录级检索问询、聚合和教研摘要。来源：`backend/app/api/chat_routes.py`。
- `/api/eval/*`：样例、汇总指标、单篇 gold 对照；默认 deterministic，`force=model` 才调用模型。来源：`backend/app/api/routes.py:eval_summary`、`backend/app/report/evaluation.py:run_eval`。
- `/api/contests/*`、`/api/imports`：赛题包导入、发布、归档和量规版本管理。来源：`backend/app/api/routes.py` 导入/量规路由段；`backend/app/importing/catalog.py`。

### 3.2 RAG 检索链路

> 用户要求中的“**双路召回**”与当前代码不一致。当前实现是三路召回：`band_text`、`paper_child`、`pitfall`。同时，query rewrite 只在第一轮无结果时触发；Prompt 拼装在 Agent/LLM 层，不在 `retrieve` 模块内完成。以下按真实代码描述。

#### 3.2.1 索引准备

1. **输入**：确认后的章节、`review_id`、`contest_id`、`rubric_id`、维度和章节类型。
2. **父块写入**：每个非空章节变成 `ParentBlock`，全文写入 MySQL `paper_parent`。
3. **切 child**：默认 `max_chars=200`；表格独立成块，普通段落按空行和长度合并；每个 child 记录字符偏移。
4. **向量化**：若 `EMBEDDING_BASE_URL` 和 `EMBEDDING_MODEL` 都存在，批量调用 `llm_client.embed`，向量写入 Chroma；否则关闭向量路径。
5. **Rerank 配置**：若 `RERANK_BASE_URL/RERANK_API_KEY/RERANK_MODEL` 完整，构造可选 reranker。

输入输出与失败点：

| 环节 | 输入 | 输出 | 失败/回退 |
|---|---|---|---|
| 父块保存 | 确认章节 | MySQL `paper_parent` 行 | 数据库异常会阻断索引准备 |
| Embedding | child 文本 | 向量数组 | 请求失败时不建向量索引，后续改用 MySQL 回退 |
| Chroma 写入 | child + vector + metadata | collection 文档 | Chroma 异常会进入接口异常路径；`/readyz` 会标记 not ready |
| Rerank 初始化 | 候选父块文本、rerank 配置 | reranker | 未配置时不重排；服务失败由调用路径抛错/记录日志 |

来源：`backend/app/api/routes.py:_prepare_review_index`；`backend/app/retrieve/parent_child.py:split_into_chunks/build_children/get_collection`；`backend/app/retrieve/models.py:PaperParent`。

#### 3.2.2 查询、召回、去重与排序

1. **查询输入**：Agent 的 `search_evidence` 提供 `dimension_code/query/section_types`；API 装配层将维度名称、维度代码和章节类型拼成 query。来源：`backend/app/agent/tools.py:search_evidence`；`backend/app/api/routes.py:_prepare_review_index.retriever`。
2. **第一轮三路召回**：每路按 `contest_id/rubric_id/review_id/section_types/doc_type` 过滤，单路最多 6 个父块；向量路径先取 child 候选，默认候选因子 3。
3. **查询改写**：只有第一轮三路合并为空时，`default_rewrite` 加入维度和轮次，执行第二轮；第二轮仍为空返回 `证据不足`，最多两轮。
4. **去重**：三路结果按 `parent_id` 合并，同一父块的 `chunk_ids` 合并保留首次顺序。
5. **Rerank**：若配置 reranker，对合并候选做一次排序；校验排序结果只能是原候选集合的重排，不能新增候选。
6. **Top-K**：默认最终保留最多 4 个父块；`search_evidence` 将父块摘要返回给 Agent，`read_parent` 再读取白名单父块最多 4000 字符。

失败点：

- 无 query embedding：进入 MySQL `mysql_search_round`，仍按 `review_id` 和章节类型返回父块。
- 召回为空：第二轮后返回 `证据不足`，不会让模型自行把“未检索到”改写成有引用结论。
- rerank 返回了候选集合之外的 id：`validate_rerank_order` 拒绝该结果。
- 引用不是父块连续子串：工具返回 `quote_not_substring`，不能提交有效维度结果。

来源：`backend/app/retrieve/three_route.py:retrieve_dimension/default_search_round/merge_candidates`；`backend/app/retrieve/parent_child.py:search_children_then_parents`；`backend/app/agent/tools.py:search_evidence/read_parent`。

#### 3.2.3 Prompt 拼装与生成

- 主评审 system prompt 由 `build_system_prompt` 构造，规定工具顺序、四档枚举、连续引用、预算和“每维必须提交”。来源：`backend/app/agent/prompt.py:build_system_prompt`。
- `build_review_agent` 使用 `DeepSeekChatModel` 适配器；适配器把 LangChain 消息和工具 schema 转成项目 `chat_with_tools` 的 OpenAI-compatible 请求。类名不代表实际 provider。来源：`backend/app/agent/graph.py:build_review_agent`；`backend/app/agent/chat_model.py:DeepSeekChatModel`。
- 当前代码没有一个名为 `build_prompt` 的独立 RAG 拼接函数；上下文由工具结果、预加载的专项结果和 Agent 消息历史共同组成。代码中未体现独立 Prompt 模板版本管理或 token 预算裁剪器。
- 生成输出先通过工具 schema 和业务函数校验，再由 `submit_dimension` 写入 `ToolContext.results`，最后由 `weighted_sum` 做确定性加权。来源：`backend/app/agent/tools.py:submit_dimension`；`backend/app/scoring/aggregate.py:weighted_sum`。

### 3.3 Agent 工具调用链路

真实链路如下：

```text
LLM tool call
  -> LangChain/Pydantic schema
  -> call_tool 参数与白名单校验
  -> 工具业务规则与证据连续子串校验
  -> 路由层身份/权限（工具本身不重新做用户权限）
  -> 风险/降档规则（mention guard + verifier）
  -> 人工确认已在工具调用前完成
  -> 局部重复提交保护
  -> 结果写入 ToolContext/ReviewState
  -> AgentStep + JSON 日志 + metrics
  -> runner 回填报告与数据库
```

各阶段事实：

| 阶段 | 当前实现 | 失败结果 |
|---|---|---|
| Schema 校验 | `StructuredTool` 使用 Pydantic 参数模型；如 `band/status/kind/severity` 使用 Literal/枚举 | LangChain 参数解析失败或 `param_invalid` |
| 白名单 | `build_tools(ctx, tool_names=...)` 按角色选择工具；`call_tool` 再检查工具名 | 未知工具 `param_invalid` |
| 业务规则 | 维度存在、章节索引、父块白名单、quote 连续子串、数量和长度上限 | `not_found/not_allowed/quote_not_substring/param_invalid` |
| 权限 | HTTP 依赖 `current_user/require_permission`；工具函数接收的是已装配上下文 | 401/403；代码中未体现独立工具级用户 ACL |
| 风险判断 | `apply_mention_guard` 可根据约束降档；verifier 只允许保留、降一级或证据不足 | 降档、证据不足或 reject；不允许升档 |
| 人工确认 | 状态图 `confirm` 节点 `interrupt()`，早于 retrieve/score | 未确认不能进入评分 |
| 幂等 | `submit_dimension` 拒绝同一维覆盖；AgentStep `(review_id,idx)` 唯一并冲突重试 | 重复提交返回 `not_allowed`；没有全局幂等键 |
| 结果核验 | 引用校验、mention guard、确定性加权、verifier | 引用失败不进入有效加权；verifier 只向下改 |
| 审计 | `AgentStep` 记录 action、参数摘要、结果、错误码和耗时；JSON 日志记录生命周期和审计事件 | 记录失败不会把评审结果转为失败，具体见 `verifier._record` |
| 回填 | `ctx.results` → `ReviewState.dimension_results` → `ReviewDimension`/`Review`/change list | 保存异常由 API 错误路径处理 |

来源：`backend/app/agent/tools.py`；`backend/app/agent/middleware.py`；`backend/app/agent/verifier.py`；`backend/app/api/routes.py:resume_review_endpoint`；`backend/app/agent/trace.py`。

### 3.4 Agent 循环控制

#### 主评审 Agent

| 控制项 | 值 | 来源 |
|---|---:|---|
| model calls | 12 | `backend/app/agent/middleware.py:BudgetMiddleware` |
| tool calls | 24 | 同上 |
| 每维工具步数 | 3 | 同上 |
| 墙钟 | 150 秒 | 同上 |
| LangGraph recursion limit | 45 | `backend/app/agent/runner.py:make_agent_runner` |
| 无进展阈值 | 连续 2 次 search/submit 没有新增父块或维度提交 | `BudgetMiddleware:_update_progress` |
| 强制补交 | 缺失维度最多 2 轮 | `backend/app/agent/runner.py:_force_submit` |

#### 专项 Agent 与 verifier

- evidence：6 model calls、24 tool calls、每维 4 步、90 秒、recursion limit 28。
- topic fit：3 model calls、12 tool calls、每维 3 步、45 秒、recursion limit 16。
- coherence：4 model calls、16 tool calls、每维 3 步、60 秒、recursion limit 20。
- verifier：一次受约束的 `chat_with_tools` 调用，最多应用 5 个降档/证据不足动作；代码没有独立 token 上限。

来源：`backend/app/agent/specialists.py`；`backend/app/agent/verifier.py:verify_results`。

#### 停止条件

1. 所有量规维度已经提交：`all_submitted`。
2. 预算耗尽：`budget_exhausted`。
3. 连续无进展：`no_progress`。
4. LangGraph 递归上限：`recursion_limit_reached`。
5. 专项 Agent 失败不会阻断主评审；结果中保留专项状态和错误。来源：`backend/app/agent/specialists.py:_run_specialist`、`backend/app/agent/runner.py:make_agent_runner`。

代码中没有 token 数预算、模型输出 token 上限或按 token 计费的停止条件；只有调用次数、工具次数、步骤、墙钟和递归上限。

### 3.5 记忆分层

| 层级 | 当前实现 | 写入策略 | 过期/删除 |
|---|---|---|---|
| 工作记忆 | `ReviewState`、`ToolContext`、Agent message state、检索缓存、证据包和临时结果 | 一次评审运行中由状态图和工具函数写入 | `InMemorySaver` 随进程退出丢失；代码中未体现独立 TTL 或手动清理入口 |
| 评审会话记忆 | MySQL `review_session` | 创建/恢复/确认时写入论文全文、章节 JSON、状态、赛题和用户归属 | 用于重启恢复；没有 review 删除 API 或自动过期策略，代码中未体现 |
| 评审长期记录 | `review`、`review_dimension`、`paper_parent`、`agent_step` | 评审完成后保存结果、引用、父块和轨迹 | 作为业务存档/记录级问询来源；没有自动过期/删除策略，代码中未体现 |
| Chat 会话记忆 | `chat_session`、`chat_message` | 每轮用户和助手消息写库，按 `created_at/seq` 全量读取 | 有问询会话删除路由；消息通过外键级联删除。来源：`backend/app/api/chat_routes.py`、`backend/app/chat/models.py` |
| 长期语义记忆 | 没有 Agent 专用长期记忆 | 评审记录会被索引为 `review_record` 供问询检索，但这属于业务知识归档 | 代码中未体现语义记忆合并、摘要写回、Redis 或向量化对话历史 |

## 4. 技术选型与原因

### 4.1 RAG 组件

- **Chroma**：本地持久化、依赖少、适合当前单实例部署；代码显式固定 cosine，并把过滤元数据写入 child。替代方案是 Milvus/pgvector/远程向量服务，适合更大规模或多副本，但当前代码没有相应适配。来源：`backend/app/retrieve/parent_child.py:get_collection`、`compose.yaml`。
- **MySQL 父块存储**：引用校验需要完整父块和字符范围；同时复用已有业务数据库。替代方案是把全文也放向量库或对象存储，当前未实现。来源：`backend/app/retrieve/models.py:PaperParent`。
- **Embedding HTTP**：模型配置可替换，缺少 embedding 时仍能用 MySQL 回退。替代方案是本地 embedding SDK 或厂商 SDK，项目依赖中未引入。来源：`backend/app/llm/client.py:embed`；`backend/requirements.txt`。
- **可选 Rerank**：只改变召回候选顺序，不扩大候选集合，以保持过滤边界和引用可追溯。替代方案是把 rerank 作为必需层，当前没有这样做。来源：`backend/app/retrieve/three_route.py`、`parent_child.py:search_children_then_parents`。

### 4.2 Agent 框架

- **LangGraph** 用于可暂停、可恢复的状态图和递归上限；人工确认不是普通布尔标志，而是 `interrupt()`。替代方案是手写状态机或任务队列，当前没有采用。来源：`backend/app/graph/review_graph.py`。
- **LangChain `create_agent`** 用于标准化 tool calling、middleware 和 Agent state；项目通过 `DeepSeekChatModel` 适配自己的 HTTP 客户端。替代方案是直接循环 `chat_with_tools`，但现有代码选择了 LangChain Agent 层。来源：`backend/app/agent/graph.py`、`chat_model.py`。
- **Pydantic + StructuredTool** 用于生成工具 schema并做参数边界校验；业务规则仍在本地函数中再次校验，避免只依赖模型遵守 description。来源：`backend/app/agent/tools.py`。

### 4.3 模型选型

- 具体模型不写死，`LLM_MODEL/EMBEDDING_MODEL/RERANK_MODEL` 由部署配置注入；因此代码只能确认协议和用途，不能确认实际供应商或模型版本。
- `DeepSeekChatModel` 是适配器类名，`_llm_type` 为 `deepseek-compatible`；不能把它当作运行时 provider 证明。来源：`backend/app/agent/chat_model.py`。
- 主评审、专项 Agent、verifier 当前共用传入的 `chat_with_tools` 入口；代码没有角色级独立模型配置。来源：`backend/app/api/routes.py:resume_review_endpoint`、`backend/app/agent/specialists.py`。

## 5. 评测方案

### 5.1 当前已实现评测

- 评测集是项目自建的 12 篇论文，每篇 gold 有 5 个维度，共 60 个维度项。来源：`data/samples/eval/README.md`；`backend/app/report/evaluation.py`。
- 当前实现的生成/判定指标是：档位一致率、引用精确匹配率、证据不足命中情况。默认 `deterministic`，只有 `GET /api/eval/summary?force=model` 才运行模型路径。来源：`backend/app/report/evaluation.py:summarize_eval/run_eval`；`backend/app/api/routes.py:eval_summary`。
- `scripts/check_eval_gold.py` 校验 gold 数据结构；`scripts/run_real_pipeline.py` 记录真实论文链路中的 quote 子串、耗时、Agent 轨迹和终止原因。

### 5.2 检索指标与生成指标应分开

以下是评测扩展方案，**当前代码中未实现 Hit Rate、MRR 和 RAGAS**，不能把它们当作已有报告字段。

#### 检索层

对每个维度保存 gold evidence parent/chunk id 或可接受 evidence set：

- `Hit Rate@K = 命中至少一个 gold evidence 的 query 数 / query 总数`。
- `MRR@K = 平均(1 / 第一个 gold evidence 的排名)`，未命中记 0。
- 评测输入应记录 query、contest/rubric/review 过滤条件、gold parent/chunk、实际候选序列、rerank 后序列和最终 Top-K。

建议将 `retrieve_dimension` 的 `route_hits/queries/after_rerank/kept` 作为评测观测字段；这是对现有返回和日志的扩展，不需要改变引用规则。来源：`backend/app/retrieve/three_route.py:DimensionRetrieval`、`retrieve_dimension`。

#### 生成层

- **忠实度（faithfulness）**：回答中的每个可验证断言必须能由引用父块支持；可复用现有连续子串校验和人工证据表。
- **相关性（answer relevance）**：回答是否直接回答问题，不把无关评审记录带入；可用人工 1–5 分和 RAGAS 的 `answer_relevancy`。
- **上下文相关性（context relevance）**：检索到的父块是否有助于回答；可用 RAGAS 的 `context_relevancy/context_precision`，具体 metric 版本需随 RAGAS 版本确定。
- **引用完整性**：回答中被引用的记录是否全部在检索结果中，未引用的有效证据比例是多少；现有 `backend/app/chat/answering.py` 已有双向引用校验逻辑，可作为确定性前置检查。

RAGAS 依赖和执行脚本不在当前 `backend/requirements.txt` 中；若采用，应作为独立评测环境依赖，不能混入生产运行时。人工抽检建议覆盖：高/中/低相似度、命中/不命中、rerank 开/关、模型/确定性回退、不同赛题隔离。

### 5.3 归因方法

每个样本应至少保留以下 trace：

1. query 原文和 query rewrite 轮次；
2. 三路各自候选、过滤条件和命中数；
3. 去重后的 parent 顺序、rerank 顺序、最终 Top-K；
4. Prompt 中实际注入的证据片段；
5. 模型输出、工具错误、quote 校验、mention guard、verifier 动作；
6. 最终回答/档位与 gold 的差异。

由此按“召回失败 → 排序失败 → 上下文截断/污染 → 生成不忠实 → 规则降档/核验改写”分桶归因。当前 `AgentStep` 和 retrieve 日志已经覆盖部分链路，但 Prompt 原文、Hit Rate/MRR、RAGAS 字段未落库，属于后续评测增强。来源：`backend/app/agent/trace.py`；`backend/app/retrieve/three_route.py`；`backend/app/observability/logging.py`。

## 6. 工程化考虑

### 6.1 权限与数据隔离

- Bearer token 解码后查 MySQL 用户，用户必须 active；路由用 `require_user/require_permission` 做 401/403 分层。来源：`backend/app/auth/deps.py`。
- `review_id`、`session_id` 等私有资源按用户归属检查；工具上下文按 `review_id/contest_id/rubric_id` 过滤。来源：`backend/app/api/routes.py`；`backend/app/api/chat_routes.py`；`backend/app/retrieve/parent_child.py:_where`。
- 代码没有租户 ID、跨组织数据域或外部策略引擎；需要多租户时不能只增加一个前端字段，必须扩展所有持久化表和查询过滤。

### 6.2 幂等与重试

当前可重试：

- LLM HTTP 网络层：`_MAX_ATTEMPTS=2`，即首次请求加一次网络重试；超时为 30 秒。来源：`backend/app/llm/client.py:_TIMEOUT_SECONDS/_MAX_ATTEMPTS`。
- 没有向量结果时的检索第二轮 query rewrite；不是无限重试。来源：`backend/app/retrieve/three_route.py:MAX_ROUNDS`。
- AgentStep 插入遇到唯一索引冲突时重试一次。来源：`backend/app/agent/trace.py:append_step`。

不可盲目重试：

- 参数、枚举、权限、quote 连续子串错误：重试相同输入不会改变结果，应返回错误或让 Agent 修正参数。
- 重复维度提交：工具明确拒绝覆盖；重试相同提交不是幂等成功。
- verifier 的 `reject/missing_decision`：需要新的决策输入，代码不会自动重复模型调用。
- 数据库/Chroma 持久化失败：是否重试取决于上层请求生命周期，代码中没有统一事务重试中间件。

### 6.3 审计与合规边界

- JSON 日志按模块和日期轮转，默认保留 30 天；敏感字段、API key、DSN 和密码被过滤。来源：`backend/app/observability/logging.py`。
- `AgentStep` 保存 action、参数 digest、结果摘要、错误码和耗时，不保存原始工具参数。来源：`backend/app/agent/trace.py`、`middleware.py:TraceMiddleware`。
- 指标是进程内累积，重启归零；没有 Prometheus remote write、集中日志或跨副本聚合。来源：`backend/app/observability/metrics.py`。

### 6.4 成本与延迟

- 代码控制模型调用次数、工具次数、每维步数、墙钟和递归深度；HTTP 单次 timeout 30 秒，网络层最多两次尝试。
- 专项 Agent 会增加模型与工具调用；rerank 和 embedding 是独立可选成本。
- 代码记录 LLM latency 和 Agent elapsed time，但没有 token 用量、美元成本、每租户预算或模型价格表。成本估算需要从模型服务响应补充 usage，再按配置单价计算。
- 当前单实例架构未引入网关/MCP/队列。可确认的原因是工具、状态和审计都在本地应用内闭环；代码没有写明规模阈值，因此规模达到多副本、跨团队复用或外部工具治理要求时，应重新评估 Gateway/MCP/队列。

## 7. 部署与运行说明

### 7.1 环境变量

`.env.example` 是唯一键名模板，实际值写入项目根 `.env`：

| 变量 | 用途 | 必需性 |
|---|---|---|
| `MYSQL_ROOT_PASSWORD/MYSQL_DATABASE/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DSN` | MySQL 连接与 Compose 初始化 | 首次配置必需 |
| `AUTH_SECRET` | token 签名，至少 32 字符 | 首次配置必需 |
| `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` | Chat/Tool calling | 模型路径必需 |
| `EMBEDDING_BASE_URL/EMBEDDING_API_KEY/EMBEDDING_MODEL` | Embedding | `EMBEDDING_MODEL` 是模型路径门禁；独立 URL/key 可回落 |
| `RERANK_BASE_URL/RERANK_API_KEY/RERANK_MODEL` | Rerank | 可选 |
| `CORS_ALLOW_ORIGINS` | CORS 白名单 | 默认 5173 两个回环源；禁止 `*` |
| `LOG_DIR/LOG_LEVEL/LOG_RETAIN_DAYS/LOG_DISABLED` | 日志位置、级别、保留期、关闭开关 | 可选 |

来源：`.env.example`；`backend/app/settings/config.py`；`backend/app/api/app.py:model_available/cors_origins`；`backend/app/observability/logging.py`。

### 7.2 本地启动

```powershell
# 1. 准备配置
Copy-Item .env.example .env

# 2. 启动 MySQL 8.4，并在 .env 中填写 MYSQL_DSN 等配置

# 3. 使用共享 Python 3.11 环境安装依赖
$py = 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe'
& $py -m pip install -r backend/requirements.txt

# 4. 显式幂等建表（应用启动不会自动建表）
& $py -c "from backend.app.importing.db import create_schema; from backend.app.report.models import create_report_schema; from backend.app.report.artifact_models import create_artifact_schema; from backend.app.retrieve.models import create_parent_schema; from backend.app.agent.trace import create_agent_trace_schema; from backend.app.auth.models import create_auth_schema; from backend.app.chat.models import create_chat_schema; [f() for f in (create_schema, create_report_schema, create_artifact_schema, create_parent_schema, create_agent_trace_schema, create_auth_schema, create_chat_schema)]"

# 5. 启动后端
& $py -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077

# 6. 另开终端启动前端
Set-Location frontend
npm ci
npm run dev
```

前端访问 `http://127.0.0.1:5173`；后端健康检查为 `http://127.0.0.1:8077/health`，就绪检查为 `/readyz`，指标为 `/metrics`。赛题需先通过 `/api/imports` 导入数据包并发布量规。来源：`README.md` 本地启动章节；`frontend/vite.config.ts`；`backend/app/api/app.py`。

### 7.3 Compose 启动

```powershell
Copy-Item .env.example .env
docker compose up -d --build frontend backend mysql
```

Compose 只提供服务和卷，不自动完成业务建表、赛题导入和量规发布；这些仍需按部署手册显式执行。镜像构建/启动是否在当前机器成功，代码中未确认。来源：`compose.yaml`；`README.md`；`docs/腾讯云Docker-Compose运维手册.md`。

## 8. 已知局限与后续演进

### 8.1 当前局限

1. **向量检索不是混合检索**：当前是 Chroma 向量路径或 MySQL 回退，代码没有 BM25+向量同轮融合；三路是按 `doc_type` 分路，不是“双路”。
2. **Prompt 观测不完整**：工具结果和 Agent 轨迹可查，但 Prompt 原文、token usage 和上下文截断原因没有单独存档。
3. **Agent token 预算缺失**：只有调用/工具/步数/墙钟限制，无法按 token 或费用做租户级配额。
4. **检查点只在进程内**：MySQL 快照可以恢复确认前状态，但不等价于分布式 LangGraph checkpoint；当前不适合多副本并行写同一评审。
5. **长期记忆缺失**：评审记录索引服务于记录问询，不是跨会话 Agent 记忆；无摘要合并和语义记忆生命周期。
6. **评测集较小**：当前 gold 评测是 12 篇/60 维度项，且是项目自建数据；没有现成 Hit Rate/MRR/RAGAS 结果。
7. **容器未由静态代码证明已验收**：Compose、Dockerfile 和 Nginx 配置存在，但构建/部署状态需要现场验证。

### 8.2 演进顺序

1. 先补检索 trace 和 gold evidence，建立 Hit Rate@K/MRR，再分别补生成忠实度/相关性和人工抽检；避免只看最终档位而无法判断是召回还是生成问题。
2. 再补 token usage、价格表和每次 Agent 的预算账本，在现有 `AgentStep`/metrics 旁增加成本字段。
3. 多副本前先把 `InMemorySaver` 换成持久化、可并发的 checkpoint，并为评审会话增加版本/乐观锁。
4. 只有在需要跨应用复用工具、第三方工具权限治理、跨团队审计或独立扩缩容时，再引入 MCP 或工具网关；当前本地工具闭环更容易保持 quote 校验、权限和审计的一致性。
5. 需要长期记忆时，先定义可删除、可过期和用户隔离的数据模型，再决定是否引入 Redis/向量记忆；不能直接把所有 Chat 历史长期喂给 Agent。

## 9. 目录结构说明

```text
paper-review/
├─ backend/
│  ├─ app/api/            FastAPI 入口、评审/问询/鉴权/设置/大屏路由
│  ├─ app/agent/          Agent、工具、专项角色、verifier、预算、轨迹
│  ├─ app/graph/          LangGraph 评审状态图
│  ├─ app/retrieve/       父子块、Chroma、三路召回、rerank
│  ├─ app/llm/            Chat/Embedding/Rerank HTTP 客户端
│  ├─ app/scoring/        JSON 选档、引用守卫、加权合计
│  ├─ app/review/         数字、引用、范围、题目约束一致性检查
│  ├─ app/report/         存档、量规、评测、修改清单、大屏、产物
│  ├─ app/importing/      赛题包导入与 MySQL 数据层
│  ├─ app/chat/           记录级问询、会话、检索、回答、聚合
│  ├─ app/auth/           用户、权限、token、鉴权
│  └─ requirements.txt    后端运行依赖
├─ frontend/
│  ├─ src/                Vue 页面、组件、路由、API 类型
│  ├─ tests/              Vitest 单测与 Playwright E2E
│  └─ package.json        前端依赖与脚本
├─ data/
│  ├─ contests/           赛题 JSON 数据包
│  └─ samples/            演示稿、真实论文 Markdown、gold 评测集
├─ docs/
│  ├─ version/Final_version/PROJECT_DOC.md  本文
│  ├─ version/Final_version/archify/        当前版本架构图源文件
│  ├─ 项目事实清单.md                       代码事实基线
│  └─ plan、acceptance、version、design/    计划、验收、版本和设计文档
├─ scripts/               OCR、索引回填、评测核验、门禁和回归脚本
├─ compose.yaml           frontend/backend/mysql 容器编排
├─ .env.example           配置键名模板
└─ README.md              快速入口与文档索引
```
