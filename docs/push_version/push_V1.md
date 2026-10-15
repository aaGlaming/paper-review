# paper-review 第一版（push_V1）完整说明

> **文档用途**：作为首次推送 GitHub 之前的版本档案，供后续开发开始前先行阅读。
> **生成时间**：2026-10-15 20:35
> **代码目录**：`D:\LEARN\AI\programs\AgentTask\Projects\paper-review`
> **代码仓库**：https://github.com/aaGlaming/paper-review
> **解释器**：`D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe`（Python 3.11.16）
> **质量基线**：`pytest backend/tests -q` → **117 passed**，退出码 0
> **事实来源**：本文件所有结论均为实测（pytest 实跑、TestClient 实捕获、SQL 实查、grep 实查）；未使用推测值。

---

## 1. 版本概述与目标

### 1.1 项目定位

一个面向数学建模竞赛参赛学生与指导教师的**论文预审平台**。它不靠大模型通读一遍就给评价，而是按**已发布的评分量规**逐维去论文里找证据，把分数钉在**量规条款**与**论文原句**上；证据不够就写「证据不足」，原句对不上就写「引用失败」，这两类都**不进入加权**。

五个智能体分工：解析 → 赛题对齐 → 分项取证评分 → 一致性审查 → 修改报告。**分数加总、数字对比、引用是否存在、原句是否为子串，全部由确定性代码完成；模型只负责在给定证据里选档。**

### 1.2 首期边界（明确不做）

| 边界 | 说明 |
|---|---|
| 身份 | 赛前预审与教学演示工具，**不是**全国评阅系统 |
| 输出 | **不输出**奖项、名次、获奖概率 |
| 论文来源 | **不收录**优秀论文原文；样例全部项目自建 |
| 代码 | 评分、审查、报告的源码**不按题号写分支**，差异只放 `constraint` 与 `rubric` 数据 |
| 模型 | 只走 OpenAI 兼容的 Chat Completions 与 Embeddings；**不接本地模型运行时**，不使用 Assistants / Responses / 厂商私有字段 |
| 权限 | 不做多用户权限与学校组织架构 |

### 1.3 本版覆盖范围

本版包含 **8 个里程碑 + 1 次补丁**，对应执行手册阶段 P0～P7：

| 里程碑 | 阶段 | 内容 | 状态 |
|---|---|---|---|
| v0.1.0 | P0 地基 | 云端模型客户端契约、环境样例、项目说明 | ✅ 通过 |
| v0.2.0 | P1 解析暂停 | 章节确认与检查点 | ✅ 通过 |
| v0.3.0 | P2 赛题数据 | 赛题数据包导入与生命周期 | ✅ 通过 |
| v0.4.0 | P3 父子块检索 | 元数据过滤 + 父块回取 | ✅ 通过 |
| v0.5.0 | P4 重排与再检索 | 三路合并、4 段上限、两轮收敛 | ✅ 通过（**经 v0.5.1 补丁收口**） |
| v0.6.0 | P5 选档与加总 | 选档、原句子串校验、加权合计 | ✅ 通过 |
| v0.7.0 | P6 规则审查 | 数字冲突、引用、越界、情形缺失 + 三篇演示稿 | ✅ 通过 |
| v0.8.0 | P7 报告与评测 | 修改清单、评审持久化、评测三项指标 | ✅ 通过 |

**尚未包含**：P8（五个 Vue 页面）与 v1.0.0（首期总验收）。

### 1.4 交付形态

| 层 | 现状 |
|---|---|
| 后端 | **可运行**：FastAPI + MySQL 8.4 + Chroma 1.5.9，9 条 REST 路径 |
| 前端 | **未开始**：`frontend/` 下 5 个 `.vue` + 1 个 `index.js` 均为 5～6 行注释壳，`package.json` **无任何依赖** |
| 容器 | `compose.yaml` 四个服务名为空壳 `{}`，无可运行配置 |

### 1.5 两套版本号（勿混用）

| 体系 | 范围 | 用途 |
|---|---|---|
| **里程碑版本** | `v0.1.0` ～ `v1.0.0` | 项目做到哪一步（本文档 §1.3 用的就是这套） |
| **文档版本** | `v1.x.y` | 提示词文档自身：第二位对齐执行手册阶段号（从 P0 的 `0` 起算），第三位是同阶段内修订次数 |

两者**不得互相推导**。规范原文见 `docs/version/v1.0.1_命名规范.md`。

### 1.6 推送前必读：当前尚未初始化 Git 仓库

实测 `git rev-parse --is-inside-work-tree` → **不是 git 仓库**（尚未 `git init`）。推送前需要：

1. `git init` 并关联远端 `https://github.com/aaGlaming/paper-review`；
2. 确认 `.env` **未**被纳入版本控制（`.gitignore` 第 1 行已是 `.env`）；
3. 清理 `.pytest_cache/` 与仓库根的 `zz-commit.json`（见 §5.9）。

---

## 2. 已实现的功能模块及其说明

源码共 **29 个 Python 文件**，按 8 个模块组织。每个模块都对上层只暴露 `__init__.py` 中 `__all__` 声明的名字。

### 2.1 `backend/app/llm` — 模型客户端（P0）

