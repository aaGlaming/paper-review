# paper-review 第二版（push_V2 · P8 前端完成）完整说明

> **文档用途**：作为分支 `v0.9.0-p8-frontend` 推送 GitHub 之前的版本档案，供后续开发开始前先行阅读。
> **生成时间**：2026-10-16 20:55
> **代码目录**：`D:\LEARN\AI\programs\AgentTask\Projects\paper-review`
> **代码仓库**：https://github.com/aaGlaming/paper-review
> **本版分支**：`v0.9.0-p8-frontend`（基线为 `main` 的「后端V1推送」`2a6964b`）
> **本版提交**：`1c5d024` — 114 个文件、+16622 / −132 行
> **质量基线**：`npm run build` 0 · `vitest` **82 passed** · `playwright` **12 passed** · `pytest backend/tests` **134 passed**
> **事实来源**：本文件所有结论均为实测（门禁实跑、TestClient 实捕获、SQL 实查、grep 实查、Playwright 实测几何中心）；未使用推测值。

---

## 1. 版本概述与目标

### 1.1 这一版做了什么

第一版（`push_V1`）交付的是**可运行的后端**：解析、检索、选档、审查、报告、评测全链路打通，但前端只有 5 个注释壳，`package.json` 没有任何依赖。

本版把首期最后一个里程碑 **P8「页面」**从零做完，同时补上两个后端接口的排期空洞：

```text
第一版（push_V1）                     本版（push_V2）
─────────────────────────            ─────────────────────────
后端 9 条路由、117 测试       →      后端 11 条路由、134 测试
前端 5 个注释壳、0 依赖       →      前端 5 个真页面、12 个依赖
无设计资产                    →      14 个原创 SVG + 完整设计方案
只有 CLAUDE.md                →      README + 功能说明 + 9 份阶段提示词
```

### 1.2 版本覆盖范围

对应执行手册阶段 **P0～P8**，里程碑 **v0.1.0～v0.9.0**，共 10 个里程碑 + 2 次补丁：

| 里程碑 | 阶段 | 内容 | 状态 |
|---|---|---|---|
| v0.1.0 | P0 地基 | 云端模型客户端契约、环境样例 | ✅ 通过 |
| v0.2.0 | P1 解析暂停 | 章节确认与检查点 | ✅ 通过 |
| v0.3.0 | P2 赛题数据 | 赛题数据包导入与生命周期 | ✅ 通过 |
| v0.4.0 | P3 父子块检索 | 元数据过滤 + 父块回取 | ✅ 通过 |
| v0.5.0 | P4 重排与再检索 | 三路合并、4 段上限、两轮收敛 | ✅ 通过（经 **v0.5.1** 补丁收口） |
| v0.6.0 | P5 选档与加总 | 选档、原句子串校验、加权合计 | ✅ 通过 |
| v0.7.0 | P6 规则审查 | 数字冲突、引用、越界、情形缺失 | ✅ 通过 |
| v0.8.0 | P7 报告与评测 | 修改清单、评审持久化、评测三项指标 | ✅ 通过 |
| **v0.8.1** | P7 补完 | **补齐 `POST /api/reviews` 与 `/resume` 两条排期空洞** | ✅ 通过（本版新增） |
| **v0.9.0** | P8 页面 | **五个页面 + 工程脚手架 + 门禁体系 + 手稿风格** | ✅ 通过（本版新增，6 个阶段全过） |

**尚未包含**：v1.0.0（需求第十二章逐条总验收）。

### 1.3 交付形态

| 层 | 第一版 | 本版 |
|---|---|---|
| 后端 | 可运行，9 条路由 | 可运行，**11 条路由** |
| 前端 | 5 个注释壳，0 依赖 | **可运行**：Vue 3.5 + Vite 8 + TS，5 个真页面，82 单测 + 12 E2E |
| 设计 | 无 | `docs/design/` 完整方案 + 14 个原创 SVG |
| 文档 | CLAUDE.md | README + 功能说明 + 9 份阶段提示词 + 命名规范 |
| 容器 | 四服务空壳 `{}` | 仍为空壳（属部署里程碑） |

### 1.4 两套版本号（勿混用）

| 体系 | 范围 | 用途 |
|---|---|---|
| **里程碑版本** | `v0.1.0` ～ `v1.0.0` | 项目做到哪一步 |
| **文档版本** | `v1.x.y` | 提示词文档自身：第二位对齐执行手册阶段号，第三位默认是修订号 |

