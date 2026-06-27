"""将 material 目录标准化为可导入 JSONL。"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from common import REPO_ROOT, discover_material_files, stable_id, write_jsonl

QUESTION_PATTERN = re.compile(r"^#{2,3}\s*第\s*(\d+)\s*题[：:]\s*(.+?)\s*$", re.MULTILINE)

# normalize_materials 是材料流水线第一步：
# 1. 从 material 目录读取 Java/Web 的题库和知识库材料。
# 2. 题库按“第 X 题”切成结构化记录，知识库按段落/标题切成检索片段。
# 3. 输出 JSONL 放到 data/normalized，供后续题库导入和向量库构建使用。
# 4. dry-run 只统计不写文件，适合在 CI 或导入前验证材料变更影响。
# 5. record_id 使用 stable_id，保证重复执行脚本不会改变同一条材料的身份。


@dataclass
class Segment:
    """表示按题目标题切分后的文档片段。"""

    order: int
    title: str
    body: str


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="标准化材料为 JSONL")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data" / "normalized"),
        help="规范化输出目录",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写出文件")
    return parser.parse_args()


def split_question_segments(content: str) -> list[Segment]:
    """按“第X题”标题切分题目块。"""
    # 正则只负责定位标题边界，正文范围由相邻标题位置计算。
    # 这样题干、解析中出现普通 Markdown 标题时，不会破坏题目级切分。
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
    # 材料中字段标题可能是 ### 到 ######，这里统一兼容。
    # 找不到字段时返回空字符串，由后续规范化逻辑使用标题或原文兜底。
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


def normalize_knowledge_file(role: str, source_path: Path, content: str) -> list[dict]:
    """标准化单个知识库文件为分块记录。"""
    source_rel_path = str(source_path.relative_to(REPO_ROOT))
    chunks = chunk_knowledge_text(content)
    rows: list[dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        record_id = stable_id(role, source_rel_path, str(idx), chunk[:80])
        rows.append(
            {
                "record_id": record_id,
                "role": role,
                "content_type": "knowledge",
                "source_path": source_rel_path,
                "chunk_no": idx,
                "title": source_path.stem,
                "content": chunk,
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
