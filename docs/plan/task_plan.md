# 任务计划

当前版本 v2.2.0 已执行（P14 功能完成，评测「证据不足命中」待复测）。版本顺序见 `docs/开发任务拆解与迭代流程.md`。

> 本文件于 2026-10-19 因编码事故整体重写：历史部分恢复自 git（内容未变），新增部分按可读数字重建。

## 首期（Phase-1）

| 版本 | 状态 |
|---|---|
| v0.1.0 | 通过 |
| v0.2.0 | 通过 |
| v0.3.0 | 通过 |
| v0.4.0 | 通过 |
| v0.5.0 | 通过 |
| v0.5.1 | 通过 |
| v0.6.0 | 通过 |
| v0.7.0 | 通过 |
| v0.8.0 | 通过 |
| v0.8.1 | 通过 |
| v0.9.0 | 通过（八个子阶段） |
| **v1.0.0** | **通过（首期验收收口）** |
| v1.9.1 | 通过（真实模型、检索/数据库与四道门禁已验；真实 rerank API 已在 v1.9.2 验收中补验） |
| v1.9.2 | 逐条验收完成，报告 V1：14 ✅ / 4 ⚠️ |
| v1.9.3 | 通过（F1–F4 修复 + 针对性复验，报告 V2：18 ✅ / 0 ⚠️） |

## Phase-2（Agent 化，P12～P15）

| 版本 | 状态 |
|---|---|
| v2.0.0 | 通过（探针判 A 路线；`chat_with_tools` + 6 条测试；pytest 165） |
| v2.0.1 | 通过（P0 定级为环境配置问题并结案；两个 LangChain 适配器；pytest 174 / Playwright 43） |
| v2.0.2 | 通过（六个工具 + 参数校验 + 唯一写口；pytest 189 / Playwright 43） |
| v2.0.3 | 通过（`agent_step` 表、线性旁路、`GET /agent-steps`；pytest 201；分数逐字不变） |
| v2.1.0 | 通过（`create_agent` 子图挂在 `score` 内部；pytest 214；真实调用五维「证据不足」） |
| v2.1.1 | 通过（无进展检测、`agent_terminated_by`、轨迹面板；pytest 218；**Playwright 退出码 1**） |
| v2.1.2 | 通过（收工协议 + `force_submit` + 预算 8→12；真实调用四维提交成功，21.5 s） |
| v2.2.0 | 通过（`critique` 只降不提；pytest 231 / 四道门禁全绿；一致率 14/60、引用 31/31；**证据不足命中 1/2 待复测**） |

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

## 阶段编排（2026-10-19 重排）

| 期 | 文件 | 阶段 | 定位 |
|---|---|---|---|
| Phase-1 | `docs/version/Phases/Phase-1/paper-review.md` | P0～P11 | 首期：五步预审主链 + 三篇演示 + 18 条验收（已收口） |
| **Phase-2** | `docs/version/Phases/Phase-2/Phase-2-plan.md` | **P12～P15** | **Agent 化：把固定管线改成有界 `create_agent` 循环** |
| Phase-3 | `docs/version/Phases/Phase-3/Phase-3-plan.md` | P16～P26 | 原第二期内容整体顺延 +4：日志监听、登录双角色、教师端三件套、解析补齐、对齐、补 gold、容器化、性能、三期验收 |

**编号口径**：期计划文档用 `Phase-<N>/Phase-<N>-plan.md`，文档版本 `v<N>.0.0`；阶段提示词用 `v<N>.<期内阶段序号>.<子任务序号>_<功能描述>.md`——**第二位是期内序号不是 P 号**（Phase-2：P12→`v2.0.x`、P13→`v2.1.x`、P14→`v2.2.x`、P15→`v2.3.x`）。这套口径与 `docs/version/v1.0.2_命名规范.md` 的「第一位固定 1、第二位＝阶段号」冲突，**以期计划为准**，已在 `findings.md` 记裁决（2026-10-19）。

## Next Step

**P14 收口还差一步**：`v2.2.1`（评测复测 + 成本实测 + critique 效果对照）。核心待确认项是「证据不足命中 1/2 还是 2/2」，需给出三种归因之一：`critique 误降` / `模型本来没判` / `gold 标注可议`。该项确认后才写 P15 的 `v2.3.0`（二期验收，产出 `report-V3.md`）。

Phase-3 的详细任务表（P21～P26）原写于已删除的 `v1.10.0_第二期计划.md`，开工前需重写细则，不凭记忆补。


## P15 验收

| 阶段 | 状态 | 证据 |
|---|---|---|
| P15 Phase-2 验收 | 部分满足 | report-V3.md；判据 5 取得 submit 层与代码路径证据，尚无真实 critique 降档轨迹；其余四条判据通过 |
