/**
 * 后端接口的响应类型。
 *
 * 字段名一律照抄接口的实测响应，不按想象命名：本文件是页面取字段的唯一依据。
 */

/** 赛题当前那一版量规的索引。 */
export interface ContestRubric {
  rubric_id: string
  version: number
  status: string
}

/** 赛题约束。check_type 只注册三种：mention / numeric_range / required_case。 */
export interface ContestConstraint {
  constraint_id: string
  name: string
  check_type: string
  params: Record<string, unknown>
  section_types: string[]
}

/** `GET /api/contests` 的 `contests[]` 一条。约束挂在赛题上，不另开接口。 */
export interface ContestSummary {
  contest_id: string
  year: number
  problem_code: string
  title: string
  statement: string
  status: string
  rubric: ContestRubric | null
  constraints: ContestConstraint[]
  pitfall_count: number
  exemplar_count: number
}

export interface ContestListResponse {
  contests: ContestSummary[]
}

/** `GET /api/samples` 的 `samples[]` 一条。`has_gold` 为真才可以进评测分母。 */
export interface SampleItem {
  sample_id: string
  title: string
  is_demo: boolean
  contest_id: string
  has_gold: boolean
}

export interface SampleListResponse {
  samples: SampleItem[]
}

/** 一项评测指标。分母为 0 时 `rate` 为 null，`caliber` 里写明口径。 */
export interface EvalMetric {
  matched: number
  total: number
  rate: number | null
  caliber: string
}

/** `GET /api/eval/summary`。`source` 为 deterministic 时这批数字是脚本自检，不是模型准确率。 */
export interface EvalSummary {
  corpus_papers: number
  gradable_papers: number
  gradable_dimensions: number
  source: string
  band_agreement: EvalMetric
  quote_exact_match: EvalMetric
  insufficient_evidence_hit: EvalMetric
  no_samples: boolean
  demo_papers_without_gold: number
  note: string
}

export interface RubricBandText {
  band: string
  score: number | null
  description: string
}

export interface RubricDimensionText {
  dimension_code: string
  name: string
  weight: number
  bands: RubricBandText[]
}

export interface PublishedRubricText {
  contest_id: string
  rubric_id: string
  version: number
  dimensions: RubricDimensionText[]
}

export interface EvalPaperDifference {
  dimension_code: string
  gold_band: string | null
  system_band: string | null
  matches: boolean
}

export interface EvalPaperResult {
  paper_id: string
  title: string
  source: string
  gold_available: boolean
  explanation: string | null
  gold: Array<{ dimension_code: string; band: string }> | null
  system: Array<DimensionResult> | null
  differences: EvalPaperDifference[] | null
}

/** 章节树的一条。`level` 是标题级别，层级在页面上用缩进表达。 */
export interface PaperSection {
  title: string
  section_type: string
  level: number
  content: string
}

/** `POST /api/reviews` 的响应：停在确认节点，响应里没有档位字段。 */
export interface ReviewCreated {
  review_id: string
  status: string
  sections: PaperSection[]
}

/** `GET /api/reviews/{id}` 落在会话快照上时的响应：尚未确认，没有档位。 */
export interface ReviewPending {
  review_id: string
  status: string
  sections: PaperSection[]
  confirmed: boolean
}

/** `resume` 响应的 `dimensions[]` 一条。`band` 为「证据不足」时 `quote` 为 null。 */
export interface DimensionResult {
  dimension_code: string
  band: string | null
  chunk_ids: string[]
  quote: string | null
  status: string | null
}

/**
 * `change_list[].evidence[]` 的一条，两种形状合在一个类型上，**两组字段都可选**：
 * - 审查类条目（数字冲突 / 越界 / 未提到条件 / 缺少情形 / 引用缺失）：带 `char_start`、`char_end`，
 *   这是「点击滚动到偏移」唯一的数据来源；
 * - 维度类条目（证据不足 / 表述）：带 `band`、`status`、`chunk_ids`，没有字符偏移。
 *
 * 页面必须先判形状再取字段：取不到时是 undefined，不会抛错，只会「点了没反应」。
 */
export interface ChangeEvidence {
  char_start?: number
  char_end?: number
  text?: string
  band?: string | null
  status?: string | null
  chunk_ids?: string[]
}

/** `change_list[]` 的一条修改建议，每条都指回一个上游记录。 */
export interface ChangeListItem {
  section: string
  kind: string
  upstream_id: string
  target?: string
  evidence: ChangeEvidence[]
  action: string
  /** 审查类条目才有：finding 的原始类型。 */
  finding_kind?: string
  /** 维度类条目才有：指向量规的 dimension_code。 */
  dimension_code?: string
}

/** 被排除在加权之外的维度，连同原因。 */
export interface ScoreEntry {
  dimension_code: string
  band: string | null
  status: string | null
  weight: number
  contribution: number
  reason: string
}

/** `resume` 响应的 `score`。本版未接模型，四个数都是 0。 */
export interface ReviewScore {
  total: number
  weighted: number
  excluded: ScoreEntry[]
  weight_sum: number
}

/** `POST /api/reviews/{id}/resume` 的响应：一条完整报告。 */
export interface ReviewReport {
  review_id: string
  status: string
  contest_id: string
  rubric_id: string | null
  rubric_version: number | null
  model_name: string
  source: string
  dimensions: DimensionResult[]
  score: ReviewScore
  change_list: ChangeListItem[]
  note: string
}

/**
 * `GET /api/reviews/{id}` 的存档：只回 7 个字段，**没有** `status` / `source` / `score` /
 * `change_list` / `note`。它和 `resume` 的完整报告不是一回事，页面取加权前必须判别。
 */
export interface ArchivedReview {
  review_id: string
  contest_id: string
  rubric_id: string | null
  rubric_version: number | null
  model_name: string
  created_at: string | null
  dimensions: DimensionResult[]
  change_list: ChangeListItem[]
  change_list_note: string | null
}

/** `GET /api/reviews/{id}` 的两段式：已落档返回存档，只有会话快照时返回章节树。 */
export type ReviewArchive = ArchivedReview | ReviewPending

/** `POST /api/reviews` 的请求体：`paper_text` 与 `sample_id` 只能给一个。 */
export interface CreateReviewPayload {
  paper_text?: string
  sample_id?: string
  contest_id?: string
}

/** `POST /api/imports` 的响应。 */
export interface ImportSummary {
  contest_id: string
  rubric_id: string
  version: number
  dimensions: number
  constraints: number
  pitfalls: number
  exemplars: number
}

/** `POST /api/contests/{id}/publish` 的响应。 */
export interface ContestPublishResult {
  contest_id: string
  status: string
  rubric_id: string | null
  rubric_version: number | null
}

/** `POST /api/contests/{id}/archive` 的响应。 */
export interface ContestArchiveResult {
  contest_id: string
  status: string
}

/** `POST /api/contests/{id}/rubrics` 的响应：复制出 version + 1 的 draft。 */
export interface RubricCopyResult {
  contest_id: string
  rubric_id: string
  version: number
  status: string
}

/** `POST /api/rubrics/{id}/publish` 的响应。 */
export interface RubricPublishResult {
  contest_id: string
  rubric_id: string
  version: number
  status: string
  archived_rubric_ids: string[]
}
