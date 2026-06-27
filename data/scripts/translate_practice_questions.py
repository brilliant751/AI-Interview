"""批量翻译 practice_choice_questions 的英文题目数据到中文。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ctranslate2
import sentencepiece as spm
from huggingface_hub import snapshot_download


# 翻译脚本用于把英文选择题离线转换为中文：
# 1. 输入可以来自 SQLite 表，也可以来自 JSON 文件，便于不同数据来源复用。
# 2. LocalTranslator 基于 CTranslate2/SentencePiece，本地 CPU 推理，不依赖在线翻译接口。
# 3. TranslationStats 记录字段级翻译数量和异常数据，便于人工复核。
# 4. dry-run 可以只统计需要翻译的内容，不写输出文件。
# 5. 内存 cache 按原文去重，减少相同选项或解释重复翻译的成本。

@dataclass
class TranslationStats:
    """翻译统计数据。"""

    total_rows: int = 0
    translated_rows: int = 0
    translated_stem: int = 0
    translated_options: int = 0
    translated_explanation: int = 0
    skipped_empty: int = 0
    json_non_dict_items: int = 0
    warnings: list[str] | None = None
    dry_run: bool = False


class LocalTranslator:
    """本地翻译器，基于 CTranslate2 和 SentencePiece。"""

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.translator = ctranslate2.Translator(str(model_dir), device="cpu")
        self.source_sp = spm.SentencePieceProcessor(model_file=str(resolve_sp_model(model_dir, "source")))
        self.target_sp = spm.SentencePieceProcessor(model_file=str(resolve_sp_model(model_dir, "target")))
        self.cache: dict[str, str] = {}

    def translate(self, text: str) -> str:
        """翻译单段文本并使用内存缓存减少重复计算。"""
        # 很多选择题选项会重复出现，例如 True/False、None of the above。
        # 使用原文缓存可以明显减少本地模型推理次数。
        if text in self.cache:
            return self.cache[text]
        source_tokens = self.source_sp.encode(text, out_type=str)
        results = self.translator.translate_batch([source_tokens], beam_size=4)
        if not results or not results[0].hypotheses or not results[0].hypotheses[0]:
            raise RuntimeError(f"翻译结果为空，无法完成推理。输入文本前 80 字符：{text[:80]}")
        target_tokens = results[0].hypotheses[0]
        translated = self.target_sp.decode(target_tokens)
        self.cache[text] = translated
        return translated


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="批量翻译 practice_choice_questions 英文数据到中文")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-sqlite",
        default=None,
        help="SQLite 文件路径，读取表 practice_choice_questions",
    )
    input_group.add_argument(
        "--input-json",
        default=None,
        help="英文题目 JSON 输入路径（数组格式）",
    )
    parser.add_argument(
        "--output-json",
        default="data/converted/practice_choice_questions_zh.json",
        help="翻译后 JSON 输出路径",
    )
    parser.add_argument(
        "--report-json",
        default="data/reports/translation_report.json",
        help="翻译报告输出路径",
    )
    parser.add_argument(
        "--export-raw-json",
        default="data/raw/practice_choice_questions_en.json",
        help="当输入为 SQLite 时，导出的原始英文 JSON 路径",
    )
    parser.add_argument(
        "--model-repo",
        default="gaudi/opus-mt-en-zh-ctranslate2",
        help="HuggingFace 模型仓库（CTranslate2 格式）",
    )
    parser.add_argument(
        "--model-dir",
        default="data/models/opus-mt-en-zh-ctranslate2",
        help="本地模型目录，不存在则自动下载",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="仅处理前 N 条，0 表示全部处理",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅运行翻译流程，不写出翻译结果文件")
    return parser.parse_args()


def ensure_model_files(model_repo: str, model_dir: Path) -> None:
    """确保本地存在 CTranslate2 模型目录。"""
    if (model_dir / "model.bin").exists():
        return
    model_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=model_repo, local_dir=str(model_dir), local_dir_use_symlinks=False)
    if not (model_dir / "model.bin").exists():
        raise FileNotFoundError(
            f"模型目录缺少 model.bin：{model_dir}。请提供可直接用于 CTranslate2 的模型仓库或本地目录。"
        )


def resolve_sp_model(model_dir: Path, model_type: str) -> Path:
    """解析 SentencePiece 模型路径。"""
    candidates = {
        "source": ["source.spm", "sentencepiece.model", "spm.model"],
        "target": ["target.spm", "sentencepiece.model", "spm.model"],
    }
    for file_name in candidates[model_type]:
        candidate = model_dir / file_name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"未找到 {model_type} SentencePiece 模型文件，目录：{model_dir}")


def read_from_sqlite(db_path: Path) -> list[dict[str, Any]]:
    """读取 SQLite 题库记录。"""
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite 文件不存在：{db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              question_id,
              domain,
              question_type,
              stem,
              options,
              answer_keys,
              explanation,
              source,
              metadata,
              created_at,
              updated_at
            FROM practice_choice_questions
            ORDER BY created_at ASC, question_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def read_from_json(json_path: Path) -> tuple[list[dict[str, Any]], int]:
    """读取 JSON 输入记录。"""
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在：{json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("JSON 输入必须是数组格式")
    rows: list[dict[str, Any]] = []
    non_dict_count = 0
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
        else:
            non_dict_count += 1
    return rows, non_dict_count


def write_json_file(path: Path, payload: Any) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_parse_options(raw_options: Any, row_index: int, question_id: str) -> list[Any]:
    """将 options 解析为数组。"""
    if isinstance(raw_options, list):
        return raw_options
    if isinstance(raw_options, str):
        text = raw_options.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"options JSON 解析失败：question_id={question_id}, row_index={row_index}, error={exc}"
            ) from exc
        if isinstance(parsed, list):
            return parsed
    raise ValueError(f"options 字段无法解析为 JSON 数组：question_id={question_id}, row_index={row_index}")


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    """仅校验题目关键字段结构，供 dry-run 使用。"""
    stem_count = 0
    option_count = 0
    explanation_count = 0
    for row_index, row in enumerate(rows):
        question_id = str(row.get("question_id", ""))
        if isinstance(row.get("stem"), str) and row.get("stem", "").strip():
            stem_count += 1
        options = safe_parse_options(row.get("options", "[]"), row_index=row_index, question_id=question_id)
        option_count += len(options)
        if isinstance(row.get("explanation"), str) and row.get("explanation", "").strip():
            explanation_count += 1
    return {
        "valid_stem_rows": stem_count,
        "valid_option_items": option_count,
        "valid_explanation_rows": explanation_count,
    }


def translate_text(text: Any, translator: LocalTranslator, stats: TranslationStats) -> tuple[str, bool]:
    """翻译文本并更新统计。"""
    if not isinstance(text, str):
        return "", False
    if not text.strip():
        stats.skipped_empty += 1
        return text, False
    return translator.translate(text), True


def translate_option_item(item: Any, translator: LocalTranslator, stats: TranslationStats) -> Any:
    """翻译单个选项对象。"""
    if isinstance(item, str):
        translated_text, translated = translate_text(item, translator, stats)
        if translated:
            stats.translated_options += 1
        return translated_text
    if isinstance(item, dict):
        translated_item = dict(item)
        translated = False
        for key in ("text", "content", "label"):
            value = translated_item.get(key)
            if isinstance(value, str) and value.strip():
                translated_text, translated_once = translate_text(value, translator, stats)
                translated_item[key] = translated_text
                translated = translated or translated_once
        if translated:
            stats.translated_options += 1
        return translated_item
    return item


def translate_rows(rows: list[dict[str, Any]], translator: LocalTranslator) -> tuple[list[dict[str, Any]], TranslationStats]:
    """批量翻译题目字段。"""
    stats = TranslationStats(total_rows=len(rows))
    translated_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        translated_row = dict(row)
        question_id = str(translated_row.get("question_id", ""))
        if isinstance(translated_row.get("stem"), str):
            translated_stem_text, translated = translate_text(translated_row["stem"], translator, stats)
            translated_row["stem"] = translated_stem_text
            if translated:
                stats.translated_stem += 1

        options_array = safe_parse_options(
            translated_row.get("options", "[]"), row_index=row_index, question_id=question_id
        )
        translated_options = [
            translate_option_item(option_item, translator, stats) for option_item in options_array
        ]
        translated_row["options"] = json.dumps(translated_options, ensure_ascii=False)

        if isinstance(translated_row.get("explanation"), str):
            translated_explanation_text, translated = translate_text(translated_row["explanation"], translator, stats)
            translated_row["explanation"] = translated_explanation_text
            if translated:
                stats.translated_explanation += 1

        translated_rows.append(translated_row)
        stats.translated_rows += 1
    return translated_rows, stats


def main() -> int:
    """执行翻译流程并输出结果。"""
    args = parse_args()
    input_sqlite = Path(args.input_sqlite).resolve() if args.input_sqlite else None
    input_json = Path(args.input_json).resolve() if args.input_json else None
    output_json_path = Path(args.output_json).resolve()
    report_json_path = Path(args.report_json).resolve()
    export_raw_path = Path(args.export_raw_json).resolve()

    if input_sqlite is not None:
        rows = read_from_sqlite(input_sqlite)
        json_non_dict_items = 0
        write_json_file(export_raw_path, rows)
        print(f"已导出英文原始数据：{export_raw_path}")
    else:
        rows, json_non_dict_items = read_from_json(input_json)  # type: ignore[arg-type]

    if args.limit > 0:
        rows = rows[: args.limit]

    model_dir = Path(args.model_dir).resolve()

    if args.dry_run:
        dry_run_validation = validate_rows(rows)
        stats = TranslationStats(total_rows=len(rows), json_non_dict_items=json_non_dict_items, warnings=[], dry_run=True)
        if json_non_dict_items > 0:
            stats.warnings.append(f"输入 JSON 含非对象项，已跳过：{json_non_dict_items} 条")
            print(f"告警：输入 JSON 含非对象项，已跳过 {json_non_dict_items} 条")
        report_payload = {
            "input_mode": "sqlite" if input_sqlite else "json",
            "input_sqlite": str(input_sqlite) if input_sqlite else "",
            "input_json": str(input_json) if input_json else "",
            "output_json": str(output_json_path),
            "report_json": str(report_json_path),
            "model_repo": args.model_repo,
            "model_dir": str(model_dir),
            "total_rows": stats.total_rows,
            "translated_rows": 0,
            "translated_stem": 0,
            "translated_options": 0,
            "translated_explanation": 0,
            "skipped_empty": 0,
            "json_non_dict_items": stats.json_non_dict_items,
            "warnings": stats.warnings,
            "dry_run": True,
            "validation": dry_run_validation,
        }
        write_json_file(report_json_path, report_payload)
        print("dry-run 完成：未执行模型翻译，仅完成数据校验与统计")
        print(f"报告文件：{report_json_path}")
        return 0

    ensure_model_files(args.model_repo, model_dir)
    translator = LocalTranslator(model_dir=model_dir)
    translated_rows, stats = translate_rows(rows, translator)
    stats.json_non_dict_items = json_non_dict_items
    stats.warnings = []
    if json_non_dict_items > 0:
        stats.warnings.append(f"输入 JSON 含非对象项，已跳过：{json_non_dict_items} 条")
        print(f"告警：输入 JSON 含非对象项，已跳过 {json_non_dict_items} 条")
    stats.dry_run = False

    report_payload = {
        "input_mode": "sqlite" if input_sqlite else "json",
        "input_sqlite": str(input_sqlite) if input_sqlite else "",
        "input_json": str(input_json) if input_json else "",
        "output_json": str(output_json_path),
        "report_json": str(report_json_path),
        "model_repo": args.model_repo,
        "model_dir": str(model_dir),
        "total_rows": stats.total_rows,
        "translated_rows": stats.translated_rows,
        "translated_stem": stats.translated_stem,
        "translated_options": stats.translated_options,
        "translated_explanation": stats.translated_explanation,
        "skipped_empty": stats.skipped_empty,
        "json_non_dict_items": stats.json_non_dict_items,
        "warnings": stats.warnings,
        "dry_run": stats.dry_run,
    }

    write_json_file(output_json_path, translated_rows)
    write_json_file(report_json_path, report_payload)
    print(f"翻译结果文件：{output_json_path}")
    print(f"报告文件：{report_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
