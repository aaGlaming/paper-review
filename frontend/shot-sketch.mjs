import { chromium } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// 设计资产样张截图工具：把 docs/design/sketch-preview.html 截成 PNG。
// 用法：在 frontend/ 下执行 `node shot-sketch.mjs`（依赖本目录的 node_modules）。
const HERE = path.dirname(fileURLToPath(import.meta.url))
const DESIGN = path.resolve(HERE, '..', 'docs', 'design')

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1200, height: 1600 }, deviceScaleFactor: 2 })
await page.goto('file:///' + path.join(DESIGN, 'sketch-preview.html').replace(/\\/g, '/'))
await page.waitForTimeout(600)
await page.screenshot({ path: path.join(DESIGN, 'sketch-preview.png'), fullPage: true })
await browser.close()
console.log('saved ->', path.join(DESIGN, 'sketch-preview.png'))
