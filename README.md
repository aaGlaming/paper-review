# paper-review

竞赛论文预审工作台（Competition Paper Pre-review Workbench）。

上传或选择一篇竞赛论文，系统按赛题自己的评分规则（量规）逐维给出**档位**与**论文原句**，跑一遍**一致性审查**（数字冲突、越界、漏条件、引用缺失），最后产出**按修改顺序排列的修改清单**。每一维的判断都能回到量规条款和论文切片，证据不够时明确写成「证据不足」，不把缺项算成低分或高分。

代码仓库：https://github.com/aaGlaming/paper-review

---

## 1. 它由五步组成

```text
① 论文解析     按标题切章节树 → 人工确认（人机回环，确认前不评分）
② 分项评分     按量规逐维选档（充分 / 基本 / 不足 / 证据不足）+ 给出论文原句
③ 一致性审查   数字冲突、越界、未提到条件、缺少情形、引用缺失
④ 修改建议     按「先改硬伤 → 再补证据 → 最后改表述」排列，每条指回上游
⑤ 评测对照     15 篇自建论文上的三项指标汇总
```

前四步是同一次预审的流水线，第五步是对系统自身的评测。

## 2. 五个页面

| 路由 | 页面 | 做什么 |
|---|---|---|
| `/parse` | 论文解析 | 选题 / 粘贴正文 / 一键填入演示稿 → 章节树 → 确认 |
| `/scoring` | 分项评分 | 逐维档位、论文原句、切片编号；证据不足单独配色 |
| `/consistency` | 一致性审查 | 冲突列表，点击证据滚动到对应字符偏移 |
| `/suggestions` | 修改建议 | 三段清单，每条带上游指针 |
| `/eval` | 评测对照 | 三项指标 + 口径 + 来源；`/eval/:paperId` 为单篇占位 |

## 3. 当前进度

**P0～P8 十个阶段全部完成**（里程碑 v0.1.0～v0.9.0）。四道门禁全绿：

| 门禁 | 结果 |
|---|---|
| `npm run build`（含 `vue-tsc --noEmit`） | 退出码 0 |
| `npx vitest run` | **82 passed**（11 个 spec） |
| `npx playwright test` | **12 passed**（真浏览器，走 5173 代理） |
| `pytest backend/tests -q` | **134 passed** |

各阶段验收要点（依据 `docs/开发任务拆解与迭代流程.md` §6～§14）：

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0 地基 | 云端模型客户端、单 HTTP 出口、`.env.example` 无密钥 | 通过 |
| P1 解析暂停 | LangGraph 章节树 + `interrupt()` 人机回环 | 通过 |
| P2 赛题数据 | 三道赛题可发布，坏包整包拒绝并指出文件与字段 | 通过 |
| P3 父子块检索 | 先按赛题过滤子块，再取 MySQL 父块 | 通过 |
| P4 重排与再检索 | 每维最多 4 段，证据不足才再查一轮 | 通过 |
| P5 选档与子串 | 原句必须是切片连续子串，否则该维不加权 | 通过 |
| P6 规则审查 | 三篇演示的数字 / 引用 / 越界 / 种植缺口被标出 | 通过 |
| P7 报告与评测 | 修改清单只转写已校验结果；15 篇出三项数字 | 通过 |
| P7 补齐（v0.8.1） | 补上排期空洞里的 `POST /api/reviews` 与 `/resume` | 通过 |
| P8 页面 | 五个页面可填入示例，全链路走通 | 通过（1 条挂账，见 §8） |

## 4. 技术栈

- **后端**：Python 3.11 + FastAPI + SQLAlchemy 2 + MySQL 8.4 + LangGraph + Chroma
- **前端**：Vue 3.5 + Vite 8 + Element Plus 2.14 + vue-router 5 + TypeScript
- **测试**：pytest（后端）、vitest + jsdom（前端单元）、@playwright/test（真浏览器 E2E）
- **模型**：只接 OpenAI 兼容接口（`/chat/completions`、`/embeddings`），不部署本地模型

## 5. 目录结构

