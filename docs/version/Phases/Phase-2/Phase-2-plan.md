# paper-review 第二期计划（Phase 2 · Agent 化）

> **文档版本**：v2.0.0 · 生成时间：2026-10-19
> **文档性质**：第二期总体规划，供评审后按阶段拆解提示词。**第二阶段（Phase 2）文档统一命名 `Phase-2-plan.md`**，与 `Phase-1/paper-review.md`、`Phase-3/Phase-3-plan.md` 并列放在 `docs/version/Phases/` 下。
> **前置状态**：首期（P0～P11）已收口，v0.1.0～v1.0.0 十一项里程碑通过，需求第十二章 **18 条全 ✅**（`docs/plan/acceptance/report-V2.md`）；四道门禁基线 pytest **159** / build 0 / vitest **110** / playwright **43**。
> **分支基线**：`V4-Phase-I-Ares.Acceptance`（提交 `48deb6a`）。本期收口后分支命名 `V5-Phase-II-Agent.Acceptance`。
> **本期只改「怎么评」，不改「评什么」**：五维量规、四档定义、引用可回溯三条不动。
> **本次修订（2026-10-19 晚）**：技术路线改为 LangChain `create_agent`（新增 §3.0）；P12 拆为四份子任务；P13 图结构改为「子图挂载」，删掉手写循环与 state 里的 `plan/trace` 字段；预算表补 `recursion_limit` 兜底与实现落点；纪律新增两条（不自建循环、只许四个 LangChain 包）。

---

## 0. 本版定位：把「工作流」改成「有界 Agent」

首期做出来的是一条**固定管线**：`START → parse → confirm → retrieve → score → END`，五条 `add_edge` 写死。模型只在 `score` 节点里做一件事——从给定证据里挑档位、抄一句原话。

它跑得通、可验收、有 159 个测试护着，但**控制权不在模型手里**：

| 现在写死的东西 | 代码位置 |
|---|---|
| 先解析再确认、确认后才检索 | `build_review_graph()` 的 `add_edge` |
| 检索哪个维度、检索几轮、每轮几段 | `_retrieve_node_factory()` 遍历 `resolved_dimensions`；`MAX_ROUNDS = 2`、`MAX_PARENTS = 4` |
| 检索为空时怎么改写查询 | `default_rewrite()`，确定性拼装，不调模型 |
| 同一维失败重试几次 | `MAX_CHAT_ATTEMPTS = 2` |
| 什么时候算完成 | `score` 节点跑完即 `STATUS_DONE` |

**第二期的目标**：把这条管线换成**有界的 plan-act-observe 循环**——模型自己决定下一步查什么、够不够、要不要再来一次；但边界由代码框死：工具白名单、步数与调用预算、写结论只有一个口、自检只能降不能提。

一句话区分：**首期是「模型被调用」，第二期是「模型做决定，代码管边界」。**

---

## 1. 什么叫「真正的 Agent」：五条可验收判据

不玩概念，逐条给现状证据与验收方式。

| # | 判据 | 首期现状（代码证据） | 本期目标 | 验收方式 |
|---|---|---|---|---|
| 1 | **控制流由模型决定** | 五条 `add_edge` 硬连；模型无法决定再查一次 | `create_agent` 子图：模型自己决定调哪个工具、调几次；主图只保留 `confirm → agent → report` 三段 | 三篇演示的 `agent_step` 里，动作序列**不完全相同** |
| 2 | **有工具且能选工具** | `grep tools\|tool_call\|function_call` 命中 0 | 六个 `@tool`：读五写一，schema 由 `args_schema` 生成，越界调用返回 `param_invalid` | 越界工具名、缺参、类型错三种非法调用各返回固定错误码 |
| 3 | **有循环与终止条件** | 单趟直线，无循环 | `create_agent` 的循环 + 四道预算闸（含 `recursion_limit` 兜底） | 人为把预算调到 2 步，能正常停在「预算耗尽」并说明停在哪 |
| 4 | **轨迹可回放** | 只有 `chat_calls` 一个计数 | 每步 `agent_step` 落库：节点、动作、参数摘要、结果摘要、耗时、错误码 | 给定 `review_id` 能按序读出完整轨迹，不依赖日志文件 |
| 5 | **能自我修正** | 只有 JSON 解析重试 | `critique` 节点：只能把「充分/基本」降一档，必须给出 `chunk_id` + `quote` | 构造一条「证据里缺必提条件却被判充分」的样例，critique 必须降档 |

> **判据 5 的方向是单向的**：只降不提。让模型审自己，它天然会给自己打高分；给「降」的权限是唯一防得住这种偏移的结构。

---

## 2. 阶段总表（P12～P15，四阶段）

