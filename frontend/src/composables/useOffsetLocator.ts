/**
 * 共享的原文偏移定位工具。
 * 产物优先按 `section.char_start` 折算到单个 section 的 paper_text 原文片段；
 * 只有缺少 section 区间时，旧的 change evidence 才沿用正文 `indexOf` 校准与偏移降级。
 */

import type { ChangeEvidence, PaperSection, ReviewArtifact } from '../api/types'

/** 一次定位的结果：命中位置与是否精确。 */
export interface EvidenceLocation {
  /** 拼接正文里的起始下标。 */
  start: number
  /** 高亮区实际展示的文本（精确匹配时就是 evidence.text，降级时是正文切片）。 */
  text: string
  /** 是否精确匹配到 evidence.text。 */
  exact: boolean
  /** 降级原因，只有非精确匹配才有。 */
  approximateNote?: string
}

/** 把各段 content 按顺序拼接（段间一个换行），复现后端切分前的全文偏移。 */
export function concatSections(sections: PaperSection[]): string {
  return sections.map((section) => section.content ?? '').join('\n')
}

/** 一条 evidence 是否带字符偏移、可点击定位。 */
export function isLocatable(evidence: ChangeEvidence): boolean {
  return typeof evidence.char_start === 'number' && typeof evidence.char_end === 'number'
}

function clampStart(value: unknown, length: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 0
  }
  return Math.max(0, Math.min(Math.floor(value), length))
}

function clampEnd(value: number, length: number): number {
  return Math.max(0, Math.min(Math.floor(value), length))
}

/**
 * 在拼接正文里定位一条 evidence：
 * - 先 `indexOf(evidence.text)` 精确校准；
 * - 找不到就落到 `char_start` 的大致位置，并标注「按偏移定位，未精确匹配」。
 * 没有可定位的 text 时返回 null（页面据此不渲染定位结果）。
 */
export function locateEvidence(body: string, evidence: ChangeEvidence): EvidenceLocation | null {
  const text = evidence.text ?? ''
  if (!text) {
    return null
  }
  const exactIndex = body.indexOf(text)
  if (exactIndex !== -1) {
    return { start: exactIndex, text, exact: true }
  }
  const fallbackStart = clampStart(evidence.char_start, body.length)
  const end = clampEnd(fallbackStart + text.length, body.length)
  return {
    start: fallbackStart,
    text: body.slice(fallbackStart, end),
    exact: false,
    approximateNote: '按偏移定位，未精确匹配',
  }
}

/** Locate an artifact inside one raw section slice using its paper_text base offset. */
export function locateSectionArtifact(
  section: PaperSection,
  sourceSlice: string,
  artifact: ReviewArtifact,
): EvidenceLocation | null {
  const text = artifact.claim_text ?? artifact.table_markdown ?? artifact.citation_text ?? ''
  if (!text) return null

  if (typeof section.char_start === 'number' && typeof section.char_end === 'number') {
    const local = artifact.char_start - section.char_start
    const start = clampStart(local, sourceSlice.length)
    const end = clampEnd(start + text.length, sourceSlice.length)
    const actual = sourceSlice.slice(start, end)
    const exact = local >= 0 && actual === text
    return {
      start,
      text: actual,
      exact,
      ...(exact ? {} : { approximateNote: '按偏移定位，未精确匹配' }),
    }
  }

  return locateEvidence(section.content ?? '', {
    text,
    char_start: artifact.char_start,
    char_end: artifact.char_end,
  })
}
