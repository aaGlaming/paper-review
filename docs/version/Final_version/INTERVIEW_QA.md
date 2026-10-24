# paper-review 项目面试问题清单

> 本文用于面试准备，答案以当前代码和 `PROJECT_DOC.md` 为准。回答时应明确区分：**已实现**、**代码中未体现**、**后续设计建议**。不要把规划中的混合检索、RAGAS、token budget、MCP 或长期语义记忆描述成现成功能。

## 快速自我介绍模板

可以用下面的顺序讲项目：

1. **业务目标**：paper-review 是竞赛论文预审工作台，按已发布量规逐维检索证据、选档、做一致性检查并输出修改清单。
2. **系统性质**：核心是 LangGraph 驱动的 Agent 工作流，不是只在已有文本上加检索的 Chat；`/api/chat/*` 是独立的记录级问询路径。
3. **主链路**：FastAPI 路由做鉴权和量规门禁，LangGraph 负责 `parse → confirm → retrieve → score`，Agent 通过本地工具检索和提交结果，最后由确定性规则、verifier 和 MySQL 存档共同收口。
4. **诚实边界**：当前使用 Chroma child 向量与 MySQL parent，三类 `doc_type` 路由；无 embedding 时走 MySQL 回退，不是同轮 BM25+向量融合。token budget、RAGAS、Hit Rate/MRR、MCP 和独立模型网关均未实现。

## 1. 项目定位与总体架构

这个模块考察候选人能否在 30 秒内讲清产品边界、请求路径和框架与自研代码的责任分界。重点不是背名词，而是能用代码入口解释一次请求怎样变成可审计结果。

### Q1. 这个项目是增强型 Chat 还是 Agent？

**参考答案要点**

- 核心评审是 Agent 工作流：`POST /api/reviews` 创建评审，`POST /api/reviews/{review_id}/resume` 在人工确认后继续；图由 `backend/app/graph/review_graph.py:build_review_graph` 构建。
- `score` 阶段会顺序运行 evidence、topic fit、coherence、review、verifier 等角色，模型可以选择和调用工具，结果会改变后续状态。
- `/api/chat/*` 是记录级问询，负责读取已保存评审记录并生成带引用回答；它不负责主评审状态机。来源：`backend/app/api/chat_routes.py`。
- 因此回答“核心是 Agent，旁路有增强型 Chat 能力”最准确。

**可能追问及应对**

- **追问：只要用了 LLM 就叫 Agent 吗？**
  - 应对：不是。这里有状态图、工具调用、停止条件、人工中断、结果提交和核验；这些行为共同构成 Agent 工作流。
- **追问：Chat 路径为什么不算同一个 Agent？**
  - 应对：它主要是检索已存记录后回答，没有主评审的多角色状态机和逐维提交链路，代码上也由独立 chat routes 处理。

### Q2. 请按路由层、检索/工具层、记忆层讲一次架构。

**参考答案要点**

- 路由层：`backend/app/api/app.py` 装配 FastAPI、CORS、认证和路由；`backend/app/api/routes.py` 处理评审、上传、恢复和评测；`chat_routes.py` 处理问询。
- 编排层：`review_graph.py` 管理 `parse → confirm → retrieve → score`；`agent/runner.py` 组织专项 Agent、主评审和 verifier。
- 检索层：`retrieve/parent_child.py` 管理 parent/child、Chroma 和 MySQL 父块；`retrieve/three_route.py` 管理三路召回、合并、rerank 和 Top-K。
- 工具层：`agent/tools.py` 用 `StructuredTool` 和 Pydantic schema 注册工具；业务校验仍在工具函数内完成。
- 记忆/存储层：`ReviewState`、`ToolContext` 是工作状态；MySQL 存 `review_session`、评审、消息、父块和 `AgentStep`；Chroma 存 child 向量。
- LLM 层：`llm/client.py` 通过 `httpx` 调用 OpenAI-compatible Chat、Embedding 和 Rerank 服务。

**可能追问及应对**

- **追问：为什么不把所有东西都放在 Agent 层？**
  - 应对：鉴权、量规门禁、引用校验、加权合计和存档需要确定性边界，不能由模型自由决定，所以分层放在 API、工具和规则模块。

### Q3. 一次创建评审请求的输入输出是什么？

**参考答案要点**

- 输入包括 Bearer token、`paper_text` 或 `sample_id`，可选 `contest_id`；路由先解析用户和评测输入。
- `_load_evaluable_inputs` 检查赛题存在、量规已发布且有可评维度；失败返回 401/403/422，而不是让模型自行补齐。
- `_parse_sections` 把 Markdown 解析为章节树；创建 `ReviewState` 和 `ReviewSession`，状态停在待确认。
- 输出是 `review_id`、章节树和待确认状态，评分结果此时不返回。来源：`backend/app/api/routes.py:create_review_endpoint`、`review_graph.py:_parse_sections/create_review`。

**可能追问及应对**

- **追问：为什么先返回确认页？**
  - 应对：章节切分会影响检索范围和引用边界，先让人确认可以避免解析错误直接进入评分。

### Q4. 章节确认是普通字段还是工作流中断？

**参考答案要点**

- 是 LangGraph 的 `interrupt()` 中断，位于 `_confirm_node`，确认前不会进入 retrieve/score。
- resume 路由通过 `review_id` 恢复会话；如果当前进程没有检查点，`_restore_snapshot` 把 MySQL 快照恢复到 parse 节点，再继续图执行。
- 这体现了“可暂停/可恢复”的 Agent 工作流，而不是单次函数调用。来源：`backend/app/graph/review_graph.py:_confirm_node/resume_review`、`backend/app/api/routes.py:_restore_snapshot`。

**可能追问及应对**

- **追问：InMemorySaver 能支撑多副本吗？**
  - 应对：不能据代码确认。它是进程内检查点；MySQL 快照能辅助恢复业务状态，但不等价于共享的分布式 LangGraph checkpoint。

### Q5. LangGraph/LangChain 提供了什么，你们自己补了什么？

**参考答案要点**

- 框架提供状态图、`interrupt`、递归限制、Agent 消息循环、tool calling 接口和 middleware 扩展点。
- 项目自定义了评审状态、角色白名单、Pydantic 工具参数、引用连续子串校验、mention guard、确定性加权、verifier 降档、AgentStep 审计和 MySQL 存档。
- 框架不会自动知道“一个 quote 是否来自允许的 parent”，这个规则在 `agent/tools.py` 和 `scoring/selection.py` 中实现。

**可能追问及应对**

- **追问：为什么不完全手写 Agent 循环？**
  - 应对：人工中断、状态恢复、递归限制和标准 tool calling 已经是框架能力；手写会增加状态一致性和异常恢复成本。
- **追问：框架保证权限和幂等吗？**
  - 应对：不保证。当前权限主要在 HTTP 路由依赖，幂等和业务拒绝在工具及 AgentStep 层补充。

### Q6. 项目当前有哪些硬边界？

**参考答案要点**

- 不输出奖项、名次和获奖概率，修改清单有禁止词规则：`backend/app/report/change_list.py`。
- 只对已发布量规和可评维度评分；缺少量规时返回 422。
- 有证据的引用必须是 parent 正文中的连续原句；证据不足不换算成分数。
- 在线上传只支持 `.md/.docx`，PDF/OCR 在系统外转换；代码没有多租户、跨副本 checkpoint 或外部业务系统适配器。

**可能追问及应对**

- **追问：边界写在 prompt 里就够了吗？**
  - 应对：不够。关键边界还要在 `Literal`、工具业务校验、引用校验、加权函数和报告规则中重复落实。

