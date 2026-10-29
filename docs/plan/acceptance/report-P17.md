# P17 收口取证报告

日期：2026-10-20。鉴权翻转与本地门禁已完成；全量 E2E 必须由人类在本机终端执行，结果回贴后更新本报告末尾结论。

## 判据 1：两张表建表幂等；`user_id` 独立且与 `permission.user_id` 外键一致

**判据原文**：两张表建表幂等；`user_id` 独立且与 `permission.user_id` 外键一致。

**取证命令**：指定解释器调用 `create_auth_schema()` 两次；`SHOW CREATE TABLE permission`。

**原始输出**：

```text
permission
CREATE TABLE `permission` (
  `permission_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `permission` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `resource` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `granted_at` datetime NOT NULL,
  `granted_by` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  PRIMARY KEY (`permission_id`),
  UNIQUE KEY `uk_user_permission` (`user_id`,`permission`,`resource`),
  CONSTRAINT `permission_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
EXIT=0
```

**结论**：满足。两次调用均完成，权限表外键明确指向 `user.user_id`。

## 判据 2：注册→登录→登出→再登录；错误文案不泄露用户名是否存在

**判据原文**：注册 → 登录 → 登出 → 再登录全流程通；错误文案不泄露“用户名是否存在”。

**取证命令**：MySQL + 8077 调用 `/api/auth/register`、`/api/auth/login`、`/api/auth/logout`；比较未知用户名与错误密码的登录响应。

**原始输出**：

```text
REGISTER_HTTP=201 USERNAME=p17ev1020030843
DUPLICATE_HTTP=409 MESSAGE={"detail":"该注册信息不可用"}
LOGIN_HTTP=200
LOGOUT_HTTP=204
RELOGIN_HTTP=200
UNKNOWN_LOGIN_HTTP=401 WRONG_PASSWORD_HTTP=401 SAME_MESSAGE=True
```

**结论**：满足。注册冲突文案为统一文案；未知用户名与错误密码返回相同 401 文案；登出事件和状态码均有记录。

## 判据 3：学生调 `/api/users` 得 403；教师调得 200

**判据原文**：学生调 `/api/users` 得 403；教师调得 200。

**取证命令**：MySQL + 8077 学生请求；`pytest backend/tests/auth/test_permissions.py::test_student_list_users_403_without_permission_code backend/tests/auth/test_permissions.py::test_teacher_list_users_200_without_password_hash -q`。

**原始输出**：

```text
STUDENT_USERS_HTTP=403 BODY={"detail":"没有权限执行该操作"}
..                                                                       [100%]
2 passed in 3.59s
PERMISSION_EVIDENCE_EXIT=0
```

**结论**：满足。线上学生得到 403；教师 200 由真实 API 的角色测试覆盖。

## 判据 4：前端路由守卫生效；登录页背景图正确显示且体积已压缩

**判据原文**：前端路由守卫生效；登录页背景图正确显示且体积已压缩。

**取证命令**：`Get-Item frontend/pictures/login_background.webp`；`cd frontend && npm run build`、`npx vitest run`；E2E 全量由人类外测。

**原始输出**：

```text
frontend/pictures/login_background.webp Length=81514
dist/assets/login_background-DWzgaFN_.webp 81.51 kB
✓ built in 970ms
BUILD_EXIT=0
Test Files  21 passed (21)
Tests  125 passed (125)
VITEST_EXIT=0
75 个文档全部通过，0 错误
DOCS_ENCODING_EXIT=0
```

**结论**：部分满足。压缩图和 build、路由单测均通过；登录后浏览器链路及未登录直达 `/parse` 由外部 E2E 回归补证。

## 判据 5：`auth/` 有登录成败记录；新评审记录带 `user_id`

**判据原文**：`auth/` 日志目录有登录成败记录；`review` 表新记录带 `user_id`。

**取证命令**：统计 `logs/auth/` 当日日志并摘录 `login_success` 安全字段；`stu001` 登录后 create→resume；按 review_id 查询 `review` 与 `review_session` 的 owner，并与 `user.username='stu001'` 比较。

**原始输出**：

