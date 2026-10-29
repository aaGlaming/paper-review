# P22（P18）赛题可评校验与确认页信息细则

> 本文按 Phase-3 §8.1 的 2026-10-21 二次修正重写 P22。只校验评审入口是否具备可用赛题量规；不判断论文内容与赛题语义是否匹配。

## 1. 证据来源与缺口

| 结论 | 来源 | 可核对内容与边界 |
|---|---|---|
| P22 的实际范围是入口可评校验，不是评分图 align | `docs/version/Phases/Phase-3/Phase-3-plan.md:481-488,498,505` | 计划规定校验赛题存在且有已发布量规，不满足返回 422；确认页展示赛题名与量规版本；不做内容级「选错题」判断。P22 原始逐任务表随旧计划删除。 |
| 原始任务表缺失 | `docs/version/Phases/Phase-3/Phase-3-plan.md:488` | 计划说明具体任务与风险原列于已删除旧文件，因此本细则按现存计划框架和代码重写，不凭记忆补条款。 |
| 需求原文缺口 | 当前仓库 `docs/` 检索未找到需求分析 V3 §9.2 | P22 原始任务表已随旧计划删除，本细则按框架重写；需求 §9.2 原文同样不在仓库。本文是可核对计划和实现契约，不冒充需求原文。 |
| 请求字段没有 rubric_id | `backend/app/api/routes.py:65-71` | `CreateReviewRequest` 只收 `paper_text`、`sample_id`、`contest_id`；量规由赛题反查。因此 contest/rubric mismatch 不存在可比较的两个请求值。 |
| 创建流程的副作用顺序 | `backend/app/api/routes.py:406-431` | 现状先解析正文、运行 `create_review`，再保存 `review_session`；在校验前传入不存在的赛题实测 HTTP 201，body 原文：`{"review_id":"a7d0647e1dfb496db9afd745c0655594","status":"待确认","sections":[{"title":"摘要","section_type":"未分类","level":1,"content":"P22 改前行为探针。"}]}`。这次请求只增加一个 `review_session`，没有新增 `review`。 |
| 量规加载语义 | `backend/app/report/rubric.py:37-45,47-89` | 空值、无已发布量规返回 `rubric_id=None`、`rubric_version=None`、`dimensions=[]`、`constraints=[]`；找到量规后再加载其维度。 |
| 评分前当前存在确定性空量规回退 | `backend/app/api/routes.py:557-586,627-645` | resume 当前允许无 rubric 继续，并在模型路径之外调用 `deterministic_results(paper_text, dimensions)`；这会使不可评请求得到 200 空结果。本版要求先拒绝，不能用确定性回退冒充评分。 |
| 赛题和量规读取接口 | `backend/app/api/routes.py:892-914`；`frontend/src/api/index.ts:147-165` | `GET /contests` 默认列发布赛题并返回 `title`；`GET /contests/{contest_id}/rubric` 返回已发布量规及 `version`、`dimensions`，没有量规时返回 404。 |
| 数据库现状（本机只读 SQL，2026-10-21） | `contest`、`rubric`、`dimension` 表联查 `status` 与维度数 | 实测 5 条赛题：4 条有 published 量规，其中发布赛题 3 条、归档赛题 1 条；各 published 量规均有 5 个维度。另 1 条发布赛题仅有 draft 量规，其 published 维度数为 0。该映射反映当前数据库，不构成固定赛题清单。 |
| 前端当前确认卡尚未显示赛题名 | `frontend/src/views/论文解析.vue:27-43,109-121,319-349` | 页面当前加载赛题列表与样例；已确认卡只显示状态、维度数、量规版本和来源，没有赛题名，也未在选题时读取 rubric 详情。 |
| P21 的空赛题路径必须保留 | `docs/plan/acceptance/report-P21.md:23-29`；P0 数据库核对 | 两条留存演示评审的 `contest_id` 为空且 24 条产物保留。创建评审接口的空 `contest_id` 路径继续用于解析；本版不回写历史评审和产物。 |

## 2. 「可评」的定义

一次评分只有同时满足以下三项才可评；三个条件缺一即不可评：

| 条件 | 数据来源 | 判断方式 |
|---|---|---|
| 赛题存在 | `contest` 表（`backend/app/importing/models.py` 的 `Contest`） | `contest_id` 能在目录表中找到对应记录。赛题状态不额外推导成需求条件；唯一要求是存在。 |
| 存在已发布量规 | `rubric` 表及 `Rubric.status == published` | `load_review_inputs(contest_id)` 返回非空 `rubric_id`。草稿或归档量规不能代替已发布量规。 |
| 量规维度非空 | `dimension` 表，经 `load_review_inputs` 读取 | 返回的 `dimensions` 至少有一项；空维度量规不能评分。 |

该定义只说明输入是否足以评分，不表示论文内容与题面相符，也不承诺评分结果质量。

## 3. 两处校验契约

### 3.1 `POST /api/reviews`：软校验