## 2. RAG 检索策略

这个模块考察检索系统是否真正理解数据形态、引用约束和失败回退。面试时要先纠正术语：项目当前不是“同轮向量+关键词混合检索”，而是向量路径或 MySQL 回退，并按三种文档类型分路。

### Q7. 当前 RAG 是双路还是三路？

**参考答案要点**

- 代码实际有三类 `doc_type` 路由：`band_text`、`paper_child`、`pitfall`，由 `retrieve/three_route.py` 管理。
- 每路都可以产生候选，之后按 `parent_id` 合并；这是“三路文档路由”，不是用户常说的“向量+关键词双路”。
- 向量服务不可用或没有 embedding 配置时，`routes.py:mysql_search_round` 从 MySQL 父块回退；当前代码没有同一轮 BM25+向量融合。
- `PROJECT_DOC.md` 已把这个边界明确写出来，面试应主动说明。

**可能追问及应对**

- **追问：如果题目要求双路召回，你怎么回答？**
  - 应对：先说设计目标可以是向量+关键词双路，但当前实现是 Chroma 向量或 MySQL fallback。若要落地双路，需要新增关键词/BM25查询、统一候选 schema、同轮合并和独立评测。

### Q8. 为什么不能只用纯向量？

**参考答案要点**

- 纯向量对精确数字、档位编号、规则术语、章节名和否定词可能不稳定；项目又要求引用可追溯，不能只依赖语义相似度。
- 当前实现通过 parent/child 保留完整原文，并以 `review_id`、`contest_id`、`rubric_id`、章节类型和 `doc_type` 做过滤。
- MySQL 回退保证没有 embedding 时仍能得到受限父块候选，但它不是完整 BM25；这要诚实说明。

**可能追问及应对**

- **追问：MySQL fallback 是不是关键词检索？**
  - 应对：当前代码只能确认它按 review 和 section 过滤父块，不能把它描述成实现了 BM25 或倒排相关性排序。

### Q9. parent/child 为什么要拆开？

**参考答案要点**

- child 较短，适合 embedding 和局部相似度召回。
- parent 保存完整连续文本，`read_parent` 和 quote 校验可以确认引用是原文连续子串。
- child 记录 parent id 和字符偏移，便于从候选 child 回到完整 parent。来源：`backend/app/retrieve/parent_child.py:build_children/search_children_then_parents`、`retrieve/models.py:PaperParent`。

**可能追问及应对**

- **追问：为什么不直接把 parent 向量化？**
  - 应对：parent 太长会稀释局部语义，也不利于检索到具体证据；但最终输出仍需要 parent 原文，所以两者职责不同。

### Q10. 当前 chunk 策略和参数是什么？

**参考答案要点**

- 默认 `max_chars=200`，由 `parent_child.py:split_into_chunks/build_children` 实现。
- 表格独立成 child，普通段落按空行和长度合并；child 记录字符偏移。
- 这是字符长度上限，不是 token 长度；代码中没有语义模型边界检测器。
- 评审索引阶段先把确认章节写为 MySQL parent，再按该策略生成 child。

**可能追问及应对**

- **追问：200 字符是通过实验得到的吗？**
  - 应对：代码只能确认默认常量和行为，不能证明它经过系统性网格搜索。后续应按 Hit Rate/MRR、引用完整性和延迟做 chunk 参数评测。

### Q11. “语义边界切割”当前实现了吗？

**参考答案要点**

- 当前实现主要使用 Markdown 章节、空行、表格和字符上限，代码中未体现 embedding 驱动的语义边界切割。
- 章节确认本身是一个业务语义边界；表格独立切割是针对结构化内容的规则。
- 如果要增加语义切割，应保持 parent 原文和 child offset 不变，并在同一评测集上比较固定字符切割和语义切割。

**可能追问及应对**

- **追问：你凭什么说表格要独立？**
  - 应对：这是 `build_children` 的代码行为；表格通常包含连续数字和列关系，和普通段落混在一起会降低证据定位质量。

### Q12. 召回、去重、rerank、Top-K 的具体参数是什么？

**参考答案要点**

- 每个 doc route 最多 6 个 parent 候选；向量 child 候选默认按 candidate factor 3 扩大。
- `merge_candidates` 以 `parent_id` 去重，并合并同一 parent 的 `chunk_ids`，保留首次顺序。
- rerank 是可选的，只能重排已有候选集合；返回新 id 会被 `validate_rerank_order` 拒绝。
- 最终默认最多 4 个 parent；`read_parent` 每次最多读取 4000 字符。
- 检索最多两轮，第一轮为空才触发 `default_rewrite`。

**可能追问及应对**

- **追问：为什么不是 rerank 后再扩大候选？**
  - 应对：当前约束是 rerank 只重排同一集合，避免模型或 reranker 越权引入未经过过滤的 parent。

### Q13. query rewrite 什么时候触发？

**参考答案要点**

- 第一轮三路结果为空时才触发，`default_rewrite` 将维度和轮次信息加入查询。
- 第二轮仍为空就返回证据不足；最多两轮，不会无限改写。
- 这不是每次查询都调用 LLM 的改写，而是确定性 fallback/规则路径。来源：`three_route.py:default_rewrite/retrieve_dimension`。

**可能追问及应对**

- **追问：为什么不每次都让 LLM 改写？**
  - 应对：会增加延迟和成本，也可能改变精确术语；当前先用原查询，只有空结果才补一轮。

### Q14. 检索失败如何处理？

**参考答案要点**

- 没有 embedding 配置或无法走向量路径时使用 MySQL 父块回退。
- 两轮均无候选时返回“证据不足”，不会让模型凭空生成引用。
- rerank 越界、父块不在白名单、quote 不是连续子串时工具返回明确错误码，交给 Agent 修正或结束。
- Chroma/数据库持久化异常会进入 API 异常和日志路径；代码没有统一的数据库事务重试中间件。

**可能追问及应对**

- **追问：回退会不会导致质量下降？**
  - 应对：会牺牲语义排序能力，所以应在 trace 中标记 fallback，并把 vector 与 fallback 分开评测。

## 3. RAG 评测与问题归因

这个模块考察是否能把检索质量和生成质量拆开测，并能从 trace 定位问题。不要只报最终档位准确率，因为最终错误可能来自切片、召回、上下文或模型生成。

### Q15. 为什么检索指标和生成指标必须分开？

**参考答案要点**

- 检索指标回答“相关证据有没有进入候选集”，生成指标回答“模型有没有忠实、相关地使用证据”。
- 检索命中但答案错，问题更可能在 prompt、工具调用或生成；检索没命中则不能只责怪模型。
- 当前项目已有 quote 和档位评估，但 `Hit Rate/MRR/RAGAS` 代码中未体现，需作为独立评测扩展。

**可能追问及应对**

- **追问：只看最终档位一致率有什么问题？**
  - 应对：它无法区分“证据没召回”和“证据召回但模型判断错”，也无法衡量候选排序质量。

### Q16. Hit Rate@K 和 MRR 怎么定义？

**参考答案要点**

- Hit Rate@K：Top-K 是否至少命中一个 gold parent/chunk，命中 query 数除以 query 总数。
- MRR：第一个相关证据的倒数排名取平均，未命中记 0。
- 评测输入要包含 query、过滤条件、gold evidence set、实际候选序列、rerank 序列和最终 Top-K。
- 这套字段应从 `three_route.py` 的 route hits、去重结果和 rerank 后结果扩展记录。

