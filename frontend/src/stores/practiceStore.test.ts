import { describe, expect, test } from 'vitest'

import { usePracticeStore } from './practiceStore'

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
      },
    })

    const state = usePracticeStore.getState()
    expect(state.completedCount).toBe(1)
    expect(state.currentQuestion?.session_question_id).toBe('psq_002')
  })
})
