"""统计 Java 知识文档条目数并与现有知识库比对。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import REPO_ROOT, write_json


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="校验 Java 知识库条目数")
    parser.add_argument(
        "--java-material-dir",
        default=str(REPO_ROOT / "assets" / "material" / "java" / "java-knowledge"),
        help="Java 知识文档目录",
    )
    parser.add_argument(
        "--normalized-path",
        default=str(REPO_ROOT / "assets" / "data" / "normalized" / "java_knowledge.jsonl"),
        help="标准化知识库 JSONL 路径",
    )
    parser.add_argument(
        "--vector-index-path",
        default=str(REPO_ROOT / "assets" / "data" / "chroma" / "kb_java" / "knowledge_index.jsonl"),
        help="向量索引 JSONL 路径",
    )
    parser.add_argument(
        "--report",
        default=str(REPO_ROOT / "assets" / "data" / "reports" / "java_knowledge_count_compare.json"),
        help="比对报告输出路径",
    )
    return parser.parse_args()


def count_h3_entries(file_path: Path) -> int:
    """按三级标题统计单个文档条目数。"""
    count = 0
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("### "):
                count += 1
    return count


def load_jsonl_count_by_source(jsonl_path: Path, source_prefix: str) -> dict[str, int]:
    """从 JSONL 中按 source_path 聚合记录数。"""
    counter: dict[str, int] = {}
    if not jsonl_path.exists():
        return counter
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            source_path = row.get("source_path", "")
            if not source_path.startswith(source_prefix):
                continue
            key = Path(source_path).name
            counter[key] = counter.get(key, 0) + 1
    return counter


def main() -> int:
    """执行条目统计与比对。"""
    args = parse_args()
    java_material_dir = Path(args.java_material_dir)
    expected_by_doc: dict[str, int] = {}
    for file_path in sorted(java_material_dir.glob("*.md")):
        expected_by_doc[file_path.name] = count_h3_entries(file_path)

    normalized_counter = load_jsonl_count_by_source(
        Path(args.normalized_path),
        "assets/material/java/java-knowledge/",
    )
    vector_counter = load_jsonl_count_by_source(
        Path(args.vector_index_path),
        "assets/material/java/java-knowledge/",
    )

    mismatched_docs: list[dict[str, int | str]] = []
    for doc_name, expected in expected_by_doc.items():
        normalized_count = normalized_counter.get(doc_name, 0)
        vector_count = vector_counter.get(doc_name, 0)
        if normalized_count != expected or vector_count != expected:
            mismatched_docs.append(
                {
                    "doc": doc_name,
                    "expected": expected,
                    "normalized": normalized_count,
                    "vector_index": vector_count,
                }
            )

    report = {
        "total_docs": len(expected_by_doc),
        "expected_total": sum(expected_by_doc.values()),
        "normalized_total": sum(normalized_counter.values()),
        "vector_index_total": sum(vector_counter.values()),
        "expected_by_doc": expected_by_doc,
        "normalized_by_doc": normalized_counter,
        "vector_index_by_doc": vector_counter,
        "mismatched_docs": mismatched_docs,
        "matched": len(mismatched_docs) == 0,
    }
    write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