| 项 | 内容 |
|---|---|
| 文件 | `client.py`（137 行） |
| 职责 | **全项目唯一的 HTTP 出口**。只使用 `httpx`，不引入厂商 SDK |
| 公开 API | `chat(messages, temperature=0.2, *, transport=None) -> str`<br>`embed(texts, *, transport=None) -> list[list[float]]`<br>异常：`LLMConfigError`、`LLMResponseError` |
| 关键约束 | 对话只走 `POST {LLM_BASE_URL}/chat/completions`，**只读** `choices[0].message.content`；嵌入只走 `POST {LLM_BASE_URL}/embeddings`，**只读** `data[].embedding`；响应结构不符时抛错，**绝不返回空字符串冒充结果** |
| 配置 | 只从环境变量读 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `EMBEDDING_MODEL`；`transport` 参数供测试注入 `httpx.MockTransport`，**测试全程不访问网络** |
| 客户端内部 | 超时 30s；**网络层**异常最多重试 1 次；密钥不打印、不回显、不落盘 |

> 注意：「JSON 解析失败重试一次」**不属于**客户端，那是调用方（选档）的职责，见 §3.4。

### 2.2 `backend/app/graph` — 预审状态图（P1 / P4 / P5）

| 项 | 内容 |
|---|---|
| 文件 | `review_graph.py`（537 行） |
| 职责 | LangGraph 状态图编排。节点固定顺序 `parse → confirm → retrieve → score → END` |
| 公开 API | `build_review_graph(checkpointer=None, *, retriever=None, dimensions=None, chat=None, rubric_dimensions=None, constraints=None)`<br>`create_review(paper_text, review_id=None, *, graph=None) -> str`<br>`resume_review(review_id, sections, *, graph=None) -> dict`<br>`default_retriever(request)`<br>常量：`REVIEW_STATUSES`、`SECTION_TYPES`、`UNCLASSIFIED_SECTION_TYPE`<br>异常：`EmptyPaperError` |
| 状态 | `ReviewState`：`review_id`、`paper_text`、`sections`、`confirmed`、`status`、`score_node_calls`、`parse_node_calls`、`contest_id`、`rubric_id`、`retrieve_section_types`、`retrievals`、`retrieve_node_calls`、`constraints`、`dimension_results`、`score` |
| 状态词表 | **恰为五个**：草稿解析 / 待确认 / 评分中 / 完成 / 失败。不得出现「已获奖」之类 |
| 章节类型 | **恰为六个**：假设 / 模型 / 求解 / 结果 / 检验 / 参考文献；切不出类型的标题归「未分类」，**不新造第七类** |
| 人机回环 | `confirm` 节点调用 `interrupt()` 交出章节树；`Command(resume=...)` 给回的章节类型**原样采用，不重新解析** |
| 检查点 | `InMemorySaver`，`thread_id` 取 `review_id`。**仅进程内有效，重启即丢**（见 §5.3） |
| 依赖注入 | 检索器 `retriever` 与模型 `chat` **一律从外部注入**；本模块不导入模型客户端、源码不含 HTTP 字样 |

### 2.3 `backend/app/importing` — 赛题数据入口（P2）

| 项 | 内容 |
|---|---|
| 文件 | `catalog.py`（690 行）、`models.py`（110 行）、`db.py`（75 行）、`__init__.py`（42 行） |
| 职责 | 读 `data/contests/{contest_id}/` 下五个 JSON，整包校验后写库；提供发布、归档、复制下一版量规、发布量规、列表 |
| 公开 API | `import_package(package_dir, *, session=None)`、`publish_contest`、`archive_contest`、`copy_rubric_as_draft`、`publish_rubric`、`list_contests(include_archived=False, include_drafts=False, *, session=None)`、`validate_package`<br>`create_schema()`、`get_dsn()`、`get_engine()`、`session_scope()`<br>常量：`DIMENSION_CODES`、`BAND_NAMES`、`CHECK_TYPES`、`SCORED_BANDS`、`INSUFFICIENT_BAND`、`WEIGHT_TOTAL`<br>异常：`PackageError`、`CatalogError`、`CatalogStateError` |
| 整包拒绝条件 | `contest.json` 缺必填字段；任一维权重之和 ≠ 100；`check_type` 不在三种之内；四档不全或「证据不足」被填了分数；`dimension_code` 不在五个允许值内；`exemplar.band` 取了「证据不足」。**任一不满足即整包拒绝，且不部分写入** |
| 表 | 赛题七张：`contest`、`constraint`、`rubric_template`、`rubric`、`dimension`、`pitfall`、`exemplar` |
| 连接 | 连接串**只从环境变量** `MYSQL_DSN` 读；建表用 `metadata.create_all()`，**不引入 alembic**（不在锁定依赖内） |
| 无题号分支 | 源码内无 `cumcm-*` 字面量比较，测试用 AST 断言过 |

### 2.4 `backend/app/api` — 接入层（P2 / P7）

| 项 | 内容 |
|---|---|
| 文件 | `routes.py`（135 行）、`app.py`（20 行） |
| 职责 | FastAPI 路由，前缀 `/api`，共 **9 条路径** |
| 公开 API | `create_app() -> FastAPI`、模块级 `app`、`router`、`get_session()` 依赖 |
| 路径清单 | `GET /api/contests`、`POST /api/imports`、`POST /api/contests/{contest_id}/publish`、`.../archive`、`.../rubrics`、`POST /api/rubrics/{rubric_id}/publish`、`GET /api/samples`、`GET /api/eval/summary`、`GET /api/reviews/{review_id}` |
| 导入路径 | **固定 `POST /api/imports`**。开发计划书写的 `/api/catalog/imports` 已被裁决弃用；实测该旧路径返回 404 |
| 错误映射 | 坏包 → 400 且带 `filename` / `field`；业务不存在 → 404；量规状态冲突 → 409；参数校验 → 422（FastAPI 默认） |
| 建表 | 应用启动**不会**隐式改库；建表由三个 `create_*_schema()` 显式调用 |

