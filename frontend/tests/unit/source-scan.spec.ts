import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { AWARD_WORDS, CONTEST_ID_TOKEN, WORDLIST_FILES } from './forbidden-words'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = path.resolve(HERE, '..', '..')
const SRC = path.join(FRONTEND_ROOT, 'src')
const TESTS = path.join(FRONTEND_ROOT, 'tests')
const TOKENS_FILE = path.join(SRC, 'styles', 'tokens.css')

// 奖项字样与题号字面量：词表在 ./forbidden-words.ts 里（唯一一处定义）。
// 扫描时跳过词表本身与写词表的这个文件——词表没法扫描自己。
const FORBIDDEN = [...AWARD_WORDS, CONTEST_ID_TOKEN]

const SOURCE_SUFFIXES = ['.ts', '.vue', '.css', '.html', '.js']

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    return entry.isDirectory() ? walk(full) : [full]
  })
}

function sourceFiles(): string[] {
  return [...walk(SRC), ...walk(TESTS)].filter((file) =>
    SOURCE_SUFFIXES.some((suffix) => file.endsWith(suffix)),
  )
}

function hexToken(source: string, name: string): { text: string; r: number; g: number; b: number } {
  const match = source.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!match?.[1]) {
    throw new Error(`tokens.css 里没有六位十六进制的 ${name}`)
  }
  const text = match[1]
  return {
    text,
    r: Number.parseInt(text.slice(1, 3), 16),
    g: Number.parseInt(text.slice(3, 5), 16),
    b: Number.parseInt(text.slice(5, 7), 16),
  }
}

describe('源码扫描', () => {
  it('src 与 tests 下没有奖项字样，也没有题号字面量', () => {
    const files = sourceFiles().filter((file) => !WORDLIST_FILES.has(path.basename(file)))
    expect(files.length).toBeGreaterThan(10)

    for (const file of files) {
      const text = readFileSync(file, 'utf8')
      for (const word of FORBIDDEN) {
        expect(text.includes(word), `${file} 出现了 ${word}`).toBe(false)
      }
    }
  })

  it('.vue 与 .css 里没有裸的十六进制颜色，颜色一律走 tokens.css 的变量', () => {
    const files = walk(SRC).filter(
      (file) => /\.(vue|css)$/.test(file) && path.basename(file) !== 'tokens.css',
    )
    expect(files.length).toBeGreaterThanOrEqual(6)

    for (const file of files) {
      const text = readFileSync(file, 'utf8')
      expect(text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], `${file} 出现裸色值`).toEqual([])
    }
  })

  it('tokens.css 覆盖 Element Plus 主题，底色偏冷、墨色不是纯黑', () => {
    const tokens = readFileSync(TOKENS_FILE, 'utf8')

    expect(tokens).toContain('--el-color-primary:')
    expect(tokens).toContain('--el-border-radius-base:')
    expect(tokens).toContain('--el-font-family:')

    const paper = hexToken(tokens, '--pr-paper')
    expect(paper.b, `底色 ${paper.text} 偏暖，应当偏冷或中性`).toBeGreaterThanOrEqual(paper.r)

    const ink = hexToken(tokens, '--pr-ink')
    expect(ink.text.toLowerCase()).not.toBe('#000000')
    expect(Math.max(ink.r, ink.g, ink.b)).toBeLessThan(140)
  })

  it('动态反馈只绑定真实状态，动效集中且尊重 reduced-motion', () => {
    // 登录开场、真实请求活动提示、数据图表和列表状态各有明确触发源；不允许泛化到每张卡片。
    const vueFiles = walk(SRC).filter(
      (file) => file.endsWith('.vue') && path.basename(file) !== 'PostLoginIntro.vue',
    )
    expect(vueFiles.length).toBeGreaterThanOrEqual(6)

    for (const file of vueFiles) {
      const text = readFileSync(file, 'utf8')
      expect(/[^{}]*:hover[^{}]*\{[^}]*transform\s*:/s.test(text), `${file} 出现 hover 位移`).toBe(false)
    }

    const tokens = readFileSync(TOKENS_FILE, 'utf8')
    expect(tokens).toContain('--pr-motion-confirm')
    expect(tokens).toContain('--pr-motion-page')
    expect(tokens).toContain('--pr-motion-list')

    for (const relative of ['components/RequestActivity.vue', 'components/MetricCard.vue', 'views/数据大屏.vue']) {
      const text = readFileSync(path.join(SRC, relative), 'utf8')
      expect(/animation\s*:/.test(text), `${relative} 应有受控动态反馈`).toBe(true)
      expect(text).toContain('prefers-reduced-motion')
    }

    const intro = readFileSync(path.join(SRC, 'components', 'PostLoginIntro.vue'), 'utf8')
    const svg = readFileSync(path.resolve(FRONTEND_ROOT, '..', 'docs', 'design', 'sketch-svg', 'sketch-review-desk-intro.svg'), 'utf8')
    expect(intro).toContain('prefers-reduced-motion: reduce')
    expect(svg).toContain('prefers-reduced-motion: reduce')
    expect(svg).toContain('animation: settle')
  })
})
