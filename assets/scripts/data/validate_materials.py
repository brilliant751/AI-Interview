"""校验 assets/material 目录材料质量，并输出可追溯报告。"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from common import REPO_ROOT, discover_material_files, write_json


@dataclass
class ValidationIssue:
    """表示单个材料文件的校验问题。"""

    level: str
    code: str
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="校验材料文件并输出报告")
    parser.add_argument(
        "--report",
        default=str(REPO_ROOT / "assets" / "data" / "reports" / "material_validation_report.json"),
        help="报告输出路径",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="出现错误时返回非 0 退出码",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    """读取 UTF-8 文本文件内容。"""
    return path.read_text(encoding="utf-8")


def validate_question_file(path: Path, content: str) -> list[ValidationIssue]:
    """校验题库文件结构。"""
    issues: list[ValidationIssue] = []
    question_count = len(re.findall(r"^#{2,3}\s*第\s*\d+\s*题[：:]", content, flags=re.MULTILINE))
    if question_count == 0:
        issues.append(
            ValidationIssue(
                level="error",
                code="QUESTION_NOT_FOUND",
                path=str(path),
                message="未识别到“第X题”结构，无法作为题库导入",
            )
        )

    if "题干" not in content:
        issues.append(
            ValidationIssue(
                level="warning",
                code="MISSING_PROMPT_SECTION",
                path=str(path),
                message="未发现“题干”字段，后续解析将使用标题兜底",
            )
        )

    if "解析" not in content:
        issues.append(
            ValidationIssue(
                level="warning",
                code="MISSING_ANALYSIS_SECTION",
                path=str(path),
                message="未发现“解析”字段，导入后解析内容可能为空",
            )
        )
    return issues


def validate_knowledge_file(path: Path, content: str) -> list[ValidationIssue]:
    """校验知识库文件结构。"""
    issues: list[ValidationIssue] = []
    heading_count = len(re.findall(r"^#{1,3}\s+\S+", content, flags=re.MULTILINE))
    if heading_count == 0:
        issues.append(
            ValidationIssue(
                level="error",
                code="HEADING_NOT_FOUND",
                path=str(path),
                message="未发现标题结构，无法稳定切分知识块",
            )
        )
    return issues


def validate_one_file(role: str, kind: str, file_path: Path) -> tuple[dict, list[ValidationIssue]]:
    """校验单个文件并返回统计与问题列表。"""
    if not file_path.exists():
        issue = ValidationIssue(
            level="error",
            code="FILE_NOT_FOUND",
            path=str(file_path),
            message="文件不存在",
        )
        return {"role": role, "kind": kind, "path": str(file_path), "size": 0}, [issue]

    size = file_path.stat().st_size
    if size == 0:
        issue = ValidationIssue(
            level="error",
            code="EMPTY_FILE",
            path=str(file_path),
            message="文件为空",
        )
        return {"role": role, "kind": kind, "path": str(file_path), "size": 0}, [issue]

    content = read_text(file_path)
    issues = []
    if kind == "question_bank":
        issues.extend(validate_question_file(file_path, content))
    else:
        issues.extend(validate_knowledge_file(file_path, content))
    return {"role": role, "kind": kind, "path": str(file_path), "size": size}, issues


def collect_targets() -> list[tuple[str, str, Path]]:
    """收集需要校验的所有材料文件路径。"""
    targets: list[tuple[str, str, Path]] = []
    for item in discover_material_files():
        role = item["role"]
        kind = item["kind"]
        path = Path(item["path"])
        if item["is_dir"] == "1":
            for file_path in sorted(path.glob("*.md")):
                targets.append((role, kind, file_path))
        else:
            targets.append((role, kind, path))
    return targets


def build_report(stats: list[dict], issues: list[ValidationIssue]) -> dict:
    """构建最终校验报告对象。"""
    error_count = len([x for x in issues if x.level == "error"])
    warning_count = len([x for x in issues if x.level == "warning"])
    return {
        "summary": {
            "total_files": len(stats),
            "error_count": error_count,
            "warning_count": warning_count,
            "pass_count": len(stats) - len({x.path for x in issues}),
        },
        "files": stats,
        "issues": [x.__dict__ for x in issues],
    }


def main() -> int:
    """执行材料校验流程。"""
    args = parse_args()
    targets = collect_targets()
    print(f"开始校验材料，共 {len(targets)} 个文件")

    all_stats: list[dict] = []
    all_issues: list[ValidationIssue] = []
    for role, kind, file_path in targets:
        stat, issues = validate_one_file(role, kind, file_path)
        all_stats.append(stat)
        all_issues.extend(issues)

    report = build_report(all_stats, all_issues)
    report_path = Path(args.report)
    write_json(report_path, report)
    print(f"校验完成，报告已输出：{report_path}")
    print(
        "校验结果摘要："
        + json.dumps(report["summary"], ensure_ascii=False)
    )

    if args.strict and report["summary"]["error_count"] > 0:
        print("严格模式已启用：检测到错误，返回非 0")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
