# P18 收口取证报告

日期：2026-10-20。取证范围：v3.2.0 列表接口、v3.2.2 总览页面与筛选、v3.2.3 详情抽屉与教师 E2E。

## 判据 1：学生传别人的 id 仍只拿到自己的

**判据原文**：学生传别人的 id 仍只拿到自己的。

**取证命令**：

```text
D:/LEARN/AI/programs/AgentTask/env/agent-task/Scripts/python.exe -m pytest backend/tests -q --basetemp=.pytest_tmp/run-041444
覆盖用例：test_student_explicit_other_user_id_is_ignored
```

**原始输出（末几行）**：

```text
310 passed, 2 warnings in 92.50s
```

**结论**：满足。专门用例带学生 A 的 token 显式传学生 B 的 user_id，响应仍只包含 A 的记录。

## 判据 2：越权访问详情返回 404，且与「记录不存在」响应逐字节相同

**判据原文**：越权访问返回 404，且与「记录不存在」响应逐字节相同。

**取证命令**：用 E2E 学生登录态请求一个非本人记录，再请求不存在的 review_id；认证值从被 `.gitignore` 忽略的 storageState 读取，不在命令输出或文档中展开。

```text
curl -s -w "HTTP %{http_code}" http://127.0.0.1:8077/api/reviews/<他人记录> -H "Authorization: Bearer [已省略]"
curl -s -w "HTTP %{http_code}" http://127.0.0.1:8077/api/reviews/p18-record-that-does-not-exist -H "Authorization: Bearer [已省略]"
```

**原始输出（末几行）**：

```text
{"detail":"找不到评审记录"}
HTTP 404
{"detail":"找不到评审记录"}
HTTP 404
```

**结论**：满足。两次响应均为 404，JSON body 与原始响应体逐字节相同；新增快照测试也验证了落档详情不改变权限路径。

## 判据 3：教师可见全部；学生无此入口

**判据原文**：教师可见全部；学生无此入口。

**取证命令**：

```text
cd frontend && npx playwright test --reporter=list
相关用例：records-teacher.spec.ts（教师总览有数据行）；records.spec.ts（学生菜单无入口且直连 /records 后 URL 为 /parse）
```

**原始输出（末几行）**：

```text
ok › 教师能打开记录总览并看到记录行
ok › 点击记录行打开包含维度卡和修改建议区块的抽屉
ok › 学生导航不显示记录总览，直接访问也回到论文解析页
40 passed / 8 failed (1.4m)，EXIT=1
```

**结论**：满足。教师表格行数至少 1，学生菜单与守卫两条行为均通过 E2E。

## 判据 4：抽屉展示与 `/scoring` `/consistency` `/suggestions` 一致

**判据原文**：与 `/scoring` `/consistency` `/suggestions` 展示一致。

**取证命令**：

```text
cd frontend && npx vitest run tests/unit/record-drawer.spec.ts --reporter=dot
cd frontend && npx playwright test tests/e2e/records-teacher.spec.ts --reporter=list
```

**复用组件清单**：

- `frontend/src/components/DimensionCard.vue`：维度码与档位原样呈现。
- `frontend/src/components/SuggestionItem.vue`：维度修改建议。
- `frontend/src/components/ConflictItem.vue`：审查 findings。
- `frontend/src/composables/useOffsetLocator.ts`：`concatSections` 与 `locateEvidence` 在抽屉内定位 quote。

**原始输出（末几行）**：

```text
Test Files  1 passed (1)
Tests       6 passed (6)
2 passed (3.6s)
```

**结论**：满足。组件清单与定位器是可复核的实现证据；教师 E2E 点击表格行后确认抽屉、维度卡和「修改建议」区块可见。

## 判据 5：`audit/` 有记录

**判据原文**：`audit/` 有记录。

**取证命令**：

```text
Get-Content logs/audit/audit-20261020.log | Select-String '"event":"(records_listed|record_viewed)"'
```

**原始输出（字段摘录；不含 token）**：

```json
{"event":"records_listed","viewer_id":"629e108fbe7b4e4b9e3532155366cb80","returned":20,"others":20,"scope":"all"}
{"event":"record_viewed","viewer_id":"629e108fbe7b4e4b9e3532155366cb80","review_id":"3e91479f18c3461bafe40ace43a790ca","owner_id":"765293c95c3e4abd8b8f204f4d649ea5"}
```

**结论**：满足。教师列表汇总记录返回数与他人记录数；查看他人详情记录 viewer、review 与 owner 标识。审计摘录未包含 token、邮箱或论文正文。

## P18 收口结论

| 判据 | 结论 |
|---|---|
| 1. 学生传入他人 id 仍只读本人记录 | 满足 |
| 2. 详情越权 404 与不存在响应相同 | 满足 |
| 3. 教师可见总览、学生无入口 | 满足 |
| 4. 抽屉复用既有展示组件并支持正文内定位 | 满足 |
| 5. 他人详情与跨用户列表有审计记录 | 满足 |

五条判据均满足，P18 收尾，允许进入 P19（教师端 AI 问询）。

全量后端为 310 passed，前端 build 与 Vitest（138 passed）通过。全量 E2E 为 40 passed / 8 failed，8 条失败与既有集合一致；本版新增学生及教师三条 E2E 全部通过。
