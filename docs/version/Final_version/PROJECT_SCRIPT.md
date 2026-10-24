# paper-review 项目逐字稿

> 用途：面试时直接口述。数字和边界以 `PROJECT_DOC.md`、`INTERVIEW_QA.md` 以及当前代码为准。涉及当前未实现的能力，稿子会直接说“目前没有”，避免把规划讲成现状。

## 30 秒版：电梯陈述（预计 30 秒）

“我做的是一个竞赛论文预审系统，项目叫 paper-review。它不是普通的问答 Chat，核心是一个 LangGraph 驱动的 Agent 工作流：用户提交论文后，系统先解析章节，经过人工确认，再按赛题量规逐维检索证据、调用工具做评审，最后经过引用校验和 verifier，输出分档结果以及可追溯的修改清单。

架构上，FastAPI 负责鉴权和路由，Agent 负责编排，RAG 用 Chroma 保存 child 向量、MySQL 保存完整 parent，模型通过 OpenAI-compatible HTTP 调用。这里我会特别说明一个边界：当前是三类文档路由，以及向量路径或 MySQL 回退，还不是同轮 BM25 加向量的混合检索。”

**主动抛出的钩子**

- “如果您关心证据可信度，我可以展开 parent/child、连续子串引用和 quote 校验。”
- “如果您关心 Agent 工程化，我可以展开工具白名单、幂等、审计和循环预算。”

## 2 分钟版：完整项目介绍（预计 2 分钟）

“这个项目解决的是竞赛论文预审问题。用户上传论文，选择已发布的赛题量规，系统按每个维度找证据、选档、做一致性检查，并生成修改清单。系统有一个很硬的规则：有证据的结论必须附论文正文中的连续原句；证据不足不能换算成分数。它还明确不输出奖项、名次和获奖概率。

我把它定位成 Agent 工作流，而不是增强型 Chat。主入口是创建评审和恢复评审两个接口。请求先经过 FastAPI 的认证、资源归属和量规门禁，然后进入 LangGraph 的 `parse → confirm → retrieve → score`。章节确认是一个真正的人工中断，确认前不会进入评分。评分阶段会运行 evidence、topic fit、coherence、主评审和 verifier 这些角色。`/api/chat/*` 是另一条记录级问询路径，它检索已经保存的评审记录，不承担主评审状态机。

**此处可指图：system-architecture.png**。图里从左到右看，用户先到 FastAPI，再到 Review graph 和 Agent 编排；右上是 RAG 和 LLM，右下是工具、记忆和 MySQL/Chroma 等外部或持久依赖。框架提供 LangGraph 的状态图、人工中断、递归限制和 tool calling 接口；项目自己补的是工具白名单、Pydantic schema、quote 连续子串校验、mention guard、verifier、幂等保护和 AgentStep 审计。

RAG 这边，确认章节先写成 MySQL 的 parent，再按默认 200 字符切成 child，表格单独成块。查询会走 `band_text`、`paper_child`、`pitfall` 三类 route，每路最多保留 6 个 parent，合并后按 parent 去重，可选 rerank，最后最多保留 4 个 parent；如果没有 embedding 或向量路径不可用，就回退到 MySQL。当前不是同轮向量加 BM25，query rewrite 只在第一轮没有结果时触发，最多两轮。

Agent 工具调用也不是模型返回 JSON 就直接执行。请求要先过 schema、工具白名单、业务规则、资源权限和 quote 校验，再写入上下文；模型或网络错误要区分可重试和不可盲重试。主评审最多 12 次模型调用、24 次工具调用、每维 3 步、150 秒，递归上限是 45。当前有调用次数和墙钟限制，但没有 token budget。

记忆上，我会分三层讲：`ReviewState` 和 `ToolContext` 是当前运行的工作记忆；`review_session`、评审结果和 Chat 消息是 MySQL 会话/业务记忆；`AgentStep` 是审计轨迹。代码里没有滚动摘要和独立的长期 Agent Memory。

