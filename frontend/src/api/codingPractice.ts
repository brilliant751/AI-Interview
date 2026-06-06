import { apiClient } from './client'

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
  const { data } = await apiClient.get<CodingPracticeQuestionListResponse>('/coding-practice/questions')
  return data
}

export async function createCodingPracticeSession(questionId: string): Promise<CodingPracticeSessionResponse> {
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
