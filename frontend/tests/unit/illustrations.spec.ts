// Phase 3 插画系统的回归契约：统一线条语言、双主题、无障碍。
// 锁死：基座存在、五幅场景齐、颜色走变量、无裸色值、无拦截。

import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ILLO_DIR = path.resolve(HERE, '..', '..', 'src', 'components', 'illustrations')

const SCENES = [
  'ParseEmptyIllustration.vue',
  'ScoringEmptyIllustration.vue',
  'ConsistencyEmptyIllustration.vue',
  'SuggestionsEmptyIllustration.vue',
  'EvalSingleIllustration.vue',
]

describe('插画系统', () => {
  it('1. 基座 + 五幅场景都在', () => {
    const files = readdirSync(ILLO_DIR)
    expect(files).toContain('EmptyIllustration.vue')
    for (const scene of SCENES) {
      expect(files, scene).toContain(scene)
    }
  })

  it('2. 每幅都有 title（叙事性插画可被读屏）且包住基座', () => {
    for (const scene of SCENES) {
      const text = readFileSync(path.join(ILLO_DIR, scene), 'utf8')
      expect(text, `${scene} 缺 title`).toContain('<EmptyIllustration title="')
      expect(text, `${scene} 未复用基座`).toContain('EmptyIllustration')
    }
  })

  it('3. 线条走 currentColor、无裸色值、无 fill 实色', () => {
    for (const scene of SCENES) {
      const text = readFileSync(path.join(ILLO_DIR, scene), 'utf8')
      expect(text, `${scene} 未用 currentColor`).toContain('stroke="currentColor"')
      expect(text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], `${scene} 出现裸色值`).toEqual([])
      expect(text, `${scene} 出现实色填充`).not.toContain('fill="')
    }
  })

  it('4. 基座：装饰性默认隐藏，颜色走墨色变量', () => {
    const base = readFileSync(path.join(ILLO_DIR, 'EmptyIllustration.vue'), 'utf8')
    expect(base).toContain("aria-hidden=\"title ? undefined : 'true'\"")
    expect(base).toContain('<title v-if="title">')
    expect(base).toContain('var(--pr-ink-faint)')
    expect(base.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([])
  })
})
