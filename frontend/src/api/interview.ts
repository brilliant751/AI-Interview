import { apiClient } from './client'

/** 创建会话请求体。 */
export interface CreateInterviewPayload {
  resume_id: string
  job_role: 'java' | 'web'
  difficulty: 'easy' | 'medium' | 'hard'
  input_mode: 'text' | 'voice'
  output_mode: 'text' | 'voice'
}

/** 会话创建响应。 */
export interface CreateInterviewResponse {
  interview_id: string
  current_stage: string
  first_question: string
}

/** 轮次提交请求体。 */
export interface SubmitTurnPayload {
  stage: string
  answer_text: string
  asr_text?: string
  answer_audio_url?: string
  answer_audio_format?: string
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
  degrade_flags: string[]
  trace_id: string
  latency_ms: number
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

/** 报告响应。 */
export interface ReportResponse {
  interview_id: string
  status: 'GENERATING' | 'READY' | 'FAILED'
  overall_score?: number
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  error_message?: string
}

/** 历史记录响应。 */
export interface HistoryResponse {
  total: number
  items: Array<{
    interview_id: string
    job_role: string
    created_at: string
    overall_score?: number
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

/** 创建面试会话。 */
export async function createInterview(payload: CreateInterviewPayload): Promise<CreateInterviewResponse> {
  const { data } = await apiClient.post('/interviews', payload)
  return data
}

/** 提交面试轮次。 */
export async function submitTurn(
  interviewId: string,
  payload: SubmitTurnPayload,
): Promise<SubmitTurnResponse> {
  const { data } = await apiClient.post(`/interviews/${interviewId}/turns`, payload)
  return data
}

/** 结束面试并触发报告。 */
export async function finishInterview(interviewId: string): Promise<{ report_status: string }> {
  const { data } = await apiClient.post(`/interviews/${interviewId}/finish`)
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
export async function fetchHistory(params: { page: number; page_size: number; job_role?: string }) {
  const { data } = await apiClient.get<HistoryResponse>('/interviews/history', { params })
  return data
}
