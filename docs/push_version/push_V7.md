# paper-review 第七版（push_V7 · Phase-3 P20～P26 完整说明）

> **分支**：`V6-Phase-III-Acceptance`（代码提交 `fca7654`）
> **上一版**：`push_V6.md`（Phase-3 P16～P19，`Phase-III-P16-P19` @ `ad9aaf0`）。本版覆盖 **Phase-3 的后七个阶段 P20～P26**：可视化大屏、上传与三类产物、可评门禁、gold 样本校准、容器骨架、性能与等待可见、三期验收。
> **改动规模**：**166 个文件，+14829 / −234 行**；新增 108 个、修改 58 个、删除 0 个。
> **门禁**：`pytest backend/tests` → **472 passed**（连跑两遍 223.97s / 213.57s，数字相同、退出码 0）；`vitest` **162 passed（32 文件）**；`playwright` **54 passed / 0 failed**（4.3 分钟）；`npm run build` 退出码 0，入口 `1,126.98 KB / 358.89 KB gzip`；`check_logs` / `check_docs_encoding` / `check_container_skeleton` 三个脚本全 EXIT=0。
> **判定口径**：P20～P23、P25、P26 六项按判据收口；**P24 容器化按 §8.1 裁剪为非验收项**——本机没有 Docker，只交付骨架与 Dockerfile 草案，报告原话是「骨架已就绪，未验证」。三期 E2E 红灯从 **8 条降到 0 条**，但其中一条的归零方式值得单独看（§3.5）。

---

## 1. 这一版做了什么

一句话：**把「有身份、有日志、能问答的系统」做成了一个能验收的完整产品——看得见的大屏、进得来的真论文、拦得住的无量规赛题、标得准的评测口径，以及一条能自己说服自己的性能证据链。**

| 阶段 | 内容 | 状态 |
|---|---|:-:|
| P20 | 可视化大屏（八模块）+ 两个只读聚合接口 + `dashboard:view` 权限拦截 | ✅ |
| P21 | 上传链路（md/docx）+ 三类产物（claim/table/citation）确定性抽取与回定位 | ✅ |
| P22 | 可评门禁：赛题无已发布量规则 422，确认页展示赛题名与量规版本 | ✅ |
| P23 | gold 校准：维持 12 篇、分母 <5 的指标不再渲染成百分比 | ✅ |
| P24 | 容器骨架 + 最小 CORS + 17 项静态校验脚本 | ⚠️ 非验收（本机无 Docker） |
| P25 | 真实耗时基线（模型路径中位 31.7 s）+ 等待可见 + 八条 E2E 逐条处置 | ✅ |
| P26 | 三期验收：八条非功能替代口径 + 首期 18 条回归 + `report-V4.md` | ✅ |

本版共写出 **20 个版本段**（`v3.4.0`～`v3.10.2`），每段都有命令、退出码与末行记录在 `docs/plan/progress.md`。

### 1.1 改动范围（`git show --stat fca7654` 实测，166 个文件）

| 类别 | 数量 | 说明 |
|---|:-:|---|
| 新增（`A`） | 108 | 六个后端模块（`report/dashboard.py`、`report/artifact_models.py`、`importing/artifacts.py`、`importing/docx_text.py`、`importing/spans.py`、`api/dashboard_routes.py`）、26 个测试文件、13 个脚本、`docs/version/10.21` 21 份阶段文档、`report-P19`～`report-P25` 与 `report-V4` 八份验收报告、前端大屏/问询/产物面板与 12 个前端测试 |
| 修改（`M`） | 58 | 路由、评测口径、样例目录、日志门禁、`Phase-3` 计划与 P21/P22/P23/P25 细则、`findings` / `progress`、`AppNav`、`api/types.ts` |
| 删除（`D`） | 0 | 无 |

### 1.2 六个新模块

| 模块 | 职责 |
|---|---|
| `backend/app/report/dashboard.py` | 大屏聚合：四档分布、赛题分布、趋势、证据不足率、热点扣分点、gold 对照，全部服务端 `GROUP BY` + 60 s TTL |
| `backend/app/report/artifact_models.py` | `review_artifact` 表：CASCADE 外键、`artifact_type` 白名单、`char_start/char_end` 可回定位 |
| `backend/app/importing/artifacts.py` | 三类产物确定性抽取（不调模型），幂等替换 |
| `backend/app/importing/docx_text.py` | docx → 带 ATX 标题的规范化 Markdown，按 `body` 子元素顺序分派段落与表格 |
| `backend/app/importing/spans.py` | 章节区间计算**唯一实现**，上传、详情、产物三处共用 |
| `backend/app/api/dashboard_routes.py` | 两个只读端点，`dashboard:view` 权限 |

