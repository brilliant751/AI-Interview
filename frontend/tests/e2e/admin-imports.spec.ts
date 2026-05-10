import { expect, test } from '@playwright/test'

/** 管理端题库管理页面 E2E。 */
test('admin question bank manage page should submit import tasks', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai_interview_access_token', 'mock-admin-access')
    localStorage.setItem('ai_interview_refresh_token', 'mock-admin-refresh')
    localStorage.setItem(
      'ai_interview_user',
      JSON.stringify({
        user_id: 'admin-default',
        email: 'admin@example.com',
        display_name: '管理员',
        role: 'admin',
        status: 'active',
      }),
    )
  })

  await page.route('**/api/v1/practice/questions?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            record_id: 'qb-001',
            job_role: 'java',
            question_no: 1,
            title: 'JVM',
            category: 'technical',
            question: '什么是 JVM？',
            analysis: '说明运行时职责。',
            source_path: 'backend/assets/material/java/java-interview/mock.md',
            updated_at: '2026-05-08T00:00:00Z',
          },
        ],
        page: 1,
        page_size: 10,
        total: 1,
      }),
    })
  })

  await page.route('**/api/v1/practice/questions/upload', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'kb-build-001',
          status: 'PENDING',
          stage: 'validate',
          progress: 10,
          task_type: 'question_bank',
          idempotency_hit: false,
        }),
      })
      return
    }
    await route.continue()
  })

  let count = 0
  await page.route('**/api/v1/practice/questions/import-tasks/kb-build-001', async (route) => {
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
        rebuild_mode: 'incremental',
        roles: ['java'],
        dry_run: false,
        task_type: 'question_bank',
        last_error: '',
        report_path: 'backend/assets/data/reports/question_bank_build_report.json',
      }),
    })
  })

  await page.goto('http://127.0.0.1:4173/admin/questions')
  await expect(page.getByRole('link', { name: '题库管理' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'JVM', exact: true })).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'batch-import.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Java 题库\n\n## 第 1 题：JVM\n\n### 题干\n\n什么是 JVM？\n\n### 类别\n\n技术\n\n### 解析\n\n说明运行时职责。'),
  })
  await page.getByRole('button', { name: '上传并触发导入' }).click()
  await expect(page.getByText('任务 ID：kb-build-001')).toBeVisible()
  await expect(page.getByText('状态：SUCCESS')).toBeVisible({ timeout: 5_000 })
  await expect(page.getByText('阶段：report')).toBeVisible()
})
