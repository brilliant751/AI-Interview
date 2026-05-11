"""API 请求与响应模型。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


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


class InterviewCreateRequest(BaseModel):
    """创建面试会话请求。"""

    resume_id: str = Field(min_length=6)
    job_role: Literal["java", "web"]
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    input_mode: Literal["text", "voice"] = "text"
    output_mode: Literal["text", "voice"] = "text"
    session_name: str = Field(default="", max_length=128)
    question_types: list[Literal["project", "technical", "scenario"]] = Field(
        default_factory=lambda: ["project", "technical", "scenario"]
    )
    jd_id: str = ""


class InterviewCreateResponse(BaseModel):
    """创建面试会话响应。"""

    interview_id: str
    current_stage: str
    first_question: str
    tts_audio_url: Optional[str] = None


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
    current_question: str = ""
    tts_audio_url: Optional[str] = None
    duration_seconds: int = 0
    duration_updated_at: Optional[str] = None


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
    error_message: Optional[str] = None


class HistoryItem(BaseModel):
    """历史记录条目。"""

    interview_id: str
    session_name: str = ""
    resume_id: str
    job_role: str
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


class MaterialImportTriggerResponse(BaseModel):
    """触发材料导入响应。"""

    task_id: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "PARTIAL_SUCCESS"]
    stage: str
    progress: int
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
    last_error: str = ""
    report_path: str = ""


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