配套脚本 13 个，其中三个是长期门禁：`check_container_skeleton.py`（17 项静态校验）、`check_eval_gold.py`（gold 结构与维度码对齐）、`measure_p25_resume.py`（可复跑的耗时测量）。

---

## 2. 核心实现

### 2.1 大屏：模块 7 的指标被换掉，因为原指标恒为 0

原计划的第七个模块是「引用失败率」。实测 `review_dimension.status` 只有四档（基本 / 充分 / 不足 / 证据不足），**「引用失败」这个状态在数据里根本不存在**，仪表盘会永远指向 0。裁成「证据不足率」后是真实可变的（当前 105/730 ≈ 14.4%）。

这是本版一个反复出现的判断方式：**恒定的指标不是"暂时没数据"，是坏图。**

### 2.2 上传：拒绝理由必须分得比"失败"更细

`POST /api/uploads` 的校验顺序固定为：权限 → 扩展名 → 字节 → 解码（UTF-8 剥 BOM → GB18030 → 拒绝）→ 非空 → 字符数 → 落盘 `data/uploads/<review_id>/<sha256>.md` → 落库。限额 20 MB / 80 页 / 200,000 字符是**工程决策**（依据真实样本最大 122.3 KB / 52,648 字符、PDF 最大 9.21 MB），不是需求原文，这一点写在 P21 细则里。

一个踩过的坑：`POST /api/reviews/upload` 会返回 **405 而不是 404**——因为 `routes.py` 有 `GET /reviews/{review_id}`，`upload` 被当成 `review_id` 匹配掉了。动态路由会静默吞掉静态子路径，**而报错看起来像"方法写错了"**。所以改用了独立前缀 `POST /api/uploads`。

### 2.3 三类产物：规则抽取，因为它先得"能定位"

claim / table / citation 全部用确定性规则抽，**不调模型**。原因不是省钱：产物有硬要求 `paper_text[start:end]` 必须逐字等于原文，模型生成的句子再像，差一个标点偏移就废了。判断准是评分环节的事，这一层只负责**能回定位**。

偏移口径也统一过：产物偏移指向 `paper_text`（含标题行与空行），而前端曾按 `sections.map(s => s.content).join('\n')` 拼（没有标题行），越往后偏得越多。修法是让 `GET /reviews/{id}` 直接返回 `char_start/char_end`，前端用差值换算，**区间计算只留一份**。

### 2.4 可评门禁：422 比 200 好，因为 200 会让人重试

原计划给 P22 设计的是「比对 `contest_id` 与 `rubric_id`」。查代码发现**这条检查永远不会触发**——`CreateReviewRequest` 只有 `paper_text / sample_id / contest_id` 三个字段，rubric 由赛题反查已发布版本，两者天生一致。

改成「赛题存在且有已发布量规」：`POST /reviews` 不可评返回 422（空赛题放行，用于纯解析），`POST /reviews/{id}/resume` 不可评也返回 422 且不产出任何档位。**理由很具体：422 会让人去查原因，200 只会让人重试。**

### 2.5 低样本指标：分母 2 不该渲染成百分比

首期 gold 60 个维度里「证据不足」只有 2 条，页面却把 `0/2` 与 `2/2` 一律乘 100 渲染成 `0%` / `100%`，与 60 样本的百分比完全同形。

处置是加 `LOW_SAMPLE_THRESHOLD = 5` 与 `_metric.low_sample`：分母 <5 时显示「样本过少」、不出现百分号、不画折线，卡片下方写「本指标分母仅 N 个维度，不足以支撑结论」。**`rate` 与 `caliber` 一个字没动**——两个值各有一条用例锁着，改动它们属于契约变更。

补样本这条也裁了：候选 136 条里 2024-A 占 133、2024-C 3、**2025-A 0**，从 2024-A 补会让 4/4/4 变 5/4/4，把均衡补坏；想补均衡就得同时补 2025-A，而它没有候选。**「可选补 1 篇」在候选分布面前自动失效**，这条写进了 P23 细则而不是靠记忆。

### 2.6 等待可见：计时器可以，但要写清它是什么

`resume` 是同步接口，25～40 秒全在一次 `await` 里，`confirmed-card` 只在返回后才渲染。P25 加了 `stage-elapsed`（每秒更新已等待秒数）与 `SLOW_HINT_MS = 20_000` 的超阈值提示。

`StageTracker` 原来的注释写着「不用定时器假装进度」。**那条禁的是点亮步骤；"已等待 12 秒"是实测值，不是进度。** 这层区别写进了组件注释——好纪律被误用的方式通常不是被违反，而是被扩大解释。

---

## 3. 本版修掉的五个真实问题

### 3.1 生产向量库读不了（`0xC0000005`）