P8 期间第三位**改作子任务序号**（`v1.8.0`～`v1.8.7` 共 8 份），此模式下已发出文档的更正一律**原地勘误**。规范原文见 `docs/version/v1.0.2_命名规范.md`（本版由 v1.0.1 升版，新增第 5 节）。

---

## 2. 本版新增内容详解

### 2.1 后端：v0.8.1 补齐两条排期空洞的接口

这是本版最重要的后端改动，解决的是一个**文档交叉核对机制缺失**导致的问题。

**问题**：执行手册 §3.6「接口（先于代码冻结）」列了 9 条路径，其中 `POST /api/reviews` 与 `POST /api/reviews/{id}/resume` 被冻结、被任务文档 §14（P8）当"已有的"引用，却**从未出现在 v0.1.0～v0.8.0 任何一版的任务清单里**。后果是 `save_review` 只有测试在调、没有 HTTP 入口，`review` 表 0 行，`GET /api/reviews/{id}` 永远 404。

**处置**：新增两条路由 + 一张表 + 一个只读模块。

| 新增/修改 | 内容 |
|---|---|
| `backend/app/api/routes.py` | 9 → **11 条路由**；新增 `POST /reviews`（201）与 `POST /reviews/{review_id}/resume`；模块注释重写（删掉 P7 自造的「属后续版本」禁令） |
| `backend/app/report/models.py` | 新增 `ReviewSession` 表（`review_id`、`paper_text`、`sections`、`confirmed`、`status`、`updated_at`） |
| `backend/app/report/store.py` | 新增 `save_session` / `load_session`；同一 `review_id` 再次调用是**覆盖**不是新增 |
| `backend/app/report/rubric.py` | **新增只读模块** `load_review_inputs(contest_id, *, session=None)`：按赛题取当前 published 量规的维度与约束；找不到返回空表、`rubric_id` 为 `None`，**不抛错、不兜底到别的赛题** |
| `backend/tests/report/test_review_flow.py` | **15 个测试函数**，覆盖两条路由的 HTTP 行为、互斥校验、空论文拒绝、坏 sample_id 400 |

**检查点恢复的真实语义**（`_restore_snapshot`）：进程重启后用 `update_state(as_node="parse")` 还原快照，`next == ("confirm",)`、`parse_node_calls` 仍为 1（章节树未被重算）。换成 `as_node="confirm"` 会得到 `next == ("retrieve",)`，**整段人工确认被跳过**——这是被明确禁止的。

### 2.2 前端：P8 六个阶段逐版验收

P8 拆成 6 份提示词文档，**一次只做一个页面，当前页过验收才动下一个**。每版都是"先写失败测试 → 看它失败 → 再写实现 → 四道门禁全绿"。

| 文档版本 | 内容 | 关键决策 |
|---|---|---|
| `v1.8.0` | 工程脚手架与门禁体系 | TypeScript；Vite 代理（后端无 CORS）；校样稿方向；四道门禁 |
| `v1.8.1` | 论文解析页 | 人工确认是闸门；章节类型词表前端镜像；不装 Pinia |
| `v1.8.2` | 分项评分页 | 存档是三态；`score` 全 0 不显示"0 分"；定位用真实 `indexOf` |
| `v1.8.3` | 一致性审查页 | 数据源是 `change_list` 审查类条目；全文偏移需拼接校准 |
| `v1.8.4` | 修改建议页 | 三段顺序不重排；两类条目都要正确渲染；`upstream_id` 可见化 |
| `v1.8.5` | 评测对照页 | 单篇缺口如实挂账；`rate===null` 显示无样本；不把百分比当成果 |
| `v1.8.6` | 手稿风格落地 | frontend-design 主导 + ui-ux-pro-max 辅助；零新依赖 |
| `v1.8.7` | 手稿风修复 | 修圈注定位 / 假折线图 / 一致性（**待执行**） |

### 2.3 五个页面各自实现什么

详细功能说明见 `docs/version/explain/v1.0.0_前端功能说明.md`，此处只列骨架：

