# paper-review 第三期计划（Phase 3）

> **文档版本**：v3.0.0 · 生成时间：2026-10-19（内容承自 2026-10-18 第二期计划，仅整体顺延）
> **文档性质**：第三期总体规划，供评审后按阶段拆解提示词。**第三阶段（Phase 3）文档统一命名 `Phase-3-plan.md`**，与 `Phase-1/paper-review.md`、`Phase-2/Phase-2-plan.md` 并列放在 `docs/version/Phases/` 下。
> **前置状态**：首期（P0～P11）已收口，需求第十二章 **18 条全 ✅**（`docs/plan/acceptance/report-V2.md`）；**Phase-2（P12～P15，Agent 化）收口后本计划才开工**。
> **分支基线**：Phase-2 完成后的 `V5-Phase-II-Agent.Acceptance`；当前代码基线仍是 `V4-Phase-I-Ares.Acceptance`（提交 `48deb6a`）。
> **本次修订（2026-10-19）**：阶段号整体 +4（原 P12～P22 → P16～P26）；提示词命名改为「期内阶段序号 + 子任务序号」（P16→`v3.0.x`）；日志目录新增 `agent/`（共 15 个）；P19 明确复用 Phase-2 的 `PaperRetriever`，禁止另写第二套检索。

---

## 0. 本版修订说明（相对 Phase-2 计划）

本文件内容与 2026-10-18 编好的第二期计划**完全相同**，只做了一件结构性调整：**Agent 化作为新的 Phase-2 插入在前，本计划整体后移为 Phase-3，阶段号统一 +4**。

| 原阶段（Phase-2 计划） | 现阶段（本文件） | 内容 |
|---|---|---|
| P12 日志与监听 | **P16** | 日志目录、结构化事件、`/health` `/readyz` `/metrics` |
| P13 登录注册与权限 | **P17** | user / permission 两表、JWT、路由守卫 |
| P14 记录总览 | **P18** | 教师看全部、学生看自己 |
| P15 AI 问询 | **P19** | 六类问询、`chat_session` / `chat_message` |
| P16 可视化大屏 | **P20** | echarts 八模块 |
| P17 上传与解析增强 | **P21** | md/docx/pdf、主张 / 表格 / 引用 |
| P18 赛题对齐节点 | **P22** | `align` 节点、错题即停 |
| P19 演示数据补满 | **P23** | 三篇演示补 gold、分母 12 → 15 |
| P20 容器化 | **P24** | compose 四服务 |
| P21 演示性能 | **P25** | ≤ 3 分钟、超时可见 |
| P22 第二期验收 | **P26** | 第十章八条 + 首期 18 条回归，产出 `report-V4.md` |

**与 Phase-2 的衔接（三条硬约束）**：

1. **日志只有一套口径**：Phase-2 只做 Agent 路径的事件与 trace 落库，**不建全量日志目录**；P16 建全量日志时必须复用 Phase-2 已定的事件字段（`ts/level/module/event/review_id/step`），不许另起一套格式。
2. **上传与对齐不在 Phase-2 做**：Phase-2 的工具只能检索「已确认章节」的父块，不解析 docx/pdf（仍显式挂账到 P21），也不引入 `align` 节点（P22）。
3. **Agent 边界不开新口子**：Phase-2 定的预算（步数 / 调用次数 / 时限）、工具白名单、`submit_dimension` 单写口，本期不得放宽；新增工具必须走同一注册表与参数校验。

## 1. 第三期定位

首期把「五步预审主链 + 三篇演示 + 18 条验收」做完了。第三期要做的是**从一个能演示的内部工具，变成一个能给真实用户（学生 + 教师）试用的多用户系统**。

三条主线：

1. **可观测先行**：全系统日志落盘 + 健康探针 + 指标，跑起来看得见、查得动；
2. **多用户与双角色**：学生用现有功能，教师多看三样——学生记录总览、AI 问询、数据大屏；
3. **原欠账清收**：Word/PDF 解析、赛题对齐节点、demo 补 gold、容器化、性能达标。

---

## 2. 阶段总表（P16～P26，十一阶段）

