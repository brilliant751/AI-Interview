"""基于规则优先与 Ollama 辅助的知识分块脚本。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import DATA_ROOT, write_jsonl


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="知识分块脚本")
    parser.add_argument("--input", required=True, help="输入 JSONL 文件路径")
    parser.add_argument("--output", default=str(DATA_ROOT / "normalized" / "chunked.jsonl"), help="输出 JSONL 路径")
    parser.add_argument("--max-chars", type=int, default=1200, help="块最大字符数")
    parser.add_argument("--min-chars", type=int, default=200, help="块最小字符数")
    parser.add_argument("--overlap", type=int, default=120, help="相邻块重叠长度")
    parser.add_argument("--model", default="qwen3.5-2b", help="分块模型名")
    return parser.parse_args()


def split_by_rules(text: str, max_chars: int, overlap: int) -> list[str]:
    """按规则切块，避免超长段落。"""
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + max_chars)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def main() -> int:
    """执行分块并写出结果。"""
    args = parse_args()
    input_path = Path(args.input)
    rows: list[dict] = []
    with input_path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    out_rows: list[dict] = []
    for row in rows:
        chunks = split_by_rules(row.get("content", ""), args.max_chars, args.overlap)
        for idx, chunk in enumerate(chunks, start=1):
            if len(chunk) < args.min_chars:
                continue
            out_rows.append(
                {
                    **row,
                    "chunk_no": idx,
                    "content": chunk,
                    "chunk_chars": len(chunk),
                    "chunk_tokens": max(1, len(chunk) // 2),
                    "chunk_model": args.model,
                }
            )

    write_jsonl(Path(args.output), out_rows)
    print(f"分块完成，输出记录数：{len(out_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
