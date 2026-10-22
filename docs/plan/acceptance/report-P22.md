# P22 验收报告（v3.6.1 收口）

## 结论

P22 的入口可评性校验与确认页展示有可追溯的测试和 live 证据，统计层已将仅解析记录从提交口径排除。**本阶段只保证不可评的赛题不出结果，不保证论文与赛题匹配**。内容级「选错题」判定仍未实现；本报告完成门禁复核后，P22 工程收口，允许进入 P23。

## 八条判据

| 判据 | 结论 | 证据 |
|---|---|---|
| 1. 空 contest 创建 parse-only 会话，可抽取产物且不生成档位 | 满足 | `backend/tests/api/test_review_gate.py::test_empty_contest_id_still_creates_parse_session`、`test_empty_contest_parse_session_can_extract_artifacts_without_scoring`：创建 201，抽取 200，dimension=0。 |
| 2. 不存在赛题创建被拒且无写入 | 满足 | `test_nonexistent_contest_is_rejected_before_review_or_session_write`：422，detail 为「该赛题不存在或没有已发布量规，无法开始评审」；live 拒绝前后行数待最终门禁后填入。 |
| 3. draft-only / published 无维度均不可评 | 满足 | `test_draft_only_rubric_is_rejected_without_database_writes`、`test_published_rubric_without_dimensions_is_not_evaluable`、`test_resume_with_empty_published_rubric_is_rejected`，均断言 422 和拒绝前后行数相同。 |
| 4. 不可评 resume 不调用评分图或 deterministic fallback | 满足 | `test_resume_without_rubric_does_not_run_graph_or_deterministic_scoring`：spy 调用列表为空；另有 `test_resume_without_published_rubric_returns_422_without_review_rows` 锁定 422。 |
| 5. 有量规会话完成评分 | 满足 | v3.6.0 live：`df92092fca624e57a6f35903ce8e90a8`，创建 201，published rubric v1、5 dimensions；resume 200、状态「完成」、5 dimensions，7,284 ms。 |
| 6. 确认页元信息、不可评禁用、空赛题仅解析 | 满足 | `frontend/tests/unit/parse-view.spec.ts`：`确认区显示所选赛题、published 量规版本与维度数`、`无 published 量规时说明原因并禁用创建入口`、`空赛题仍可创建解析会话，并明确标记为仅解析`；vitest 全量结果见 v3.6.1 progress。 |
| 7. 两类拒绝均有不含正文的日志 | 满足 | `test_unavailable_contest_rejections_write_review_rejected_events`：两条 `("review", "review_rejected")`；字段含 `reason`、`contest_id`（resume 另含 review_id），不含 `paper_text` 或正文。 |
| 8. 不改图节点、历史行或 Chroma；演示数据保留 | 满足 | 门禁前只读 SQL：`review=180`、parse-only=2、`review_artifact=24`（claim 22 / table 1 / citation 1）；最终 E2E 后为 `review=196`、`review_session=322`、`review_dimension=970`、`review_artifact=24`。P21 演示评审仍为 `2446e390294542efbe3afddf637065a1` 与 `833f43f990284c19834ae1742d8425cb`。本版仅改 dashboard 查询与前端说明，没有改评分图、Chroma 或业务表。 |

## 契约变更审计

以下是 v3.6.0 对既有测试契约的修正，来源为 `docs/plan/progress.md` 的 v3.6.0 段：

| 文件与用例 | 原断言 | 新断言 | 理由 |
|---|---|---|---|
| `backend/tests/api/test_auth_required.py::test_student_create_review_persists_student_owner` | 使用 `contest_id="c1"` 并期望创建成功 | 使用空 `contest_id` 验证 student owner | SQLite fixture 未建赛题目录；该用例验证归属，应走合法 parse-only 路径。 |
| `backend/tests/auth/test_permissions.py::test_create_review_with_token_stores_owner` | 使用 `contest_id="c1"` 并期望创建成功 | 使用空 `contest_id` 验证 owner 写入 | 同上，避免把无效赛题误作可评赛题。 |
| `backend/tests/report/test_review_flow.py::test_unbound_contest_yields_empty_dimensions_and_no_change_list` | 空赛题 resume 期望 200 和空结果 | 重命名为 `test_unbound_contest_cannot_resume_without_published_rubric`，断言 422 | 评分必须有已发布量规，空结果不能冒充评分。 |
| `backend/tests/chat/test_chat_sessions.py::test_list_sessions_sorts_updated_descending` | 两行依赖相同时间精度下的更新时间排序 | 明确设置相差 1 秒的更新时间后断言降序 | 消除相同时间戳造成的随机并列，保留排序语义。 |

