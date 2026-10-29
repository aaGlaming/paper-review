# 三期验收报告（P26）

## 一、结论

**P26 收口，三期完成：两条原 E2E 红灯已归零，末尾 `/eval` 红灯来自 `low_sample` 契约变更后的断言滞后，现已按契约修正并通过全量 E2E。**

## 二、八条非功能替代口径

需求分析 V3 第十章原文不在仓库。本表是替代口径，取得原文后需校准；不把替代值描述成原文要求。

| # | 项目 | 结论 | 本次证据 |
|---|---|---|---|
| 1 | 聚合接口响应 ≤500 ms | 满足 | 教师 `GET /api/dashboard/summary`：首次 200 / 144 ms；连续三次 200，16 / 12 / 13 ms；最大值 144 ms。 |
| 2 | 首屏入口 JS 增量 ≤400 KB raw / ≤120 KB gzip | 满足 | `npm run build` 的 `index.html` 入口 `index-C9tcL9CC.js`：1,126.98 KB / 358.89 KB；v3.8.0 基线 1,125.84 KB / 358.45 KB，增量 +1.14 KB / +0.44 KB。预算 E2E 的 `/parse`、`/records` 实际响应均为 1,126,984 raw / 355,787 gzip bytes；相对其固定首屏预算基线 +9,802 / -93 bytes。dashboard 额外 1,660,358 raw / 531,637 gzip bytes，交互 424.3 ms。 |
| 3 | 上传限额：20 MB、80 页、200,000 字符 | 满足（适用范围见证据） | `routes.py:47-48` 为 `MAX_UPLOAD_BYTES=20_000_000`、`MAX_PAPER_CHARS=200_000`；`test_byte_limit_is_injectable_and_rejected_before_writing`、`test_character_limit_is_injectable_and_rejected_before_review_or_file` 覆盖边界。PDF 运行时在扩展名校验处 415 拒绝，`test_pdf_upload_is_rejected_before_any_online_page_count_check` 证明不会在线解析；80 页规则因此不适用于当前 md/docx 上传运行时，不能声称已在线执行页数校验。 |
| 4 | 单次完整评审耗时 | 不适用（无硬门槛） | 仅引用 P25 模型路径：中位数 31,734 ms、最大值 34,201 ms；按 §8.1 撤销三分钟验收，本版只记录，不设性能门槛。 |
| 5 | 权限隔离 | 满足 | 教师 `GET /api/dashboard/summary` 返回 200；学生同接口返回 403。P25 E2E `dashboard.spec.ts` 同时覆盖教师进入与学生被拦。 |
| 6 | 日志门禁 | 满足 | `scripts/check_logs.py` EXIT=0，末行 `[ok] 15 dirs, 8 writers, 0 issue (window=20261015..20261021)`。 |
| 7 | 文档编码门禁 | 满足 | `scripts/check_docs_encoding.py docs --strict` EXIT=0，末行 `合计 126 个文件，有问题 0 个`（本报告写入前；写入后复跑结果见 progress）。 |
| 8 | 数据完整性 | 满足 | 只读 SQL：`review=240`、`rubric_id=''` 为 2、`review_artifact=24`、产物孤儿 0；教师 dashboard `total_submissions=238`、`parse_only=2`，无空赛题分组。12 个 gold JSON 的逐文件 SHA-256 门禁前后清单摘要相同：`Cc5u5w+J/uONLUxF5YMt5TRMdlPX/GQ47ZmVxAUgDWA=`；未改数据文件。 |

## 三、首期 18 条回归

