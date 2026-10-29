// 手稿风修复的冒烟：圈中心偏差（真布局断言，jsdom 量不到）、三张卡折线互不相同。
// 走 5173 吃代理；第一条会真写库（创建 + 确认），接口没有删除路径——已知污染。

import { expect, test } from '@playwright/test'
import { waitForConfirmed } from './timeouts'

test('完整链路 → /scoring：圈中心与"基本"档位文本中心偏差 ≤ 4px', async ({ page }) => {
  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.getByTestId('demo-item').first().click()
  await page.getByTestId('submit-sample').click()
  await expect(page.getByTestId('confirm-sections')).toBeVisible({ timeout: 20_000 })
  await page.getByTestId('confirm-sections').click()
  await waitForConfirmed(page)

  await page.goto('/scoring')
  await expect(page.getByTestId('dimension-card')).toHaveCount(5)

  const card = page.locator('[data-testid="dimension-card"]').first()
  const band = card.locator('[data-testid="band"]')
  await expect(band).toHaveText('基本')
  const circle = card.locator('.card__band-circle')

  const bandBox = await band.boundingBox()
  const circleBox = await circle.boundingBox()
  expect(bandBox, '档位文本无 boundingBox').not.toBeNull()
  expect(circleBox, '圈无 boundingBox').not.toBeNull()
  if (bandBox && circleBox) {
    const dx = Math.abs(bandBox.x + bandBox.width / 2 - (circleBox.x + circleBox.width / 2))
    const dy = Math.abs(bandBox.y + bandBox.height / 2 - (circleBox.y + circleBox.height / 2))
    const deviation = Math.hypot(dx, dy)
    console.log(`[sketch-fix] scoring 圈中心偏差 dx=${dx.toFixed(2)} dy=${dy.toFixed(2)} ≈${deviation.toFixed(2)}px`)
    expect(deviation).toBeLessThanOrEqual(4)
  }
})

test('/consistency：冲突数值的圈中心偏差 ≤ 4px', async ({ page }) => {
  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.getByTestId('demo-item').first().click()
  await page.getByTestId('submit-sample').click()
  await expect(page.getByTestId('confirm-sections')).toBeVisible({ timeout: 20_000 })
  await page.getByTestId('confirm-sections').click()
  await waitForConfirmed(page)

  await page.goto('/consistency')
  await expect(page.getByTestId('conflict-item').first()).toBeVisible()

  const hit = page.getByTestId('evidence-hit').first()
  const label = hit.locator('.conflict__hit-label')
  const circle = hit.locator('.conflict__hit-circle')
  const hitBox = await label.boundingBox()
  const circleBox = await circle.boundingBox()
  expect(hitBox).not.toBeNull()
  expect(circleBox).not.toBeNull()
  if (hitBox && circleBox) {
    const dx = Math.abs(hitBox.x + hitBox.width / 2 - (circleBox.x + circleBox.width / 2))
    const dy = Math.abs(hitBox.y + hitBox.height / 2 - (circleBox.y + circleBox.height / 2))
    const deviation = Math.hypot(dx, dy)
    console.log(`[sketch-fix] consistency 圈中心偏差 dx=${dx.toFixed(2)} dy=${dy.toFixed(2)} ≈${deviation.toFixed(2)}px`)
    expect(deviation).toBeLessThanOrEqual(4)
  }
})

test('/eval：三张指标卡的折线 path 互不相同', async ({ page }) => {
  await page.goto('/eval')
  await expect(page.getByTestId('metric-card')).toHaveCount(3)

  const response = await page.evaluate(async () => {
    const token = localStorage.getItem('pr.auth.token')
    const result = await fetch('/api/eval/summary', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    return { status: result.status, summary: await result.json() as Record<string, unknown> }
  })
  expect(response.status).toBe(200)

  const paths: Array<{ code: string; d: string }> = []
  for (const code of ['band_agreement', 'quote_exact_match', 'insufficient_evidence_hit']) {
    const metric = response.summary[code] as
      | { low_sample?: unknown; matched?: number; total?: number }
      | undefined
    expect(
      typeof metric?.low_sample,
      '后端进程未加载 low_sample 字段，请重启后再跑',
    ).toBe('boolean')
    if (!metric || typeof metric.low_sample !== 'boolean') {
      throw new Error('后端进程未加载 low_sample 字段，请重启后再跑')
    }

    const card = page.locator(`[data-metric="${code}"]`)
    const line = card.locator('.metric__chart-line')
    if (metric.low_sample) {
      await expect(line).toHaveCount(0)
      await expect(card.getByTestId('metric-rate')).toHaveText('样本过少')
      await expect(card.getByTestId('metric-low-sample-note')).toBeVisible()
      await expect(card.getByTestId('metric-fraction')).toHaveText(
        `${metric.matched} / ${metric.total}`,
      )
    } else {
      await expect(line).toHaveCount(1)
      paths.push({ code, d: (await line.getAttribute('d')) ?? '' })
    }
  }

  for (let left = 0; left < paths.length; left += 1) {
    for (let right = left + 1; right < paths.length; right += 1) {
      expect(paths[left].d, `${paths[left].code} 与 ${paths[right].code} 折线重合`).not.toBe(paths[right].d)
    }
  }
  console.log(`[sketch-fix] 正常样本折线 path：\n${paths.map(({ code, d }) => `  ${code} = ${d}`).join('\n')}`)
})
