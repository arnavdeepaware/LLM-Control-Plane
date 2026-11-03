import { test, expect } from '@playwright/test'

test('gateway console shows live overview and playground', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Administrator access' })).toBeVisible()
  await page.getByLabel('Admin access code').fill('local-admin-token')
  await page.getByRole('button', { name: 'Open developer console' }).click()
  await expect(page.getByRole('heading', { name: 'Gateway overview' })).toBeVisible()
  await page.getByRole('link', { name: 'Playground' }).click()
  await expect(page.getByRole('heading', { name: 'Playground' })).toBeVisible()
  await page.getByRole('button', { name: 'Use local sample key' }).click()
  await page.getByRole('button', { name: 'Verify key' }).click()
  await expect(page.getByText(/Authenticated as Team Alpha/)).toBeVisible()
  await page.getByRole('textbox', { name: 'Message 1 content' }).fill('Hello gateway')
  await page.getByRole('button', { name: 'Send request' }).click()
  await expect(page.getByRole('heading', { name: 'Response' })).toBeVisible()
  await expect(page.getByText('mock:mock-smart-chat')).toBeVisible()
  await page.getByRole('link', { name: 'Test Lab' }).click()
  await expect(page.getByRole('heading', { name: 'Test Lab' })).toBeVisible()
  await page.getByLabel('Development token').fill('local-dev-token')
  await page.getByRole('button', { name: 'Queue failures' }).click()
  await expect(page.getByText(/PASS Failures queued/)).toBeVisible()
  await page.getByRole('button', { name: 'Primary → fallback' }).click()
  await expect(page.getByText(/PASS Primary fallback/)).toBeVisible()
  await page.getByRole('button', { name: 'Reset all' }).click()
  await expect(page.getByText(/PASS Demo state reset/)).toBeVisible()
  await page.getByRole('link', { name: 'Observability' }).click()
  await expect(page.getByTitle('Gateway Grafana dashboard')).toBeVisible()
  expect((await page.request.get('/grafana/api/health')).status()).toBe(200)
  await page.getByRole('button', { name: 'End admin session' }).click()
  await expect(page.getByRole('heading', { name: 'Administrator access' })).toBeVisible()
  expect((await page.request.get('/admin/teams')).status()).toBe(401)
  expect((await page.request.get('/grafana/api/health')).status()).toBe(401)
})

test('Test Lab verifies each gateway failure mode', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Admin access code').fill('local-admin-token')
  await page.getByRole('button', { name: 'Open developer console' }).click()
  await page.getByRole('link', { name: 'Test Lab' }).click()
  await page.getByLabel('Development token').fill('local-dev-token')
  await page.getByLabel('Scenario team API key').fill('alpha-secret-key')
  for (const [button, result] of [
    ['Retry then success', 'Transient retry'],
    ['Primary → fallback', 'Primary fallback'],
    ['Auth error', 'Provider auth error'],
    ['Block budget', 'Budget block'],
    ['Open circuit', 'Open circuit'],
    ['Exhaust rate limit', 'Rate limit'],
  ]) {
    await page.getByRole('button', { name: button }).click()
    await expect(page.getByText(new RegExp(`PASS ${result}$`)).first()).toBeVisible()
  }
  await page.getByRole('button', { name: 'Reset all' }).click()
  await expect(page.getByText(/PASS Demo state reset/)).toBeVisible()
})
