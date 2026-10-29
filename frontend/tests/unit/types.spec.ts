import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const TYPES_FILE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  'src',
  'api',
  'types.ts',
)

const SOURCE = readFileSync(TYPES_FILE, 'utf8')

function interfaceBody(name: string): string {
  const match = SOURCE.match(new RegExp(`export interface ${name} \\{([\\s\\S]*?)\\n\\}`))
  if (!match?.[1]) {
    throw new Error(`types.ts 里没有 export interface ${name}`)
  }
  return match[1]
}

describe('接口响应类型的形状守卫', () => {
  it('ChangeEvidence 同时声明了字符偏移组与档位组，两组都是可选的', () => {
    const body = interfaceBody('ChangeEvidence')

    // 审查类条目带偏移，维度类条目带档位；两组都在同一个类型上，页面判形状后再取字段
    for (const field of ['char_start', 'char_end', 'text', 'band', 'status', 'chunk_ids']) {
      expect(body, `ChangeEvidence 缺 ${field}`).toContain(field)
    }
    expect(body.match(/\?:/g) ?? []).toHaveLength(6)
  })

  it('ReviewReport 覆盖 resume 响应的全部字段', () => {
    const body = interfaceBody('ReviewReport')

    for (const field of [
      'review_id',
      'status',
      'contest_id',
      'rubric_id',
      'rubric_version',
      'model_name',
      'source',
      'dimensions',
      'score',
      'change_list',
      'note',
    ]) {
      expect(body, `ReviewReport 缺 ${field}`).toContain(field)
    }
  })

  it('DimensionResult 覆盖 dimensions[] 的字段，ChangeListItem 覆盖两种条目', () => {
    const dimension = interfaceBody('DimensionResult')
    for (const field of ['dimension_code', 'band', 'chunk_ids', 'quote', 'status']) {
      expect(dimension, `DimensionResult 缺 ${field}`).toContain(field)
    }

    const item = interfaceBody('ChangeListItem')
    for (const field of ['section', 'kind', 'upstream_id', 'target', 'evidence', 'action']) {
      expect(item, `ChangeListItem 缺 ${field}`).toContain(field)
    }
    // 审查类才有 finding_kind / target，维度类才有 dimension_code
    expect(item).toContain('finding_kind?')
    expect(item).toContain('dimension_code?')
  })
})