```text
AUTH_FILES=1 TODAY_EVENTS=43 LOGIN_SUCCESS=18 LOGIN_FAILED=4 LOGOUT=2
{"ts":"2026-10-20T03:08:45.150-07:00","module":"auth","event":"login_success","user_id":"4eb2c044e79443849258a00a42e0a2ab"}
STU001_LOGIN_HTTP=200 ROLE=student
STU001_CREATE_HTTP=201 REVIEW_ID=3e91479f18c3461bafe40ace43a790ca
STU001_RESUME_HTTP=200 REVIEW_ID=3e91479f18c3461bafe40ace43a790ca
3e91479f18c3461bafe40ace43a790ca 765293c95c3e4abd8b8f204f4d649ea5 True
3e91479f18c3461bafe40ace43a790ca 765293c95c3e4abd8b8f204f4d649ea5 True
```

**结论**：满足。日志字段摘录不含 token；数据库中正式评审及会话快照的 owner 均匹配该学生。

## 判据 6：四道门禁；既有测试没有为翻转放宽断言

**判据原文**：四道门禁全 0；既有 159 个后端测试一个没红（登录是新增路径，不改既有断言）。

**取证命令**：指定解释器全量后端 pytest（全新 basetemp）、`python scripts/check_logs.py`、`cd frontend && npm run build`、`npx vitest run`、`npx playwright test --reporter=list`、`python scripts/check_docs_encoding.py docs --strict`。

**原始输出**：

```text
291 passed, 2 warnings in 39.41s
FULL_PYTEST_EXIT=0
[ok] 15 dirs, 8 writers, 0 issue
CHECK_LOGS_EXIT=0
✓ built in 970ms
BUILD_EXIT=0
Tests  125 passed (125)
VITEST_EXIT=0
```

E2E 基线来源（不是本轮本地复跑）：

```text
E2E 基线 37 passed / 8 failed，2026-10-20 17:19 由另一执行器在同一机器实测
（命令：npx playwright test --reporter=list，2.0 min，EXIT=1），非本轮本地复跑；
失败集合：consistency / parse×2 / scoring / sketch-fix×2 / suggestions / visual。
```

失败归类依据：`v3.0.2` §4 将环境类列为 A、数据类列为 B；`docs/plan/progress.md` 的 v3.1.1 P8 复核记录了这八项的具体成因。consistency、scoring、sketch-fix 两项、suggestions、visual 共六项走确认链路，空白模型占位被 `.env` 回填后落入不可达的模型路径，resume 500；parse 两项是 `demo-item` 数量断言期望 3、当前样例为 10。两类原因均不由 P17 鉴权翻转引起。

```text
E2E 本轮外测：等待人类回贴。当前执行 shell 命中 spawn EPERM，未在本轮本地复跑。
```

本版既有测试改动清单：

- `test_me_needs_bearer_token`：增加 `anonymous` marker，让无 header 的 401 不被默认身份注入遮住，断言未改。
- `test_list_users_without_or_expired_token_401`：同样增加 marker，断言未改。
- `test_create_review_without_token_stores_null`：旧行为已删除，拆成匿名创建 401（更严）及 store 层空串落 NULL；另有八条新鉴权测试。
- 冻结文件 `test_interrupt.py`、`test_rerank_cap.py` 未改；其余既有测试断言未改。

**结论**：部分满足。pytest、build、Vitest 三条本地门禁为绿；E2E 当前外测待回贴，不能写成已复测或已确认不劣化。若回贴与 37/8 基线及失败集合逐条一致，判据维持部分满足（8 条既有红灯为 6 条环境、2 条数据，与 P17 无关）。

## P17 收口结论

| 判据 | 状态 |
|---|---|
| 1 两表幂等与外键 | 满足 |
| 2 注册、登录、登出、再登录与统一错误文案 | 满足 |
| 3 学生 403、教师 200 | 满足 |
| 4 路由守卫与压缩背景图 | 部分满足，浏览器外测待回贴 |
| 5 登录日志与评审 owner | 满足 |
| 6 四门禁与既有断言 | 部分满足，E2E 外测待回贴 |

当前暂缓最终裁决，等待人类全量 E2E 输出核对 37/8 及失败集合。核对一致后，P17 可按“三条绿、E2E 保持既有红灯不劣化”收口并进入 P18；若无法外测，则按 P9 记部分满足并创建 v3.1.6 专项复核，不得把 E2E 写成通过。
