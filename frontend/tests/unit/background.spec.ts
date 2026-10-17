// Phase 2 背景系统的回归契约：背景只是氛围，关掉也不影响可用性。
// 网格已退役，背景 = 纸纹 + 页缘线稿 + 构图角标 + 每页独立 PageArt 双图。

import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '..', '..', 'src')
const SKETCH_CSS = readFileSync(path.join(SRC, 'styles', 'sketch.css'), 'utf8')
const TOKENS = readFileSync(path.join(SRC, 'styles', 'tokens.css'), 'utf8')

function assetNames(): string[] {
  return readdirSync(path.join(SRC, 'assets', 'sketch'))
}

const PAGE_BG = [
  'sketch-bg-parse.svg',
  'sketch-bg-scoring.svg',
  'sketch-bg-consistency.svg',
  'sketch-bg-suggestions.svg',
  'sketch-bg-eval.svg',
  'sketch-spot-parse.svg',
  'sketch-spot-scoring.svg',
  'sketch-spot-consistency.svg',
  'sketch-spot-suggestions.svg',
  'sketch-spot-eval.svg',
]

describe('全局背景系统', () => {
  it('1. 资源都在：纸纹 + 页缘线稿 + 构图角标 + 每页双图 + 全局照片', () => {
    const assets = assetNames()
    expect(assets).toContain('sketch-paper-grain.svg')
    expect(assets).toContain('sketch-margin-draft.svg')
    expect(assets).toContain('sketch-corner-mark.svg')
    expect(assets).toContain('photo-background.jpg')
    for (const file of PAGE_BG) {
      expect(assets, file).toContain(file)
    }
  })

  it('2. 背景各层全部 pointer-events 穿透，不拦截交互', () => {
    // 背景段从「5. 全局背景系统」注释开始：.shell 两伪元素共用一条规则，
    // 穿透声明覆盖 4 个选择器（body::after 已退役为空占位，不在其中）。
    const backgroundSection = SKETCH_CSS.slice(SKETCH_CSS.indexOf('5. 全局背景系统'))
    for (const rule of backgroundSection.split('}')) {
      // 只断言主规则（带 content 或背景图）：后位的 left/right 微调规则不重复声明穿透。
      if (/(\.shell::|\.shell__body::)/.test(rule) && /content|background-image/.test(rule)) {
        expect(rule, rule.slice(0, 60)).toContain('pointer-events: none')
      }
    }
    expect(backgroundSection).toContain('position: fixed')
    for (const selector of [
      '.shell::before',
      '.shell::after',
      '.shell__body::before',
      '.shell__body::after',
    ]) {
      expect(backgroundSection, selector).toContain(selector)
    }
    // PageArt 组件自身穿透
    const pageArt = readFileSync(path.join(SRC, 'components', 'PageArt.vue'), 'utf8')
    expect(pageArt).toContain('pointer-events: none')
    expect(pageArt).toContain('aria-hidden')
  })

  it('3. 背景层无裸色值：线稿颜色走主题变量，透明度走背景令牌', () => {
    expect(SKETCH_CSS.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([])
    expect(SKETCH_CSS).toContain('var(--pr-ink)')
    for (const token of ['--pr-bg-draft-opacity', '--pr-bg-corner-opacity']) {
      expect(TOKENS, token).toContain(token)
    }
  })

  it('4. 窄屏隐藏页缘与角标：不挤内容、不产横向滚动', () => {
    expect(SKETCH_CSS).toContain('@media (max-width: 1100px)')
    expect(SKETCH_CSS).toContain('.shell__body::after')
  })

  it('5. 线稿 SVG 遵循手绘约定：currentColor、无填充、无裸色值', () => {
    for (const file of [
      'sketch-margin-draft.svg',
      'sketch-corner-mark.svg',
      ...PAGE_BG,
    ]) {
      const text = readFileSync(path.join(SRC, 'assets', 'sketch', file), 'utf8')
      expect(text, `${file} 未用 currentColor`).toContain('stroke="currentColor"')
      expect(text, `${file} 缺 fill=none`).toContain('fill="none"')
      expect(text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], `${file} 出现裸色值`).toEqual([])
    }
  })
})
