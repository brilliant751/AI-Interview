"""题库管理服务。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.core.errors import ApiError
from app.models.schemas import MaterialImportRequest, MaterialImportTriggerResponse
from app.repositories.interview_repository import InterviewRepository
from app.services.material_import_service import MaterialImportService

_CATEGORY_LABELS = {
    "technical": "技术",
    "project": "项目",
    "scenario": "场景",
    "behavior": "行为",
}
_ALLOWED_CATEGORY_VALUES = {
    "技术": "technical",
    "项目": "project",
    "场景": "scenario",
    "行为": "behavior",
    "technical": "technical",
    "project": "project",
    "scenario": "scenario",
    "behavior": "behavior",
    "behavioral": "behavior",
}
_QUESTION_HEADING_PATTERN = re.compile(r"^#{2,3}\s*第\s*(\d+)\s*题[：:]\s*(.+?)\s*$", re.MULTILINE)
_JAVA_BLOCK_PATTERN = re.compile(r"^##\s*第\s*\d+\s*题[：:]\s*.+?\s*$([\s\S]*?)(?=^##\s*第\s*\d+\s*题[：:]|\Z)", re.MULTILINE)
_WEB_BLOCK_PATTERN = re.compile(r"^###\s*第\s*\d+\s*题[：:]\s*.+?\s*$([\s\S]*?)(?=^###\s*第\s*\d+\s*题[：:]|\Z)", re.MULTILINE)
_JAVA_SECTION_PATTERN = re.compile(
    r"^###\s*题干\s*$\s*([\s\S]*?)^###\s*类别\s*$\s*([\s\S]*?)^###\s*解析\s*$\s*([\s\S]*?)(?=^###\s+\S+|\Z)",
    re.MULTILINE,
)
_WEB_SECTION_PATTERN = re.compile(
    r"^####\s*题干\s*$\s*([\s\S]*?)^####\s*类别\s*$\s*([\s\S]*?)^####\s*解析\s*$\s*([\s\S]*?)(?=^####\s+\S+|\Z)",
    re.MULTILINE,
)


class QuestionBankService:
    """负责题库查询、Markdown 落盘与导入任务触发。"""

    def __init__(
        self,
        repo: InterviewRepository,
        import_service: MaterialImportService,
        repo_root: Path,
        material_root: Path | None = None,
    ) -> None:
        """初始化服务依赖与素材根目录。"""
        self.repo = repo
        self.import_service = import_service
        self.repo_root = repo_root
        self.material_root = material_root or repo_root / "backend" / "assets" / "material"

    def list_questions(
        self,
        job_role: str,
        category: str | None,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        """分页查询题库条目。"""
        items, total = self.repo.list_admin_question_bank_items(
            job_role=job_role,
            category=category,
            keyword=keyword,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [
                {
                    "record_id": str(item["question_id"]),
                    "job_role": str(item["domain"]),
                    "question_no": 0,
                    "title": str(item["stem"])[:80],
                    "category": "single_choice",
                    "question": str(item["stem"]),
                    "analysis": item["explanation"],
                    "source_path": str(item["metadata"].get("source_key", "")),
                    "updated_at": str(item["updated_at"]),
                }
                for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    async def upload_markdown(self, job_role: str, file_name: str, markdown: str) -> MaterialImportTriggerResponse:
        """保存 Markdown 题库材料并触发题库导入任务。"""
        normalized_name = self._validate_markdown_file_name(file_name)
        self._validate_markdown_content(job_role=job_role, markdown=markdown)
        target_path = self._resolve_target_path(job_role=job_role, file_name=normalized_name)
        self._write_markdown(target_path, markdown)
        return await self._trigger_question_bank_import(job_role=job_role, idempotency_key=f"upload:{job_role}:{normalized_name}")

    async def create_question(
        self,
        job_role: str,
        category: str,
        title: str,
        question: str,
        analysis: str,
        source_note: str,
    ) -> MaterialImportTriggerResponse:
        """生成单题 Markdown 并触发题库导入任务。"""
        target_path = self._resolve_target_path(
            job_role=job_role,
            file_name=self._build_generated_file_name(),
        )
        question_no = self._next_question_no(target_path=target_path, job_role=job_role)
        markdown = self._render_single_question_markdown(
            job_role=job_role,
            question_no=question_no,
            title=title.strip(),
            category=category,
            question=question.strip(),
            analysis=analysis.strip(),
            source_note=source_note.strip(),
        )
        self._write_markdown(target_path, markdown, append=job_role == "web")
        target_name = target_path.name
        return await self._trigger_question_bank_import(job_role=job_role, idempotency_key=f"single:{job_role}:{target_name}")

    def _validate_markdown_file_name(self, file_name: str) -> str:
        """校验上传文件名合法且扩展名为 Markdown。"""
        normalized_name = Path(file_name).name.strip()
        if not normalized_name or normalized_name != file_name.strip():
            raise ApiError(code="QUESTION_BANK_400", message="文件名不合法，仅允许上传到题库材料目录", status_code=400)
        if Path(normalized_name).suffix.lower() != ".md":
            raise ApiError(code="QUESTION_BANK_400", message="仅支持上传 .md 格式的题库文件", status_code=400)
        return normalized_name

    def _validate_markdown_content(self, job_role: str, markdown: str) -> None:
        """校验 Markdown 是否满足题库最小结构要求。"""
        content = markdown.strip()
        blocks = self._split_question_blocks(job_role=job_role, content=content)
        if not blocks:
            raise ApiError(code="QUESTION_BANK_400", message="Markdown 内容不符合题库格式要求", status_code=400)
        for block in blocks:
            raw_category = self._validate_question_block(job_role=job_role, block=block)
            if self._normalize_category_value(raw_category) is None:
                raise ApiError(code="QUESTION_BANK_400", message="Markdown 中存在不支持的题目类别", status_code=400)

    def _resolve_target_path(self, job_role: str, file_name: str) -> Path:
        """根据岗位计算安全的题库写入路径。"""
        role_root = self.material_root / job_role
        if job_role == "java":
            target_dir = role_root / "java-interview"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = (target_dir / file_name).resolve()
        else:
            role_root.mkdir(parents=True, exist_ok=True)
            target_path = (role_root / file_name).resolve()
        material_root = self.material_root.resolve()
        if material_root not in target_path.parents:
            raise ApiError(code="QUESTION_BANK_400", message="文件路径超出题库材料目录", status_code=400)
        return target_path

    def _write_markdown(self, target_path: Path, markdown: str, append: bool = False) -> None:
        """将题库 Markdown 安全写入磁盘。"""
        normalized_markdown = markdown.strip() + "\n"
        if append and target_path.exists():
            current = target_path.read_text(encoding="utf-8").rstrip()
            if current:
                normalized_markdown = current + "\n\n" + normalized_markdown
        target_path.write_text(normalized_markdown, encoding="utf-8")

    async def _trigger_question_bank_import(self, job_role: str, idempotency_key: str) -> MaterialImportTriggerResponse:
        """复用材料导入服务触发题库专用导入任务。"""
        return await self.import_service.trigger(
            payload=MaterialImportRequest(
                rebuild_mode="incremental",
                roles=[job_role],
                dry_run=False,
                chunk_model=self.import_service.settings.chunk_model,
                embedding_model=self.import_service.settings.embedding_model,
                task_type="question_bank",
            ),
            idempotency_key=idempotency_key,
        )

    def _build_generated_file_name(self) -> str:
        """生成按日期归档的管理端增量题库文件名。"""
        return f"admin-added-{datetime.now().strftime('%Y%m%d')}.md"

    def _render_single_question_markdown(
        self,
        job_role: str,
        question_no: int,
        title: str,
        category: str,
        question: str,
        analysis: str,
        source_note: str,
    ) -> str:
        """按当前题库约定渲染单题 Markdown。"""
        question_heading = "###" if job_role == "web" else "##"
        section_heading = "####" if job_role == "web" else "###"
        lines = [
            f"{question_heading} 第 {question_no} 题：{title}",
            "",
            f"{section_heading} 题干",
            "",
            question,
            "",
            f"{section_heading} 类别",
            "",
            _CATEGORY_LABELS[category],
            "",
            f"{section_heading} 解析",
            "",
            analysis,
        ]
        if source_note:
            lines.extend(["", f"{section_heading} 来源备注", "", source_note])
        return "\n".join(lines)

    def _split_question_blocks(self, job_role: str, content: str) -> list[str]:
        """按岗位题库规范切分题目块。"""
        pattern = _WEB_BLOCK_PATTERN if job_role == "web" else _JAVA_BLOCK_PATTERN
        return [match.group(0).strip() for match in pattern.finditer(content)]

    def _validate_question_block(self, job_role: str, block: str) -> str:
        """校验单个题目块的 heading 层级、字段顺序和必填内容。"""
        pattern = _WEB_SECTION_PATTERN if job_role == "web" else _JAVA_SECTION_PATTERN
        match = pattern.search(block)
        if match is None:
            raise ApiError(code="QUESTION_BANK_400", message="Markdown 内容不符合题库格式要求", status_code=400)
        stem, category, analysis = (item.strip() for item in match.groups())
        if not stem or not category or not analysis:
            raise ApiError(code="QUESTION_BANK_400", message="Markdown 内容不符合题库格式要求", status_code=400)
        return category.splitlines()[0].strip()

    def _normalize_category_value(self, category: str) -> str | None:
        """将类别值归一化到受支持集合。"""
        normalized = re.sub(r"\s+", "", category).strip().lower()
        if not normalized:
            return None
        return _ALLOWED_CATEGORY_VALUES.get(normalized) or _ALLOWED_CATEGORY_VALUES.get(category.strip())

    def _next_question_no(self, target_path: Path, job_role: str) -> int:
        """计算目标材料文件中的下一个题号。"""
        if not target_path.exists():
            return 1
        content = target_path.read_text(encoding="utf-8")
        matches = [int(match.group(1)) for match in _QUESTION_HEADING_PATTERN.finditer(content)]
        return (max(matches) + 1) if matches else 1
