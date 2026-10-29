# paper-review 执行手册

> 立项：竞赛论文评价 Agent，英文目录 `paper-review`。  
> 开发方式：vibe coding。一次只做一个里程碑，先写失败测试，再写实现。  
> 依据：《竞赛论文评价Agent_需求分析》（需求分析V3）、《竞赛论文评价Agent_开发计划书》（项目开发计划书V2）。两份文档冲突时，以需求分析的验收条目为准，并在 `docs/plan/findings.md` 记一条裁决。  
> 代码目录：`D:\LEARN\AI\programs\AgentTask\Projects\paper-review`。  
> 代码仓库：https://github.com/aaGlaming/paper-review  
> 解释器：`D:\LEARN\AI\programs\AgentTask\env\Scripts\python.exe`。不在项目内再建虚拟环境。  
> Skills 清单：`D:\.skills`（2026-10-14 核对，共 79 个技能目录，其中没有 archify）。  
> 图示工具：[archify](https://github.com/tt-a1i/archify) v3.1.0。只用来产出可交互架构图，不进入产品运行时。  
> 版本：V1 · 2026-10-14

---

## 1. 项目目标与范围

### 1.1 目标

做一个赛前预审工具。学生或教师选定一道已发布赛题、上传论文后，系统按该题评分量规逐维取证，给出档位、论文原句和修改清单。进入加权的每一维必须能打开量规条款和论文原句。证据不够写成「证据不足」，原句对不上写成「引用失败」，这两类不进加权。系统不输出奖项、名次或获奖概率。

### 1.2 首期要做

- 三道公开赛题：`cumcm-2024-A`、`cumcm-2024-C`、`cumcm-2025-A`。题目正文保持公开发布文本的原意。
- 自建量规五维：假设的合理性、建模是否针对本题、求解与结果、检验与题目约束、表述与结构。每维四档：充分、基本、不足、证据不足。权重合计 100。证据不足没有分数。
- 15 篇自建论文，其中 3 篇 `is_demo = true`：板凳龙、种植策略、烟幕投放。
- 三篇演示必须标出：412 s 与 386 s；1286 万元与 974 万元；22.4 s 与 18.6 s；引用 \[12\] 缺失；无人机 160 m/s 超出 70～140 m/s；种植样例缺豆类「三年内至少一次」和 50% 降价 / `result1_2`。
- 章节树由人确认后才评分。检查点按 `review_id` 保存，进程重启后从暂停处继续。
- 赛题数据包可追加。缺字段、权重合计不是 100、`check_type` 未注册或档位不全时整包拒绝。
- 对话、嵌入、重排都走云端 OpenAI 兼容接口。仓库不提供本地模型运行时。

### 1.3 首期不做

- 不做全国评阅，不做多用户权限和学校组织架构。
- 不把优秀论文原文切进向量库。
- 不按题号在评分代码里写分支。差异只放在 `constraint` 与 `rubric`。
- 不使用 Assistants、Responses 或厂商私有响应字段。
- PDF 版面解析失败不能当成空论文。Markdown 是验收主路径。

### 1.4 成功时人能看见什么

打开三个「填入示例」，一致性审查能定位到两处冲突原文；证据不足的维度单独着色且不进总分；评测页对 15 篇给出档位一致率、引用精确匹配率、证据不足命中情况，并能点进单篇。导出文本里没有奖项字样。

---

## 2. 核心功能模块

| 模块 | 目录 | 职责 | 不做什么 |
|---|---|---|---|
| 赛题导入 | `backend/app/importing` | 校验并发布赛题、约束、量规、扣分点、样例评语 | 不按题号写流程分支 |
| 解析 | `backend/app/graph` 的解析节点 | 章节树、主张、表格、文内引用、参考文献 | 用户未确认不进入评分 |
| 对齐 | 同一状态图 | 绑定当前 `published` 量规，逐条读 `constraint` | 赛题不一致则停止 |
| 检索 | `backend/app/retrieve` | 过滤子块、重排、取回父块 | 父块不进 Chroma；每维最多 4 段 |
| 选档 | 状态图评分节点 | 在给定片段里选四档之一，返回切片编号和原句 | 不改权重 |
| 审查 | `backend/app/review` | 数字冲突、引用是否存在、数值是否越界 | 不用模型做这三项判断 |
| 加总 | `backend/app/scoring` | 只加权通过校验的维度 | 证据不足、引用失败排除 |
| 报告 | `backend/app/report` | 转写已校验结果，排序为硬伤、证据不足、表述 | 不另写褒贬，不写奖项 |
| 模型客户端 | `backend/app/llm` | 唯一 HTTP 出口 | 智能体不自己发请求 |
| 前端 | `frontend/src/views` | 解析、评分、审查、修改、评测 | P8 之前不生成页面 |

`check_type` 首批只注册三种：`mention`、`numeric_range`、`required_case`。

---

## 3. 技术方案与架构

### 3.1 运行时

```text
Vue 3 预审工作台 ──HTTP──> FastAPI
                            ├── LangGraph（解析确认 → 逐维检索 → 选档 → 审查 → 报告）
                            ├── MySQL 8.0（赛题、约束、量规、父块、评审、检查点）
                            ├── Chroma（paper_child、band_text、pitfall、exemplar、contest_statement）
                            └── 云端 /chat/completions、/embeddings、重排接口
```

编排是 LangGraph 状态图，不是自由 ReAct。章节确认调用 `interrupt()`，用户改完章节类型后用 `Command(resume)` 继续。

检索顺序：按维度的 `evidence_prompts` 和 `section_types` 生成查询；用 `contest_id`、`rubric_id`、`section_types` 过滤子块；重排只改顺序；送入模型的是父块。证据不足才改写查询再查一轮。模型给出的原句必须是切片里的连续子串。

### 3.2 环境变量

只允许这些键，密钥不进仓库：

```text
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
EMBEDDING_MODEL
RERANK_BASE_URL
RERANK_MODEL
MYSQL_DSN
```

对话只读 `choices[0].message.content`。嵌入只读 `data[].embedding`。选档要求 JSON；解析失败重试一次，再次失败则该步标为失败并显示在页面上。父块不向量化。

### 3.3 Compose

服务只有 `frontend`、`backend`、`mysql`、`chroma`。不部署 Ollama，不挂载模型权重。

### 3.4 与 archify 的衔接

archify 把 Typed JSON 校验后交付成一个独立 HTML。本项目用它做五张说明图，放在 `Projects/paper-review/docs/diagrams/`。图是开发文档，不是评分引擎。

| 图 | archify 类型 | 何时画 | 源文件 | 成品 |
|---|---|---|---|---|
| 运行时 | architecture | P0 结束前 | `runtime.architecture.json` | `runtime.architecture.html` |
| 预审主路径 | workflow | P1 开始前 | `review.workflow.json` | `review.workflow.html` |
| 一维检索 | sequence | P3 开始前 | `retrieve.sequence.json` | `retrieve.sequence.html` |
| 父子块 | dataflow | P3 完成时 | `chunks.dataflow.json` | `chunks.dataflow.html` |
| 评审单状态 | lifecycle | P1 完成时 | `review.lifecycle.json` | `review.lifecycle.html` |

每张图 8～12 个节点。主路径只留一条：上传 → 确认章节 → 对齐赛题 → 逐维检索 → 选档 → 规则审查 → 子串校验 → 修改清单。模型调用画在信任边界外，标成外部依赖。不要把「预测奖项」画成节点。

安装与出图命令见第 6.2 节。出图失败不阻塞 P1 的 pytest；P0 的完成定义要求第一张 architecture 图已经 `deliver` 成功。

### 3.5 与现有 skills 的衔接

开发时按下面的技能做事，不要另起一套流程。

| 时机 | 读取的 skill | 落在本项目的动作 |
|---|---|---|
| 开工前 | `D:\.skills\using-superpowers` | 先确认本手册是当前任务的执行说明 |
| 每个里程碑开始 | `D:\.skills\test-driven-development` | 先写测试，看着它失败，再写实现。先写了实现就删掉重来 |
| 里程碑执行 | `D:\.skills\executing-plans` | 本会话内联做完当前编号；裁决写入 `docs/plan/findings.md`，格式：`Ruling: 决定 — 原因 — 错了的代价` |
| 跨会话 | `D:\.skills\planning-with-files` | 维持 `docs/plan/task_plan.md`、`findings.md`、`progress.md` |
| 声称通过之前 | `D:\.skills\verification-before-completion` | 当场跑第 7 节的命令，读退出码，再写「通过」 |
| PDF 上传路径 | `D:\.skills\pdf` | 用 pypdf 抽文本；抽不出就返回错误，不把空字符串当论文 |
| 接口形状 | `D:\.skills\api-designer`、`api-documenter` | 路径以第 3.6 节为准；OpenAPI 在 P7 后补，不提前发明路径 |
| Vue 页面 | `D:\.skills\vue-best-practices`、`vue-router-best-practices`、`vue-testing-best-practices` | 只在 P8 使用。Composition API |
| 页面验收 | `D:\.skills\webapp-testing` 或 `agent-browser` | 三篇示例要点到冲突原文 |
| 失败排查 | `D:\.skills\systematic-debugging` | 先复现失败测试，再改代码 |
| 里程碑结束 | `D:\.skills\requesting-code-review` | P8 全部通过后做一次整支审查，不每个编号都开审查 |
| 提交 | `D:\.skills\commit-helper` | 只在人明确要求提交时使用 |

不要用这些技能做本项目：`book-sft-pipeline`、`bdi-mental-states`、`create-adaptable-composable`、`figma-designer`、`azure-*`、`microsoft-foundry`。它们和论文预审无关。

### 3.6 接口（先于代码冻结）

```text
GET  /api/contests
POST /api/reviews
POST /api/reviews/{review_id}/resume
GET  /api/reviews/{review_id}
GET  /api/samples?is_demo=
GET  /api/eval/summary
POST /api/catalog/imports
POST /api/contests/{contest_id}/publish
POST /api/contests/{contest_id}/archive
```

新增路径先改本手册这一节和开发计划书第四节，再写代码。

---

## 4. 开发阶段与里程碑

阶段按依赖排列。上一个编号的 pytest 退出码不是 0，就不写下一个编号的提示词。

| 阶段 | 编号 | 人要看到的结果 | 依赖 |
|---|---|---|---|
| 地基 | P0 | 虚拟环境可导入 FastAPI；`.env.example` 只有第 3.2 节的键；第一张 archify 运行时图已交付 | Python 3.11、Node 20、Docker、云端密钥由人填入 |
| 解析暂停 | P1 | 未确认章节树不会进入评分；重启后从暂停点继续 | P0 |
| 赛题数据 | P2 | 三道赛题可读；坏包整包拒绝且已有数据不变 | P0 |
| 父子块检索 | P3 | 先过滤再取父块；错赛题子块不会被取回 | P2 |
| 重排与再检索 | P4 | 每维最多 4 段；重排不放宽过滤；证据不足才再查一轮 | P3 |
| 选档与子串 | P5 | 原句不是子串则不加权；未写调头圆弧的维度为证据不足 | P4 |
| 规则审查 | P6 | 三篇演示的数字、引用、速度越界被标出 | P2。可与 P5 并行开发，合并前两边都要绿 |
| 报告 | P7 | 清单只转写已校验结果；文本中无奖项 | P5、P6 |
| 页面 | P8 | 五个页面可填入示例；评测页能点进单篇 | P7 |

P6 允许和 P4、P5 并行，因为它只读论文纯文本和约束，不读向量库。其余编号顺序执行。

---

## 5. 各阶段任务拆解

每一轮提示词只带三样东西：编号、允许修改的目录、完成定义原句。提示词模板：

```text
执行 paper-review 的 <编号>。
解释器：D:\LEARN\AI\programs\AgentTask\env\Scripts\python.exe
不要在项目里创建虚拟环境。不要引入 Neo4j、FAISS 或本地模型运行时。
允许修改的目录：<目录>
完成定义：<下表原句>
先写失败测试，看着 pytest 失败，再写实现。
核对命令：
& D:\LEARN\AI\programs\AgentTask\env\Scripts\python.exe -m pytest <测试文件> -q
退出码 0 才算通过。把退出码和失败摘要写入 docs/plan/progress.md。
```

### P0 地基

允许修改：`Projects/paper-review` 根下的环境文件、`backend/app/llm`、`backend/tests/llm`、`docs/diagrams`、`docs/plan`、`compose.yaml`、`CLAUDE.md`。

任务：

1. 若 `D:\LEARN\AI\programs\AgentTask\env` 尚不存在，由人执行（代理不要擅自创建，除非人当轮明确说「现在建环境」）：

```text
py -3.11 -m venv D:\LEARN\AI\programs\AgentTask\env
& D:\LEARN\AI\programs\AgentTask\env\Scripts\python.exe -m pip install -U pip
```

2. 写 `backend/requirements.txt`，至少包含：fastapi、uvicorn、pydantic、sqlalchemy、langgraph、chromadb、pypdf、python-docx、httpx、pytest。安装进上述环境。
3. `backend/app/llm/client.py` 只提供 `chat()` 和 `embed()`。测试用 httpx mock：断言请求路径是 `/chat/completions` 与 `/embeddings`，断言不读取 `choices` 以外的厂商字段。
4. 写 `.env.example` 与 `.gitignore`（忽略 `.env`、`env/` 若被误放进项目、Chroma 数据目录）。
5. 写 `CLAUDE.md`，不超过 200 行，只写：选型、引用必须是子串、不得输出奖项、验证命令、云端接口。
6. 建立 `docs/plan/task_plan.md`、`findings.md`、`progress.md`。`task_plan.md` 抄第 4 节的表，把当前编号标成 P0。
7. 按第 6.2 节交付 `runtime.architecture.html`。

完成定义：mock 客户端测试退出码 0；仓库内搜不到 `ollama`、`sentence-transformers`、`qwen2.5`；architecture 图的 deliver JSON 没有失败诊断。

### P1 解析暂停

允许修改：`backend/app/graph`、`backend/tests`。

完成定义：章节树可确认，未确认不进入评分。重启后从暂停点继续。

测试要点：

- 上传一篇 Markdown，得到章节类型：假设、模型、求解、结果、检验、参考文献。
- 未 resume 时评分节点不被调用。
- 用同一个 `review_id` 重建图，停在解析节点，resume 后不再重新解析已确认的树。
- 空 Markdown 返回错误，不创建评审。

同时交付 `review.workflow.json` 与 `review.lifecycle.json`。状态只含：草稿解析、待确认、评分中、完成、失败。不要加「已获奖」。

### P2 赛题数据

允许修改：`backend/app/importing`、`data/contests`、`backend/tests`。

完成定义：三道赛题与约束可读取；坏包被拒绝。权重合计不是 100 时整包失败。

数据包目录：

```text
data/contests/{contest_id}/contest.json
data/contests/{contest_id}/constraints.json
data/contests/{contest_id}/rubric.json
data/contests/{contest_id}/pitfalls.json
data/contests/{contest_id}/exemplars.json
```

`numeric_range` 的 params 示例：`{"min": 70, "max": 140, "unit": "m/s"}`。`required_case` 示例：`{"label": "50%降价", "artifact": "result1_2"}`。

必须有的约束：

- A 题：碰撞、螺距 1.7 m、调头圆弧半径 2 倍且相切、龙头速度 1 m/s、把手速度不超过 2 m/s。
- C 题：不能连续重茬、三年内至少一次豆类、滞销与 50% 降价两种情形。
- A 题 2025：云团 3 m/s 下沉、10 m / 20 s、无人机 70～140 m/s。

测试：合法包发布后 `GET` 式查询能读到 `contest_id`；坏包返回文件名和字段名；已发布赛题行数不变。`archived` 后新建列表没有它，旧 `review_id` 仍能打开。

### P3 父子块

允许修改：`backend/app/retrieve`、`backend/tests`。

完成定义：先过滤再取父块，父块不进 Chroma。错赛题的子块不会被取回。

测试：

- 两道赛题各插入一个子块，查询带 `contest_id=cumcm-2024-A` 时不返回 C 题子块。
- Chroma 的 `doc_type` 只有 `paper_child`、`band_text`、`pitfall`、`exemplar`、`contest_statement`。
- 父块全文只在 MySQL，通过 `parent_id` 取回。
- 表格单独成块。

交付 `retrieve.sequence.html` 与 `chunks.dataflow.html`。数据流要标明：子块进 Chroma，父块留在 MySQL，送入模型的是父块。

### P4 重排

允许修改：`backend/app/retrieve`、`backend/app/graph`、`backend/tests`。

完成定义：每维最多 4 段；证据不足可再查一轮。重排不放宽过滤。

测试：过滤后只剩 2 段时，重排不能把被过滤掉的段加回来。候选多于 4 段时，模型输入长度为 4。第一轮空结果才允许第二轮；第二轮仍空则档位为证据不足，且不调用第三次检索。

重排客户端读取 `RERANK_BASE_URL`。测试默认 mock。没有密钥时 P4 的过滤与截断测试仍须通过。

### P5 选档与子串

允许修改：`backend/app/graph`、`backend/app/scoring`、`backend/tests`。

完成定义：原句不是子串则不加权。未写调头圆弧的维度为证据不足。

测试：

- 模型返回的原句不在父块中，该维状态为「引用失败」，加权和里没有它。
- 证据不足的 `score` 不参与求和。
- 权重来自量规数据。模型 JSON 里如果带了权重字段，加总函数忽略它。
- JSON 解析失败重试一次，第二次失败则该步为失败，页面可见。

### P6 规则审查

允许修改：`backend/app/review`、`data/samples`、`backend/tests`。

完成定义：三篇演示的数字、引用、速度越界被标出。点击能定位原文。

样例文件：

- `data/samples/bench-dragon.md`：摘要 412 s，结果表 386 s；假设写「忽略板凳宽度」。
- `data/samples/planting.md`：摘要 1286 万元，汇总表 974 万元；没有豆类三年约束；没有 `result1_2`。
- `data/samples/smoke.md`：摘要 22.4 s，正文 18.6 s；正文引用 \[12\] 但参考文献没有 \[12\]；无人机 160 m/s。若把云团写成静止且没有 3 m/s 下沉，对应维度不得为「充分」（该条由 P5 的量规测试覆盖，P6 只负责 160 m/s 和引用）。

测试不调用模型。定位信息是字符偏移，供 P8 滚动。

另外 12 篇放在 `data/samples/eval/`，每篇带 `gold`（维度与档位）和 `expected_findings`。P6 只要求三篇演示的规则冲突；12 篇的档位对比放到 P7 的评测脚本。

### P7 报告与评测脚本

允许修改：`backend/app/report`、`backend/tests`。

完成定义：修改清单只转写已校验结果。文本中无奖项。

测试：

- 清单顺序：题目约束和数字冲突、证据不足、表述。
- 每条建议能指回一个 `dimension_code` 或一条审查结果。删掉上游记录后，这条建议不能单独存在。
- 报告文本、接口 JSON 用正则拒绝「一等奖」「二等奖」「获奖概率」「名次」。
- 15 篇脚本输出三个数：档位一致率、引用精确匹配率、证据不足命中情况。百分比以脚本实际输出为准，不在代码里写死一个目标准确率。
- 发布第 2 版量规后，新建评审 `rubric_version` 为 2，旧记录仍为 1。

### P8 页面

允许修改：`frontend/src/views`、`frontend/src/api`。后端测试仍须保持绿色。

完成定义：五个页面可填入示例。评测页能点进单篇。

页面：论文解析、分项评分、一致性审查、修改建议、评测对照。三篇演示都有「填入示例」。证据不足用单独颜色。点击审查结果滚动到原文偏移。

先读 `vue-best-practices` 再写组件。验收用 `webapp-testing`：填入板凳龙，断言页面同时出现 412 和 386。

---

## 6. 依赖与风险

### 6.1 外部依赖

| 依赖 | 用途 | 谁准备 | 缺失时 |
|---|---|---|---|
| Python 3.11 x64 | 共享虚拟环境 | 人 | P0 停止 |
| Node 20 | 前端与 archify CLI | 人 | P0 的图和 P8 停止；P1～P7 的 pytest 仍可做 |
| Docker Desktop | MySQL 与 Chroma | 人 | P3 的集成测试停止；纯函数测试可先用内存假件 |
| 云端 API 密钥 | 对话、嵌入、重排 | 人写入 `.env`，不写入仓库 | P4 过滤测试用 mock；真实预审在 P5 之后才需要 |
| 三道赛题公开文本 | 约束依据 | 开发时对照组委会发布文本抄写，不改数字 | P2 不能发布 |

### 6.2 archify 安装与出图

`D:\.skills` 里目前没有 archify。P0 之前由人执行：

```text
npx -y skills add tt-a1i/archify --skill archify --agent cursor --global --copy --yes
```

安装完成后，把得到的 `archify` 技能目录复制到 `D:\.skills\archify`，与现有技能放在同一清单里。复制前若目标已存在，先看 `SKILL.md` 版本，不要覆盖成旧文件。

出图在技能目录内执行（把 `<SKILL_DIR>` 换成安装后的 `archify` 路径）：

```text
node <SKILL_DIR>\bin\archify.mjs validate architecture docs\diagrams\runtime.architecture.json --quality showcase --json
node <SKILL_DIR>\bin\archify.mjs deliver architecture docs\diagrams\runtime.architecture.json docs\diagrams\runtime.architecture.html --quality showcase --json
```

workflow、sequence、dataflow、lifecycle 把第一个参数换成对应类型。失败时只改 JSON 里诊断指向的对象，同一张图最多修两轮。修不好就把诊断贴进 `docs/plan/findings.md`，不要改成 Mermaid 顶替。archify 的成品是 HTML，不是产品页面。

### 6.3 风险

| 风险 | 后果 | 处理 |
|---|---|---|
| PDF 抽文本为空 | 被当成没有内容的论文 | 返回解析失败；验收走 Markdown |
| 检索混入其他赛题 | 档位没有依据 | 测试断言 `contest_id` 过滤先于重排 |
| 模型编造原句 | 假引用进入总分 | 子串失败则该维不加权 |
| 重排把过滤结果加回来 | 每维超过 4 段或串题 | P4 用假重排客户端断言输入集合不变 |
| 样例数字被当成标准答案 | 演示失真 | 页面标明自建样例 |
| 按题号写 if | 第四道题无法追加 | P2 用自建第四道题做导入测试，评分代码不出现 `cumcm-2024-A` 分支 |
| 云端超时 | 预审停住 | 页面显示当前步骤，不补写评语 |
| archify 未安装 | P0 的图交不出 | 先安装再画；不把画图失败记成评分测试失败 |
| 提示词一次做多个编号 | 测试和实现缠在一起 | 提示词模板拒绝同时出现两个编号 |

---

## 7. 验证与验收标准

### 7.1 每个编号的核对命令

在 `D:\LEARN\AI\programs\AgentTask\Projects\paper-review` 执行：

```text
& D:\LEARN\AI\programs\AgentTask\env\Scripts\python.exe -m pytest <该编号的测试文件> -q
```

退出码 0 才把 `docs/plan/progress.md` 里该编号写成通过，并附上命令与最后一行摘要。没有这次输出，就不能说通过。

建议测试文件：

| 编号 | 测试文件 |
|---|---|
| P0 | `backend/tests/llm/test_client.py` |
| P1 | `backend/tests/graph/test_interrupt.py` |
| P2 | `backend/tests/importing/test_catalog.py` |
| P3 | `backend/tests/retrieve/test_parent_child.py` |
| P4 | `backend/tests/retrieve/test_rerank_cap.py` |
| P5 | `backend/tests/scoring/test_quote_and_weight.py` |
| P6 | `backend/tests/review/test_demo_conflicts.py` |
| P7 | `backend/tests/report/test_report_and_eval.py` |
| P8 | 前端测试命令在 P8 开始时写入 `frontend/package.json`，再跑一次后端全量 pytest |

P8 之前额外跑：

```text
& D:\LEARN\AI\programs\AgentTask\env\Scripts\python.exe -m pytest backend/tests -q
```

### 7.2 验收场景

下列全部发生，才算首期完成。

- 可以选择三道赛题并读到硬性条件。
- 板凳龙：412 s 与 386 s 同时标出并可定位；「忽略板凳宽度」出现在假设证据里；未讨论「两段圆弧半径 2 倍且相切」为证据不足。
- 种植策略：缺口含豆类三年约束和 50% 降价 / `result1_2`；1286 万元与 974 万元冲突。
- 烟幕：22.4 s 与 18.6 s；引用 \[12\] 缺失；160 m/s 不在 70～140 m/s。云团写成静止且没有 3 m/s 下沉时，对应维度不是「充分」。
- 原句对不上或证据不足的维度不进入加权。
- 修改建议每条都能指回审查结果或维度档位。
- 任意页面和导出文本没有奖项、名次、获奖概率。
- 再导入一份符合目录的赛题后，不改智能体代码即可预审。坏包指出字段，已有赛题不变。
- 第 2 版量规只影响新建评审。归档后不能新建，历史仍可打开。
- 评分、审查、报告的源码不按 `cumcm-2024-A` 等题号分支。
- 配置说明里的模型地址只指向兼容接口。
- 15 页以内样例，从确认章节到出报告，演示环境 3 分钟内结束；超时能看到停在哪一步。
- 评测页对 15 篇给出三项指标，并能点进单篇。

百分比不在本手册写死。评测脚本的实际输出记在 `docs/plan/progress.md`。

### 7.3 检索与图的核对

- Chroma 集合里不存在父块全文。
- 每维送入模型的正文片段不超过 4 段。
- 五张 HTML 能用浏览器单独打开。`deliver --json` 的结果保留在 `docs/diagrams/*.deliver.json`。

---

## 8. 交付物清单

| 交付物 | 路径 | 所属编号 |
|---|---|---|
| 本执行手册 | `执行手册\V1\paper-review.md` | 立项时已有 |
| 计划三件套 | `Projects/paper-review/docs/plan/` 下 `task_plan.md`、`findings.md`、`progress.md` | P0 |
| 项目说明 | `Projects/paper-review/CLAUDE.md` | P0 |
| 环境样例 | `Projects/paper-review/.env.example` | P0 |
| 依赖 | `Projects/paper-review/backend/requirements.txt` | P0 |
| Compose | `Projects/paper-review/compose.yaml` | P0 |
| 模型客户端 | `backend/app/llm/client.py` | P0 |
| 五张图 | `docs/diagrams/*.json` 与对应 `.html` | P0～P3 |
| 赛题包 | `data/contests/` 三道题 | P2 |
| 样例论文 | `data/samples/` 3 篇演示 + 12 篇评测 | P6 |
| 后端模块 | graph、importing、retrieve、review、scoring、report | P1～P7 |
| 测试 | `backend/tests/` | 每个编号 |
| 前端五页 | `frontend/src/views` | P8 |
| 评测输出 | 写入 `progress.md` 的三项数字 | P7、P8 |

不交付：本地模型权重、优秀论文原文、奖项预测接口、第二个虚拟环境。

---

## 9. Skills 缺口

`D:\.skills` 已覆盖测试先行、计划执行、Vue、PDF 抽文本、接口设计和完成前核对。下面四项没有对应技能。没有它们也能按本手册开发，但代理容易把接口和检索写偏。

| 欠缺 | 为什么本项目需要 | 现有技能盖不住的部分 | 建议 |
|---|---|---|---|
| archify | P0～P3 要交付五张可校验的交互图 | 清单中无此目录 | 按第 6.2 节安装，并复制到 `D:\.skills\archify` |
| LangGraph 检查点与 interrupt | P1 的暂停、恢复、按 `review_id` 持久化 | `multi-agent-patterns` 只讲协作形态，没有 `interrupt()` / `Command(resume)` 的写法 | 补一个只含本项目状态图契约的技能，或在 P1 提示词里粘贴 LangGraph 官方 interrupt 示例。不要用自由 ReAct 技能替代 |
| 父子块检索与重排 | P3、P4 的过滤、父块回取、最多 4 段 | 没有 Chroma 或 rerank 技能 | 以本手册 P3、P4 的测试要点为契约。不必先写通用 RAG 技能 |
| OpenAI 兼容客户端 | 全项目只有一个 HTTP 出口，字段读法已冻结 | 没有「只读 message.content / data[].embedding」的技能 | P0 的 mock 测试就是契约。技能可以后补，不要现在引入厂商 SDK |

不需要为 MySQL、Docker、Vue、PDF、pytest 再找新技能。`sql-optimization` 留到评测变慢以后再用，P0 不要上。

---

## 10. 开工顺序

1. 人确认云端密钥准备好，但先不写入仓库。
2. 安装 archify，并确认 `D:\.skills\archify\SKILL.md` 存在。
3. 从 P0 的提示词模板开始。P0 的 pytest 退出码为 0 且运行时图 deliver 成功后，再写 P1。
4. 每个编号结束时更新 `progress.md`。需要偏离本手册时，先在 `findings.md` 写 Ruling，再改代码。