| 阶段 | 名称 | 目标（人能看到的结果） | 依赖 | 风险 |
|---|---|---|---|---|
| **P12** | Agent 适配层与工具层 | `DeepSeekChatModel` 与 `PaperRetriever` 两个 LangChain 适配器可用；六个工具用 `@tool` 注册；每次调用落 `agent_step`；图仍是线性 | — | 低（不满足可整体回退） |
| **P13** | LangChain agent 接入 | 用 `create_agent` 建出 agent 子图并挂进主图；预算四闸生效；前端能看到真实轨迹 | P12 | 中（调用次数与时限） |
| **P14** | 自检、降档与评测回归 | `critique` 只降不提；档位一致率不低于基线 | P13 | 中高（可能把档位拉低） |
| **P15** | 二期验收 | 五条判据逐条核验 + 首期 18 条回归 + `report-V3.md` | P12～P14 | — |

**串行理由**：P12 不引入循环，先把「工具 + 轨迹」这两件地基铺好，出问题能整段回退；P13 才动控制流；P14 的自检必须建立在「轨迹能回放」之上，否则降档说不清依据。

---

## 3. P12 · Agent 适配层与工具层

**本阶段四份子任务文档**（与 `v2.0.0` 勘误表一致，编号已排定不重排）：

| 版本 | 内容 | 状态 |
|---|---|---|
| `v2.0.0` | 工具调用探针 + `chat_with_tools` | **已通过**：探针判 A 路线，pytest 165 passed；Playwright 的红灯由 `v2.0.1` 的 P0 结案 |
| `v2.0.1` | LangChain 适配层（`DeepSeekChatModel` / `PaperRetriever`）+ 依赖清单补齐 | **已通过**：pytest 174 passed、Playwright 43 passed；P0 判为环境问题（`load_dotenv(override=False)` 回填模型键） |
| `v2.0.2` | 六个 `@tool` 工具与参数校验 | **已通过**：189 passed、Playwright 43 passed；六个工具 + `call_tool` 唯一入口 + 错误码封闭五个 |
| `v2.0.3` | `agent_step` 落库与线性接入（工具可被调用、轨迹可回放） | 提示词已就绪，待执行（旁路接入，不改分数） |

下面 §3.1～§3.5 是**设计依据**，不是执行顺序；执行按上表逐份推进，每份通过四道门禁才写下一条。

### 3.0 技术路线：用 LangChain 的 `create_agent`，不自建循环（2026-10-19 修订）

**环境实测**（共享解释器 `agent-task`，非推测）：

| 包 | 版本 | 在 requirements.txt 里？ |
|---|---|---|
| `langchain` | 1.4.5 | ❌ **不在**（实装却有） |
| `langchain-core` | 1.6.10 | ❌ 不在（随 langchain 装） |
| `langgraph` | 1.2.15 | ✅ 在 |
| `langgraph-prebuilt` | 1.1.0 | ❌ 不在（随 langgraph 装） |

**先记一个坑**：LangChain **1.x 已删除 `AgentExecutor`**，`from langchain.agents import AgentExecutor` 直接 `ImportError`。网上绝大多数「LangChain 做 Agent」的教程写的是 0.1/0.2 的 `create_tool_calling_agent + AgentExecutor`，照抄必炸。1.x 的官方入口是 `langchain.agents.create_agent`（返回一个 `CompiledStateGraph`），底层同源的是 `langgraph.prebuilt.create_react_agent`。

**选定路线**：

```text
create_agent(
    model         = DeepSeekChatModel(...)      # BaseChatModel 适配器，_generate 委托 client.chat_with_tools
    tools         = [6 个 @tool]                # 读五写一，submit_dimension 是唯一写口
    system_prompt = 选档纪律（只输出 band/chunk_id/quote）
    state_schema  = AgentState（带 review_id / contest_id / dimension_results / budget）
    checkpointer  = InMemorySaver()             # 与主图同构，thread_id 仍取 review_id
    middleware    = [BudgetMiddleware, TraceMiddleware]
)
```

**RAG 怎么结合**（这是本期的核心，不是"顺便加个向量库"）：

| 层 | 做法 | 为什么不用现成的 |
|---|---|---|
| 检索适配 | `PaperRetriever(BaseRetriever)` 包住现有 `retrieve_dimension`，把父块转成 `Document(page_content=父块全文, metadata={parent_id, section_type, chunk_ids, char_span})` | 不用 `VectorStoreRetriever`：我们的检索是「四键过滤 + 三路召回 + 合并去重 + 一次重排 + 截断 4 段」，Chroma 原生 retriever 表达不了三路与父子块回填 |
| 工具 | 六个 `@tool`，其中 `search_evidence` 内部走 `PaperRetriever`；`submit_dimension` 内部做子串校验与降档守卫 | 不把检索逻辑写进 tool 里：否则 LCEL 与「AI 问询」将来复用不到 |
| 模型 | `DeepSeekChatModel(BaseChatModel)`，只实现 `_generate` 与 `_llm_type`，内部调 `client.chat_with_tools` | 不用 `ChatOpenAI`：那会绕开 `client.py`，破坏「唯一 HTTP 出口」这条硬约束，也拿不到统一的超时/重试/密钥保护 |

