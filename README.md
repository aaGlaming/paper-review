# paper-review

竞赛论文预审工作台。系统将论文按章节整理，依据当前赛题已发布的量规逐维选档，并尽量为判断附上可回到正文的原句；随后检查数字、引用、范围和题目约束，生成按优先级排列的修改清单。

评审结果用于辅助检查论文内容。证据不足时会明确标记，不把缺少证据伪装成确定结论。

## 功能

1. **论文解析**：选择赛题并粘贴论文，或载入内置演示稿；系统生成章节树，用户确认后才继续评审。
2. **分项评分**：按量规展示维度、档位、分值和原句；原句必须能在检索到的论文段落中找到。
3. **一致性审查**：标出数字冲突、范围越界、条件缺失和引用问题，并支持定位正文。
4. **修改建议**：按“先处理硬性问题、再补证据、最后改表述”的顺序展示清单和来源。
5. **评测对照**：查看评测集的汇总指标；单篇页面展示 gold 与系统档位的逐维差异。没有 gold 的演示稿会明确说明无法计算差异。

目前输入方式是粘贴文本或使用内置样例，不提供 PDF / DOCX 上传。系统不输出论文奖项、名次或获奖概率。

## 页面

| 路径 | 用途 |
|---|---|
| `/parse` | 选择赛题、输入论文、确认章节树 |
| `/scoring` | 查看量规条文、逐维档位和引用原句 |
| `/consistency` | 查看一致性审查并定位正文 |
| `/suggestions` | 查看带来源的修改清单 |
| `/eval` | 查看汇总评测指标及样例列表 |
| `/eval/:paperId` | 查看单篇逐维对照；无 gold 时显示说明 |

## 环境要求

- Python 3.11
- Node.js 22 和 npm
- MySQL 8.x
- 可选：兼容 OpenAI Chat Completions 与 Embeddings 的模型服务；独立的 Cohere 风格 rerank 服务

在本项目开发工作区，后端使用共享解释器：

```powershell
D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe
```

不要在项目目录创建 Python 虚拟环境。依赖清单见 [backend/requirements.txt](backend/requirements.txt)；前端依赖由 `frontend/package-lock.json` 锁定。

## 本地启动

以下命令以 Windows PowerShell 为例，从项目根目录执行。

### 1. 配置数据库

先启动 MySQL，并确认 3306 端口可连接。复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑项目根目录的 `.env`，至少配置 `MYSQL_DSN`。不要把真实密钥提交到 Git。

首次启动或更新数据库结构时执行幂等建表：

```powershell
& 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe' -c "from backend.app.importing.db import create_schema; from backend.app.report.models import create_report_schema; create_schema(); create_report_schema(); print('tables ready')"
```

### 2. 导入并发布内置赛题

数据库中尚无赛题时，启动后端后，对三份初始数据包各执行一次导入和发布。已发布的赛题无需重复导入。

```powershell
$base = 'http://127.0.0.1:8077/api'
$contests = @('cumcm-2024-A', 'cumcm-2024-C', 'cumcm-2025-A')
foreach ($id in $contests) {
  $body = @{ package_dir = "data/contests/$id" } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "$base/imports" -ContentType 'application/json' -Body $body
  Invoke-RestMethod -Method Post -Uri "$base/contests/$id/publish"
}
```

`GET /api/contests` 默认只列出 published 赛题。导入或发布失败时，先查看 API 返回的 `filename`、`field` 或错误详情。

### 3. 启动后端和前端

在一个终端启动后端：

```powershell
& 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe' -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077
```

另开终端启动前端：

```powershell
Set-Location frontend
npm ci
npm run dev
```

浏览器打开 <http://127.0.0.1:5173>。前端通过 Vite 将 `/api` 请求代理到后端 8077 端口；开发时请通过前端地址访问页面。

## 模型配置

模型服务不是运行前端和确定性回退所必需的。将配置写在本机环境或项目根目录的 `.env` 中，不要把密钥放进 README、测试夹具或日志。