| 条目 | 判定 | 本次证据及沿用理由 |
|---|---|---|
| 1.1 | ✅ | `backend/tests/importing/test_catalog.py::test_three_contests_import_with_expected_constraints`；赛题导入/约束接口仍在，且本次全量 pytest 472 passed。 |
| 1.2 | ✅ | `backend/tests/api/test_v193_read_endpoints.py::test_published_rubric_endpoint_returns_dimensions_and_four_bands`；量规读取契约仍由该用例覆盖，全量 pytest 472 passed。 |
| 1.3 | ✅ | `backend/tests/report/test_eval_gold.py::test_eval_gold_dimension_codes_match_contest_rubric_exactly` 与 `scripts/check_eval_gold.py`：12 篇、60 维、issues=0；按 §8.1 当前分母维持 12，V2 的历史 15 篇口径不再作为现行判据。 |
| 2.1 | ✅ | 全量 E2E `consistency.spec.ts` 通过；显式选择 `bench-dragon` 后页面的 `412 s`、`386 s` 与原有冲突断言通过。`backend/tests/review/test_demo_conflicts.py::test_bench_dragon_flags_both_termination_times` 仍通过。 |
| 2.2 | ✅ | `test_planting_flags_two_revenue_figures`、`test_planting_reports_missing_legume_requirement`、`test_planting_reports_missing_discount_case`；规则检查仍有单测覆盖，全量 pytest 472 passed。 |
| 2.3 | ✅ | `test_smoke_flags_both_shielding_durations`、`test_smoke_reports_missing_citation`、`test_smoke_flags_uav_speed_out_of_range`；规则检查仍有单测覆盖，全量 pytest 472 passed。 |
| 3.1 | ✅ | `frontend/tests/unit/scoring-view.spec.ts` 中“16. 读取到量规时显示维度中文名、权重和四档说明”；量规展示仍有组件测试覆盖，Vitest 162 passed。 |
| 3.2 | ✅ | `backend/tests/scoring/test_quote_and_weight.py::test_insufficient_evidence_ignores_model_score`、`test_matched_bands_enter_the_sum_by_rubric_weight`；评分排除与加权契约仍在，全量 pytest 472 passed。 |
| 3.3 | ✅ | `backend/tests/report/test_report_and_eval.py::test_every_item_carries_an_upstream_id` 与 `frontend/tests/unit/suggestions-view.spec.ts` 的 upstream 展示/定位用例；契约仍在，全量 pytest 472 passed、Vitest 162 passed。 |
| 3.4 | ✅ | `backend/tests/report/test_report_and_eval.py::test_report_text_and_api_json_have_no_award_words` 与 `frontend/tests/unit/source-scan.spec.ts`；受控词扫描仍运行，全量 pytest 472 passed、Vitest 162 passed。 |
| 4.1 | ✅ | `backend/tests/report/test_report_and_eval.py::test_run_eval_reports_source_and_calibers` 与 `frontend/tests/unit/eval-view.spec.ts` 单篇 gold 差异用例；接口和页面契约仍有测试，全量 pytest 472 passed、Vitest 162 passed。本版没有运行模型评测。 |
| 4.2 | ✅ | `frontend/tests/unit/parse-view.spec.ts` 的计时器真实递增、20 秒提示、非 running 隐藏用例；完整链路 `parse.spec.ts` 通过。计时只报告经过时间，不点亮虚构步骤。 |
| 4.3 | ✅ | `backend/tests/report/test_report_and_eval.py::test_new_review_round_trips_change_list_and_old_review_is_explained`、`backend/tests/api/test_review_list.py::test_archived_review_detail_includes_saved_sections`；旧记录兼容与存档读取仍有全量测试覆盖。 |
| 5.1 | ✅ | `backend/tests/importing/test_catalog.py::test_fixture_extra_uses_the_same_import_path` 与 `test_import_and_publish_makes_contest_readable`；导入和发布契约仍在，全量 pytest 472 passed。 |
| 5.2 | ✅ | `backend/tests/importing/test_catalog.py::test_failed_import_keeps_published_rows_unchanged`；坏包拒绝的原子性仍被覆盖，全量 pytest 472 passed。 |
| 5.3 | ✅ | `backend/tests/importing/test_catalog.py::test_copy_rubric_as_draft_bumps_version_and_keeps_single_published`；量规版本与发布状态仍有测试，全量 pytest 472 passed。 |
| 5.4 | ✅ | `backend/tests/importing/test_catalog.py::test_archived_contest_disappears_from_list` 与 review 归档读取用例；归档后列表/历史读取契约仍在，全量 pytest 472 passed。 |
| 5.5 | ✅ | `backend/tests/importing/test_catalog.py::test_backend_selection_follows_availability`、`backend/tests/llm/test_client.py::test_missing_env_raises_config_error_without_secret`；配置与模型选择约束仍有测试，全量 pytest 472 passed。 |

## 四、E2E 与门禁最终状态

- 后端 `"$PY" -X utf8 -m pytest backend/tests -q` 两遍均 EXIT=0：`472 passed, 11 warnings`，耗时 223.97 秒与 213.57 秒。
- 前端 `npm run build` EXIT=0；入口 `index-C9tcL9CC.js` 为 1,126.98 KB / 358.89 KB gzip，较 v3.8.0 基线增加 1.14 KB / 0.44 KB。`npx vitest run --reporter=dot` EXIT=0，`162 passed (162)`。
- 聚焦 `npx playwright test sketch-fix.spec.ts --reporter=list` EXIT=0：3 passed（1.2 分钟）；全量 `npx playwright test --reporter=list` EXIT=0：54 passed / 0 failed（54 条，4.3 分钟）。全量 E2E 如下：