**图怎么融合**：`create_agent` 返回的本身就是 `CompiledStateGraph`，当**子图**挂在 `confirm` 之后：

```text
START → parse → confirm → [agent 子图] → report → END
                          （内部的 plan/工具循环由 LangChain 管）
```

`confirm` 的 `interrupt()` 原样保留；`report` 仍由代码生成 `change_list`、仍由 `weighted_sum()` 加总。**不整体替换 retrieve+score**——那会把子串校验与加权丢掉。

**预算怎么控**：`create_agent` 没有 `max_iterations` 参数（那是旧 `AgentExecutor` 的东西）。三个落点：`config={"recursion_limit": N}`、`BudgetMiddleware.before_model / wrap_tool_call` 计数、工具内检查 `deadline`。超限抛统一错误，由子图外层收口成 `terminated_by=budget_exhausted`。

**依赖决策**：`requirements.txt` 补 `langchain==1.4.5` 与 `langchain-core==1.6.10`（两者已在共享环境，属"清单漏记"而非新装）。这一步单独一行写进进度记录，不许悄悄装完就完事。

### 3.1 前置验证（代码已落，结论待补）

`chat_with_tools` 已按 A 路线实现并通过六条离线测试，但**探针本身没有留档**：现有测试全部用 `MockTransport`，测的是"我们发了什么、怎么解析"，测不出"服务端认不认 `tools`"。所以第一件事是补一条真实探针，而不是继续往上盖楼。

先打一次探针，确认当前配置的模型端点支不支持 `tools` 字段：

| 路线 | 探针做法 | 判定 | 后续 |
|---|---|---|---|
| **A 标准 tool calling** | 发一条带一个 `echo` 工具的短请求，看响应 `choices[0].message.tool_calls` 是否存在且参数可解析 | 有 `tool_calls` | 走 A 路线，正式实现按 OpenAI 兼容格式 |
| **B 文本协议** | 同上，若返回 400 / 忽略 `tools` / 只回文本 | 无 `tool_calls` | 走 B 路线：约定模型输出 `{"action":{"name":...,"args":{...}}}` 或 `{"final":...}`，代码解析；解析失败重试 1 次 |

**探针结果必须写进 `docs/plan/progress.md`**（命令、HTTP 状态、是否含 `tool_calls`），A/B 路线二选一后**不许中途混用**。

### 3.2 模型客户端扩展（唯一 HTTP 出口不能破）

`backend/app/llm/client.py` 现在 `chat()` 的 payload 只有 `{model, messages, temperature}`。新增同文件内的兄弟函数：

```text
chat_with_tools(messages, tools, *, tool_choice="auto", temperature=0.2, transport=None)
    -> {"content": str, "tool_calls": [{"id": str, "name": str, "arguments": dict}], "finish_reason": str}
```

要求：

- 仍只发 `POST {LLM_BASE_URL}/chat/completions`，仍只用 httpx，**仍是全项目唯一 HTTP 出口**；
- `arguments` 是 JSON 字符串，解析失败抛 `LLMResponseError`，不返回半截结构；
- B 路线时该函数负责把文本里的 JSON 抽出来，抽不到同样抛 `LLMResponseError`；
- 密钥、请求头、原始报文不进任何返回结构与日志；
- 原有 `chat()` 的签名与行为**一行不改**，既有 159 个测试必须照跑。

### 3.3 工具注册表（六个，读五写一）

新增 `backend/app/agent/tools.py`，一张表定死工具边界：

| 工具 | 入参 | 读/写 | 复用 | 失败语义 |
|---|---|---|---|---|
| `list_dimensions` | 无 | 读 | `report/rubric.load_published_rubric` | 未绑定赛题 → `not_allowed` |
| `search_evidence` | `dimension_code`、`query`、`section_types?` | 读 | `retrieve/three_route.retrieve_dimension` | 空结果 → `ok` + 空列表（不算错） |
| `read_parent` | `parent_id` | 读 | `ParentRepository.get_parents` | 不存在 → `not_found` |
| `check_consistency` | `kinds?` | 读 | `review/consistency.check_numbers_citations_ranges` | 无命中 → `ok` + 空列表 |
| `get_constraints` | 无 | 读 | 同赛题 `constraints` 读取 | 同上 → `not_allowed` |
| `submit_dimension` | `dimension_code`、`band`、`chunk_id`、`quote` | **写** | `scoring/selection.quote_is_substring` + `apply_mention_guard` | `quote_not_substring` / `param_invalid` |

纪律三条：

1. **只有 `submit_dimension` 能写结论**，其余工具一律只读，代码里不提供任何「直接改档位」的入口；
2. 工具返回统一结构 `{"ok": bool, "data": ..., "error_code": str|null}`，`error_code` 只在白名单内：`param_invalid` / `not_found` / `not_allowed` / `quote_not_substring` / `budget_exceeded`；
3. 模型传了白名单外的工具名、缺必填参数、或参数类型不对，**直接返回 `param_invalid` 并把错误原文回给模型**，不抛 500、不静默当成空结果。

