# P21 验收报告（v3.5.6 收口）

## 结论

**P21 工程收口，允许进入 P22。** 本次核对的唯一硬缺口是需求分析 V3 §9.1 原文不在仓库，故工程推导项目不能视作已与原文校准；缺口保留，取得原文后仍须逐项校准。

## 七条判据

| 判据 | 结论 | 证据 |
|---|---|---|
| 1. §9.1 原文校准 | 缺口保留 | `Phase-3-P21-plan.md:3,18,28-43,56` 明确原文缺失并将数值/规则标为工程决策或推导。待校准项包括三类产物判定依据、20 MB/80 页/200,000 字符、Markdown 编码与换行规范化顺序、扫描件判定阈值。系统运行时不做 PDF 文本层/扫描件判定；历史 v3.5.3 的 0 非空白字符探测属于已撤回的工程实验，不是需求条款。 |
| 2. Markdown/DOCX 边界、坏文件与空抽取 | 满足 | `backend/tests/api/test_upload.py`: `test_markdown_upload_creates_review_session_and_parses_atx`、`test_utf8_bom_is_removed`、`test_gb18030_markdown_decodes_correctly`、`test_empty_or_whitespace_markdown_rejected_without_review_or_file`、`test_invalid_encoding_rejected_without_review_or_file`、`test_corrupt_docx_rejects_without_review_or_file`、`test_docx_normalized_character_limit_rejects_before_review_or_file`；`backend/tests/importing/test_docx_text.py`: `test_empty_document_or_only_empty_paragraphs_raise`。拒绝用例检查 review 计数与上传文件均未增加。 |
| 3. DOCX 转 ATX、section 解析与无标题回退 | 满足 | `backend/tests/importing/test_docx_text.py`: `test_headings_and_body_keep_document_order`、`test_chinese_heading_style_name_is_recognized`、`test_plain_paragraphs_fall_back_to_unclassified_section`。 |
| 4. 产物、偏移、顺序与只读归属读取 | 满足（claim 按最小规则版，不作为阻断项） | `backend/tests/importing/test_artifacts_extract.py`: `test_extracts_planting_markdown_table_verbatim`、`test_sentence_mentioning_table_does_not_create_table_artifact`、`test_extracts_inline_citation_but_not_reference_entries`、`test_every_artifact_span_matches_its_type_specific_text_and_ordinals_are_stable`、`test_extracts_both_conflicting_smoke_results_without_deduplication`；`backend/tests/api/test_artifacts_extract.py`: `test_first_extract_persists_artifacts_and_get_returns_ordinal_order`、`test_repeated_extract_replaces_existing_rows_idempotently`、`test_student_cannot_extract_another_users_review`。当前两条演示评审保留 24 条产物（claim 22 / table 1 / citation 1）。 |
| 5. PDF 离线处理边界 | 满足 | 当前 `backend/app/api/routes.py:444-448` 对 PDF 返回 415：「PDF 请先在外部转成文本或 Markdown 后再上传；系统不在线上解析 PDF。」P21 运行时仅接收 `.md` 与 `.docx`，归档 PDF 只作原始凭证。 |
| 6. 可观测性、受控写入与权限 | 满足 | 上传与抽取分别记 `log_event("importing", "paper_uploaded", ...)`、`log_event("importing", "artifacts_extracted", ...)`，实现位于 `backend/app/api/routes.py`；`backend/tests/api/test_upload.py`: `test_missing_token_is_rejected_without_review_or_file`、`test_student_without_review_create_is_forbidden`；`backend/tests/api/test_artifacts_extract.py`: `test_student_cannot_extract_another_users_review`、`test_extract_log_contains_counts_without_source_text`。 |
| 7. P22 消费契约 | 原判据失效；替代判据满足 | 原 §7 判据「P22 消费契约由 align 侧验证」随 P22 改为入口校验而失效。替代判据为当前全部 24 条产物在关联 `ReviewSession.paper_text[char_start:char_end]` 上逐字等于对应正文列。只读 SQL 回读 24/24，mismatches=0；类型计数 claim 22 / table 1 / citation 1。v3.5.5 的逐字示例见下方端到端证据。 |

## 端到端证据

| 演示稿 | review_id | count / by_type | 截图 |
|---|---|---|---|
| smoke | `2446e390294542efbe3afddf637065a1` | 11；claim 10、table 0、citation 1 | [`v3.5.5-artifacts-smoke.png`](screenshots/v3.5.5-artifacts-smoke.png) |
| planting | `833f43f990284c19834ae1742d8425cb` | 13；claim 12、table 1、citation 0 | [`v3.5.5-artifacts-planting.png`](screenshots/v3.5.5-artifacts-planting.png) |

从 `paper_text` 按接口偏移回读的逐字片段（v3.5.5 已记录；本版再次逐条核验全库 24 条）：

- smoke claim `[132,186)`：`按题目给定的\n投放与起爆时序求解，得到有效遮蔽时长为 22.4 s，并给出使遮蔽时间更长的投放策略[12]。`
- planting table `[643,705)`：`| 项目 | 数值 |\n| --- | --- |\n| 七年总收益（万元） | 974 万元 |\n| 求解状态 | 最优 |`

## 口径说明

- PDF 只作为离线原始凭证；离线 OCR 或文本整理结果以 Markdown 导入，运行时不解析 PDF，也不判断文本层或调用 OCR。
- `claim` 按 Phase-3 §8.1 只保留最小规则抽取，不作为 P21 收口阻断项；table 与 citation 是收口项。原因是 P22 改为入口校验后，产物没有 align/评分消费者，仅保留展示价值；主张判定又比表格结构与引用标记更主观。
- §9.1 未找到，因此所有工程推导仍须原文补齐后校准；本报告没有把推导冒充需求原文。

## 遗留

- **唯一硬缺口：需求分析 V3 §9.1 原文缺失**；工程推导项目需在取得原文后校准。
- P22 不做论文内容级「选错题」判定；只校验赛题存在且有已发布量规，并在确认页展示赛题名与量规版本。
- 产物面板尚无按类型筛选与导出。
- 公式与图注尚未抽取；当前没有字段契约或下游消费方。
- E2E 有 8 条既有失败，均等待确认链路产生 `confirmed-card`，属 P18 确认链路 25–40 秒延迟债；本版新增失败 0。
- `pdfminer.six` 与 `pypdf` 已按 2026-10-21 PDF 运行时口径撤回；未接路由的解析器及专属测试已删除，旧探测矩阵与 OCR 耗时仍保留在 progress 作为历史证据。

## P22 交接

- 可校验对象：赛题是否存在、该赛题是否有已发布量规。`report_rubric.load_review_inputs(contest_id)` 无已发布量规时返回空维度、`rubric_id=None`，应以 HTTP 422 拒绝开始评审；建议 detail 明示「该赛题不存在或没有已发布量规，无法开始评审」。当前文档裁定状态码为 422，文案是可读契约建议，需在 P22 实现与测试时固定。
- 不做内容级「选错题」语义判定。`CreateReviewRequest` 没有 `rubric_id`，量规由 contest 反查，所以「contest/rubric 不匹配」不是有效检查项，不应写入 P22 提示词。
- 确认页展示数据来源：已有 `GET /contests` 与 `GET /contests/{id}/rubric`（`backend/app/api/routes.py:892,908`；前端 API 封装在 `frontend/src/api/index.ts:159,164`），承载组件为 `frontend/src/views/论文解析.vue` 的确认结果卡。
