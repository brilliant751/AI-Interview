import { apiClient } from './client'

// 面试 API 类型与后端 Pydantic Schema 对齐：
// 1. 创建会话、预约、轮次提交、报告播放都从这里统一导出。
// 2. 前端页面不要直接拼响应字段，优先复用这些 interface。
// 3. status/stage 等字符串枚举尽量在类型层收窄，减少页面条件判断拼写错误。
// 4. 语音模式字段可选，因为文本模式不会返回 tts_audio_url。
// 5. 预约相关字段保留日历链接，页面可以直接渲染 Google/Outlook 入口。

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
  scheduled_start_at?: string
  voice_tone_id?: string
}

/** 会话创建响应。 */
export interface CreateInterviewResponse {
  interview_id: string
  status: 'ACTIVE' | 'SCHEDULED'
  current_stage: string
  first_question: string
  scheduled_start_at?: string
  tts_audio_url?: string
  voice_tone_id?: string
  voice_tone_name?: string
}

/** 创建预约请求体。 */
export interface CreateInterviewSchedulePayload {
  title?: string
  scheduled_start_at: string
  duration_minutes: 20 | 45 | 60
  resume_id: string
  job_role?: 'java' | 'web'
  difficulty: 'easy' | 'medium' | 'hard'
  input_mode: 'text' | 'voice'
  output_mode: 'text' | 'voice'
  session_name?: string
  question_types?: Array<'project' | 'technical' | 'scenario'>
  jd_id?: string
  voice_tone_id?: string
}

/** 预约列表条目。 */
export interface InterviewScheduleListItem {
  schedule_id: string
  title: string
  status: 'scheduled' | 'ready' | 'in_progress' | 'completed' | 'missed' | 'cancelled'
  source_type: 'single' | 'plan'
  scheduled_start_at: string
  scheduled_end_at: string
  duration_minutes: number
  job_role: string
  difficulty: string
  resume_id: string
  jd_id?: string
  interview_id?: string
  resume_file_name?: string
  google_calendar_url: string
  outlook_calendar_url: string
  created_at: string
}

/** 预约列表响应。 */
export interface InterviewScheduleListResponse {
  items: InterviewScheduleListItem[]
  page: number
  page_size: number
  total: number
}

/** 预约创建响应。 */
export interface InterviewScheduleCreateResponse {
  schedule_id: string
  status: 'scheduled' | 'ready' | 'in_progress' | 'completed' | 'missed' | 'cancelled'
  source_type: 'single' | 'plan'
  title: string
  scheduled_start_at: string
  scheduled_end_at: string
  duration_minutes: number
  timezone: string
  interview_id?: string
  calendar_download_url: string
  google_calendar_url: string
  outlook_calendar_url: string
  created_at: string
}

/** 预约详情响应。 */
export interface InterviewScheduleDetailResponse {
  schedule_id: string
  status: 'scheduled' | 'ready' | 'in_progress' | 'completed' | 'missed' | 'cancelled'
  source_type: 'single' | 'plan'
  sequence_no?: number | null
  plan_id?: string | null
  title: string
  scheduled_start_at: string
  scheduled_end_at: string
  duration_minutes: number
  timezone: string
  resume_id: string
  resume_file_name?: string
  job_role: string
  jd_id?: string
  jd_title?: string
  difficulty: 'easy' | 'medium' | 'hard'
  input_mode: 'text' | 'voice'
  output_mode: 'text' | 'voice'
  session_name: string
  question_types: Array<'project' | 'technical' | 'scenario'>
  voice_tone_id?: string
  interview_id?: string
  calendar_download_url: string
  google_calendar_url: string
  outlook_calendar_url: string
  can_start: boolean
  can_cancel: boolean
  created_at: string
  updated_at: string
}

/** 预约开始响应。 */
export interface InterviewScheduleStartResponse {
  schedule_id: string
  status: 'in_progress'
  interview_id: string
  current_stage: string
  first_question: string
  tts_audio_url?: string
}

/** 语气配置条目。 */
export interface VoiceToneProfileItem {
  tone_id: string
  tone_name: string
  description: string
  base_instructions: string
  speed: number
}