### 3.4 轨迹落库（`agent_step`）

新增独立 Base + 幂等建表（沿用 `ParentBase` / `ReportBase` 先例），表 `agent_step`：

```sql
CREATE TABLE `agent_step` (
    step_id      VARCHAR(64) PRIMARY KEY,
    review_id    VARCHAR(64) NOT NULL,
    idx          INT         NOT NULL,          -- 本单内从 1 递增
    node         VARCHAR(32) NOT NULL,          -- model / tools / critique（由 middleware 写入）
    action       VARCHAR(64) NOT NULL,          -- 工具名，或 finish / submit
    args_digest  VARCHAR(64) NOT NULL,          -- 参数摘要，不存论文全文
    result_note  VARCHAR(256) NOT NULL,         -- 结果摘要（命中几段、错误码）
    ok           TINYINT(1)  NOT NULL,
    error_code   VARCHAR(32) NULL,
    elapsed_ms   INT         NOT NULL,
    created_at   DATETIME    NOT NULL,
    UNIQUE KEY uk_review_idx (review_id, idx)
);
```

**谁来写这张表**：`TraceMiddleware` 的两个钩子——`after_model`（记一次模型决策：调了哪个工具、参数摘要）与 `wrap_tool_call`（记一次工具执行：耗时、成败、错误码）。**不手写循环、不靠日志文件反推**。

**事件字段与 Phase-3 的日志口径对齐**：`ts` / `level` / `module` / `event` / `review_id` / `step`。本期只写 `agent/` 一个模块的事件，**不建全量日志目录**（那是 Phase-3 P16 的活，见 `Phase-3-plan.md` §0）。

### 3.5 完成判据（阶段级；逐份判据见各自提示词）

> P12 拆成四份，单份通过不写「P12 通过」——四份全绿且探针结论留档，P12 才算过。

- [ ] 探针结果留档，A/B 路线明确写进 `progress.md`；
- [ ] `chat_with_tools` 有单测：正常返回、`arguments` 非法 JSON、`tool_calls` 缺失、HTTP 非 2xx 四种路径；
- [ ] 六个工具各有「合法调用 / 缺参 / 越界工具名」三类测试；
- [ ] `agent_step` 建表幂等；同一 `review_id` 重复写不出主键冲突；
- [ ] `submit_dimension` 收到非子串原句时返回 `quote_not_substring`，且该维**不产生档位写入**；
- [ ] 既有 159 个后端测试全过，冻结文件零改动；
- [ ] 四道门禁退出码全 0。

---

## 4. P13 · LangChain agent 接入

**本阶段两份子任务文档**：

| 版本 | 内容 | 状态 |
|---|---|---|
| `v2.1.0` | `create_agent` 装配（挂在 `score` 内部）、预算四闸、缺维补齐、真实调用验收 | **装配已完成**（pytest 214、13 条新测试）；**真实调用未执行**，欠账交 `v2.1.1` 的 P0 |
| `v2.1.1` | 补真实调用验收、无进展检测、`agent_terminated_by`、前端轨迹面板 | **已完成**：pytest 218；真实调用 21 行轨迹、18.874 s；**五维全「证据不足」（agent 未提交）**；Playwright 退出码 1 |
| `v2.1.2` | 修「agent 未提交结论」：诊断 → 收工协议 → 收尾补提交 → 预算 8→12；Playwright 回绿 | **已执行**：五维中 4 维由 `submit_dimension` 写入（基本/基本/基本/不足/证据不足）、21.5 s；但 `terminated_by` 误标 `budget_exhausted`（实为递归顶格）、Playwright 仍红 → 三笔账转入 `v2.2.0` 的 P0～P2 |

### 4.1 图结构（2026-10-19 修正：agent 挂在 `score` 节点内部，不替换图结构）

```text
START → parse → confirm → retrieve → score ──→ END
                                      │
                                      └─ 注入了 agent_runner 时：
                                         score 节点内部跑 create_agent 子图
                                         （模型自己调工具、自己收工）
```

- **为什么不能把 `retrieve` / `score` 换成独立 agent 节点**：冻结文件 `backend/tests/graph/test_interrupt.py` 断言 `final["score_node_calls"] == 1`、`status == "完成"`、`get_state().next == ()`。图结构一换，这个文件必红，而它不许改。
- 所以 `score` 节点做成**分派器**：未注入 `agent_runner` → 保持首期行为（`_make_score_node` 原逻辑）；注入了 → `score_node_calls` 照常 +1，内部跑 agent 子图，把 `ctx.results` 转成 `dimension_results`。
- `retrieve` 节点在 agent 模式下**提前返回空 `retrievals`**，检索改由工具完成，避免同一篇论文检索两遍。
- `critique` 仍放在 `score` 之后（P14 才加），因此 P13 阶段图仍是五节点，只是 `score` 内部换了实现。
- 子图与主图共用同一个 `checkpointer`，`thread_id` 仍是 `review_id`；**子图不单独传 checkpointer**，否则 resume 会找不到父图的快照。

