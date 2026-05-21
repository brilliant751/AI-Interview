import { create } from 'zustand'

import type { PracticeAnswerResponse, PracticeQuestion, PracticeSessionResponse } from '../api/practice'

/** 题库练习状态模型。 */
interface PracticeState {
  practiceId: string
  jobRole: 'java' | 'web'
  mode: 'sequence' | 'followup'
  status: 'ACTIVE' | 'FINISHED'
  totalQuestions: number
  completedCount: number
  questionStrategy: 'sequence' | 'followup_placeholder'
  currentQuestion: PracticeQuestion | null
}

/** 题库练习状态操作。 */
interface PracticeActions {
  setSession: (payload: PracticeSessionResponse) => void
  applyAnswerResult: (payload: PracticeAnswerResponse) => void
  reset: () => void
}

const initialState: PracticeState = {
  practiceId: '',
  jobRole: 'java',
  mode: 'sequence',
  status: 'ACTIVE',
  totalQuestions: 0,
  completedCount: 0,
  questionStrategy: 'sequence',
  currentQuestion: null,
}

/** 题库练习全局状态。 */
export const usePracticeStore = create<PracticeState & PracticeActions>()((set) => ({
  ...initialState,
  setSession: (payload) =>
    set({
      practiceId: payload.practice_id,
      jobRole: payload.job_role,
      mode: payload.mode,
      status: payload.status,
      totalQuestions: payload.total_questions,
      completedCount: payload.completed_count,
      questionStrategy: payload.question_strategy,
      currentQuestion: payload.current_question || null,
    }),
  applyAnswerResult: (payload) =>
    set((state) => ({
      practiceId: payload.practice_id || state.practiceId,
      status: payload.status,
      completedCount: payload.completed_count,
      questionStrategy: payload.question_strategy,
      currentQuestion: payload.next_question || null,
    })),
  reset: () => set(initialState),
}))