| 路由 | 页面 | 核心功能 |
|---|---|---|
| `/parse` | 论文解析 | 选题 / 演示稿一键填入 / 粘贴正文（两条路互斥）→ 章节树（类型可改）→ **人工确认**（确认前不评分）→ 已确认结果卡 |
| `/scoring` | 分项评分 | 逐维维度卡：编号 / 档位 / 状态 / 量规条文预留 / 论文原句 / 切片编号 / 定位原句；证据不足单独配色且不给原句不给分；加权只来自后端 |
| `/consistency` | 一致性审查 | 冲突列表（五类 finding_kind）；带偏移的证据可点击 → 滚动到论文里的真实位置并高亮；找不到时诚实标注「按偏移定位」 |
| `/suggestions` | 修改建议 | 三段固定顺序（题目约束与数字冲突 → 证据不足 → 表述）；每条带 `upstream_id` 指回上游；空段不消失 |
| `/eval` | 评测对照 | 三项指标 + 口径 + `matched/total`；`source` 与 `note` 原文可见；样例列表 15 篇；单篇占位说明 |
| `/eval/:paperId` | 单篇占位 | 只显示缺口说明（后端无单篇接口），不臆造 gold |

### 2.4 八个组件

| 组件 | 职责 |
|---|---|
| `AppNav.vue` | 五个页面入口，顺序即流程顺序，激活态下划线 |
| `SectionTree.vue` | 章节树，层级用缩进（不用 01/02/03），每条带类型下拉 |
| `SectionReader.vue` | 选中章节正文原样呈现 + 主张/表格/引用三个预留位 |
| `StageTracker.vue` | 六步指示器，**只点真实观测到的步骤**，禁定时器伪造 |
| `DimensionCard.vue` | 维度卡；证据不足单独配色 |
| `ConflictItem.vue` | 审查条目；证据可点击定位 |
| `SuggestionItem.vue` | 建议条目；带上游指针 |
| `MetricCard.vue` | 指标卡；`rate===null` 显示「—（无样本）」 |

另有四个 composable：`useReviewFlow.ts`（跨页共享状态 + sessionStorage）、`reviewVocabulary.ts`（章节类型 + 六步骤词表，只一处定义）、`reviewShape.ts`（三态判别）、`useOffsetLocator.ts`（偏移定位）。

### 2.5 手稿风格设计资产

`docs/design/` 是一套完整的手稿风格（Sketch / Hand-drawn）设计方案，产出包括：

| 资产 | 数量 | 说明 |
|---|---|---|
| `sketch-style.md` | 409 行 | 设计方案：色彩、字体、布局、元素词典、组件规范、五页草图、落地提示词 |
| `sketch-svg/*.svg` | **14 个原创 SVG** | 箭头 ×2、手绘圈、下划线、卡片边框、铅笔、胶带、放大镜、章节树、清单、折线图、引文标记、流程点、纸张颗粒 |
| `sketch-preview.html` / `.png` | 样张 | 浏览器打开可看全部 SVG 实时效果；PNG 为 Playwright 截图（1200×1600 @2x） |
| `frontend/shot-sketch.mjs` | 工具 | 改了 SVG 后重新出图：在 `frontend/` 下 `node shot-sketch.mjs` |

**SVG 绘制约定**：`stroke="currentColor"`（CSS 可控色）、`stroke-width` 1.2–1.8、`stroke-linecap/linejoin="round"`、`fill="none"`、路径一律微弯不取直、重点形状描两遍（第二遍 `opacity 0.45–0.55` 且略偏移）。

**方案里三个冲突的处置**（写进了设计文档 §2）：

1. **暖纸 vs 冷白纸**：Sketch 规范要 `#F4F0E8`，但项目 `tokens.css` 明令不用暖奶油色，且 `source-scan` 有硬断言「底色蓝分量 ≥ 红分量」（`#F4F0E8` 是 r=244/b=232，断言会失败）。**采用方案 B：保留冷白纸**，手工纸感由纸张颗粒 SVG + 手绘线条 + 衬线引文 + 编辑部排版完成。
2. **手写字体 vs 不引网络字体**：不引入任何网络字体，手写感由 SVG 手写标注 + 系统字体微旋转 + 衬线引文补足。
3. **Editorial 非对称 vs 1040px 工作台**：保留版心，把编辑部感做进版心内部（01–05 等宽大编号、细 rule、7:5 双栏、卡片微旋转）。

### 2.6 测试资产

| 层 | 文件数 | 用例数 | 状态 |
|---|---|---|---|
| 后端 `backend/tests/` | 9 个 | **134** | ✅ 全绿 |
| 前端单元 `frontend/tests/unit/` | 11 个 spec | **82** | ✅ 全绿 |
| 前端 E2E `frontend/tests/e2e/` | 6 个 spec | **12** | ✅ 全绿（真浏览器，走 5173 代理） |

