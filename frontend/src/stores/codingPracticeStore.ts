import { create } from 'zustand'

import type { CodingLanguage, CodingPracticeExecutionResult, CodingPracticeSessionResponse } from '../api/codingPractice'

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

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
    set((state) => ({
      activeLanguage: language,
      activeCode: state.codeByLanguage[language],
      executionResult: null,
    })),
  setActiveCode: (sourceCode) =>
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
