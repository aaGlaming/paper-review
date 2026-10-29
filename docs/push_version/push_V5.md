# paper-review 第五版（push_V5 · Phase-2 Agent 化与验收）完整说明

> **分支**：`Phase-II-Acceptance`（提交 `fb75d77`）
> **上一版**：`push_V4.md`（前端第二版上传，2026-10-17）。本版覆盖 **Phase-2 全部四个阶段 P12～P15**：LangChain Agent 接入、真实论文全链路验证、两个真实缺陷修复。
> **改动规模**：103 个文件，+16553 / −474 行；新增 70 个文件、修改 30 个、删除 3 个。
> **门禁**：`pytest backend/tests -q` → **231 passed**（退出码 0）；文档编码检查 63 个 md 全部通过。
> **判定口径**：项目规矩是「拿不出证据就不写通过」。本版四条判据通过、判据 5 部分满足，**不写「五条全通过」**。

---

## 1. 这一版做了什么

一句话：**让评审系统从「固定管线」变成「有界 Agent」，并在 10 篇真实参赛论文上验证它真的在决策，同时挖出并修掉两个只有真实数据才会暴露的缺陷。**

| 阶段 | 内容 | 状态 |
|---|---|:-:|
| P12 | 工具层、`agent_step` 轨迹、线性旁路 | ✅ |
| P13 | `create_agent` 子图接入、预算四闸、无进展检测、轨迹面板 | ✅ |
| P14 | critique 自检（只降不提） | ⚠️ 实现完成，真实链路 0 触发 |
| P15 | 验收取证、验收报告、`V5` 分支 | ✅ 四条通过 + 一条部分满足 |

### 1.1 改动范围（`git show --stat fb75d77` 实测，103 个文件）

| 类别 | 数量 | 说明 |
|---|:-:|---|
| 新增（`A`） | 70 | `backend/app/agent/` 13 个文件、11 个测试文件、10 篇论文、10.19 阶段文档、验收证据等 |
| 修改（`M`） | 30 | 检索层、客户端、路由、模型、量规数据、图示等 |
| 删除（`D`） | 3 | 三个零引用的空占位 `data/contests/*/samples/README.md` |

### 1.2 新增的 agent 包（13 个文件 / 1302 行）

| 文件 | 行数 | 职责 |
|---|:-:|---|
| `tools.py` | 329 | 六个工具、错误码封闭、唯一写结论的口 |
| `middleware.py` | 185 | 预算四闸、无进展检测、轨迹记录 |
| `runner.py` | 176 | 子图装配、收尾补交、critique 接入 |
| `critique.py` | 142 | 只降不提的自检 |
| `chat_model.py` | 148 | `BaseChatModel` 适配，委托既有客户端 |
| `trace.py` | 146 | `agent_step` 落库与查询 |
| `retriever.py` | 57 | `BaseRetriever` 适配，包住三路检索 |
| `linear.py` | 34 | 线性旁路接入（可整段回退） |
| `prompt.py` | 23 | system prompt 与收工协议 |
| `graph.py` | 22 | `create_agent` 的调用封装 |
| `state.py` | 14 | 状态结构 |
| `context.py` | 25 | 运行期依赖装配 |
| `__init__.py` | 1 | — |

---

## 2. 核心实现

### 2.1 Agent 挂在 `score` 内部，不是独立节点

冻结测试 `backend/tests/graph/test_interrupt.py` 断言了三条：`score_node_calls == 1`、`graph.get_state(...).next == ()`、`status == "完成"`。**把 `retrieve` / `score` 换成独立的 agent 节点会直接打破这三条，而那个文件不许改。**

所以接法是：

```text
START → parse → confirm → retrieve → score → END
                                      └─ 内嵌 LangChain create_agent 子图
```

- `score` 变成分派器：没有 `agent_runner` 时走老逻辑，有就跑 agent，但 `score_node_calls` 照常 +1；
- agent 模式下 `retrieve` 提前返回空 `retrievals`，否则同一篇论文检索两遍，embed / rerank 成本翻倍；
- 子图**不单独传 checkpointer**，否则 resume 时按 `thread_id` 找不到父图快照，`GET /reviews/{id}` 直接 404。

### 2.2 六个工具，读五写一

| 工具 | 作用 | 写库 |
|---|---|:-:|
| `list_dimensions` | 读取量规五维 | 否 |
| `search_evidence` | 按维检索父块摘要（每段 ≤200 字） | 否 |
| `read_parent` | 读检索白名单内的父块全文 | 否 |
| `check_consistency` | 数字 / 引用 / 范围一致性 | 否 |
| `get_constraints` | 硬约束只读视图 | 否 |
| **`submit_dimension`** | **记录结论的唯一入口** | **是** |