**可能追问及应对**

- **追问：gold 只有一个 parent 吗？**
  - 应对：不应强制只有一个，应该允许可接受 evidence set；否则会把等价证据误判为未命中。

### Q17. 当前评测集和指标是什么？

**参考答案要点**

- `data/samples/eval` 有 12 篇评测论文，每篇 5 个维度，共 60 个维度项。
- 当前实现主要看档位一致、引用精确匹配和证据不足命中；默认 deterministic，`force=model` 才走模型评测。
- `scripts/check_eval_gold.py` 检查 gold 数据结构；`report/evaluation.py` 执行汇总。

**可能追问及应对**

- **追问：12 篇够不够？**
  - 应对：适合回归基线，不足以代表生产分布；应扩展不同文体、表格密度、数字规则、长文和边界案例，并分训练调参集与冻结测试集。

### Q18. RAGAS 在这个项目里已经用了么？

**参考答案要点**

- 没有。当前依赖和代码中未体现 RAGAS、Faithfulness 或 Answer Relevancy 的执行脚本。
- 设计上可以把 RAGAS 放在独立评测环境，不混入生产运行时；输入应包括 question、answer、contexts 和 reference。
- 现有连续子串引用校验可以作为 deterministic 前置检查，再结合 RAGAS 和人工抽检。

**可能追问及应对**

- **追问：为什么不完全依赖 LLM-as-judge？**
  - 应对：引用是否为连续原句、档位枚举和禁止词适合确定性判断；LLM judge 适合补充语义忠实度和相关性，不能替代硬规则。

### Q19. 怎样把“忠实度”和“答案相关性”分开测？

**参考答案要点**

- 忠实度：逐条检查回答断言是否能被引用 parent 支持；引用完整性和 quote 连续子串是确定性基础。
- 答案相关性：检查回答是否直接解决用户问题、是否带入无关评审记录，可用人工 1–5 分或 RAGAS answer relevancy。
- 上下文相关性：检查召回 parent 是否真的有助于回答，可用 context precision/relevancy。
- 三者分别记录，避免把“回答相关但无证据”和“有证据但答非所问”混在一个分数里。

**可能追问及应对**

- **追问：问询链路已有引用校验吗？**
  - 应对：`backend/app/chat/answering.py` 已有双向引用校验逻辑，可以复用为前置门禁，但 RAGAS 字段尚未落库。

### Q20. 出现错误时怎样归因到切片、召回或知识库缺失？

**参考答案要点**

- 切片问题：gold parent 在库中，但 child 被切断、关键表格被拆散或 quote 偏移不一致；比较 parent/child 和 chunk offset。
- 召回跑偏：gold 在库中且存在候选，但排名低或被错误 route/过滤；查看每路候选、去重顺序和 rerank 顺序。
- 知识库缺失：gold 内容根本不在 parent 或索引中；不能把它当作模型幻觉。
- 生成问题：Top-K 已含 gold，但模型引用错误、选档错误或回答无关；查看 prompt、tool result 和 verifier 动作。

**可能追问及应对**

- **追问：需要保留哪些 trace？**
  - 应对：query/rewrite、过滤条件、三路候选、去重后顺序、rerank 后顺序、Top-K、工具错误、quote 校验、模型输出和最终动作。当前 `AgentStep` 覆盖部分字段，Prompt 原文和 Hit/MRR 字段还需补。

## 4. Agent 工具调用与安全链路

这个模块考察候选人是否知道工具调用不是“模型给 JSON，系统就执行”。安全边界要依次经过 schema、白名单、业务规则、权限、风险、幂等、核验和审计。

### Q21. 项目工具调用的完整链路是什么？

**参考答案要点**

```text
模型 tool call
→ StructuredTool/Pydantic schema
→ call_tool 工具名与参数校验
→ parent/维度/章节/quote 业务规则
→ API 用户权限与资源归属
→ mention guard / verifier 风险判断
→ 已完成的人工章节确认
→ 重复提交保护
→ 工具结果写入 ToolContext/ReviewState
→ AgentStep、JSON log、metrics
→ report/review_dimension/change list 存档
```

- 对应代码主要在 `backend/app/agent/tools.py`、`middleware.py`、`verifier.py`、`trace.py` 和 `api/routes.py`。

**可能追问及应对**

- **追问：人工确认在每个工具前吗？**
  - 应对：不是。章节确认在状态图的 `confirm` 节点，早于 retrieve/score；当前没有每个本地读工具都弹人工确认。

### Q22. “模型返回合法 JSON”为什么仍然不能执行？

**参考答案要点**

- JSON 合法只说明语法可能符合 schema，不代表工具名在白名单、资源属于当前 review、quote 来自允许 parent，也不代表用户有权限。
- `call_tool` 还要检查未知工具、枚举、父块白名单、数量/长度和重复提交。
- 业务规则必须在本地函数再次校验，因为模型可能被 prompt injection 或错误上下文诱导。

**可能追问及应对**

- **追问：schema 校验和业务校验有什么区别？**
  - 应对：schema 校验类型、枚举、必填字段；业务校验资源存在性、权限边界、引用连续性、状态转移和幂等。

### Q23. 工具是如何注册和按角色控制的？

**参考答案要点**

- `build_tools(ctx, tool_names=...)` 创建本地 `StructuredTool` 集合，主评审和专项 Agent 传入不同白名单。
- 当前工具是进程内函数注册，不是 MCP Server；项目事实清单统计 16 个工具契约，包括检索、读 parent、提交维度、题目匹配、核验等。
- `call_tool` 是二次分发入口，会拒绝不在当前工具 map 的名称。

**可能追问及应对**

- **追问：为什么同时需要工具白名单和 call_tool 检查？**
  - 应对：白名单减少模型可见面，分发入口再做防御性校验，避免模型或上层传入未知工具绕过注册表。

### Q24. 项目有哪些权限边界？工具自己做 ACL 了吗？

**参考答案要点**

- HTTP 层通过 `current_user/require_permission` 处理 Bearer token、active 用户和 401/403；review/session 等资源检查用户归属。
- 工具上下文按 `review_id/contest_id/rubric_id/section_types` 过滤，避免跨评审取证。
- 工具函数接收的是已装配上下文，代码中未体现每个工具独立的用户 ACL 或外部 policy engine。
- 若未来开放远程工具，应把用户身份、租户、工具权限和审计上下文显式传给工具服务，不能只信本地路由。

**可能追问及应对**

- **追问：多租户需要改哪些地方？**
  - 应对：用户/租户字段要进入所有业务表和索引，所有查询和 Chroma metadata 过滤都要带 tenant scope，并增加跨租户测试。

### Q25. 风险判断和 verifier 做什么？

**参考答案要点**

- `apply_mention_guard` 根据量规约束和输出内容进行降档或证据不足处理。
- verifier 对主评审结果做受约束核验，只允许保留、降一级、标记证据不足或 reject，不能把结果升级。
- 这是确定性规则和模型核验的组合：模型可以提供判断，但最终动作被枚举和单向规则限制。

**可能追问及应对**

- **追问：为什么 verifier 不能升级？**
  - 应对：升级会放大模型过度乐观风险；当前产品更重视证据约束，verifier 只做保守修正。

### Q26. 项目怎样保证引用可信？

**参考答案要点**

- `read_parent` 只读取当前白名单 parent，且有字符上限。
- `submit_dimension` 要求 quote 是 parent 正文的连续子串；失败返回 `quote_not_substring`，不进入有效加权。
- parent 全文存 MySQL，child 只用于召回，避免向量片段成为最终引用来源。
- chat 回答路径也有引用双向校验，来源：`backend/app/chat/answering.py`。

