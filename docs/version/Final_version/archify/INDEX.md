# Archify 图集索引

以下图均基于当前项目代码与 `PROJECT_DOC.md` 的事实清单生成。每张图保留 Archify 候选源文件、最终 HTML，以及从最终 HTML 内联 SVG 提取的 `.svg` 和浏览器视觉校验导出的 `.png`。

| 图名 | Archify 源文件 | 导出文件 | 用途 |
|---|---|---|---|
| system-architecture | [system-architecture.json](system-architecture.json) | [HTML](system-architecture.html) · [PNG](system-architecture.png) · [SVG](system-architecture.svg) | 30 秒理解用户、FastAPI、LangGraph/Agent、RAG/工具/记忆、LLM 与 Chroma/MySQL/模型 API 边界。 |
| rag-pipeline | [rag-pipeline.json](rag-pipeline.json) | [HTML](rag-pipeline.html) · [PNG](rag-pipeline.png) · [SVG](rag-pipeline.svg) | 展示查询改写、向量路径/MySQL 回退、三类文档路由、去重、rerank、Top-K、上下文与生成。 |
| agent-tool-call-sequence | [agent-tool-call-sequence.json](agent-tool-call-sequence.json) | [HTML](agent-tool-call-sequence.html) · [PNG](agent-tool-call-sequence.png) · [SVG](agent-tool-call-sequence.svg) | 展示人工确认、模型工具调用、Schema/规则、执行、可重试网络错误、不可盲重试输入错误、审计与回填。 |
| agent-loop-control | [agent-loop-control.json](agent-loop-control.json) | [HTML](agent-loop-control.html) · [PNG](agent-loop-control.png) · [SVG](agent-loop-control.svg) | 展示规划—工具—观察循环及 12 次模型、24 次工具、150 秒、递归上限和强制提交出口。 |
| memory-layering | [memory-layering.json](memory-layering.json) | [HTML](memory-layering.html) · [PNG](memory-layering.png) · [SVG](memory-layering.svg) | 区分 `ReviewState`/`ToolContext` 工作状态、MySQL 会话/评审记录、AgentStep 日志和删除入口。 |
| eval-and-attribution | [eval-and-attribution.json](eval-and-attribution.json) | [HTML](eval-and-attribution.html) · [PNG](eval-and-attribution.png) · [SVG](eval-and-attribution.svg) | 分开当前评测与计划指标，并把失败归因到切片问题、召回跑偏或知识库缺失。 |

## 生成与校验

- 6 张图均使用 Archify `finalize --quality showcase` 生成，并通过 `validate`、`deliver`、`check`、`browser-check`。
- PNG 来自 `visual-check` 的 2048×1320 light capture；SVG 是对应最终 HTML 的唯一内联 `<svg>` 导出。
- `system-architecture.mmd` 是此前保留的 Mermaid 草稿，不是本图集的 Archify 源文件。

## deployment-runtime

未单独生成。当前代码体现的是单体 Compose 运行时（frontend/backend/mysql），Chroma 为应用本地持久状态，未体现独立模型网关、任务队列、日志服务或拆分后的监控服务。新增一张 deployment-runtime 会把尚未存在的服务边界画成事实；相关运行时边界已合并在 `system-architecture` 和 [PROJECT_DOC.md](../PROJECT_DOC.md) 的部署章节中。
