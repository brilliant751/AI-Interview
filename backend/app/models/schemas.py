"""API 请求与响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
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
    chunk_model: str = "qwen3.5-2b"
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
