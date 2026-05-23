"""清洗 Java/Web 选择题并输出统一格式数据。"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import ASSETS_ROOT, stable_id, write_json

SOURCES_PATH = ASSETS_ROOT / "material" / "sources" / "question_bank_sources.json"
OUTPUT_PATH = ASSETS_ROOT / "material" / "choice" / "normalized" / "choice_questions.json"
REPORT_PATH = ASSETS_ROOT / "data" / "reports" / "choice_question_normalize_report.json"
CHECKPOINT_PATH = ASSETS_ROOT / "data" / "reports" / "choice_question_normalize_checkpoint.json"
CACHE_DIR = ASSETS_ROOT / "data" / ".cache" / "choice_sources"


@dataclass
class SourceFile:
    """表示单个源仓库中需要抓取的文件。"""

    domain: str
    repo_full_name: str
    url: str
    license_name: str
    entry_file: str
    raw_url: str


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="清洗 Java/Web 选择题数据")
    parser.add_argument("--sources", default=str(SOURCES_PATH), help="来源配置 JSON 路径")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="统一题目输出路径")
    parser.add_argument("--report", default=str(REPORT_PATH), help="清洗报告输出路径")
    parser.add_argument("--checkpoint", default=str(CHECKPOINT_PATH), help="检查点文件路径")
    parser.add_argument("--cache-dir", default=str(CACHE_DIR), help="源码缓存目录")
    parser.add_argument("--retry", type=int, default=3, help="网络请求失败重试次数")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写输出")
    return parser.parse_args()


def http_get_text(url: str, retry: int) -> str:
    """以重试机制获取文本内容。"""
    last_error: Exception | None = None
    for attempt in range(1, retry + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ai-interview-choice-normalizer/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retry:
                time.sleep(min(2 * attempt, 5))
    raise RuntimeError(f"请求失败: {url}") from last_error


def github_raw_url(repo_full_name: str, entry_file: str) -> str:
    """构建 GitHub raw 文件 URL。"""
    return f"https://raw.githubusercontent.com/{repo_full_name}/HEAD/{entry_file}"


def load_sources(path: Path) -> list[SourceFile]:
    """读取来源配置并展开文件列表。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: list[SourceFile] = []
    for item in payload:
        domain = item.get("domain", "").strip().lower()
        if domain not in {"java", "web"}:
            continue
        repo_full_name = item.get("repo_full_name", "").strip()
        url = item.get("url", "").strip()
        license_name = item.get("license", "").strip()
        for entry in item.get("entry_files", []):
            entry_file = str(entry).strip()
            if not entry_file.lower().endswith(".md"):
                continue
            results.append(
                SourceFile(
                    domain=domain,
                    repo_full_name=repo_full_name,
                    url=url,
                    license_name=license_name,
                    entry_file=entry_file,
                    raw_url=github_raw_url(repo_full_name, entry_file),
                )
            )
    return results


def parse_java_markdown_mcq(content: str) -> list[dict[str, Any]]:
    """解析 Java 题库中的选择题。"""
    rows: list[dict[str, Any]] = []
    blocks = re.split(r"(?=^##\s*Q\.)", content, flags=re.MULTILINE)
    for block in blocks:
        title_match = re.search(r"^##\s*Q\.\s*(.+)$", block, re.MULTILINE)
        if not title_match:
            continue
        stem = title_match.group(1).strip()
        # 仅在题干后、答案/输出/解释前的区域解析选项，避免误抓代码块与解析文本。
        option_region_end = len(block)
        stop_match = re.search(
            r"^\s*(?:```|Answer\s*[:：]|答案\s*[:：]|Output\s*$|\*\*Explanation\*\*)",
            block,
            re.IGNORECASE | re.MULTILINE,
        )
        if stop_match:
            option_region_end = stop_match.start()
        option_region = block[:option_region_end]

        options: list[dict[str, str]] = []
        for match in re.finditer(r"^\s*(?:\*\*?)?\s*([A-D])[).:\-]\s*([^\n`]+?)\s*$", option_region, re.MULTILINE):
            options.append({"key": match.group(1).upper(), "text": match.group(2).strip()})
        if not options:
            bullet_options = [m.group(1).strip() for m in re.finditer(r"^\s*\*\s+([^\n`]+?)\s*$", option_region, re.MULTILINE)]
            if 2 <= len(bullet_options) <= 6:
                for idx, text in enumerate(bullet_options, start=0):
                    options.append({"key": chr(ord("A") + idx), "text": text})
        if len(options) < 2:
            continue

        answer_keys: list[str] = []
        answer_match = re.search(r"(Answer|答案)\s*[:：]\s*([A-D])\b", block, re.IGNORECASE)
        if answer_match:
            answer_keys = [answer_match.group(2).upper()]
        else:
            for fenced in re.findall(r"```(?:\w+)?\n([\s\S]*?)```", block):
                candidate = fenced.strip().splitlines()[0].strip() if fenced.strip() else ""
                if re.match(r"^[A-D][).:\-]\s*", candidate, re.IGNORECASE):
                    answer_keys = [candidate[0].upper()]
                    break
                for opt in options:
                    if candidate and candidate.lower() == opt["text"].strip().lower():
                        answer_keys = [opt["key"]]
                        break
                if answer_keys:
                    break

        explanation = ""
        explanation_match = re.search(r"\*\*Explanation\*\*\s*[:：]\s*(.+)$", block, re.IGNORECASE | re.MULTILINE)
        if explanation_match:
            explanation = explanation_match.group(1).strip()

        if len(answer_keys) == 1 and answer_keys[0] in {o["key"] for o in options}:
            rows.append(
                {
                    "stem": stem,
                    "options": options,
                    "answer_keys": answer_keys,
                    "explanation": explanation,
                }
            )
    return rows