评测上，当前是 12 篇论文、60 个维度项，主要看档位一致、引用精确匹配和证据不足命中。Hit Rate、MRR 和 RAGAS 还没有实现，下一步会把检索和生成分开评估，再按切片、召回、知识库缺失和生成问题做归因。”

**主动抛出的钩子**

- “这里最容易追问的是为什么要 parent/child，以及为什么 quote 必须是连续子串。”
- “如果需要，我可以继续讲当前单体架构为什么暂时没有 MCP、模型网关和多副本 checkpoint。”

## 5 分钟版：深度展开（预计 5 分钟）

### 1. 先讲定位和边界

“我先讲定位。paper-review 是竞赛论文预审工作台，不是开放式论文聊天机器人。它要对照已发布量规，逐维找到证据，选择档位，做一致性检查，最后给修改建议。系统还有几条明确边界：证据引用必须是正文 parent 中的连续原句，证据不足不换算分数，不输出奖项、名次和获奖概率。PDF 和 OCR 不在在线服务里做，只接收 Markdown 和 DOCX。

所以我把它叫 Agent 工作流。因为它有状态、有人工中断、有工具调用、有停止条件，也有结果核验。`/api/chat/*` 可以看成旁路的记录级问询 Chat，但它不负责主评审状态机。”

### 2. 配合总体架构图讲分层

“**此处可指图：system-architecture.png**。我通常按五层讲。

第一层是入口和路由。Vue 把请求发到 FastAPI；FastAPI 做 token、用户状态、资源归属、CORS 和量规门禁。第二层是编排。`review_graph.py` 管理 `parse → confirm → retrieve → score`，`runner.py` 再把专项 Agent、主评审和 verifier 串起来。第三层是检索和工具。检索负责 parent/child、Chroma、MySQL fallback、三路合并和 rerank；工具负责检索、读 parent、提交维度以及各种业务校验。第四层是记忆和存储。当前轨迹在 `ReviewState`、`ToolContext`，MySQL 保存 session、结果、消息、parent 和 AgentStep。第五层是模型调用。项目自己的 `httpx` client 访问 OpenAI-compatible Chat、Embedding 和 Rerank 服务。

这里框架能力和自研能力要分开说。LangGraph 给了状态图、interrupt、recursion limit 和恢复接口，LangChain 给了 Agent 和 StructuredTool。项目自己补了权限门禁、工具白名单、quote 连续性、mention guard、verifier、重复提交保护、审计和确定性加权。换句话说，框架负责把循环跑起来，业务代码负责决定什么可以做、什么结果算有效。”

### 3. 配合 RAG 图讲检索链路

“**此处可指图：rag-pipeline.png**。先说一个容易被问到的事实：当前实现不是同轮向量加关键词的混合检索。它有三个文档类型 route：`band_text`、`paper_child` 和 `pitfall`。向量路径不可用时，才回退到 MySQL 父块查询。

索引准备时，确认过的章节先落成 MySQL parent。默认按 200 字符切 child，表格单独成块，child 带 parent id 和偏移。Embedding 配置齐全时，child 向量写入 Chroma；Rerank 配置完整时再启用可选 reranker。

查询从 `search_evidence` 进入。第一轮按 review、contest、rubric、章节类型和 doc type 做过滤。三路结果合并后按 `parent_id` 去重，同一个 parent 的 chunk id 合并。Rerank 只能把原候选重新排序，不能带来新 parent。最后最多保留 4 个 parent，`read_parent` 最多读 4000 字符。第一轮为空才做 query rewrite，第二轮仍为空就返回证据不足。

为什么不纯向量？因为数字、档位编号和术语需要精确过滤，而且最终引用必须回到连续原文。为什么不把 MySQL fallback 直接说成 BM25？因为当前代码只确认了按 review 和 section 过滤父块，没有实现同轮倒排相关性排序。面试时我会把这个边界说清楚。”

### 4. 配合工具调用时序图讲安全链路