`submit_dimension` 进来先做子串校验、再走 `apply_mention_guard`，同一维第二次提交返回 `not_allowed` 不允许覆盖。五个封闭错误码：`param_invalid` / `not_found` / `not_allowed` / `quote_not_substring` / `budget_exceeded`。

### 2.3 预算四闸 + 递归兜底

| 闸门 | 上限 | 落在哪 |
|---|:-:|---|
| 单维步数 | 3 步 | `wrap_tool_call` |
| 全局工具调用 | 24 次 | `wrap_tool_call` |
| 模型调用 | 12 次 | `before_model` |
| 墙钟时间 | 150 s | 每个工具入口 |
| **递归深度** | `recursion_limit=45` | `graph.invoke` |

`create_agent` **没有** `max_iterations`（那是旧 `AgentExecutor` 的参数），必须自己兜底。递归达上限与预算耗尽**分开记录**——曾把前者误标成后者，指标名一错，后面排查全跑偏。

### 2.4 LangChain 1.x 的两个坑（实测）

| 事项 | 实测结果 |
|---|---|
| `AgentExecutor` | **1.x 已删除**，`ImportError`。网上 90% 的 LangChain Agent 教程照抄必炸 |
| 正确入口 | `langchain.agents.create_agent`（返回 `CompiledStateGraph`）或 `langgraph.prebuilt.create_react_agent` |
| middleware 钩子 | `before_agent` / `before_model` / `after_model` / `after_agent` 都是 `(state, runtime)`，**只有 `wrap_tool_call` 是 `(request, handler)`** |

---

## 3. 本版修复的两个真实缺陷

**这两个缺陷在 231 条测试全绿的状态下长期存在**，只有把真实论文灌进系统才暴露。

### 3.1 跨论文引用污染（严重）

**现象**：a163 论文的五维引用，内容全部来自 a016（另一篇论文）。

**根因**：向量检索的过滤条件只有 `contest_id` / `rubric_id` / `section_type` / `doc_type`，**没有 `review_id`**。同一赛题下多篇论文共用一个 Chroma collection，于是 B 论文召回 A 论文的父块。

**为何校验没拦住**：`quote_is_substring` 校验的是「是否在该维检索到的父块里」，而那些父块本身就是别的论文的——校验通过，引用却指向别人的论文。**「引用可回溯」这条底线被合法绕过。**

**修复（6 个点）**：

| 位置 | 改动 |
|---|---|
| `parent_child.ChildChunk` | 新增 `review_id` 字段 |
| `parent_child.child_metadata` | 元数据写入 `review_id`（第九个键） |
| `parent_child.build_children` | 新增 `review_id` 入参，缺省取父块的 |
| `parent_child._where` | 新增 `review_id` 过滤子句 |
| `parent_child.search_children_then_parents` | 新增 `review_id` 形参 |
| `three_route.default_search_round` | 补齐并下传（原先完全没接） |
| `three_route.retrieve_dimension` | `round_request` 补（原先只在 fallback 分支传） |

**效果**：

| | 修复前 | 修复后 |
|---|:-:|:-:|
| 引用命中本篇原句 | 24 / 50 | **48 / 50** |
| 引用指向他篇 | **26** | **0** |

### 3.2 档位枚举缺失导致收尾补交全废

**现象**：agent 检索到 14 段证据却不提交，轨迹以 `no_progress` 收尾，五维全「证据不足」。

**根因**：`_force_submit` 用的临时工具 schema 是空壳 `{"items": {"type": "array"}}`，**`band` 没有任何约束**。模型于是自创档位 `high` / `medium`，被 `param_invalid` 逐条挡下，补交 0 条。

探针实测：5 条提交的 quote **全是论文原句、子串校验全过**，唯一失败点就是 band 取值。

**修复**：

| 位置 | 改动 |
|---|---|
| `tools._SubmitArgs.band` | `str + description` → `Literal["充分","基本","不足","证据不足"]` |
| `runner._force_submit` | 临时工具补完整 schema（含 `enum`）+ 提示词显式列出四档 |

> `description` 只是提示，挡不住模型自创档位；必须在 schema 层用 `Literal` 生成 `enum`。

**效果**：主动提交 **0 → 45 次**，五维从「全部证据不足」变为「基本 35 / 不足 7 / 充分 6」。

---

## 4. 真实数据全链路

10 篇真实参赛论文（3 道赛题），逐篇走 `parse → confirm → retrieve → score → report`，全部 `source=model`。

| 指标 | 实测 |
|---|---|
| 成功 | **10 / 10** |
| 端到端耗时 | 合计 233.6 s，均值 **23.4 s**，最大 36.6 s |
| 轨迹行数 | 270 |
| 模型主动提交 | 45 次 |
| 收尾补交 | 7 篇由 `force_submit` 补交 |
| 终止原因 | `all_submitted` 8 篇 / `budget_exhausted` 2 篇 |
| 不同动作序列 | **10 篇产生 10 种互不相同的序列** |
| 引用可回溯 | **48 / 50 维为本篇原句，0 维指向他篇** |