| 用例 | 本次结果 | 结论 |
|---|---|---|
| `consistency.spec.ts` 解析确认→一致性审查 | 通过，19.8 秒 | `bench-dragon` 可选；冲突数、`412 s`、`386 s`、非「总分 0」断言通过。 |
| `parse.spec.ts` 完整演示稿 | 通过，19.5 秒 | 显式选择 `bench-dragon`；8 个 section、确认后 5 个维度。 |
| `parse.spec.ts` 粘贴 Markdown | 通过，14.1 秒 | 原有章节与维度断言通过。 |
| `scoring.spec.ts` 解析→评分 | 通过，20.5 秒 | 显式选择 `bench-dragon`；“忽略板凳宽度”定位与原断言通过。 |
| `sketch-fix.spec.ts` 评分几何 | 通过，偏差约 0.85 px | 原几何断言通过。 |
| `sketch-fix.spec.ts` 一致性几何 | 通过，偏差约 0.86 px | 原几何断言通过。 |
| `sketch-fix.spec.ts` `/eval` 三指标折线 | 通过，635 ms | 从 summary 读取 `low_sample`；两张正常卡的 path 不同，低样本卡无折线且样本提示/分母显示正确。 |
| `suggestions.spec.ts` 修改建议 | 通过，34.8 秒 | 原链路断言通过。 |
| `visual.spec.ts` 评分高亮 | 通过，42.0 秒 | 原高亮断言通过。 |

### 契约变更审计

- v3.7.2 引入 `low_sample` 呈现契约：低样本指标不画折线；unit 版 `sketch-fix.spec.ts` 已同步采用 `total=5` 的正常样本 fixture，E2E 版仍要求三张卡都画线。
- 8077 从 v3.7.2 到 v3.10.0 一直未重启，接口未返回 `low_sample`，该 E2E 因此连续六版假绿；v3.10.1 重启后首次暴露断言滞后。
- v3.10.2 的 E2E 改为读 `/api/eval/summary` 的布尔 `low_sample`：按实际值检查绘线或低样本提示；产品代码、阈值与 unit fixture 均未改。

本次完整链路 scoring 确认等待为 18,519 ms。预算用例 `/parse` 与 `/records` 各 1,126,984 raw / 355,787 gzip bytes；dashboard 额外 1,660,358 raw / 531,637 gzip bytes，交互 382.9 ms。

- `"$PY" -X utf8 scripts/check_container_skeleton.py` EXIT=0，末行 `summary checks=17 issues=0`；`"$PY" -X utf8 scripts/check_logs.py` EXIT=0，末行 `[ok] 15 dirs, 8 writers, 0 issue (window=20261015..20261021)`；`"$PY" -X utf8 scripts/check_docs_encoding.py docs --strict` EXIT=0，末行见 v3.10.2 progress。
- 全量 E2E 前后只读计数：review 254 → 262（+8）、review_dimension 1260 → 1300（+40）、review_artifact 24 → 24；新增评审为 E2E 正常链路写入，未人工清理。

## 五、三期范围裁剪

按 `docs/version/Phases/Phase-3/Phase-3-plan.md §8.1` 六项决定执行现行口径：

1. P24 容器化从可运行部署降为非验收骨架与 Dockerfile 草案；本报告不声称镜像或服务已验证。
2. 大屏模块 7 从恒为零的引用失败率改为证据不足率。
3. P22 从假设的 contest/rubric ID 对齐改为入口可评性校验；不做内容级“选错题”判定、不加 `align` 节点。
4. P23 gold 分母保持 12，不强制扩成 15。
5. P25 只做基线测量与超时可见；不做并行化，不恢复三分钟验收。
6. P21 产物范围收窄：table/citation 为收口项，claim 为最小规则实现；不进入评分或对齐链路。

## 六、遗留继承

以下四项从 P24/P25 报告继承，并继续保留：

- 镜像从未构建。
- `frontend/` 无 Dockerfile。
- Chroma tag 未验证。
- 镜像预期 ≥1GB。

## 七、挂账

- 需求分析 V3 第十章原文缺失；八条非功能只能按替代口径记录，取得原文后需校准。
- 内容级“论文选错题”判定未实现；P22 只保证不可评赛题不出结果。
- `run_eval()` 不覆盖 `agent_runner` 的工具调用、critique 降档与预算终止行为；这些仍由 `agent_step` 轨迹及既有证据衡量。