### 2.5 `backend/app/retrieve` — 检索工具层（P3 / P4）

| 项 | 内容 |
|---|---|
| 文件 | `parent_child.py`（491 行）、`three_route.py`（179 行）、`rerank.py`（84 行）、`models.py`（38 行）、`__init__.py`（100 行） |
| 职责 | 先按元数据过滤子块，再按 `parent_id` 取回 MySQL 父块；三路合并、上限截断、两轮收敛 |
| 核心 API | `search_children_then_parents(...)`、`index_children(...)`、`save_parents` / `get_parents`、`build_children` / `split_into_chunks` / `child_metadata`、`retrieve_dimension(...)`、`merge_candidates`、`create_parent_schema()` |
| 重排 | `RerankClient`（协议）、`FakeRerankClient`（把顺序倒过来）、`build_rerank_client`、`read_rerank_config`、`validate_rerank_order`。**本版只发假客户端，不发 HTTP** |
| 关键常量 | `MAX_PARENTS = 4`、`MAX_ROUNDS = 2`、`PER_ROUTE_LIMIT = 6`、`ROUTES = (band_text, paper_child, pitfall)`、`STATUS_HIT = "命中"`、`STATUS_INSUFFICIENT = "证据不足"` |
| `doc_type` 白名单 | **恰为五个**：`paper_child`、`band_text`、`pitfall`、`exemplar`、`contest_statement`。越界抛 `DocTypeError` |
| 父块存储 | `paper_parent` 表（`ParentBase` + `create_parent_schema()`），全文**只在 MySQL**，不进 Chroma |

### 2.6 `backend/app/scoring` — 选档与加总（P5）

| 项 | 内容 |
|---|---|
| 文件 | `selection.py`（174 行）、`aggregate.py`（110 行）、`__init__.py`（60 行） |
| 职责 | 模型 JSON 解析与字段白名单、原句子串校验、确定性降档守卫、加权合计 |
| 公开 API | `parse_scoring_json(raw) -> {'band','chunk_id','quote'}`、`quote_is_substring`、`join_evidence`、`apply_mention_guard`、`build_scoring_messages`<br>`weighted_sum(dimensions, dimension_results)`、`weight_table`、`dimension_code_of`<br>常量：`JSON_FIELDS`、`MAX_CHAT_ATTEMPTS`、`SCORING_TEMPERATURE`、`WEIGHTED_BANDS`、`STATUS_CITATION_FAILURE`、`STATUS_INSUFFICIENT`、`STATUS_FAILURE`、`REASON_*` |
| 三条「不进入加权」的状态 | 检索为空 → **证据不足**；模型给的 `quote` 对不上父块 → **引用失败**；JSON 两次都解析失败 → **失败**。三者**严格区分、不得混用** |
| 权重来源 | **只读量规数据**（由调用方传入的 `dimensions`）。模型返回里若带 `weight` 或 `score`，**一律忽略且不报错** |
| 本模块不做的 | 不连数据库、不发 HTTP、不读文件 |

### 2.7 `backend/app/review` — 规则审查（P6）

| 项 | 内容 |
|---|---|
| 文件 | `consistency.py`（417 行）、`samples.py`（69 行）、`__init__.py`（60 行） |
| 职责 | 数字一致性、引用存在性、越界，以及三种已注册检查（`mention` / `numeric_range` / `required_case`） |
| 核心 API | `check_numbers_citations_ranges(text, constraints) -> list[dict]`（汇总入口）<br>`check_number_conflicts`、`check_citations`、`check_mention`、`check_numeric_range`、`check_required_case`、`REGISTERED_CHECKS`<br>`load_demo_text` / `load_demo_texts` / `load_eval_papers`、`DEMO_FILES` |
| 五类 `kind` | 数字冲突、越界、未提到条件、缺少情形、引用缺失 |
| 每条结果结构 | `kind`、`constraint_id` 或 `indicator`、`evidence`（含 `char_start` / `char_end` / `text`）、`message`。数字冲突类必有**两条以上、偏移不同**的证据 |
| 数据驱动 | 消费 v0.3.0 冻结的 `constraints.json` 结构：`mention → params.keywords`；`numeric_range → params.min/max/unit`；`required_case → params.label/artifact` |
| 本模块不做的 | 不连数据库、不读向量库、不发 HTTP、不调模型；文本与约束由调用方传入 |

### 2.8 `backend/app/report` — 报告与评测（P7）

| 项 | 内容 |
|---|---|
| 文件 | `evaluation.py`（307 行）、`change_list.py`（193 行）、`store.py`（141 行）、`models.py`（60 行）、`catalog.py`（48 行）、`__init__.py`（63 行） |
| 职责 | 把已校验的档位与审查结果转成修改清单；评审记录持久化；评测三项指标 |
| 修改清单 API | `build_change_list(dimension_results, findings, dimensions=None)`、`render_change_list`、`contains_award_words`<br>常量：`AWARD_WORDS = ("一等奖","二等奖","三等奖","获奖概率","获奖","名次")`、`SECTION_ORDER`、`KIND_CONSTRAINT`、`KIND_INSUFFICIENT`、`KIND_NUMBER_CONFLICT`、`KIND_PRESENTATION` |
| 清单排序 | 固定为**第一段**题目约束与数字冲突 → **第二段**证据不足 → **第三段**表述。每条带上游 id；**删掉上游记录后对应建议必须消失** |
| 评审持久化 | `save_review` / `load_review`；表 `review`、`review_dimension`（`ReportBase` + `create_report_schema()`）。**同一 `review_id` 再次保存不回写**，改记录只能换新 id |
| 评测 API | `summarize_eval(pairs)`（纯计算）、`run_eval(chat=None, ...)`、`deterministic_results`、`SOURCE_DETERMINISTIC`、`SOURCE_MODEL`、`list_samples` |
| 本模块不做的 | 不发 HTTP、不导入模型客户端、不按题号写分支 |

