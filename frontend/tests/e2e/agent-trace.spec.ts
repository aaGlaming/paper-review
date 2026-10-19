import { expect, test } from '@playwright/test'

const report = {
  review_id: 'trace-e2e', status: '完成', contest_id: 'c1', rubric_id: null, rubric_version: null,
  model_name: 'test', source: 'model', agent_terminated_by: 'no_progress',
  dimensions: [], score: { total: 0, weighted: 0, excluded: [], weight_sum: 0 }, change_list: [], note: '',
}

test('轨迹面板用 mock 数据显示三步', async ({ page }) => {
  await page.route('**/api/reviews/trace-e2e/agent-steps', route => route.fulfill({ json: { review_id: 'trace-e2e', steps: [
    { idx: 1, node: 'model', action: 'list_dimensions', args_digest: 'a', result_note: 'ok', ok: true, error_code: null, elapsed_ms: 1, created_at: '' },
    { idx: 2, node: 'tools', action: 'search_evidence', args_digest: 'b', result_note: '命中 1 条', ok: true, error_code: null, elapsed_ms: 2, created_at: '' },
    { idx: 3, node: 'tools', action: 'submit_dimension', args_digest: 'c', result_note: 'ok', ok: false, error_code: 'not_allowed', elapsed_ms: 3, created_at: '' },
  ] } }))
  await page.goto('/scoring')
  await page.evaluate((value) => sessionStorage.setItem('paper-review:review-flow', JSON.stringify(value)), { contestId: 'c1', reviewId: 'trace-e2e', sections: [], report })
  await page.reload()
  await page.getByRole('button', { name: /Agent/ }).click()
  await expect(page.locator('.trace__row')).toHaveCount(3)
  await page.screenshot({ path: 'test-results/agent-trace-panel.png', fullPage: true })
})

test('轨迹面板 mock 空数组显示空态', async ({ page }) => {
  await page.route('**/api/reviews/trace-empty/agent-steps', route => route.fulfill({ json: { review_id: 'trace-empty', steps: [] } }))
  await page.goto('/scoring')
  await page.evaluate((value) => sessionStorage.setItem('paper-review:review-flow', JSON.stringify(value)), { contestId: 'c1', reviewId: 'trace-empty', sections: [], report: { ...report, review_id: 'trace-empty', agent_terminated_by: null } })
  await page.reload()
  await page.getByRole('button', { name: /Agent/ }).click()
  await expect(page.getByText('本次评审未产生 Agent 轨迹')).toBeVisible()
})