| 环境变量 | 用途 |
|---|---|
| `LLM_BASE_URL` | 对话模型兼容 API 的基础地址 |
| `LLM_API_KEY` | 对话模型密钥 |
| `LLM_MODEL` | 对话模型名称 |
| `EMBEDDING_MODEL` | 嵌入模型名称；嵌入服务地址和密钥可单独设置 |
| `EMBEDDING_BASE_URL` | 嵌入 API 基础地址；未设置时回落到 `LLM_BASE_URL` |
| `EMBEDDING_API_KEY` | 嵌入服务密钥；未设置时回落到 `LLM_API_KEY` |
| `RERANK_BASE_URL` | 重排服务基础地址 |
| `RERANK_API_KEY` | 重排服务密钥 |
| `RERANK_MODEL` | 重排模型名称 |
| `MYSQL_DSN` | MySQL 连接串 |

真实对话选档要求 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 和 `EMBEDDING_MODEL` 均已配置。重排使用独立的 `RERANK_*` 配置。评测汇总默认使用确定性结果；只有显式请求 `GET /api/eval/summary?force=model` 才会运行模型评测并产生模型调用。

应用不会在启动时自动建表。模型 HTTP 请求统一由 `backend/app/llm/client.py` 发出；嵌入或模型调用不可用时，检索按当前配置使用相应的回退或错误处理路径。

## API

所有接口前缀为 `/api`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/contests` | 查询赛题；默认只返回 published |
| GET | `/contests/{contest_id}/rubric` | 查询赛题当前已发布量规及各维度档位说明 |
| GET | `/samples` | 查询内置演示稿与评测样例 |
| GET | `/eval/summary` | 查询汇总指标；默认 deterministic |
| GET | `/eval/summary?force=model` | 显式运行模型评测 |
| GET | `/eval/papers/{paper_id}` | 查询单篇 gold、系统档位及逐维差异 |
| POST | `/reviews` | 创建评审并返回待确认的章节树 |
| POST | `/reviews/{review_id}/resume` | 提交确认后的章节树，继续评审并保存报告 |
| GET | `/reviews/{review_id}` | 查询评审存档或待确认会话 |
| POST | `/imports` | 导入赛题数据包 |
| POST | `/contests/{contest_id}/publish` | 发布赛题 |
| POST | `/contests/{contest_id}/archive` | 归档赛题 |
| POST | `/contests/{contest_id}/rubrics` | 从当前量规复制出新版本草稿 |
| POST | `/rubrics/{rubric_id}/publish` | 发布量规版本 |

创建演示稿评审示例：

```powershell
$body = @{ sample_id = 'bench-dragon'; contest_id = 'cumcm-2024-A' } | ConvertTo-Json
$created = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8077/api/reviews' -ContentType 'application/json' -Body $body
$reviewId = $created.review_id
$resumeBody = @{ sections = $created.sections } | ConvertTo-Json -Depth 20
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8077/api/reviews/$reviewId/resume" -ContentType 'application/json' -Body $resumeBody
```

## 开发与测试

前端构建、单元测试和浏览器端到端测试：

```powershell
Set-Location frontend
npm run build
npx vitest run
npx playwright test
```

后端测试从项目根目录运行：

```powershell
New-Item -ItemType Directory -Force .pytest_tmp | Out-Null
$env:PYTEST_DEBUG_TEMPROOT = (Resolve-Path .pytest_tmp).Path
& 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe' -m pytest backend/tests -q
```

后端测试使用 `backend/tests/conftest.py` 隔离模型配置，测试不会调用真实模型服务。Playwright 测试需要本地 MySQL 和测试所需的本地服务可用。

## 项目结构

```text
backend/app/
  api/          FastAPI 路由与应用装配
  graph/        解析、确认、评分状态图
  importing/    赛题数据包导入、MySQL 目录
  llm/          对话、嵌入和重排的唯一 HTTP 客户端
  retrieve/     证据检索、向量索引及重排
  review/       数字、引用、范围等一致性检查
  scoring/      量规选档、引用校验和加权合计
  report/       量规读取、评测、修改清单与评审存档
backend/tests/  后端测试
frontend/src/   Vue 页面、组件、API 类型与样式
frontend/tests/ 前端单元和浏览器测试
data/           赛题数据包、演示稿和评测样例
docs/plan/      计划、进度、裁决和验收记录
```

## 相关文档

- [版本计划](docs/plan/task_plan.md)
- [开发进度](docs/plan/progress.md)
- [实现裁决](docs/plan/findings.md)
- [首期验收报告 V1](docs/plan/acceptance/report.md)
- [首期验收报告 V2](docs/plan/acceptance/report-V2.md)
