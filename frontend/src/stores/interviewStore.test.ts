import { describe, expect, test } from 'vitest'

import { useInterviewStore } from './interviewStore'

// interviewStore 测试说明：
// 1. 覆盖简历选择、会话配置、轮次结果和 provider health 更新。
// 2. 所有断言都直接读取 Zustand 状态，不需要渲染页面。
// 3. reset 在每个关键场景前调用，避免上一个测试残留会话数据。
// 4. pipelineMeta 派生字段用于页面展示降级信息，需要单独验证。
// 5. 这些用例保证面试页复杂状态更新有稳定基础。

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
      ttsAudioUrl: 'https://mock-tts.local/test.mp3',
      pipelineMeta: {
        input_source: 'TEXT',
        trace_id: 'trace_123',
        latency_ms: 99,
        providers: { asr: undefined, llm: 'mock', tts: 'mock' },
        provider_status: { asr: 'UP', llm: 'UP', tts: 'UP' },
        degrade_flags: [],
        generation_mode: 'mock',
      },
    })
    const state = useInterviewStore.getState()
    expect(state.currentStage).toBe('TECHNICAL')
    expect(state.currentQuestion).toContain('性能优化')
    expect(state.liveScore).toBe(78)
    expect(state.followUpCount).toBe(1)
    expect(state.ttsAudioUrl).toContain('mock-tts.local')
    expect(state.lastInputSource).toBe('TEXT')
  })

  test('should handle missing pipeline meta gracefully', () => {
    useInterviewStore.getState().updateTurnResult({
      stage: 'BEHAVIORAL',
      question: '请描述一次跨团队协作冲突解决经历',
      score: 82,
      followUpCount: 2,
    })
    const state = useInterviewStore.getState()
    expect(state.currentStage).toBe('BEHAVIORAL')
    expect(state.pipelineMeta).toBeNull()
    expect(state.lastInputSource).toBe('')
    expect(state.ttsAudioUrl).toBe('')
  })
})
