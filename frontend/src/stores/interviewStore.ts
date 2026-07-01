import { create } from 'zustand'

import type { ProviderHealthResponse } from '../api/admin'
import type { PipelineMeta } from '../api/interview'

// 面试 store 保存“当前正在进行的会话”：
// 1. 页面刷新后的长期恢复主要靠后端接口，store 只保存当前前端运行期状态。
// 2. pipelineMeta 用于展示本轮是否走了 ASR/LLM/TTS 以及是否降级。
// 3. providerHealth 是管理端健康信息的轻量缓存，避免每个组件重复请求。
// 4. setSessionConfig 在创建或恢复会话时重置轮次状态。
// 5. updateTurnResult 只接收后端确认后的结果，不在本地预测下一阶段。

/** 面试流程状态模型。 */
interface InterviewState {
  resumeId: string
  interviewId: string
  jobRole: 'java' | 'web'
  difficulty: 'easy' | 'medium' | 'hard'
  inputMode: 'text' | 'voice'
  outputMode: 'text' | 'voice'
  currentStage: string
  currentQuestion: string
  liveScore: number
  followUpCount: number
  ttsAudioUrl: string
  pipelineMeta: PipelineMeta | null
  lastInputSource: string
  generationMode: 'local_ai' | 'fallback_template' | 'mock'
  providerHealth: ProviderHealthResponse | null
}

/** 面试流程状态操作。 */
interface InterviewActions {
  setResumeId: (resumeId: string) => void
  setSessionConfig: (payload: {
    interviewId: string
    jobRole: 'java' | 'web'
    difficulty: 'easy' | 'medium' | 'hard'
    inputMode: 'text' | 'voice'
    outputMode: 'text' | 'voice'
    stage: string
    firstQuestion: string
    ttsAudioUrl?: string
  }) => void
  updateTurnResult: (payload: {
    stage: string
    question: string
    score: number
    followUpCount: number
    ttsAudioUrl?: string
    pipelineMeta?: PipelineMeta
  }) => void
  setProviderHealth: (health: ProviderHealthResponse | null) => void
  syncSessionStatus: (payload: { stage: string; followUpCount: number; currentQuestion?: string; ttsAudioUrl?: string }) => void
  reset: () => void
}

/** 初始状态对象。 */
const initialState: InterviewState = {
  resumeId: '',
  interviewId: '',
  jobRole: 'java',
  difficulty: 'medium',
  inputMode: 'text',
  outputMode: 'text',
  currentStage: 'SELF_INTRO',
  currentQuestion: '',
  liveScore: 0,
  followUpCount: 0,
  ttsAudioUrl: '',
  pipelineMeta: null,
  lastInputSource: '',
  generationMode: 'mock',
  providerHealth: null,
}

/** 面试全局状态容器。 */
export const useInterviewStore = create<InterviewState & InterviewActions>()((set) => ({
  ...initialState,
  setResumeId: (resumeId) => set({ resumeId }),
  setSessionConfig: (payload) =>
    // 新会话开始时清空上一场面试的即时分、降级信息和 provider 状态。
    set({
      interviewId: payload.interviewId,
      jobRole: payload.jobRole,
      difficulty: payload.difficulty,
      inputMode: payload.inputMode,
      outputMode: payload.outputMode,
      currentStage: payload.stage,
      currentQuestion: payload.firstQuestion,
      liveScore: 0,
      followUpCount: 0,
      ttsAudioUrl: payload.ttsAudioUrl || '',
      pipelineMeta: null,
      lastInputSource: '',
      generationMode: 'mock',
      providerHealth: null,
    }),
  updateTurnResult: (payload) =>
    // 每次提交回答后，以后端返回的阶段、题目和分数作为唯一事实来源。
    // generationMode/lastInputSource 从 pipelineMeta 派生，供页面标签和提示展示。
    set({
      currentStage: payload.stage,
      currentQuestion: payload.question,
      liveScore: payload.score,
      followUpCount: payload.followUpCount,
      ttsAudioUrl: payload.ttsAudioUrl || '',
      pipelineMeta: payload.pipelineMeta || null,
      lastInputSource: payload.pipelineMeta?.input_source || '',
      generationMode: payload.pipelineMeta?.generation_mode || 'mock',
    }),
  setProviderHealth: (health) => set({ providerHealth: health }),
  syncSessionStatus: (payload) =>
    // 恢复暂停会话或轮询任务状态时，只同步服务端确认的字段。
    // currentQuestion/ttsAudioUrl 未提供时保留原值，避免短暂空响应清掉页面题目。
    set((state) => ({
      currentStage: payload.stage,
      followUpCount: payload.followUpCount,
      currentQuestion: payload.currentQuestion ?? state.currentQuestion,
      ttsAudioUrl: payload.ttsAudioUrl ?? state.ttsAudioUrl,
    })),
  reset: () => set(initialState),
}))
