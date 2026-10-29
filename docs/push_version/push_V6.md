# paper-review 第六版（push_V6 · Phase-3 P16～P19 完整说明）

> **分支**：`Phase-III-P16-P19`（提交 `ad9aaf0`）
> **上一版**：`push_V5.md`（Phase-2 Agent 化与验收，`Phase-II-Acceptance` @ `fb75d77`）。本版覆盖 **Phase-3 的前四个阶段 P16～P19**：日志与监听、登录鉴权、记录总览、AI 问询。
> **改动规模**：**112 个文件，+14369 / −129 行**；新增 82 个、修改 29 个、删除 1 个。
> **门禁**：`pytest backend/tests` → **356 passed**（后端保持运行时连跑两遍，172.40s / 176.08s，退出码 0）；`vitest` **138 passed（24 文件）**；`playwright` **40 passed / 8 failed**（1.6 分钟，8 条红与 `v3.2.3` 逐条一致）；`npm run build` 退出码 0。
> **判定口径**：P16 / P17 / P18 三项收口均满足判据；**P19 不宣称全部能力验收通过**——问答链路、聚合、摘要均有实测记录，但「单条详情问询命中指定 `review_id`」这一项检索精度未达标，详见 §6。

---

## 1. 这一版做了什么

一句话：**把「一个能跑评审的工具」变成「一个有身份、有日志、有记录总览、能对着数据提问的系统」。**

| 阶段 | 内容 | 状态 |
|---|---|:-:|
| P16 | 日志底座（15 目录 / JSON 行 / 按天滚动）+ 监听三件套（`/health` `/readyz` `/metrics`）+ 门禁脚本 | ✅ |
| P17 | 账号体系：scrypt 哈希、自签 token、两种角色七条权限、强制鉴权翻转 | ✅ |
| P18 | 记录总览：列表接口 + 索引 + 审计日志 + `/records` 页 + 详情抽屉 | ✅ |
| P19 | AI 问询：会话消息表、评审记录索引与检索、回答链路、聚合统计、教研摘要 | ⚠️ 链路可用，单条详情命中精度未达标 |

### 1.1 改动范围（`git show --stat ad9aaf0` 实测，112 个文件）

| 类别 | 数量 | 说明 |
|---|:-:|---|
| 新增（`A`） | 82 | 4 个后端包（`auth` / `chat` / `observability` / 5 个 `api/*_routes.py`）、8 个测试目录、5 个脚本、10.20 阶段文档 21 份、`report-P16/P17/P18` 三份验收报告、前端登录/注册/记录总览页与组件 |
| 修改（`M`） | 29 | 检索层、路由、模型、日志接入点、`AppNav`、`api/index.ts`、`Phase-3` 计划、`findings` / `progress` |
| 删除（`D`） | 1 | `frontend/pictures/login_background.png`（2.35 MB，换成 81 KB 的 WebP） |

### 1.2 四个新包（1603 行）

| 包 | 文件数 | 行数 | 职责 |
|---|:-:|:-:|---|
| `backend/app/observability/` | 3 | 412 | JSON 行日志（15 模块 / 按天 / 大小滚动）+ 进程内 Prometheus 指标 |
| `backend/app/auth/` | 7 | 538 | 两张表、scrypt 哈希、自签 token、权限常量、`current_user` / `require_permission` |
| `backend/app/chat/` | 7 | 653 | 会话消息表、评审记录索引、赛题内检索、回答链路、聚合统计 |
| `backend/app/api/`（新增 5 个文件） | 5 | 677 | `auth_routes` / `user_routes` / `reviews_list_routes` / `chat_routes` / `pagination` |

配套脚本 5 个、394 行：`check_logs.py`（日志门禁）、`index_review_records.py`（记录索引回填）、`rebuild_chroma_from_parents.py`（向量库重建）、`compress_login_background.py`（压图）、`promote_e2e_teacher.py`（E2E 教师身份装置）。

---

## 2. 核心实现

### 2.1 日志：15 个目录，但只有 8 个是「必需写入者」

`logs/` 按模块分 15 个目录（`api` / `graph` / `agent` / `llm` / `retrieve` / `scoring` / `review` / `report` / `importing` / `auth` / `ai_chat` / `dashboard` / `errors` / `audit` / `frontend`），每行一条 JSON，按天滚动、超过大小切分并保留最近几份。

`scripts/check_logs.py` 是这套东西的门禁：查 15 个目录齐不齐、**8 个必需写入者**当天有没有日志、每行能否 `json.loads`、`module` 是否等于目录名、以及扫 5 类密钥模式。它有一条自我约束写在源码注释里——**白名单只减不增**：`auth` 有登录写入者后被移出白名单，`audit` 只在权限拒绝时写所以允许空，`ai_chat` 同理。

### 2.2 监听三件套：`/health` 与 `/readyz` 是两件事

- `/health` 纯进程内，永远 200，就算 MySQL 挂了也 200；
- `/readyz` 探 MySQL 与 Chroma，**两项都探完再汇总**，任一不通返回 503 并指出是哪个；
- `/metrics` 手写 Prometheus 文本（不引 `prometheus_client`），五个指标族，`+Inf` 桶必在，浮点不用科学计数法，标签做最小转义。