**可能追问及应对**

- **追问：连续子串规则会不会太严格？**
  - 应对：它牺牲了一些改写灵活性，换来逐字可核查；如果要放宽，应增加规范化规则并保留原文 offset，不能直接接受模型摘要作为 quote。

### Q27. 哪些错误可重试，哪些不能盲重试？

**参考答案要点**

- 可重试：LLM HTTP 网络层最多两次尝试，超时 30 秒；无结果时检索 query rewrite 第二轮；`AgentStep` 唯一冲突按代码重试一次。
- 不应盲重试：参数/枚举错误、未知工具、权限错误、父块不存在、quote 非连续子串、重复提交、verifier reject。
- 数据库或 Chroma 持久化失败是否重试取决于上层生命周期，代码没有统一事务重试中间件。

**可能追问及应对**

- **追问：为什么参数错误不重试？**
  - 应对：相同输入的确定性失败不会因重试改变；应该把错误回填给 Agent，让它生成新的参数，或直接结束。

### Q28. 幂等具体做到什么程度？

**参考答案要点**

- 同一维度重复 `submit_dimension` 不覆盖已有结果，工具返回 `not_allowed`。
- `AgentStep` 有 `(review_id, idx)` 唯一约束，插入冲突时处理一次重试。
- 这不是完整的全局幂等：代码中未体现请求级 idempotency key、跨服务去重表或所有写操作的幂等契约。
- 如果接入队列，应为 resume、写报告和审计事件分别设计幂等键与 outbox/事务边界。

**可能追问及应对**

- **追问：重复请求返回成功还是错误？**
  - 应对：当前重复维度提交返回 `not_allowed`，不是把重复写当作幂等成功；如果要支持请求重放，需要另加请求级幂等键和结果回放表。

## 5. Agent 循环控制

这个模块考察能否防止 Agent 无限调用、无限花费和无进展循环。回答必须说出代码中的真实数值，并指出 token budget 目前缺失。

### Q29. 主评审 Agent 的循环上限是什么？

**参考答案要点**

- 12 次 model calls、24 次 tool calls、每个维度最多 3 步、墙钟 150 秒；LangGraph recursion limit 45。
- 连续两次 search/submit 没有新增 parent 或提交维度时，`BudgetMiddleware:_update_progress` 判定无进展。
- 这些值来自 `backend/app/agent/middleware.py` 和 `agent/runner.py`，不是泛化的“5~10 次”。

**可能追问及应对**

- **追问：面试题常要求 5~10 次，项目为什么是 12？**
  - 应对：按代码回答 12；如果产品需要 5~10，应在冻结评测集上调参，不能为了符合口径虚报实现值。

### Q30. token budget 实现了吗？

**参考答案要点**

- 没有。当前有调用次数、工具次数、每维步骤、墙钟和递归限制，但没有 token count、max output tokens、美元成本或租户级 token budget 字段。
- `PROJECT_DOC.md` 已把它列为局限；面试时应主动说明。
- 建议从模型响应的 usage、输入上下文长度和价格表建立每次 AgentStep 的成本账本，再在 middleware 中做 hard stop。

**可能追问及应对**

- **追问：只限制调用次数有什么漏洞？**
  - 应对：一次调用可能携带很长上下文，成本仍不可控；需要 token 预算和上下文裁剪协同。

### Q31. 停止条件有哪些？

**参考答案要点**

- 所有量规维度已提交：`all_submitted`。
- 预算耗尽、150 秒超时、连续无进展或 recursion limit 达到：进入预算/终止路径。
- 缺失维度最多两轮后 `_force_submit`，把缺失项标为证据不足，避免一直循环。
- 专项 Agent 失败不会阻断主评审，会保留错误状态。

**可能追问及应对**

- **追问：模型说“我已经完成”就停止吗？**
  - 应对：不能只信自然语言；需要检查工具提交状态、维度集合和预算状态。

### Q32. system prompt 如何约束 Agent？

**参考答案要点**

- `build_system_prompt` 规定工具使用顺序、四档枚举、连续 quote、每维必须提交、证据不足处理和预算边界。
- prompt 是行为提示，不是安全边界；本地 schema、业务规则、quote 校验和 verifier 才是强约束。
- 工具结果和专项 preload 会进入 Agent 消息上下文，当前没有独立 prompt 版本库和 token 裁剪器。

**可能追问及应对**

- **追问：为什么还要在代码里重复规则？**
  - 应对：模型可能违反 prompt、上下文可能被注入或截断；服务端必须把高风险约束做成不可绕过的确定性校验。

### Q33. 专项 Agent 的预算如何不同？

**参考答案要点**

- evidence：6 model、24 tool、每维 4 步、90 秒、recursion 28。
- topic fit：3 model、12 tool、每维 3 步、45 秒、recursion 16。
- coherence：4 model、16 tool、每维 3 步、60 秒、recursion 20。
- verifier 是受约束的一次工具调用，最多应用 5 个降档/证据不足动作，代码没有独立 token 上限。

**可能追问及应对**

- **追问：专项失败会不会把整单评审判失败？**
  - 应对：当前 `_run_specialist` 记录错误并返回状态，主评审仍可继续；产品是否要求硬失败需要另设策略。

### Q34. 如何防止工具调用风暴？

**参考答案要点**

- middleware 限制 model/tool calls、每维步数、墙钟、递归和无进展；工具白名单限制可调用面。
- 检索自身最多两轮，避免 query rewrite 无限重试。
- 仍有 token budget 缺口；生产化要增加每请求 token/cost quota、并发 semaphore、模型超时和熔断。

**可能追问及应对**

- **追问：只把 `recursion_limit` 调大能解决问题吗？**
  - 应对：不能。它只控制图递归深度，不控制实际 tokens、HTTP 并发、数据库写入或调用费用。

## 6. 记忆设计与数据生命周期

这个模块考察候选人是否能把“上下文”“会话历史”“长期记忆”分开，并能回答谁写、保存多久、谁能删、恶意内容怎么处理。项目当前没有成熟的长期 Agent Memory，必须坦诚。

### Q35. 工作记忆保存什么？

**参考答案要点**

- `ReviewState` 保存章节、评审输入、维度结果、状态和中间信息；`ToolContext` 保存当前工具上下文、证据包、检索结果和已提交维度。
- Agent message history 和工具结果构成当前轨迹。
- `InMemorySaver` 是进程内 checkpoint，进程退出即丢；代码未体现独立 TTL 或手工清理 API。

**可能追问及应对**

- **追问：工作记忆能跨进程恢复吗？**
  - 应对：不能单靠 InMemorySaver。MySQL `review_session` 快照可以辅助业务恢复，但还不是完整的共享图 checkpoint。

### Q36. 会话历史存几轮？

**参考答案要点**

- 主评审的工作状态按 Agent 循环运行；代码没有“只保留 N 轮”的统一截断策略。
- Chat 会话由 `chat_session` 和 `chat_message` 全量按时间/序号保存和读取，代码中没有固定轮数或滚动摘要。
- 因此正确回答是“当前主要存完整会话历史/业务记录，没有实现几轮摘要策略”。

**可能追问及应对**

- **追问：为什么不说只存 10 轮？**
  - 应对：因为代码没有这个限制；面试回答必须以实现为准。

### Q37. 长期 Memory 实现了吗？

**参考答案要点**