前端单测覆盖：api 层 11 函数、路由 7 条、五页挂载与 `h1` 契约、解析页 15 条、评分页、审查页、建议页、评测页、类型判别、源码扫描（奖项词 / 题号字面量 / 裸色值 / 动效）。

### 2.7 文档体系

| 文档 | 内容 |
|---|---|
| `README.md` | 启动六步（MySQL 拉起 → .env → 幂等建表 → 导入发布 → 前端 dev → 5173）、四道门禁、7 条挂账、11 条接口表 |
| `docs/version/explain/v1.0.0_前端功能说明.md` | 五页八组件功能说明，零代码痕迹 |
| `docs/version/v1.0.2_命名规范.md` | 新增第 5 节「修订号的两种用法」（子任务序号模式） |
| `docs/version/10.16/v1.7.2` | 补齐评审接口与赛题发布（含 9 条冻结路径对账表） |
| `docs/version/10.16/v1.8.0`～`v1.8.7` | P8 八份阶段提示词 |
| `docs/plan/progress.md` | 从 205 行增至 1100+ 行，含 P8 八个阶段的命令/退出码/末行 |
| `docs/plan/findings.md` | 21 → 40+ 条 Ruling |
| `docs/plan/task_plan.md` | v0.9.0 已改「通过」 |

---

## 3. 关键设计决策（本版新增的）

### 3.1 人工确认是一道闸门，不是装饰

`parse → confirm → score` 的图里，`confirm` 节点调 `interrupt()` 交出章节树。**章节树未确认，评分节点调用次数为 0**。理由：解析可能切错、类型可能判错，让机器在错的章节结构上打分没有意义。前端对应表现为：解析页确认前不渲染任何档位，其余四页在没有 report 时显示空态并指回解析页。

### 3.2 三个「不显示」比显示更重要

| 情形 | 错误做法 | 本版做法 |
|---|---|---|
| 证据不足 | 给一个看起来精确的低分 | 单独灰蓝配色，**不给原句、不给任何分数** |
| `score` 四个数全 0（确定性回退） | 显示「总分 0」 | 显示「加权未产生（本次来源 deterministic，未接模型）」+ 列出后端原始值 |
| `rate` 为 null（分母 0） | 显示 0 或 NaN | 显示「—（无样本）」 |

这三条的共同原则来自需求第 41 行：**证据不够时明确写成「证据不足」，不把缺项写成低分或高分**。

### 3.3 定位必须是真实位置

点击「定位原句」或某条证据时，依据是**后端校验过的连续子串**（`quote` 必须逐字出现在论文切片里）。前端在章节正文里找它的真实下标：找到就精确高亮，找不到就按字符偏移大致定位并**明确标注「按偏移定位，未精确匹配」**。绝不编造位置——点了跳到错段落，用户会以为引用对不上，直接摧毁"可溯源"这件核心价值。

高亮用**文本节点三段拼接**（前段 / `<mark>` / 后段），**禁 `v-html`**——论文正文是用户可控输入。

### 3.4 诚实的步骤指示

预审过程在界面上分步可见（赛题对齐 / 按维检索 / 选档 / 规则审查 / 原句校验 / 生成报告），但**后端是同步接口，一次跑完六步，中间态拿不到**。所以：请求进行中只显示「处理中」这个不确定态，**不用定时器假装进度**；失败显示「停在：等待服务返回」，**不补写任何评语**。

"看到假进度"比"看到不确定态"更糟——它会让超时的页面显示一个从未发生的"已完成到第 N 步"。

### 3.5 数据形状先判再用

`change_list` 里有**两种形状**的条目：审查类带 `finding_kind` + `evidence[]{char_start,char_end,text}`；维度类带 `dimension_code` + `evidence[]{text,band,status,chunk_ids}`。类型上两组字段皆可选，页面**先判形状再取字段**——只写一种会在运行时静默取到 `undefined`，表现是"点了没反应"而不是报错。

### 3.6 契约必须迁就既有闸门

`views.spec.ts`、`app-shell.spec.ts`、`smoke.spec.ts`、`source-scan.spec.ts` 是前几版逐版攒下的回归网。本版新增页面时**允许更新它们，但不得放宽断言意图**（例如把「含待实现」断言删掉了事、或给 `data-testid` 断言加 `try/catch` 绕过）。86 个 `data-testid`、每页恰好一个 `h1`、`.vue` 无裸色值、空态文案词表——全部守住。