**状态怎么传**（`create_agent(state_schema=...)`）：

| 字段 | 谁写 | 说明 |
|---|---|---|
| `messages` | LangChain | agent 子图的对话与工具结果，我们只读不改 |
| `review_id` / `contest_id` / `rubric_id` | 装配层 | 工具按它们取数据，**不从 messages 里猜** |
| `dimension_results` | `submit_dimension` | 唯一写口，内部已做子串校验与降档守卫 |
| `budget` | `BudgetMiddleware` | 计数与剩余额度；超限抛统一错误 |
| `terminated_by` | 子图外层 | `all_submitted` / `budget_exhausted` / `no_progress` |

**不再保留** `plan` / `step_index` / `trace` 三个字段：循环由 `create_agent` 管，过程写 `agent_step` 表，不在 state 里存第二份——两份状态一定会分叉。

### 4.2 预算与终止（四道闸，缺一不可）

| 闸门 | 默认值 | 落在哪（`create_agent` 没有 `max_iterations`） | 超限行为 |
|---|---|---|---|
| 单维步数 | ≤ 3 步 | `BudgetMiddleware.wrap_tool_call` 按 `dimension_code` 计数 | 该维记「证据不足」，`error_code=budget_exceeded` |
| 全局工具调用 | ≤ 24 次 | 同上，全局计数 | 直接进 `report`，`terminated_by=budget_exhausted` |
| 模型调用 | ≤ 8 次 | `BudgetMiddleware.before_model` | 同上 |
| 递归深度 | ≤ 25 | `config={"recursion_limit": 25}`（兜底，不替代上面三个） | LangGraph 抛 `GraphRecursionError`，外层转成 `budget_exhausted` |
| 墙钟时间 | ≤ 150 s（留 30 s 给报告与落库） | 每个工具入口检查 `deadline_at` | 同上，并显示「停在哪一步」 |

**终止只有三个合法出口**：五维都有结论、预算耗尽、连续两步无进展。没有第四个——不许「模型说停就停」而不留痕迹。

**无进展检测**：连续两步既没有新增 `parent_id`、也没有新的 `submit_dimension`，记 `no_progress` 并终止。这是防死循环的最后一根绳。

### 4.3 与首期硬约束的关系（一条都不能松）

| 约束 | 在循环里的落点 |
|---|---|
| 引用必须是父块连续子串 | `submit_dimension` 内部校验，失败返回错误码让模型重试；重试仍失败 → 该维记「引用失败」 |
| 证据不足不换算分数 | 只有 `submit_dimension` 成功且 band ≠ 证据不足 才进加权 |
| 权重与加总归代码 | `weighted_sum()` 一行不改；模型传 `weight` / `score` 一律丢弃 |
| 不按题号写分支 | 工具与阈值全部读 `constraints` / `rubric` 数据，代码里不出现题面字面量 |
| 唯一 HTTP 出口 | `agent/` 模块不 import client，模型调用从装配层注入 |

### 4.4 前端

- 解析页或评分页新增「Agent 轨迹」折叠面板：逐步显示「模型决策 → 工具调用 → 结果摘要」，工具名与错误码都来自 `agent_step`；
- **只渲染 `agent_step` 里真实存在的行**，禁止用定时器伪造进度（首期已立规矩，`grep setInterval|setTimeout frontend/src/views` 必须仍为 0）；
- 预算耗尽时明确显示「停在第 N 步 / 原因」，不无限转圈；
- 轨迹面板默认折叠，不干扰正常阅读。

### 4.5 完成判据

- [ ] 三篇演示各跑一次，`terminated_by` 均为 `all_submitted`；人为把预算调到 2 步，能正常以 `budget_exhausted` 收尾；
- [ ] 同一篇跑两次，`action` 序列允许不同，但**五维结论与引用校验结果可复核**；
- [ ] 构造一个检索永远为空的维度，出现 `no_progress` 终止且该维记「证据不足」；
- [ ] 轨迹面板显示步骤与 `agent_step` 行数一致，页面无定时器；
- [ ] 端到端耗时 ≤ 3 分钟（15 页以内样例）；
- [ ] 四道门禁全 0，冻结文件零改动。

---

## 5. P14 · 自检、降档与评测回归

**本阶段两份子任务文档**：

| 版本 | 内容 | 状态 |
|---|---|---|
| `v2.2.0` | P0 分清递归与预算、P1 Playwright 回绿、P2 全量门禁、主体 `critique`（只降不提） | **已完成**：231 passed、Playwright 45、真实调用 23.663 s / `all_submitted`；一致率 14/60、引用 31/31；**证据不足命中 1/2 待复测** |
| `v2.2.1` | 评测复测（重点是证据不足命中）、成本与延迟实测、critique 效果对照 | 提示词已就绪，待执行 |