| 阶段 | 名称 | 目标（人能看到的结果） | 依赖 | 日志/监听 |
|---|---|---|---|---|
| **P16** | 日志与监听 | `logs/` 按模块分目录落盘；`/health` `/readyz` `/metrics` 可用；首期全链路可追溯 | — | **本阶段就是建它** |
| **P17** | 登录注册与权限 | 注册 / 登录 / 登出；学生与教师两种角色；路由守卫；未登录不可用 | P16 | `auth/` |
| **P18** | 教师端 · 记录总览 | 教师可看全部学生的评审记录与详情；学生只看自己的 | P17 | `teacher/` |
| **P19** | 教师端 · AI 问询 | 教师用自然语言问询提交详情，回答带 `review_id` 与维度码引用 | P17、P18；复用 Phase-2 的 `PaperRetriever` 与工具注册表 | `ai_chat/` |
| **P20** | 教师端 · 可视化大屏 | echarts 大屏展示八类关键数据 | P18 | `dashboard/` |
| **P21** | 上传与解析增强 | md/docx/pdf 上传；主张 / 表格 / 引用三类产物入库并展示 | P8、P16 | `parsing/` |
| **P22** | 赛题对齐节点 | 图中新增 `align` 节点；选错题停止评分 | P1、P21 | `graph/`（已建） |
| **P23** | 演示数据补满 | 三篇演示补 gold；评测分母 12 → 15 | P6 | `report/`（已建） |
| **P24** | 容器化 | `compose.yaml` 四服务可运行 + 健康检查 | P16、P20 | — |
| **P25** | 演示性能 | 15 页样例端到端 ≤ 3 分钟；超时显示停在哪步 | P22、P16 | `graph/`（已建） |
| **P26** | 三期验收 | 第十章非功能需求逐条 + 首期 18 条回归 | P18～P25 | — |

**串行理由**：P16 必须第一（后面每个功能都要写日志）；P17 是 P18～P20 的前置（没身份就没教师端）；P21 是 P22 的前置（对齐要读解析产物）；P24 要 P16（健康检查）与 P20（大屏也要容器化）。

---

## 3. P16 · 日志与监听（三期第一步，最高优先级）

### 3.1 日志目录结构（总目录 `logs/`，模块独立英文目录）

```text
logs/
├── api/            接入层：每个请求的方法、路径、状态码、耗时、review_id、user_id
│   └── api-YYYYMMDD.log
├── graph/          编排层：节点进出、状态变迁、interrupt / resume、检查点恢复
├── agent/          Agent 子图：模型决策、工具调用、预算余量、critique 结果（Phase-2 已建，此处只扩目录）
├── llm/            模型客户端：每次调用的 model、耗时、重试次数、成败（绝不记密钥）
├── retrieve/       检索：每维召回条数、route_hits、是否触发第二轮、重排前后顺序
├── scoring/        选档：每维 band、quote 子串校验结果、chat_calls、守卫降档
├── review/         规则审查：每类 finding 数量、命中的 constraint_id、漏报边界
├── report/         报告：change_list 条数、存档写入、change_list_note 命中
├── importing/      数据导入：导入结果、整包拒绝的文件与字段
├── auth/           登录注册：登录成败、注册、权限校验失败、token 签发与失效
├── ai_chat/        AI 问询：会话创建、每轮问询、检索到的记录数、模型耗时
├── dashboard/      大屏：聚合查询的耗时与结果行数
├── errors/         未捕获异常汇总（全局异常处理器统一写入）
├── audit/          审计：敏感操作（发布量规、归档赛题、查看他人记录、导出）
└── frontend/       前端：页面错误、接口失败、路由切换（由前端上报接口落盘）
```

**每条日志目录一个独立目录**，互不混写；同一天多进程写入用 `RotatingFileHandler` 或按 PID 分片，避免并发写冲突。

### 3.2 日志格式（结构化 JSON 行）

每行一个 JSON 对象，便于后续用 `jq` / Python 解析：

```json
{"ts":"2026-10-18T21:05:03.412+08:00","level":"INFO","module":"scoring",
 "event":"dimension_scored","review_id":"2525dc78…","dimension_code":"assumption",
 "band":"不足","chat_calls":1,"quote_ok":true,"elapsed_ms":1830}
```

**必填字段**：`ts` / `level` / `module` / `event`。**关联字段**：`review_id`（有评审时必带）、`user_id`（P17 后必带）。

**硬禁令**（写进提示词纪律）：

- 日志中**不得出现** `LLM_API_KEY` / `EMBEDDING_API_KEY` / `RERANK_API_KEY` / `MYSQL_DSN` 的值；
- 不得打印论文全文（只记 `review_id` 与切片编号）；
- 不得打印用户密码哈希。

### 3.3 切割与保留

