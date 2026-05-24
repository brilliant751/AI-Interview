import { apiClient } from './client'

/** 创建会话请求体。 */
export interface CreateInterviewPayload {
  resume_id: string
  job_role?: 'java' | 'web'
  difficulty: 'easy' | 'medium' | 'hard'
  input_mode: 'text' | 'voice'
  output_mode: 'text' | 'voice'
  session_name?: string
  question_types?: Array<'project' | 'technical' | 'scenario'>
  jd_id?: string
}

/** 会话创建响应。 */
export interface CreateInterviewResponse {
  interview_id: string
  current_stage: string
  first_question: string
  tts_audio_url?: string
}

/** 轮次提交请求体。 */
export interface SubmitTurnPayload {
  stage: string
  answer_text: string
  asr_text?: string
  answer_audio_url?: string
  answer_audio_format?: string
}

/** 音频轮次提交请求体。 */
export interface SubmitAudioTurnPayload {
  stage: string
  file: File
}

/** 链路 provider 信息。 */
export interface PipelineProviders {
  asr?: string
  llm?: string
  tts?: string
}

/** 链路元数据。 */
export interface PipelineMeta {
  input_source: string
  providers: PipelineProviders
  provider_status: {
    asr: string
    llm: string
    tts: string
  }
  degrade_flags: string[]
  trace_id: string
  latency_ms: number
  generation_mode: 'local_ai' | 'fallback_template' | 'mock'
}

/** 轮次提交响应。 */
export interface SubmitTurnResponse {
  interview_id: string
  stage: string
  next_question: string
  follow_up_count: number
  live_score: number
  output_mode: 'text' | 'voice'
  tts_audio_url?: string
  pipeline_meta?: PipelineMeta
}

/** 轮次异步任务响应。 */
export interface SubmitTurnJobResponse {
  interview_id: string
  job_id: string
  status: 'PROCESSING'
}

/** 轮次异步任务查询响应。 */
export interface SubmitTurnJobResultResponse {
  interview_id: string
  job_id: string
  status: 'PROCESSING' | 'READY' | 'FAILED'
  result?: SubmitTurnResponse
  error_message?: string
}

/** 报告响应。 */
export interface ReportResponse {
  interview_id: string
  status: 'GENERATING' | 'READY' | 'FAILED'
  overall_score?: number
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  dimension_scores: Array<{
    dimension: string
    capability_score: number
    match_score: number
    confidence: string
    evidence: string
  }>
  jd_resume_alignment: Array<{
    jd_skill: string
    priority: string
    resume_evidence: string
    answer_evidence: string
    status: string
    note: string
  }>
  question_deep_dives: Array<{
    question_no: number
    question: string
    intent: string
    answer_summary: string
    hit_rate: number
    depth_level: string
    resume_relevance: string
    jd_relevance: string
    strengths: string
    gaps: string
    follow_up_questions: string[]
  }>
  key_risks: string[]
  final_recommendation: string
  error_message?: string
}

/** 历史记录响应。 */
export interface HistoryResponse {
  total: number
  items: Array<{
    interview_id: string
    session_name?: string
    resume_id: string
    job_role: string
    difficulty: string
    status: string
    jd_id?: string
    jd_title?: string
    jd_source_type?: string
    started_at: string
    finished_at?: string
    turn_count: number
    created_at: string
    overall_score?: number
  }>
}

/** 简历列表响应。 */
export interface ResumeListResponse {
  items: Array<{
    resume_id: string
    file_name: string
    parse_status: string
    created_at: string
    last_used_at?: string
  }>
  page: number
  page_size: number
  total: number
}

/** 回放详情响应。 */
export interface InterviewPlaybackResponse {
  interview_id: string
  resume: {
    resume_id: string
    file_name: string
  }
  meta: {
    job_role: string
    difficulty: string
    status: string
    jd_id?: string
    jd_title?: string
    jd_source_type?: string
    started_at: string
    finished_at?: string
    duration_seconds: number
    duration_updated_at?: string
  }
  turns: Array<{
    turn_id: string
    sequence: number
    question: string
    answer: string
    question_ts: string
    answer_ts?: string
  }>
}

/** 会话状态响应。 */
export interface InterviewStatusResponse {
  interview_id: string
  status: string
  current_stage: string
  follow_up_count: number
  technical_count: number
  job_role: 'java' | 'web'
  difficulty: 'easy' | 'medium' | 'hard'
  input_mode: 'text' | 'voice'
  output_mode: 'text' | 'voice'
  jd_id?: string
  jd_title?: string
  jd_source_type?: string
  current_question: string
  tts_audio_url?: string
  duration_seconds: number
  duration_updated_at?: string
}

/** JD 列表响应。 */
export interface JdListResponse {
  items: Array<{
    jd_id: string
    source_type: 'USER_UPLOAD' | 'SYSTEM_PRESET'
    company_id: string
    company_name: string
    title: string
    job_role: string
    status: string
    content_text: string
    created_at: string
    updated_at: string
  }>
}

/** 公司列表响应。 */
export interface CompanyListResponse {
  items: Array<{
    company_id: string
    name: string
    status: string
    created_at: string
    updated_at: string
  }>
}

