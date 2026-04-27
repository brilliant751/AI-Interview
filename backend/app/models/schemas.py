"""API 请求与响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ResumeUploadResponse(BaseModel):
    """简历上传响应。"""

    resume_id: str
    parse_status: Literal["PENDING", "READY"]


class InterviewCreateRequest(BaseModel):
    """创建面试会话请求。"""

    resume_id: str = Field(min_length=6)
    job_role: Literal["java", "web"]
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    input_mode: Literal["text", "voice"] = "text"
    output_mode: Literal["text", "voice"] = "text"


class InterviewCreateResponse(BaseModel):
    """创建面试会话响应。"""

    interview_id: str
    current_stage: str
    first_question: str


class InterviewTurnRequest(BaseModel):
    """提交轮次请求。"""

    stage: str
    answer_text: str = ""
    asr_text: str = ""


class InterviewTurnResponse(BaseModel):
    """提交轮次响应。"""

    interview_id: str
    stage: str
    next_question: str
    follow_up_count: int
    live_score: int
    output_mode: str
    tts_audio_url: str | None = None


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


class ReportResponse(BaseModel):
    """面试报告响应。"""

    interview_id: str
    status: Literal["GENERATING", "READY", "FAILED"]
    overall_score: int | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error_message: str | None = None


class HistoryItem(BaseModel):
    """历史记录条目。"""

    interview_id: str
    job_role: str
    overall_score: int | None = None
    created_at: str


class HistoryResponse(BaseModel):
    """历史记录列表响应。"""

    items: list[HistoryItem]
    total: int


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