“**此处可指图：agent-tool-call-sequence.png**。工具调用不是模型给出合法 JSON 就执行。先是 StructuredTool 和 Pydantic 做 schema 校验，再做工具名白名单、业务规则、资源权限、父块白名单、章节和 quote 校验。人工确认已经在进入 retrieve/score 之前完成。通过后才执行工具，结果写回 `ToolContext` 和 `ReviewState`，同时写 AgentStep、JSON 日志和指标，最后回填报告。

风险控制有两层。一层是 mention guard，处理量规约束和降档；另一层是 verifier，只能保留、降一级、标记证据不足或 reject，不能把结果升级。对于网络类瞬时错误，LLM client 最多两次尝试，单次 timeout 是 30 秒；对于参数、权限、quote、重复提交这类确定性错误，重复同一个输入没有意义，所以不能盲重试。

幂等也要讲清楚：同一维度重复提交不会覆盖已有结果，AgentStep 对 review 和 index 有唯一约束并处理冲突。但代码没有全局的 request idempotency key，所以还不是完整的跨服务幂等方案。”

### 5. 配合循环控制图讲停止条件

“**此处可指图：agent-loop-control.png**。一次循环就是任务开始、规划、调用工具、观察结果，然后判断是否满足停止条件。停止条件不是模型说一句‘完成了’就算，而是检查维度是否都提交、预算是否耗尽、是否超时、是否达到递归上限，以及有没有连续无进展。

当前主评审的限制是 12 次模型调用、24 次工具调用、每个维度 3 步、150 秒墙钟、recursion limit 45。连续两次 search 或 submit 没有新增 parent 或维度提交，会进入无进展处理。缺失维度最多两轮后会强制标成证据不足。专项 Agent 还有各自的 6/24/90 秒、3/12/45 秒和 4/16/60 秒配置。

这里要主动说明限制：当前没有 token budget，也没有按美元成本停止。调用次数、字符上限和墙钟并不等于 token 预算。下一步应该从模型响应 usage 和价格表补上每个 review、role 和 step 的成本账本。”

### 6. 讲记忆分层，不夸大长期记忆

“**此处可指图：memory-layering.png**。第一层是工作记忆，包含 `ReviewState`、`ToolContext`、当前消息、证据包和临时结果，主要服务一次运行；`InMemorySaver` 随进程生命周期存在。第二层是会话和业务记录，`review_session` 保存恢复需要的快照，MySQL 还保存 review、review_dimension、paper_parent 和 Chat 消息。第三层是 AgentStep 和 JSON 日志，它们更像审计和观测记录。

我不会把它说成已经有长期语义记忆。代码没有滚动摘要、对话向量记忆或独立的 Agent Memory 生命周期。Chat 消息有删除入口，但没有一个统一的‘删除全部记忆’接口。未来如果要加长期 Memory，必须先回答谁能写、保存多久、谁能删、如何隔离租户，以及怎样过滤恶意内容。”

### 7. 讲评测和归因

“**此处可指图：eval-and-attribution.png**。当前评测集是 12 篇论文、每篇 5 个维度，共 60 个维度项。现在实现的是档位一致、引用精确匹配和证据不足命中，默认 deterministic，强制 model 才走模型路径。

我会把检索和生成分开评估。检索侧用 Hit Rate@K 和 MRR，看 gold evidence 有没有进入候选集以及排在什么位置。生成侧看忠实度、答案相关性和上下文相关性，RAGAS 可以作为补充，但当前依赖里没有 RAGAS，必须放在独立评测环境。再加人工抽检，覆盖命中/不命中、fallback、rerank 开关、长文和表格场景。

归因时保留 query、rewrite 轮次、三路候选、去重顺序、rerank 顺序、Top-K、实际上下文、工具错误、quote 校验和 verifier 动作。如果 gold 根本不在库里，是知识库缺失；gold 在库但没进 Top-K，是召回或排序；进了上下文但回答不支持，是生成或上下文拼装；quote 不连续，则是证据边界问题。这样才不会只看到最终错分，而找不到责任节点。”