> **2026-10-19 修正**：`critique` **不做成图节点**，改为 runner 的后处理（`agent 子图 → force_submit → critique → weighted_sum`）。原因是冻结测试锁死 `next` / `score_node_calls` / `status`，且五维结果与父块在 runner 里已现成，做成节点要来回塞 state。

### 5.1 `critique` 后处理职责

| 项 | 规则 |
|---|---|
| 触发范围 | 只检查 band ∈ {充分, 基本} 的维度；「不足 / 证据不足」不进自检 |
| 权限 | **只能降一档**：充分 → 基本，基本 → 不足；不许反向，不许连降两级 |
| 依据 | 必须给出 `dimension_code` + `chunk_id` + `quote`；给不出依据的降档请求直接丢弃 |
| 次数 | 每单最多 2 次降档，超出的自检结论不采纳（记 `budget_exceeded` 到 `agent_step`） |
| 输入 | 只用该维检索到的父块与该题 `constraints`，**不给它看全文**，防止它顺着别处找理由 |

### 5.2 评测纪律

- 档位一致率基线：**model 13/60（21.67%）**、引用精确匹配 27/27、证据不足命中 2/2；
- P14 完成后重跑一次 `GET /api/eval/summary?force=model`，**一致率不得低于 13/60**；引用匹配率必须是 27/27 或更高；
- 若一致率下降，先查是 critique 误降还是工具检索变差，**不许改 prompt 把分数凑回来**（v1.9.2 已立这条纪律）；
- 新基线连同命令、退出码、指标写进 `progress.md`。

### 5.3 成本与延迟实测

记三项：单篇模型调用次数、单篇 token 用量（可从响应 `usage` 读）、端到端秒数。三项都要与 P13 的实测值并列，用来判断自检值不值。

### 5.4 完成判据

- [ ] 构造「证据里缺必提条件却被判充分」的样例，critique 必须降档且给出 `chunk_id`；
- [ ] 构造「critique 想提档」的输入，代码拒绝并记 `agent_step`；
- [ ] 单篇降档次数不超过 2；
- [ ] `?force=model` 重跑：一致率 ≥ 13/60、引用 27/27、证据不足 2/2；
- [ ] 成本与延迟三项写进 `progress.md`；
- [ ] 四道门禁全 0。

---

## 6. P15 · 二期验收

### 6.0 子任务与状态

| 版本 | 内容 | 状态 |
|---|---|---|
| `v2.3.0` | 清污染 → 定级 critique 空转 → 判据 5 真实证据 → 三篇留档 → 18 条回归 → 成本对照 → `report-V3.md` + `V5` 分支 | 执行到 **P0.4 停止**：P0 清污完成（留证 `calls/v230-00-orphan-steps.sql`），P0.4 因「改 conftest」与「冻结 tests」的措辞冲突而停手 |
| `v2.3.1` | 勘误续跑：把 P0.4 的改动边界写成白名单（允许改 `conftest.py`，只冻结两个文件的断言），从 P0.4 接续到 P6 | **已执行**：P0.4 通过（+43 → +0）、P1 定级 C；P2 卡在「无修改约束的接口」而停。真实数据跑通 10 篇，另修两个缺陷（跨论文引用污染、档位枚举缺失） |
| `v2.4.0` | 判据 5 取证（复制赛题包 + 加离谱 mention 约束，不改代码即可造样本）→ 18 条回归 → `report-V3.md` + `V5` 分支 | 提示词已就绪，待执行 |

### 6.1 验收前置（2026-10-19 实测发现，必须先处理）

| 发现 | 证据 | 为什么挡住验收 |
|---|---|---|
| 判据 5 真实零触发 | 全库 96 条 `critique` 轨迹**全部来自 `review_id = r` / `r1`**，两者在 `review` 表不存在 | 自检只有单元测试证据，没有一条真实链路证据 |
| 数据污染 | `agent_step` 中 862 行属上述假 ID（`r` 101 / `r1` 762） | 任何按库统计的指标都不可信 |
| 评测不覆盖 agent | `evaluation.py` 走 `build_review_graph(retriever=..., chat=...)`，不注入 `agent_runner` | P14 的交付在 12 篇 gold 上从未被衡量 |
| guard 三重调用 | `agent/tools.py:207`、`agent/critique.py:81`、`graph/review_graph.py:405`；前两处参数完全一致 | submit 时已降档，critique 的 guard 分支结构上走不到 |

**上表四项已由 v2.3.1 与真实数据跑通处理完毕**（污染已清、fixture 已阻断、
10 篇真实论文全链路 `source=model` 跑通、引用 48/48 为本篇原句）。当前唯一未解决的是判据 5，
原因已查明：`apply_mention_guard` 第一行 `if band != BANDS[0]: return`，
**只有「充分」才进降档分支**，而真实产出极少「充分」。`v2.4.0` 的破解方式：
复制一份赛题包、加一条论文绝对命不中的 mention 约束，
**用 `POST /api/imports` 导入即可造出「能判充分但缺必提条件」的样本，不必新增任何接口**。

