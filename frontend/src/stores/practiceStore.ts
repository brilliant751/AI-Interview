import { create } from 'zustand'

import type { PracticeAnswerResponse, PracticeQuestion, PracticeSessionResponse } from '../api/practice'

// 题库练习 store 的职责：
// 1. 保存当前练习会话的题目进度和当前题快照。
// 2. 不缓存完整题库列表，列表/概览由 React Query 页面层负责。
// 3. applyAnswerResult 只应用提交答案后的服务端结果，避免本地自行推进题号。
// 4. reset 用于离开或重新创建练习时清理上一次状态。

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
    // 后端返回的是练习会话快照，包含当前题和已完成数量。
    // 进入练习页或刷新详情时都可以直接覆盖本地状态。
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
    // 提交答案后只更新进度、状态和下一题。
    // practiceId 缺省时保留当前状态，兼容未来响应字段裁剪。
    set((state) => ({
      practiceId: payload.practice_id || state.practiceId,
      status: payload.status,
      completedCount: payload.completed_count,
      questionStrategy: payload.question_strategy,
      currentQuestion: payload.next_question || null,
    })),
  reset: () => set(initialState),
}))
