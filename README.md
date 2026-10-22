# paper-review

竞赛论文预审工作台。把一篇数学建模竞赛论文按章节切开，依据该赛题**已发布**的量规逐维选档，每一维必须附一句能在正文里**逐字找到**的原句；再检查数字冲突、范围越界、引用与题目约束，产出可溯源、按优先级排序的修改清单。

三条硬边界，写在需求里，也写在代码与验收里：

1. **不输出奖项、名次、获奖概率。**验收中有一条专门扫这些字样。
2. **引用必须是父块文本的连续子串。**对不上就判「引用失败」，该维保留档位但不进加权。
3. **「证据不足」不换算成分数。**该维直接出局，同时返回还有多少权重没有依据；页面显示「加权未产生」而不是 0 分。

> 当前分支 `V6-Phase-III-Acceptance`（Phase-3 已收口）。最近一次推送说明见 [push_V7](docs/push_version/push_V7.md)。

---

## 1. 现状速览

| 项 | 数值 | 口径 |
|---|---:|---|
| HTTP 接口 | **33** | 业务 17 / 问询 7 / 鉴权 4 / 用户 2 / 大屏 2 / 记录列表 1 |
| 数据表 | **17** | 赛题目录 7 + 评审 4（含产物）+ 账号权限 2 + 问询 2 + 父块与 Agent 轨迹 2 |
| 前端页面 | **10** | 登录、注册、解析、评分、一致性、建议、评测、记录、问询、大屏 |
| 量规结构 | 5 维 × 4 档 | 权重合计 100，全部读数据不读代码 |
| Agent 工具 | **6** | 只有「提交结论」能记录结果 |
| Agent 预算闸 | **4** | 模型 12 次 / 工具 24 次 / 每维 3 步 / 总墙钟 150 s，另有连续无进展检测 |
| 后端测试 | **472 passed** | `pytest backend/tests -q` |
| 前端单测 | **162 passed** | 32 个文件 |
| 浏览器端到端 | **54 passed / 0 failed** | 真起前后端，走 5173 代理 |
| 静态门禁 | **3 个** | 日志窗口、文档编码、容器骨架（17 项） |

## 2. 功能

1. **账号与角色**：注册 / 登录 / 登出；学生 3 条权限，教师 7 条。问询、大屏、全员记录需要教师权限。
2. **论文解析**：粘贴文本、载入样例，或上传 `.md` / `.docx`；生成章节树并判类型，**必须人工确认**才往下走。
3. **分项评分**：Agent 逐维检索 → 读父块全文 → 选档 → 提交。档位只有「充分 / 基本 / 不足 / 证据不足」四值，权重与合计由代码按量规计算。
4. **一致性审查**：数字冲突、范围越界、条件缺失、引用缺失；数字冲突按**指标**归组而不是按单位，带定位。
5. **修改建议**：纯转写不生成，每条带指回上游的编号，顺序固定为「硬问题 → 缺证据 → 表述」。
6. **评测对照**：12 篇有 gold 的语料、60 个维度项；分母 <5 的指标显示「样本过少」，不渲染成百分比、不画折线。
7. **记录总览与 AI 问询**：已评记录重新切块索引后可被提问；回答里的引用必须来自本次检索结果，编造的引用会被删除并计数；统计数字一律由数据库算。
8. **数据大屏**：四档分布、赛题分布、7 日趋势、证据不足率、热点扣分点；聚合有 60 s TTL 并返回 `cached` 标记。

## 3. 页面

| 路径 | 用途 | 权限 |
|---|---|---|
| `/login`、`/register` | 登录、注册 | 公开 |
| `/parse` | 选赛题、输入论文（粘贴/样例/上传）、确认章节树 | 登录 |
| `/scoring` | 量规条文、逐维档位与引用原句、Agent 轨迹 | 登录 |
| `/consistency` | 一致性问题与正文定位 | 登录 |
| `/suggestions` | 带来源的修改清单 | 登录 |
| `/eval`、`/eval/:paperId` | 汇总指标、单篇 gold 逐维对照 | 公开 |
| `/records` | 记录总览、筛选、详情抽屉 | 登录（教师看全部） |
| `/chat` | AI 问询（记录级检索） | `chat:use` |
| `/dashboard` | 可视化大屏 | `dashboard:view` |

