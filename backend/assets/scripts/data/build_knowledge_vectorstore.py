"""将规范化知识库构建为本地可检索向量索引（JSONL 形式）。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from common import DATA_ROOT, write_json, write_jsonl


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="构建知识库向量索引")
    parser.add_argument(
        "--input-dir",
        default=str(DATA_ROOT / "normalized"),
        help="规范化输入目录",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DATA_ROOT / "chroma"),
        help="向量索引输出目录",
    )
    parser.add_argument(
        "--report",
        default=str(DATA_ROOT / "reports" / "knowledge_vectorstore_build_report.json"),
        help="报告输出路径",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=64,
        help="向量维度，默认 64",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入索引")
    return parser.parse_args()


def tokenize(text: str) -> list[str]:
    """将文本分词为中英文 token 序列。"""
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower())


def hash_token(token: str, dim: int) -> int:
    """将 token 映射到固定维度桶。"""
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % dim


def embed_text(text: str, dim: int) -> list[float]:
    """使用 Hashing Trick 生成归一化向量。"""
    vector = [0.0] * dim
    tokens = tokenize(text)
    for token in tokens:
        idx = hash_token(token, dim)
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [round(v / norm, 6) for v in vector]


def iter_knowledge_rows(input_dir: Path) -> dict[str, list[dict]]:
    """按岗位读取知识 JSONL 记录。"""
    by_role: dict[str, list[dict]] = {}
    for file_path in sorted(input_dir.glob("*_knowledge.jsonl")):
        role = file_path.name.replace("_knowledge.jsonl", "")
        rows: list[dict] = []
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        by_role[role] = rows
    return by_role


def main() -> int:
    """执行向量索引构建并输出报告。"""
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    by_role = iter_knowledge_rows(input_dir)

    summary: dict[str, int] = {}
    total_rows = 0
    total_written = 0
    output_dir.mkdir(parents=True, exist_ok=True)

    chroma_client = None
    try:
        import chromadb  # type: ignore

        chroma_client = chromadb.PersistentClient(path=str(output_dir))
    except Exception:
        chroma_client = None

    for role, rows in sorted(by_role.items()):
        total_rows += len(rows)
        summary[role] = len(rows)
        index_rows: list[dict] = []
        for row in rows:
            embedding = embed_text(row.get("content", ""), args.dimension)
            index_rows.append(
                {
                    "id": row["record_id"],
                    "role": role,
                    "source_path": row.get("source_path", ""),
                    "chunk_no": row.get("chunk_no", 0),
                    "title": row.get("title", ""),
                    "content": row.get("content", ""),
                    "embedding": embedding,
                    "metadata": {
                        "updated_at": "",
                        "source_type": "knowledge",
                    },
                }
            )
        print(f"岗位 {role}：知识块 {len(index_rows)}")
        if not args.dry_run:
            role_dir = output_dir / f"kb_{role}"
            role_dir.mkdir(parents=True, exist_ok=True)
            written = write_jsonl(role_dir / "knowledge_index.jsonl", index_rows)
            total_written += written
            print(f"已写入：{role_dir / 'knowledge_index.jsonl'}")
            if chroma_client is not None:
                collection = chroma_client.get_or_create_collection(name=f"kb_{role}")
                collection.upsert(
                    ids=[item["id"] for item in index_rows],
                    documents=[item["content"] for item in index_rows],
                    metadatas=[
                        {
                            "role": role,
                            "title": item["title"],
                            "source_path": item["source_path"],
                            "chunk_no": item["chunk_no"],
                            "updated_at": item["metadata"].get("updated_at", ""),
                        }
                        for item in index_rows
                    ],
                    embeddings=[item["embedding"] for item in index_rows],
                )
                print(f"已写入 Chroma collection：kb_{role}")

    report = {
        "total_rows": total_rows,
        "written_rows": total_written if not args.dry_run else 0,
        "dimension": args.dimension,
        "roles": summary,
        "dry_run": args.dry_run,
    }
    write_json(Path(args.report), report)
    print("向量索引构建完成：" + json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