### 2.9 数据资产

| 资产 | 位置 | 数量 | 说明 |
|---|---|---|---|
| 赛题数据包 | `data/contests/{contest_id}/` | **4 题 × 5 文件 = 20 个 JSON** | `cumcm-2024-A`（板凳龙）、`cumcm-2024-C`（农作物种植）、`cumcm-2025-A`（烟幕干扰弹）、`fixture-extra`（自建导入夹具） |
| 演示稿 | `data/samples/*.md` | **3 篇** | `bench-dragon.md`、`planting.md`、`smoke.md`。每篇开头声明「本项目自建的演示样例，不是官方答案，也不是真实参赛论文」 |
| 评测样例 | `data/samples/eval/` | **12 篇 md + 12 篇同名 json** | 每篇 `json` 含 `paper_id`、`contest_id`、`title`、`gold`（五维档位）、`expected_findings` |
| archify 图 | `docs/diagrams/` | **5 张 × (json + html)** | `runtime.architecture`、`review.workflow`、`review.lifecycle`、`retrieve.sequence`、`chunks.dataflow`；HTML 约 0.81～0.83 MB |

`gold` 档位分布（12 篇共 **60 个维度项**）：充分 20 / 基本 26 / 不足 12 / **证据不足 2**。

### 2.10 测试资产

`backend/tests/` 共 **8 个文件，全部有实现**，全量为 **117 项、117 通过**：

| 测试文件 | 行数 | 用例数 | 对应模块 |
|---|---|---|---|
| `llm/test_client.py` | 270 | 22 | `llm` |
| `graph/test_interrupt.py` | 261 | 11 | `graph` |
| `importing/test_catalog.py` | 416 | 14 | `importing` + `api` |
| `retrieve/test_parent_child.py` | 536 | 14 | `retrieve` |
| `retrieve/test_rerank_cap.py` | 481 | 13 | `retrieve` + `graph` |
| `scoring/test_quote_and_weight.py` | 504 | 17 | `scoring` + `graph` |
| `review/test_demo_conflicts.py` | 306 | 13 | `review` |
| `report/test_report_and_eval.py` | 421 | 13 | `report` + `api` |

### 2.11 开发过程档案

| 文件 | 内容 |
|---|---|
| `docs/plan/task_plan.md` | 10 个里程碑的状态表（v0.1.0～v0.8.0 已通过） |
| `docs/plan/progress.md` | 205 行 / 9 节：每版的命令、退出码、pytest 末行与补充说明。**含 v0.5.0 的失败史**，未粉饰 |
| `docs/plan/findings.md` | 50 行 / **21 条 Ruling**，格式 `决定 — 原因 — 做错的代价` |
| `docs/开发任务拆解与迭代流程.md` | 708 行，首期拆成 10 个版本，冻结解释器与导入路径 |
| `docs/version/v1.0.1_命名规范.md` | 版本化文档命名规范 |
| `docs/version/10.15/v1.0.0`～`v1.7.0`（9 份） | 各阶段的 vibe coding 提示词，含实测结论与设计理由 |
| `docs/version/explain/项目进度报告V1.md`、`V2.md` | 两个时点的全量进度快照 |

---

## 3. 关键实现细节与设计决策

### 3.1 三条不可协商的硬约束

| 约束 | 落地位置 | 为什么 |
|---|---|---|
| **引用必须是切片中的连续子串** | `selection.quote_is_substring` | 模型最容易编造原句。对不上则该维「引用失败」，不加权。逐字匹配，不做分词、不做相似度 |
| **证据不足不换算成分数** | `aggregate.weighted_sum` | 把「没找到」折成一个看起来精确的低分，等于把缺项伪装成结论。证据不足单列，不进合计 |
| **不输出奖项、名次、获奖概率** | `change_list.AWARD_WORDS` + 正则用例 | 系统是预审工具不是评奖系统。报告文本与接口 JSON 一律拒绝这六个词 |

### 3.2 可注入契约（本项目最重要的架构约定）

`build_review_graph` 的**检索器**与**模型**一律从外部注入：

```python
build_review_graph(retriever=..., chat=..., rubric_dimensions=..., constraints=...)
```

- 模块内**不得**导入 `backend/app/llm/client.py`，源码里不得出现 `httpx` / `requests` / `urllib` / `aiohttp` 字样；
- **未注入时保持占位/记账行为，绝不报失败**——未注入 `retriever` 时每维记「证据不足」，未注入 `chat` 时评分节点只累加 `score_node_calls` 并记「完成」。

这不是洁癖。`backend/tests/graph/test_interrupt.py` 断言「未注入时 `status == "完成"`、`score_node_calls == 1`、二次 resume 不重算」，而该文件**在多个版本中都不在允许修改范围内**。若把缺省行为改成「报失败」，这些用例会立刻变红却无权修改——**契约必须迁就既有闸门**。

好处同样直接：全部选档测试可以离线跑，不需要任何密钥。

### 3.3 父子块与向量库边界