## 4. 架构

```text
浏览器（Vue 3 单页应用，10 个页面）
   │  /api 相对路径，开发期由 Vite 代理到 8077
   ▼
FastAPI 接入层（33 条接口，统一 /api 前缀；鉴权、权限、日志中间件、CORS 白名单）
   │
   ├── 评审状态图：parse → confirm（真中断）→ retrieve → score
   │        └── score 内挂 Agent 子层：6 工具 + 4 道预算闸 + 轨迹落库 + 只降不提的自检
   │
   ├── 规则审查（纯函数，不调模型）：数字冲突 / 越界 / 条件缺失 / 引用缺失
   ├── 记录级问询：定点取证 → 引用校验 → 回答（统计走数据库）
   └── 大屏聚合：服务端 GROUP BY + 60 s TTL
   │
   ├── MySQL（17 张表）：赛题目录、量规、父块全文、评审存档、账号权限、问询、产物、轨迹
   ├── Chroma（本地持久化）：短子块（≤200 字）+ 向量 + 8 个单值元数据
   └── 唯一外部出口：对话 / 嵌入 / 重排（httpx，不发厂商 SDK）
```

四个关键取舍：

- **父子块双存储**：子块进向量库做召回，父块全文留 MySQL。送进模型的是段落全文而不是碎片——**引用校验需要比切片更完整的上下文才不会误杀**。
- **人工确认用状态图的真中断**：章节未确认不进评分；恢复时从断点继续，不重跑解析。
- **依赖全部外部注入**：检索器与模型从外面传进编排，编排模块内部不导入模型客户端、不发 HTTP。所以 472 条后端测试一次网络请求都不发；没有模型配置也是合法运行态，走确定性结构回退并标注「这是脚本自检，不是模型结果」。
- **Agent 的自由度被关住**：工具是白名单，读原文限定在本次命中的父块里，提交只认四个合法档位；撞预算闸不崩，走一次强制补交（最多两轮），仍失败标「证据不足」并记录终止原因。

## 5. 环境要求

- Python **3.11**（本工作区使用共享解释器，见下）
- Node.js **22** 与 npm
- MySQL **8.4**（`StartType=Manual`，重启机器后需手动启动）
- Chroma 使用本地持久化目录 `chroma_data/`，不需要单独服务
- 可选：兼容 OpenAI Chat Completions / Embeddings 的模型服务，以及独立的 Cohere 风格 rerank 服务

本工作区不建项目内虚拟环境，统一用：

```powershell
$py = 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe'
```

依赖见 [backend/requirements.txt](backend/requirements.txt)（含 `langgraph` / `langchain` / `chromadb`；不引厂商 SDK、不用 alembic），前端由 `frontend/package-lock.json` 锁定。

## 6. 本地启动

### 1）启动 MySQL 并确认 3306 可连

```powershell
net start MySQL84
# 无管理员权限时用：
# "D:/MySQL/Server8.4/bin/mysqld.exe" --defaults-file="D:/MySQL/my.ini"
```

### 2）准备环境变量

```powershell
Copy-Item .env.example .env
```

至少填 `MYSQL_DSN` 与 `AUTH_SECRET`。**`AUTH_SECRET` 少于 32 字符会直接拒绝签发 token**，登录、上传、问询、大屏都会不可用。`.env` 不入库，仓库里只有 `.env.example`。

### 3）幂等建表（应用启动不会自动建表）

```powershell
& $py -c "from backend.app.importing.db import create_schema; from backend.app.report.models import create_report_schema; from backend.app.report.artifact_models import create_artifact_schema; from backend.app.retrieve.models import create_parent_schema; from backend.app.agent.trace import create_agent_trace_schema; from backend.app.auth.models import create_auth_schema; from backend.app.chat.models import create_chat_schema; [f() for f in (create_schema, create_report_schema, create_artifact_schema, create_parent_schema, create_agent_trace_schema, create_auth_schema, create_chat_schema)]; print('tables ready')"
```

