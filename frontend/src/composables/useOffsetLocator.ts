/**
 * 一致性审查页的偏移定位器（P8 阶段 4/6）。
 *
 * 审查类条目的 `char_start / char_end` 是**论文全文**的偏移，而前端共享状态里只有 `sections[]`
 * （每个 `{title, section_type, level, content}`），没有整篇 `paper_text`。
 * 所以先把各段 `content` 按顺序拼接（段间一个换行 `\n`）复现全文，再用 `evidence.text` 做
 * `indexOf` 校准：能精确找到就用精确位置，找不到就落到 `char_start` 的大致位置并诚实标注
 * 「按偏移定位，未精确匹配」，绝不静默跳到错误处。
 *
 * 这是「全文偏移 vs 分段正文」的双源风险（见 findings.md 的 Ruling）。
 */

import type { ChangeEvidence, PaperSection } from '../api/types'

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