| 决策 | 内容 |
|---|---|
| Chroma 只存子块 | `doc_type` 五值白名单；父块全文**只在 MySQL**，用 `parent_id` 关联 |
| 送入模型的是父块 | 子块用于检索命中，父块用于给模型看——避免断章取义 |
| 过滤先于排序 | 先用 `contest_id`、`rubric_id`、`section_type` 过滤，再做重排。**重排只改顺序，加不回被过滤掉的片段**（`validate_rerank_order` 会抛错） |
| 每维上限 | 三路（档位说明 / 论文子块 / 扣分点）**各自召回 → 合并去重 → 一次重排 → 截断到总共 4 段**。不是每路 4 段 |
| 两轮上限 | 第一轮有结果不再查；第一轮为空才允许第二轮；两轮都空 → 该维「证据不足」，调用次数**恰为 2** |

**本机实测的两个 Chroma 1.5.9 坑（已在实现中规避，但需记住）：**

1. **数组型元数据能写入、读回也是 `list`，但用 `$in` 过滤会静默返回空且不报错。** 因此子块元数据的 `section_type` 必须是**单值字符串**，过滤走 `{"section_type": {"$in": [...]}}`。这是「数据进去了、永远搜不到、还不报错」的静默失败。
2. **Chroma 不校验 `doc_type` 白名单**——把 `paper_parent` 写进去它照样接受。白名单只能由代码自己拦。

另：Chroma 默认 EmbeddingFunction 会**下载 ONNX 模型**。测试一律注入自定义假 EF 并显式传向量，保证完全离线。

### 3.4 选档的三态与重试上界

| 输入 | 结果状态 | 是否加权 |
|---|---|---|
| 检索为空 | 证据不足 | ❌ |
| 模型给的 `quote` 不是父块连续子串 | **引用失败** | ❌ |
| JSON 两次都解析失败 | **失败** | ❌ |
| `band` ∈ {充分, 基本, 不足} 且子串匹配 | 正常档位 | ✅ |

- 模型 JSON **只采纳三个字段**：`band`、`chunk_id`、`quote`；带 `weight` / `score` 一律忽略且不报错；
- JSON 解析失败**重试一次**（再调一次 `chat`），总调用次数**恰为 2**；
- 模型**不改权重**，加总只读量规数据。

### 3.5 加权口径（容易被误读，特别说明）

`weighted_sum().total` 定义为**进入合计的维度权重之和**，**不是分数**：

- 不引入任何档位系数，「充分 / 基本 / 不足」对 `total` 的贡献相同；
- 档位只用于**单列与展示**；另有 `rubric_weight_sum` 作为分母；
- 被排除的维度连同原因进 `excluded`。

这么定是为了不与「分数由量规决定」这条原则打架——本版还没有把档位映射成分数的机制。

### 3.6 规则审查的「指标辨识」与「宁漏不误」

数字冲突**按「单位 + 指标名」归组**，越界**按「指标名」匹配约束**，都**不是**按单位：

- 指标名 = 数字前紧邻、**且不越过前一处数值**的那段文字（在标点或换行处断开），去掉数字、单位、括号与通用连接词后的结果；
- 两处需单位相同**且**指标名相同或**互为前缀 / 后缀**才算同一指标；
- 越界的指标上下文取自约束名里在正文出现过的最长前缀（≥3 字），**完全由约束数据驱动**。

**为什么不能按单位：** 烟幕演示稿里 1.5 s / 3.6 s / 20 s / 22.4 s / 18.6 s **全是秒**，只按单位归组会把合法的前三者报成冲突；无人机速度约束的 `unit` 是 `m/s`，而正文里导弹速度 300 m/s 同为 `m/s`，只按单位匹配会把 300 m/s 误报越界。正向验收全绿、质量全废——**这类「假阳性」比漏报更危险**。

**主动接受的代价：宁漏不误。** 同一指标的两处若措辞完全不同、或相距超过 24 字符且中间无标点，会**漏报**。

两处判据细节都是**被测试逼出来的**（已写入 Ruling，防后人改回去）：① 用「互为前缀/后缀」而非「任意包含」——否则短标签「起爆」会落进「把起爆时刻提前」里，把 20 s 与 0.5 s 并成同一指标；② 指标窗口不越过前一处数值——否则「提前 0.5 s 后……约 0.4 s」会把两处并组。

### 3.7 评测口径与来源标注

三项指标的可计算定义（分母均按**有 gold 的可算样本**）：

| 指标 | 分子 / 分母 | 实测值 |
|---|---|---|
| 档位一致率 | 一致维度数 / 有 gold 的维度总数（60） | 26 / 60 = 0.4333 |
| 引用精确匹配率 | `quote` 逐字命中的维度数 / 给出 `quote` 的维度数 | 60 / 60 = 1.0 |
| 证据不足命中情况 | 系统也判「证据不足」的数量 / gold 为「证据不足」的维度数（**2**） | 0 / 2 = 0.0 |

响应里**同时**给出 `corpus_papers: 15`（语料规模）与 `gradable_papers: 12` / `gradable_dimensions: 60` / `demo_papers_without_gold: 3`，每个指标带 `caliber` 字段写明口径。

**来源标注**：`.env` 的四个模型键全空，故 `source = "deterministic"`——系统档位来自**确定性结构回退**，响应体自带说明「这些数字是脚本自检，**不是模型准确率**」。**代码里没有写死任何目标准确率**；指标只做输出，不做断言。

> 注意：引用精确匹配率在回退路径下必然是 60/60，因为它比对的正是回退自己抄的那句原话。**这条在回退下是链路自检，不是效果指标。**

### 3.8 模块边界与「建表无处安放」的统一解法

P3、P7 两次遇到同一问题：**需要的表不属于本版允许修改的模块**。

统一解法（已成先例）：

```
在允许修改的模块内建独立 Base（ParentBase / ReportBase）
  + 自己的 create_*_schema()
  + 只读导入 importing/db.py 的引擎与会话工厂复用连接
  + 不得修改 importing/
```

