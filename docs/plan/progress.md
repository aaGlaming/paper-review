# 进度

还没有运行过 pytest。某一版退出码为 0 之前，不把该版写成通过。

## v0.1.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/llm/test_client.py -q
退出码：0
末行：22 passed in 0.15s
未完成：无

补充说明：

- 测试函数 11 个，参数化后 22 项。先写测试、后写实现：测试首跑为 ImportError（`client.py` 还是占位文件，没有 `chat` / `embed` / `LLMConfigError` / `LLMResponseError`），实现补上后退出码 0。
- 除 `backend/app/llm/client.py` 外，仓库内没有第二处发 HTTP 的代码（已全局搜 `httpx`、`requests.`、`urllib`、`aiohttp`、`openai`）。
- `.env.example` 仍是 7 个键且值为空，本版未改。`compose.yaml` 服务名仍是 frontend、backend、mysql、chroma。
- `CLAUDE.md` 31 行，已含验证命令小节。`.gitignore` 已加 Chroma 数据目录条目。
- `docs/diagrams/runtime.architecture.html` 已交付（archify 随后安装到 `D:\.skills\archify`）。11 个节点：前端、后端 API、评审编排、MySQL、检索、Chroma、报告、规则审查、评分与选档、模型客户端、模型兼容接口。模型兼容接口在信任边界外，模型客户端是界内唯一 HTTP 出口，全图没有奖项类节点。
- 出图命令与结果：`node D:/.skills/archify/bin/archify.mjs finalize architecture docs/diagrams/runtime.architecture.json docs/diagrams/runtime.architecture.html --quality showcase --json`，四道门禁 validate / deliver / check / browser-check 全部 pass，诊断 0 条，无交叉、无绕行（maxBends 2）。产物 sha256 `c3f7d93fb7ee74ecf9774449f94855b2a25c80ba521a6854df068bb0e30e7253`，832655 字节。入库后在最终位置复核：`archify check … --json` 九项结构检查全过，`archify browser-check … --out-dir <临时目录>` 退出码 0，两种视口下文本投影 ≥ 7.5px。
- 交付方式见 `findings.md` 的 Ruling：产物在仓库外临时目录生成并通过门禁，再按字节复制入库（两份 sha256 相同）。回执留在 `%TEMP%\archify-paper-review\`，未入库。未做感知性目视复核，质量结论仅来自自动门禁。
- `ollama`、`sentence-transformers`、`qwen2.5` 三处命中全在 `docs/` 下的文档正文（禁止清单与文件树说明），不在代码、依赖或 compose 中。本版允许修改的目录不含这些文档。
- `data/` 下 15 个赛题 JSON、4 个样例 md，以及其余 8 个后端模块、7 个测试文件本版未改动。

## v0.2.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/graph/test_interrupt.py -q
退出码：0
末行：11 passed in 0.71s
未完成：无

补充说明：

- 测试函数 11 个（任务列的 8 项全覆盖，另加 3 项加固：中断 payload 携带章节树、切不出类型的标题归「未分类」且不新造第七类、模块内无 HTTP 与模型客户端引用）。先写测试、后写实现：首跑为 ImportError（`review_graph.py` 还是占位文件，没有 `REVIEW_STATUSES`），退出码 2。
- 图与实现：`parse → confirm → score → END`。parse 按 ATX 标题规则（`#` ～ `######`）切章节树，第一个标题之前的非空正文单列为「未分类」；confirm 用 `interrupt()` 交出章节树，`Command(resume=...)` 给的章节类型原样覆盖，不重新解析；score 是占位节点，只把 `score_node_calls` 加 1。状态另含 `parse_node_calls`，用来直接断言章节树未被重算。
- 检查点用 `InMemorySaver`，`thread_id` 取 `review_id`。同一 review_id 用同一 checkpointer 重建图后仍停在 `next == ("confirm",)` 且 `parse_node_calls` 仍为 1；resume 后 `parse_node_calls` 仍为 1、`score_node_calls` 为 1、`sections` 严格等于 resume 传入的值；对已完成的 review_id 再次 resume，`score_node_calls` 不变成 2。
- 空字符串与纯空白都抛 `EmptyPaperError`（`ValueError` 子类），且检查点里没有该 review_id 的条目。
- 本版不调用云端模型：`review_graph.py` 不含 httpx / requests / urllib / aiohttp / openai 字样，也不导入 `backend.app.llm.client`；测试不访问网络。状态词表恰为草稿解析、待确认、评分中、完成、失败五个，章节类型恰为六个。
- 中途自查发现测试自身一处缺陷并已修：原先断言整个会话的 `sys.modules` 里没有模型客户端，与 v0.1.0 测试同跑会误报（33 项里 1 项失败，退出码 1）。改为只检查本模块命名空间里导入的模块，修正后两版同跑 33 passed、退出码 0。
- 跨版回归：`pytest backend/tests/llm/test_client.py backend/tests/graph/test_interrupt.py -q` → 33 passed，退出码 0。
- 两张图已交付（archify 装在 `D:\.skills\archify`）：
  - `docs/diagrams/review.workflow.html`：9 个节点 = 8 步主路径 + 信任边界外的模型兼容接口；四个泳道，外部依赖泳道 `variant: exception`；`embed()` 与 `chat()` 两条依赖边指向界外节点。四道门禁全过、诊断 0 条，sha256 `1e9de82ae77d168fe66afde69446c373885fdf79f5e5861f287e3d3c2e3af8e0`，819513 字节。
  - `docs/diagrams/review.lifecycle.html`：5 个状态 + 5 条迁移，含「失败 → 评分中」的可恢复回边。四道门禁全过、诊断 0 条，sha256 `daf6aef3159c460853f46b8f4d3062e11a43d5b4a0cdc40af42fb5676fa517e5`，811119 字节。
  - 交付方式沿用 v0.1.0 在 `findings.md` 记的 Ruling：仓库外临时目录生成并通过门禁，再按字节复制入库（两份 sha256 相同），入库后在最终位置 `archify check … --json` 两张都是 ok: true、退出码 0。回执留在 `%TEMP%\archify-paper-review\v020\`，未入库。未做感知性目视复核，质量结论仅来自自动门禁。
- 未改动：`data/` 下 15 个赛题 JSON 与 4 个样例 md、`backend/app/llm/`、`backend/app` 其余模块、其余测试文件、`frontend/`、`CLAUDE.md`、`compose.yaml`、`.env.example`、`backend/requirements.txt`；`findings.md` 不在本版允许清单内，未改。

## v0.3.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/importing/test_catalog.py -q
退出码：0
末行：14 passed in 1.66s
未完成：无

补充说明：

- **实际连的是真实 MySQL**：`MYSQL_DSN` 已由人填写且实测连通（MySQL 8.4.11、库 `paper_review`、字符集 utf8mb4）。sqlite 内存库只是连不上时的兜底，本次没有启用；用例 `test_backend_selection_follows_availability` 会断言「能连真库就必须连真库」。
- 建表：SQLAlchemy 2 声明式模型 + `Base.metadata.create_all()`，在 `paper_review` 里实建七张表 contest、constraint、rubric_template、rubric、dimension、pitfall、exemplar（InnoDB、utf8mb4）。未引入 alembic，未引入锁定清单之外的任何依赖；`backend/requirements.txt` 未改。`constraint` 是 MySQL 保留字，表名用 `quoted_name` 固定加引号。
- 测试隔离：每个用例跑在外层事务 + 保存点里，进入时清空目录、结束整体回滚。跑完复查库里残留行数合计为 0，既有数据不受影响。
- 先写测试、后写实现：首跑为 `ModuleNotFoundError: No module named 'backend.app.api.app'`，退出码 2；实现补齐后退出码 0。
- 坏包矩阵逐条落测：权重合计改成 95 → 拒绝；删掉 `contest.json` 的 `title` → 拒绝；`check_type` 写成 `regex` → 拒绝；四档缺「证据不足」→ 拒绝；把「证据不足」的 score 写成 0 → 拒绝。五条都返回 400，响应体带 `filename` 与 `field`（如 `rubric.json` / `dimensions[0].weight`）。校验全部发生在写库之前，坏包之后已发布赛题行数与列表都不变。
- 无题号分支：`backend/app/importing` 与 `backend/app/api` 的源码里搜不到 `cumcm`、`fixture-extra`，也没有题号字面量比较（AST 逐节点断言）。自建第四道题 `data/contests/fixture-extra/` 走同一个 `import_package`，导入并发布后出现在 `GET /api/contests` 里。
- 接口实测：`GET /api/contests`、`POST /api/imports`、`POST /api/contests/{contest_id}/publish`、`/archive`、`/rubrics`、`POST /api/rubrics/{rubric_id}/publish` 六条路径齐备；`POST /api/catalog/imports` 返回 404，没有第二个导入路径；默认列表不含 draft 与 archived（归档后立即从默认列表消失）；复制量规产出 version 2 的 draft，发布后该赛题的 published 量规仍只有一条。
- 数据包：三道赛题各五个 JSON，题面取自需求分析里对三道公开赛题的原意描述；螺距 1.7 m、龙头 1 m/s、把手 ≤ 2 m/s、云团 3 m/s、有效范围 10 m / 20 s、无人机 70～140 m/s、禁止连续重茬、三年内至少一次豆类、滞销与 50% 降价（result1_1 / result1_2）逐条写入 constraints；五维权重各 20、合计 100，证据不足的 score 为 `null`；样例评语不含「证据不足」档。
- 自查抓到并修掉一处越界：`cumcm-2025-A/pitfalls.json` 原先拿 P6 样例的 `160 m/s` 当反例，违反「这些数字不要写进赛题 JSON」，已删掉该数字（保留 70～140 m/s 区间）。复查 15 个赛题 JSON 里没有 412、386、1286、974、22.4、18.6、160 任何一处。
- 库保持空表（测试写入全部回滚，没有把赛题数据落成长期状态）。要手工看效果：`POST /api/imports` 传 `{"package_dir": "data/contests/cumcm-2024-A"}`，再 `POST /api/contests/cumcm-2024-A/publish`，然后 `GET /api/contests`。
- 跨版回归：`pytest backend/tests/llm/test_client.py backend/tests/graph/test_interrupt.py backend/tests/importing/test_catalog.py -q` → 47 passed，退出码 0。
- 未改动：`data/samples/`、`frontend/`、`backend/app/llm/`、`backend/app/graph/`、其余后端模块与测试文件、`CLAUDE.md`、`compose.yaml`、`.env.example`、`backend/requirements.txt`、`.env`。

## v0.4.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/retrieve/test_parent_child.py -q
退出码：0
末行：14 passed in 3.20s
未完成：无

补充说明：

- **实际环境**：向量库用临时目录里的**真实 chromadb 1.5.9**（`PersistentClient` + 自定义假 EmbeddingFunction，add 与 query 都显式传向量），父块仓储用**真实 MySQL**（`paper_parent` 实建在 `paper_review` 里，InnoDB / utf8mb4）。不起 Docker、不访问网络、不下载嵌入模型；sqlite 只作兜底，本次未启用。用例 `test_backend_selection_follows_availability` 断言「能连真库就必须连真库」。
- 先写测试、后写实现：首跑为 `ImportError: cannot import name 'models' from 'backend.app.retrieve'`，退出码 2；实现补齐后退出码 0。
- 本机实测（写测试前先验证，作为本版的依据）：chromadb 1.5.9 **不会**拦 `doc_type` 非白名单的写入；数组型 `section_type` 用 `$in` 过滤**静默返回空且不报错**；换成单值字符串 + `$in` 正常命中。所以白名单与「单值字符串」两条都由本模块自己校验，不指望向量库兜底。
- 顺序固定为过滤 → 召回 → 取父块：`where` 里带 `contest_id`、`rubric_id`、`section_type $in`；用例用记录型客户端断言过滤条件确实交给了向量库（`where` 内容与 `n_results`），且候选 6 条、`limit=4` 时恰好返回 4 条、全部满足过滤。
- 父块全文只在 MySQL：`save_parents` / `get_parents` 走 `paper_parent`；用例断言返回文本等于 MySQL 里的父块全文、且不等于子块片段，`chunk_ids` 是命中的子块 id。
- 切块：表格单独成块，不与前后段落合并。用例给「段落 + 表格 + 段落」，断言恰好 3 块、表格块含表头与数据行、不含前后段落文字，且每个块都能用 `char_start:char_end` 切回原文。
- `doc_type` 白名单只有五个值；写成 `paper_parent` 时抛错，且向量库里没有留下任何写入。元数据八个键齐全，`section_type` 是单值字符串（用例断言不是数组）。
- 本版不调用模型：`backend/app/retrieve` 源码不含 httpx / requests / urllib / aiohttp / openai / `backend.app.llm`，也不导入模型客户端；向量一律由调用方显式传入，模块内的占位 EmbeddingFunction 一旦被调用就直接报错，避免 Chroma 去下载默认嵌入模型。未传 `query_embedding` 时函数抛错而不是偷偷调模型。
- 重排位置已留出：`rerank` 参数可以改候选顺序，但传入候选之外的 id 会抛错（用例覆盖「只能改顺序」与「不能加回被过滤片段」两条）。
- `paper_parent` 的表模型与仓储放在 `backend/app/retrieve/models.py`，只读复用 `backend/app/importing/db.py` 的引擎与会话工厂，**没有修改** importing；`paper_review` 里现有 8 张表（赛题七张 + paper_parent），测试写入全部回滚（跑完复查 paper_parent 行数为 0）。
- 两张图已交付（沿用 v0.1.0 在 findings.md 记的 Ruling：仓库外临时目录生成并通过门禁，再按字节复制入库，两份 sha256 相同）：
  - `docs/diagrams/retrieve.sequence.html`：8 个参与者、13 条消息，覆盖「生成查询 → 过滤子块 → 召回 → 取回父块 → 顺位重排占位 → 送入选档」，选档的 `chat()` 指向界外的模型兼容接口。四道门禁全过、诊断 0 条，sha256 `b1940fdb8f5c151bf8af5ce58cc13666b3fbea74f87c7df850e72d27ed885838`，823277 字节。
  - `docs/diagrams/chunks.dataflow.html`：5 个阶段、8 个节点，图上直接写明「子块片段与向量进 Chroma」「父块全文留在 MySQL」「送入模型的是父块全文」。四道门禁全过、诊断 0 条，sha256 `b40215c336b79f22967da26ca9f1bf2e612d19f7a07158e1015ebd6cc8aeba10`，816792 字节。
  - 入库后在最终位置复核：两张 `archify check … --json` 都是 `ok: true`、退出码 0。回执留在 `%TEMP%\archify-paper-review\v040\`，未入库。未做感知性目视复核。
- 跨版回归：`pytest backend/tests/llm/test_client.py backend/tests/graph/test_interrupt.py backend/tests/importing/test_catalog.py backend/tests/retrieve/test_parent_child.py -q` → 61 passed，退出码 0。
- 未引入新依赖（chromadb、SQLAlchemy 均在锁定清单内）；`backend/requirements.txt`、`.env` 未改；`backend/app/importing/`、`backend/app/graph/`、`backend/app/llm/`、其余模块、`data/`、`frontend/`、其余测试文件均未改动。

## v0.5.0
状态：未通过（由 v0.5.1 收口）
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q
退出码：1
末行：1 failed, 73 passed in 5.14s
未完成：`backend/tests/retrieve/test_rerank_cap.py::test_unconfirmed_sections_never_reach_retrieve_node` 失败，报错 `KeyError: 'retrieve_node_calls'`

补充说明：

- 本版交付的代码（都在 v0.5.1 修复后保留）：`backend/app/retrieve/rerank.py`（重排接口 + 假客户端 + 只读配置项）、`backend/app/retrieve/three_route.py`（三路各自过滤召回 → 合并去重 → 一次重排 → 截断到总共 4 段；两轮检索，`MAX_ROUNDS = 2`）、`parent_child.py` 增加 `doc_types` 分路过滤、`backend/app/graph/review_graph.py` 插入 retrieve 节点（`parse → confirm → retrieve → score → END`，检索器可注入）、`backend/tests/retrieve/test_rerank_cap.py`（13 个用例）。本版新增的状态键：`contest_id`、`rubric_id`、`retrieve_section_types`、`retrievals`、`retrieve_node_calls`。
- 第一次的单文件结果：`pytest backend/tests/retrieve/test_rerank_cap.py -q` → `1 failed, 12 passed in 1.93s`，退出码 1；单独跑失败用例 → `1 failed in 1.70s`，报错正是 `KeyError: 'retrieve_node_calls'`（断言 `snapshot.values["retrieve_node_calls"] == 0`），不是 ImportError，也不是收集错误或别的功能错。
- 全量基线（修复前）：`pytest backend/tests -q` → `1 failed, 73 passed in 5.14s`，退出码 1。
- 根因与只改一行的收口过程见下一节 v0.5.1；本节按事实记为未通过，不写成通过。

## v0.5.1
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q
退出码：0
末行：74 passed in 4.11s
未完成：无

补充说明：

- 先复现后动代码：单文件 `1 failed, 12 passed`；单跑失败用例报 `KeyError: 'retrieve_node_calls'`；全量基线 `1 failed, 73 passed in 5.14s`，退出码 1。
- 根因：图停在 confirm 节点时，retrieve 节点从未执行，它负责写入的 `retrieve_node_calls` 也就从未出现在状态里；而 `create_review()` 的初始状态里已经预置了 `score_node_calls` 与 `parse_node_calls`，**漏了 P4 新增的 `retrieve_node_calls`**。
- 实现侧**只改了一行**：`create_review()` 初始状态字典里加 `"retrieve_node_calls": 0`。没有改节点顺序、没有改 interrupt 行为、没有动 parse / confirm / retrieve / score 四个节点的逻辑，没有调 `chat()` / `embed()`，没有发 HTTP。
- 测试**未被改动**：失败用例的断言仍是 `snapshot.values["retrieve_node_calls"] == 0`（严格取值，没有改成 `.get(key, 0)`）。时间戳可查：`backend/tests/retrieve/test_rerank_cap.py` 仍是 v0.5.0 写下时的 16:57，本节只写了 `backend/app/graph/review_graph.py`（19:08）。
- 新增状态键自检结论（只判断，未顺手改）：五个键里**只有 `retrieve_node_calls` 需要预置初值**——它在图停在 confirm 时就被直接下标取值。`retrievals` 只在 resume 之后被直接取值，而那时 retrieve 节点已经写过它；`contest_id`、`rubric_id`、`retrieve_section_types` 在实现里一律走 `state.get(...)`（缺省即 `None` / 空元组，正是「还没绑定」的语义），代码里没有对它们的直接下标取值；测试里出现的 `["contest_id"]` 命中都属于 importing 的赛题包字段，与图状态无关。
- 回归：单文件 `13 passed in 1.97s`、退出码 0；全量 `74 passed in 4.59s`、退出码 0。修复前 73 passed + 1 failed = 74，修复后仍是 74，没有把别的用例改坏，也没有减少用例。
- 五张 archify 图在最终位置复检：`runtime.architecture`、`review.workflow`、`review.lifecycle`、`retrieve.sequence`、`chunks.dataflow` 的 `archify check … --json` 全部 `ok: true`、退出码 0。
- 未改动：`backend/tests/`、`backend/app/retrieve/`、`backend/app/llm/`、`backend/app/importing/`、`backend/app/api/`、`data/`、`frontend/`、`docs/diagrams/`、`.env`、`backend/requirements.txt`、`compose.yaml`。

## v0.6.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/scoring/test_quote_and_weight.py -q
退出码：0
末行：17 passed in 1.62s
未完成：无

补充说明：

- 先写测试、后写实现：首跑为 `ImportError: cannot import name 'selection' from 'backend.app.scoring'`，退出码 2；实现补齐后 17 passed、退出码 0。
- 测试 17 个（要求的 10 项全覆盖，另加 7 项：降档守卫完全由数据驱动——换一组关键词数据结果就换、未注入 chat 时二次 resume 不重算、注入 chat 但缺 rubric_dimensions 时直接拒绝、喂给模型的证据不超过 4 段（断言 `[4]` 在、`[5]` 不在）、源码不含 HTTP 与模型客户端、`REVIEW_STATUSES` 仍是五个、维度编码与共享常量一致）。
- `backend/app/scoring/aggregate.py`：纯函数 `weighted_sum(dimensions, dimension_results)`。`band` 属三档且 `status` 不是「引用失败 / 失败」才进入合计；「证据不足」「引用失败」「失败」「量规里没有这一维」四种排除各带中文原因。权重只读 `dimensions`，模型结果里的 `weight` / `score` 一律忽略——用例分别验证「改量规权重 20→30，total 40→50」与「模型 JSON 带 weight 99 / score 100，total 仍是 20」。
- `backend/app/scoring/selection.py`：`parse_scoring_json()` 只采纳 `band` / `chunk_id` / `quote`（其余字段丢弃，容忍 ```json 围栏）；`quote_is_substring()` 严格按连续子串判定，不做分词、不模糊匹配；`apply_mention_guard()` 是数据驱动的降档守卫；`build_scoring_messages()` 把证据逐段编号并附上 `parent_id` 与 `chunk_ids`。
- 选档与三种状态：注入了 `chat` 时逐维调用，每维最多两轮（`MAX_CHAT_ATTEMPTS = 2`，解析失败只重试一次）；检索为空的维度**不问模型**、直接记「证据不足」；模型返回「证据不足」也记该状态；原句对不上记「引用失败」；两次都解析不出记「失败」并把原因写进该维。维度结果里 `dimension_code`、`band`、`status`、`chunk_ids`、`quote`、`reason` 都可读。
- 未注入 `chat` 时评分节点沿用 v0.2.0 的占位实现，状态里不出现 `score` 与 `dimension_results`——本版用例直接锁住这一条，P1 的四条闸门断言在全量回归里也仍然通过。
- 降档守卫实测：烟幕题固定切片「烟幕云团在空间中静止不动」配 `data/contests/cumcm-2025-A/constraints.json` 里的 mention 约束（关键词 10 m / 20 s）→ 模型给「充分」被降到「基本」，`guard.downgraded` 为真。题面字面量没有进代码（用例扫描 graph 与 scoring 源码里没有「静止」「3 m/s」等字面量）。
- 复核结果：单文件 `17 passed in 1.65s`、退出码 0；全量 `91 passed in 4.25s`、退出码 0（74 + 17，没有把旧用例改坏）。
- 本版不在出图范围，`docs/diagrams/` 未改动（五张图仍是 v0.1.0～v0.4.0 交付的版本）。
- 未改动：`backend/tests/graph/test_interrupt.py`（时间戳仍是 P1 的 14:48）、`backend/app/llm/`、`backend/app/retrieve/`（源码仍是 17:00，只有 `__pycache__` 因导入刷新）、`backend/app/importing/`、`backend/app/api/`、`backend/app/review/`、`backend/app/report/`、`data/`、`frontend/`、`docs/diagrams/`、`.env`、`backend/requirements.txt`、`compose.yaml`。

