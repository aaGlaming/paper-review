# 任务计划

当前版本 v1.9.3 已完成，首期验收收口（v1.0.0 通过）。版本顺序见 `docs/开发任务拆解与迭代流程.md`。

| 版本 | 状态 |
|---|---|
| v0.1.0 | 通过 |
| v0.2.0 | 通过 |
| v0.3.0 | 通过 |
| v0.4.0 | 通过 |
| v0.5.0 | 通过 |
| v0.6.0 | 通过 |
| v0.7.0 | 通过 |
| v0.8.0 | 通过 |
| v0.9.0 | 通过 |
| **v1.0.0** | **通过（首期验收收口）** |
| v1.9.1 | 通过（真实模型、检索/数据库与四道门禁已验；真实 rerank API 已在 v1.9.2 验收中补验） |
| v1.9.2 | 逐条验收完成，报告 V1：14 ✅ / 4 ⚠️ |
| v1.9.3 | 通过（F1–F4 修复 + 针对性复验，报告 V2：18 ✅ / 0 ⚠️） |

## v1.9.3 执行结果（全部完成）

1. [x] 为 F1–F4 编写失败测试并观察预期失败。
2. [x] 实现 prompt 链路、量规读取 API / 页面、单篇评测 API / 页面、存档 change_list 兼容。
3. [x] 运行新增测试、全量后端与前端四道门禁。
4. [x] 真调用一次 bench-dragon，并对 F2–F4 做针对性复验，留存脱敏证据。
5. [x] 生成 `docs/plan/acceptance/report-V2.md`，记录命令与退出码；v1.0.0 已更新为通过。

## 首期验收结论

- **报告 V1**（`docs/plan/acceptance/report.md`，v1.9.2）：18 条中 14 ✅ / 4 ⚠️ / 0 ❌。
- **报告 V2**（`docs/plan/acceptance/report-V2.md`，v1.9.3）：F1～F4 修复后复验，**18 条全部 ✅ / 0 ⚠️ / 0 ❌**。
- 四项修复的证据：`docs/plan/acceptance/calls/v193-01` ～ `v193-06`。
- 四道门禁：pytest **159 passed** / build 0 / vitest **110 passed** / playwright **43 passed**。
- 冻结文件零改动：`backend/tests/graph/test_interrupt.py`、`backend/tests/retrieve/test_rerank_cap.py`。

## Next Step

首期（P0～P11）已全部收口。后续方向（未排期）：论文文件上传、主张/表格/引用解析产出、三篇演示稿补 gold、可观测性、`compose.yaml` 可运行配置。
