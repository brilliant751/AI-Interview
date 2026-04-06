import { create } from 'zustand'

import type { PipelineMeta } from '../api/interview'

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
  }) => void
  updateTurnResult: (payload: {
    stage: string
    question: string
    score: number
    followUpCount: number
    ttsAudioUrl?: string
    pipelineMeta?: PipelineMeta
  }) => void
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
}

/** 面试全局状态容器。 */
export const useInterviewStore = create<InterviewState & InterviewActions>()((set) => ({
  ...initialState,
  setResumeId: (resumeId) => set({ resumeId }),
  setSessionConfig: (payload) =>
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
      ttsAudioUrl: '',
      pipelineMeta: null,
      lastInputSource: '',
    }),
  updateTurnResult: (payload) =>
    set({
      currentStage: payload.stage,
      currentQuestion: payload.question,
      liveScore: payload.score,
      followUpCount: payload.followUpCount,
      ttsAudioUrl: payload.ttsAudioUrl || '',
      pipelineMeta: payload.pipelineMeta || null,
      lastInputSource: payload.pipelineMeta?.input_source || '',
    }),
  reset: () => set(initialState),
}))
