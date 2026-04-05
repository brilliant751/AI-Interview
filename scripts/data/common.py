"""数据脚本公共能力：路径发现、ID 生成与文件写入。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
MATERIAL_ROOT = REPO_ROOT / "material"


def discover_material_files() -> list[dict[str, str]]:
    """发现并返回受支持的材料文件清单。"""
    return [
        {
            "role": "java",
            "kind": "question_bank",
            "path": str(MATERIAL_ROOT / "java" / "java-interview"),
            "is_dir": "1",
        },
        {
            "role": "java",
            "kind": "knowledge",
            "path": str(MATERIAL_ROOT / "java" / "java-knowledge"),
            "is_dir": "1",
        },
        {
            "role": "web",
            "kind": "question_bank",
            "path": str(MATERIAL_ROOT / "web" / "interview.md"),
            "is_dir": "0",
        },
        {
            "role": "web",
            "kind": "knowledge",
            "path": str(MATERIAL_ROOT / "web" / "knowledge.md"),
            "is_dir": "0",
        },
    ]


def stable_id(*parts: str) -> str:
    """为记录生成稳定且可重复的 ID。"""
    plain = "||".join(parts)
    return hashlib.sha1(plain.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    """将对象写入 JSON 文件，并自动创建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    """将对象迭代器写入 JSONL 文件，并返回写入行数。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count