于是三处 metadata 各自独立：赛题七张表（`importing`）、`paper_parent`（`retrieve`）、`review` + `review_dimension`（`report`）。

### 3.9 HTTP 出口与重排的处置

项目硬约束是「全项目只有 `backend/app/llm/client.py` 可以发 HTTP」，而 P4 需要重排 HTTP 客户端，其允许修改范围却不含该文件。处置：**本版只做重排的接口 + 假客户端**（`FakeRerankClient` 把顺序倒过来），从环境变量读 `RERANK_BASE_URL` / `RERANK_MODEL` 当配置项，**一个 HTTP 请求都不发**；真实实现留到允许改 `client.py` 的版本。`build_rerank_client("http")` 现在显式抛 `NotImplementedError`——**把越界写成可见的失败，而不是静默实现**。

### 3.10 21 条 Ruling 索引

裁决全部记录在 `docs/plan/findings.md`，按版本分布：v0.1.0(4)、v0.3.0(3)、v0.4.0(2)、v0.5.0(2)、v0.5.1(1)、v0.6.0(3)、v0.7.0(3)、v0.8.0(3)。按主题归类：

| 主题 | 关键裁决 |
|---|---|
| 环境与依赖 | 解释器统一用 `env\agent-task\Scripts\python.exe`（执行手册写的 `env\Scripts\...` 本机不存在）；PyMySQL 实装 2.2.8 与锁定 1.2.3 不一致，**只记录不改**（共享锁定文件，动了会波及同环境其他项目） |
| 文档与工具 | archify 产物在仓库外临时目录生成过门禁、再按字节复制入库（工作区内会留下硬链接导致原子发布失败）；图中每个节点标注实现它的版本 |
| 数据库 | 测试实连真实 MySQL，用「外层事务 + 保存点」隔离而非表名前缀；`constraint` 是 MySQL 保留字靠 SQLAlchemy 自动加反引号 |
| 模块边界 | `paper_parent` 放 `retrieve/models.py`；`review`/`review_dimension` 放 `report/models.py`；均只读复用 `importing/db.py` |
| 检索 | 测试用**真实 chromadb + 真实 MySQL**（sqlite 仅兜底），因为只有真向量库才能验证单值元数据 + `$in` 真的命中、父块正文确实没进 `document` 字段 |
| 注入契约 | 逐维检索用可注入检索器；`chat` 可注入且未注入时沿用占位；新增状态节点必须在 `create_review` 预置计数初值（测试保留严格取值，**不改为 `.get(key, 0)`**，否则计数器脱线也测不出来） |
| 选档 | 降档守卫做成纯函数 `apply_mention_guard()`，只读 `check_type = mention` 的约束；`total` 定义为权重之和，不引入档位系数 |
| 审查 | 数字冲突按「单位 + 指标名」、越界按「指标名」；判据两处细节由测试逼出；评测样例用「同名 md + json」并由 `load_eval_papers()` 跳过 `README.md` |
| 评测 | 分母按可算样本算、同时给出语料 15；未注入 `chat` 走确定性回退并标 `source`；评审两张表用独立 `ReportBase` 且旧记录不回写 |

---

## 4. 尚未完成的内容

### 4.1 整个 P8 阶段（前端）

- `frontend/` 五个 `.vue`（论文解析 / 分项评分 / 一致性审查 / 修改建议 / 评测对照）+ `src/api/index.js` **全部是 5～6 行注释壳**；
- `package.json` 只有 `name` / `private` / `description`，**没有任何依赖**（无 Vue、无 Vite、无 Element Plus）——P8 需要**从零搭前端工程**，这是本版剩余工作量最大的一块；
- 需求要求的交互均未实现：三篇演示的「填入示例」按钮、证据不足单独着色、点击审查结果滚动到字符偏移、评测页点进单篇。

### 4.2 总验收（v1.0.0）

需求第十二章的逐条验收尚未执行。

### 4.3 接口层缺口

| 缺口 | 影响 |
|---|---|
| `POST /api/reviews`（创建评审） | 前端无法发起预审；`review` 表因此为 0 行 |
| `POST /api/reviews/{review_id}/resume` | 引擎侧 `Command(resume)` 已通过测试，但**没有 HTTP 入口**，人工确认章节无法从接口层触发 |
| 文件上传 | `POST /api/imports` 只接受服务器本地路径字符串；上传论文未实现 |
| 无健康检查 | 没有 `/health`、`/readyz` |

### 4.4 赛题对齐尚未成为独立节点

状态图节点为 `parse → confirm → retrieve → score`，**没有独立的「对齐」节点**。三种 `check_type` 已被规则审查与选档降档守卫消费，但「判断论文对应哪道题、不一致就停止评分」这条流程未落到图里。

### 4.5 真实重排客户端

只实现了接口与假客户端，真实 HTTP 重排（读 `RERANK_BASE_URL` / `RERANK_MODEL`）未实现，需先授权修改 `backend/app/llm/client.py`。

### 4.6 三篇演示稿缺 `gold`

`data/samples/` 下三篇演示稿**只有 `.md`、没有同名 `json`**，因此评测可算样本只有 12 篇；而需求要求「对 15 篇给出三项指标」。补 `gold` 需要修改 `data/samples/`（不在 P7 允许范围）。

### 4.7 数据库尚未装载到验收要求的状态

