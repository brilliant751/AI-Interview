"""将 backend/assets/material 目录标准化为可导入 JSONL。"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from common import DATA_ROOT, REPO_ROOT, discover_material_files, stable_id, write_jsonl

QUESTION_PATTERN = re.compile(r"^#{2,3}\s*第\s*(\d+)\s*题[：:]\s*(.+?)\s*$", re.MULTILINE)
WEB_KNOWLEDGE_PATTERN = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Segment:
    """表示按题目标题切分后的文档片段。"""

    order: int
    title: str
    body: str


@dataclass
class HeadingNode:
    """表示知识文档中的标题节点。"""

    level: int
    start: int
    line_end: int
    title: str


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="标准化材料为 JSONL")
    parser.add_argument(
        "--output-dir",
        default=str(DATA_ROOT / "normalized"),
        help="规范化输出目录",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写出文件")
    return parser.parse_args()


def split_question_segments(content: str) -> list[Segment]:
    """按“第X题”标题切分题目块。"""
    matches = list(QUESTION_PATTERN.finditer(content))
    segments: list[Segment] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        segments.append(
            Segment(
                order=int(match.group(1)),
                title=match.group(2).strip(),
                body=body,
            )
        )
    return segments


def pick_section_text(body: str, section_name: str) -> str:
    """从题目块中提取指定字段内容。"""
    escaped = re.escape(section_name)
    pattern = re.compile(
        rf"^#{3,6}\s*{escaped}\s*$([\s\S]*?)(?=^#{3,6}\s+\S+|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(body)
    if not match:
        return ""
    return match.group(1).strip()


def normalize_question_file(role: str, source_path: Path, content: str) -> list[dict]:
    """标准化单个题库文件为记录列表。"""
    rows: list[dict] = []
    segments = split_question_segments(content)
    for seg in segments:
        prompt = pick_section_text(seg.body, "题干") or seg.title
        category = pick_section_text(seg.body, "类别")
        analysis = pick_section_text(seg.body, "解析")
        source_rel_path = str(source_path.relative_to(REPO_ROOT))
        record_id = stable_id(role, source_rel_path, str(seg.order), seg.title)
        rows.append(
            {
                "record_id": record_id,
                "role": role,
                "content_type": "question_bank",
                "source_path": source_rel_path,
                "question_no": seg.order,
                "title": seg.title,
                "category": category,
                "question": prompt,
                "analysis": analysis,
                "raw_markdown": seg.body,
            }
        )
    return rows


def chunk_knowledge_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    """按字符窗口切分知识文本，保留重叠窗口以降低信息断裂。"""
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not compact:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(compact):
        end = min(start + chunk_size, len(compact))
        chunk = compact[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(compact):
            break
        start = max(0, end - overlap)
    return chunks


def find_last_heading(headings: list[tuple[int, int, str]], level: int, pos: int) -> str:
    """在指定位置前查找最近的指定级别标题。"""
    latest = ""
    for heading_level, heading_pos, heading_text in headings:
        if heading_level != level:
            continue
        if heading_pos >= pos:
            break
        latest = heading_text
    return latest


def split_web_knowledge_segments(content: str) -> list[Segment]:
    """按 Web 知识库中的编号题干切分条目。"""
    entry_matches = list(WEB_KNOWLEDGE_PATTERN.finditer(content))
    section_matches = [
        (2, match.start(), match.group(2).strip())
        for match in HEADING_PATTERN.finditer(content)
        if len(match.group(1)) == 2
    ]
    segments: list[Segment] = []
    for idx, match in enumerate(entry_matches):
        start = match.end()
        end = entry_matches[idx + 1].start() if idx + 1 < len(entry_matches) else len(content)
        body = content[start:end].strip()
        question_no = int(match.group(1))
        question_title = match.group(2).strip()
        section_title = find_last_heading(section_matches, 2, match.start())
        content_parts = []
        if section_title:
            content_parts.append(f"## {section_title}")
        content_parts.append(f"{question_no}. {question_title}")
        if body:
            content_parts.append(body)
        segments.append(
            Segment(
                order=question_no,
                title=question_title,
                body="\n\n".join(content_parts).strip(),
            )
        )
    return segments


def split_java_knowledge_segments(content: str) -> list[Segment]:
    """按 Java 知识库层级切分条目，最细到四级标题，最粗到二级标题。"""
    heading_matches = list(HEADING_PATTERN.finditer(content))
    headings: list[HeadingNode] = []
    for match in heading_matches:
        level = len(match.group(1))
        if level > 4:
            continue
        start = match.start()
        line_end = content.find("\n", start)
        headings.append(
            HeadingNode(
                level=level,
                start=start,
                line_end=len(content) if line_end == -1 else line_end + 1,
                title=match.group(2).strip(),
            )
        )

    def find_section_end(index: int) -> int:
        """查找当前标题作用域的结束位置。"""
        current_level = headings[index].level
        for candidate in headings[index + 1 :]:
            if candidate.level <= current_level:
                return candidate.start
        return len(content)

    def build_heading_context(index: int) -> list[tuple[int, str]]:
        """构建当前标题的层级上下文。"""
        context: dict[int, str] = {}
        current_level = headings[index].level
        for item in headings[: index + 1]:
            if item.level <= current_level:
                context[item.level] = item.title
        return [(level, context[level]) for level in range(1, current_level + 1) if level in context]

    segments: list[Segment] = []
    seg_no = 0
    for index, heading in enumerate(headings):
        if heading.level < 2 or heading.level > 4:
            continue
        section_end = find_section_end(index)
        child_positions = [
            item.start
            for item in headings[index + 1 :]
            if item.start < section_end and item.level == heading.level + 1
        ]
        body_end = child_positions[0] if child_positions else section_end
        body = content[heading.line_end:body_end].strip()
        if not body:
            continue

        context = build_heading_context(index)
        content_parts = [f"{'#' * level} {title}" for level, title in context]
        content_parts.append(body)
        seg_no += 1
        segments.append(
            Segment(
                order=seg_no,
                title=heading.title,
                body="\n\n".join(content_parts).strip(),
            )
        )
    return segments


def normalize_knowledge_file(role: str, source_path: Path, content: str) -> list[dict]:
    """标准化单个知识库文件为分块记录。"""
    source_rel_path = str(source_path.relative_to(REPO_ROOT))
    if role == "web":
        segments = split_web_knowledge_segments(content)
    elif role == "java":
        segments = split_java_knowledge_segments(content)
    else:
        segments = []
    if not segments:
        fallback_chunks = chunk_knowledge_text(content)
        segments = [
            Segment(order=idx, title=source_path.stem, body=chunk)
            for idx, chunk in enumerate(fallback_chunks, start=1)
        ]
    rows: list[dict] = []
    for seg in segments:
        record_id = stable_id(role, source_rel_path, str(seg.order), seg.title)
        rows.append(
            {
                "record_id": record_id,
                "role": role,
                "content_type": "knowledge",
                "source_path": source_rel_path,
                "chunk_no": seg.order,
                "title": seg.title,
                "content": seg.body,
            }
        )
    return rows


def collect_source_files() -> list[tuple[str, str, Path]]:
    """收集所有需要规范化的源文件。"""
    files: list[tuple[str, str, Path]] = []
    for item in discover_material_files():
        role = item["role"]
        kind = item["kind"]
        path = Path(item["path"])
        if item["is_dir"] == "1":
            for file_path in sorted(path.glob("*.md")):
                files.append((role, kind, file_path))
        else:
            files.append((role, kind, path))
    return files


def main() -> int:
    """执行规范化流程并输出 JSONL。"""
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_files = collect_source_files()
    print(f"开始规范化，共 {len(source_files)} 个材料文件")

    question_rows_by_role: dict[str, list[dict]] = {}
    knowledge_rows_by_role: dict[str, list[dict]] = {}

    for role, kind, source_path in source_files:
        content = source_path.read_text(encoding="utf-8")
        if kind == "question_bank":
            rows = normalize_question_file(role, source_path, content)
            question_rows_by_role.setdefault(role, []).extend(rows)
        else:
            rows = normalize_knowledge_file(role, source_path, content)
            knowledge_rows_by_role.setdefault(role, []).extend(rows)

    total_written = 0
    for role, rows in sorted(question_rows_by_role.items()):
        output_path = output_dir / f"{role}_question_bank.jsonl"
        print(f"题库记录：{role} -> {len(rows)}")
        if not args.dry_run:
            total_written += write_jsonl(output_path, rows)
            print(f"已写入：{output_path}")
    for role, rows in sorted(knowledge_rows_by_role.items()):
        output_path = output_dir / f"{role}_knowledge.jsonl"
        print(f"知识记录：{role} -> {len(rows)}")
        if not args.dry_run:
            total_written += write_jsonl(output_path, rows)
            print(f"已写入：{output_path}")

    print(f"规范化完成，写入总记录数：{total_written if not args.dry_run else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