/** 语气配置列表响应。 */
export interface VoiceToneProfileListResponse {
  items: VoiceToneProfileItem[]
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

/** 报告列表条目。 */
export interface ReportListItem {
  interview_id: string
  session_name?: string
  job_role: string
  difficulty: string
  status: 'GENERATING' | 'READY' | 'FAILED'
  overall_score?: number
  updated_at: string
  started_at: string
  finished_at?: string
}

/** 报告列表响应。 */
export interface ReportListResponse {
  items: ReportListItem[]
  total: number
  page: number
  page_size: number
}

/** 历史记录响应。 */
export interface HistoryResponse {
  total: number
  items: Array<{
    interview_id: string
    session_name?: string
    resume_id: string
    resume_file_name?: string
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
  scheduled_start_at?: string
  start_available: boolean
  current_question: string
  tts_audio_url?: string
  duration_seconds: number
  duration_updated_at?: string
}

/** 面试会话级预约条目。 */
export interface ScheduledInterviewItem {
  interview_id: string
  session_name?: string
  resume_id: string
  resume_file_name?: string
  job_role: 'java' | 'web' | string
  difficulty: 'easy' | 'medium' | 'hard' | string
  status: 'SCHEDULED' | 'ACTIVE' | 'PAUSED' | 'FINISHED' | string
  scheduled_start_at: string
  started_at?: string
  current_stage: string
  start_available: boolean
}

/** 面试会话级预约列表响应。 */
export interface ScheduledInterviewListResponse {
  items: ScheduledInterviewItem[]
}

/** 开始已预约面试会话响应。 */
export interface StartScheduledInterviewResponse {
  interview_id: string
  status: 'ACTIVE'
  stage: string
  question: string
  job_role: 'java' | 'web'
  difficulty: 'easy' | 'medium' | 'hard'
  input_mode: 'text' | 'voice'
  output_mode: 'text' | 'voice'
  scheduled_start_at?: string
  tts_audio_url?: string
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
  // 简历上传必须走 multipart/form-data。
  // apiClient 仍会自动追加鉴权和幂等头，后端据此避免重复上传记录。
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post('/resumes', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 查询简历列表。 */
export async function fetchResumes(params: { page: number; page_size: number }): Promise<ResumeListResponse> {
  // 简历列表用于管理页、准备页和面试页弹窗。
  // 分页参数由页面决定，API 层只保持后端字段命名。
  const { data } = await apiClient.get<ResumeListResponse>('/resumes', { params })
  return data
}

/** 删除简历。 */
export async function deleteResume(resumeId: string): Promise<void> {
  await apiClient.delete(`/resumes/${resumeId}`)
}

/** 获取简历原始文件（二进制）。 */
export async function fetchResumeFile(resumeId: string): Promise<Blob> {
  // 预览 PDF/DOC 文件时需要 Blob，不能按 JSON 解析响应。
  // 调用方负责创建和释放 object URL。
  const { data } = await apiClient.get(`/resumes/${resumeId}/file`, { responseType: 'blob' })
  return data as Blob
}

/** 创建面试会话。 */
export async function createInterview(payload: CreateInterviewPayload): Promise<CreateInterviewResponse> {
  // 同一个接口既支持立即面试，也支持带 scheduled_start_at 的预约会话。
  // 页面必须根据 response.status 决定跳转面试页还是提示预约成功。
  const { data } = await apiClient.post('/interviews', payload)
  return data
}

/** 创建单次面试预约。 */
export async function createInterviewSchedule(
  payload: CreateInterviewSchedulePayload,
): Promise<InterviewScheduleCreateResponse> {
  const { data } = await apiClient.post('/interview-schedules', payload)
  return data
}

/** 查询预约列表。 */
export async function fetchInterviewSchedules(params: {
  page: number
  page_size: number
  status?: string
  date_from?: string
  date_to?: string
}): Promise<InterviewScheduleListResponse> {
  // 这是预约管理页使用的 schedule 维度接口。
  // date_from/date_to/status 用于筛选日历范围和列表状态。
  const { data } = await apiClient.get<InterviewScheduleListResponse>('/interview-schedules', { params })
  return data
}

/** 查询预约详情。 */
export async function fetchInterviewScheduleDetail(scheduleId: string): Promise<InterviewScheduleDetailResponse> {
  const { data } = await apiClient.get<InterviewScheduleDetailResponse>(`/interview-schedules/${scheduleId}`)
  return data
}

/** 取消预约。 */
export async function cancelInterviewSchedule(scheduleId: string, reason = ''): Promise<{ schedule_id: string; status: string; cancelled_at: string }> {
  const { data } = await apiClient.post(`/interview-schedules/${scheduleId}/cancel`, { reason })
  return data
}

/** 开始预约面试。 */
export async function startInterviewSchedule(scheduleId: string): Promise<InterviewScheduleStartResponse> {
  // schedule 维度的 start 会把预约状态推进为 in_progress，并返回面试会话信息。
  // 成功后页面需要把 first_question 同步进 interviewStore。
  const { data } = await apiClient.post<InterviewScheduleStartResponse>(`/interview-schedules/${scheduleId}/start`)
  return data
}

/** 下载预约日历文件。 */
export async function downloadInterviewScheduleCalendar(scheduleId: string): Promise<Blob> {
  const { data } = await apiClient.get(`/interview-schedules/${scheduleId}/calendar.ics`, { responseType: 'blob' })
  return data as Blob
}

/** 查询可选语气配置。 */
export async function fetchVoiceToneProfiles(): Promise<VoiceToneProfileListResponse> {
  const { data } = await apiClient.get<VoiceToneProfileListResponse>('/interviews/voice-tones')
  return data
}

/** 提交面试轮次。 */
export async function submitTurn(
  interviewId: string,
  payload: SubmitTurnPayload,
): Promise<SubmitTurnJobResponse> {
  // 文本提交不会直接返回下一题，而是返回异步 job。
  // 前端通过 fetchTurnJobResult 轮询，避免 LLM/TTS 处理期间阻塞 UI。
  const { data } = await apiClient.post(`/interviews/${interviewId}/turns`, payload)
  return data
}

/** 提交音频轮次。 */
export async function submitAudioTurn(
  interviewId: string,
  payload: SubmitAudioTurnPayload,
): Promise<SubmitTurnJobResponse> {
  // 音频提交同样返回 job_id。
  // stage 放在 form 字段中，file 放二进制，后端会进行 ASR 后复用轮次处理逻辑。
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
  // PROCESSING 状态下 result 为 null，READY 时才包含 SubmitTurnResponse。
  // interviewId 放在路径中，后端会校验 job 是否属于该会话。
  const { data } = await apiClient.get(`/interviews/${interviewId}/turn-jobs/${jobId}`)
  return data
}

/** 结束面试并触发报告。 */
export async function finishInterview(interviewId: string): Promise<{ report_status: string }> {
  // finish 可能触发报告生成和数据库状态写入，超时时间略长于普通请求。
  // 返回后报告仍可能处于 GENERATING，页面需要跳转报告页继续查询。
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
  // 报告接口会返回 GENERATING/READY/FAILED 三种状态。
  // READY 前各结构化数组可能为空，页面应按 status 分支渲染。
  const { data } = await apiClient.get(`/report/${interviewId}`)
  return data
}

/** 查询我的报告列表。 */
export async function fetchReportList(params: {
  page: number
  page_size: number
  status?: 'GENERATING' | 'READY' | 'FAILED'
}): Promise<ReportListResponse> {
  const { data } = await apiClient.get<ReportListResponse>('/report', { params })
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
  // 状态接口用于恢复会话、轮询阶段和获取累计时长。
  // params.status 兼容“恢复暂停会话”场景，由后端决定是否推进状态。
  const { data } = await apiClient.get<InterviewStatusResponse>(`/interviews/${interviewId}/status`, { params })
  return data
}

/** 查询面试回放详情。 */
export async function fetchInterviewPlayback(interviewId: string): Promise<InterviewPlaybackResponse> {
  const { data } = await apiClient.get<InterviewPlaybackResponse>(`/interviews/${interviewId}/playback`)
  return data
}

/** 查询面试会话级预约列表。 */
export async function fetchScheduledInterviews(params: {
  scheduled_from?: string
  scheduled_to?: string
  statuses?: string[]
}): Promise<ScheduledInterviewListResponse> {
  // 这是 interview session 维度的预约列表，供面试大厅和顶部提醒使用。
  // statuses 数组按逗号拼接，保持 URL 查询参数简洁。
  const { data } = await apiClient.get<ScheduledInterviewListResponse>('/interviews/schedules', {
    params: {
      scheduled_from: params.scheduled_from,
      scheduled_to: params.scheduled_to,
      statuses: params.statuses?.join(','),
    },
  })
  return data
}

/** 开始预约面试。 */
export async function startScheduledInterview(interviewId: string): Promise<StartScheduledInterviewResponse> {
  const { data } = await apiClient.post<StartScheduledInterviewResponse>(`/interviews/${interviewId}/start`)
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
  // JD 支持文件上传和纯文本录入，两种方式统一走 FormData。
  // title、content_text、company_id 都是可选字段，后端负责最终归一化。
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