| 表 | 当前行数 |
|---|---|
| `contest` | **1**（`cumcm-2024-A`，状态 **`draft`**） |
| `rubric` | 1（`cumcm-2024-A-v1`，`draft`） |
| `dimension` / `constraint` / `pitfall` / `exemplar` | 5 / 5 / 5 / 4 |
| `paper_parent` / `review` / `review_dimension` | 0 / 0 / 0 |

总验收要求「可以选择 2024 年 A 题、2024 年 C 题、2025 年 A 题」，即三道赛题应为 `published`。当前只导入了一道且仍是 `draft`——**属数据装载事项，不是代码缺陷，但会直接卡住 v1.0.0**。

### 4.8 Compose 可运行配置

`compose.yaml` 四个服务全为空壳 `{}`，镜像、端口、卷、健康检查都未写。

---

## 5. 已知问题与限制

### 5.1 无模型密钥，评测数字是脚本自检

`.env` 的 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `EMBEDDING_MODEL` **全为空**，`/api/eval/summary` 的 `source = "deterministic"`。三项指标来自确定性结构回退。**这些数字不能当作模型效果基线。** 要真实数字需注入 `chat`（`run_eval(chat=...)` 会返回 `source="model"`）。

### 5.2 可观测性基础设施为零

| 能力 | 状态 |
|---|---|
| 应用日志 | ❌ 全局 grep `import logging` / `logging.` / `logger` / `print(` → **0 处命中** |
| 访问日志 | 🟡 仅 `uvicorn` 自带（只有状态码与路径，**无耗时、无 `review_id` 关联**，进程重启即丢） |
| 监控 / 指标 | ❌ 无 Prometheus、无 `/metrics`、无 `Gauge`/`Counter`/`Histogram` |
| 链路追踪 | ❌ 无 OpenTelemetry、无 `trace_id`、无 span |
| 关联 ID | 🟡 `review_id` 由 `uuid4().hex` 生成，但**未进响应头、未进访问日志** |
| 健康检查 | ❌ 无 |
| 全局异常处理 | 🟡 无 `add_exception_handler`，靠逐路由 `try/except`；未捕获异常走默认 500 且**不落日志** |

执行手册第 23 节要求记录的「每维检索条数、重排前后顺序、引用校验结果、模型耗时」**全部未落地**。

### 5.3 章节检查点在进程内存，重启即丢

`InMemorySaver` 只活在进程内。执行手册要求「模型或重排不可用时，已确认的章节树仍可查看」——**该应急能力当前不成立**。

### 5.4 错误响应有三种体例

| 场景 | 结构 |
|---|---|
| 坏包 | `{"filename", "field", "detail"}` |
| 业务错误 | `{"detail": "…"}` |
| 参数校验 | `{"detail": [{…}]}` |

前端需分别处理。

### 5.5 接口文档版本号写死

`api/app.py` 里 `FastAPI(..., version="0.3.0")` 是字面量，实测 `/openapi.json` 的 `info.version` 仍为 `0.3.0`，与实际进度（v0.8.0）不符。

### 5.6 契约错位型 bug 已发生过一次

v0.5.0 首次验收失败：`create_review` 的初始状态字典预置了两个计数键、**漏了新增的 `retrieve_node_calls`**；图停在 `confirm` 时该键从未写入，严格取值抛 `KeyError`。**规律：新增状态节点必须同步在入口预置计数初值。** 已写入 Ruling。

### 5.7 依赖版本与锁定不一致

`backend/requirements.txt` 锁定 `PyMySQL==1.2.3`，而实际环境装的是 **2.2.8**。当前功能正常（已实测连通 MySQL 8.4.11），但**锁定值与实装值不符**，属于隐性风险。因 `requirements.txt` 是共享锁定文件（多项目共用同一环境），本版只记录不处理。

### 5.8 规则审查的漏报边界

「宁漏不误」的主动取舍：同一指标两处措辞完全不同、或相距超过 24 字符且中间无标点时会**漏报**。这是设计决策，不是缺陷，但使用者需知道。

### 5.9 仓库卫生问题

| 问题 | 说明 |
|---|---|
| `zz-commit.json` | 仓库根有一个 **1 字节、内容仅 `x`** 的文件（2026-10-15 13:54 生成），**未被 `.gitignore` 覆盖**，推送前应删除或忽略 |
| `.pytest_cache/` | 测试产生的缓存目录（已被 `.gitignore` 覆盖，不会入库） |
| `.env` | 含真实 MySQL 连接串（含密码）。**已被 `.gitignore` 第 1 行覆盖**，推送前务必确认未被 `git add -f` 之类操作带进去 |

### 5.10 其它限制

- **Markdown 是验收主路径**，PDF 解析不作为验收前置条件（`pypdf` / `python-docx` 虽在锁定依赖内，但本版未接入解析流程）；
- `llm/client.py` 的网络层重试上限为 1 次，**不区分** 4xx / 5xx（4xx 直接抛错），未实现指数退避；
- 评测与预审尚未打通：`GET /api/eval/summary` 用的是确定性回退或注入数据，**不是**从真实评审记录汇总。

---

## 6. 后续待改进和待开发的事项

### 6.1 推送前必须先做

| # | 事项 | 说明 |
|---|---|---|
| 1 | `git init` + 关联远端 | 当前不是 git 仓库 |
| 2 | 删除或忽略 `zz-commit.json` | 1 字节垃圾文件，未被 gitignore 覆盖 |
| 3 | 核对 `.env` 未入库 | 含真实密码；`.gitignore` 已覆盖，但推送前应再确认一次 |
| 4 | 确认 `.pytest_cache/` 未入库 | 已被 gitignore 覆盖 |
| 5 | 补一份面向使用者的 README | 目前只有 `CLAUDE.md`（项目约束），没有说明如何启动与验证 |

