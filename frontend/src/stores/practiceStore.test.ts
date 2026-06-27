import { describe, expect, test } from 'vitest'

import { usePracticeStore } from './practiceStore'

// practiceStore 测试说明：
// 1. 验证创建练习后会话快照能完整进入 store。
// 2. 验证提交答案后 currentQuestion 会切换到后端返回的下一题。
// 3. 验证完成状态和 completedCount 不由页面自行推算。
// 4. reset 用来隔离每个测试用例，避免题目快照残留。
// 5. 这些测试保护题库练习作答页的核心状态流。

/** practiceStore 基础行为测试。 */
describe('practiceStore', () => {
  test('stores session payload', () => {
    usePracticeStore.getState().reset()
    usePracticeStore.getState().setSession({
      practice_id: 'prac_001',
      job_role: 'java',
      mode: 'sequence',
      status: 'ACTIVE',
      total_questions: 2,
      completed_count: 0,
      finished: false,
      question_strategy: 'sequence',
      current_question: {
        session_question_id: 'psq_001',
        question_order: 1,
        stem: '什么是 JVM？',
        options: [],
      },
    })

    const state = usePracticeStore.getState()
    expect(state.practiceId).toBe('prac_001')
    expect(state.currentQuestion?.session_question_id).toBe('psq_001')
    expect(state.totalQuestions).toBe(2)
  })

  test('applies answer result and switches to next question', () => {
    usePracticeStore.getState().reset()
    usePracticeStore.getState().setSession({
      practice_id: 'prac_001',
      job_role: 'java',
      mode: 'sequence',
      status: 'ACTIVE',
      total_questions: 2,
      completed_count: 0,
      finished: false,
      question_strategy: 'sequence',
      current_question: {
        session_question_id: 'psq_001',
        question_order: 1,
        stem: '第一题',
        options: [],
      },
    })

    usePracticeStore.getState().applyAnswerResult({
      practice_id: 'prac_001',
      status: 'ACTIVE',
      completed_count: 1,
      finished: false,
      question_strategy: 'sequence',
      next_question: {
        session_question_id: 'psq_002',
        question_order: 2,
        stem: '第二题',
        options: [],
      },
    })

    const state = usePracticeStore.getState()
    expect(state.completedCount).toBe(1)
    expect(state.currentQuestion?.session_question_id).toBe('psq_002')
  })
})
