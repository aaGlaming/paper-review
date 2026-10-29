import { expect, test } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

test('登录成功后先展示开场，点击后进入解析页', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill('e2e_student')
  await page.getByLabel('密码').fill('e2e-password-123')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  const intro = page.getByRole('button', { name: /开场动画/ })
  await expect(intro).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)

  await intro.click()
  await expect(page).toHaveURL(/\/parse$/)
  await expect(page.getByRole('heading', { name: '论文解析' })).toBeVisible()
})
