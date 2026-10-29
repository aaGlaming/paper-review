/**
 * 评审单的三种形状判别。
 *
 * `GET /api/reviews/{id}` 返回的是两段式联合（存档或未确认快照），`resume` 返回的是完整报告，
 * 两者字段不同。页面在取 `score` / `source` / `change_list` 之前必须先判别——照旧类型写，
 * 会在存档上静默取到 `undefined`，加权区显示空白且不报错。
 */

import type { ArchivedReview, ReviewPending, ReviewReport } from '../api/types'

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object'
}

/** 完整报告：来自 `resume`，带 `score`、`source`、`change_list`。 */
export function isReviewReport(value: unknown): value is ReviewReport {
  return (
    isObject(value) &&
    'score' in value &&
    'source' in value &&
    'change_list' in value &&
    'dimensions' in value
  )
}

/** 存档：来自 `GET /api/reviews/{id}`，带 `created_at`、`dimensions`，但没有 `score`。 */
export function isArchivedReview(value: unknown): value is ArchivedReview {
  return (
    isObject(value) &&
    'created_at' in value &&
    'dimensions' in value &&
    !('score' in value) &&
    !('confirmed' in value)
  )
}

/** 未确认快照：只有章节树与 `confirmed`，没有维度。 */
export function isReviewPending(value: unknown): value is ReviewPending {
  return isObject(value) && 'confirmed' in value && 'sections' in value && !('dimensions' in value)
}
