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

export interface AuthUser {
  user_id: string
  username: string
  role: 'student' | 'teacher' | string
  permissions: string[]
  email?: string
  display_name?: string
}

export interface ChatSessionItem {
  session_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}
export interface ChatSessionListResponse { sessions: ChatSessionItem[] }
export interface ChatRef { review_id: string; dimension_code: string }
export interface ChatMessageItem {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  refs: ChatRef[] | null
  model_name: string | null
  seq: number
  created_at: string
}
export interface ChatMessageListResponse { session_id: string; messages: ChatMessageItem[] }
export interface ChatAnswerResponse {
  message_id: string
  content: string
  refs: ChatRef[]
  model_name: string
  notifications: { rejected: number; unused: number }
}
export type AnalyticsKind = 'bands' | 'conflicts' | 'gaps'
export interface BandsResult {
  contest_id: string; reviews: number; students: number; orphan_reviews: number
  bands: Array<{ dimension_code: string; counts: Record<string, number>; insufficient: number; reviews: number }>
  insufficient_total: number
}
export interface ConflictsResult {
  contest_id: string; reviews_with_changes: number; kinds: Record<string, number>
  hotspots: Array<{ target: string; count: number; review_ids: string[] }>
  finding_total: number; unparsable: number
}
export interface GapsResult {
  contest_id: string; dimension_code: string | null
  gaps: Array<{ review_id: string; dimension_code: string; band: string; has_quote: boolean }>
  count: number
}
export type AnalyticsResult = BandsResult | ConflictsResult | GapsResult
export interface AnalyticsResponse { kind: AnalyticsKind; result: AnalyticsResult }
export interface SummaryResponse {
  content: string; refs: ChatRef[]; model_name: string
  notes: { rejected: number; evidence_short?: number }
}

export interface DashboardSummary {
  cached: boolean
  cards: {
    total_submissions: number
    weekly_new: number
    parse_only: number
    pending_conflicts: number
    gold_agreement: { agreement: number; matched: number; total: number; source: string } | null
  }
  contests: Array<{ contest_id: string; review_count: number }>
  bands: Array<{
    dimension_code: string
    counts: Record<'充分' | '基本' | '不足' | '证据不足', number>
    insufficient_total: number
  }>
  insufficient_top: Array<{ dimension_code: string; counts: Record<string, number>; insufficient_total: number }>
  conflicts: Array<{ kind: string; count: number }>
  hotspots: Array<{ target: string; count: number }>
  citation: { failure_count: number; total_dimensions: number; citation_rate: number }
  gold: { agreement: number; matched: number; total: number; source: string } | null
}

export interface DashboardTrend {
  cached: boolean
  days: number
  series: Array<{ date: string; total: number; ownerless: number }>
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

export interface ReviewListItem {
  review_id: string
  contest_id: string
  rubric_id: string
  rubric_version: number
  model_name: string
  created_at: string
  user_id: string | null
  owner_username: string | null
  bands: Record<string, string | null>
  finding_total: number
}

export interface ReviewListResponse {
  reviews: ReviewListItem[]
  total: number
  page: number
  page_size: number
  scope: 'all' | 'own'
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
    low_sample: boolean
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
  char_start?: number
  char_end?: number
}

export interface ReviewArtifact {
  artifact_id: number
  review_id: string
  ordinal: number
  artifact_type: 'claim' | 'table' | 'citation'
  section_type: string | null
  char_start: number
  char_end: number
  claim_text: string | null
  table_markdown: string | null
  citation_text: string | null
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
  sections_ranged?: boolean
  paper_text?: string
  user_id?: string | null
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
  agent_terminated_by?: string | null
}

export interface AgentStep {
  idx: number
  node: string
  action: string
  args_digest: string
  result_note: string
  ok: boolean
  error_code: string | null
  elapsed_ms: number
  created_at: string
}

export interface AgentStepsResponse {
  review_id: string
  steps: AgentStep[]
}

/**
 * `GET /api/reviews/{id}` 的存档：包含档案字段与 change_list，sections 仅在有正文快照时返回。
 * 它和 `resume` 的完整报告不是一回事，页面取加权前必须判别。
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
  sections?: PaperSection[]
  sections_ranged?: boolean
  paper_text?: string
  user_id?: string | null
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