### 6.2 验收项

| # | 内容 | 交付 |
|---|---|---|
| 1 | §1 的五条判据逐条核验，每条附证据（`agent_step` 摘录 / 测试名 / 接口响应） | 报告 §a |
| 2 | 首期第十二章 18 条回归（重点：证据不足不计分、引用失败不进加权、不输出奖项） | 报告 §b |
| 3 | 三篇演示真实调用留档（`calls/`），密钥只查是否配置 | 报告 §c |
| 4 | 成本与延迟对照表（首期 vs 本期） | 报告 §d |
| 5 | 产出 `docs/plan/acceptance/report-V3.md`，格式对齐 V1 / V2 | 文件 |
| 6 | `task_plan.md` 增加 Phase-2 里程碑；分支命名 `V5-Phase-II-Agent.Acceptance` | 提交 |

**验收不能只看「跑通了」**：五条判据里任何一条拿不出证据，本期不写「通过」。判据 5 若只有 guard 证据、没有 critique 轨迹，只能写「有条件通过」并挂账。

---

## 7. 明确的非目标（第二期不做）

| 不做 | 原因 |
|---|---|
| 全自主（模型决定何时结束、自我扩权） | 本项目卖点是「引用可回溯」；全自主必然产出无出处结论，把最值钱的约束废掉 |
| 开放工具平台 / 任意注册新工具 | 工具白名单是边界的载体；开放注册等于放弃预算与权限控制 |
| 多智能体协作（评审员 + 复核员互掐） | 无需求驱动，且会把单篇成本翻倍、把 3 分钟时限打穿 |
| 让模型算权重、总分或直接写修改建议 | 权重与加总归代码（首期硬约束）；模型只能给 `band/chunk_id/quote` |
| 让 Agent 自己改论文或自动重写章节 | 越界到「代写」，需求明确不输出改写稿 |
| 流式输出 / WebSocket | 首期已定同步接口，前端步骤条按真实观测点亮即可 |
| 本地模型运行时（Ollama / vLLM） | 第十一章明令不接 |
| 奖项 / 名次 / 获奖概率 | 第十一章；`AWARD_WORDS` 已是硬门禁 |
| 上传解析（docx / pdf）与 `align` 节点 | 属 Phase-3 的 P21 / P22，本期工具只能检索已确认章节的父块 |
| 多用户 / 登录 / 教师端 | 属 Phase-3 的 P17～P20 |
| 用 `AgentExecutor` / `create_tool_calling_agent` | 1.x 已删除，且它不给检查点、不给 interrupt，与现有主图接不上 |
| 引入 `langchain-openai` 等厂商包 | 会绕开 `client.py`，项目立刻多出第二个 HTTP 出口 |

---

## 8. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 模型端点不支持 `tools` | P12 走不通 A 路线 | 先探针后动手；B 路线（文本 JSON 协议）已定，解析失败重试 1 次，仍失败则该维记「失败」 |
| **探针结论缺失、代码已按 A 路线落地**（当前状态） | 若端点其实不支持，`chat_with_tools` 上线即 400，而六条离线测试全绿测不出来 | 把"补探针"列为 `v2.0.1` 的第一件事；判 B 时停在 `v2.0.0` 改解析层，不许在错误前提上继续搭适配器 |
| 循环不收敛，反复检索同一段 | 超时、烧钱 | 无进展检测（连续 2 步）+ 四类预算 + 单维 3 步上限 |
| 调用次数从 5 次涨到 5～15 次 | P25 的 3 分钟时限更难 | 预算里墙钟 150 s 硬顶；P13 先测再调；检索结果按 `parent_id` 去重后截断 4 段 |
| 自检把档位一路拉低 | 评测一致率下降 | critique 只降不提、单篇 ≤2 次、必须给 `chunk_id` + `quote`；一致率低于 13/60 判 P14 不通过 |
| Agent 行为不可复现 | 报告无法追溯 | 每步落 `agent_step`；`temperature=0.2`；报告里给 `review_id` 可回放轨迹；不承诺「逐字复现」，承诺「可复核」 |
| 工具写坏数据 | 档位被污染 | 只有 `submit_dimension` 能写，且内部做子串校验与降档守卫；其余工具只读 |
| 两套日志口径 | Phase-3 P16 返工 | 事件字段现在就按 `ts/level/module/event/review_id/step` 定；P16 只扩展目录，不改字段 |
| 真库测试污染继续累积 | 行数失控 | 沿用「接受污染 + 记录行数 + 挂账」先例，不偷偷加删除接口 |
| `tools` 探针花钱 | 额度 | 单次探针，固定一条极短请求；结果留档后不再重复打 |

---

## 9. 每阶段通用纪律（必须带进每份提示词）

