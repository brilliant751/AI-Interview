"""基于可靠来源题库重建中文选择题数据（离线翻译）。"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import argostranslate.package as argos_package
import argostranslate.translate as argos_translate


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="重建中文选择题数据")
    parser.add_argument(
        "--input",
        default="backend/assets/material/choice/normalized/choice_questions.json",
        help="可靠来源归一化题库输入路径",
    )
    parser.add_argument(
        "--output",
        default="data/converted/choice_questions_zh_reliable.json",
        help="中文题库输出路径",
    )
    parser.add_argument(
        "--report",
        default="data/reports/choice_questions_rebuild_report.json",
        help="重建报告路径",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    """读取输入题库。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("输入数据格式错误，期望 JSON 数组")
    return [row for row in payload if isinstance(row, dict)]


def looks_english(text: str) -> bool:
    """判断文本是否主要由英文组成。"""
    if not text.strip():
        return False
    letters = re.findall(r"[A-Za-z]", text)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    return len(letters) >= 6 and len(cjk) * 2 < len(letters)


def maybe_translate(text: str) -> tuple[str, bool]:
    """按需翻译文本。"""
    if not looks_english(text):
        return text, False
    translated = argos_translate.translate(text, "en", "zh")
    return translated or text, True


def translate_options(options: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """翻译选项内容并保留 key。"""
    translated_count = 0
    result: list[dict[str, str]] = []
    for option in options:
        key = str(option.get("key") or "").strip().upper()
        text = str(option.get("text") or "")
        next_text, changed = maybe_translate(text)
        if changed:
            translated_count += 1
        result.append({"key": key, "text": next_text})
    return result, translated_count


def ensure_argos_en_zh_package() -> None:
    """确保已安装 en->zh 的 Argos 翻译模型包。"""
    try:
        probe = argos_translate.translate("hello", "en", "zh")
        if probe:
            return
    except Exception:
        pass
    if argos_package.get_available_packages() is None:
        argos_package.update_package_index()
    package = next(
        (
            item
            for item in argos_package.get_available_packages()
            if item.from_code == "en" and item.to_code.startswith("zh")
        ),
        None,
    )
    if package is None:
        return
    downloaded_path = package.download()
    argos_package.install_from_path(downloaded_path)


def main() -> int:
    """执行重建流程。"""
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)
    rows = load_rows(input_path)
    ensure_argos_en_zh_package()

    out_rows: list[dict[str, Any]] = []
    stem_changed = 0
    explanation_changed = 0
    option_changed = 0
    for row in rows:
        item = dict(row)
        stem = str(item.get("stem") or "")
        stem_next, stem_hit = maybe_translate(stem)
        if stem_hit:
            stem_changed += 1
        item["stem"] = stem_next

        options = item.get("options") or []
        if isinstance(options, list):
            normalized_options = []
            for option in options:
                if isinstance(option, dict):
                    normalized_options.append({"key": str(option.get("key") or ""), "text": str(option.get("text") or "")})
            translated_options, changed_count = translate_options(normalized_options)
            option_changed += changed_count
            item["options"] = translated_options

        explanation = str(item.get("explanation") or "")
        explanation_next, explanation_hit = maybe_translate(explanation)
        if explanation_hit:
            explanation_changed += 1
        item["explanation"] = explanation_next
        out_rows.append(item)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "input": str(input_path),
        "output": str(output_path),
        "total": len(out_rows),
        "translated_stem": stem_changed,
        "translated_option_items": option_changed,
        "translated_explanation": explanation_changed,
        "generated_at": int(time.time()),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
