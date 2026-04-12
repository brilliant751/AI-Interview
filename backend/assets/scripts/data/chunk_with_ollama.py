"""使用 Ollama 模型进行知识分块，不提供规则兜底。"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from common import DATA_ROOT, write_jsonl


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="知识分块脚本（强制模型分块）")
    parser.add_argument("--input", required=True, help="输入 JSONL 文件路径")
    parser.add_argument("--output", default=str(DATA_ROOT / "normalized" / "chunked.jsonl"), help="输出 JSONL 路径")
    parser.add_argument("--max-chars", type=int, default=1200, help="块最大字符数")
    parser.add_argument("--min-chars", type=int, default=200, help="块最小字符数")
    parser.add_argument("--overlap", type=int, default=120, help="相邻块建议重叠长度")
    parser.add_argument("--model", default="qwen2.5:7b", help="分块模型名")
    parser.add_argument("--ollama-base-url", default="http://127.0.0.1:11434", help="Ollama 服务地址")
    parser.add_argument("--max-retries", type=int, default=2, help="模型调用失败重试次数")
    parser.add_argument("--request-timeout", type=int, default=600, help="单次模型请求超时秒数")
    return parser.parse_args()


def build_prompt(text: str, min_chars: int, max_chars: int, overlap: int) -> str:
    """构建分块提示词。"""
    return (
        "你是知识库分块器。请将输入文本切分为多个连续 chunks，并严格返回 JSON。\n"
        "要求：\n"
        f"1) 每个 chunk 尽量在 {min_chars}~{max_chars} 字符范围内；\n"
        f"2) 相邻 chunk 尽量保留约 {overlap} 字符语义重叠；\n"
        "3) 不要遗漏原文信息，不要改写语义；\n"
        "4) 只返回 JSON，结构为 {\"chunks\": [\"...\", \"...\"]}。\n"
        "待分块文本如下：\n"
        "-----BEGIN_TEXT-----\n"
        f"{text}\n"
        "-----END_TEXT-----"
    )


def parse_or_repair_json(base_url: str, model: str, raw_text: str, request_timeout: int) -> dict:
    """解析模型 JSON；失败时请求模型修复为合法 JSON。"""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    repair_payload = {
        "model": model,
        "prompt": (
            "请将以下文本修复为严格合法 JSON，仅输出 JSON。\n"
            "目标结构：{\"chunks\":[\"...\"]}\n"
            f"原始文本：\n{raw_text}"
        ),
        "stream": False,
        "format": {
            "type": "object",
            "properties": {"chunks": {"type": "array", "items": {"type": "string"}}},
            "required": ["chunks"],
        },
        "think": False,
        "options": {"temperature": 0, "num_predict": 2048},
    }
    request = urllib.request.Request(
        url=base_url.rstrip("/") + "/api/generate",
        data=json.dumps(repair_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        fixed_raw = response.read().decode("utf-8")
    fixed_payload = json.loads(fixed_raw)
    fixed_content = str(fixed_payload.get("response", "")).strip() or str(fixed_payload.get("thinking", "")).strip()
    return json.loads(fixed_content)


def call_ollama_chunk(
    base_url: str,
    model: str,
    text: str,
    min_chars: int,
    max_chars: int,
    overlap: int,
    max_retries: int,
    request_timeout: int,
) -> list[str]:
    """调用 Ollama 进行分块。"""
    url = base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": build_prompt(text=text, min_chars=min_chars, max_chars=max_chars, overlap=overlap),
        "stream": False,
        "format": {
            "type": "object",
            "properties": {"chunks": {"type": "array", "items": {"type": "string"}}},
            "required": ["chunks"],
        },
        "think": False,
        "options": {"temperature": 0, "num_predict": 4096},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    last_error = "未知错误"
    for _ in range(max_retries + 1):
        request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            content = str(parsed.get("response", "")).strip()
            if not content:
                content = str(parsed.get("thinking", "")).strip()
            if not content:
                raise RuntimeError("模型返回为空")
            chunk_payload = parse_or_repair_json(
                base_url=base_url,
                model=model,
                raw_text=content,
                request_timeout=request_timeout,
            )
            chunks = chunk_payload.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                raise RuntimeError("模型返回 chunks 非法")
            cleaned = [str(item).strip() for item in chunks if str(item).strip()]
            if not cleaned:
                raise RuntimeError("模型返回的 chunks 为空")
            return cleaned
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = str(exc)
            continue
    raise RuntimeError(f"Ollama 分块失败：{last_error}")


def main() -> int:
    """执行分块并写出结果。"""
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"输入文件不存在：{input_path}")

    rows: list[dict] = []
    with input_path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    out_rows: list[dict] = []
    for row in rows:
        source_text = str(row.get("content", "")).strip()
        if not source_text:
            continue
        chunks = call_ollama_chunk(
            base_url=args.ollama_base_url,
            model=args.model,
            text=source_text,
            min_chars=args.min_chars,
            max_chars=args.max_chars,
            overlap=args.overlap,
            max_retries=args.max_retries,
            request_timeout=args.request_timeout,
        )
        for idx, chunk in enumerate(chunks, start=1):
            out_rows.append(
                {
                    **row,
                    "record_id": f"{row.get('record_id', '')}-c{idx}",
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