## v0.7.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/review/test_demo_conflicts.py -q
退出码：0
末行：13 passed in 0.04s
未完成：无

补充说明：

- 先写测试、后写实现：首跑为 `ImportError: cannot import name 'samples' from 'backend.app.review'`，退出码 2；实现补齐后 13 passed、退出码 0。
- 三篇演示稿写成完整可读的自建稿（摘要 / 假设 / 建模 / 求解 / 结果 / 检验 / 参考文献），每篇开头明确标注是本项目自建的演示样例、不是官方答案也不是真实参赛论文。必含事实分散在不同位置：板凳龙摘要「412 s」在偏移 175、结果表「386 s」在偏移 699，假设一节写「忽略板凳宽度」，全文不讨论两段圆弧相切与半径倍数；种植摘要「1286 万元」在偏移 182、汇总表「974 万元」在偏移 683，全文没有豆类三年内至少一次，只给滞销 result1_1；烟幕摘要「22.4 s」在偏移 159、正文「18.6 s」在偏移 549，正文引用 [12] 而参考文献只列 [1]～[3]，无人机速度 160 m/s。
- 审查实现：`check_numbers_citations_ranges(text, constraints)` 汇总数字冲突、引用缺失与三类已注册检查（`mention` / `numeric_range` / `required_case`，放在 `REGISTERED_CHECKS` 里按 `check_type` 分派）。纯函数，不连库、不读文件、不发 HTTP、不调模型。每条结果含 `kind`、`constraint_id` 或 `indicator`、`evidence`（带字符偏移）、`message`；数字冲突必有两条以上偏移不同的证据。
- 三篇演示的实测结果（逐条）：板凳龙 2 条 = 数字冲突「盘入终止时刻」412 s / 386 s + 未提到条件「调头圆弧两段相切且半径 2 倍」（与 §4.7 一致）；种植 3 条 = 数字冲突「七年总收益」1286 万元 / 974 万元 + 未提到条件「每块地三年内至少种植一次豆类」+ 缺少情形「50%降价 / result1_2」；烟幕 3 条 = 数字冲突「有效遮蔽时长」22.4 s / 18.6 s + 引用缺失 [12] + 越界 160 m/s（约束「无人机速度范围为 70～140 m/s」）。**反向断言成立**：导弹速度 300 m/s 不报越界，题目给定的 1.5 s / 3.6 s / 20 s 不报冲突。
- 两个误报陷阱的处理方式：数字冲突按「单位 + 指标名」归组，指标名取数字前紧邻、且不越过前一处数值的那段文字，去掉数字单位括号与通用连接词后的结果，两处需单位相同且指标名互为前缀 / 后缀；越界按指标名匹配约束，指标上下文取自约束名里在正文出现过的最长前缀（≥3 字）。两处机制都写进 findings.md 的 Ruling。
- 实现过程中被测试抓到的两个真问题（都已修）：①第一版用「任意包含」判指标相同，短标签「起爆」落进「把起爆时刻提前」里面，把 20 s 与 0.5 s 并成一组；②指标窗口原来可以跨过前一处数值，导致「0.5 s 后……约 0.4 s」里后一处继承前一处的措辞，两处被并成一组。改成「互为前缀 / 后缀」并把窗口下界锁到前一处数值的末尾后，烟幕只剩 3 条应有结果。另有一处：`data/samples/eval/README.md` 没有同名 json，读入函数原来直接抛 `FileNotFoundError`，已改为按文件名前缀跳过。
- 12 篇评测论文：`data/samples/eval/eval-01.md`～`eval-12.md` 各配同名 `.json`（`paper_id`、`contest_id`、`title`、`gold`、`expected_findings`），每篇 `gold` 覆盖五个维度且档位在四档之内。读入函数 `load_eval_papers()` 放在 `backend/app/review/samples.py`，本版只做到能读入；档位一致率等对比计算按计划留到 v0.8.0，本版不做。目录说明 README 已按实际格式改写。
- 密钥无关性：把 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`EMBEDDING_MODEL` 四个变量显式置空后再跑本版测试，仍是 `13 passed`、退出码 0。
- 复核结果：单文件 `13 passed in 0.05s`、退出码 0；全量 `104 passed in 4.05s`、退出码 0（91 + 13，没有把旧用例改坏）。
- 本版不在出图范围，`docs/diagrams/` 未改动（五张图仍是 v0.1.0～v0.4.0 交付的版本）。
- 未改动：`backend/app/graph/`、`backend/app/scoring/`、`backend/app/retrieve/`、`backend/app/importing/`、`backend/app/api/`、`backend/app/llm/`、`backend/app/report/`、`backend/tests/` 下除 review 以外的文件、`data/contests/`、`frontend/`、`docs/diagrams/`、`CLAUDE.md`、`compose.yaml`、`.env.example`、`backend/requirements.txt`、`.env`。