明细见 `docs/plan/acceptance/calls/real-pipeline-10papers.json`。

### 4.1 两处值得说明的现象

- **c234 的 `constraint_check` 判「证据不足」是对的**：该论文只有模型假设、建立求解、优缺点、改进、推广，没有检验或结果分析章节。系统没有硬凑。
- **a242 三维判「充分」**，是全库第一批由真实论文产出的充分档（此前 1955 条里只有 1 条，且来自复述题目条件的 `assumption` 维）。

---

## 5. 数据归档与仓库卫生

### 5.1 归档

原始 PDF 从 `data/cumcm-*/论文/` 移到 **`data/papers/<赛题>/`**（13 个文件）。`data/contests/` 与 `data/samples/` **原地不动**——它们被导入模块与 4 个测试文件直接依赖，改路径等于改产品行为。

两个转换脚本同步改造，**不再写死题号**，改为扫 `data/papers/` 子目录自动发现赛题；题面 PDF 按「题.pdf」后缀识别并从论文批次排除。新增赛题不必改代码。

### 5.2 清理

| 项 | 处置 | 理由 |
|---|---|:-:|
| `contests/*/samples/README.md` ×3 | **删除** | 零引用的空占位目录；导入校验与测试均不涉及 |
| 三篇演示稿 | **保留** | 是测试夹具：4 个测试文件按文件名直读并断言具体结果；`evaluation` 用 `len(DEMO_FILES)` 当语料口径。删除会让 231 条测试失败 |
| `fixture-extra` 赛题包 | **保留** | `test_catalog.py` 运行时自己导入它 |
| `eval/` 12 篇评测集 | **保留** | 60 维 gold 是评测指标的分母 |

### 5.3 `.gitignore` 本版新增 5 条

| 条目 | 理由 |
|---|---|
| `.bak_db/` | 清库前的数据库导出（1.3 MB），本机留证 |
| `.bak_encoding/` | 编码事故前的损坏备份（280 KB），本机留证 |
| `.pytest_out.txt` | 临时输出 |
| `data/papers/` | 原始 PDF 46 MB，有版权；Markdown 776 KB 已入库，复现方式见 `data/README.md` §七 |
| `docs/interview/` | 面试自用材料，数字基于 Phase-1 时期已随 Agent 化过时 |

### 5.4 两个库换成真实数据

| 库 | 清空前 | 现状 |
|---|:-:|:-:|
| `review` | 395 | 17（10 篇正式回归 + 3 条 probe 取证 + 4 条对照实验） |
| `review_dimension` | 1960 | 85 |
| `paper_parent` | 1021 | 真实父块 |
| `agent_step` | 1276 | 470（孤儿 0） |
| Chroma `paper_review` | 1224 | 2522 |

**赛题配置保留**：`contest` 5 道 / `rubric` 4 / `dimension` 20 / `constraint` 22。清库前备份在 `.bak_db/`（本地，已 ignore）。

---

## 6. 测试与门禁

### 6.1 新增测试（11 个文件、约 800 行）

| 文件 | 条数 | 覆盖 |
|---|:-:|---|
| `agent/test_tools.py` | 15 | 六工具、错误码、唯一写口、重复提交拒绝 |
| `agent/test_middleware.py` | 10 | 预算四闸、无进展、终止原因分离 |
| `agent/test_runner.py` | 9 | 子图装配、补交、critique 接入 |
| `agent/test_critique.py` | 8 | 只降不提、跳级拒绝、mention 降档、配额 |
| `agent/test_trace.py` | 6 | 轨迹落库与查询 |
| `agent/test_chat_model.py` | 5 | `BaseChatModel` 契约 |
| `agent/test_linear.py` | 4 | 线性旁路 |
| `agent/test_retriever.py` | 3 | `BaseRetriever` 契约 |
| `agent/test_no_http.py` | 1 | **源码扫描**：`agent/` 包内不得出现 `httpx` / `requests` / `urllib` |
| `llm/test_chat_tools.py` | 6 | `tools` 字段与 `tool_calls` 解析 |
| `graph/test_agent_score.py` + `api/test_agent_steps.py` | 5 | 冻结语义与轨迹接口 |

### 6.2 门禁（提交前实跑）

| 门禁 | 结果 |
|---|---|
| `pytest backend/tests -q` | **231 passed in 9.12s**，退出码 0 |
| `python scripts/check_docs_encoding.py docs --strict` | 63 个文件，有问题 **0** |
| `npm run build` / `vitest` / `playwright` | **本版未跑**——未修改 `frontend/src` 下任何文件。这是「未改动」而非「已复跑」；若要出总验收数字需补跑 |