---

## 4. 尚未完成的内容

### 4.1 手稿风格修复（v1.8.7，提示词已写待执行）

用户截图反馈三个问题，我已实测确认并写成 v1.8.7 提示词：

| 问题 | 根因 |
|---|---|
| 手绘圈跑位 | `DimensionCard.card__band-circle` 同时写 `inset` 与 `width/height`（互相覆盖）；`ConflictItem.conflict__hit-circle` 依赖父级 `position: relative` 但没保证 |
| 评测折线图是假的 | `MetricCard.vue` 三张卡 `import` 同一张静态 `sketch-chart.svg`，三条折线一模一样，**与数据无关** |
| 修改建议页未手稿化 | 五页里四页有手绘语言，唯独建议页是朴素卡片 |

### 4.2 总验收（v1.0.0）

需求第十二章逐条验收尚未执行。

### 4.3 后端接口缺口（挂账）

| 缺口 | 影响 |
|---|---|
| 无「取量规维度」接口 | 评分页只能显示 `dimension_code`，显示不了维度中文名、权重、四档说明 |
| 无单篇评测接口 | `/eval/:paperId` 只能显示缺口说明，看不到系统档位与 gold 的逐维差异 |
| 审查结果不落库 | `GET /api/reviews/{id}` 存档不含 `change_list`，历史记录看不到审查清单 |
| 无文件上传 | 只收 Markdown 文本或 `sample_id` |
| 解析产物不全 | 主张 / 表格 / 文内引用后端从未产出 |

### 4.4 模型未接入

`.env` 已配 DeepSeek（`LLM_BASE_URL=https://api.deepseek.com/v1`、`LLM_MODEL=deepseek-v4-flash`），但**尚未跑过一次真实评审**。当前所有档位来自确定性结构回退，`source='deterministic'`，三项指标是脚本自检不是模型准确率。

**待验证的风险**：`deepseek-v4-flash` 默认开 thinking 模式，而 `parse_scoring_json` 要求返回纯 JSON（解析失败只重试 1 次，共 2 次）。DeepSeek 的思考内容在 `reasoning_content` 字段、代码只读 `content`，理论上不污染，但**首次接入必须实测一次**。

### 4.5 嵌入与重排未接（架构限制）

`chat()` 与 `embed()` **共用同一个 `LLM_BASE_URL`**，而 DeepSeek 没有 `/embeddings` 接口。当前 `embed()` 全项目零调用点、`rerank.py` 只读配置不发请求，所以不影响运行。要接检索链路需给 `embed()` 加独立的 `EMBEDDING_BASE_URL` 键（要改 `client.py`，属另一版）。

免费方案已调研：**硅基流动 `BAAI/bge-m3`（1024 维）+ `BAAI/bge-reranker-v2-m3` 均为免费**，OpenAI 兼容、中国大陆直连。

---

## 5. 已知问题与限制

### 5.1 本版实测发现的环境坑

| 坑 | 表现 | 解法 |
|---|---|---|
| pytest 临时目录清理被安全策略拦截 | 一次删 85 个文件 → **测试全绿但退出码 1** | 先 `mkdir` 项目内目录，再用 `PYTEST_DEBUG_TEMPROOT=<项目内绝对路径>`；目录不存在会导致 18 个用例 setup 阶段 `FileNotFoundError` |
| 本机 curl 默认走代理 | 请求 127.0.0.1 返回 502 | `curl --noproxy "*"` 或用 Python `ProxyHandler({})` 直连 |
| Vite 默认只监听 IPv6 `[::1]:5173` | Playwright 的 `baseURL` 用 `127.0.0.1` 连不上 | `vite.config.ts` 里 `server.host: '127.0.0.1'` |
| `ms-playwright` 缓存原本为空 | E2E 跑不起来 | 先装 chromium（118.1 MiB） |
| `typescript@7.0.2` 与 `vue-tsc@3.3.13` 不兼容 | `ERR_PACKAGE_PATH_NOT_EXPORTED: './lib/tsc'`，构建直接失败 | 降到 **6.0.3**；教训：**peerDependencies 的版本区间不能当相容性证明**，前端依赖必须"装上跑一次" |
| `MySQL84` 服务 `StartType=Manual` | 开机不自启，`Start-Service` 权限不足 | `Start-Process "D:\MySQL\Server8.4\bin\mysqld.exe" -ArgumentList "--defaults-file=D:\MySQL\my.ini" -WindowStyle Hidden` |
| E2E 会写真库 | 无删除接口，行数持续增长 | 接受污染 + 在 `progress.md` 记运行后行数 + 挂账 |