## v0.8.0
状态：通过
命令：& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/report/test_report_and_eval.py -q
退出码：0
末行：13 passed in 1.88s
未完成：无

补充说明：

**(a) 三项指标的实际数字与分母**

语料片数 **15**（三篇演示稿 + 12 篇评测论文）；有 gold 的**可算样本 12 篇 / 60 个维度项**；三篇演示稿没有 gold，返回体里用 `demo_papers_without_gold: 3` 单列。三项指标按**可算样本**计算：

| 指标 | 实测 | 分母口径 |
|---|---|---|
| 档位一致率 | **26 / 60 = 0.4333** | 系统档位与 gold 档位一致的维度数 / 有 gold 的维度总数（60） |
| 引用精确匹配率 | **60 / 60 = 1.0** | 原句逐字出现在所引父块里的维度数 / 给出原句的维度数（60） |
| 证据不足命中情况 | **0 / 2 = 0.0** | gold 为证据不足且系统也判证据不足的维度数 / gold 为证据不足的维度数（**2**，不是 0） |

**(b) 这批数字的来源**

`source = deterministic`：`.env` 的四个模型键全为空，本版**没有调用任何模型**，系统档位来自**确定性结构回退**（按量规的 `section_types` 找对应章节，有非空正文就给「基本」并抄一句原话，没有就判「证据不足」）。**这不是模型准确率，是脚本自检**：它只能证明「读入语料 → 逐维出档位 → 与原句比对 → 汇总三项指标」这条链路与三项口径是通的。要模型数字得注入 `chat`（`run_eval(chat=...)` 会把 chat 传给状态图走真实选档，返回 `source="model"`；本版测试用一个假 chat 验过这条路径，确认来源标记会切换）。代码里没有写死任何目标准确率，指标只做输出、不做断言。