### 6.3 一条环境纪律

pytest 必须带 `PYTEST_DEBUG_TEMPROOT="$(pwd)/.pytest_tmp"`（目录需先存在），否则本机安全策略会拦截临时目录清理，**测试全绿但退出码 1**。

---

## 7. 遗留问题（本版未处理）

### 7.1 阻塞「五条全 ✅」的（1 项）

**P14 critique 真实链路 0 触发。** 实现完整（8 条单元测试通过），代码路径经审查确认可达降档分支，但真实链路一次都没走到。

收口复核做了对照实验（同一篇论文重复跑 3 次）：

| 论文 / 赛题 | 3 次「充分」维度数 |
|---|---|
| `a242` / 原题 | **3 / 1 / 1** |
| `a242` / probe 赛题 | **0 / 0 / 0** |
| `c234` / 原题 | **2 / 2 / 0** |

先排除量规差异：probe 的 `rubric.json` 与原题**逐字段完全相同**。

**由此得出两条硬阻塞**：

| # | 阻塞 | 依据 |
|:-:|---|---|
| 1 | 模型极少判「充分」，guard 与 critique 都没有作用对象 | `apply_mention_guard` 首行 `if band != BANDS[0]: return` |
| 2 | runner 以 `chat_fn=None` 调 critique，第二条路径永远走不到 | `critique.py:96` |

**关键推论**：mention 约束只能「拦」充分，**不能「造」充分**。v2.4.0 设计的「加一条命中不了的约束造样本」路线，在真实链路上本质上走不通——不是执行问题，是机制上限。

要解除必须改产品语义，**须先立 Ruling**，不在验收阶段范围内。

### 7.2 其他挂账（6 项）

| # | 项 | 去向 |
|:-:|---|---|
| 1 | token 与成本不可测（`agent_step` 未记 usage） | Phase-3 的 P16 |
| 2 | 无结构化日志文件与 `/metrics` | Phase-3 的 P16 |
| 3 | 无鉴权与多用户 | Phase-3 的 P17 |
| 4 | `compose.yaml` 的 frontend 空壳 | Phase-3 的 P24 |
| 5 | **没有「修改量规内约束」的接口**，只能整包重导 | 视需要排期 |
| 6 | 论文为 OCR 扫描件，公式与表格有损 | 需原生文本版论文才能评估评分质量 |

---

## 附录 A：分支与提交关系

```text
main / V4-Phase-I-Ares.Acceptance
  └─ 48deb6a  第一期验收收口
       ├─ V5-Phase-II-Agent.Acceptance（581b3a2 docs: complete phase-2 acceptance evidence）
       └─ Phase-II-Acceptance（fb75d77）← 本版
```

## 附录 B：常用命令

```bash
# 切到本版分支
git checkout Phase-II-Acceptance

# 后端门禁（注意 PYTEST_DEBUG_TEMPROOT，缺了会「全绿但退出码 1」）
mkdir -p .pytest_tmp
PYTEST_DEBUG_TEMPROOT="$(pwd)/.pytest_tmp" \
  "D:/LEARN/AI/programs/AgentTask/env/agent-task/Scripts/python.exe" -m pytest backend/tests -q

# 文档编码门禁
python scripts/check_docs_encoding.py docs --strict

# 10 篇真实论文全链路回归（需后端在 8077 运行）
python scripts/run_real_pipeline.py
python scripts/run_real_pipeline.py --only a016   # 只跑一篇

# 验收取证（按五条判据从库里取证据）
python scripts/collect_phase2_evidence.py

# 论文 OCR 转换（需先自行下载 PDF 放进 data/papers/<赛题>/）
pip install rapidocr-onnxruntime
python scripts/batch_papers.py --workers 4
python scripts/update_statements.py
python scripts/retitle_md.py --all

# MySQL（StartType=Manual，开机不自启）
net start MySQL80

# 改过 retrieve/parent_child.py 或向量库结构后必须重启后端，
# 否则进程持有失效的 Chroma collection 句柄，表现为「五维全证据不足 + 轨迹 0 行」
```

## 附录 C：给拿到本仓库的人

1. **原始 PDF 不在仓库里**（46 MB 且有版权）。Markdown 已在 `data/samples/`，要复现转换请自行从官方渠道下载 PDF，按 `data/README.md` §七 的目录结构放回 `data/papers/<赛题>/`。
2. **`.env` 不在仓库里**，需自行配置 `LLM_*` / `EMBEDDING_*` / `RERANK_*` 与 `MYSQL_DSN`。
3. **`data/contests/probe-critique-acceptance/` 是验收夹具**，量规与 `cumcm-2024-A` 逐字段相同，仅用于判据 5 取证，**不参与真实评测集**，后续可删除。