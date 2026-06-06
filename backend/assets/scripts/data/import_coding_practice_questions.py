"""将编程练习题 JSON 导入 coding_questions 表，支持幂等重复执行。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from common import DATA_ROOT, write_json


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="导入编程练习题到 SQLite")
    parser.add_argument(
        "--input",
        default=str(Path("backend/assets/material/coding/programming_practice_questions.json")),
        help="编程题 JSON 文件路径",
    )
    parser.add_argument(
        "--db-path",
        default=str(DATA_ROOT / "sqlite" / "interview.db"),
        help="SQLite 输出路径",
    )
    parser.add_argument(
        "--report",
        default=str(DATA_ROOT / "reports" / "coding_practice_question_import_report.json"),
        help="导入报告输出路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入数据库")
    return parser.parse_args()


def init_schema(conn: sqlite3.Connection) -> None:
    """初始化编程题表结构。"""
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coding_questions (
          question_id TEXT PRIMARY KEY,
          slug TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          difficulty TEXT NOT NULL,
          topic_tags TEXT NOT NULL DEFAULT '[]',
          prompt_markdown TEXT NOT NULL,
          input_spec TEXT NOT NULL,
          output_spec TEXT NOT NULL,
          constraints_text TEXT NOT NULL DEFAULT '',
          sample_cases TEXT NOT NULL DEFAULT '[]',
          judge_cases TEXT NOT NULL DEFAULT '[]',
          self_test_case TEXT NOT NULL DEFAULT '{}',
          starter_codes TEXT NOT NULL DEFAULT '{}',
          source TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_coding_questions_difficulty ON coding_questions(difficulty, question_id);")


def read_rows(input_path: Path) -> list[dict]:
    """读取编程题 JSON。"""
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("编程题输入文件格式错误，期望 JSON 数组")
    return payload


def _validate_row(row: dict) -> None:
    """校验单题结构。"""
    judge_cases = row.get("judge_cases") or []
    self_test_case = row.get("self_test_case") or {}
    starter_codes = row.get("starter_codes") or {}
    if len(judge_cases) < 10:
        raise RuntimeError(f"题目 {row.get('question_id') or row.get('slug') or 'unknown'} 的正式测试用例少于 10 条")
    if not isinstance(self_test_case, dict) or not self_test_case.get("input") or not self_test_case.get("output"):
        raise RuntimeError(f"题目 {row.get('question_id') or row.get('slug') or 'unknown'} 缺少有效自测用例")
    for language in ("cpp", "java", "javascript"):
        if not str(starter_codes.get(language) or "").strip():
            raise RuntimeError(f"题目 {row.get('question_id') or row.get('slug') or 'unknown'} 缺少 {language} starter code")


def upsert_rows(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    """幂等写入编程题记录，并返回成功数与跳过数。"""
    upserted = 0
    skipped = 0
    sql = """
        INSERT INTO coding_questions(
          question_id, slug, title, difficulty, topic_tags, prompt_markdown, input_spec, output_spec,
          constraints_text, sample_cases, judge_cases, self_test_case, starter_codes, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
          slug = excluded.slug,
          title = excluded.title,
          difficulty = excluded.difficulty,
          topic_tags = excluded.topic_tags,
          prompt_markdown = excluded.prompt_markdown,
          input_spec = excluded.input_spec,
          output_spec = excluded.output_spec,
          constraints_text = excluded.constraints_text,
          sample_cases = excluded.sample_cases,
          judge_cases = excluded.judge_cases,
          self_test_case = excluded.self_test_case,
          starter_codes = excluded.starter_codes,
          source = excluded.source,
          updated_at = datetime('now');
    """
    for row in rows:
        _validate_row(row)
        conn.execute(
            sql,
            (
                str(row["question_id"]),
                str(row["slug"]),
                str(row["title"]),
                str(row["difficulty"]),
                json.dumps(row.get("topic_tags") or [], ensure_ascii=False),
                str(row["prompt_markdown"]),
                str(row["input_spec"]),
                str(row["output_spec"]),
                str(row.get("constraints_text") or ""),
                json.dumps(row.get("sample_cases") or [], ensure_ascii=False),
                json.dumps(row.get("judge_cases") or [], ensure_ascii=False),
                json.dumps(row.get("self_test_case") or {}, ensure_ascii=False),
                json.dumps(row.get("starter_codes") or {}, ensure_ascii=False),
                json.dumps(row.get("source") or {}, ensure_ascii=False),
            ),
        )
        upserted += 1
    return upserted, skipped


def main() -> int:
    """执行编程题导入。"""
    args = parse_args()
    input_path = Path(args.input)
    db_path = Path(args.db_path)
    report_path = Path(args.report)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_rows(input_path)
    if args.dry_run:
        report = {"total_rows": len(rows), "upserted": 0, "skipped": 0, "dry_run": True}
        write_json(report_path, report)
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        init_schema(conn)
        with conn:
            upserted, skipped = upsert_rows(conn, rows)
        report = {
            "total_rows": len(rows),
            "upserted": upserted,
            "skipped": skipped,
            "dry_run": False,
        }
        write_json(report_path, report)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