- 没有独立的 Agent 长期语义记忆、摘要合并、Redis memory 或对话向量记忆。
- `review`、`review_dimension`、`paper_parent`、`agent_step` 是业务存档和审计；记录级问询会检索它们，但不等于跨会话 Agent 记忆。
- Chroma 保存检索文档 child，不应描述成对话长期记忆。

**可能追问及应对**

- **追问：如果要加长期 Memory，第一步做什么？**
  - 应对：先定义 memory 类型、写入者、用户/租户隔离、保留期限、删除入口、敏感内容过滤和召回用途，再决定 Redis、结构化表或向量库。

### Q38. 谁可以写入长期记忆，存多久，如何删除？

**参考答案要点**

- 当前没有长期 Agent Memory，因此代码中未体现这些策略。
- 设计建议：只允许服务端经过校验的 summarizer 或显式用户操作写入；记录 owner/tenant、source、confidence、created_at、expires_at；提供按用户、会话、记录和内容类型删除。
- 删除应覆盖结构化表、向量索引、缓存和审计索引，并返回可验证的删除结果。

**可能追问及应对**

- **追问：用户删除 Chat 后，所有记忆都会删除吗？**
  - 应对：当前 chat session 有删除入口并可级联消息；不能推断它会删除评审记录、AgentStep 或 Chroma 文档，代码未体现统一 memory purge。

### Q39. 恶意内容怎样防止进入记忆？

**参考答案要点**

- 当前主要有 quote 连续子串、工具白名单、参数枚举、mention guard 和权限边界；没有完整的长期记忆写入审核流水线。
- 设计上应在写入前做敏感信息、prompt injection 指令、越权请求、脚本/链接和低置信度事实过滤，并保存原始来源而不是只存模型摘要。
- 召回到 Agent 前要标注 memory 来源和可信度，并把记忆当不可信输入，不能覆盖 system/developer policy。

**可能追问及应对**

- **追问：把用户一句话摘要后存起来安全吗？**
  - 应对：不安全。摘要可能固化错误或恶意指令，应限制写入类型、要求来源证据并支持人工/规则审核。

### Q40. 评审会话和 Chat 会话有什么区别？

**参考答案要点**

- `review_session` 是主评审状态快照，用于 resume、章节确认和评审业务恢复。
- `chat_session/chat_message` 是记录级问询的消息历史，用于上下文和回答。
- 主评审最终结果存 `review/review_dimension`，Agent 轨迹存 `agent_step`；它们有不同生命周期和访问权限。

**可能追问及应对**

- **追问：为什么不把所有状态都放聊天消息？**
  - 应对：聊天历史适合展示和问询，状态快照需要可恢复、可校验的结构化字段，二者语义不同。

## 7. 模型选型与替换方法

这个模块考察候选人能否把模型选择落到成功率、工具参数、延迟、成本和结构化输出，并能用评测集证明替换结果，而不是只说“更大模型更好”。

### Q41. 项目实际用了什么模型？

**参考答案要点**

- 代码通过 `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` 配置 Chat/Tool calling；Embedding 和 Rerank 也有独立环境变量。
- `DeepSeekChatModel` 是项目适配器类名，不能据此断言运行时一定使用 DeepSeek；provider/model 值由部署配置决定。
- 统一 HTTP client 使模型服务保持 OpenAI-compatible，不依赖厂商 SDK。来源：`backend/app/llm/client.py`、`agent/chat_model.py`、`.env.example`。

**可能追问及应对**

- **追问：为什么类名叫 DeepSeek？**
  - 应对：它是兼容适配器的历史命名；实际 provider 需要看运行时环境变量，代码本身不能证明供应商。

### Q42. 选择模型时最看重哪些指标？

**参考答案要点**

- 任务成功率：档位一致、引用有效、证据不足不乱判、verifier 通过率。
- 工具参数填写：schema 错误、未知工具、无效 parent、重复提交和 quote 错误率。
- 延迟与稳定性：单次 HTTP latency、重试率、150 秒内完成率、并发下 p95/p99。
- 成本：输入/输出 token、Embedding/Rerank 调用数和每次评审美元成本；当前未落 token usage，需补观测。
- 结构化输出：工具调用 JSON 可解析率和业务规则通过率。

**可能追问及应对**

- **追问：只看最终答案质量可以吗？**
  - 应对：不够。工具参数和调用成本是 Agent 关键指标，最终答案高分但调用风暴也不能上线。

### Q43. 如何从强模型切换到小模型？

**参考答案要点**

1. 用强模型在冻结评测集上建立 baseline，记录答案、工具调用、引用和延迟。
2. 按节点逐步替换：先尝试检索改写或结构简单的专项节点，再评估主评审和 verifier。
3. 同一数据、同一 prompt 版本、同一随机性配置比较档位、quote、工具错误、延迟和成本。
4. 只有在质量回归和风险阈值都可接受时替换；失败样本要归因到检索、工具参数还是生成。

**可能追问及应对**

- **追问：你会给每个角色配置不同模型吗？**
  - 应对：当前代码没有角色级独立模型配置；这是可演进方向，需把模型选择注入 runner，并保持同一评测集对比。

### Q44. 哪些节点适合小模型，哪些不适合？

**参考答案要点**

- 规则明确、结构简单的 query rewrite、格式校验、摘要分类可优先尝试小模型或确定性函数。
- 需要综合多段证据、处理工具链和输出最终档位的主评审更依赖工具参数正确率和上下文理解，应先以强模型做基线。
- verifier 不能只看语言能力，还要看降档保守性和不升级约束。
- 当前项目已把部分门禁、加权和引用校验做成确定性逻辑，减少模型承担的规则工作。

**可能追问及应对**

- **追问：为什么不让小模型做 verifier？**
  - 应对：可以实验，但必须验证它不会误放行或升级，且 verifier 本身有高风险；不能只比较文本相似度。

### Q45. 如何处理结构化输出不稳定？

**参考答案要点**

- 用 `StructuredTool`/Pydantic schema 让工具参数在进入业务函数前解析和校验。
- 对枚举、数量、长度和必填字段做显式限制；业务规则继续二次校验。
- 对可修正的参数错误回填错误码给 Agent，让它生成新调用；对权限、quote、重复提交等确定性失败不做盲重试。
- 记录 schema error、tool error 和最终状态，纳入评测。

**可能追问及应对**

- **追问：JSON mode 能替代 Pydantic 吗？**
  - 应对：不能。JSON mode 主要保证格式，不保证业务字段语义、资源权限和状态转移。

### Q46. embedding 和 rerank 模型如何选？

**参考答案要点**

- Embedding 要看术语、数字、中文论文段落、向量维度和召回延迟；用 Hit Rate/MRR 比较，而不是只看模型名称。
- Rerank 要看候选集合内的排序改进、p95 延迟、成本和是否能稳定保留 gold evidence。
- 项目允许两者通过环境变量独立配置，rerank 可选；当前代码不能确认实际模型版本。

**可能追问及应对**

- **追问：为什么 rerank 不能新增候选？**
  - 应对：候选过滤和权限边界已经在召回阶段确定，rerank 只负责排序，新增候选会绕过原有边界。

## 8. 架构边界：本地工具、MCP 与网关

这个模块考察是否能根据项目规模做取舍，而不是为了“看起来先进”强行引入 MCP、Gateway 或消息队列。答案要说清当前证据和未来触发条件。

### Q47. 为什么当前使用本地函数注册而不是 MCP？

**参考答案要点**