### 8. 讲技术取舍、局限和演进

“技术取舍上，我选择 LangGraph，是因为这里需要人工暂停和恢复；选择 Chroma 加 MySQL parent，是因为向量检索和逐字引用的需求不同；选择本地 StructuredTool，是因为当前工具只服务同一个应用，权限、校验和审计在同一进程闭环；模型则通过环境变量和 OpenAI-compatible HTTP 适配，避免把 provider 写死。

当前局限也很明确：没有同轮混合检索、没有 token budget、没有 Hit Rate/MRR/RAGAS、检查点只在进程内、没有长期 Agent Memory，也没有独立 MCP、API Gateway、队列或多副本状态方案。演进顺序我会先补检索 trace、gold evidence、质量指标和成本账本；多副本之前先解决持久化 checkpoint、版本控制和幂等；只有在跨应用复用工具、第三方治理或独立扩缩容出现时，再评估 MCP 或工具网关。”

**主动抛出的钩子**

- “如果您想听工程化，我可以继续讲一次网络超时、重复 resume 和跨副本部署会怎样处理。”
- “如果您想听评测，我可以现场画出 Hit Rate/MRR 与忠实度/相关性的归因链路。”

## 高频追问速答卡

每题控制在三句话以内，适合面试现场快速回答。

### 1. 这是 Chat 还是 Agent？

核心评审是 Agent 工作流，因为它有状态图、人工中断、工具调用、停止条件和结果核验。`/api/chat/*` 是独立的记录级问询 Chat。两条路径的边界在 `review_graph.py` 和 `chat_routes.py` 中很清楚。

### 2. 你们实现了真正的混合检索吗？

当前没有实现同轮 BM25 加向量融合。实际是三个 `doc_type` route，向量路径不可用时回退到 MySQL 父块查询；如果要做混合检索，需要新增关键词召回、统一候选合并和 Hit Rate/MRR 评测。

### 3. 为什么要 parent/child？

child 适合短文本向量召回，parent 保留完整连续原文。最终 quote 必须从 MySQL parent 中逐字找到，所以不能只保存向量片段。

### 4. 合法 JSON 为什么还不能执行？

JSON 只说明格式可能正确，还要过工具白名单、资源权限、业务规则、父块范围和 quote 连续性校验。重复提交、越权 parent 或不连续 quote 都会被服务端拒绝。

### 5. Agent 怎么防止无限循环？

主评审限制 12 次模型、24 次工具、每维 3 步、150 秒和 recursion limit 45，并检测连续无进展。当前没有 token budget，下一步需要从模型 usage 补充成本和 token hard stop。

### 6. 你们的长期记忆是什么？

当前没有独立的长期 Agent Memory。MySQL 中的评审、Chat 消息和 AgentStep 是业务存档、会话历史和审计记录，不应直接叫跨会话语义记忆。

### 7. 为什么不用 MCP？

当前工具只在同一个应用内使用，本地 StructuredTool 能把权限、quote 校验和审计放在同一边界，复杂度更低。等出现跨应用复用、第三方工具治理或独立扩缩容，再评估 MCP，并重新设计身份传播和幂等。

### 8. 如何判断 RAG 错误来自哪里？

先看 gold 是否在知识库，再看是否进入候选、是否被 rerank 排到前面、是否进入最终上下文，最后看模型是否忠实使用。对应的归因就是知识库缺失、切片/召回、排序、上下文或生成问题。

### 9. 当前模型的具体供应商和版本是什么？

代码只能确认使用 OpenAI-compatible HTTP，实际 `LLM_MODEL`、Embedding 和 Rerank 值由环境变量决定。`DeepSeekChatModel` 是适配器类名，不能单凭类名证明运行时 provider。

### 10. 下一步最值得做什么？

我会先补 retrieval trace、gold evidence、Hit Rate/MRR、忠实度和相关性评测，再补 token/cost 账本。多副本之前解决持久化 checkpoint、会话版本和幂等；MCP 或网关等到真实复用和治理需求出现再引入。