七个建表函数都是幂等的，重复执行是空操作。项目没有迁移工具，加列走幂等 DDL。

### 4）导入并发布赛题

```powershell
$base = 'http://127.0.0.1:8077/api'
foreach ($id in @('cumcm-2024-A','cumcm-2024-C','cumcm-2025-A')) {
  $body = @{ package_dir = "data/contests/$id" } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "$base/imports" -ContentType 'application/json' -Body $body
  Invoke-RestMethod -Method Post -Uri "$base/contests/$id/publish"
}
```

`data/contests/` 下的 `fixture-extra` 与 `probe-critique-acceptance` 是测试夹具，不要导入。`GET /api/contests` 默认只返回 published。

### 5）启动后端（8077，**没有 `--reload`**）

```powershell
& $py -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077
```

**改过后端代码必须手动重启**，否则你测的是旧进程——这个项目曾因此出现连续六个版本的假绿灯。

自检：`GET /health` 返回版本与运行时长；`GET /readyz` 检查 MySQL 与 Chroma，任一不可用返回 503；`GET /metrics` 暴露计数。

### 6）启动前端（5173）

```powershell
Set-Location frontend
npm ci
npm run dev
```

打开 <http://127.0.0.1:5173>。前端一律走相对路径 `/api`，由 Vite 代理到 8077；**不要直连 8077 访问页面**，端到端测试同理。

### 7）关于账号

注册出来的账号默认是 `student`（`review:create` / `review:read:own` / `eval:view`）。问询、大屏、全员记录需要 `teacher` 角色。仓库**不提供用户管理接口**，开发期按 `scripts/promote_e2e_teacher.py` 的做法手动提权——该脚本是本地测试夹具，只针对 `e2e_teacher`，不是通用管理工具。

## 7. 模型配置

模型服务不是跑通前端、跑确定性回退所必需的。配置写在本机环境或项目根 `.env`，**不要把密钥写进 README、夹具或日志**。