- 文件名 `<module>-YYYYMMDD.log`，按天切割；
- 单文件上限 50 MB，超出按 `.1` `.2` 滚动，最多留 5 个；
- 默认保留 30 天，超期在启动时清理（可配置）；
- `logs/` 加进 `.gitignore`（日志是本机产物，不入库）。

### 3.4 监听三件套

| 端点 | 用途 | 返回 |
|---|---|---|
| `GET /health` | 进程存活探活 | `{"status":"ok","uptime_s":…}` |
| `GET /readyz` | 依赖就绪探活 | MySQL / Chroma 各自连通性；任一不通返回 503 并指出哪个 |
| `GET /metrics` | Prometheus 文本格式指标 | 评审次数（按状态）、模型调用次数与耗时直方图、检索召回条数分布、登录成败计数 |

**指标命名**：`paper_review_reviews_total{status}`、`paper_review_llm_calls_total{model,result}`、`paper_review_llm_latency_seconds_bucket`、`paper_review_retrieve_parents_histogram`、`paper_review_auth_total{result}`。

### 3.5 首期链路要补的具体埋点

| 模块 | 补什么 |
|---|---|
| `api/routes.py` | 每个端点一条请求日志（含耗时）；异常路径写 `errors/` |
| `graph/review_graph.py` | `parse` / `confirm` / `retrieve` / `score` 四节点进出；`interrupt` 与 `resume`；`_restore_snapshot` 触发 |
| `llm/client.py` | 每次 `chat` / `embed`：model、耗时、重试次数、HTTP 状态（**不含请求头与密钥**） |
| `retrieve/three_route.py` | 每维：三路各自命中数、合并数、重排前后顺序、最终截断数、是否二轮 |
| `scoring/selection.py` + `graph/_score_dimension` | 每维 band、quote 子串校验结果、`chat_calls`、`apply_mention_guard` 是否降档 |
| `review/consistency.py` | 五类 `kind` 各自命中数、命中的 `constraint_id` |
| `report/` | `change_list` 条数与三段分布、`save_review` / `save_session` 写入、`change_list_note` 是否命中 |
| `importing/catalog.py` | 导入成功 / 整包拒绝（记 `filename` 与 `field`） |

### 3.6 完成判据

- [ ] `logs/` 下 15 个模块目录全部存在，跑一次完整预审后每个相关目录都有当天日志；
- [ ] 日志为 JSON 行格式，可用 `jq` 按 `review_id` 串起一次预审全过程；
- [ ] grep 日志文件不含任何密钥值（单测断言）；
- [ ] `/health` `/readyz` `/metrics` 三个端点可用，MySQL 停时 `/readyz` 返回 503 且指出原因；
- [ ] 四道门禁退出码全 0，且**新增测试不许为日志放宽任何既有断言**。

---

## 4. P17 · 登录注册与权限

### 4.1 数据库表（严格按需求：两张表）

```sql
-- 表一：用户表
CREATE TABLE `user` (                          -- user 是 MySQL 保留字，必须反引号（沿用 constraint 先例）
    user_id        VARCHAR(64)  PRIMARY KEY,   -- 每个用户独立 ID，uuid4().hex
    username       VARCHAR(64)  NOT NULL UNIQUE,
    email          VARCHAR(128) NOT NULL UNIQUE,
    password_hash  VARCHAR(256) NOT NULL,      -- argon2，绝不存明文
    display_name   VARCHAR(128) NOT NULL DEFAULT '',
    role           VARCHAR(32)  NOT NULL DEFAULT 'student',  -- student / teacher
    status         VARCHAR(32)  NOT NULL DEFAULT 'active',   -- active / disabled
    created_at     DATETIME     NOT NULL,
    last_login_at  DATETIME     NULL
);

-- 表二：权限表（每个用户独立 ID 对应权限）
CREATE TABLE `permission` (
    permission_id  VARCHAR(64)  PRIMARY KEY,
    user_id        VARCHAR(64)  NOT NULL,      -- 外键指向 user.user_id
    permission     VARCHAR(64)  NOT NULL,      -- 权限标识，见 4.2
    resource       VARCHAR(128) NOT NULL DEFAULT '',  -- 可选：限定资源（如 contest_id）
    granted_at     DATETIME     NOT NULL,
    granted_by     VARCHAR(64)  NOT NULL DEFAULT '',   -- 授权人 user_id（系统建号时为空）
    CONSTRAINT fk_permission_user FOREIGN KEY (user_id) REFERENCES `user`(user_id),
    UNIQUE KEY uk_user_permission (user_id, permission, resource)   -- 同一用户同一权限同一资源只一条
);
```