def parse_web_markdown_mcq(content: str) -> list[dict[str, Any]]:
    """解析 Web/JS 题库中的选择题。"""
    blocks = re.split(r"\n(?=#+\s*\d+\.)", content)
    rows: list[dict[str, Any]] = []
    for block in blocks:
        title_match = re.search(r"^#+\s*\d+\.\s*(.+)$", block, re.MULTILINE)
        if not title_match:
            continue
        stem = title_match.group(1).strip()
        options: list[dict[str, str]] = []
        for match in re.finditer(r"^\s*[-*]\s*([A-D])[:.)-]\s*(.+)$", block, re.MULTILINE):
            options.append({"key": match.group(1).upper(), "text": match.group(2).strip()})
        if len(options) < 2:
            continue
        answer_match = re.search(r"(Answer|答案)\s*[:：]\s*\**\s*([A-D])\b", block, re.IGNORECASE)
        if not answer_match:
            continue
        answer_key = answer_match.group(2).upper()
        if answer_key not in {o["key"] for o in options}:
            continue
        explanation = ""
        explanation_match = re.search(r"(Explanation|解释|解析)\s*[:：]\s*(.+)$", block, re.IGNORECASE | re.DOTALL)
        if explanation_match:
            explanation = explanation_match.group(2).strip()
        rows.append(
            {
                "stem": stem,
                "options": options,
                "answer_keys": [answer_key],
                "explanation": explanation,
            }
        )
    return rows


def normalize_options(options: list[dict[str, str]]) -> list[dict[str, str]]:
    """去重并规范化选项，保证 key 唯一且 (key,text) 不重复。"""
    normalized: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_keys: set[str] = set()
    for option in options:
        key = str(option.get("key", "")).strip().upper()
        text = re.sub(r"\s+", " ", str(option.get("text", "")).strip())
        if not key or not text:
            continue
        pair = (key, text)
        if pair in seen_pairs:
            continue
        if key in seen_keys:
            continue
        seen_pairs.add(pair)
        seen_keys.add(key)
        normalized.append({"key": key, "text": text})
    return normalized


def validate_question(row: dict[str, Any]) -> bool:
    """统一校验题目结构，失败返回 False。"""
    options = normalize_options(row.get("options", []))
    answer_keys = [str(k).strip().upper() for k in row.get("answer_keys", []) if str(k).strip()]
    option_keys = [opt["key"] for opt in options]
    if len(options) < 2 or len(options) > 6:
        return False
    if len(option_keys) != len(set(option_keys)):
        return False
    if len(answer_keys) != 1:
        return False
    if answer_keys[0] not in set(option_keys):
        return False
    row["options"] = options
    row["answer_keys"] = answer_keys
    return True


def parse_mcq(domain: str, content: str) -> list[dict[str, Any]]:
    """根据领域选择解析器。"""
    if domain == "java":
        return parse_java_markdown_mcq(content)
    return parse_web_markdown_mcq(content)


def count_candidates(domain: str, content: str) -> int:
    """统计候选题块数量，用于过滤率报告。"""
    if domain == "java":
        return len(re.findall(r"^##\s*Q\.", content, re.MULTILINE))
    return len(re.findall(r"^#+\s*\d+\.", content, re.MULTILINE))


