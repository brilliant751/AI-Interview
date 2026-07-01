import { apiClient } from './client'

// 在线编程练习 API 契约：
// 1. 题目列表带用户进度，详情通过创建/恢复 session 后获取。
// 2. RUN 表示自测样例，SUBMIT 表示正式判题，两者共用执行结果结构。
// 3. source_code 可选，后端会在缺省时回退到题目 starter code。
// 4. results 设计为 Record<string, unknown>，兼容不同语言和判题错误的扩展字段。
// 5. 页面层只根据 status/message/passed_count 做展示，不直接理解后端执行细节。

export type CodingLanguage = 'cpp' | 'java' | 'javascript'

export interface CodingPracticeQuestionSummary {
  question_id: string
  slug: string
  title: string
  difficulty: 'easy' | 'medium' | 'hard'
  topic_tags: string[]
  status: 'NOT_STARTED' | 'ACTIVE' | 'SOLVED'
  last_language: CodingLanguage
  latest_submission_status?: string | null
  session_id?: string | null
  updated_at?: string | null
}

export interface CodingPracticeQuestionDetail {
  question_id: string
  slug: string
  title: string
  difficulty: 'easy' | 'medium' | 'hard'
  topic_tags: string[]
  prompt_markdown: string
  input_spec: string
  output_spec: string
  constraints_text: string
  sample_cases: Array<{ input: string; output: string }>
  self_test_case: { input: string; output: string }
}

export interface CodingPracticeSessionResponse {
  session_id: string
  question: CodingPracticeQuestionDetail
  status: 'ACTIVE' | 'SOLVED'
  active_language: CodingLanguage
  last_opened_at?: string | null
  created_at?: string | null
}

export interface CodingPracticeExecutionResult {
  status: string
  passed_count: number
  total_count: number
  submit_type: 'RUN' | 'SUBMIT'
  message: string
  results: Array<Record<string, unknown>>
  compile_output?: string | null
}

export interface CodingPracticeExecutionResponse {
  session_id: string
  submission_id: string
  result: CodingPracticeExecutionResult
}

export interface CodingPracticeQuestionListResponse {
  items: CodingPracticeQuestionSummary[]
  total: number
}

export interface CodingPracticeRecordsResponse {
  items: Array<{
    session_id: string
    question_id: string
    title: string
    difficulty: 'easy' | 'medium' | 'hard'
    status: 'ACTIVE' | 'SOLVED'
    last_language: CodingLanguage
    latest_submission_status?: string | null
    last_opened_at?: string | null
    created_at?: string | null
  }>
  total: number
}

export async function fetchCodingPracticeQuestions(): Promise<CodingPracticeQuestionListResponse> {
  // 列表接口已经合并当前用户进度，页面无需再逐题查询 session。
  const { data } = await apiClient.get<CodingPracticeQuestionListResponse>('/coding-practice/questions')
  return data
}

export async function createCodingPracticeSession(questionId: string): Promise<CodingPracticeSessionResponse> {
  // 后端会按 user_id + question_id 创建或恢复会话，因此重复进入同一道题不会丢失上下文。
  const { data } = await apiClient.post<CodingPracticeSessionResponse>('/coding-practice/sessions', {
    question_id: questionId,
  })
  return data
}

export async function fetchCodingPracticeSession(sessionId: string): Promise<CodingPracticeSessionResponse> {
  const { data } = await apiClient.get<CodingPracticeSessionResponse>(`/coding-practice/sessions/${sessionId}`)
  return data
}

export async function runCodingPracticeSelfTest(
  sessionId: string,
  payload: { language: CodingLanguage; source_code?: string },
): Promise<CodingPracticeExecutionResponse> {
  const { data } = await apiClient.post<CodingPracticeExecutionResponse>(`/coding-practice/sessions/${sessionId}/run`, payload)
  return data
}

export async function submitCodingPracticeSolution(
  sessionId: string,
  payload: { language: CodingLanguage; source_code?: string },
): Promise<CodingPracticeExecutionResponse> {
  const { data } = await apiClient.post<CodingPracticeExecutionResponse>(`/coding-practice/sessions/${sessionId}/submit`, payload)
  return data
}

export async function fetchCodingPracticeRecords(): Promise<CodingPracticeRecordsResponse> {
  const { data } = await apiClient.get<CodingPracticeRecordsResponse>('/coding-practice/records')
  return data
}
