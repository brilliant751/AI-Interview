"""将规范化题库 JSONL 导入 SQLite，支持重复执行。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from common import DATA_ROOT, write_json
from normalize_materials import normalize_question_category


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="构建题库 SQLite 数据")
    parser.add_argument(
        "--input-dir",
        default=str(DATA_ROOT / "normalized"),
        help="规范化输入目录",
    )
    parser.add_argument(
        "--db-path",
        default=str(DATA_ROOT / "sqlite" / "interview.db"),
        help="SQLite 输出路径",
    )
    parser.add_argument(
        "--report",
        default=str(DATA_ROOT / "reports" / "question_bank_build_report.json"),
        help="构建报告输出路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入数据库")
    return parser.parse_args()


def init_schema(conn: sqlite3.Connection) -> None:
    """初始化题库表结构和必要索引。"""
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS question_bank (
          record_id TEXT PRIMARY KEY,
          role TEXT NOT NULL,
          question_no INTEGER NOT NULL,
          title TEXT NOT NULL,
          category TEXT,
          question TEXT NOT NULL,
          analysis TEXT,
          source_path TEXT NOT NULL,
          raw_markdown TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_question_bank_role_no ON question_bank(role, question_no);"
    )


def iter_rows(input_dir: Path) -> list[dict]:
    """读取所有题库 JSONL 记录。"""
    rows: list[dict] = []
    for file_path in sorted(input_dir.glob("*_question_bank.jsonl")):
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    return rows


def group_rows_by_source(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """按岗位和源文件分组，便于以文件快照方式重建题库。"""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        group_key = (row["role"], row["source_path"])
        grouped.setdefault(group_key, []).append(row)
    return grouped


def upsert_rows(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    """按材料文件快照重建题库并返回成功数与失败数。"""
    ok = 0
    sql = """
        INSERT INTO question_bank (
          record_id, role, question_no, title, category, question, analysis, source_path, raw_markdown
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(record_id) DO UPDATE SET
          role=excluded.role,
          question_no=excluded.question_no,
          title=excluded.title,
          category=excluded.category,
          question=excluded.question,
          analysis=excluded.analysis,
          source_path=excluded.source_path,
          raw_markdown=excluded.raw_markdown,
          updated_at=datetime('now');
    """
    grouped_rows = group_rows_by_source(rows)
    for (role, source_path), source_rows in grouped_rows.items():
        conn.execute("DELETE FROM question_bank WHERE role = ? AND source_path = ?", (role, source_path))
        for row in source_rows:
            try:
                conn.execute(
                    sql,
                    (
                        row["record_id"],
                        row["role"],
                        row["question_no"],
                        row["title"],
                        normalize_question_category(row.get("category", "")),
                        row["question"],
                        row.get("analysis", ""),
                        row["source_path"],
                        row.get("raw_markdown", ""),
                    ),
                )
                ok += 1
            except Exception as exc:
                row_identity = {
                    "record_id": row.get("record_id", ""),
                    "role": row.get("role", ""),
                    "question_no": row.get("question_no", ""),
                    "source_path": row.get("source_path", ""),
                }
                raise RuntimeError(f"题库写入失败，记录标识：{json.dumps(row_identity, ensure_ascii=False)}") from exc
    return ok, 0


def main() -> int:
    """执行题库构建流程并输出报告。"""
    args = parse_args()
    input_dir = Path(args.input_dir)
    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rows = iter_rows(input_dir)
    print(f"加载题库记录：{len(rows)}")

    if args.dry_run:
        print("当前为 dry-run，仅做统计不写库")
        report = {"total_rows": len(rows), "inserted_or_updated": 0, "failed": 0, "dry_run": True}
        write_json(Path(args.report), report)
        print(f"报告已输出：{args.report}")
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        init_schema(conn)
        try:
            with conn:
                ok, failed = upsert_rows(conn, rows)
        except RuntimeError as exc:
            report = {
                "total_rows": len(rows),
                "inserted_or_updated": 0,
                "failed": 1,
                "dry_run": False,
                "error": str(exc),
            }
            write_json(Path(args.report), report)
            print(str(exc))
            print(f"报告已输出：{args.report}")
            return 1
        report = {"total_rows": len(rows), "inserted_or_updated": ok, "failed": failed, "dry_run": False}
        write_json(Path(args.report), report)
        print("题库构建完成：" + json.dumps(report, ensure_ascii=False))
        print(f"数据库路径：{db_path}")
        return 0 if failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