- 当前工具只服务同一 FastAPI 进程内的固定 Agent 白名单，工具、权限上下文、quote 校验、审计和数据库在同一边界内闭环。
- `build_tools` 使用本地 `StructuredTool`；代码中没有 MCP server/client、远程工具发现或工具网关。
- 本地注册减少网络跳数、序列化、部署和跨服务权限同步成本，适合当前形态。

**可能追问及应对**

- **追问：是不是因为项目规模小？**
  - 应对：可以说当前代码体现为单体和固定工具闭环，但没有正式规模阈值或 ADR。不要把“规模不足”说成代码已证明的结论。

### Q48. 什么时候评估 MCP？

**参考答案要点**

- 需要跨应用复用工具、第三方工具接入、独立扩缩容、跨团队工具治理或远程权限/审计时，再评估 MCP。
- 评估前要定义身份传播、租户隔离、schema 版本、超时、重试、幂等和审计协议。
- 不能只把本地函数搬到 MCP server；quote 校验和资源权限必须在远程边界重新执行。

**可能追问及应对**

- **追问：MCP 会自动解决权限吗？**
  - 应对：不会。它提供协议和工具发现方式，权限、审批、审计和数据隔离仍需系统设计。

### Q49. 什么时候需要模型网关？

**参考答案要点**

- 多 provider 路由、统一密钥、预算、限流、fallback、审计和跨服务模型观测成为共性需求时，网关价值明显。
- 当前项目由 `httpx` client 直接访问 OpenAI-compatible endpoint，模型配置是环境变量；没有独立网关。
- 引入网关前要比较额外延迟、单点故障、流式/工具调用兼容性和成本收益。

**可能追问及应对**

- **追问：为什么现在不直接加一层？**
  - 应对：当前引入会增加部署边界和故障点；先补 token/cost/latency 观测，等出现多 provider 或跨应用治理需求再抽象。

### Q50. 当前部署为什么没有独立 worker 或队列？

**参考答案要点**

- Compose 当前只体现 frontend、backend、mysql；Chroma 是应用本地持久目录，代码没有队列消费者、异步任务服务或独立日志服务。
- 主评审仍由 API 请求生命周期驱动，虽然有 150 秒控制，但不等于后台任务架构。
- 长评审、多并发或需要断线续跑时，应先把 checkpoint 持久化、任务状态和幂等做好，再引入队列。

**可能追问及应对**

- **追问：长请求放在 API 进程有什么风险？**
  - 应对：会占用 worker、放大超时和并发风险；演进方案是任务队列+持久状态+状态查询，但当前代码尚未实现。

### Q51. 如何判断是否过早抽象？

**参考答案要点**

- 先看重复需求和稳定边界：是否有多个调用方、跨团队复用、独立权限、独立扩缩容和集中审计要求。
- 当前本地工具和 HTTP client 的边界简单、调用方少，过早引入会增加网络和运维复杂度。
- 仍要保留清晰接口（tool schema、LLM client、trace），方便未来替换，而不是把未来组件提前部署。

**可能追问及应对**

- **追问：怎样证明某个抽象已经值得引入？**
  - 应对：用调用方数量、跨团队复用、独立扩缩容、权限治理和实际故障/成本数据作为证据；没有这些证据时先保持本地边界和清晰接口。

## 9. 成本、延迟与资源优化

这个模块考察是否能把模型系统当作有预算、有 p95、有失败成本的工程系统。回答要落到当前调用上限、可选路径和缺失观测。

### Q52. 一次评审的主要成本来源是什么？

**参考答案要点**

- 主评审和专项 Agent 的 Chat/tool calls；当前主路径最多 12 次 model、24 次 tool，专项 Agent 还会额外调用。
- Embedding 建索引和可选 Rerank 是独立模型调用成本。
- 长 prompt、parent 读取、重试和 150 秒内的多轮调用会增加输入 token 和延迟。
- 当前没有 token usage 和美元价格字段，不能从代码给出准确成本。

**可能追问及应对**

- **追问：如何补成本账本？**
  - 应对：从模型响应记录 input/output tokens、model、attempt、latency；按配置价格计算到 review_id、agent role 和 step，并写入 AgentStep/metrics。

### Q53. 如何降低延迟？

**参考答案要点**

- 先利用确定性路径：无 embedding 时不反复请求模型，检索最多两轮；减少不必要 query rewrite。
- 对能并行的专项 Agent 或索引工作做受控并发，但要考虑数据库、Chroma 和模型服务限流；当前代码主要按顺序编排。
- 用缓存复用确认后的 parent/child 索引、embedding 和重复 query 结果，但缓存必须绑定 review/rubric/version。
- 监控 p50/p95、各阶段耗时和重试率，再决定优化点。

**可能追问及应对**

- **追问：能把所有 Agent 并行吗？**
  - 应对：不一定。它们可能共享状态、数据库写入或同一模型配额；应先区分只读专项和有写入副作用的步骤。

### Q54. 如何降低 token 消耗？

**参考答案要点**

- 限制 `read_parent` 4000 字符、最终最多 4 个 parent，避免把全文和重复 chunk 都塞进上下文。
- 只把当前维度相关的证据和专项 preload 注入上下文；去重后再组装。
- 增加真正的 token budget 和上下文裁剪器，当前代码中未体现；不能只依赖字符上限推断 token 上限。

**可能追问及应对**

- **追问：字符上限能代替 token budget 吗？**
  - 应对：不能。不同语言和 JSON 结构的 token 密度不同，必须从 tokenizer 或模型 usage 统计。

### Q55. 哪些路径可以使用确定性回退？

**参考答案要点**

- 没有模型配置或 embedding 不可用时，检索可回退到 MySQL 父块路径。
- 评测默认 deterministic，模型评测需要 `force=model`。
- quote 连续子串、枚举、加权合计、禁止词和缺失维度补交适合确定性逻辑。
- 回退必须打标，防止把不同质量路径混在同一指标里。

**可能追问及应对**

- **追问：回退会不会隐藏模型服务故障？**
  - 应对：如果只返回正常结果会隐藏；应在日志、metrics 和响应元数据记录 vector/fallback、失败原因和质量差异。

### Q56. HTTP 重试怎样避免把延迟放大？

**参考答案要点**

- 当前 LLM client `_MAX_ATTEMPTS=2`、单次 timeout 30 秒，最多一次网络重试。
- 只对网络/瞬时错误重试；参数、权限、quote 和重复提交不重试。
- 生产建议增加指数退避、jitter、按错误类型限次、熔断和总墙钟预算；现有代码不能声称已有完整熔断器。

**可能追问及应对**

- **追问：网络错误重试两次会不会造成重复写？**
  - 应对：当前重试主要在 LLM HTTP 请求层；带副作用的工具提交不能简单套同样策略，应依赖提交保护、AgentStep 唯一键和明确的幂等契约。

## 10. 幻觉治理、安全与 Prompt Injection

这个模块考察候选人能否把模型当作不可信组件。回答应覆盖证据约束、注入隔离、权限、敏感信息和输出安全，而不是只说“prompt 写严一点”。

### Q57. 项目怎样治理评审幻觉？

**参考答案要点**

- 检索结果必须来自当前 review/rubric/章节过滤范围；引用必须是 parent 连续原句。
- `submit_dimension`、mention guard、verifier 和确定性加权共同限制无证据结论。
- 缺证据时输出证据不足，不把它换算成分数；verifier 不能升级结果。
- 主评审 prompt 规定工具顺序和每维提交，但 prompt 不是唯一防线。

**可能追问及应对**