### 6.2 高优先级（P8 前 / 总验收前）

| 优先级 | 事项 | 落点 |
|---|---|---|
| 高 | 把 `review_id` 写进响应头与访问日志，让 HTTP 层能追到内部 | 摘要层中间件 |
| 高 | 章节检查点从 `InMemorySaver` 换成持久化（`review` / `review_dimension` 已在 MySQL） | `graph` + `report` |
| 高 | 加全局异常处理器，统一错误响应结构（消除现有三种体例） | `backend/app/api/` |
| 高 | 装载数据：导入三道公开赛题并 `publish`，使默认列表可见 | 数据操作 |
| 高 | 补 `POST /api/reviews` 与 `POST /api/reviews/{id}/resume`，让前端能发起并确认预审 | `backend/app/api/` |
| 高 | 清掉 `zz-commit.json`、补 README | 仓库根 |

### 6.3 中优先级

| 事项 | 说明 |
|---|---|
| 每维检索的结构化日志 | 记录维度、召回条数、`route_hits`、是否触发第二轮 |
| 模型耗时与重试次数记录 | 在 `llm/client.py` 内（**不得记录密钥**） |
| 加 `/health` 与 `compose.yaml` 可运行配置 | P8 前 |
| 把 `app.py` 里写死的 `version="0.3.0"` 改为随版本更新 | `backend/app/api/app.py` |
| 三篇演示稿补 `gold` | 使评测分母达到需求要求的 15 篇 |
| 真实重排 HTTP 客户端 | 需授权修改 `backend/app/llm/client.py` |
| 赛题对齐落成独立节点 | 「错题即停」这条流程目前只在数据层 |
| PyMySQL 版本锁定与实装对齐 | 需评估对同环境其他项目的影响 |

### 6.4 低优先级 / 二期候选

| 事项 | 说明 |
|---|---|
| 指标端点 `/metrics` 与链路追踪 | 运行期可观测性 |
| 注册新的 `check_type` | 首批只有 `mention` / `numeric_range` / `required_case` |
| 评测样本从 12 篇扩展 | 需求把 15 篇作为首期分母 |
| 导出带切片编号的预审记录 | 供教师对照 |
| 把 `%TEMP%` 下的 archify 交付回执复制进 `docs/diagrams/` | 随手可做，目前回执重启即失 |
| PDF 解析接入 | 目前 Markdown 是唯一验收主路径 |

### 6.5 需要人决策的事项

| 事项 | 背景 |
|---|---|
| 评测分母口径 | 需求 §12.4 要 15 篇，但三篇演示缺 `gold`；当前做法是「语料 15 + 可算 12」两个数都报 |
| 主数据上做发布/归档测试的副作用 | 会产生 `cumcm-2024-A-v2` 量规 + 5 条维度且**无删除接口**；建议先用 `fixture-extra` 当试验田 |

---

## 附录 A：目录结构

```text
paper-review/
├── CLAUDE.md                     项目约束（选型、硬约束、命名规范、验证命令）
├── compose.yaml                  四服务空壳（无可运行配置）
├── .env.example                  7 个键名，值留空
├── .gitignore                    忽略 .env / env / __pycache__ / .pytest_cache / 向量库数据目录
├── .env                          本地私有（含真实 DSN，已被 gitignore 覆盖）
├── backend/
│   ├── requirements.txt          12 个锁定依赖
│   ├── app/
│   │   ├── llm/client.py                     模型客户端（唯一 HTTP 出口）
│   │   ├── graph/review_graph.py             状态图
│   │   ├── importing/{catalog,models,db}.py  赛题数据入口
│   │   ├── api/{routes,app}.py               接入层（9 条路径）
│   │   ├── retrieve/{parent_child,three_route,rerank,models}.py  检索工具层
│   │   ├── scoring/{selection,aggregate}.py  选档与加总
│   │   ├── review/{consistency,samples}.py   规则审查
│   │   └── report/{change_list,evaluation,store,models,catalog}.py  报告与评测
│   └── tests/                    8 个测试文件，117 项用例
├── data/
│   ├── contests/                 4 道赛题 × 5 个 JSON
│   └── samples/                  3 篇演示稿 + eval/ 12 篇评测样例（md + json）
├── docs/
│   ├── diagrams/                 5 张 archify 图（json + html）
│   ├── plan/                     task_plan / progress / findings
│   ├── version/
│   │   ├── v1.0.1_命名规范.md
│   │   ├── 10.15/                v1.0.0 ～ v1.7.0 共 9 份阶段提示词
│   │   └── explain/              项目进度报告 V1 / V2
│   ├── 开发任务拆解与迭代流程.md
│   └── 项目文件树.md
└── frontend/                     ⬜ 全部为注释壳，未开始（P8）
```

## 附录 B：环境与常用命令

```text
# 解释器（唯一，不要在项目内建虚拟环境）
D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe   # Python 3.11.16

# 全量测试（当前基线：117 passed）
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q

# 启动服务（供接口联调）
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077

# 首次建表（三处 metadata 各自独立）
& ... -c "from backend.app.importing.db import create_schema; create_schema()"
& ... -c "from backend.app.retrieve.models import create_parent_schema; create_parent_schema()"
& ... -c "from backend.app.report.models import create_report_schema; create_report_schema()"

# 导入并发布一道赛题
curl -X POST http://127.0.0.1:8077/api/imports -H "Content-Type: application/json" -d "{\"package_dir\": \"data/contests/cumcm-2024-A\"}"
curl -X POST http://127.0.0.1:8077/api/contests/cumcm-2024-A/publish
```
