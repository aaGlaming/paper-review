/**
 * 五页共用的评审流程状态：`{ contestId, reviewId, sections, report }`。
 *
 * 要跨页传的只有这四项，所以用 `sessionStorage` 就够，**不装 Pinia**：
 * 多一个依赖就多一份版本相容风险，而 Pinia 的收益（devtools、插件、模块化）这里用不上。
 *
 * 读写都走同一处：页面挂载时 `readReviewFlow()`，每次变化用下面的写入方法落盘，
 * 刷新页面不丢。坏数据（手工改坏、旧版本残留、存储不可用）一律退回空状态，不抛错。
 */

import type { PaperSection, ReviewReport } from '../api/types'

export const REVIEW_FLOW_STORAGE_KEY = 'paper-review:review-flow'

export interface ReviewFlowState {
  contestId: string
  reviewId: string
  sections: PaperSection[]
  report: ReviewReport | null
}

function emptyFlow(): ReviewFlowState {
  return { contestId: '', reviewId: '', sections: [], report: null }
}

function storage(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage
  } catch {
    return null
  }
}

/** 读取：没有存档或存档坏了都返回空状态。 */
export function readReviewFlow(): ReviewFlowState {
  const store = storage()
  const raw = store?.getItem(REVIEW_FLOW_STORAGE_KEY)
  if (!raw) {
    return emptyFlow()
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ReviewFlowState>
    return {
      contestId: typeof parsed.contestId === 'string' ? parsed.contestId : '',
      reviewId: typeof parsed.reviewId === 'string' ? parsed.reviewId : '',
      sections: Array.isArray(parsed.sections) ? parsed.sections : [],
      report: parsed.report ?? null,
    }
  } catch {
    return emptyFlow()
  }
}

/** 写入：只覆盖传进来的字段，返回合并后的完整状态。 */
export function writeReviewFlow(patch: Partial<ReviewFlowState>): ReviewFlowState {
  const next: ReviewFlowState = { ...readReviewFlow(), ...patch }
  storage()?.setItem(REVIEW_FLOW_STORAGE_KEY, JSON.stringify(next))
  return next
}

/** 创建评审成功后记录：赛题、评审单与**用户确认前**的章节树。 */
export function setReviewCreated(
  reviewId: string,
  contestId: string,
  sections: PaperSection[],
): ReviewFlowState {
  return writeReviewFlow({ reviewId, contestId, sections, report: null })
}

/** 确认章节树之后记录：报告与当时提交的章节树，供分项评分页等后续页面使用。 */
export function setConfirmedReport(
  report: ReviewReport,
  sections: PaperSection[],
): ReviewFlowState {
  return writeReviewFlow({ reviewId: report.review_id, sections, report })
}

/** 清空：整条流程从头再来时用。 */
export function resetReviewFlow(): void {
  storage()?.removeItem(REVIEW_FLOW_STORAGE_KEY)
}