**设计说明**：

- `role` 是**粗粒度**（登录后快速判断能进哪个菜单），`permission` 表是**细粒度**（逐条可授予 / 收回）。两层配合：role 决定默认权限集，permission 表记录增量与例外。
- 需求说"每个用户独立 ID，ID 对应权限"——所以权限**按 `user_id` 逐条授**，不做"角色 → 权限"的第三张表。这样收回某人的单项权限不用动角色。
- `user_id` 用 `uuid4().hex`（与 `review_id` 同一套生成方式），不暴露自增整数。

### 4.2 权限清单

| 权限标识 | 学生 | 教师 | 说明 |
|---|---|---|---|
| `review:create` | ✅ | ✅ | 创建预审 |
| `review:read:own` | ✅ | ✅ | 读自己的评审 |
| `review:read:all` | ❌ | ✅ | 读任意学生的评审（P18） |
| `chat:use` | ❌ | ✅ | AI 问询页（P19） |
| `dashboard:view` | ❌ | ✅ | 可视化大屏（P20） |
| `contest:manage` | ❌ | ✅ | 导入 / 发布 / 归档赛题 |
| `eval:view` | ✅ | ✅ | 评测汇总页 |

建号时按 role 写入默认权限集（学生 3 条、教师 6 条）；`permission` 表用于后续按人调整。

### 4.3 接口

| 方法 | URL | 请求 | 响应 | 备注 |
|---|---|---|---|---|
| `POST` | `/api/auth/register` | `{username, email, password, display_name}` | 201 `{user_id, username, role}` | 密码强度校验；用户名 / 邮箱重复返回 409 且**不提示"已存在"的具体字段**（防枚举） |
| `POST` | `/api/auth/login` | `{username, password}` | 200 `{token, user_id, role, permissions}` | 失败返回 401 统一文案"用户名或密码错误"，不区分是哪个错 |
| `POST` | `/api/auth/logout` | Header `Authorization` | 204 | 服务端把 token 加入黑名单（或改用短时效 JWT + 刷新令牌） |
| `GET` | `/api/auth/me` | Header `Authorization` | 200 `{user_id, username, role, permissions}` | 前端刷新页面时取当前身份 |
| `GET` | `/api/users` | Header | 200 用户列表 | **仅教师**（`review:read:all`）；学生调返回 403 |
| `GET` | `/api/users/{user_id}` | Header | 200 用户详情 + 其评审列表 | 仅教师；学生只能传自己的 id |

**鉴权方式**：`Authorization: Bearer <token>`。token 用 JWT（短时效，如 2 小时）+ 刷新令牌，**不引入 Session 表**（避免第三张表）。密钥仍只进 `.env`（新增 `AUTH_SECRET` 键）。

### 4.4 前端

| 页面 | 路由 | 内容 |
|---|---|---|
| 登录页 | `/login` | 居中卡片，**背景图 `frontend/pictures/login_background.png`**（已存在，2.4 MB，需压缩到 500 KB 以内）；表单：用户名 / 密码 / 登录按钮 / 去注册链接 |
| 注册页 | `/register` | 用户名 / 邮箱 / 密码 / 确认密码 / 显示名；密码强度提示 |
| 路由守卫 | 全局 | 未登录访问任意页面 → 重定向 `/login`；登录后访问 `/login` → 重定向 `/parse` |
| 角色菜单 | `AppNav.vue` | 教师额外显示「记录总览 / AI 问询 / 数据大屏」三个入口；学生不显示 |

**首期五个页面的改造**：`/parse` 等页面顶部显示当前用户与登出入口；创建评审时把 `user_id` 写入（见 4.5）。

### 4.5 与首期数据的衔接

`review` 表新增 `user_id` 列（nullable，旧记录为 NULL 表示"首期无主"）：

```sql
ALTER TABLE `review` ADD COLUMN user_id VARCHAR(64) NULL AFTER review_id;
```

- 旧记录 `user_id IS NULL`：仅教师可读（`review:read:all`），学生读不到也不报错；
- 新记录必填 `user_id`（从 token 取，**不许由前端传**——防冒名提交）；
- `ReviewSession` 表同步加 `user_id`。

### 4.6 完成判据

