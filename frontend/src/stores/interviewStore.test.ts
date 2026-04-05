import { describe, expect, test } from 'vitest'

import { useInterviewStore } from './interviewStore'

/** interviewStore 基础行为测试。 */
describe('interviewStore', () => {
  test('should set resume id and session config', () => {
    useInterviewStore.getState().reset()
    useInterviewStore.getState().setResumeId('res_123456')
    useInterviewStore.getState().setSessionConfig({
      interviewId: 'int_123456',
      jobRole: 'java',
      difficulty: 'medium',
      inputMode: 'text',
      outputMode: 'text',
      stage: 'SELF_INTRO',
      firstQuestion: '请自我介绍',
    })

    const state = useInterviewStore.getState()
    expect(state.resumeId).toBe('res_123456')
    expect(state.interviewId).toBe('int_123456')
    expect(state.currentQuestion).toBe('请自我介绍')
  })

  test('should update turn result', () => {
    useInterviewStore.getState().updateTurnResult({
      stage: 'TECHNICAL',
      question: '请描述一次性能优化',
      score: 78,
      followUpCount: 1,
    })
    const state = useInterviewStore.getState()
    expect(state.currentStage).toBe('TECHNICAL')
    expect(state.currentQuestion).toContain('性能优化')
    expect(state.liveScore).toBe(78)
    expect(state.followUpCount).toBe(1)
  })
})