## 统计口径修正

改动前的教师接口实测摘录：

```json
{"cards_total_submissions":180,"cards_weekly_new":180,"empty_contest":{"contest_id":"","review_count":2}}
```

改动后的教师接口实测摘要：

```json
{"cards":{"total_submissions":178,"weekly_new":178,"parse_only":2},"contests":[{"contest_id":"cumcm-2024-A","review_count":168},{"contest_id":"cumcm-2024-C","review_count":6},{"contest_id":"cumcm-2025-A","review_count":1},{"contest_id":"probe-critique-acceptance","review_count":3}]}
```

改后赛题分组不含空 `contest_id`。两个 parse-only 父行及其产物保持不变，仅从已评分提交统计中排除。大屏显示「总提交 178」并在指标卡下解释「另有 2 篇仅解析未评分」。截图因数字口径变更后重拍：[`v3.6.1-dashboard.png`](screenshots/v3.6.1-dashboard.png)。

## 门禁与数据库差额

全量 pytest 两次各 `465 passed, 11 warnings`；Vitest `157 passed`；最终 Playwright `46 passed / 8 failed`，失败均为既有 `confirmed-card` 等待超时，本版新增失败 0。第一次 Playwright 运行错误复用了占据 5174 的 Vite dev server，导致预算用例读到开发依赖模块并多出 1 个环境性失败；停止冲突进程后，预算用例单测通过，且全量 Playwright 复跑达到上述 46/8。预算实测 `/parse`、`/records` 各 raw 1,125,585 B / gzip 355,229 B，dashboard 额外 1,658,959 B，可交互 372.9 ms。E2E 正常 API 写入使门禁前 review/session/dimension/artifact `180/306/890/24` 变为 `196/322/970/24`；差值 `+16/+16/+80/0`，属于两次完整 E2E 链路的正常写入，不是手工数据修改。8 条确认链路超时按 P25 范围记录。

## 遗留

- 不做论文内容级对齐或「选错题」判定；入口只核验赛题存在与已发布且有维度的量规。
- parse-only 仍以 `rubric_id=''` 作哨兵，语义脆弱；后续可评估独立 `kind` 字段。
- 历史不可评记录保持只读；尝试 resume 时按新契约返回 422，不回溯改写。
- 产物面板尚未提供按类型筛选与导出。
- 公式与图注未抽取，目前没有字段契约与消费方。
- 8 条 E2E 确认链路超时属于 P25 范围；v3.6.1 应报告新增失败数。不得把这项写作本版新增缺陷。

## P23 交接

- Gold 目录为 `data/samples/eval/`，当前 12 个 `.md` 和 12 个同名 `.json`。字段为 `paper_id`、`contest_id`、`title`、`gold`、`expected_findings`；`gold` 对照五个维度的 `dimension_code` / `band`。README 声明这些是自建评测稿，数值为构造值。
- Phase-3 §8.1 已裁定维持 12 篇，可选补 1 篇，不强制补到 15；新增 3 篇需人工标注 15 个档位且对一致率说服力有限，本版未改 gold 数据。计划首页摘要仍有旧的「12→15」表述，P23 开工前应以 §8.1 为准并同步摘要。
- 评测入口：`backend/app/review/samples.py::load_eval_papers()` 读取 `data/samples/eval/`；`backend/app/report/evaluation.py` 的 `run_eval` / `summarize_eval` 对比档位一致率、引用精确匹配、证据不足命中率。
- 当前档位分母为 60 个 gold 维度（12×5），证据不足分母为 2；补 1 篇后档位分母变为 65，三篇则为 75。引用精确匹配分母取决于系统产生引用的维度数，证据不足分母取决于新增 gold 标注。新样本会改变重新计算的指标分母与比率；历史报告数字仍是其当时数据集上的结果，不应被静默改写。