```text
paper-review/
├── backend/
│   ├── app/
│   │   ├── api/          11 条路由（唯一 HTTP 出口在 llm/client.py）
│   │   ├── graph/        LangGraph 状态图（parse → confirm → score）
│   │   ├── scoring/      选档解析、子串校验、加权合计
│   │   ├── review/       一致性审查（数字 / 引用 / 越界 / 情形）
│   │   ├── retrieve/     父子块过滤检索与重排
│   │   ├── report/       量规、修改清单、评测、存档
│   │   ├── importing/    赛题数据包导入与目录管理
│   │   └── llm/          模型客户端
│   └── tests/            134 个用例
├── frontend/
│   ├── src/
│   │   ├── views/        五个页面（中文文件名）
│   │   ├── components/   章节树、正文阅读器、步骤指示器、维度卡、冲突条、建议条、指标卡
│   │   ├── composables/  共享状态、词表、偏移定位、形状判别
│   │   ├── api/          接口封装与类型（字段名照抄实测响应）
│   │   ├── router/       7 条路由
│   │   └── styles/       tokens.css（设计令牌 + Element Plus 主题覆盖）
│   └── tests/            11 个单元 spec + 6 个 E2E spec
├── data/
│   ├── contests/         四道赛题数据包（三道已发布 + fixture-extra）
│   └── samples/          3 篇演示稿 + 15 篇评测论文（12 篇有 gold）
├── docs/
│   ├── plan/             progress.md、task_plan.md、findings.md
│   ├── version/          版本化提示词文档（v1.0.0～v1.8.5）+ 命名规范
│   └── diagrams/         运行架构图
├── compose.yaml          四服务占位（frontend / backend / mysql / chroma）
├── CLAUDE.md             项目约束
└── .env.example          环境变量键名模板
```

---

## 6. 怎么启动

### 6.1 前置条件

| 项 | 要求 |
|---|---|
| Python | **`D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe`**（3.11.16，依赖已装在这个共享环境里，**不要**在项目内建虚拟环境） |
| Node | v22.22.2（`D:\WorkBuddyData\binaries\node\versions\22.22.2-6\node.exe`） |
| MySQL | 8.4，端口 3306，库名 `paper_review` |
| 模型 | 可选。不配就走确定性结构回退，页面全链路可用 |

> **MySQL 若没在跑**：本机 `MySQL84` 服务的启动类型是 `Manual`，开机不会自启。用管理员权限执行：
>
> ```powershell
> Start-Process "D:\MySQL\Server8.4\bin\mysqld.exe" -ArgumentList "--defaults-file=D:\MySQL\my.ini" -WindowStyle Hidden
> ```
>
> 确认监听：`Get-NetTCPConnection -LocalPort 3306 -State Listen`

### 6.2 配置环境变量

```bash
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
cp .env.example .env
```

编辑 `.env`，至少填数据库连接（其余模型键留空即走确定性回退）：

```text
MYSQL_DSN=mysql+pymysql://root:123456@127.0.0.1:3306/paper_review?charset=utf8mb4
```

`.env` 已被 `.gitignore` 忽略，不会进仓库。

### 6.3 建表（幂等，可重复跑）

```bash
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -c "from backend.app.importing.db import create_schema; from backend.app.report import create_report_schema; create_schema(); create_report_schema(); print('tables ready')"
```

两个函数都用 `create_all()`，表已存在时是空操作，不会删数据。

### 6.4 导入并发布赛题（一次性）

```bash
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077
```

后端起来后，另开一个终端，对三道首批赛题各做一次「导入 → 发布」：

```bash
# 把 cumcm-2024-A / cumcm-2024-C / cumcm-2025-A 各跑一遍
curl -X POST http://127.0.0.1:8077/api/imports -H "Content-Type: application/json" -d "{\"package_dir\":\"data/contests/cumcm-2024-A\"}"
curl -X POST http://127.0.0.1:8077/api/contests/cumcm-2024-A/publish
```

> 若本机 curl 走了代理报 502，改用 `curl --noproxy "*"` 或直接调 `catalog.import_package()`。

发布后 `GET /api/contests` 应返回**恰好三道** `published` 赛题——页面的下拉列表就是这个接口。

### 6.5 启动前端

```bash
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
npm ci
npm run dev
```

### 6.6 打开页面

浏览器访问 **http://127.0.0.1:5173**（会自动跳到 `/parse`）。

典型用法：选题 → 点一篇演示稿「填入」→ 等章节树出来 → 确认章节树 → 看评分 / 审查 / 修改建议 → 去 `/eval` 看三项指标。

> **两个端口的分工**：后端在 `8077`，前端 dev server 在 `5173`。后端**没有 CORS 中间件**，所以前端一律用相对路径 `/api/...`，由 Vite 代理到 `8077`。浏览器直连 8077 会被 CORS 挡死，且报错不指向根因。

