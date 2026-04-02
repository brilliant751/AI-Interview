"""面试领域 SQLite 仓储实现。"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class InterviewRepository:
    """面试数据访问层。"""

    def __init__(self, db_path: str):
        """初始化仓储并保存数据库路径。"""
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _session(self):
        """创建自动关闭的数据库会话。"""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """初始化核心表结构。"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._session() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                  resume_id TEXT PRIMARY KEY,
                  filename TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'PENDING',
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_sessions (
                  interview_id TEXT PRIMARY KEY,
                  resume_id TEXT NOT NULL,
                  job_role TEXT NOT NULL,
                  difficulty TEXT NOT NULL,
                  input_mode TEXT NOT NULL,
                  output_mode TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  current_stage TEXT NOT NULL DEFAULT 'SELF_INTRO',
                  follow_up_count INTEGER NOT NULL DEFAULT 0,
                  technical_count INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_turns (
                  turn_id TEXT PRIMARY KEY,
                  interview_id TEXT NOT NULL,
                  stage TEXT NOT NULL,
                  answer_text TEXT NOT NULL,
                  next_question TEXT NOT NULL,
                  live_score INTEGER NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_reports (
                  interview_id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  overall_score INTEGER,
                  strengths TEXT NOT NULL DEFAULT '[]',
                  weaknesses TEXT NOT NULL DEFAULT '[]',
                  suggestions TEXT NOT NULL DEFAULT '[]',
                  error_message TEXT,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS request_idempotency (
                  endpoint TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  response_body TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  PRIMARY KEY(endpoint, idempotency_key)
                );
                """
            )
            self._ensure_column(conn, "interview_sessions", "technical_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "interview_sessions", "follow_up_count", "INTEGER NOT NULL DEFAULT 0")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        """确保表包含指定列，缺失则补齐。"""
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        exists = any(str(row["name"]) == column for row in rows)
        if not exists:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def create_resume(self, filename: str) -> dict:
        """创建简历记录。"""
        resume_id = f"res_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                "INSERT INTO resumes(resume_id, filename, status) VALUES (?, ?, 'READY')",
                (resume_id, filename),
            )
        return {"resume_id": resume_id, "status": "READY"}

    def create_session(self, payload: dict) -> dict:
        """创建面试会话记录。"""
        interview_id = f"int_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions(
                  interview_id, resume_id, job_role, difficulty, input_mode, output_mode, status, current_stage, follow_up_count, technical_count
                ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', 'SELF_INTRO', 0, 0)
                """,
                (
                    interview_id,
                    payload["resume_id"],
                    payload["job_role"],
                    payload["difficulty"],
                    payload["input_mode"],
                    payload["output_mode"],
                ),
            )
        return {"interview_id": interview_id, "current_stage": "SELF_INTRO"}

    def get_session(self, interview_id: str) -> dict | None:
        """查询单个会话。"""
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_session_stage(
        self,
        interview_id: str,
        stage: str,
        follow_up_count: int,
        technical_count: int,
    ) -> None:
        """更新会话阶段和追问次数。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE interview_sessions
                SET current_stage = ?, follow_up_count = ?, technical_count = ?
                WHERE interview_id = ?
                """,
                (stage, follow_up_count, technical_count, interview_id),
            )

    def finish_session(self, interview_id: str) -> None:
        """标记会话为结束。"""
        with self._session() as conn:
            conn.execute(
                "UPDATE interview_sessions SET status='FINISHED', current_stage='END' WHERE interview_id = ?",
                (interview_id,),
            )

    def add_turn(self, interview_id: str, stage: str, answer_text: str, next_question: str, score: int) -> None:
        """写入单轮面试记录。"""
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_turns(turn_id, interview_id, stage, answer_text, next_question, live_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, interview_id, stage, answer_text, next_question, score),
            )

    def list_turns(self, interview_id: str) -> list[dict]:
        """获取会话所有轮次。"""
        with self._session() as conn:
            rows = conn.execute(
                "SELECT * FROM interview_turns WHERE interview_id = ? ORDER BY created_at ASC",
                (interview_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_report(self, interview_id: str, report: dict) -> None:
        """创建或更新报告记录。"""
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_reports(interview_id, status, overall_score, strengths, weaknesses, suggestions, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(interview_id) DO UPDATE SET
                  status = excluded.status,
                  overall_score = excluded.overall_score,
                  strengths = excluded.strengths,
                  weaknesses = excluded.weaknesses,
                  suggestions = excluded.suggestions,
                  error_message = excluded.error_message,
                  updated_at = datetime('now')
                """,
                (
                    interview_id,
                    report["status"],
                    report.get("overall_score"),
                    report.get("strengths", "[]"),
                    report.get("weaknesses", "[]"),
                    report.get("suggestions", "[]"),
                    report.get("error_message"),
                ),
            )

    def get_idempotent_response(self, endpoint: str, idempotency_key: str) -> str | None:
        """读取已缓存的幂等响应。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT response_body FROM request_idempotency
                WHERE endpoint = ? AND idempotency_key = ?
                """,
                (endpoint, idempotency_key),
            ).fetchone()
        return row["response_body"] if row else None

    def save_idempotent_response(self, endpoint: str, idempotency_key: str, response_body: str) -> None:
        """写入幂等响应缓存。"""
        with self._session() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO request_idempotency(endpoint, idempotency_key, response_body)
                VALUES (?, ?, ?)
                """,
                (endpoint, idempotency_key, response_body),
            )

    def get_report(self, interview_id: str) -> dict | None:
        """查询报告状态。"""
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM interview_reports WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_history(self, job_role: str | None, offset: int, limit: int) -> tuple[list[dict], int]:
        """分页查询历史会话。"""
        where = ""
        params: list[object] = []
        if job_role:
            where = "WHERE s.job_role = ?"
            params.append(job_role)
        with self._session() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) AS cnt FROM interview_sessions s {where}",
                params,
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""
                SELECT s.interview_id, s.job_role, s.created_at, r.overall_score
                FROM interview_sessions s
                LEFT JOIN interview_reports r ON r.interview_id = s.interview_id
                {where}
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], int(total)
