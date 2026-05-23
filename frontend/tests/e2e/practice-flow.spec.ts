import { expect, test } from '@playwright/test'

/** 题库练习流程 E2E。 */
test('practice flow should work with mocked backend', async ({ page }) => {
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

  await page.route('**/api/v1/practice/records', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    })
  })

  await page.route('**/api/v1/practice/overview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_questions: 200,
        total_answered_questions: 0,
        total_sessions: 0,
        active_sessions: 0,
        role_stats: [
          {
            job_role: 'java',
            total_questions: 120,
            active_sessions: 0,
            finished_sessions: 0,
            answered_questions: 0,
            completion_rate: 0,
            latest_active_practice_id: null,
          },
          {
            job_role: 'web',
            total_questions: 80,
            active_sessions: 0,
            finished_sessions: 0,
            answered_questions: 0,
            completion_rate: 0,
            latest_active_practice_id: null,
          },
        ],
        recent_records: [],
      }),
    })
  })

  await page.route('**/api/v1/practice/sessions', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        practice_id: 'prac-001',
        job_role: 'java',
        mode: 'sequence',
        status: 'ACTIVE',
        total_questions: 2,
        completed_count: 0,
        finished: false,
        question_strategy: 'sequence',
        current_question: {
          session_question_id: 'psq-001',
          question_order: 1,
          category: 'technical',
          stem: '什么是 JVM？',
        },
      }),
    })
  })

  await page.route('**/api/v1/practice/sessions/prac-001', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        practice_id: 'prac-001',
        job_role: 'java',
        mode: 'sequence',
        status: 'ACTIVE',
        total_questions: 2,
        completed_count: 0,
        finished: false,
        question_strategy: 'sequence',
        current_question: {
          session_question_id: 'psq-001',
          question_order: 1,
          category: 'technical',
          stem: '什么是 JVM？',
        },
      }),
    })
  })

  let answerCount = 0
  await page.route('**/api/v1/practice/sessions/prac-001/answers', async (route) => {
    answerCount += 1
    if (answerCount === 1) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          practice_id: 'prac-001',
          status: 'ACTIVE',
          completed_count: 1,
          finished: false,
          question_strategy: 'sequence',
          next_question: {
            session_question_id: 'psq-002',
            question_order: 2,
            category: 'project',
            stem: '介绍一次性能优化。',
          },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        practice_id: 'prac-001',
        status: 'FINISHED',
        completed_count: 2,
        finished: true,
        question_strategy: 'sequence',
        next_question: null,
      }),
    })
  })

  await page.route('**/api/v1/practice/sessions/prac-001/records', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        practice_id: 'prac-001',
        job_role: 'java',
        mode: 'sequence',
        status: 'FINISHED',
        total_questions: 2,
        completed_count: 2,
        items: [
          { session_question_id: 'psq-001', question_order: 1, category: 'technical', stem: '什么是 JVM？', answer_text: 'Java 虚拟机。' },
          { session_question_id: 'psq-002', question_order: 2, category: 'project', stem: '介绍一次性能优化。', answer_text: '优化 SQL 与缓存。' },
        ],
      }),
    })
  })

  await page.goto('http://127.0.0.1:4173/practice')
  await expect(page.getByRole('link', { name: '题库练习' })).toBeVisible()
  await page.getByRole('button', { name: '开始该岗位练习' }).first().click()
  await expect(page).toHaveURL(/\/practice\/prac-001$/)
  await expect(page.getByText('什么是 JVM？')).toBeVisible()

  await page.getByPlaceholder('输入你的回答').fill('Java 虚拟机。')
  await page.getByRole('button', { name: '提交并进入下一题' }).click()
  await expect(page.getByText('介绍一次性能优化。')).toBeVisible()

  await page.getByPlaceholder('输入你的回答').fill('优化 SQL 与缓存。')
  await page.getByRole('button', { name: '提交并进入下一题' }).click()
  await expect(page).toHaveURL(/\/practice\/prac-001\/records$/)
  await expect(page.getByText('Java 虚拟机。')).toBeVisible()
  await expect(page.getByText('优化 SQL 与缓存。')).toBeVisible()
})

/** 题库练习继续同岗位 active 会话 E2E。 */
test('practice prepare should continue active session by role', async ({ page }) => {
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

  await page.route('**/api/v1/practice/overview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_questions: 200,
        total_answered_questions: 12,
        total_sessions: 2,
        active_sessions: 1,
        role_stats: [
          {
            job_role: 'java',
            total_questions: 120,
            active_sessions: 1,
            finished_sessions: 1,
            answered_questions: 12,
            completion_rate: 0.1,
            latest_active_practice_id: 'prac-active-java',
          },
          {
            job_role: 'web',
            total_questions: 80,
            active_sessions: 0,
            finished_sessions: 0,
            answered_questions: 0,
            completion_rate: 0,
            latest_active_practice_id: null,
          },
        ],
        recent_records: [],
      }),
    })
  })

  await page.route('**/api/v1/practice/records', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            practice_id: 'prac-active-java',
            job_role: 'java',
            mode: 'sequence',
            status: 'ACTIVE',
            total_questions: 10,
            answered_count: 2,
            created_at: '2026-05-23 10:00:00',
          },
        ],
        total: 1,
      }),
    })
  })

  await page.route('**/api/v1/practice/sessions', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 500, body: 'should not create session' })
      return
    }
    await route.continue()
  })

  await page.route('**/api/v1/practice/sessions/prac-active-java', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        practice_id: 'prac-active-java',
        job_role: 'java',
        mode: 'sequence',
        status: 'ACTIVE',
        total_questions: 10,
        completed_count: 2,
        finished: false,
        question_strategy: 'sequence',
        current_question: {
          session_question_id: 'psq-003',
          question_order: 3,
          category: 'technical',
          stem: '什么是 GC？',
        },
      }),
    })
  })

  await page.goto('http://127.0.0.1:4173/practice')
  await page.getByRole('button', { name: '继续该岗位练习' }).first().click()
  await expect(page).toHaveURL(/\/practice\/prac-active-java$/)
  await expect(page.getByText('什么是 GC？')).toBeVisible()
})