> **端口被占用（`[Errno 10048] ... 通常每个套接字地址只允许使用一次`）**：说明 8077 上已有一个后端实例（比如上一次没关干净的 uvicorn，或 Playwright 的 `webServer` 没退）。用下面这条查 + 杀：
>
> ```powershell
> $c = Get-NetTCPConnection -LocalPort 8077 -ErrorAction SilentlyContinue
> if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; "已清理" } else { "8077 空闲" }
> ```
>
> 如果那条 python 进程是 Playwright 拉起的，跑一次 `npx playwright test` 也会顺带 `reuseExistingServer` 复用它——**但不建议复用**，因为它可能在测试结束时被一起收走，导致你的 dev 后端突然消失。

## 7. 验证（四道门禁）

任一版本要算"通过"，四条命令退出码必须全为 0：

```bash
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
npm run build                 # 含 vue-tsc --noEmit
npx vitest run                # 82 passed
npx playwright test           # 12 passed（会自动拉起 uvicorn 8077 + vite 5173）

cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q    # 134 passed
```

> **pytest 环境注意**：默认临时根在 `%TEMP%`，清理旧目录时一次删 85 个文件会被本机安全策略拦下，表现为**测试全绿但退出码 1**。解法：
>
> ```bash
> mkdir -p .pytest_tmp
> PYTEST_DEBUG_TEMPROOT=D:\LEARN\AI\programs\AgentTask\Projects\paper-review\.pytest_tmp
> ```
>
> 目录必须先存在，否则 18 个用例在 setup 阶段报 `FileNotFoundError`。

## 8. 已知限制（挂账，等补后端或接模型）

| 缺口 | 影响 | 前置条件 |
|---|---|---|
| **量规条文无接口** | 评分页只能显示 `dimension_code`，显示不了维度中文名、权重、四档说明 | 加「取量规维度」接口 |
| **加权恒为 0** | 未接模型时 `score` 四个数都是 0，页面显示「加权未产生」而不是分数 | 接入模型 |
| **审查结果不落库** | `GET /api/reviews/{id}` 存档不含 `change_list`，历史记录看不到审查清单 | findings 落库 |
| **无单篇评测接口** | `/eval/:paperId` 只能显示缺口说明，看不到系统档位与 gold 的逐维差异 | 加单篇评测接口 |
| **解析产物不全** | 主张 / 表格 / 文内引用后端未产出，解析页右栏为预留位 | 后端补解析产物 |
| **只收 Markdown 文本** | 不支持 PDF / docx 上传 | 加文件解析 |
| **`compose.yaml` 是空壳** | 四个服务只有名字，没有可运行的编排配置 | 部署里程碑 |

另外：接入真实模型后，需求 §12.2 里几条依赖模型判断的必现结果（如「两段圆弧半径 2 倍且相切」判为证据不足、种植策略两个金额标红）才会完整出现。

## 9. 接口一览

11 条路由，前缀 `/api`：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/contests` | 赛题列表（默认只返回 `published`） |
| GET | `/samples` | 样例列表（3 篇演示 + 12 篇有 gold） |
| GET | `/eval/summary` | 三项评测指标 |
| POST | `/reviews` | 创建评审（`paper_text` 与 `sample_id` 互斥） |
| POST | `/reviews/{id}/resume` | 确认章节树并出报告 |
| GET | `/reviews/{id}` | 读存档（已落档返回 7 字段；只有会话快照返回章节树） |
| POST | `/imports` | 导入赛题数据包（整包校验） |
| POST | `/contests/{id}/publish` | 发布赛题 |
| POST | `/contests/{id}/archive` | 归档赛题 |
| POST | `/contests/{id}/rubrics` | 复制出 `version + 1` 的 draft 量规 |
| POST | `/rubrics/{id}/publish` | 发布新版本量规 |

## 10. 文档

| 文档 | 内容 |
|---|---|
| `docs/plan/progress.md` | 每版命令、退出码、末行与补充说明 |
| `docs/plan/task_plan.md` | 十个里程碑的状态表 |
| `docs/plan/findings.md` | 裁决记录（`决定 — 原因 — 做错的代价`） |
| `docs/version/v1.0.2_命名规范.md` | 版本化文档命名规范 |
| `docs/version/10.16/v1.8.*` | P8 六份页面提示词 |
| `CLAUDE.md` | 项目硬约束（必读） |

---

**两条红线**：不输出奖项、名次、获奖概率；评分、审查、报告不按题号写分支，三道首批赛题的差异只体现在 `constraint` 与 `rubric` 数据里。