1. **先写失败测试，看它失败，再写实现**；先写了实现就删掉重来。
2. **退出码 0 才算通过**；命令、退出码、末行写进 `docs/plan/progress.md`，未过不写下一版。
3. 裁决写 `docs/plan/findings.md`，格式 `决定 — 原因 — 做错的代价`。
4. 不输出奖项、名次、获奖概率；评分 / 审查 / 报告源码**不按题号写分支**，差异全部放 `constraint` 与 `rubric` 数据。
5. 只有 `backend/app/llm/client.py` 能发 HTTP；`build_review_graph` 与新增的 `agent/` 模块内**不导入 client、不出现 HTTP 字样**；检索器与模型一律外部注入，未注入时保持占位且不报错。
6. **不许放宽既有断言**；冻结文件 `backend/tests/graph/test_interrupt.py`、`backend/tests/retrieve/test_rerank_cap.py` 不许改。
7. 密钥只进 `.env`，不打印、不回显、不落盘、不进日志、不进测试夹具、不进提交。
8. `.env` 模型选品保持首期定案：对话 DeepSeek `deepseek-flash` / 嵌入 `BAAI/bge-m3` / 重排 `BAAI/bge-reranker-v2-m3`。
9. 前端 TypeScript + `<script setup lang="ts">`；类型集中在 `src/api/types.ts`；**步骤指示器只能来自真实 `agent_step` 记录，禁止定时器伪造进度**。
10. 一次提示词只解决一个阶段；本版未通过不前强。
11. **本期新增五条**：
    - 预算不可绕过：任何路径（含重试、改写、自检）都必须先扣预算再执行；
    - 写结论只有一个口：除 `submit_dimension` 外不许有第二个函数能把 `band` 写进 `dimension_results`；
    - 轨迹必落库：没有 `agent_step` 记录的步骤视为没发生，不许只在内存里存在；
    - **不自建 agent 循环**：循环归 `create_agent`，代码里出现手写的「调模型 → 判工具 → 再调」推进逻辑即判不通过；
    - **LangChain 侧只许四个包**：`langchain` / `langchain-core` / `langgraph` / `langgraph-prebuilt`，其余（尤其 `langchain-openai`）一律拒绝。

---

## 10. 交付物

| 阶段 | 新增交付物 | 位置 |
|---|---|---|
| P12 | `chat_with_tools`；`DeepSeekChatModel`、`PaperRetriever`、六个 `@tool`、`agent_step` 表与建表函数；`requirements.txt` 补两行 | `backend/app/llm/client.py`、`backend/app/agent/`（新：`chat_model.py` / `retriever.py` / `tools.py` / `trace.py`） |
| P13 | `create_agent` 装配（`state.py` / `middleware.py`）、子图挂载、预算与终止、轨迹面板 | `backend/app/agent/`、`backend/app/graph/review_graph.py`、`frontend/src/views/论文解析.vue` 或 `分项评分.vue` |
| P14 | `critique` 节点、降档测试、新评测基线 | `backend/app/agent/`、`docs/plan/progress.md` |
| P15 | `report-V3.md`、Phase-2 里程碑状态 | `docs/plan/acceptance/report-V3.md`、`docs/plan/task_plan.md` |

---

## 11. 推进节奏建议

| 周次 | 内容 |
|---|---|
| 第 1 周 | P12 前两份：补 v2.0.0 探针记录与门禁（半天）→ `v2.0.1` 两个适配器 |
| 第 2 周 | P12 后两份：`v2.0.2` 六工具（一次一个，别攒）→ `v2.0.3` 轨迹与线性接入 |
| 第 3 周 | P13（`create_agent` 装配 + 预算 + 轨迹面板，风险最高的一段） |
| 第 4 周 | P14（自检 + 评测回归 + 成本实测） |
| 第 5 周 | P15（验收收口，产出 `report-V3.md`） |

**每阶段开始前**：先确认上一阶段四道门禁全绿（`npm run build` / `npx vitest run` / `npx playwright test` / `pytest backend/tests -q`），再动笔写该阶段提示词。

---

## 12. 与 Phase-3 的衔接

| 衔接点 | 约定 |
|---|---|
| 日志 | 本期只写 `agent/` 一个模块的事件，字段按 `ts/level/module/event/review_id/step`；Phase-3 的 P16 建全量目录时**复用同一套字段**，不改格式 |
| 上传与解析 | 本期工具只读「已确认章节」的父块；docx / pdf 与 `align` 节点仍是 Phase-3 的 P21 / P22 |
| Agent 边界 | Phase-3 的纪律第 12 条锁死：预算、工具白名单、`submit_dimension` 单写口、critique 只降不提，四条不得放宽 |
| 新工具 | Phase-3 若因 `align` 需要新工具，必须走同一注册表与参数校验，不许另开旁路 |
| 检索复用 | Phase-3 的 P19「AI 问询」**直接复用 `PaperRetriever`**：新增一个记录类数据源与一个 `query_records` 工具即可，不许另写第二套检索。这也是把检索做成 `BaseRetriever` 而不是塞进 tool 的原因 |
