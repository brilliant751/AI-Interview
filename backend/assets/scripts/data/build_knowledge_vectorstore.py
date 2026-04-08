"""将规范化知识库构建为可检索向量索引，并维护版本化 collection alias。"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import re
import urllib.error
import urllib.request
from pathlib import Path

from common import DATA_ROOT, write_build_report, write_json, write_jsonl


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="构建知识库向量索引")
    parser.add_argument("--input-dir", default=str(DATA_ROOT / "normalized"), help="规范化输入目录")
    parser.add_argument("--output-dir", default=str(DATA_ROOT / "chroma"), help="向量索引输出目录")
    parser.add_argument(
        "--report",
        default=str(DATA_ROOT / "reports" / "knowledge_vectorstore_build_report.json"),
        help="报告输出路径",
    )
    parser.add_argument("--rebuild-mode", choices=["full", "incremental"], default="full", help="重建模式")
    parser.add_argument("--roles", nargs="*", choices=["java", "web"], default=["java", "web"], help="岗位列表")
    parser.add_argument("--embed-model", default="nomic-embed-text", help="嵌入模型名")
    parser.add_argument("--embed-batch-size", type=int, default=32, help="嵌入批次大小")
    parser.add_argument("--ollama-base-url", default="http://127.0.0.1:11434", help="Ollama 服务地址")
    parser.add_argument(
        "--checkpoint",
        default=str(DATA_ROOT / "reports" / "vectorstore_checkpoint.json"),
        help="断点续跑 checkpoint 路径",
    )
    parser.add_argument("--max-retries", type=int, default=3, help="嵌入批次失败重试次数")
    parser.add_argument("--task-id", default="", help="任务 ID（可选）")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入索引")
    return parser.parse_args()


def tokenize(text: str) -> list[str]:
    """将文本分词为中英文 token 序列。"""
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower())


def hash_token(token: str, dim: int) -> int:
    """将 token 映射到固定维度桶。"""
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % dim


def hash_embed_text(text: str, dim: int = 64) -> list[float]:
    """使用哈希方式生成占位向量（仅 dry-run 或容灾场景）。"""
    vector = [0.0] * dim
    for token in tokenize(text):
        vector[hash_token(token, dim)] += 1.0
    total = sum(vector) or 1.0
    return [round(item / total, 6) for item in vector]


def iter_knowledge_rows(input_dir: Path, roles: list[str]) -> dict[str, list[dict]]:
    """按岗位读取知识 JSONL 记录。"""
    by_role: dict[str, list[dict]] = {}
    for role in roles:
        file_path = input_dir / f"{role}_knowledge.jsonl"
        rows: list[dict] = []
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as file_obj:
                for line in file_obj:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line))
        by_role[role] = rows
    return by_role


def load_aliases(alias_path: Path) -> dict[str, str]:
    """加载岗位 collection alias 文件。"""
    if not alias_path.exists():
        return {}
    try:
        payload = json.loads(alias_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {str(key): str(value) for key, value in payload.items()}
        return {}
    except Exception:
        return {}


def load_checkpoint(path: Path) -> dict:
    """读取 checkpoint 文件。"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_checkpoint(path: Path, payload: dict) -> None:
    """保存 checkpoint 文件。"""
    write_json(path, payload)


def parse_version(collection_name: str) -> int:
    """从 collection 名推断版本号。"""
    match = re.search(r"_v(\d+)$", collection_name)
    if not match:
        return 0
    return int(match.group(1))


def next_collection_name(role: str, aliases: dict[str, str]) -> str:
    """计算岗位下一版本 collection 名。"""
    current = aliases.get(role, "")
    version = parse_version(current)
    return f"kb_{role}_v{version + 1}"


def call_ollama_embed(
    base_url: str,
    model: str,
    inputs: list[str],
    retries: int,
) -> list[list[float]]:
    """调用 Ollama /api/embed 获取批量向量。"""
    url = base_url.rstrip("/") + "/api/embed"
    payload = json.dumps({"model": model, "input": inputs}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    last_error = "未知错误"
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url=url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            embeddings = parsed.get("embeddings")
            if not embeddings or not isinstance(embeddings, list):
                raise ValueError("Ollama 返回 embeddings 为空")
            return embeddings
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.5 * attempt)
                continue
    raise RuntimeError(f"Ollama 调用失败：{last_error}")


def compute_row_signature(row: dict) -> str:
    """计算知识行签名，用于增量判断。"""
    plain = "||".join(
        [
            str(row.get("record_id", "")),
            str(row.get("title", "")),
            str(row.get("content", "")),
            str(row.get("source_path", "")),
        ]
    )
    return hashlib.sha1(plain.encode("utf-8")).hexdigest()


