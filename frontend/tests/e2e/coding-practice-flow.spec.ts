import { expect, test } from '@playwright/test'

test('coding practice flow should work with mocked backend', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai_interview_access_token', 'mock-access')
    localStorage.setItem('ai_interview_refresh_token', 'mock-refresh')
    localStorage.setItem(
      'ai_interview_user',
      JSON.stringify({
        user_id: 'usr_test',
        email: 'user@example.com',
        display_name: '测试用户',
        role: 'user',
        status: 'active',
      }),
    )
  })

  await page.route('**/api/v1/coding-practice/questions', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            question_id: 'coding-a-plus-b',
            slug: 'a-plus-b',
            title: 'A+B',
            difficulty: 'easy',
            topic_tags: ['模拟'],
            status: 'NOT_STARTED',
            last_language: 'cpp',
            latest_submission_status: null,
            session_id: null,
          },
        ],
        total: 1,
      }),
    })
  })

  await page.route('**/api/v1/coding-practice/sessions', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'code-001',
        status: 'ACTIVE',
        active_language: 'javascript',
        question: {
          question_id: 'coding-a-plus-b',
          slug: 'a-plus-b',
          title: 'A+B',
          difficulty: 'easy',
          topic_tags: ['模拟'],
          prompt_markdown: '给定两个整数，输出它们的和。',
          input_spec: '输入两个整数',
          output_spec: '输出和',
          constraints_text: '32 位整数范围',
          sample_cases: [{ input: '1 2\n', output: '3\n' }],
          self_test_case: { input: '8 9\n', output: '17\n' },
        },
      }),
    })
  })

  await page.route('**/api/v1/coding-practice/sessions/code-001', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'code-001',
        status: 'ACTIVE',
        active_language: 'javascript',
        question: {
          question_id: 'coding-a-plus-b',
          slug: 'a-plus-b',
          title: 'A+B',
          difficulty: 'easy',
          topic_tags: ['模拟'],
          prompt_markdown: '给定两个整数，输出它们的和。',
          input_spec: '输入两个整数',
          output_spec: '输出和',
          constraints_text: '32 位整数范围',
          sample_cases: [{ input: '1 2\n', output: '3\n' }],
          self_test_case: { input: '8 9\n', output: '17\n' },
        },
      }),
    })
  })

  await page.route('**/api/v1/coding-practice/sessions/code-001/run', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'code-001',
        submission_id: 'sub-run',
        result: {
          status: 'ACCEPTED',
          passed_count: 1,
          total_count: 1,
          submit_type: 'RUN',
          message: '全部通过',
          results: [],
        },
      }),
    })
  })

  await page.route('**/api/v1/coding-practice/sessions/code-001/submit', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'code-001',
        submission_id: 'sub-submit',
        result: {
          status: 'ACCEPTED',
          passed_count: 10,
          total_count: 10,
          submit_type: 'SUBMIT',
          message: '全部通过',
          results: [],
        },
      }),
    })
  })

  await page.goto('http://127.0.0.1:4173/coding-practice')
  await expect(page.getByRole('heading', { name: '编程练习' })).toBeVisible()
  await page.getByRole('button', { name: '开始练习' }).click()
  await expect(page).toHaveURL(/\/coding-practice\/code-001$/)
  await expect(page.getByText('A+B')).toBeVisible()
  await expect(page.locator('.monaco-editor')).toContainText('hello world')

  await page.getByRole('button', { name: '运行自测' }).click()
  await expect(page.getByText('通过 1/1')).toBeVisible()

  await page.getByRole('button', { name: '提交判题' }).click()
  await expect(page.getByText('通过 10/10')).toBeVisible()
})