`count()` / `get()` / `query()` 三条路径全崩在 `chromadb/api/rust.py` 的不同行，空目录新建 collection 却全绿。定位结论是 HNSW 段损坏，不是 sqlite。处置：旧目录改名 + 建空目录 + `rebuild_chroma_from_parents.py` 重建。

关键教训写进了验收报告：**「pytest 全绿」与「空库探针全绿」都不度量生产库可用性**——381 项测试用的是隔离小库，两处都碰不到那份 107 MB 索引。

### 3.2 重建后少了 8925 条，但不是丢失

旧库 24519、新库 15594。交叉核对：旧库有 204 个 `review_id`，MySQL 只有 129 个，**孤儿 75、缺失 0**。那 8925 条全是已删评审的残留子块。这条必须写清楚，否则下一个人翻到旧数就会去回滚。

### 3.3 parse-only 行污染了提交统计

为了让空赛题会话的产物能落库，插了一条 `rubric_id=''` 的父行。后果是大屏把它算成一次提交，赛题分布里还多出一根空字符串柱子（实测 `total_submissions=180`，真实 178）。

修法是改口径不改数据：`dashboard.py` 用唯一谓词 `rubric_id != ""` 作用于总数、7 日新增、赛题分布、趋势四处，并额外返回 `parse_only` 计数，页面加一行「另有 2 篇仅解析未评分」。**数字从 180 变 178 如果不解释，用户会以为丢了数据。**

### 3.4 日志门禁的日界耦合

`check_logs.py` 要求「必需写入者今天必须有日志」，但 `retrieve/scoring/review/importing` 只在跑完整评审时写。纯前端版本永远标红，于是**真坏的那天也会被当成"又是没业务"放过去**。

改成 `--since-days N`（默认 7）窗口判定，保留 `--strict-today` 原语义；并且明确**不许把那 4 个 writer 挪进 `ALLOWED_EMPTY`**——那是豁免（可以永远不写），不是窗口（可以几天不写）。同样变绿，改的对象不一样。

### 3.5 六个版本的假绿灯

P23 给 `evaluation.py` 加了 `low_sample`，但 8077 上的进程从 P23 一路写到 P25 都是「运行中，PID 12232」，**从未重启**。接口因此从未返回该字段，前端拿到 `undefined` 当 false 照常画折线，`/eval` 三折线 E2E 连续六版都是绿的。

P26 重启后字段首次生效，那条用例立刻红。修法不改产品（不画线是 P23 的明确决策），而是把断言改成按字段判断，并加一道最便宜的闸：先断言 `/api/eval/summary` 每项都带布尔型 `low_sample`，缺失就报「后端进程未加载新字段，请重启后再跑」。

**绿灯有两种：一种是被测对象真的对，另一种是被测进程还是旧的。**

### 3.6 演示样例被一行 `or` 遮蔽

`catalog.py` 写的是 `sources = load_real_papers() or load_demo_texts()`——`or` 是**回退**不是**并列**。P21 接入 10 篇真实论文后，三篇演示稿（`bench-dragon` / `planting` / `smoke`）彻底从 `/api/samples` 消失，而首期 18 条的 2.1/2.2/2.3 与两条 E2E 恰恰依赖它们（`412 s` / `386 s` / 「忽略板凳宽度」只存在于 `bench-dragon`）。

改成并列后 `?is_demo=true` 从 10 条变 13 条，两条 E2E 归零。**替换是一个决定，但当时没人检查它带走了什么。**

---

## 4. 数据现状（本版结束时实查）

| 项 | 数值 | 说明 |
|---|---:|---|
| MySQL 表 | 17 | 新增 `review_artifact` |
| `review` | 262 | 含 E2E 正常链路写入，均未清理 |
| `review_dimension` | 1300 | 四档齐全 |
| `review_session` | 388 | — |
| `review_artifact` | 24 | claim 22 / table 1 / citation 1 |
| `chat_message` / `chat_session` | 33 / 61 | seq 连续、无重复 |
| `user` | 6 | 演示教师 `demo_teacher` 为手动提权（`granted_by=manual-demo`） |
| `paper_parent` | 12299 | 父块全文，供引用逐字校验 |
| `agent_step` | 6700 | Agent 轨迹，前端可查 |
| Chroma 向量 | **29676** | `paper_child` 29031 + `review_record` 645；260 个 review、8457 个 parent |

---

## 5. 接口现状（33 条）

| 文件 | 条数 | 范围 |
|---|:-:|---|
| `api/routes.py` | 17 | 赛题、评审、上传、产物抽取与读取、评分、评测、大屏聚合入口 |
| `api/chat_routes.py` | 7 | 会话、消息、聚合统计、检索问询 |
| `api/auth_routes.py` | 4 | 注册、登录、当前用户、登出 |
| `api/user_routes.py` | 2 | 用户列表、角色/权限 |
| `api/dashboard_routes.py` | 2 | 汇总、趋势 |
| `api/reviews_list_routes.py` | 1 | 记录总览列表 |