**(c) 口径说明**

- 档位一致率：逐维比对 `dimension_code` 上的系统档位与 gold 档位，完全相等才计一致；分母 60 = 12 篇 × 5 维。
- 引用精确匹配率：只统计系统**给出了原句**的维度；原句必须逐字出现在它引用的父块正文里（回退路径里父块就是该维对应章节的正文，所以 60/60；这条指标在回退下必然接近满分，正说明它是链路自检而不是效果指标）。
- 证据不足命中情况：只看 gold 判「证据不足」的维度（共 2 个，都在 `constraint_check` 维），系统也判「证据不足」才算命中；回退路径一条都没判出来 → 0/2。这三篇演示稿与 12 篇评测样本都不含奖项字样。

其余：

- 先写测试、后写实现：首跑为 `ImportError: cannot import name 'change_list' from 'backend.app.report'`，退出码 2；实现补齐后 13 passed、退出码 0。
- 修改清单 `build_change_list(dimension_results, findings, dimensions=None)`：只转写已校验的维度档位与审查结果，顺序固定为「题目约束与数字冲突 → 证据不足 → 表述」；每条带上游 id（维度类 `dimension:<code>`、审查类 `finding:<kind>:<constraint_id 或 indicator>`）、类型、目标、当前证据与修改动作。用例验证：第一条属题目约束或数字冲突、证据不足在中间、表述在最后、没有上游 id 的条数为 0、删掉一条上游 finding 后对应建议消失、删掉某维结果后该维相关建议消失。`引用失败` 的维度不进清单（三段顺序里没有它的位置），已在模块文档里写明。
- 奖项字样：报告文本与四个接口响应都用 `一等奖|二等奖|三等奖|获奖概率|获奖|名次` 正则筛过，全部不匹配。
- 评审记录：`review`、`review_dimension` 两张表用 report 自己的 `ReportBase` 建在 `paper_review` 里（现共 10 张表；赛题七张表与 `paper_parent` 未被触碰，行数不变），字段按计划书 §7.2。旧记录一律不回写：同一 `review_id` 再次保存时，赛题编号、量规版本、模型名、创建时间与当时各维原句 / 切片编号都保持原样（用例覆盖）。
- 新增三条只读接口：`GET /api/samples?is_demo=`（15 条，`is_demo=true` 恰好 3 条）、`GET /api/eval/summary`、`GET /api/reviews/{review_id}`（不存在返回 404）。原有六条路径的行为未改动。
- 复核结果：单文件 `13 passed in 2.52s`、退出码 0；全量 `117 passed in 4.72s`、退出码 0（104 + 13，没有把旧用例改坏）。
- 本版不在出图范围，`docs/diagrams/` 未改动。
- 未改动：`backend/app/graph/`、`backend/app/scoring/`、`backend/app/review/`、`backend/app/retrieve/`、`backend/app/importing/`、`backend/app/llm/`、`backend/tests/` 下除 report 以外的文件、`data/`（含 samples 与 contests）、`frontend/`、`docs/diagrams/`、`CLAUDE.md`、`compose.yaml`、`.env.example`、`backend/requirements.txt`、`.env`。
