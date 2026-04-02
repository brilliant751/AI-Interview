import { expect, test } from '@playwright/test'

/** 主流程 E2E：上传 -> 准备 -> 面试 -> 报告 -> 历史。 */
test('main flow should work with mocked backend', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const url = request.url()

    if (method === 'POST' && url.includes('/api/v1/resumes')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ resume_id: 'resume-001', parse_status: 'READY' }),
      })
      return
    }

    if (method === 'POST' && url.includes('/api/v1/interviews') && !url.includes('/turns') && !url.includes('/finish')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          interview_id: 'interview-001',
          current_stage: 'SELF_INTRO',
          first_question: '请做一个简短自我介绍。',
        }),
      })
      return
    }

    if (method === 'POST' && url.includes('/api/v1/interviews/interview-001/turns')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          interview_id: 'interview-001',
          stage: 'TECHNICAL',
          next_question: '介绍一次你排查慢查询的过程。',
          follow_up_count: 1,
          live_score: 88,
          output_mode: 'text',
        }),
      })
      return
    }

    if (method === 'POST' && url.includes('/api/v1/interviews/interview-001/finish')) {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ report_status: 'GENERATING' }),
      })
      return
    }

    if (method === 'GET' && url.includes('/api/v1/report/interview-001')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          interview_id: 'interview-001',
          status: 'READY',
          overall_score: 85,
          strengths: ['表达清晰'],
          weaknesses: ['深度不足'],
          suggestions: ['补充性能调优案例'],
        }),
      })
      return
    }

    if (method === 'GET' && url.includes('/api/v1/interviews/history')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [
            {
              interview_id: 'interview-001',
              job_role: 'java',
              created_at: '2026-04-03T00:00:00Z',
            },
          ],
        }),
      })
      return
    }

    await route.continue()
  })

  await page.goto('/upload')
  await expect(page.getByRole('button', { name: '开始解析并继续' })).toBeVisible()

  await page.locator('input[type="file"]').setInputFiles({
    name: 'resume.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('mock resume file'),
  })
  await page.getByRole('button', { name: '开始解析并继续' }).click()
  await expect(page).toHaveURL(/\/prepare$/)

  await page.getByRole('button', { name: '创建会话' }).click()
  await expect(page).toHaveURL(/\/interview$/)
  await expect(page.getByText('请做一个简短自我介绍。')).toBeVisible()

  await page.getByPlaceholder('输入你的回答').fill('我负责后端开发与性能优化。')
  await page.getByRole('button', { name: '提交回答' }).click()
  await expect(page.getByText('阶段：TECHNICAL')).toBeVisible()
  await expect(page.getByText('实时分：88')).toBeVisible()

  await page.getByRole('button', { name: '结束面试' }).click()
  await expect(page).toHaveURL(/\/report$/)
  await expect(page.getByText('状态：READY')).toBeVisible()
  await expect(page.getByText('总分：85')).toBeVisible()

  await page.getByRole('link', { name: '历史记录' }).click()
  await expect(page).toHaveURL(/\/history$/)
  await expect(page.getByText('interview-001')).toBeVisible()
})
