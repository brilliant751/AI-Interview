"""将选择题 JSON 导入 practice_choice_questions 表，支持幂等重复执行。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from common import DATA_ROOT, write_json


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="导入选择题到练习专用题库表")
    parser.add_argument(
        "--input",
        default=str(Path("backend/assets/material/choice/normalized/choice_questions.json")),
        help="选择题 JSON 文件路径",
    )
    parser.add_argument(
        "--db-path",
        default=str(DATA_ROOT / "sqlite" / "interview.db"),
        help="SQLite 输出路径",
    )
    parser.add_argument(
        "--report",
        default=str(DATA_ROOT / "reports" / "practice_choice_question_import_report.json"),
        help="导入报告输出路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入数据库")
    return parser.parse_args()


def init_schema(conn: sqlite3.Connection) -> None:
    """初始化练习选择题表结构和索引。"""
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS practice_choice_questions (
          question_id TEXT PRIMARY KEY,
          domain TEXT NOT NULL,
          question_type TEXT NOT NULL CHECK(question_type = 'single_choice'),
          stem TEXT NOT NULL,
          options TEXT NOT NULL DEFAULT '[]',
          answer_keys TEXT NOT NULL DEFAULT '[]',
          explanation TEXT NOT NULL DEFAULT '',
          source TEXT NOT NULL DEFAULT '{}',
          metadata TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_practice_choice_domain_type ON practice_choice_questions(domain, question_type);"
    )


def read_rows(input_path: Path) -> list[dict]:
    """读取并解析选择题 JSON 列表。"""
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("选择题输入文件格式错误，期望 JSON 数组")
    return payload


def upsert_rows(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    """幂等写入选择题记录，并返回成功数与跳过数。"""
    upserted = 0
    skipped = 0
    sql = """
        INSERT INTO practice_choice_questions(
          question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
          domain = excluded.domain,
          question_type = excluded.question_type,
          stem = excluded.stem,
          options = excluded.options,
          answer_keys = excluded.answer_keys,
          explanation = excluded.explanation,
          source = excluded.source,
          metadata = excluded.metadata,
          updated_at = datetime('now');
    """
    for row in rows:
        question_type = str(row.get("question_type") or "")
        if question_type != "single_choice":
            skipped += 1
            continue
        conn.execute(
            sql,
            (
                str(row["question_id"]),
                str(row["domain"]),
                question_type,
                str(row["stem"]),
                json.dumps(row.get("options") or [], ensure_ascii=False),
                json.dumps(row.get("answer_keys") or [], ensure_ascii=False),
                str(row.get("explanation") or ""),
                json.dumps(row.get("source") or {}, ensure_ascii=False),
                json.dumps(row.get("metadata") or {}, ensure_ascii=False),
            ),
        )
        upserted += 1
    return upserted, skipped


def main() -> int:
    """执行选择题导入。"""
    args = parse_args()
    input_path = Path(args.input)
    db_path = Path(args.db_path)
    report_path = Path(args.report)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_rows(input_path)
    print(f"加载选择题记录：{len(rows)}")
    if args.dry_run:
        report = {"total_rows": len(rows), "upserted": 0, "skipped": 0, "dry_run": True}
        write_json(report_path, report)
        print(f"报告已输出：{report_path}")
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
        print("选择题导入完成：" + json.dumps(report, ensure_ascii=False))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