- [ ] 两张表建表幂等；`user_id` 独立且与 `permission.user_id` 外键一致；
- [ ] 注册 → 登录 → 登出 → 再登录全流程通；错误文案不泄露"用户名是否存在"；
- [ ] 学生调 `/api/users` 得 403；教师调得 200；
- [ ] 前端路由守卫生效；登录页背景图正确显示且体积已压缩；
- [ ] `auth/` 日志目录有登录成败记录；`review` 表新记录带 `user_id`；
- [ ] 四道门禁全 0；既有 159 个后端测试一个没红（登录是新增路径，不改既有断言）。

---

## 5. P18 · 教师端 · 记录总览

| # | 任务 | 内容 | 完成判据 |
|---|---|---|---|
| 1 | 记录列表接口 | `GET /api/reviews?user_id=&contest_id=&page=&page_size=`：教师看全部、学生看自己；服务端按 `user_id` 强制过滤（**不许信前端的 user_id**） | 学生传别人的 id 仍只拿到自己的 |
| 2 | 记录详情接口 | `GET /api/reviews/{id}` 增加权限判断：本人的、或教师；否则 403（不暴露"是否存在"） | 越权访问返回 403 而非 404 泄露 |
| 3 | 前端记录总览页 | 新路由 `/records`：表格列 = 提交时间 / 学生 / 赛题 / 量规版本 / 模型 / 档位概览 / 冲突数；点击进详情抽屉 | 教师可见全部；学生无此入口 |
| 4 | 详情抽屉 | 展示该记录的五维档位、原句、`change_list`、审查 findings；原句可点定位 | 与 `/scoring` `/consistency` `/suggestions` 展示一致 |
| 5 | 审计 | 教师查看他人记录写 `audit/` 日志（谁、什么时候、看了哪条） | `audit/` 有记录 |

---

## 6. P19 · 教师端 · AI 问询（详细设计）

### 6.1 定位

教师的**预审数据助手**：基于系统里已产生的评审记录对话，**不是通用聊天机器人**。它只能回答"这些提交里发生了什么"，不能回答编程、写作、闲谈。

### 6.2 数据范围与权限

- 可见范围 = 调用者权限内的评审记录（教师 = 全部，未来可扩展为"只看自己班级"）；
- 检索时**必须带上 `contest_id` / `user_id` 过滤**，不许跨权限捞数据；
- 每轮问询落库，可复现、可审计。

### 6.3 六类问询能力（详细内容）

| # | 能力 | 用户会怎么问 | 系统怎么做 |
|---|---|---|---|
| 1 | **单条提交详情问询** | "张三的板凳龙论文，假设维为什么判证据不足？" | 定位 `review_id` → 取该维的 `dimension_results` + 检索到的父块 → 回答带 `review_id` 与 `dimension_code` 引用 |
| 2 | **修改建议追溯** | "这条『把两处数值改成同一口径』的依据是什么？" | 按 `upstream_id` 反查上游 finding 或维度档位，给出原文证据 |
| 3 | **横向对比** | "这道题里有多少学生的假设维是证据不足？按人数排" | 聚合查询（SQL，不过模型）→ 返回数字 + 涉及的学生列表 |
| 4 | **冲突汇总** | "本周提交里数字冲突最多的是哪几处？" | 聚合 `change_list` 里 `kind=数字冲突` 的条目，按 `target` 分组计数 |
| 5 | **证据充分性检查** | "有没有学生完全没提板凳宽度？" | 检索 `assumption` 维 `band=证据不足` 且 quote 为空的记录 |
| 6 | **教研摘要导出** | "把这周 A 题的提交整理成一段给教研会的摘要" | 取该周该题的聚合结果 → 模型生成 ≤ 300 字摘要 → **必须带三条具体证据引用**，不许空泛总结 |

### 6.4 实现要点

- **RAG 检索**：**直接复用 Phase-2 的 `PaperRetriever`**（`BaseRetriever` 适配器），只换数据源与 `doc_type`；新增 `doc_type = review_record`（白名单加一个值，需同步 `DOC_TYPES` 与其测试）；检索对象是"评审记录的维度结果 + 原句"，不是论文原文。**不许另写一套检索**——两套检索必然给出两套口径。
- **prompt 纪律**（写进 system）：
  - 只能基于给定的评审记录片段回答，**不得编造**；
  - 引用必须带 `review_id` 与 `dimension_code`，格式 `[review_id=xxx dim=yyy]`；
  - 查不到就说"这些记录里没有相关信息"，**不许推测**；
  - 不输出奖项、名次、获奖概率；