### 5.2 截图色偏（已辟谣）

v1.8.6 执行后用户截图显示整体暖黄，疑似纸底被改成暖纸。**实测：没有**——`--pr-paper` 仍是 `#f6f7f9`、`getComputedStyle(body)` 是 `rgb(246,247,249)`、`source-scan` 的「底色 b≥r」断言仍成立。截图发黄来自截图环境（护眼模式 / 显示器色偏 / 截图工具）。v1.8.7 已明令禁止以"截图偏暖"为由改纸底。

### 5.3 第一版遗留的限制（仍未处理）

- `InMemorySaver` 只在进程内，重启即丢章节检查点（现已用 `review_session` 表部分缓解，但图检查点本身仍未持久化）；
- 错误响应有三种体例（坏包 `{filename,field,detail}` / 业务 `{detail}` / 参数校验 `{detail:[...]}`）；
- `api/app.py` 的 `version="0.3.0"` 是字面量，与实际进度不符；
- 可观测性基础设施为零（无结构化日志、无 `/metrics`、无链路追踪）；
- 三篇演示稿没有 `gold`，评测可算样本 12 篇（需求要 15 篇）；
- `compose.yaml` 仍是四服务空壳。

---

## 6. 后续待开发事项

### 6.1 立即可做（提示词已备好）

| # | 事项 | 文档 |
|---|---|---|
| 1 | 执行 v1.8.7：修圈注定位、假折线图、修改建议页手稿化、一致性统一 | `docs/version/10.16/v1.8.7_修复手稿风格落地问题.md` |
| 2 | 首次接入 DeepSeek 并实测：跑一次完整评审，确认档位 JSON 能正常解析 | 需先填 `.env`（已填），再跑一次 `POST /api/reviews` + `/resume` |
| 3 | 需求第十二章逐条总验收 | 属 v1.0.0 / 文档版本 `v1.9.0` |

### 6.2 需要补后端接口（各需单独一版）

| 事项 | 说明 |
|---|---|
| 「取量规维度」接口 | 让评分页能显示维度中文名、权重、四档说明（需求 §12.3 硬要求） |
| 单篇评测接口 | 让 `/eval/:paperId` 能看系统档位与 gold 的逐维差异 |
| `EMBEDDING_BASE_URL` 独立配置 | 让嵌入能单独指向硅基流动等免费服务（要改 `client.py`） |
| 真实重排客户端 | `build_rerank_client("http")` 现在显式抛 `NotImplementedError`，需授权改 `client.py` |
| 审查结果落库 | 让历史记录也能看到审查清单 |

### 6.3 数据与部署

- 三道赛题数据已装载并 published（`contest` 4 行含 1 道 archived 的 `fixture-extra`）；
- `compose.yaml` 可运行配置（镜像、端口、卷、健康检查）；
- 论文文件上传（PDF / docx）。

---

## 附录 A：本版目录结构（相对第一版的变化）