- **追问：如果模型给了一个看起来很合理但库里没有的引用？**
  - 应对：quote 校验失败，工具返回错误；不能写入有效结果，也不应由后续文本润色绕过。

### Q58. 如何防止论文正文里的 Prompt Injection？

**参考答案要点**

- 论文内容只能作为检索证据数据，不能改变 system/developer 指令或工具白名单。
- 工具权限、参数、review scope 和 quote 校验在服务端执行，不由正文决定。
- 生成 prompt 应标注“不可信文档内容”和证据边界，模型输出还要经过 verifier 与确定性规则。
- 当前代码有这些业务门禁，但没有独立的注入检测模块或完整攻击集，需通过安全测试补齐。

**可能追问及应对**

- **追问：把正文转义一下就能防注入吗？**
  - 应对：转义只解决显示/格式问题，不能解决语义指令注入；关键是权限隔离、工具白名单和结果验证。

### Q59. 日志和审计如何避免泄露敏感信息？

**参考答案要点**

- JSON 日志按模块和日期轮转，默认保留 30 天；`logging.py` 过滤 API key、DSN、密码等敏感字段。
- AgentStep 保存参数 digest、结果摘要、错误码和耗时，不保存原始工具参数。
- 仍需注意论文正文、quote 和用户数据是否出现在业务存储/错误响应中；代码中未体现全面脱敏分类策略。

**可能追问及应对**

- **追问：参数 digest 能满足审计吗？**
  - 应对：适合证明调用发生和参数一致性，但不一定满足人工复核；高敏字段应保留受控、加密、最小权限的审计副本或明确不保存。

### Q60. Bearer token 和 CORS 在哪里处理？

**参考答案要点**

- `auth/deps.py` 解码 token、检查用户 active；路由依赖区分 401 和 403。
- `api/app.py` 读取 `CORS_ALLOW_ORIGINS`，默认允许本地前端回环地址，禁止 `*` 的宽松配置。
- 资源路由还要检查 review/session 用户归属，不能只依赖前端隐藏按钮。

**可能追问及应对**

- **追问：CORS 能保护后端权限吗？**
  - 应对：不能。CORS 是浏览器来源控制，真正权限仍靠 token、资源归属和服务端授权。

### Q61. 模型 API key 怎么管理？

**参考答案要点**

- 通过 `.env` 和 settings 配置，代码使用 HTTP client；日志层会过滤 API key、DSN、密码。
- `.env.example` 只提供键名模板，实际 secret 不应提交仓库。
- 生产应使用 secret manager、轮换、最小权限和按模型 provider 隔离；当前代码未体现云 secret manager 集成。

**可能追问及应对**

- **追问：日志过滤后是否能证明 secret 没泄露？**
  - 应对：不能只靠过滤规则证明；还要做日志快照扫描、错误响应测试、配置审查和 secret 轮换演练。当前代码只明确提供了字段过滤。

### Q62. 输出内容还需要哪些安全检查？

**参考答案要点**

- 当前已有禁止奖项/名次/概率、档位枚举、quote 校验、mention guard 和 verifier。
- 还应检查 Markdown/HTML 注入、恶意链接、超长输出、敏感信息回显和跨记录引用；代码中未体现完整的统一输出 sanitizer。
- 聊天回答需要确保引用 id、review scope 和用户权限一致，不能只验证文本格式。

**可能追问及应对**

- **追问：最危险的输出安全问题是什么？**
  - 应对：跨 review 引用和未经校验的 HTML/链接比普通措辞问题更严重；应先做资源 scope、引用 id 和渲染层面的确定性校验。

## 11. 并发、稳定性、日志与监控

这个模块考察能否从单实例代码推导出并发风险，并建立从请求到 AgentStep、模型调用、检索和存储的可观测链路。

### Q63. 当前系统适合多副本部署吗？

**参考答案要点**

- 代码和 Compose 体现的是单体 frontend/backend/mysql；Chroma 为本地持久目录，`InMemorySaver` 为进程内状态。
- 多副本会遇到 checkpoint 不共享、Chroma 本地数据不一致、进程内 metrics 不聚合和重复 resume 写入问题。
- 在多副本前需要持久化 checkpoint、共享/远程向量库、数据库并发控制、分布式 metrics 和请求幂等。

**可能追问及应对**

- **追问：MySQL 快照是不是已经解决多副本？**
  - 应对：只能辅助恢复业务快照，不能自动解决 LangGraph 线程状态、并发 resume、版本冲突和工具重复执行。

### Q64. 怎样处理同一 review 的并发 resume？

**参考答案要点**

- 当前代码有资源归属和部分重复提交保护，但没有明确的 review version/乐观锁或分布式锁证据。
- 设计建议：对 `ReviewSession` 增加 version，resume 携带 expected version，使用数据库条件更新；状态转移和 AgentStep 写入做幂等。
- 同一 review 的第二个请求应返回冲突/处理中，而不是并行修改 `ReviewState`。

**可能追问及应对**

- **追问：为什么不只用内存锁？**
  - 应对：内存锁只覆盖单进程，无法保护多副本和进程重启；应优先使用数据库条件更新或分布式锁，并保留幂等结果。

### Q65. 日志、AgentStep、metrics 各记录什么？

**参考答案要点**

- JSON 日志记录模块生命周期、错误和审计事件，按日期/模块轮转。
- `AgentStep` 记录 action、参数 digest、结果摘要、错误码和耗时，便于回看工具/模型链路。
- `/metrics` 暴露进程内累积指标；重启归零，没有 remote write 或跨副本聚合。
- 评测和排障时要用 `review_id/step_id/agent role` 串联这些记录。

**可能追问及应对**

- **追问：为什么既要 AgentStep 又要日志？**
  - 应对：AgentStep 是结构化业务轨迹，日志是通用运行事件；前者适合按 review 查询，后者适合运维检索。

### Q66. 你会配置哪些告警？

**参考答案要点**

- 可用性：`/health`、`/readyz` 失败，模型/Chroma/MySQL readiness 异常。
- 性能：评审 p95/p99、LLM timeout、重试率、Rerank/Embedding 延迟、队列/worker 饱和。
- 质量：evidence 不足率、quote 校验失败率、verifier 降档率、fallback 比例、工具参数错误率。
- 成本：单 review token/cost 超预算、模型调用数接近上限。
- 当前代码有 health/readyz/metrics 入口，但集中告警平台和阈值未体现。

**可能追问及应对**

- **追问：质量告警和服务告警为什么要分开？**
  - 应对：服务可能健康但质量下降，例如 fallback 比例或 quote 失败率升高；两类告警要分别看可用性与业务结果。

### Q67. 如果模型服务变慢，怎么保护 API？

**参考答案要点**

- 当前有单次 30 秒 timeout、最多一次网络重试、Agent 总墙钟 150 秒。
- 进一步需要连接池上限、并发 semaphore、熔断、限流、fallback 和请求取消；不能让每个 API worker 无限等待。
- 对已完成的 AgentStep 要保留状态，确保超时后可以安全查询或恢复，而不是重复执行所有工具。

**可能追问及应对**

- **追问：timeout 后应该重试整个评审吗？**
  - 应对：不应该默认从头重试；先读取已提交维度和 AgentStep，按可恢复节点继续，避免重复写入和重复模型费用。

### Q68. 日志保留 30 天够吗？

**参考答案要点**

- 当前默认保留 30 天是配置事实，不代表满足所有业务或合规要求。
- 应按日志类型、论文敏感级别、审计要求和删除请求定义 retention；原文 quote 和参数摘要可能需要不同策略。
- 需要证明轮转、删除、备份和恢复行为，并避免把长期业务记录误当作普通日志处理。