三个端点都跳过日志中间件——Prometheus 15 秒一抓，一天 5760 条 `api/request` 会把真正有用的日志淹掉。

### 2.3 鉴权：scrypt + 自签 token，不用 argon2 也不用 JWT

- 密码用标准库 `hashlib.scrypt`（n=2¹⁴, r=8, p=1），存 `scrypt$16384$8$1$salt$dk`；
- token 是自签三段 `v1.<b64url(payload)>.<b64url(hmac)>`，**明确不叫 JWT**；
- payload 里带 `pv = sha256(password_hash)[:16]`，改密码即全部旧 token 失效——**用 16 个字符省掉一张 token 表**；
- 登出只清前端，服务端不撤销（黑名单要么建第三张表，要么放内存重启即失效），代价与替代方案写进 `findings.md`。

### 2.4 记录总览：过滤规则是这一版唯一的安全边界

`GET /api/reviews` 的规则写成两条互斥分支：有 `review:read:all` 才可采用请求里的 `user_id`，否则**强制用 token 的 uid**。为此专门写了一条测试：「学生显式传别人的 `user_id` 仍只拿到自己的」——它比其它 11 条加起来更重要，别的失败说明功能没做对，这条失败说明数据在泄露。

详情接口对他人返回 **404 而不是 403**：403 等于告诉调用方「这个 id 存在」。计划书 §5 原写 403，与它自己给的括号理由「不暴露是否存在」自相矛盾，本版按理由实现并记了勘误。

### 2.5 AI 问询：聚合不过模型，模型只负责「讲」

- 评审记录被索引成 `doc_type="review_record"`，**一维一块**（`rr-{review_id}-{dimension_code}`），父块进 MySQL、子块进 Chroma；
- 检索复用既有 `search_children_then_parents`，**没有第二套检索**；
- 三个聚合能力（横向对比 / 冲突汇总 / 证据充分性）全部在 Python 层算，数字来自 SQL；
- 摘要的数字先算好再喂模型，模型只写文字；引用**双向校验**（剔除编造的 + 统计未引用的），有效引用不足 3 条时如实标注，不许凑。

---

## 3. 本版修掉的三个真实问题

### 3.1 向量库原生崩溃（最严重，导致 P19 门禁两度中断）

**现象**：`v3.3.5` 完成后，全量 pytest 跑到访问 Chroma 的用例就整进程消失（原生 access violation），真机问答与摘要同样中断；E2E 从 40/8 掉到 24/24。

**定位过程**（按决策树走，不猜）：

1. 只读直连 `chroma_data/chroma.sqlite3` → `embeddings` **16347** 行、`segments` = VECTOR 1 + METADATA 1 → **数据没丢**；
2. 停 8077 后 probe `get_collection().count()` → 退出码 `-1073741819`；**8077 运行中再跑，同样退出码** → 排除「单纯跨进程并发」，归到旧持久库结构/版本状态异常；
3. 新建空目录 probe → `count=0`、退出码 0 → 说明「新建能活、旧库不能」。

**处置**：旧目录完整保留为 `chroma_data.broken-2026…`（未删），从 `paper_parent` 的 5,514 个论文父块重建 20,807 个子块，再写入 102 条记录的 510 个子块，重建后 collection count = **21,317**；`review` / `review_dimension` / `paper_parent` 三张表**一行没动**。

**同时修的根因侧**：`parent_child.py` 新增 `set_client_for_tests` / `reset_client_for_tests`，`conftest.py` 加全局 autouse `isolate_chroma`——每条测试用临时 PersistentClient，测试结束删目录。**改完之后后端保持运行时连跑两遍 356 passed，且生产库 `embeddings` 前后一致**（21317 → 21317），证明测试再也不会碰生产向量库。

**一条差点翻车的教训**：中途用 `cp -r chroma_data /tmp/cc` 做副本探测，查出 `count 0`，差点写成「向量被清空」。真实原因是 66 MB 的 sqlite 边写边拷成了撕裂副本——**副本不能当证据，数据口径只认只读直连原始库**。

### 3.2 引用锚点缺失导致「定位」无从谈起

详情抽屉要展示「原句可点定位」，但 `GET /api/reviews/{id}` 的落档分支只返回档案、不含 `sections`，而定位函数需要拼好的全文。补法不是新开接口，而是让落档分支从 `review_session` 带上 `sections`（无快照则空数组）——**同一份数据两套接口，改一处必忘另一处**。

### 3.3 登录页背景 2.35 MB → 81 KB

用 Pillow 压成 1672×941 → 1600×900 的 WebP，PSNR 39.0 dB。顺带记一个坑：这台机器上 `which convert` 命中的是 `C:\Windows\system32\convert.exe`——**NTFS 文件系统工具，不是 ImageMagick**，误用会去动磁盘分区。

---

## 4. 数据现状（本版结束时实查）

