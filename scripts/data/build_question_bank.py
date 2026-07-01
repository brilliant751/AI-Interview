"""将规范化题库 JSONL 导入 SQLite，支持重复执行。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from common import REPO_ROOT, write_json


# build_question_bank 将 normalized JSONL 写入 SQLite：
# 1. 输入来自 normalize_materials 生成的 *_question_bank.jsonl。
# 2. 使用 INSERT ... ON CONFLICT 支持重复执行和增量修正材料。
# 3. dry-run 只生成统计报告，不改动数据库。
# 4. 构建报告写入 data/reports，方便管理端或 CI 查看本次导入数量。
# 5. 表结构在脚本内初始化，保证空数据库也能直接构建题库。

def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="构建题库 SQLite 数据")
    parser.add_argument(
        "--input-dir",
        default=str(REPO_ROOT / "data" / "normalized"),
        help="规范化输入目录",
    )
    parser.add_argument(
        "--db-path",
        default=str(REPO_ROOT / "data" / "sqlite" / "interview.db"),
        help="SQLite 输出路径",
    )
    parser.add_argument(
        "--report",
        default=str(REPO_ROOT / "data" / "reports" / "question_bank_build_report.json"),
        help="构建报告输出路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入数据库")
    return parser.parse_args()


def init_schema(conn: sqlite3.Connection) -> None:
    """初始化题库表结构和必要索引。"""
    # WAL 模式提升本地读写并发体验，前端查询和脚本导入互不容易阻塞。
    # record_id 是稳定主键，role + question_no 索引用于管理端列表排序和查询。
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
    # 统一读取所有岗位题库文件，文件名中的 role 已经在记录里保留。
    # 空行跳过，避免手工编辑 JSONL 时多出的空白影响导入。
    rows: list[dict] = []
    for file_path in sorted(input_dir.glob("*_question_bank.jsonl")):
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    return rows


def upsert_rows(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    """执行批量 upsert 并返回成功数与失败数。"""
    # 单条失败不阻断整个批次，最终通过 failed 数量和退出码暴露问题。
    # 这有利于在材料部分损坏时仍能导入其他有效题目，并在报告中定位坏数据。
    ok = 0
    failed = 0
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
    for row in rows:
        try:
            conn.execute(
                sql,
                (
                    row["record_id"],
                    row["role"],
                    row["question_no"],
                    row["title"],
                    row.get("category", ""),
                    row["question"],
                    row.get("analysis", ""),
                    row["source_path"],
                    row.get("raw_markdown", ""),
                ),
            )
            ok += 1
        except Exception:
            failed += 1
    return ok, failed


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
        with conn:
            ok, failed = upsert_rows(conn, rows)
        report = {"total_rows": len(rows), "inserted_or_updated": ok, "failed": failed, "dry_run": False}
        write_json(Path(args.report), report)
        print("题库构建完成：" + json.dumps(report, ensure_ascii=False))
        print(f"数据库路径：{db_path}")
        return 0 if failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