**可能追问及应对**

- **追问：谁决定 30 天？**
  - 应对：当前只是配置默认值，不是业务合规结论；应由数据分类、法务/合规要求、用户删除协议和审计需求共同确定。

## 12. 测试、评测与代码质量

这个模块考察候选人是否会围绕高风险边界写测试，并能解释如何让 Agent 代码可回归、可维护。重点是测试规则和故障路径，而不是只测 happy path。

### Q69. 你会怎样设计测试分层？

**参考答案要点**

- 单元测试：chunk 切割、parent/child offset、quote substring、枚举/schema、mention guard、weighted sum、rerank 集合校验。
- 集成测试：Chroma/MySQL、LLM mock、两轮检索、resume/快照、AgentStep 唯一冲突和权限隔离。
- 端到端：创建评审→人工确认→评分→报告→chat 问询；前端已有 Vitest/Playwright 目录，后端有按模块 tests。
- 回归评测：12 篇/60 维度冻结 gold，记录档位、quote、证据不足、延迟和调用次数。

**可能追问及应对**

- **追问：Agent 测试为什么不能只 mock 最终答案？**
  - 应对：要验证工具顺序、参数、错误恢复、停止条件、审计和幂等；只 mock 最终文本会漏掉最危险的中间行为。

### Q70. 最重要的负面测试有哪些？

**参考答案要点**

- quote 不是连续子串、parent 不在白名单、未知工具、非法枚举、重复维度提交、跨 review 访问。
- embedding 空结果、Chroma 不可用、MySQL fallback、rerank 新增 id、LLM 网络超时和第二次重试失败。
- 章节未确认、量规未发布、用户 inactive、禁止词输出和 verifier 试图升级。
- 并发 resume、重复 HTTP 请求和 Agent 超时后的恢复也应纳入。

**可能追问及应对**

- **追问：哪个失败最需要回归保护？**
  - 应对：引用绕过、跨资源读取、重复写覆盖和无证据加分，因为这些直接影响业务正确性和安全。

### Q71. 如何测试 RAG 评测本身？

**参考答案要点**

- 先用人工构造的 gold parent/chunk 验证 Hit Rate/MRR 公式、未命中记 0、多个可接受 evidence 的处理。
- 固定 query、过滤条件和候选序列，分别测试 vector、fallback、rerank 开关和去重顺序。
- 对 RAGAS/人工抽检保存输入快照和评审者版本，避免评测脚本变更造成不可比结果。
- 当前 Hit Rate/MRR/RAGAS 未实现，先把评测 schema 和 trace 字段定义清楚。

**可能追问及应对**

- **追问：评测脚本自身出错怎么发现？**
  - 应对：用人工构造的极小样本覆盖命中、未命中、多 gold、重复候选和空候选，并对指标结果做确定性断言；同时记录评测代码与数据版本。

### Q72. 如何验证“模型输出 JSON 合法但业务不合法”的场景？

**参考答案要点**

- 构造 schema 合法但未知工具、错误 review_id、越权 parent、非连续 quote、重复 submit、禁止词和超出数量上限的调用。
- 断言工具返回明确错误码、不写入有效结果、不改变加权合计，并生成 AgentStep/日志。
- 验证 Agent 能修正参数时只产生有限新调用，不能在错误输入上无限重试。

**可能追问及应对**

- **追问：schema 合法但越权的请求应该在什么层拦截？**
  - 应对：在工具分发和业务函数的服务端上下文校验层拦截，不能等模型下一轮自行发现，也不能只依赖前端。

### Q73. 怎样保证代码可维护？

**参考答案要点**

- 保持 API、graph、agent、retrieve、scoring、report、llm、observability 的边界，避免路由直接拼模型 prompt 或工具直接写任意表。
- 对工具 schema、错误码、状态字段和评测 trace 建立版本兼容策略。
- 把确定性规则做成纯函数，减少对模型、数据库和全局状态的隐式依赖。
- 用 `PROJECT_DOC.md`、架构图、事实清单和本文件记录“已实现/未实现”，代码变更时同步更新文档。

**可能追问及应对**

- **追问：如何重构一个过大的 `tools.py`？**
  - 应对：先按读工具、检索工具、提交工具、校验工具拆分，保持统一 schema/error contract，再逐步迁移调用方和测试，避免一次改变所有 Agent 行为。

### Q74. 你如何做一次代码审查？

**参考答案要点**

1. 先检查输入边界、权限 scope、异常和重试，确认错误不会变成成功。
2. 再看 Agent 工具 schema、调用白名单、状态转移、幂等和审计是否一致。
3. 检查 RAG 的过滤条件、去重、rerank 集合和 quote 来源，防止检索越权。
4. 用冻结评测集跑确定性回归，再抽样看 AgentStep 和日志，最后评估延迟/成本影响。

**可能追问及应对**

- **追问：你会优先看 prompt 还是业务代码？**
  - 应对：先看服务端约束和数据边界，再看 prompt；prompt 可以改行为，不能替代权限、校验和幂等。

### Q75. 如果线上出现一个错误档位，你会怎么排查？

**参考答案要点**

- 用 `review_id` 找 AgentStep、模型调用 latency、工具错误、检索 route hits、fallback、rerank 和最终 verifier 动作。
- 检查 gold/量规版本、章节确认结果、parent/child 内容和 quote 是否连续。
- 判断是知识库缺失、切片/过滤、排序、上下文拼装、模型工具参数、mention guard 还是 verifier 改写。
- 把样本加入回归集，修复后同时看质量、延迟、调用数和成本是否回归。

**可能追问及应对**

- **追问：如果日志没有 Prompt 原文怎么办？**
  - 应对：当前确实存在这个观测缺口；先用工具结果、AgentStep 和检索 trace 缩小范围，再补受控的 prompt hash/版本/截断元数据，避免直接长期保存敏感全文。

### Q76. 项目下一步最值得做什么？

**参考答案要点**

- 第一优先：补 retrieval trace 和 gold evidence，建立 Hit Rate@K/MRR，再分别测忠实度和相关性。
- 第二优先：补 token usage、价格表、单评审成本和每节点预算。
- 多副本前：持久化 checkpoint、会话版本/乐观锁、共享向量存储和跨副本 metrics。
- 只有需要跨应用复用工具、第三方治理或独立扩缩容时，再引入 MCP/工具网关；长期记忆则先定义删除、过期、隔离和恶意内容清理。

**可能追问及应对**

- **追问：为什么不先上 MCP 或大模型网关？**
  - 应对：当前更大的信息缺口是检索/生成归因、成本和状态一致性；先解决可验证性和稳定性，再根据真实复用与治理需求抽象边界。

## 面试前最后检查清单

- 能在 30 秒内说清：**FastAPI → LangGraph → Agent/工具/RAG → 规则核验 → MySQL/输出**。
- 能主动纠正：当前是三类文档路由、向量或 MySQL fallback，不是同轮 BM25+向量混合。
- 记住关键数字：主评审 12 model、24 tool、每维 3 步、150 秒、recursion 45；最终最多 4 个 parent、单路最多 6 个。
- 能说出没有实现的内容：token budget、Hit Rate/MRR、RAGAS、MCP、独立网关、长期 Agent Memory、统一删除策略。
- 工具链不要漏掉：schema、白名单、业务规则、权限、风险降档、幂等、quote 校验、审计和回填。
- 所有优化建议都要配评测方法、回滚策略和成本/延迟观测。