| 表 | 行数 | 说明 |
|---|:-:|---|
| `review` | **109** | 评审记录（E2E 又写了 7 条） |
| `review_dimension` | **545** | 五维结果 |
| `review_session` | **188** | 会话快照 |
| `paper_parent` | **6242** | 父块（含 510 条评审记录派生的父块） |
| `user` / `permission` | **5** / **23** | 学生 3 条、教师 7 条 |
| `chat_session` / `chat_message` | **2** / **9** | AI 问询会话 |
| `agent_step` | **3066** | Agent 轨迹（Phase-2 起累积） |

向量库：`chroma_data/chroma.sqlite3` 的 `embeddings` = **22117**（重建后 21317，E2E 新增评审又写入 800）。表总数 **16**。

日志：`logs/` 15 个目录，`check_logs.py` → `[ok] 15 dirs, 8 writers, 0 issue`。

---

## 5. 接口现状（31 条）

| 分类 | 条数 | 路径前缀 |
|---|:-:|---|
| 既有业务 | 14 | `/api/contests` `/api/samples` `/api/reviews` `/api/imports` `/api/rubrics` `/api/eval` … |
| 监听 | 3 | `/health` `/readyz` `/metrics` |
| 账号 | 4 | `/api/auth/register` `/login` `/logout` `/me` |
| 用户管理 | 2 | `/api/users` `/api/users/{user_id}` |
| 记录列表 | 1 | `GET /api/reviews` |
| AI 问询 | 7 | `/api/chat/sessions`（增删查）+ `/sessions/{id}/messages`（读写）+ `/analytics` + `/summary` |

401 / 403 / 404 的口径在四个模块里保持一致：没登录 401、能力类无权限 403（列表）、查别人的私有资源 404（详情与会话）。

---

## 6. 已知边界（不写「全部通过」）

1. **P19 单条详情问询未命中指定 `review_id`**：实测「这条记录的假设维档位是什么」时，答案引用了同赛题的其他记录，未引用被问的那条。链路通、引用可溯源，但**检索精度未达标**——这是 P19 不能宣称全部能力验收通过的唯一原因。
2. **摘要数字覆盖完整性未验证**：四个维度分项合计 83，统计总数 88，差额 5 未在摘要中解释。链路能返回，但「数字不漏项」这一点没有验证通过。
3. **E2E 8 条既有红灯**：`consistency` / `parse`×2 / `scoring` / `sketch-fix`×2 / `suggestions` / `visual`，全部卡在「确认卡 5 秒超时」这一类链路上，与 `v3.2.3` 记录逐条一致，本版未引入新红。
4. **档位值两种写法**：`证据不足` 76 条、`不足` 18 条。聚合层用 `INSUFFICIENT_BANDS` 归一，**没有改数据**——改已落档的 band 等于篡改历史证据，清洗要单独立项。
5. **`logs/agent/` 仍无写入者**：Agent 轨迹以 `agent_step` 表为唯一口径，该目录预留给 P19 之后的 AI 问询子图（如需要）。
6. **3 个历史段目录未清理**：`chroma_data.broken-*` 里另有 3 个不被 sqlite 当前 segments 引用的 UUID 子目录，未删。

---

## 7. 仓库卫生

`.gitignore` 本版新增 3 条：`chroma_data.bak-*/`、`chroma_data.broken-*/`、`.pytest_tmp/`。它们对应向量库事故处置产生的 160 MB 级目录，**绝不入库**。

推前检查的三项：`.env` 未被跟踪（`git ls-files --error-unmatch .env` 报错即正常）、暂存区无真实密钥（命中的两条是 `test_check_logs.py` 里的假样例 `sk-abcdefghij1234`）、无 >200 KB 的二进制（唯一大文件是 240 KB 的 `progress.md`，文本）。

---

## 8. 怎么验这一版

```bash
# 后端（可保持 8077 运行，向量库已隔离）
BT=".pytest_tmp/run-$(date +%H%M%S)"; mkdir -p "$BT"
PYTEST_DEBUG_TEMPROOT="$BT" python -m pytest backend/tests -q --basetemp="$BT"
# → 356 passed

# 前端
cd frontend && npm run build && npx vitest run --reporter=dot && npx playwright test --reporter=list
# → 138 passed；40 passed / 8 failed（8 条为既有红灯）

# 日志门禁与文档编码
python scripts/check_logs.py
python scripts/check_docs_encoding.py docs --strict
# → EXIT=0 / EXIT=0

# 向量库自检（只读，不启动客户端）
python -X utf8 -c "
import sqlite3
db = sqlite3.connect('file:chroma_data/chroma.sqlite3?mode=ro', uri=True)
print(db.execute('select count(*) from embeddings').fetchone()[0])"
# → 22117 左右
```

---

## 9. 下一版

`v3.3.7`：前端 `/chat` 页（会话列表 + 消息流 + 引用可点回详情 + 三个聚合入口）+ P19 五条判据取证。前置是把 §6 第 1 条（单条详情命中精度）单独定位——**页面做完但引用点不到对的记录，等于没做完**。

再之后是 P20（可视化大屏，`v3.4.x`）。大屏的统计口径直接复用 `chat/analytics.py` 的三个函数，不要另写一套。