- **失败可见**：检索为空 → 明确说"没有找到相关记录"；模型 JSON / 文本解析失败 → 重试一次后仍失败则报"问询失败，请重试"，不返回半截答案；
- **不做流式**（首期已确认同步接口），本轮只做请求 → 响应；
- **上下文控制**：单轮最多带 8 段记录片段（沿用 `MAX_PARENTS=4` 的精神，放宽到 8 因为记录片段短），超出先聚合再答。

### 6.5 需要的额外两张表（超出需求指定的两张，需说明理由）

```sql
CREATE TABLE `chat_session` (
    session_id  VARCHAR(64) PRIMARY KEY,
    user_id     VARCHAR(64) NOT NULL,          -- 发起问询的教师
    title       VARCHAR(256) NOT NULL DEFAULT '',
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);

CREATE TABLE `chat_message` (
    message_id   VARCHAR(64) PRIMARY KEY,
    session_id   VARCHAR(64) NOT NULL,
    role         VARCHAR(32) NOT NULL,          -- user / assistant
    content      TEXT NOT NULL,
    refs         JSON NULL,                     -- assistant 引用：[{review_id, dimension_code}]
    model_name   VARCHAR(128) NOT NULL DEFAULT '',
    created_at   DATETIME NOT NULL
);
```

**为什么必须加**：没有这两张表，问询历史刷新即丢、无法复现、无法审计"AI 对教师说了什么"。需求指定的两张表（user / permission）只管身份，不管会话。

### 6.6 前端 `/chat`

- 左侧会话列表（新建 / 切换 / 删除）；
- 右侧消息流：用户消息右对齐、助手消息左对齐且**引用可点**（点 `[review_id=xxx]` 跳到该记录详情）；
- 顶部显示可见范围提示"你正在问询全部 89 条提交记录"；
- 空态：提示三类示例问法（单条详情 / 横向对比 / 摘要导出）；
- 手稿风格与既有页面一致（衬线引文、墨色、无圆角卡片泛滥）。

### 6.7 完成判据

- [ ] 六类问询各有一条可复现的实测记录（落 `ai_chat/` 日志 + `calls/` 证据）；
- [ ] 引用全部带 `review_id` 与 `dimension_code` 且可点回详情；
- [ ] 检索为空时明确说"没有找到"，不编造；
- [ ] 越权问询（学生调 `/api/chat`）返回 403；
- [ ] `chat_session` / `chat_message` 两张表落库，刷新后历史在。

---

## 7. P20 · 教师端 · 可视化大屏（echarts）

### 7.1 技术栈

- `echarts@5`（**按需引入**，不整包——首期 Element Plus 全量引入已让 bundle 到 1 MB，不能再涨）；
- 图表容器用手写 div + `echarts.init()`，不用第三方 Vue 封装（少一个依赖）；
- 数据来自两个只读聚合接口，**不过模型**。

### 7.2 八个展示模块

| # | 模块 | 图表类型 | 数据口径 |
|---|---|---|---|
| 1 | **提交总量趋势** | 折线图（近 30 天） | 每日新建 `review` 数（含无主的首期记录单列一档） |
| 2 | **赛题分布** | 环形图 | 各 `contest_id` 的提交占比 |
| 3 | **五维档位分布** | 堆叠柱状图 | 每维各自的 充分 / 基本 / 不足 / 证据不足 条数 |
| 4 | **证据不足 Top 维度** | 水平条形图 | 哪些维最容易证据不足（给教研反馈：是学生没写还是检索没捞到） |
| 5 | **冲突类型分布** | 饼图 | `change_list` 五类 kind 的条数占比 |
| 6 | **高频冲突对象** | 词云或条形图 | `target` 字段聚合 Top 10（如"盘入终止时刻"） |
| 7 | **引用失败率** | 仪表盘 | `status=引用失败` 的维度占比（**反映模型质量**，不是成果） |
| 8 | **关键指标卡** | 数字卡（非图表） | 总提交数 / 本周新增 / 待处理冲突数 / 有 gold 时的档位一致率 |

**设计纪律**：

- 手稿风格：图表线宽、坐标轴、标签都用墨色系；**不渐变、不发光、不 3D**；数据标签用等宽体；
- 空数据时显示"暂无数据"，不画空图表框；
- 大屏默认 `/dashboard` 路由，仅 `dashboard:view` 权限可进；
- 首屏加载 ≤ 2 秒（聚合接口加缓存，60 秒 TTL）。

### 7.3 接口