def load_role_state(path: Path) -> dict[str, str]:
    """读取岗位状态快照（record_id -> 签名）。"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_role_state(path: Path, payload: dict[str, str]) -> None:
    """保存岗位状态快照。"""
    write_json(path, payload)


def main() -> int:
    """执行向量索引构建并输出报告。"""
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report)
    alias_path = output_dir / "aliases.json"
    checkpoint_path = Path(args.checkpoint)
    by_role = iter_knowledge_rows(input_dir, args.roles)
    aliases = load_aliases(alias_path)
    checkpoint = load_checkpoint(checkpoint_path)

    summary: dict[str, int] = {}
    collections: dict[str, str] = {}
    embedding_dimensions: dict[str, int] = {}
    total_rows = 0
    total_written = 0
    updated_rows = 0
    errors: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    chroma_client = None
    try:
        import chromadb  # type: ignore

        chroma_client = chromadb.PersistentClient(path=str(output_dir))
    except Exception as exc:
        if not args.dry_run:
            errors.append(f"Chroma 客户端初始化失败：{exc}")

    for role, rows in sorted(by_role.items()):
        summary[role] = len(rows)
        total_rows += len(rows)
        collection_name = next_collection_name(role, aliases)
        collections[role] = collection_name
        if not rows:
            continue

        state_path = output_dir / f"{role}_state.json"
        previous_state = load_role_state(state_path)
        current_state = {row["record_id"]: compute_row_signature(row) for row in rows}
        changed_ids = {row_id for row_id, sign in current_state.items() if previous_state.get(row_id) != sign}
        if args.rebuild_mode == "incremental":
            role_rows = [row for row in rows if row["record_id"] in changed_ids]
        else:
            role_rows = rows
        updated_rows += len(role_rows)

        index_rows: list[dict] = []
        for row in role_rows:
            index_rows.append(
                {
                    "id": row["record_id"],
                    "role": role,
                    "source_path": row.get("source_path", ""),
                    "chunk_no": row.get("chunk_no", 0),
                    "title": row.get("title", ""),
                    "content": row.get("content", ""),
                    "embedding": [],
                    "metadata": {
                        "source_type": "knowledge",
                        "chunk_tokens": row.get("chunk_tokens", 0),
                        "chunk_chars": row.get("chunk_chars", 0),
                    },
                }
            )

        print(f"岗位 {role}：知识块 {len(index_rows)}（总量 {len(rows)}）")
        if args.dry_run:
            for item in index_rows:
                item["embedding"] = hash_embed_text(item["content"])
            embedding_dimensions[role] = len(index_rows[0]["embedding"]) if index_rows else 0
            continue

        role_dir = output_dir / collection_name
        role_dir.mkdir(parents=True, exist_ok=True)
        if chroma_client is None:
            errors.append(f"岗位 {role} 写入 Chroma 失败：客户端不可用")
            continue

        try:
            collection = chroma_client.get_or_create_collection(name=collection_name)
            start_offset = 0
            if checkpoint.get("role") == role and checkpoint.get("collection_name") == collection_name:
                start_offset = int(checkpoint.get("offset", 0))
            for start in range(start_offset, len(index_rows), args.embed_batch_size):
                batch = index_rows[start : start + args.embed_batch_size]
                embeddings = call_ollama_embed(
                    base_url=args.ollama_base_url,
                    model=args.embed_model,
                    inputs=[item["content"] for item in batch],
                    retries=args.max_retries,
                )
                for item, embedding in zip(batch, embeddings):
                    item["embedding"] = embedding
                if batch and batch[0]["embedding"]:
                    embedding_dimensions[role] = len(batch[0]["embedding"])
                collection.upsert(
                    ids=[item["id"] for item in batch],
                    documents=[item["content"] for item in batch],
                    metadatas=[
                        {
                            "role": role,
                            "title": item["title"],
                            "source_path": item["source_path"],
                            "chunk_no": item["chunk_no"],
                        }
                        for item in batch
                    ],
                    embeddings=[item["embedding"] for item in batch],
                )
                save_checkpoint(
                    checkpoint_path,
                    {
                        "role": role,
                        "collection_name": collection_name,
                        "offset": start + len(batch),
                        "updated_at": int(time.time()),
                    },
                )
            written = write_jsonl(role_dir / "knowledge_index.jsonl", index_rows)
            total_written += written
            save_role_state(state_path, current_state)
            aliases[role] = collection_name
            print(f"已写入 Chroma collection：{collection_name}")
        except Exception as exc:
            errors.append(f"岗位 {role} 写入 Chroma 失败：{exc}")

    if not args.dry_run:
        write_json(alias_path, aliases)
        save_checkpoint(checkpoint_path, {})

    status = "SUCCESS" if not errors else "PARTIAL_SUCCESS"
    report = {
        "status": status,
        "total_rows": total_rows,
        "updated_rows": updated_rows,
        "written_rows": total_written if not args.dry_run else 0,
        "embedding_dimensions": embedding_dimensions,
        "rebuild_mode": args.rebuild_mode,
        "embed_model": args.embed_model,
        "ollama_base_url": args.ollama_base_url,
        "embed_batch_size": args.embed_batch_size,
        "roles": summary,
        "collection_version": collections,
        "task_id": args.task_id,
        "errors": errors,
        "dry_run": args.dry_run,
    }
    write_build_report(report_path, report)
    print("向量索引构建完成：" + json.dumps(report, ensure_ascii=False))
    return 0 if status in {"SUCCESS", "PARTIAL_SUCCESS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
