import { expect, type Page } from '@playwright/test'

export const CONFIRM_WAIT_MS = 60_000

export async function waitForConfirmed(page: Page): Promise<void> {
  await expect(page.getByTestId('confirmed-card')).toBeVisible({ timeout: CONFIRM_WAIT_MS })
}