### 5.1 接口层的已知边界

- 上传只收 `.md` 与 `.docx`；**pdf 在扩展名校验处直接 415**，提示「请先在外部转成文本后上传，系统不在线上解析 PDF」。真实论文是扫描件，OCR 已在上游离线做过一次，`data/samples/*.md` 就是那份产物。
- 大屏聚合有 60 s TTL，响应带 `cached` 字段；数值与只读 SQL 的一致性由 `report-V4.md` §2 的第 8 项抽查。

---

## 6. 已知边界（不写「全部通过」）

1. **P24 容器化是非验收项**：`compose.yaml` 四服务每个都标了 `UNVERIFIED`，`backend/Dockerfile` 首行也标了。本机 `docker --version` 退出码 127，**镜像从未构建**。`frontend/` 没有 Dockerfile，compose 里已注明「本服务不可构建」。`chromadb/chroma:1.5.9` 这个 tag 未验证是否存在。镜像预期 ≥1 GB（含 chromadb）。
2. **需求分析 V3 的第十章不在仓库里**，八条非功能是**替代口径**（聚合接口 ≤500 ms、首屏 400 KB/120 KB、上传限额、单次耗时只记录、权限隔离、日志门禁、编码门禁、数据完整性）。报告里写明了「取得原文后需校准」，没有假装拿到过。
3. **不做内容级「选错题」判定**：P22 只保证不可评的赛题不出结果，不保证论文与题目匹配。
4. **不做并行化**：P25 只做基线测量与等待可见，三分钟验收已按 §8.1 撤销。
5. **claim 是最小规则版**：只抽「含数字的结果句」，不作收口项；因为 P22 降为入口校验后产物已无评审侧消费方。
6. **`run_eval()` 不注入 `agent_runner`**，评测数字不覆盖工具调用、critique 降档与预算终止；这些由 `agent_step` 轨迹单独衡量。

---

## 7. 仓库卫生

- `.env` **从未被跟踪**，只提交 `.env.example`。本次提交前重新核验：`git ls-files | grep '^\.env'` 只有 `.env.example`。
- `.gitignore` 本版新增两条：`chroma_data.failed-*/`（向量库重建失败目录，含二进制索引）与 `.tmp_*`（一次性排查脚本）。
- `logs/`、`chroma_data/`、`data/papers/`、`data/uploads/`、`node_modules/`、`.workbuddy/`、`playwright-report/`、`test-results/` 全部不入库。
- 仓库内唯一的凭据是 E2E 夹具口令 `e2e-teacher-password-123`，出现在 `frontend/tests/e2e/global-setup.ts` 与 `scripts/measure_p25_resume.py`，**只用于本地测试库创建教师身份**，不是生产凭据。
- 本版新增 6 张验收截图共约 3.7 MB（大屏与产物面板），属证据材料。

---

## 8. 怎么验这一版

```bash
# 后端（8077 可保持运行；改过后端代码后必须重启，没有 --reload）
"D:/LEARN/AI/programs/AgentTask/env/agent-task/Scripts/python.exe" -X utf8 -m pytest backend/tests -q
# → 472 passed

# 前端
cd frontend && npm run build && npx vitest run --reporter=dot
# → 入口 1,126.98 KB / 358.89 KB gzip；Tests 162 passed
cd frontend && npx playwright test --reporter=list
# → 54 passed

# 三个门禁脚本
"D:/LEARN/AI/programs/AgentTask/env/agent-task/Scripts/python.exe" -X utf8 scripts/check_logs.py
"D:/LEARN/AI/programs/AgentTask/env/agent-task/Scripts/python.exe" -X utf8 scripts/check_docs_encoding.py docs --strict
"D:/LEARN/AI/programs/AgentTask/env/agent-task/Scripts/python.exe" -X utf8 scripts/check_container_skeleton.py
# → 三条都 EXIT=0

# 样例目录自检（应看到三篇演示稿与真实论文并列）
curl -s "http://127.0.0.1:8077/api/samples?is_demo=true" | head -c 400
```

---

## 9. 下一版

三期已经收口。要继续做的话，按价值排序是三件事：

1. **取得需求分析 V3 原文**，回来校准第十章八条——现在报告里写的是替代口径，这一条一直挂账。
2. **真正的容器化**：装 Docker、补 `frontend` 的 Dockerfile、验证 Chroma tag、跑通四服务，才有资格把 P24 从非验收改成验收。
3. **内容级「选错题」判定**（`align` 的真实工作）：需要题面文本与论文的语义比对，属新能力，不是入口校验能覆盖的。
