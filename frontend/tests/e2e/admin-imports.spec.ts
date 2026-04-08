import { expect, test } from '@playwright/test'

/** 管理端重建任务页面 E2E。 */
test('admin imports should trigger and poll task status', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai_interview_token', 'admin-token')
  })

  await page.route('**/api/v1/admin/imports/materials', async (route) => {
    const method = route.request().method()
    if (method === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'kb-build-001',
          status: 'PENDING',
          stage: 'validate',
          progress: 10,
          idempotency_hit: false,
        }),
      })
      return
    }
    await route.continue()
  })

  let count = 0
  await page.route('**/api/v1/admin/imports/materials/kb-build-001', async (route) => {
    count += 1
    const done = count > 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        task_id: 'kb-build-001',
        status: done ? 'SUCCESS' : 'RUNNING',
        stage: done ? 'report' : 'embedding',
        progress: done ? 100 : 55,
        rebuild_mode: 'full',
        roles: ['java', 'web'],
        dry_run: false,
        last_error: '',
        report_path: 'backend/assets/data/reports/knowledge_vectorstore_build_report.json',
      }),
    })
  })

  await page.goto('/admin/imports')
  await expect(page.getByText('知识库重建任务')).toBeVisible()
  await page.getByRole('button', { name: '发起任务' }).click()
  await expect(page.getByText('任务 ID：kb-build-001')).toBeVisible()
  await expect(page.getByText('状态：SUCCESS')).toBeVisible({ timeout: 5_000 })
  await expect(page.getByText('阶段：report')).toBeVisible()
})
