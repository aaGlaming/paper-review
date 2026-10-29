# 项目图表目录

以下 29 张图对应 `C:\Users\36194\Desktop\6.md` 的完整清单。每张图均提供 HTML 与 Archify JSON 源文件。

| # | 图表 | HTML | JSON |
|---:|---|---|---|
| 1 | 系统运行时架构 | [查看](01-runtime-architecture.html) | [JSON](01-runtime-architecture.json) |
| 2 | 后端依赖分层 | [查看](02-backend-dependency-layers.html) | [JSON](02-backend-dependency-layers.json) |
| 3 | 前端依赖分层 | [查看](03-frontend-layers.html) | [JSON](03-frontend-layers.json) |
| 4 | P20–P26 能力范围 | [查看](04-phase3-capabilities.html) | [JSON](04-phase3-capabilities.json) |
| 5 | 评审主流程 | [查看](05-review-main-path.html) | [JSON](05-review-main-path.json) |
| 6 | 上传与产物抽取 | [查看](06-upload-artifact-workflow.html) | [JSON](06-upload-artifact-workflow.json) |
| 7 | Agent 评审循环与预算闸 | [查看](agent-review-loop.workflow.html) | [JSON](agent-review-loop.workflow.json) |
| 8 | 问答路由 | [查看](08-qa-routing.html) | [JSON](08-qa-routing.json) |
| 9 | 门禁与交付 | [查看](09-gates-delivery.html) | [JSON](09-gates-delivery.json) |
| 10 | 检索时序 | [查看](10-retrieval-sequence.html) | [JSON](10-retrieval-sequence.json) |
| 11 | 确认章节到评审报告的调用时序 | [查看](review-confirm-scoring.sequence.html) | [JSON](review-confirm-scoring.sequence.json) |
| 12 | 登录与鉴权时序 | [查看](12-auth-sequence.html) | [JSON](12-auth-sequence.json) |
| 13 | DOCX 上传时序 | [查看](13-docx-upload-sequence.html) | [JSON](13-docx-upload-sequence.json) |
| 14 | Parent–Child 数据流 | [查看](14-parent-child-dataflow.html) | [JSON](14-parent-child-dataflow.json) |
| 15 | 大屏服务端聚合 | [查看](15-dashboard-aggregation.html) | [JSON](15-dashboard-aggregation.json) |
| 16 | 评测数据流 | [查看](16-evaluation-dataflow.html) | [JSON](16-evaluation-dataflow.json) |
| 17 | 评审生命周期 | [查看](17-review-lifecycle.html) | [JSON](17-review-lifecycle.json) |
| 18 | 量规生命周期 | [查看](18-rubric-lifecycle.html) | [JSON](18-rubric-lifecycle.json) |
| 19 | 账号生命周期 | [查看](19-account-lifecycle.html) | [JSON](19-account-lifecycle.json) |
| 20 | 评审主数据关系 ERD | [查看](business-review-core.erd.html) | [JSON](business-review-core.erd.json) |
| 21 | 赛题与量规 ERD | [查看](21-contest-rubric-erd.html) | [JSON](21-contest-rubric-erd.json) |
| 22 | Section 解析树 | [查看](22-section-parsing-tree.html) | [JSON](22-section-parsing-tree.json) |
| 23 | 权限关系树 | [查看](23-permission-tree.html) | [JSON](23-permission-tree.json) |
| 24 | Agent 工具契约 | [查看](24-agent-tool-contract.html) | [JSON](24-agent-tool-contract.json) |
| 25 | 前端 API 类型 | [查看](25-frontend-api-types.html) | [JSON](25-frontend-api-types.json) |
| 26 | P16–P26 里程碑 | [查看](26-phase3-milestones.html) | [JSON](26-phase3-milestones.json) |
| 27 | 故障与修复时间线 | [查看](27-incident-fix-timeline.html) | [JSON](27-incident-fix-timeline.json) |
| 28 | P25 三次完整评审耗时 | [查看](review-latency-samples.waterfall.html) | [JSON](review-latency-samples.waterfall.json) |
| 29 | 门禁耗时比较 | [查看](29-gate-duration-waterfall.html) | [JSON](29-gate-duration-waterfall.json) |

## 数据口径

- 第 28 张是三次独立完整评审的端到端耗时样本，不代表解析、检索、评分等阶段耗时拆分；仓库没有这些阶段的独立计时证据。
- 第 29 张比较的是现有门禁运行时长，不代表单个评审请求的阶段耗时。
- P16–P26 的部分历史只精确到日期，时间线按日展示；没有把日期推断成具体时刻。