```text
paper-review/
├── README.md                      ⬜ 新增：启动六步 + 四道门禁 + 挂账清单
├── CLAUDE.md                      项目约束
├── compose.yaml                   四服务空壳（未变）
├── .env.example / .env            7 个键（.env 已配 DeepSeek + MySQL，被 gitignore 覆盖）
├── backend/
│   ├── requirements.txt           12 个锁定依赖
│   ├── app/
│   │   ├── llm/client.py          模型客户端（唯一 HTTP 出口）
│   │   ├── graph/review_graph.py  状态图
│   │   ├── importing/             赛题数据入口
│   │   ├── api/routes.py          ⬜ 9 → 11 条路由（新增 /reviews、/reviews/{id}/resume）
│   │   ├── retrieve/              检索工具层
│   │   ├── scoring/               选档与加总
│   │   ├── review/                规则审查
│   │   └── report/
│   │       ├── change_list.py     修改清单
│   │       ├── evaluation.py      评测
│   │       ├── store.py           ⬜ 新增 save_session / load_session
│   │       ├── models.py          ⬜ 新增 ReviewSession 表
│   │       └── rubric.py          ⬜ 新增只读模块 load_review_inputs
│   └── tests/                     8 → 9 个文件，117 → 134 项用例
├── data/                          4 道赛题 × 5 JSON + 3 篇演示 + 12 篇评测
├── docs/
│   ├── design/                    ⬜ 新增：手稿风格方案 + 14 SVG + 样张
│   ├── diagrams/                  5 张 archify 图
│   ├── plan/                      task_plan / progress / findings
│   ├── push_version/
│   │   ├── push_V1.md             第一版说明
│   │   └── push_V2.md             ⬜ 本文件
│   ├── version/
│   │   ├── v1.0.2_命名规范.md      ⬜ 由 v1.0.1 升版（新增第 5 节）
│   │   ├── 10.15/                 v1.0.0 ～ v1.7.0
│   │   ├── 10.16/                 ⬜ v1.7.2 与 v1.8.0 ～ v1.8.7 共 9 份
│   │   └── explain/               ⬜ v1.0.0_前端功能说明.md
│   └── 开发任务拆解与迭代流程.md
└── frontend/                      ⬜ 从 5 个注释壳 → 完整工程
    ├── package.json               3 deps + 9 devDeps（含 lock）
    ├── index.html / vite.config.ts / vitest.config.ts / playwright.config.ts
    ├── tsconfig.json / tsconfig.node.json / env.d.ts
    ├── shot-sketch.mjs            ⬜ 设计资产截图工具
    ├── src/
    │   ├── main.ts / App.vue / router/
    │   ├── api/                   index.ts（11 函数）+ types.ts
    │   ├── components/            8 个组件
    │   ├── composables/           4 个 composable
    │   ├── styles/                tokens.css + sketch.css
    │   ├── assets/sketch/         14 个 SVG
    │   └── views/                 5 个中文名页面
    └── tests/                     11 unit + 6 e2e
```

## 附录 B：环境与常用命令

```text
# 解释器（唯一，不要在项目内建虚拟环境）
D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe   # Python 3.11.16

# 四道门禁（本版基线）
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
npm run build                 # 含 vue-tsc --noEmit
npx vitest run                # 82 passed
npx playwright test            # 12 passed（自动拉起 uvicorn 8077 + vite 5173）
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q   # 134 passed

# pytest 环境坑（测试全绿但退出码 1 时用）
mkdir -p .pytest_tmp
$env:PYTEST_DEBUG_TEMPROOT="D:\LEARN\AI\programs\AgentTask\Projects\paper-review\.pytest_tmp"

# MySQL（服务 StartType=Manual，开机不自启）
Start-Process "D:\MySQL\Server8.4\bin\mysqld.exe" -ArgumentList "--defaults-file=D:\MySQL\my.ini" -WindowStyle Hidden

# 8077 端口被占用时
$c = Get-NetTCPConnection -LocalPort 8077 -ErrorAction SilentlyContinue
if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }

# 启动后端
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077

# 建表（幂等）
& ... -c "from backend.app.importing.db import create_schema; from backend.app.report import create_report_schema; create_schema(); create_report_schema(); print('tables ready')"

# 启动前端
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
npm run dev                   # → http://127.0.0.1:5173

# 本机 curl 走代理，调 127.0.0.1 要加 --noproxy
curl --noproxy "*" -X POST http://127.0.0.1:8077/api/imports -H "Content-Type: application/json" -d "{\"package_dir\":\"data/contests/cumcm-2024-A\"}"
```

## 附录 C：本版分支与提交

| 项 | 值 |
|---|---|
| 分支 | `v0.9.0-p8-frontend`（从 `main` 的 `2a6964b` 切出） |
| 提交 | `1c5d024` |
| 规模 | 114 个文件，+16622 / −132 行 |
| 分类 | backend 7 · frontend 71 · docs 34 · 其他 2（`.gitignore`、`README.md`） |
| 远端 | https://github.com/aaGlaming/paper-review |
| PR 入口 | https://github.com/aaGlaming/paper-review/pull/new/v0.9.0-p8-frontend |

**推送前安全检查（已执行）**：暂存区无 `.env`、无 `node_modules/`、无 `dist/`、无 `playwright-report/`、无 `test-results/`；`git ls-files --error-unmatch .env` 确认 `.env` 未被追踪；已删除两个临时文件（`frontend/.dev.log`、`frontend/probe-tmp.mjs`）。