| 方法 | URL | 响应 |
|---|---|---|
| `GET` | `/api/dashboard/summary` | 指标卡 + 分布类数据（模块 2 / 3 / 5 / 7 / 8） |
| `GET` | `/api/dashboard/trend?days=30` | 模块 1 的时序数据 |

两个接口都做服务端聚合（SQL `GROUP BY`），不下拉全量到前端算。

### 7.4 完成判据

- [ ] 八个模块全部渲染，空数据显示"暂无数据"；
- [ ] echarts 按需引入，`npm run build` 的 bundle 增量 ≤ 400 KB（gzip 后 ≤ 120 KB）；
- [ ] 学生访问 `/dashboard` 被守卫挡住并提示无权限；
- [ ] 聚合接口 ≤ 500 ms（有索引支撑）；
- [ ] 截图存 `docs/plan/acceptance/screenshots/` 或三期验收证据目录。

---

## 8. 原欠账阶段（P21～P26）

以下六阶段沿用 2026-10-18 版计划的目标与完成判据，只改阶段号与依赖：

| 本文件阶段 | 该版计划中的阶段 | 核心内容 |
|---|---|---|
| **P21** | P17 | md/docx/pdf 上传；主张 / 表格 / 引用三类产物；`review_artifact` 表。依赖 P8 + P16（解析也要写日志） |
| **P22** | P18 | 图中新增 `align` 节点；选错题停止评分；阈值宁漏不误。依赖 P1 + P21；与 Phase-2 的 Agent 图衔接方式在开工前定（节点优先于工具） |
| **P23** | P19 | 三篇演示补 gold；评测分母 12 → 15 |
| **P24** | P20 | compose 四服务可运行；健康检查。依赖 P16（探针）+ P20（大屏也要进镜像） |
| **P25** | P21 | 3 分钟时限；超时显示停在哪步；并行化不改 `chat_calls` 语义 |
| **P26** | P22 | 第十章非功能八条 + 首期 18 条回归；产出 `report-V4.md` |

> **挂账**：P21～P26 的逐条任务表（每个任务的具体做法与风险）原本写在 `docs/version/v1.10.0_第二期计划.md`，该文件已按 §9 删除。开工前需按该框架重写细则，**不凭记忆补**。

## 9. 文档处置

| 文件 | 处置 |
|---|---|
| `docs/version/Phases/Phase-1/paper-review.md` | 第一阶段（首期）执行手册，不动 |
| `docs/version/Phases/Phase-2/Phase-2-plan.md` | 第二阶段（Agent 化）唯一有效计划 |
| `docs/version/Phases/Phase-3/Phase-3-plan.md` | **本文件，第三期唯一有效计划** |
| `docs/version/Phases/Phase-2/v2.0.0_第二期计划.md` | 已删除（内容并入本文件前身） |
| `docs/version/v1.10.0_第二期计划.md` | 已删除 |

**第三阶段后续提示词命名**：`docs/version/Phases/Phase-3/v3.<期内阶段序号>.<子任务序号>_<功能描述>.md`——第二位是**期内序号**不是 P 号（P16→`v3.0.x`、P17→`v3.1.x`、P18→`v3.2.x` …… P26→`v3.10.x`），第三位为子任务序号（内容多就拆，规则同 Phase-2）。如 P16 的提示词为 `v3.0.0_日志与监听.md`。第一位固定 3（第三期）。

## 10. 明确的非目标（第三期不做）

| 不做 | 原因 |
|---|---|
| 多用户权限与学校组织架构 | 需求第十一章明令"不做"；本期只做"学生 / 教师"两类，不做班级、院系、多级管理 |
| 奖项 / 名次 / 获奖概率 | 第十一章"不输出获奖等级" |
| 本地模型运行时 | 第十一章"不接本地模型运行时" |
| 优秀论文原文入库 | 第十一章版权约束 |
| 新的 `check_type` | §12.5 只要求"不改代码即可加题" |
| 流式对话 / WebSocket | 首期已定同步接口；AI 问询先做请求-响应 |
| 大屏自助拖拽 / 自定义看板 | 八模块固定，够用即可 |
| 移动端专门适配 | 桌面工作台定位（既有纪律） |
| 开放工具平台 / 多智能体协作 | Phase-2 已定「有界 Agent」：工具白名单固定、写结论只有一个口；本期不扩 |

---