| 项 | 契约 |
|---|---|
| 触发条件 | `contest_id` 为空时跳过校验并允许创建解析会话；非空时赛题不存在、没有 published 量规，或 published 量规的 dimensions 为空。 |
| 失败响应 | HTTP 422，body 为 `{"detail":"该赛题不存在或没有已发布量规，无法开始评审"}`。 |
| 成功响应 | 仍为 HTTP 201，形状 `{review_id, status, sections}`。空赛题或有效赛题都先建立待确认解析会话，不返回档位。 |
| 写库边界 | 拒绝时在正文解析图、`review_session` 写入之前结束，不创建 `review` 或 session。空 `contest_id` 正常解析时写待确认 session，并写一条无量规、无维度的 parse-only `review` 父记录：这是 `review_artifact.review_id` 外键要求，不能用于评分。有效赛题的创建阶段只写待确认 session。 |
| 日志 | 拒绝时写 `log_event("review", "review_rejected", reason=..., contest_id=...)`；不写正文。 |

### 3.2 `POST /api/reviews/{review_id}/resume`：硬校验

| 项 | 契约 |
|---|---|
| 触发条件 | resume 读取会话的 `contest_id` 后，`load_review_inputs` 的 `rubric_id is None` 或 `dimensions` 为空。空赛题也属于不可评。 |
| 失败响应 | HTTP 422，body 为 `{"detail":"该赛题没有已发布量规，无法评分"}`。 |
| 成功响应 | 量规有效时保持改动前状态码与报告响应形状，返回量规维度对应的评分；模型不可用时仍可走既有确定性路径，但不能在空量规下运行。 |
| 写库边界 | 校验在恢复/推进图、索引准备、确定性结果、`save_session`、`save_review` 之前。拒绝时不写 `review`、`review_dimension` 或 session，不产生任何档位，也不触发检索索引写入。 |
| 日志 | 拒绝时写 `log_event("review", "review_rejected", reason=..., contest_id=...)`；不写正文。 |

## 4. 为什么不做内容级对齐

「论文与题面语义不符」需要取得题面正文，并对题面与论文内容做语义比对；这才是 `align` 的真实工作。赛题存在、已发布量规存在，只能证明这份输入可以评审，不能证明用户没有选错题。本阶段不实现内容级判定，不以赛题编号、标题或关键词匹配假装覆盖该问题。

只有同时满足以下升级条件，才另立版本恢复内容级 `align` 评估：找到需求分析 V3 §9.2 原文；题面全文有稳定、可用的数据来源；业务方给出明确可验证的判定信号与误判处置规则。即使满足条件，也需单独验证，不能隐式扩进本入口门禁。

## 5. 前端确认页契约

- 选中赛题后，用 `GET /contests` 的 `title` 展示赛题名；再用 `GET /contests/{id}/rubric` 的 `version` 与 `dimensions.length` 展示量规版本和维度数，格式为「赛题名 · 量规 vN · N 个维度」。
- 量规请求返回 404 时显示「该赛题没有已发布量规，暂时无法评分」，评分确认按钮禁用；其他读取错误也不能把状态当成可评，应展示错误并保持评分按钮禁用。
- 创建非空赛题评审的提交按钮在确认 rubric 可用前禁用，避免把前端 422 当成正常交互；后端仍必须独立校验，不能信任前端状态。
- `contest_id` 为空时显示「未绑定赛题 · 仅解析」。允许继续提交正文/样例做解析与调用既有产物抽取端点；不调用评分，不为无量规结果生成空档位。为满足产物表的 review 外键，创建解析会话时会同步建立无量规、无维度的 parse-only `review` 父记录。已有两条留存演示记录与产物保持可读，不更新它们。
- 元信息在选题区与确认结果卡均可见；确认卡须显示赛题名、量规版本和维度数。数据请求继续复用 `frontend/src/api/index.ts` 的 `listContests` 与 `getContestRubric`，不新增路由。

## 6. P22 可验证判据

- [ ] 空 `contest_id` 的创建返回 201，产生待确认解析 session 与不参与评分的 parse-only `review` 父记录；既有抽取端点可写入产物且不生成档位。
- [ ] 不存在的非空 `contest_id` 返回 422 与约定 detail，`review`、`review_session` 行数不变。
- [ ] 只有 draft 量规或 published 量规无维度时创建返回 422 与同一 detail，拒绝前无评审/session 写入。
- [ ] 不可评会话 resume 返回 422 与约定 detail；mock/spy 证明 `resume_review` 与 `deterministic_results` 均未调用，`review`、`review_dimension`、`review_session` 行数不变。
- [ ] 有非空 published 量规的会话仍完成既有评分流程，响应中的量规版本与维度数正确。
- [ ] 前端从两个既有接口显示赛题名、量规版本、维度数；无量规状态展示原因并禁用创建/评分动作；空赛题显示「未绑定赛题 · 仅解析」且可创建解析会话。
- [ ] 两类后端拒绝各有 `review_rejected` 结构化日志，不包含论文正文。
- [ ] 全程不新增评分图节点、不更改历史数据、不写 Chroma；留存空赛题演示与产物数量前后相同。

## 7. 非目标

- 不实现论文与题面语义匹配，不做内容级「选错题」判断；不对比 contest/rubric ID，因为请求没有 `rubric_id`。
- 不改 `build_review_graph`、不加 `align` 节点、不改 `test_interrupt.py` 或评分图结构。
- 不做 PDF 解析或 OCR，不改变产物抽取规则；仅允许空赛题 parse-only 会话复用既有抽取端点，不回写历史 `review`、`review_session`、`review_dimension` 或 `review_artifact`。
- 不改导航、不加路由；本版只扩展现有论文解析页的信息与按钮状态。
