"""API 请求与响应模型。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class ResumeUploadResponse(BaseModel):
    """简历上传响应。"""

    resume_id: str
    parse_status: Literal["PENDING", "READY", "FAILED"]


class ResumeListItem(BaseModel):
    """简历列表条目。"""

    resume_id: str
    file_name: str
    parse_status: str
    created_at: str
    last_used_at: Optional[str] = None


class ResumeListResponse(BaseModel):
    """简历列表响应。"""

    items: list[ResumeListItem] = Field(default_factory=list)
    page: int
    page_size: int
    total: int


class InterviewScheduleCreateRequest(BaseModel):
    """创建单次面试预约请求。"""

    title: str = Field(default="", max_length=128)
    scheduled_start_at: str = Field(min_length=16, max_length=64)
    duration_minutes: Literal[20, 45, 60]
    resume_id: str = Field(min_length=6)
    job_role: Optional[Literal["java", "web"]] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    input_mode: Literal["text", "voice"] = "text"
    output_mode: Literal["text", "voice"] = "text"
    session_name: str = Field(default="", max_length=128)
    question_types: list[Literal["project", "technical", "scenario"]] = Field(
        default_factory=lambda: ["project", "technical", "scenario"]
    )
    jd_id: str = ""
    voice_tone_id: str = ""

    @model_validator(mode="after")
    def validate_role_or_jd(self) -> "InterviewScheduleCreateRequest":
        """校验岗位方向与岗位描述至少提供一个。"""
        if self.job_role is None and not (self.jd_id or "").strip():
            raise ValueError("job_role 与 jd_id 至少提供一个")
        return self


class InterviewScheduleListItem(BaseModel):
    """面试预约列表条目。"""

    schedule_id: str
    title: str = ""
    status: Literal["scheduled", "ready", "in_progress", "completed", "missed", "cancelled"]
    source_type: Literal["single", "plan"] = "single"
    scheduled_start_at: str
    scheduled_end_at: str
    duration_minutes: int
    job_role: str = ""
    difficulty: str = "medium"
    resume_id: str
    jd_id: str = ""
    interview_id: str = ""
    resume_file_name: str = ""
    google_calendar_url: str = ""
    outlook_calendar_url: str = ""
    created_at: str


class InterviewScheduleListResponse(BaseModel):
    """面试预约列表响应。"""

    items: list[InterviewScheduleListItem] = Field(default_factory=list)
    page: int
    page_size: int
    total: int


class InterviewScheduleCreateResponse(BaseModel):
    """创建单次面试预约响应。"""

    schedule_id: str
    status: Literal["scheduled", "ready", "in_progress", "completed", "missed", "cancelled"]
    source_type: Literal["single", "plan"] = "single"
    title: str = ""
    scheduled_start_at: str
    scheduled_end_at: str
    duration_minutes: int
    timezone: str = "Asia/Shanghai"
    interview_id: str = ""
    calendar_download_url: str
    google_calendar_url: str
    outlook_calendar_url: str
    created_at: str


class InterviewScheduleDetailResponse(BaseModel):
    """面试预约详情响应。"""

    schedule_id: str
    status: Literal["scheduled", "ready", "in_progress", "completed", "missed", "cancelled"]
    source_type: Literal["single", "plan"] = "single"
    sequence_no: Optional[int] = None
    plan_id: Optional[str] = None
    title: str = ""
    scheduled_start_at: str
    scheduled_end_at: str
    duration_minutes: int
    timezone: str = "Asia/Shanghai"
    resume_id: str
    resume_file_name: str = ""
    job_role: str = ""
    jd_id: str = ""
    jd_title: str = ""
    difficulty: str = "medium"
    input_mode: str = "text"
    output_mode: str = "text"
    session_name: str = ""
    question_types: list[str] = Field(default_factory=list)
    voice_tone_id: str = ""
    interview_id: str = ""
    calendar_download_url: str
    google_calendar_url: str
    outlook_calendar_url: str
    can_start: bool = False
    can_cancel: bool = False
    created_at: str
    updated_at: str


class InterviewScheduleCancelRequest(BaseModel):
    """取消预约请求。"""

    reason: str = Field(default="", max_length=200)


class InterviewScheduleCancelResponse(BaseModel):
    """取消预约响应。"""

    schedule_id: str
    status: Literal["cancelled"]
    cancelled_at: str


class InterviewScheduleStartResponse(BaseModel):
    """开始预约面试响应。"""

    schedule_id: str
    status: Literal["in_progress"]
    interview_id: str
    current_stage: str
    first_question: str
    tts_audio_url: Optional[str] = None


class InterviewCreateRequest(BaseModel):
    """创建面试会话请求。"""

    resume_id: str = Field(min_length=6)
    job_role: Optional[Literal["java", "web"]] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    input_mode: Literal["text", "voice"] = "text"
    output_mode: Literal["text", "voice"] = "text"
    session_name: str = Field(default="", max_length=128)
    question_types: list[Literal["project", "technical", "scenario"]] = Field(
        default_factory=lambda: ["project", "technical", "scenario"]
    )
    jd_id: str = ""
    scheduled_start_at: str = ""
    voice_tone_id: str = ""

    @model_validator(mode="after")
    def validate_role_or_jd(self) -> "InterviewCreateRequest":
        """校验岗位方向与岗位描述至少提供一个。"""
        if self.job_role is None and not (self.jd_id or "").strip():
            raise ValueError("job_role 与 jd_id 至少提供一个")
        return self


class InterviewCreateResponse(BaseModel):
    """创建面试会话响应。"""

    interview_id: str
    status: str = "ACTIVE"
    current_stage: str
    first_question: str
    scheduled_start_at: Optional[str] = None
    tts_audio_url: Optional[str] = None
    voice_tone_id: str = ""
    voice_tone_name: str = ""


class VoiceToneProfileItem(BaseModel):
    """语气配置条目。"""

    tone_id: str
    tone_name: str
    description: str = ""
    base_instructions: str = ""
    speed: float = 1.0


class VoiceToneProfileListResponse(BaseModel):
    """语气配置列表响应。"""

    items: list[VoiceToneProfileItem] = Field(default_factory=list)


class InterviewTurnRequest(BaseModel):
    """提交轮次请求。"""

    stage: Literal["SELF_INTRO", "PROJECT_DEEP_DIVE", "TECHNICAL", "BEHAVIORAL", "END"]
    answer_text: str = ""
    asr_text: str = ""
    answer_audio_url: str = ""
    answer_audio_format: str = "mp3"


class PipelineProviders(BaseModel):
    """链路 provider 信息。"""

    asr: Optional[str] = None
    llm: Optional[str] = None
    tts: Optional[str] = None


class PipelineProviderStatus(BaseModel):
    """链路 provider 状态。"""

    asr: str = "UNKNOWN"
    llm: str = "UNKNOWN"
    tts: str = "UNKNOWN"


class PipelineMeta(BaseModel):
    """链路元数据。"""

    input_source: str
    providers: PipelineProviders
    provider_status: PipelineProviderStatus = Field(default_factory=PipelineProviderStatus)
    degrade_flags: list[str] = Field(default_factory=list)
    trace_id: str
    latency_ms: int = 0
    generation_mode: Literal["local_ai", "fallback_template", "mock"] = "mock"


class InterviewTurnResponse(BaseModel):
    """提交轮次响应。"""

    interview_id: str
    stage: str
    next_question: str
    follow_up_count: int
    live_score: int
    output_mode: str
    tts_audio_url: Optional[str] = None
    pipeline_meta: Optional[PipelineMeta] = None


class InterviewTurnJobResponse(BaseModel):
    """轮次异步任务响应。"""

    interview_id: str
    job_id: str
    status: Literal["PROCESSING"]


class InterviewTurnJobResultResponse(BaseModel):
    """轮次异步任务结果响应。"""

    interview_id: str
    job_id: str
    status: Literal["PROCESSING", "READY", "FAILED"]
    result: Optional[InterviewTurnResponse] = None
    error_message: str = ""


class InterviewTurnItemResponse(BaseModel):
    """单轮面试记录响应。"""

    turn_id: str
    interview_id: str
    stage: str
    answer_text: str
    next_question: str
    live_score: int
    generation_mode: str
    input_source: Optional[str] = None
    asr_provider: Optional[str] = None
    llm_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    degrade_flags: list[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
    latency_ms: int = 0
    created_at: str


class InterviewTurnsResponse(BaseModel):
    """面试轮次列表响应。"""

    interview_id: str
    items: list[InterviewTurnItemResponse] = Field(default_factory=list)


class InterviewFinishResponse(BaseModel):
    """结束面试响应。"""

    interview_id: str
    report_status: Literal["GENERATING"]


class InterviewStatusResponse(BaseModel):
    """会话状态响应。"""

    interview_id: str
    status: str
    current_stage: str
    follow_up_count: int
    technical_count: int
    job_role: str = "java"
    difficulty: str = "medium"
    input_mode: str = "text"
    output_mode: str = "text"
    jd_id: str = ""
    jd_title: str = ""
    jd_source_type: str = ""
    scheduled_start_at: Optional[str] = None
    start_available: bool = False
    current_question: str = ""
    tts_audio_url: Optional[str] = None
    duration_seconds: int = 0
    duration_updated_at: Optional[str] = None


class InterviewScheduleItemResponse(BaseModel):
    """预约面试条目响应。"""

    interview_id: str
    session_name: str = ""
    resume_id: str = ""
    resume_file_name: str = ""
    job_role: str
    difficulty: str
    status: str
    scheduled_start_at: str
    started_at: Optional[str] = None
    current_stage: str = "SELF_INTRO"
    start_available: bool = False


class InterviewScheduleListResponse(BaseModel):
    """预约面试列表响应。"""

    items: list[InterviewScheduleItemResponse] = Field(default_factory=list)


class InterviewStartResponse(BaseModel):
    """开始预约面试响应。"""

    interview_id: str
    status: str
    stage: str
    question: str
    job_role: str
    difficulty: str
    input_mode: str
    output_mode: str
    scheduled_start_at: Optional[str] = None
    tts_audio_url: Optional[str] = None


class PausedInterviewItemResponse(BaseModel):
    """暂停中的面试条目。"""

    interview_id: str
    session_name: str = ""
    job_role: str
    difficulty: str
    current_stage: str
    follow_up_count: int = 0
    technical_count: int = 0
    input_mode: str
    output_mode: str
    started_at: str
    updated_at: Optional[str] = None
    resume_file_name: str = ""


class PausedInterviewListResponse(BaseModel):
    """暂停面试列表响应。"""

    items: list[PausedInterviewItemResponse] = Field(default_factory=list)


class ResumeInterviewResponse(BaseModel):
    """恢复暂停面试响应。"""

    interview_id: str
    stage: str
    question: str
    job_role: str
    difficulty: str
    input_mode: str
    output_mode: str
    tts_audio_url: Optional[str] = None


class ReportResponse(BaseModel):
    """面试报告响应。"""

    interview_id: str
    status: Literal["GENERATING", "READY", "FAILED"]
    overall_score: Optional[int] = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    dimension_scores: list[dict] = Field(default_factory=list)
    jd_resume_alignment: list[dict] = Field(default_factory=list)
    question_deep_dives: list[dict] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    final_recommendation: str = ""
    error_message: Optional[str] = None


class ReportListItem(BaseModel):
    """报告列表条目。"""

    interview_id: str
    session_name: str = ""
    job_role: str
    difficulty: str = "medium"
    status: str
    overall_score: Optional[int] = None
    updated_at: str
    started_at: str
    finished_at: Optional[str] = None


class ReportListResponse(BaseModel):
    """报告列表响应。"""

    items: list[ReportListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class HistoryItem(BaseModel):
    """历史记录条目。"""

    interview_id: str
    session_name: str = ""
    resume_id: str
    resume_file_name: str = ""
    job_role: str
    difficulty: str = "medium"
    status: str
    jd_id: str = ""
    jd_title: str = ""
    jd_source_type: str = ""
    started_at: str
    finished_at: Optional[str] = None
    turn_count: int = 0
    overall_score: Optional[int] = None
    created_at: str
    duration_seconds: int = 0
    duration_updated_at: Optional[str] = None


class HistoryResponse(BaseModel):
    """历史记录列表响应。"""

    items: list[HistoryItem]
    total: int


class InterviewPlaybackResume(BaseModel):
    """回放中的简历信息。"""

    resume_id: str
    file_name: str


class InterviewPlaybackMeta(BaseModel):
    """回放中的会话元数据。"""

    job_role: str
    difficulty: str
    status: str
    jd_id: str = ""
    jd_title: str = ""
    jd_source_type: str = ""
    started_at: str
    finished_at: Optional[str] = None
    duration_seconds: int = 0
    duration_updated_at: Optional[str] = None


class InterviewPlaybackTurn(BaseModel):
    """回放中的单轮问答。"""

    turn_id: str
    sequence: int
    question: str
    answer: str
    question_ts: str
    answer_ts: Optional[str] = None


class InterviewPlaybackResponse(BaseModel):
    """面试回放详情响应。"""

    interview_id: str
    resume: InterviewPlaybackResume
    meta: InterviewPlaybackMeta
    turns: list[InterviewPlaybackTurn] = Field(default_factory=list)


class JobDescriptionUploadResponse(BaseModel):
    """JD 上传响应。"""

    jd_id: str
    source_type: str
    company_id: str = ""
    company_name: str = ""
    title: str
    job_role: str
    status: str
    created_at: str


class JobDescriptionListItem(BaseModel):
    """JD 列表条目。"""

    jd_id: str
    source_type: str
    company_id: str = ""
    company_name: str = ""
    title: str
    job_role: str
    status: str
    content_text: str = ""
    created_at: str
    updated_at: str


class JobDescriptionListResponse(BaseModel):
    """JD 列表响应。"""

    items: list[JobDescriptionListItem] = Field(default_factory=list)


class CompanyListItem(BaseModel):
    """公司列表条目。"""

    company_id: str
    name: str
    status: str
    created_at: str
    updated_at: str


class CompanyListResponse(BaseModel):
    """公司列表响应。"""

    items: list[CompanyListItem] = Field(default_factory=list)


class MaterialImportRequest(BaseModel):
    """触发材料导入请求。"""

    rebuild_mode: Literal["full", "incremental"] = "full"
    roles: list[Literal["java", "web"]] = Field(default_factory=lambda: ["java", "web"])
    dry_run: bool = False
    chunk_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"
    task_type: Literal["full_pipeline", "question_bank"] = "full_pipeline"


class MaterialImportTriggerResponse(BaseModel):
    """触发材料导入响应。"""

    task_id: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "PARTIAL_SUCCESS"]
    stage: str
    progress: int
    task_type: Literal["full_pipeline", "question_bank"] = "full_pipeline"
    idempotency_hit: bool = False


class MaterialImportTaskResponse(BaseModel):
    """材料导入任务状态响应。"""

    task_id: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "PARTIAL_SUCCESS"]
    stage: str
    progress: int
    rebuild_mode: Literal["full", "incremental"]
    roles: list[Literal["java", "web"]]
    dry_run: bool
    task_type: Literal["full_pipeline", "question_bank"] = "full_pipeline"
    last_error: str = ""
    report_path: str = ""


class AdminQuestionBankItemResponse(BaseModel):
    """管理端题库条目响应。"""

    record_id: str
    job_role: str
    question_no: int
    title: str
    category: Optional[str] = None
    question: str
    analysis: Optional[str] = None
    source_path: str
    updated_at: str


class AdminQuestionBankListResponse(BaseModel):
    """管理端题库分页列表响应。"""

    items: list[AdminQuestionBankItemResponse] = Field(default_factory=list)
    page: int
    page_size: int
    total: int


class AdminQuestionBankUploadRequest(BaseModel):
    """管理端题库 Markdown 上传请求。"""

    job_role: Literal["java", "web"]
    file_name: str = Field(min_length=3, max_length=255)
    markdown: str = Field(min_length=1, max_length=200000)


class AdminQuestionBankCreateRequest(BaseModel):
    """管理端单题录入请求。"""

    job_role: Literal["java", "web"]
    category: Literal["technical", "project", "scenario", "behavior"]
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=10000)
    analysis: str = Field(min_length=1, max_length=20000)
    source_note: str = Field(default="", max_length=200)


class PracticeQuestionResponse(BaseModel):
    """练习题目快照响应。"""

    session_question_id: str
    question_order: int
    source_question_id: Optional[str] = None
    category: Optional[str] = None
    stem: str
    options: list[dict[str, str]] = Field(default_factory=list)
    analysis: Optional[str] = None


class PracticeCreateRequest(BaseModel):
    """创建题库练习会话请求。"""

    job_role: Literal["java", "web"]
    mode: Literal["sequence", "followup"] = "sequence"
    question_count: int = Field(ge=1, le=50)
    category_filters: list[Literal["technical", "project", "scenario", "behavior"]] = Field(default_factory=list)


class PracticeSessionResponse(BaseModel):
    """题库练习会话状态响应。"""

    practice_id: str
    job_role: str
    mode: str
    status: Literal["ACTIVE", "FINISHED"]
    total_questions: int
    completed_count: int
    finished: bool
    question_strategy: Literal["sequence", "followup_placeholder"]
    current_question: Optional[PracticeQuestionResponse] = None
    created_at: Optional[str] = None


class PracticeAnswerRequest(BaseModel):
    """提交题库练习答案请求。"""

    session_question_id: str = Field(min_length=6)
    answer_text: str = Field(min_length=1, max_length=20000)


class PracticeAnswerResponse(BaseModel):
    """提交题库练习答案响应。"""

    practice_id: str
    status: Literal["ACTIVE", "FINISHED"]
    completed_count: int
    finished: bool
    question_strategy: Literal["sequence", "followup_placeholder"]
    next_question: Optional[PracticeQuestionResponse] = None


class PracticeRecordItemResponse(BaseModel):
    """题库练习记录条目响应。"""

    practice_id: str
    job_role: str
    mode: str
    status: str
    total_questions: int
    answered_count: int
    created_at: str


class PracticeRecordsResponse(BaseModel):
    """题库练习记录列表响应。"""

    items: list[PracticeRecordItemResponse] = Field(default_factory=list)
    total: int


class PracticeOverviewRoleStatsResponse(BaseModel):
    """题库练习页岗位统计响应。"""

    job_role: Literal["java", "web"]
    total_questions: int
    active_sessions: int = 0
    finished_sessions: int = 0
    answered_questions: int = 0
    completion_rate: float = 0
    latest_active_practice_id: Optional[str] = None


class PracticeOverviewRecentRecordResponse(BaseModel):
    """题库练习页最近记录响应。"""

    practice_id: str
    job_role: Literal["java", "web"]
    mode: str
    status: str
    total_questions: int
    answered_count: int
    created_at: str


class PracticeOverviewResponse(BaseModel):
    """题库练习页概览响应。"""

    total_questions: int
    total_answered_questions: int
    total_sessions: int
    active_sessions: int
    role_stats: list[PracticeOverviewRoleStatsResponse] = Field(default_factory=list)
    recent_records: list[PracticeOverviewRecentRecordResponse] = Field(default_factory=list)


class PracticeSessionRecordQuestionResponse(BaseModel):
    """题库练习记录中的单题详情。"""

    session_question_id: str
    question_order: int
    category: Optional[str] = None
    stem: str
    analysis: Optional[str] = None
    answer_text: Optional[str] = None
    answered_at: Optional[str] = None


class PracticeSessionRecordsResponse(BaseModel):
    """单场题库练习记录明细响应。"""

    practice_id: str
    job_role: str
    mode: str
    status: str
    total_questions: int
    completed_count: int
    items: list[PracticeSessionRecordQuestionResponse] = Field(default_factory=list)
    created_at: Optional[str] = None
    finished_at: Optional[str] = None


class CodingPracticeQuestionSummaryResponse(BaseModel):
    """编程题列表项响应。"""

    question_id: str
    slug: str
    title: str
    difficulty: Literal["easy", "medium", "hard"]
    topic_tags: list[str] = Field(default_factory=list)
    status: Literal["NOT_STARTED", "ACTIVE", "SOLVED"]
    last_language: Literal["cpp", "java", "javascript"] = "cpp"
    latest_submission_status: Optional[str] = None
    session_id: Optional[str] = None
    updated_at: Optional[str] = None


class CodingPracticeQuestionDetailResponse(BaseModel):
    """编程题详情响应。"""

    question_id: str
    slug: str
    title: str
    difficulty: Literal["easy", "medium", "hard"]
    topic_tags: list[str] = Field(default_factory=list)
    prompt_markdown: str
    input_spec: str
    output_spec: str
    constraints_text: str = ""
    sample_cases: list[dict[str, str]] = Field(default_factory=list)
    self_test_case: dict[str, str] = Field(default_factory=dict)


class CodingPracticeQuestionListResponse(BaseModel):
    """编程题列表响应。"""

    items: list[CodingPracticeQuestionSummaryResponse] = Field(default_factory=list)
    total: int


class CodingPracticeCreateSessionRequest(BaseModel):
    """创建编程练习会话请求。"""

    question_id: str = Field(min_length=3)


class CodingPracticeSessionResponse(BaseModel):
    """编程练习会话响应。"""

    session_id: str
    question: CodingPracticeQuestionDetailResponse
    status: Literal["ACTIVE", "SOLVED"]
    active_language: Literal["cpp", "java", "javascript"]
    last_opened_at: Optional[str] = None
    created_at: Optional[str] = None


class CodingPracticeRunRequest(BaseModel):
    """运行自测请求。"""

    language: Literal["cpp", "java", "javascript"]
    source_code: str = Field(default="", max_length=200000)


class CodingPracticeExecutionResultResponse(BaseModel):
    """运行或提交结果响应。"""

    status: str
    passed_count: int
    total_count: int
    submit_type: Literal["RUN", "SUBMIT"]
    message: str
    results: list[dict] = Field(default_factory=list)
    compile_output: Optional[str] = None


class CodingPracticeExecutionResponse(BaseModel):
    """运行或提交接口响应。"""

    session_id: str
    submission_id: str
    result: CodingPracticeExecutionResultResponse


class CodingPracticeRecordItemResponse(BaseModel):
    """编程练习记录项。"""

    session_id: str
    question_id: str
    title: str
    difficulty: Literal["easy", "medium", "hard"]
    status: Literal["ACTIVE", "SOLVED"]
    last_language: Literal["cpp", "java", "javascript"]
    latest_submission_status: Optional[str] = None
    last_opened_at: Optional[str] = None
    created_at: Optional[str] = None


class CodingPracticeRecordsResponse(BaseModel):
    """编程练习记录列表响应。"""

    items: list[CodingPracticeRecordItemResponse] = Field(default_factory=list)
    total: int


class RegisterRequest(BaseModel):
    """注册请求。"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenRefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    """登出请求。"""

    refresh_token: str = Field(min_length=20)


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求。"""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""

    reset_token: str = Field(min_length=20)
    new_password: str = Field(min_length=8, max_length=128)


class AuthUserProfile(BaseModel):
    """认证用户信息。"""

    user_id: str
    email: EmailStr
    display_name: str
    role: Literal["user", "admin"]
    status: Literal["active", "disabled"]


class AuthTokenResponse(BaseModel):
    """认证令牌响应。"""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    refresh_token: str
    user: AuthUserProfile


class RegisterResponse(BaseModel):
    """注册响应。"""

    user: AuthUserProfile


class ForgotPasswordResponse(BaseModel):
    """忘记密码响应。"""

    accepted: bool = True
    message: str = "如邮箱存在，我们已发送重置邮件"


class AuthMeResponse(BaseModel):
    """当前登录用户响应。"""

    user: AuthUserProfile


class ProviderHealthItem(BaseModel):
    """单个 provider 健康状态（基于 SDK 初始化与最小调用）。"""

    status: Literal["UP", "DOWN", "DEGRADED"]
    provider: str
    model: str
    latency_ms: int = 0
    error_message: str = ""


class ProviderHealthResponse(BaseModel):
    """provider 健康检查响应（非 URL 可达性检查）。"""

    overall: Literal["UP", "DOWN", "DEGRADED"]
    providers: dict[str, ProviderHealthItem]
