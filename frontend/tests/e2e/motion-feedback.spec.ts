import { expect, test } from '@playwright/test'

test.use({ storageState: './tests/e2e/.auth/teacher.json' })

test('路由切换、大屏数据到达与问询等待都跟随真实状态', async ({ page }) => {
  await page.route('**/api/dashboard/summary', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      cached: false,
      cards: { total_submissions: 12, weekly_new: 3, parse_only: 0, pending_conflicts: 1, gold_agreement: null },
      contests: [], bands: [], insufficient_top: [], conflicts: [], hotspots: [],
      citation: { failure_count: 0, total_dimensions: 0, citation_rate: 0 }, gold: null,
    }),
  }))
  await page.route('**/api/dashboard/trend*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ cached: false, days: 30, series: [] }),
  }))
  await page.route('**/api/contests', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ contests: [{ contest_id: 'motion-contest', year: 2026, problem_code: 'A', title: '测试赛题', statement: '', status: 'published', rubric: null, constraints: [], pitfall_count: 0, exemplar_count: 0 }] }),
  }))
  await page.route('**/api/reviews*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ reviews: [], total: 0, page: 1, page_size: 1, scope: 'all' }),
  }))
  await page.route('**/api/chat/sessions', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ session_id: 'motion-session', title: '新会话', created_at: '2026-10-21T00:00:00Z' }) })
    } else {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ sessions: [] }) })
    }
  })
  await page.route('**/api/chat/sessions/motion-session/messages', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ session_id: 'motion-session', messages: [] }) })
      return
    }
    await responseGate
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message_id: 'motion-answer', content: '问询结果已返回', refs: [], model_name: 'test', notifications: { rejected: 0, unused: 0 } }),
    })
  })

  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: '数据大屏' })).toBeVisible()
  await expect(page.locator('[data-dashboard-module]')).toHaveCount(8)
  await expect(page.locator('.dashboard__metrics')).toContainText('12')

  await page.evaluate(() => {
    const state = window as Window & { __pageTransitionEvents?: number }
    state.__pageTransitionEvents = 0
    document.addEventListener('transitionrun', (event) => {
      if ((event.target as HTMLElement).classList?.contains('chat-page')) {
        state.__pageTransitionEvents = (state.__pageTransitionEvents ?? 0) + 1
      }
    })
  })
  await page.getByRole('link', { name: 'AI 问询' }).click()
  await expect(page.getByRole('heading', { name: 'AI 问询' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => (window as Window & { __pageTransitionEvents?: number }).__pageTransitionEvents ?? 0)).toBeGreaterThan(0)
  await page.getByRole('button', { name: '新建会话' }).click()
  await page.getByRole('textbox', { name: '问询内容' }).fill('解释一个维度')

  let releaseResponse!: () => void
  const responseGate = new Promise<void>((resolve) => { releaseResponse = resolve })
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByTestId('request-activity')).toContainText('正在整理回答')
  releaseResponse()
  await expect(page.getByText('问询结果已返回')).toBeVisible()
  await expect(page.getByTestId('request-activity')).toHaveCount(0)
})
