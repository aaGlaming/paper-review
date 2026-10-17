// 视觉重设计（阶段 7/7）的回归契约：本版只改外观，不碰语义与测试钩子。
// 这两条守住「87 个 data-testid 一个不少」与「不用 emoji 当图标」。
// 87 = P8 收尾时的 86 + 昼夜主题切换按钮（theme-toggle）1 个新增功能钩子。

import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '..', '..', 'src')

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    return entry.isDirectory() ? walk(full) : [full]
  })
}

function sourceFiles(): string[] {
  return walk(SRC).filter((file) => /\.(vue|ts|css)$/.test(file))
}

describe('视觉契约', () => {
  it('87 个 data-testid 一个不少（新增只有 theme-toggle 一个功能钩子）', () => {
    const ids = new Set<string>()
    for (const file of sourceFiles().filter((f) => f.endsWith('.vue'))) {
      const text = readFileSync(file, 'utf8')
      for (const match of text.matchAll(/data-testid="([^"]+)"/g)) {
        ids.add(match[1])
      }
    }
    expect(ids.size).toBe(87)
    expect(ids.has('theme-toggle')).toBe(true)
  })

  it('src 下不用 emoji 当图标（手绘图形一律用 sketch SVG，不用 emoji）', () => {
    // 常见 emoji 区段：表情/图形符号（含变体选择器）；不含箭头与破折号这类非 emoji 字符。
    const emoji = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/u
    for (const file of sourceFiles().filter((f) => /\.(vue|ts)$/.test(f))) {
      const text = readFileSync(file, 'utf8')
      expect(emoji.test(text), `${file} 出现 emoji`).toBe(false)
    }
  })
})