def load_checkpoint(path: Path) -> dict[str, Any]:
    """读取检查点，失败时返回空结构。"""
    if not path.exists():
        return {"completed": {}, "errors": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"completed": {}, "errors": {}}


def save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    """保存检查点内容。"""
    write_json(path, payload)


def load_existing_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    """读取既有结果，按 source_key 分组以支持失败恢复。"""
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        meta = row.get("metadata", {})
        source_key = meta.get("source_key", "")
        if not source_key:
            continue
        grouped.setdefault(source_key, []).append(row)
    return grouped


def main() -> int:
    """执行选择题清洗流程。"""
    args = parse_args()
    sources = load_sources(Path(args.sources))
    checkpoint = load_checkpoint(Path(args.checkpoint))
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing_rows = load_existing_rows(Path(args.output))
    source_rows_map: dict[str, list[dict[str, Any]]] = {}

    filtered_count = 0
    failed_count = 0
    validation_filtered_count = 0
    domain_stats_raw: dict[str, int] = {"java": 0, "web": 0}
    candidate_total = 0
    recovered_sources = 0

    for source in sources:
        source_key = f"{source.repo_full_name}::{source.entry_file}"
        try:
            cache_file = cache_dir / f"{stable_id(source.repo_full_name, source.entry_file)}.md"
            if cache_file.exists():
                content = cache_file.read_text(encoding="utf-8")
            else:
                content = http_get_text(source.raw_url, args.retry)
                cache_file.write_text(content, encoding="utf-8")
            candidate_total += count_candidates(source.domain, content)
            questions = parse_mcq(source.domain, content)
            source_total = len(questions)
            source_rows_map[source_key] = []
            commit_or_tag = checkpoint.get("completed", {}).get(source_key, {}).get("commit_or_tag", "HEAD")
            for q in questions:
                q["options"] = normalize_options(q.get("options", []))
                if not validate_question(q):
                    validation_filtered_count += 1
                    continue
                question_id = stable_id(source.domain, source.repo_full_name, source.entry_file, q["stem"])
                source_rows_map[source_key].append(
                    {
                        "question_id": question_id,
                        "domain": source.domain,
                        "question_type": "single_choice",
                        "stem": q["stem"],
                        "options": q["options"],
                        "answer_keys": q["answer_keys"],
                        "explanation": q.get("explanation", ""),
                        "source": {
                            "repo_full_name": source.repo_full_name,
                            "url": source.url,
                            "license": source.license_name,
                            "commit_or_tag": commit_or_tag,
                        },
                        "metadata": {
                            "entry_file": source.entry_file,
                            "default_branch": "HEAD",
                            "source_key": source_key,
                        },
                    }
                )
            domain_stats_raw[source.domain] += source_total
            checkpoint["completed"][source_key] = {
                "count": source_total,
                "updated_at": int(time.time()),
                "commit_or_tag": commit_or_tag,
            }
            checkpoint["errors"].pop(source_key, None)
            save_checkpoint(Path(args.checkpoint), checkpoint)
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            if source_key in existing_rows:
                source_rows_map[source_key] = existing_rows[source_key]
                recovered_sources += 1
            checkpoint["errors"][source_key] = str(exc)
            save_checkpoint(Path(args.checkpoint), checkpoint)

    normalized_rows = [row for rows in source_rows_map.values() for row in rows]
    deduped = {row["question_id"]: row for row in normalized_rows}
    total_count = len(deduped)
    rows_sorted = sorted(deduped.values(), key=lambda x: (x["domain"], x["question_id"]))
    output_domain_distribution: dict[str, int] = {"java": 0, "web": 0}
    for row in rows_sorted:
        output_domain_distribution[row["domain"]] = output_domain_distribution.get(row["domain"], 0) + 1
    filtered_count = max(0, candidate_total - total_count)

    report = {
        "total_count": total_count,
        "filtered_count": filtered_count,
        "validation_filtered_count": validation_filtered_count,
        "failed_count": failed_count,
        "domain_distribution": output_domain_distribution,
        "domain_distribution_raw": domain_stats_raw,
        "sources_total": len(sources),
        "recovered_sources": recovered_sources,
        "generated_at": int(time.time()),
    }

    if not args.dry_run:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(rows_sorted, ensure_ascii=False, indent=2), encoding="utf-8")
        write_json(Path(args.report), report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
