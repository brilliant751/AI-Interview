import { create } from 'zustand'

import type { CodingLanguage, CodingPracticeExecutionResult, CodingPracticeSessionResponse } from '../api/codingPractice'

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

// 编程练习 store 管理编辑器侧状态：
// 1. codeByLanguage 保存每种语言的当前草稿，切换语言时不丢失已输入代码。
// 2. activeCode 是编辑器当前显示内容，和 activeLanguage 保持同步。
// 3. executionResult 只保存最近一次运行或提交结果，切换语言后清空。
// 4. LOCAL_STARTER_CODES 是前端兜底模板，后端没有返回草稿时仍能展示可编辑代码。
// 5. reset 会重新构造代码对象，避免多个会话共享同一个可变引用。

interface CodingPracticeState {
  sessionId: string
  question: CodingPracticeSessionResponse['question'] | null
  status: 'ACTIVE' | 'SOLVED'
  activeLanguage: CodingLanguage
  codeByLanguage: Record<CodingLanguage, string>
  activeCode: string
  saveStatus: SaveStatus
  executionResult: CodingPracticeExecutionResult | null
}

interface CodingPracticeActions {
  setSession: (payload: CodingPracticeSessionResponse) => void
  setActiveLanguage: (language: CodingLanguage) => void
  setActiveCode: (sourceCode: string) => void
  setSaveStatus: (status: SaveStatus) => void
  setExecutionResult: (result: CodingPracticeExecutionResult | null) => void
  reset: () => void
}

const LOCAL_STARTER_CODES: Record<CodingLanguage, string> = {
  cpp: `#include <iostream>
using namespace std;

int main() {
    cout << "hello world" << "\\n";
    return 0;
}
`,
  java: `public class Main {
    public static void main(String[] args) {
        System.out.println("hello world");
    }
}
`,
  javascript: `console.log('hello world')
`,
}

function buildLocalCodes(): Record<CodingLanguage, string> {
  // 每次调用都返回新对象，防止 Zustand 状态之间共享同一份 starter code 引用。
  return {
    cpp: LOCAL_STARTER_CODES.cpp,
    java: LOCAL_STARTER_CODES.java,
    javascript: LOCAL_STARTER_CODES.javascript,
  }
}

const initialCodes = buildLocalCodes()

const initialState: CodingPracticeState = {
  sessionId: '',
  question: null,
  status: 'ACTIVE',
  activeLanguage: 'cpp',
  codeByLanguage: initialCodes,
  activeCode: initialCodes.cpp,
  saveStatus: 'idle',
  executionResult: null,
}

export const useCodingPracticeStore = create<CodingPracticeState & CodingPracticeActions>()((set) => ({
  ...initialState,
  setSession: (payload) => {
    // 进入新题目时重置执行结果和保存状态。
    // 当前实现使用本地 starter code，后续接入后端草稿时可在这里合并。
    const nextCodes = buildLocalCodes()
    set({
      sessionId: payload.session_id,
      question: payload.question,
      status: payload.status,
      activeLanguage: payload.active_language,
      codeByLanguage: nextCodes,
      activeCode: nextCodes[payload.active_language],
      saveStatus: 'idle',
      executionResult: null,
    })
  },
  setActiveLanguage: (language) =>
    // 切换语言时恢复该语言之前的草稿，并清掉旧语言的运行结果。
    set((state) => ({
      activeLanguage: language,
      activeCode: state.codeByLanguage[language],
      executionResult: null,
    })),
  setActiveCode: (sourceCode) =>
    // 编辑器每次变更同时更新 activeCode 和对应语言的代码缓存。
    set((state) => ({
      activeCode: sourceCode,
      codeByLanguage: {
        ...state.codeByLanguage,
        [state.activeLanguage]: sourceCode,
      },
    })),
  setSaveStatus: (status) => set({ saveStatus: status }),
  setExecutionResult: (result) => set({ executionResult: result }),
  reset: () =>
    set({
      ...initialState,
      codeByLanguage: buildLocalCodes(),
      activeCode: buildLocalCodes().cpp,
    }),
}))