## 11. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 日志写入拖慢接口 | 演示超 3 分钟（P25 达标难） | 日志用异步队列（`QueueHandler` + 后台线程）；单条日志序列化开销 < 1 ms；P25 复测时确认日志开启不影响耗时 |
| 日志磁盘膨胀 | 磁盘写满 | 按天切割 + 50 MB 滚动 + 30 天清理；`logs/` 进 `.gitignore` |
| 登录改造打破既有 159 个测试 | 大面积返工 | 登录是**新增路径**；`review` 表加 nullable `user_id`，旧测试不传也照跑；守卫只加在前端路由 |
| `user` / `permission` 与既有 11 张表的关系 | 建表冲突 | 新建独立 `AuthBase` + `create_auth_schema()`（沿用 `ParentBase` / `ReportBase` 先例），只读复用 `importing/db.py` 的引擎 |
| echarts 增加 bundle 体积 | 首屏变慢 | 按需引入；P20 完成判据里卡死增量 ≤ 400 KB |
| AI 问询编造答案 | 教师被误导 | prompt 纪律 + 引用必须带 `review_id` + 检索为空明说"没有找到"；每轮落库可复查 |
| AI 问询花钱 | 额度失控 | 单轮最多 8 段上下文；问询历史可查用量；不加 `force` 不触发批量 |
| 教师越权看学生记录 | 数据边界 | 服务端按 `user_id` 过滤，不信前端参数；`audit/` 记录每次跨人查看 |
| 登录背景图 2.4 MB | 首屏慢 | 压缩到 500 KB 以内（可用项目已有的 `shot-sketch.mjs` 同款工具或任意压缩工具），保留手稿风格 |
| 每阶段动真库，测试污染累积 | 行数失控 | 沿用"接受污染 + 记录行数 + 挂账"先例，不偷偷加删除接口 |

---

## 12. 每阶段通用纪律（必须带进每份提示词）

1. **先写失败测试，看它失败，再写实现**；先写了实现就删掉重来。
2. **退出码 0 才算通过**；命令、退出码、末行写进 `docs/plan/progress.md`，未过不写下一版。
3. **每个功能都必须有日志和监听**：新代码按 §3.1 的模块目录归位，关键路径加埋点，不许出现"没有日志的新模块"。
4. 裁决写 `docs/plan/findings.md`，格式 `决定 — 原因 — 做错的代价`。
5. 不输出奖项、名次、获奖概率；评分 / 审查 / 报告源码不按题号写分支。
6. 只有 `backend/app/llm/client.py` 能发 HTTP；`build_review_graph` 与 Phase-2 新增的 `agent/` 模块内不导入 client、不出现 HTTP 字样；检索器与模型一律外部注入，未注入时保持占位行为。
7. 不许放宽既有断言；冻结文件 `backend/tests/graph/test_interrupt.py`、`backend/tests/retrieve/test_rerank_cap.py` 不许改。
8. 密钥只进 `.env`，不打印、不回显、不落盘、不进日志、不进测试夹具、不进提交。
9. `.env` 模型选品保持定案：对话 DeepSeek `deepseek-flash` / 嵌入 `BAAI/bge-m3` / 重排 `BAAI/bge-reranker-v2-m3`。
10. 前端 TypeScript + `<script setup lang="ts">`；类型集中在 `src/api/types.ts`；Element Plus 只用于表单 / 表格 / 消息；echarts 按需引入。
11. 一次提示词只解决一个阶段；本版未通过不前强。
12. **不得放宽 Phase-2 的 Agent 边界**：预算、工具白名单、`submit_dimension` 单写口、critique 只降不提，四条任一条被改动，本阶段判不通过。

---

## 13. 推进节奏建议

以下为 **Phase-3 自身**的七周节奏；Phase-2（P12～P15，Agent 化）收口并产出 `report-V3.md` 后才启动。

| 周次 | 内容 |
|---|---|
| 第 1 周 | P16（日志与监听，独占一周——它是后面一切的地基） |
| 第 2 周 | P17（登录注册与权限） |
| 第 3 周 | P18 + P19（记录总览 + AI 问询） |
| 第 4 周 | P20（大屏）+ P21（解析增强，视工作量可延一周） |
| 第 5 周 | P22 + P23（对齐节点 + 补 gold） |
| 第 6 周 | P24 + P25（容器化 + 性能） |
| 第 7 周 | P26（三期验收收口） |

**每阶段开始前**：先确认上一阶段四道门禁全绿（`npm run build` / `npx vitest run` / `npx playwright test` / `pytest backend/tests -q`），再动笔写该阶段提示词。
