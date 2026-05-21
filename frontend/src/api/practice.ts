import { apiClient } from './client'

/** 题库练习模式。 */
export type PracticeMode = 'sequence' | 'followup'

/** 题库练习类别。 */
export type PracticeCategory = 'technical' | 'project' | 'scenario' | 'behavior'

/** 当前题目响应。 */
export interface PracticeQuestion {
  session_question_id: string
  question_order: number
  source_question_id?: string
  category?: string
  stem: string
  analysis?: string
}

/** 创建题库练习请求。 */
export interface CreatePracticePayload {
  job_role: 'java' | 'web'
  mode: PracticeMode
  question_count: number
  category_filters?: PracticeCategory[]
}

/** 题库练习会话响应。 */
export interface PracticeSessionResponse {
  practice_id: string
  job_role: 'java' | 'web'
  mode: PracticeMode
  status: 'ACTIVE' | 'FINISHED'
  total_questions: number
  completed_count: number
  finished: boolean
  question_strategy: 'sequence' | 'followup_placeholder'
  current_question?: PracticeQuestion | null
  created_at?: string | null
}

/** 提交答案请求。 */
export interface SubmitPracticeAnswerPayload {
  session_question_id: string
  answer_text: string
}

/** 提交答案响应。 */
export interface PracticeAnswerResponse {
  practice_id: string
  status: 'ACTIVE' | 'FINISHED'
  completed_count: number
  finished: boolean
  question_strategy: 'sequence' | 'followup_placeholder'
  next_question?: PracticeQuestion | null
}

/** 练习记录摘要项。 */
export interface PracticeRecordItem {
  practice_id: string
  job_role: 'java' | 'web'
  mode: PracticeMode
  status: 'ACTIVE' | 'FINISHED'
  total_questions: number
  answered_count: number
  created_at: string
}

/** 练习记录列表响应。 */
export interface PracticeRecordsResponse {
  items: PracticeRecordItem[]
  total: number
}

/** 单场练习记录条目。 */
export interface PracticeSessionRecordItem {
  session_question_id: string
  question_order: number
  category?: string
  stem: string
  analysis?: string
  answer_text?: string
  answered_at?: string
}

/** 单场练习记录明细响应。 */
export interface PracticeSessionRecordsResponse {
  practice_id: string
  job_role: 'java' | 'web'
  mode: PracticeMode
  status: 'ACTIVE' | 'FINISHED'
  total_questions: number
  completed_count: number
  items: PracticeSessionRecordItem[]
  created_at?: string | null
  finished_at?: string | null
}

/** 管理端题库项。 */
export interface AdminQuestionBankItem {
  record_id: string
  job_role: 'java' | 'web'
  question_no: number
  title: string
  category?: string
  question: string
  analysis?: string
  source_path: string
  updated_at: string
}

/** 管理端题库列表响应。 */
export interface AdminQuestionBankListResponse {
  items: AdminQuestionBankItem[]
  page: number
  page_size: number
  total: number
}

/** 管理端单题录入请求。 */
export interface CreateQuestionBankQuestionPayload {
  job_role: 'java' | 'web'
  category: PracticeCategory
  title: string
  question: string
  analysis: string
  source_note?: string
}

/** 导入任务响应。 */
export interface PracticeImportTaskResponse {
  task_id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PARTIAL_SUCCESS'
  stage: string
  progress: number
  rebuild_mode: 'full' | 'incremental'
  roles: Array<'java' | 'web'>
  dry_run: boolean
  task_type: 'question_bank' | 'full_pipeline'
  last_error: string
  report_path: string
}

/** 导入任务触发响应。 */
export interface PracticeImportTriggerResponse {
  task_id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PARTIAL_SUCCESS'
  stage: string
  progress: number
  task_type: 'question_bank' | 'full_pipeline'
  idempotency_hit: boolean
}

/** 创建题库练习。 */
export async function createPracticeSession(payload: CreatePracticePayload): Promise<PracticeSessionResponse> {
  const { data } = await apiClient.post<PracticeSessionResponse>('/practice/sessions', payload)
  return data
}

/** 获取题库练习会话。 */
export async function fetchPracticeSession(practiceId: string): Promise<PracticeSessionResponse> {
  const { data } = await apiClient.get<PracticeSessionResponse>(`/practice/sessions/${practiceId}`)
  return data
}

/** 提交题库练习答案。 */
export async function submitPracticeAnswer(
  practiceId: string,
  payload: SubmitPracticeAnswerPayload,
): Promise<PracticeAnswerResponse> {
  const { data } = await apiClient.post<PracticeAnswerResponse>(`/practice/sessions/${practiceId}/answers`, payload)
  return data
}

/** 结束题库练习。 */
export async function finishPracticeSession(practiceId: string): Promise<PracticeSessionResponse> {
  const { data } = await apiClient.post<PracticeSessionResponse>(`/practice/sessions/${practiceId}/finish`)
  return data
}

/** 获取当前用户练习记录摘要。 */
export async function fetchPracticeRecords(): Promise<PracticeRecordsResponse> {
  const { data } = await apiClient.get<PracticeRecordsResponse>('/practice/records')
  return data
}

/** 获取单场练习记录明细。 */
export async function fetchPracticeSessionRecords(practiceId: string): Promise<PracticeSessionRecordsResponse> {
  const { data } = await apiClient.get<PracticeSessionRecordsResponse>(`/practice/sessions/${practiceId}/records`)
  return data
}

/** 获取管理端题库列表。 */
export async function fetchAdminQuestionBank(params: {
  job_role: 'java' | 'web'
  category?: PracticeCategory
  keyword?: string
  page: number
  page_size: number
}): Promise<AdminQuestionBankListResponse> {
  const { data } = await apiClient.get<AdminQuestionBankListResponse>('/practice/questions', { params })
  return data
}

/** 上传 Markdown 题库文件。 */
export async function uploadQuestionBankMarkdown(
  jobRole: 'java' | 'web',
  file: File,
): Promise<PracticeImportTriggerResponse> {
  const formData = new FormData()
  formData.append('job_role', jobRole)
  formData.append('file', file)
  const { data } = await apiClient.post<PracticeImportTriggerResponse>('/practice/questions/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 录入单题并触发导入。 */
export async function createQuestionBankQuestion(
  payload: CreateQuestionBankQuestionPayload,
): Promise<PracticeImportTriggerResponse> {
  const { data } = await apiClient.post<PracticeImportTriggerResponse>('/practice/questions', payload)
  return data
}

/** 获取题库管理导入任务状态。 */
export async function fetchPracticeImportTask(taskId: string): Promise<PracticeImportTaskResponse> {
  const { data } = await apiClient.get<PracticeImportTaskResponse>(`/practice/questions/import-tasks/${taskId}`)
  return data
}
