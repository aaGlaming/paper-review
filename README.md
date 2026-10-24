# paper-review

竞赛论文预审工作台：解析论文章节，依据已发布赛题量规逐维检索证据、选档、做一致性检查，并生成可追溯修改清单。

## 项目简介

这是一个 **Agent 工作流系统**，不是普通增强型 Chat：核心流程由 LangGraph 驱动，包含人工确认中断、RAG 检索、专项 Agent、主评审 Agent 和只允许向下调整的 verifier。`/api/chat/*` 是独立的记录级问询功能。

核心边界：

- 引用必须是论文父块中的连续原句。
- “证据不足”不换算成分数。
- 不输出奖项、名次和获奖概率。
- 在线上传只支持 `.md` / `.docx`；PDF/OCR 在外部完成。

## 核心特性

- 人工确认章节后才进入评分。
- 5 个 Agent 角色：`evidence_agent`、`topic_fit_agent`、`coherence_agent`、`review_agent`、`verifier_agent`。
- 16 个工具契约，按角色白名单注册；参数使用 Pydantic schema 校验。
- Chroma child 向量 + MySQL parent 全文；三路召回、去重、可选 rerank、最多 4 个父块。
- MySQL 保存评审、会话、问询、产物和 Agent 轨迹；JSON 日志按模块轮转。
- 默认可走确定性回退；模型、Embedding、Rerank 均通过环境变量配置。

## 架构图

[查看 Archify 最终图集、源文件与导出文件](docs/version/Final_version/archify/INDEX.md)

详细分层、流程、工具 schema、预算、记忆、评测和限制见：[PROJECT_DOC.md](docs/version/Final_version/PROJECT_DOC.md)。

## 快速开始

### 本地运行

要求：Python 3.11、Node.js 22、MySQL 8.4。后端依赖见 [`backend/requirements.txt`](backend/requirements.txt)，前端依赖由 [`frontend/package-lock.json`](frontend/package-lock.json) 锁定。

```powershell
Copy-Item .env.example .env
$py = 'D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe'
& $py -m pip install -r backend/requirements.txt

# 先启动 MySQL，并填写 .env；再显式执行项目的 create_*_schema 建表函数。
& $py -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077
```

另开终端启动前端：

```powershell
Set-Location frontend
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173`。前端通过 Vite 将 `/api` 代理到 `http://127.0.0.1:8077`。首次配置、完整建表、赛题导入发布和模型配置步骤见 [详细项目文档](docs/version/Final_version/PROJECT_DOC.md)。

### Compose

```powershell
Copy-Item .env.example .env
docker compose up -d --build frontend backend mysql
```

Compose 配置见 [`compose.yaml`](compose.yaml)。应用不会在启动时自动建表，也不会自动导入和发布赛题量规。

## 目录结构

```text
backend/      FastAPI、LangGraph、Agent、RAG、MySQL、日志与评测
frontend/     Vue 3、页面、组件、API 类型和测试
data/         赛题包、论文 Markdown、评测 gold
docs/         事实清单、版本文档、架构图、计划与验收记录
scripts/      OCR、索引回填、评测核验和运维检查
compose.yaml  frontend/backend/mysql 容器编排
```

## 文档

- [详细项目文档](docs/version/Final_version/PROJECT_DOC.md)
- [项目事实清单](docs/项目事实清单.md)
- [Archify 最终图集索引](docs/version/Final_version/archify/INDEX.md)
- [部署运维手册](docs/腾讯云Docker-Compose运维手册.md)
- [验收文档](docs/plan/acceptance/)

## License

仓库中未提供 `LICENSE` 文件，授权条款代码中未体现。
