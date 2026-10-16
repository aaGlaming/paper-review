/**
 * 已冻结接口的封装：十一条 REST 路径各一个函数。
 *
 * 两条纪律写在这里，页面不再各写一遍：
 * - **URL 一律相对路径**（`/api/...`），不拼 host。后端没有 CORS 中间件，直连 8077 会被浏览器挡掉；
 *   相对路径交给 Vite 开发服务器代理。写死 host 会让单页能跑、部署全崩。
 * - 非 2xx 一律抛 `ApiError`，消息里带上响应体的 `detail`（坏包还带 `filename` 与 `field`，
 *   参数校验失败时 `detail` 是数组）。页面用消息显示错误，用字段名指出改哪个文件的哪个字段。
 */

import type {
  ContestArchiveResult,
  ContestListResponse,
  ContestPublishResult,
  CreateReviewPayload,
  EvalSummary,
  ImportSummary,
  PaperSection,
  ReviewArchive,
  ReviewCreated,
  ReviewReport,
  RubricCopyResult,
  RubricPublishResult,
  SampleListResponse,
} from './types'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  readonly filename?: string
  readonly field?: string

  constructor(
    status: number,
    message: string,
    options: { detail?: unknown; filename?: string; field?: string } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = options.detail
    this.filename = options.filename
    this.field = options.field
  }
}

function optionalText(source: Record<string, unknown>, key: string): string | undefined {
  const value = source[key]
  return typeof value === 'string' && value.trim() ? value : undefined
}

function describeFailure(
  status: number,
  body: unknown,
): { message: string; detail: unknown; filename?: string; field?: string } {
  if (body && typeof body === 'object' && !Array.isArray(body)) {
    const record = body as Record<string, unknown>
    const detail = record.detail
    if (typeof detail === 'string' && detail.trim()) {
      return {
        message: detail,
        detail,
        filename: optionalText(record, 'filename'),
        field: optionalText(record, 'field'),
      }
    }
    if (Array.isArray(detail)) {
      return { message: `参数校验失败（HTTP ${status}）：${JSON.stringify(detail)}`, detail }
    }
  }
  if (typeof body === 'string' && body.trim()) {
    return { message: `请求失败（HTTP ${status}）：${body}`, detail: body }
  }
  return { message: `请求失败（HTTP ${status}）`, detail: body }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!response.ok) {
    const failure = describeFailure(response.status, body)
    throw new ApiError(response.status, failure.message, failure)
  }
  return body as T
}

function asQuery(query: URLSearchParams): string {
  const text = query.toString()
  return text ? `?${text}` : ''
}

/** 赛题列表。默认只返回已发布；草稿与归档要显式要求。 */
export function listContests(
  includeArchived = false,
  includeDrafts = false,
): Promise<ContestListResponse> {
  const query = new URLSearchParams()
  if (includeArchived) {
    query.set('include_archived', 'true')
  }
  if (includeDrafts) {
    query.set('include_drafts', 'true')
  }
  return request<ContestListResponse>(`/api/contests${asQuery(query)}`)
}

/** 创建评审：解析章节树后停在确认节点，响应里没有档位字段。 */
export function createReview(payload: CreateReviewPayload): Promise<ReviewCreated> {
  return request<ReviewCreated>('/api/reviews', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 确认章节树后继续到终态，返回完整报告。 */
export function resumeReview(reviewId: string, sections: PaperSection[]): Promise<ReviewReport> {
  return request<ReviewReport>(`/api/reviews/${encodeURIComponent(reviewId)}/resume`, {
    method: 'POST',
    body: JSON.stringify({ sections }),
  })
}

/** 读取一条评审：已落档返回报告，只有会话快照时返回章节树。 */
export function getReview(reviewId: string): Promise<ReviewArchive> {
  return request<ReviewArchive>(`/api/reviews/${encodeURIComponent(reviewId)}`)
}

/** 样例列表。`isDemo` 给布尔值时才带查询参数。 */
export function listSamples(isDemo?: boolean): Promise<SampleListResponse> {
  const query = new URLSearchParams()
  if (typeof isDemo === 'boolean') {
    query.set('is_demo', isDemo ? 'true' : 'false')
  }
  return request<SampleListResponse>(`/api/samples${asQuery(query)}`)
}

/** 三项评测指标。 */
export function getEvalSummary(): Promise<EvalSummary> {
  return request<EvalSummary>('/api/eval/summary')
}

/** 导入赛题数据包。相对路径按项目根目录解析。 */
export function importPackage(packageDir: string): Promise<ImportSummary> {
  return request<ImportSummary>('/api/imports', {
    method: 'POST',
    body: JSON.stringify({ package_dir: packageDir }),
  })
}

/** 发布赛题，并把它当前那一版量规设为可预审。 */
export function publishContest(contestId: string): Promise<ContestPublishResult> {
  return request<ContestPublishResult>(
    `/api/contests/${encodeURIComponent(contestId)}/publish`,
    { method: 'POST' },
  )
}

/** 归档赛题，默认列表里不再出现。 */
export function archiveContest(contestId: string): Promise<ContestArchiveResult> {
  return request<ContestArchiveResult>(
    `/api/contests/${encodeURIComponent(contestId)}/archive`,
    { method: 'POST' },
  )
}

/** 从当前已发布量规复制出 version + 1 的草稿。 */
export function copyRubricAsDraft(contestId: string): Promise<RubricCopyResult> {
  return request<RubricCopyResult>(`/api/contests/${encodeURIComponent(contestId)}/rubrics`, {
    method: 'POST',
  })
}

/** 发布某一版量规，同一赛题同时只留一条已发布。 */
export function publishRubric(rubricId: string): Promise<RubricPublishResult> {
  return request<RubricPublishResult>(`/api/rubrics/${encodeURIComponent(rubricId)}/publish`, {
    method: 'POST',
  })
}
