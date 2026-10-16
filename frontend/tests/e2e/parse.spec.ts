// 论文解析页的冒烟：走 5173 吃 Vite 代理，后端与真库都在。
// 两条用例都会真写库（创建评审 + 确认），接口里没有删除路径，这是已知且已记档的污染。

import { expect, test } from '@playwright/test'

const FLOW_STORAGE_KEY = 'paper-review:review-flow'

test('完整链路：选赛题 → 点第一篇演示 → 章节树 → 确认 → 已确认结果卡', async ({ page }) => {
  await page.goto('/parse')

  // 演示按钮的文案与条数来自 listSamples(true)，源码里没有写死标题
  await expect(page.getByTestId('demo-item')).toHaveCount(3)
  await expect(page.getByTestId('submit-sample')).toBeDisabled()

  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.getByTestId('demo-item').first().click()
  await page.getByTestId('submit-sample').click()

  // 章节树出来了，条数 ≥ 5
  await expect(page.getByTestId('section-item').first()).toBeVisible()
  const sectionCount = await page.getByTestId('section-item').count()
  expect(sectionCount).toBeGreaterThanOrEqual(5)

  // 未确认：页面上没有任何档位字样
  await expect(page.getByTestId('parse-page')).not.toContainText('证据不足')
  await expect(page.getByTestId('confirmed-card')).toHaveCount(0)

  await page.getByTestId('confirm-sections').click()

  const card = page.getByTestId('confirmed-card')
  await expect(card).toBeVisible()
  await expect(page.getByTestId('confirmed-dimension-count')).toHaveText('5')
  await expect(card).toContainText('完成')
  await expect(page.getByTestId('stage-badge')).toHaveText('已完成')

  // 刷新页面：共享状态不丢，结果卡与章节树都还在
  await page.reload()
  await expect(page.getByTestId('confirmed-card')).toBeVisible()
  await expect(page.getByTestId('confirmed-dimension-count')).toHaveText('5')
  await expect(page.getByTestId('section-item')).toHaveCount(sectionCount)

  // 共享状态确实写进了 sessionStorage
  const stored = await page.evaluate((key) => sessionStorage.getItem(key), FLOW_STORAGE_KEY)
  const flow = JSON.parse(stored ?? '{}') as { reviewId?: string; report?: { dimensions?: unknown[] } }
  expect(flow.reviewId).toBeTruthy()
  expect(flow.report?.dimensions).toHaveLength(5)

  console.log(
    `[e2e] 完整链路创建的评审 review_id=${flow.reviewId} 章节树条数=${sectionCount} 确认后维度数=5`,
  )
})

test('粘贴正文这条：内联一小段 Markdown → 创建 → 确认', async ({ page }) => {
  // 用例内联的稿子，不从 data/ 下读文件：E2E 只经 HTTP
  const paperText = [
    '# 摘要',
    '',
    '本文给出一段用于验证解析页的最小稿子。',
    '',
    '## 一、模型假设',
    '',
    '把手简化为孔中心点。',
  ].join('\n')

  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.getByTestId('paper-text').fill(paperText)
  await page.getByTestId('submit-text').click()

  // 两个标题 → 两条章节
  await expect(page.getByTestId('section-item')).toHaveCount(2)

  await page.getByTestId('confirm-sections').click()
  const card = page.getByTestId('confirmed-card')
  await expect(card).toBeVisible()
  await expect(card).toContainText('完成')

  const dimensionCount = await page.getByTestId('confirmed-dimension-count').textContent()
  expect(Number(dimensionCount)).toBeGreaterThan(0)

  console.log(`[e2e] 粘贴正文创建的评审确认后维度数=${dimensionCount}`)
})