| 环境变量 | 用途 |
|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 对话模型（Chat Completions 兼容） |
| `EMBEDDING_MODEL` | 嵌入模型名称；必需 |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` | 嵌入服务独立地址与密钥；缺省回落 `LLM_*` |
| `RERANK_BASE_URL` / `RERANK_API_KEY` / `RERANK_MODEL` | 重排服务 |
| `MYSQL_DSN` | MySQL 连接串 |
| `AUTH_SECRET` | token 签名密钥，**≥32 字符** |
| `AUTH_TOKEN_TTL_HOURS` | token 时效，默认 8 小时 |
| `CORS_ALLOW_ORIGINS` | 允许的前端源，逗号分隔；**禁止 `*`** |

真实选档要求 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`EMBEDDING_MODEL` 四项齐全；缺任一项走确定性结构回退，响应里带回 `source` 标注。重排是独立配置。评测汇总默认 deterministic，只有显式请求 `GET /api/eval/summary?force=model` 才会跑模型评测并产生调用。

## 8. API

所有业务接口前缀 `/api`；`/health`、`/readyz`、`/metrics` 在根路径。

| 方法与路径 | 说明 | 鉴权 |
|---|---|---|
| `POST /api/auth/register` · `login` · `logout` · `GET me` | 注册、登录、登出、当前用户 | 公开 / Bearer |
| `GET /api/contests` | 赛题列表，默认只返回 published | 公开 |
| `GET /api/contests/{id}/rubric` | 当前已发布量规及各档说明 | 公开 |
| `GET /api/samples` | 样例与评测稿（演示稿与真实论文并列） | 公开 |
| `GET /api/eval/summary` | 汇总指标；默认 deterministic，`?force=model` 跑模型 | 公开 |
| `GET /api/eval/papers/{paper_id}` | 单篇 gold 与逐维差异 | 公开 |
| `POST /api/reviews` | 创建评审，返回待确认章节树；赛题无已发布量规返回 **422** | Bearer |
| `POST /api/uploads` | 上传 `.md` / `.docx` 建评审（20 MB / 200,000 字符） | `review:create` |
| `POST /api/reviews/{id}/resume` | 提交确认后的章节树，继续评审并落存档 | Bearer |
| `GET /api/reviews/{id}` | 评审存档或待确认会话 | Bearer + 归属校验 |
| `GET /api/reviews/{id}/agent-steps` | Agent 轨迹（工具序列与成败） | Bearer + 归属校验 |
| `GET` / `POST /api/reviews/{id}/artifacts[/extract]` | 三类产物读取与确定性抽取 | Bearer + 归属校验 |
| `GET /api/reviews` | 记录总览列表（分页、筛选） | 登录（教师看全部） |
| `GET /api/users`、`/api/users/{id}` | 用户与权限 | `review:read:all` |
| `GET /api/chat/sessions` 等 7 条 | 会话、消息、聚合统计、检索问询 | `chat:use` |
| `GET /api/dashboard/summary`、`/trend` | 大屏聚合与趋势（60 s TTL） | `dashboard:view` |
| `POST /api/imports`、`publish`、`archive`、`rubrics`、`rubrics/{id}/publish` | 赛题目录与量规版本管理 | 公开（仅限本地开发） |

约定：

- 未登录 **401**，权限不足 **403**，赛题不可评 **422**，文件类型不支持 **415**，超限 **413**。
- 上传只收 `.md` 与 `.docx`。**PDF 在扩展名校验处直接 415**，提示先在外部转成文本——真实论文是扫描件，OCR 在上游离线做一次，`data/samples/*.md` 就是那份产物。
- 子路径不要挂成 `/reviews/upload` 这类形式：`GET /reviews/{review_id}` 会把 `upload` 当编号吃掉，返回 **405 而不是 404**。新增子路径用独立前缀，或声明在动态路由之前。

示例：创建一次演示稿评审

```powershell
$body = @{ sample_id = 'bench-dragon'; contest_id = 'cumcm-2024-A' } | ConvertTo-Json
$created = Invoke-RestMethod -Method Post -Uri "$base/reviews" -ContentType 'application/json' -Body $body -Headers @{ Authorization = "Bearer $token" }
$resume = @{ sections = $created.sections } | ConvertTo-Json -Depth 20
Invoke-RestMethod -Method Post -Uri "$base/reviews/$($created.review_id)/resume" -ContentType 'application/json' -Body $resume -Headers @{ Authorization = "Bearer $token" }
```

## 9. 测试与门禁

四道自动门禁加三个静态检查，全部在项目根目录或 `frontend/` 下执行：

```powershell
# 后端：472 passed
$bt = ".pytest_tmp/run-" + (Get-Date -Format 'HHmmss')
& $py -X utf8 -m pytest backend/tests -q --basetemp=$bt

# 前端：构建 + 单测（162 passed）
Set-Location frontend
npm run build
npx vitest run --reporter=dot

# 浏览器端到端：54 passed（需 MySQL 与 8077 可用；从 5173 进才吃到代理）
npx playwright test --reporter=list
Set-Location ..

# 三个静态门禁，均要求 EXIT=0
& $py -X utf8 scripts/check_logs.py
& $py -X utf8 scripts/check_docs_encoding.py docs --strict
& $py -X utf8 scripts/check_container_skeleton.py
```

注意三点：

- **每次都换一个新的 basetemp 目录**。复用旧的 `pytest-of-<user>` 会在 session 开始时触发批量清理，本机安全策略会直接杀掉进程，表现为「N 个点全过但没有汇总行、退出码 1」。
- 后端测试用隔离的小库与假的模型，**不发一次网络请求**；端到端则会写真实表，接口没有删除路径，这是挂账的取舍而不是漏做。
- 端到端登录态由 `global-setup` 注册固定账号并写 `storageState`；账号已存在则改登录，产物在 `frontend/tests/e2e/.auth/`（不入库）。

## 10. 项目结构

```text
backend/app/
  api/           路由与应用装配（含鉴权、日志、CORS、健康检查）
  agent/         Agent 子层：工具注册、预算闸、轨迹、prompt、runner、自检
  auth/          账号、权限、token
  chat/          记录级问询：会话、检索、回答与引用校验、聚合统计
  graph/         评审状态图：解析 → 确认 → 检索 → 评分
  importing/     赛题数据包导入、docx 转换、产物抽取、字符区间
  llm/           对话 / 嵌入 / 重排的唯一 HTTP 客户端
  observability/ 日志、指标、评审编号绑定
  retrieve/      父子块、三路召回、重排
  review/        数字、引用、范围等一致性检查
  scoring/       选档解析、逐字引用校验、降档守卫、加权合计
  report/        量规、评测、修改清单、评审存档、大屏聚合、产物模型
backend/tests/   后端测试（472）
frontend/src/    Vue 页面、组件、组合式函数、API 类型
frontend/tests/  前端单测（162）与端到端（54）
data/            赛题包、真实论文正文、评测样例、上传落盘
docs/            计划、进度、裁决、验收、版本记录、面试材料
scripts/         回填、重建索引、门禁检查、一次性测量
logs/  chroma_data/     运行时产物（不入库）
```

## 11. 已知边界

不写「全部通过」，这些是有意留下的：

1. **容器化是非验收项。**`compose.yaml` 四个服务每个都标了 `UNVERIFIED`，`backend/Dockerfile` 首行也标了；开发机没有 Docker，**镜像从未构建**，`frontend/` 没有 Dockerfile，`chromadb/chroma:1.5.9` 这个 tag 未验证。
2. **不做在线 PDF 解析、不做在线 OCR。**真实扫描件靠离线 OCR 转成 Markdown 后上传，运行时只收 `.md` / `.docx`。
3. **检查点放在内存。**进程重启靠数据库快照回写，不支持多副本；换持久化检查点只需替换装配处传入的对象。
4. **评测集小且偏斜。**12 篇 / 60 个维度项，「基本」占多数，档位一致率不宜当作模型能力结论；标注集扩容列入下一期。
5. **`run_eval()` 不注入 Agent 链路。**评测数字不覆盖工具调用、自检降档与预算终止，这些由轨迹表单独观察。
6. **不做内容级「选错题」判定。**只保证无已发布量规的赛题不出结果，不保证论文与题目匹配。
7. **无租户概念。**单实例、单一数据域；多用户权限已有，多租户明确不做。

## 12. 文档索引

| 文档 | 内容 |
|---|---|
| [推送说明 V7](docs/push_version/push_V7.md) | 三期改动范围、接口与数据现状、已知边界、怎么验 |
| [开发进度](docs/plan/progress.md) | 每个版本的命令、退出码与末行 |
| [实现裁决](docs/plan/findings.md) | 冲突时的裁决记录与原因 |
| [验收报告](docs/plan/acceptance/) | 首期 18 条、各阶段报告、三期总验收 |
| [面试手册](docs/interview/项目面试手册.md) / [自测清单](docs/interview/项目自测问题清单.md) | 讲解口径与自测题（**首期视角，体量数字以 README 与本文件为准**） |
| [全面问题清单](docs/questions/项目全面问题清单.md) | 282 题，覆盖到当前版本 |
| [口头讲解逐字稿](docs/项目讲解逐字稿.md) | 4 分半主稿 + 60 秒版 + 打断速答 |
| [命名规范](docs/version/v1.0.2_命名规范.md) | 版本号与文件命名 |

## 13. 数据快照（开发库，非承诺值）

截至 Phase-3 收口：`review` 262、`review_dimension` 1300、`review_session` 388、`review_artifact` 24、`chat_message` / `chat_session` 33 / 61、`user` 6、`paper_parent` 12299、`agent_step` 6700；向量库 29676 条（`paper_child` 29031 + `review_record` 645），覆盖 260 个评审、8457 个父块。这些数字会随本地实验变动，**不要拿来当断言基线**。
