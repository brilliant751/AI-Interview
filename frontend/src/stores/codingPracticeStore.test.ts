import { describe, expect, test } from 'vitest'

import { useCodingPracticeStore } from './codingPracticeStore'

// codingPracticeStore 测试说明：
// 1. 验证进入题目后 session、question 和 activeLanguage 能正确写入。
// 2. 验证本地 starter code 兜底，避免编辑器出现空白内容。
// 3. 验证切换语言时不同语言草稿相互独立。
// 4. 验证运行结果和 reset 行为不会污染下一道题。
// 5. 这些测试不依赖 Monaco，只验证状态容器的纯逻辑。

describe('codingPracticeStore', () => {
  test('stores session payload and injects local starter template', () => {
    useCodingPracticeStore.getState().reset()
    useCodingPracticeStore.getState().setSession({
      session_id: 'code_001',
      status: 'ACTIVE',
      active_language: 'javascript',
      question: {
        question_id: 'coding-a-plus-b',
        slug: 'a-plus-b',
        title: 'A+B',
        difficulty: 'easy',
        topic_tags: ['模拟'],
        prompt_markdown: '给定两个整数，输出它们的和。',
        input_spec: '一行两个整数',
        output_spec: '输出和',
        constraints_text: '',
        sample_cases: [],
        self_test_case: { input: '1 2\n', output: '3\n' },
      },
    })

    const state = useCodingPracticeStore.getState()
    expect(state.sessionId).toBe('code_001')
    expect(state.activeLanguage).toBe('javascript')
    expect(state.activeCode).toContain('hello world')
    expect(state.question?.question_id).toBe('coding-a-plus-b')
  })

  test('tracks saving state and execution result', () => {
    useCodingPracticeStore.getState().reset()
    useCodingPracticeStore.getState().setSaveStatus('saving')
    useCodingPracticeStore.getState().setExecutionResult({
      status: 'ACCEPTED',
      passed_count: 10,
      total_count: 10,
      submit_type: 'SUBMIT',
      message: '全部通过',
      results: [],
    })

    const state = useCodingPracticeStore.getState()
    expect(state.saveStatus).toBe('saving')
    expect(state.executionResult?.status).toBe('ACCEPTED')
    expect(state.executionResult?.passed_count).toBe(10)
  })

  test('switches language with local starter templates and keeps execution result explicit', () => {
    useCodingPracticeStore.getState().reset()
    useCodingPracticeStore.getState().setSession({
      session_id: 'code_001',
      status: 'ACTIVE',
      active_language: 'javascript',
      question: {
        question_id: 'coding-a-plus-b',
        slug: 'a-plus-b',
        title: 'A+B',
        difficulty: 'easy',
        topic_tags: ['模拟'],
        prompt_markdown: '给定两个整数，输出它们的和。',
        input_spec: '一行两个整数',
        output_spec: '输出和',
        constraints_text: '',
        sample_cases: [],
        self_test_case: { input: '1 2\n', output: '3\n' },
      },
    })
    useCodingPracticeStore.getState().setExecutionResult({
      status: 'ACCEPTED',
      passed_count: 1,
      total_count: 1,
      submit_type: 'RUN',
      message: '全部通过',
      results: [],
    })

    useCodingPracticeStore.getState().setActiveLanguage('cpp')

    const state = useCodingPracticeStore.getState()
    expect(state.activeCode).toContain('#include <iostream>')
    expect(state.executionResult).toBeNull()
  })
})
