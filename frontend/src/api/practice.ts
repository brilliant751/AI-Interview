import { apiClient } from './client'

// 题库练习 API 契约：
// 1. 普通练习、练习记录、首页概览和管理端题库维护都集中在该文件。
// 2. PracticeQuestion 是会话题目快照，不一定等同于后台题库最新版本。
// 3. sequence/followup 两种模式共享提交接口，差异由 question_strategy 告诉页面。
// 4. 管理端导入任务返回 task_id，页面需要轮询任务状态而不是阻塞等待。
// 5. 前端类别值使用英文枚举，后端会负责和中文材料类别互相映射。

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
  options: Array<{ key: string; text: string }>
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

/** 题库概览岗位统计。 */
export interface PracticeOverviewRoleStats {
  job_role: 'java' | 'web'
  total_questions: number
  active_sessions: number
  finished_sessions: number
  answered_questions: number
  completion_rate: number
  latest_active_practice_id?: string | null
}

/** 题库概览最近记录。 */
export interface PracticeOverviewRecentRecord {
  practice_id: string
  job_role: 'java' | 'web'
  mode: PracticeMode
  status: 'ACTIVE' | 'FINISHED'
  total_questions: number
  answered_count: number
  created_at: string
}

/** 题库概览响应。 */
export interface PracticeOverviewResponse {
  total_questions: number
  total_answered_questions: number
  total_sessions: number
  active_sessions: number
  role_stats: PracticeOverviewRoleStats[]
  recent_records: PracticeOverviewRecentRecord[]
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
  // 创建练习时后端会立即选题并保存题目快照。
  // 前端拿到响应后可以直接进入第一题，不需要再额外请求题库。
  const { data } = await apiClient.post<PracticeSessionResponse>('/practice/sessions', payload)
  return data
}

/** 获取题库练习会话。 */
export async function fetchPracticeSession(practiceId: string): Promise<PracticeSessionResponse> {
  // 作答页刷新时通过 practiceId 恢复当前题和进度。
  // 后端会校验当前用户是否拥有该练习。
  const { data } = await apiClient.get<PracticeSessionResponse>(`/practice/sessions/${practiceId}`)
  return data
}

/** 提交题库练习答案。 */
export async function submitPracticeAnswer(
  practiceId: string,
  payload: SubmitPracticeAnswerPayload,
): Promise<PracticeAnswerResponse> {
  // 提交答案后，后端返回下一题或 finished 状态。
  // 页面不自行推导题号，避免和服务端顺序规则不一致。
  const { data } = await apiClient.post<PracticeAnswerResponse>(`/practice/sessions/${practiceId}/answers`, payload)
  return data
}

/** 结束题库练习。 */
export async function finishPracticeSession(practiceId: string): Promise<PracticeSessionResponse> {
  // 手动结束后仍返回完整会话快照，页面可以直接刷新进度和状态。
  const { data } = await apiClient.post<PracticeSessionResponse>(`/practice/sessions/${practiceId}/finish`)
  return data
}

/** 获取当前用户练习记录摘要。 */
export async function fetchPracticeRecords(): Promise<PracticeRecordsResponse> {
  // 记录摘要用于列表和首页最近练习，不包含每道题明细。
  const { data } = await apiClient.get<PracticeRecordsResponse>('/practice/records')
  return data
}

/** 获取题库练习首页概览。 */
export async function fetchPracticeOverview(): Promise<PracticeOverviewResponse> {
  // 概览接口已经聚合岗位统计、总题量和最近记录。
  // 页面只负责展示，不重复计算 completion_rate。
  const { data } = await apiClient.get<PracticeOverviewResponse>('/practice/overview')
  return data
}

/** 获取单场练习记录明细。 */
export async function fetchPracticeSessionRecords(practiceId: string): Promise<PracticeSessionRecordsResponse> {
  // 明细接口用于复盘页，返回每道题快照、答案和解析。
  // 它读取的是练习快照，不受当前题库最新编辑影响。
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
  // 管理端题库列表支持岗位、类别、关键字和分页筛选。
  // 该接口需要管理员权限，普通用户页面不应调用。
  const { data } = await apiClient.get<AdminQuestionBankListResponse>('/practice/questions', { params })
  return data
}

/** 上传 Markdown 题库文件。 */
export async function uploadQuestionBankMarkdown(
  jobRole: 'java' | 'web',
  file: File,
): Promise<PracticeImportTriggerResponse> {
  // Markdown 上传后后端会触发导入任务。
  // 返回的是 task_id，页面需要轮询 fetchPracticeImportTask 查看进度。
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
  // 手动录入单题会写入源材料并触发导入。
  // 这样管理端新增题目后，练习接口能读取结构化数据库结果。
  const { data } = await apiClient.post<PracticeImportTriggerResponse>('/practice/questions', payload)
  return data
}

/** 获取题库管理导入任务状态。 */
export async function fetchPracticeImportTask(taskId: string): Promise<PracticeImportTaskResponse> {
  // 任务状态用于展示导入进度、失败原因和报告路径。
  // SUCCESS/PARTIAL_SUCCESS/FAILED 都属于终态，页面可以停止轮询。
  const { data } = await apiClient.get<PracticeImportTaskResponse>(`/practice/questions/import-tasks/${taskId}`)
  return data
}