/** 上传简历并返回简历 ID。 */
export async function uploadResume(file: File): Promise<{ resume_id: string; parse_status: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post('/resumes', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 查询简历列表。 */
export async function fetchResumes(params: { page: number; page_size: number }): Promise<ResumeListResponse> {
  const { data } = await apiClient.get<ResumeListResponse>('/resumes', { params })
  return data
}

/** 删除简历。 */
export async function deleteResume(resumeId: string): Promise<void> {
  await apiClient.delete(`/resumes/${resumeId}`)
}

/** 获取简历原始文件（二进制）。 */
export async function fetchResumeFile(resumeId: string): Promise<Blob> {
  const { data } = await apiClient.get(`/resumes/${resumeId}/file`, { responseType: 'blob' })
  return data as Blob
}

/** 创建面试会话。 */
export async function createInterview(payload: CreateInterviewPayload): Promise<CreateInterviewResponse> {
  const { data } = await apiClient.post('/interviews', payload)
  return data
}

/** 提交面试轮次。 */
export async function submitTurn(
  interviewId: string,
  payload: SubmitTurnPayload,
): Promise<SubmitTurnJobResponse> {
  const { data } = await apiClient.post(`/interviews/${interviewId}/turns`, payload)
  return data
}

/** 提交音频轮次。 */
export async function submitAudioTurn(
  interviewId: string,
  payload: SubmitAudioTurnPayload,
): Promise<SubmitTurnJobResponse> {
  const formData = new FormData()
  formData.append('stage', payload.stage)
  formData.append('file', payload.file)
  const { data } = await apiClient.post(`/interviews/${interviewId}/turns/audio`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 查询轮次异步任务结果。 */
export async function fetchTurnJobResult(
  interviewId: string,
  jobId: string,
): Promise<SubmitTurnJobResultResponse> {
  const { data } = await apiClient.get(`/interviews/${interviewId}/turn-jobs/${jobId}`)
  return data
}

/** 结束面试并触发报告。 */
export async function finishInterview(interviewId: string): Promise<{ report_status: string }> {
  const { data } = await apiClient.post(`/interviews/${interviewId}/finish`, undefined, { timeout: 30000 })
  return data
}

/** 暂停面试。 */
export async function pauseInterview(interviewId: string): Promise<{ interview_id: string; status: string }> {
  const { data } = await apiClient.post(`/interviews/${interviewId}/pause`)
  return data
}

/** 查询面试报告。 */
export async function fetchReport(interviewId: string): Promise<ReportResponse> {
  const { data } = await apiClient.get(`/report/${interviewId}`)
  return data
}

/** 触发报告重试。 */
export async function retryReport(interviewId: string): Promise<{ status: string }> {
  const { data } = await apiClient.post(`/report/${interviewId}/retry`)
  return data
}

/** 查询历史记录。 */
export async function fetchHistory(params: { page: number; page_size: number; job_role?: string; status?: string }) {
  const { data } = await apiClient.get<HistoryResponse>('/interviews/history', { params })
  return data
}

/** 删除历史面试记录。 */
export async function deleteInterviewHistory(interviewId: string): Promise<{ interview_id: string; deleted: boolean }> {
  const { data } = await apiClient.delete(`/interviews/history/${interviewId}`)
  return data
}

/** 查询会话当前状态。 */
export async function fetchInterviewStatus(
  interviewId: string,
  params?: { status?: 'ACTIVE' | 'PAUSED' },
): Promise<InterviewStatusResponse> {
  const { data } = await apiClient.get<InterviewStatusResponse>(`/interviews/${interviewId}/status`, { params })
  return data
}

/** 查询面试回放详情。 */
export async function fetchInterviewPlayback(interviewId: string): Promise<InterviewPlaybackResponse> {
  const { data } = await apiClient.get<InterviewPlaybackResponse>(`/interviews/${interviewId}/playback`)
  return data
}

/** 上传 JD。 */
export async function uploadJd(payload: {
  job_role: string
  title?: string
  file?: File
  content_text?: string
  company_id?: string
}) {
  const formData = new FormData()
  formData.append('job_role', payload.job_role)
  if (payload.title) {
    formData.append('title', payload.title)
  }
  if (payload.file) {
    formData.append('file', payload.file)
  }
  if (payload.content_text) {
    formData.append('content_text', payload.content_text)
  }
  if (payload.company_id) {
    formData.append('company_id', payload.company_id)
  }
  const { data } = await apiClient.post('/jds', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data as { jd_id: string; title: string; job_role: 'java' | 'web' }
}

/** 查询公司列表。 */
export async function fetchCompanies(): Promise<CompanyListResponse> {
  const { data } = await apiClient.get<CompanyListResponse>('/companies')
  return data
}

/** 查询 JD 列表。 */
export async function fetchJds(params?: {
  job_role?: string
  source_type?: 'USER_UPLOAD' | 'SYSTEM_PRESET'
  title?: string
}): Promise<JdListResponse> {
  const { data } = await apiClient.get<JdListResponse>('/jds', { params })
  return data
}

/** 删除 JD。 */
export async function deleteJd(jdId: string): Promise<void> {
  await apiClient.delete(`/jds/${jdId}`)
}
