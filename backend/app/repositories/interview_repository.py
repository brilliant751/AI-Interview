"""面试领域 SQLite 仓储实现。"""

from __future__ import annotations

import json
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
        conn.execute("PRAGMA foreign_keys=ON;")
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

    def _practice_tables_sql(self) -> str:
        """返回题库练习域的表结构 DDL。"""
        return """
                CREATE TABLE IF NOT EXISTS practice_sessions (
                  practice_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  job_role TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  question_count INTEGER NOT NULL CHECK(question_count > 0),
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS practice_session_questions (
                  session_question_id TEXT PRIMARY KEY,
                  practice_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  question_order INTEGER NOT NULL CHECK(question_order > 0),
                  source_question_id TEXT,
                  category TEXT,
                  stem TEXT NOT NULL,
                  analysis TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  UNIQUE(practice_id, question_order),
                  UNIQUE(practice_id, session_question_id),
                  FOREIGN KEY (practice_id) REFERENCES practice_sessions(practice_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS practice_answers (
                  answer_id TEXT PRIMARY KEY,
                  practice_id TEXT NOT NULL,
                  session_question_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  answer_text TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  UNIQUE(practice_id, session_question_id),
                  FOREIGN KEY (practice_id) REFERENCES practice_sessions(practice_id) ON DELETE CASCADE,
                  FOREIGN KEY (practice_id, session_question_id) REFERENCES practice_session_questions(practice_id, session_question_id) ON DELETE CASCADE
                );
        """

    def _practice_indexes_sql(self) -> str:
        """返回题库练习域的索引 DDL。"""
        return """
                CREATE INDEX IF NOT EXISTS idx_practice_sessions_user_created ON practice_sessions(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_practice_questions_session_order ON practice_session_questions(practice_id, question_order ASC);
                CREATE INDEX IF NOT EXISTS idx_practice_answers_user_session ON practice_answers(user_id, practice_id, created_at ASC);
        """

    def init_schema(self) -> None:
        """初始化核心表结构。"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._session() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS resumes (
                  resume_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  filename TEXT NOT NULL,
                  storage_path TEXT,
                  status TEXT NOT NULL DEFAULT 'PENDING',
                  parsed_text TEXT NOT NULL DEFAULT '',
                  parse_error TEXT NOT NULL DEFAULT '',
                  is_deleted INTEGER NOT NULL DEFAULT 0,
                  deleted_at TEXT,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_sessions (
                  interview_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  resume_id TEXT NOT NULL,
                  session_name TEXT NOT NULL DEFAULT '',
                  question_types TEXT NOT NULL DEFAULT '[]',
                  job_role TEXT NOT NULL,
                  difficulty TEXT NOT NULL,
                  input_mode TEXT NOT NULL,
                  output_mode TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  current_stage TEXT NOT NULL DEFAULT 'SELF_INTRO',
                  follow_up_count INTEGER NOT NULL DEFAULT 0,
                  technical_count INTEGER NOT NULL DEFAULT 0,
                  duration_seconds INTEGER NOT NULL DEFAULT 0,
                  duration_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                  started_at TEXT NOT NULL DEFAULT (datetime('now')),
                  finished_at TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_turns (
                  turn_id TEXT PRIMARY KEY,
                  interview_id TEXT NOT NULL,
                  user_id TEXT,
                  stage TEXT NOT NULL,
                  answer_text TEXT NOT NULL,
                  next_question TEXT NOT NULL,
                  live_score INTEGER NOT NULL,
                                    generation_mode TEXT NOT NULL DEFAULT 'mock',
                  input_source TEXT,
                  asr_provider TEXT,
                  llm_provider TEXT,
                  tts_provider TEXT,
                  degrade_flags TEXT NOT NULL DEFAULT '[]',
                  trace_id TEXT,
                  latency_ms INTEGER NOT NULL DEFAULT 0,
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

                CREATE TABLE IF NOT EXISTS user_accounts (
                  user_id TEXT PRIMARY KEY,
                  email TEXT NOT NULL UNIQUE,
                  password_hash TEXT NOT NULL,
                  display_name TEXT NOT NULL,
                  role TEXT NOT NULL DEFAULT 'user',
                  status TEXT NOT NULL DEFAULT 'active',
                  email_verified INTEGER NOT NULL DEFAULT 0,
                  last_login_at TEXT,
                  password_changed_at TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
                  token_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  token_hash TEXT NOT NULL UNIQUE,
                  issued_at TEXT NOT NULL DEFAULT (datetime('now')),
                  expires_at TEXT NOT NULL,
                  revoked_at TEXT,
                  replaced_by_token_id TEXT,
                  ip TEXT,
                  user_agent TEXT
                );

                CREATE TABLE IF NOT EXISTS auth_password_reset_tokens (
                  reset_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  token_hash TEXT NOT NULL UNIQUE,
                  expires_at TEXT NOT NULL,
                  used_at TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                {self._practice_tables_sql()}

                CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts(email);
                CREATE INDEX IF NOT EXISTS idx_refresh_user_expires ON auth_refresh_tokens(user_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_reset_user_expires ON auth_password_reset_tokens(user_id, expires_at);
                {self._practice_indexes_sql()}
                """
            )
            self._ensure_column(conn, "interview_sessions", "technical_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "interview_sessions", "follow_up_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "interview_turns", "input_source", "TEXT")
            self._ensure_column(conn, "interview_turns", "asr_provider", "TEXT")
            self._ensure_column(conn, "interview_turns", "llm_provider", "TEXT")
            self._ensure_column(conn, "interview_turns", "tts_provider", "TEXT")
            self._ensure_column(conn, "interview_turns", "degrade_flags", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "interview_turns", "trace_id", "TEXT")
            self._ensure_column(conn, "interview_turns", "latency_ms", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "interview_turns", "generation_mode", "TEXT NOT NULL DEFAULT 'mock'")
            self._ensure_column(conn, "resumes", "user_id", "TEXT")
            self._ensure_column(conn, "resumes", "storage_path", "TEXT")
            self._ensure_column(conn, "resumes", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "resumes", "deleted_at", "TEXT")
            self._ensure_column(conn, "resumes", "updated_at", "TEXT")
            self._ensure_column(conn, "resumes", "parsed_text", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "resumes", "parse_error", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "user_id", "TEXT")
            self._ensure_column(conn, "interview_sessions", "session_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "question_types", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "interview_sessions", "started_at", "TEXT")
            self._ensure_column(conn, "interview_sessions", "finished_at", "TEXT")
            self._ensure_column(conn, "interview_sessions", "duration_seconds", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "interview_sessions", "duration_updated_at", "TEXT")
            self._ensure_column(conn, "interview_turns", "user_id", "TEXT")
            conn.execute(
                """
                UPDATE resumes
                SET user_id = COALESCE(NULLIF(user_id, ''), 'user-default')
                WHERE user_id IS NULL OR user_id = ''
                """
            )
            conn.execute(
                """
                UPDATE interview_sessions
                SET user_id = COALESCE(NULLIF(user_id, ''), 'user-default')
                WHERE user_id IS NULL OR user_id = ''
                """
            )
            conn.execute(
                """
                UPDATE interview_turns
                SET user_id = (
                  SELECT s.user_id FROM interview_sessions s WHERE s.interview_id = interview_turns.interview_id
                )
                WHERE user_id IS NULL OR user_id = ''
                """
            )
            conn.execute(
                """
                UPDATE resumes
                SET updated_at = COALESCE(NULLIF(updated_at, ''), datetime('now'))
                WHERE updated_at IS NULL OR updated_at = ''
                """
            )
            conn.execute(
                """
                UPDATE interview_sessions
                SET started_at = COALESCE(NULLIF(started_at, ''), created_at)
                WHERE started_at IS NULL OR started_at = ''
                """
            )
            conn.execute(
                """
                UPDATE interview_sessions
                SET duration_seconds = COALESCE(duration_seconds, 0)
                WHERE duration_seconds IS NULL
                """
            )
            conn.execute(
                """
                UPDATE interview_sessions
                SET duration_updated_at = COALESCE(NULLIF(duration_updated_at, ''), started_at, created_at, datetime('now'))
                WHERE duration_updated_at IS NULL OR duration_updated_at = ''
                """
            )
            self._upgrade_practice_schema(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_created ON resumes(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON interview_sessions(user_id, created_at DESC)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_user_interview_created ON interview_turns(user_id, interview_id, created_at ASC)"
            )
            conn.executescript(self._practice_indexes_sql())

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        """确保表包含指定列，缺失则补齐。"""
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        exists = any(str(row["name"]) == column for row in rows)
        if not exists:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _practice_schema_needs_upgrade(self, conn: sqlite3.Connection) -> bool:
        """检查 practice 表是否仍是缺少约束的旧结构。"""
        expected_tokens = {
            "practice_sessions": ["check(question_count > 0)"],
            "practice_session_questions": [
                "check(question_order > 0)",
                "unique(practice_id, question_order)",
                "unique(practice_id, session_question_id)",
                "foreign key (practice_id) references practice_sessions(practice_id) on delete cascade",
            ],
            "practice_answers": [
                "unique(practice_id, session_question_id)",
                "foreign key (practice_id) references practice_sessions(practice_id) on delete cascade",
                "foreign key (practice_id, session_question_id) references practice_session_questions(practice_id, session_question_id) on delete cascade",
            ],
        }
        for table, tokens in expected_tokens.items():
            row = conn.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table,),
            ).fetchone()
            if not row or not row["sql"]:
                return True
            normalized_sql = " ".join(str(row["sql"]).lower().split())
            if any(token not in normalized_sql for token in tokens):
                return True
        return False

    def _upgrade_practice_schema(self, conn: sqlite3.Connection) -> None:
        """按确定性重建方式升级旧版 practice 表结构。"""
        if not self._practice_schema_needs_upgrade(conn):
            return

        conn.execute("DROP TABLE IF EXISTS practice_answers__legacy")
        conn.execute("DROP TABLE IF EXISTS practice_session_questions__legacy")
        conn.execute("DROP TABLE IF EXISTS practice_sessions__legacy")

        existing_tables = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?, ?)",
                ("practice_sessions", "practice_session_questions", "practice_answers"),
            ).fetchall()
        }
        if "practice_answers" in existing_tables:
            conn.execute("ALTER TABLE practice_answers RENAME TO practice_answers__legacy")
        if "practice_session_questions" in existing_tables:
            conn.execute("ALTER TABLE practice_session_questions RENAME TO practice_session_questions__legacy")
        if "practice_sessions" in existing_tables:
            conn.execute("ALTER TABLE practice_sessions RENAME TO practice_sessions__legacy")

        conn.executescript(self._practice_tables_sql())

        if "practice_sessions" in existing_tables:
            conn.execute(
                """
                INSERT INTO practice_sessions(practice_id, user_id, job_role, mode, question_count, status, created_at)
                SELECT
                  practice_id,
                  user_id,
                  job_role,
                  mode,
                  CASE WHEN question_count IS NULL OR question_count <= 0 THEN 1 ELSE question_count END,
                  COALESCE(NULLIF(status, ''), 'ACTIVE'),
                  COALESCE(NULLIF(created_at, ''), datetime('now'))
                FROM practice_sessions__legacy
                WHERE practice_id IS NOT NULL
                  AND user_id IS NOT NULL
                  AND job_role IS NOT NULL
                  AND mode IS NOT NULL
                """
            )

        if "practice_session_questions" in existing_tables:
            conn.execute(
                """
                WITH ranked_questions AS (
                  SELECT
                    session_question_id,
                    practice_id,
                    user_id,
                    question_order,
                    source_question_id,
                    category,
                    stem,
                    analysis,
                    COALESCE(NULLIF(created_at, ''), datetime('now')) AS created_at,
                    ROW_NUMBER() OVER (
                      PARTITION BY practice_id, question_order
                      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, session_question_id ASC, rowid ASC
                    ) AS order_rn,
                    ROW_NUMBER() OVER (
                      PARTITION BY practice_id, session_question_id
                      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, question_order ASC, rowid ASC
                    ) AS snapshot_rn
                  FROM practice_session_questions__legacy
                  WHERE practice_id IS NOT NULL
                    AND user_id IS NOT NULL
                    AND session_question_id IS NOT NULL
                    AND question_order > 0
                    AND stem IS NOT NULL
                    AND stem != ''
                )
                INSERT INTO practice_session_questions(
                  session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis, created_at
                )
                SELECT
                  q.session_question_id,
                  q.practice_id,
                  q.user_id,
                  q.question_order,
                  q.source_question_id,
                  q.category,
                  q.stem,
                  q.analysis,
                  q.created_at
                FROM ranked_questions q
                JOIN practice_sessions s
                  ON s.practice_id = q.practice_id
                 AND s.user_id = q.user_id
                WHERE q.order_rn = 1
                  AND q.snapshot_rn = 1
                """
            )

        if "practice_answers" in existing_tables:
            conn.execute(
                """
                WITH ranked_answers AS (
                  SELECT
                    answer_id,
                    practice_id,
                    session_question_id,
                    user_id,
                    answer_text,
                    COALESCE(NULLIF(created_at, ''), datetime('now')) AS created_at,
                    ROW_NUMBER() OVER (
                      PARTITION BY answer_id
                      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, rowid ASC
                    ) AS answer_rn
                    ,
                    ROW_NUMBER() OVER (
                      PARTITION BY practice_id, session_question_id
                      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, answer_id ASC, rowid ASC
                    ) AS session_question_rn
                  FROM practice_answers__legacy
                  WHERE answer_id IS NOT NULL
                    AND practice_id IS NOT NULL
                    AND session_question_id IS NOT NULL
                    AND user_id IS NOT NULL
                    AND answer_text IS NOT NULL
                    AND answer_text != ''
                )
                INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text, created_at)
                SELECT
                  a.answer_id,
                  a.practice_id,
                  a.session_question_id,
                  a.user_id,
                  a.answer_text,
                  a.created_at
                FROM ranked_answers a
                JOIN practice_sessions s
                  ON s.practice_id = a.practice_id
                 AND s.user_id = a.user_id
                JOIN practice_session_questions q
                 ON q.practice_id = a.practice_id
                 AND q.session_question_id = a.session_question_id
                 AND q.user_id = a.user_id
                WHERE a.answer_rn = 1
                  AND a.session_question_rn = 1
                """
            )

        conn.execute("DROP TABLE IF EXISTS practice_answers__legacy")
        conn.execute("DROP TABLE IF EXISTS practice_session_questions__legacy")
        conn.execute("DROP TABLE IF EXISTS practice_sessions__legacy")

    def _require_practice_session_owner(self, conn: sqlite3.Connection, user_id: str, practice_id: str) -> None:
        """确保用户对练习会话具备访问权限。"""
        row = conn.execute(
            """
            SELECT practice_id FROM practice_sessions
            WHERE practice_id = ? AND user_id = ?
            """,
            (practice_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("练习会话不存在或无权访问")

    def _require_practice_question_owner(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        practice_id: str,
        session_question_id: str,
    ) -> None:
        """确保用户对题目快照具备访问权限。"""
        row = conn.execute(
            """
            SELECT session_question_id FROM practice_session_questions
            WHERE practice_id = ? AND session_question_id = ? AND user_id = ?
            """,
            (practice_id, session_question_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("题目快照不存在或无权访问")

    def create_resume(self, user_id: str, filename: str, storage_path: str, status: str, parsed_text: str, parse_error: str) -> dict:
        """创建简历记录。"""
        resume_id = f"res_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO resumes(resume_id, user_id, filename, storage_path, status, parsed_text, parse_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (resume_id, user_id, filename, storage_path, status, parsed_text, parse_error),
            )
        return {"resume_id": resume_id, "status": status}

    def list_resumes(self, user_id: str, offset: int, limit: int) -> tuple[list[dict], int]:
        """分页查询用户简历列表。"""
        with self._session() as conn:
            total = conn.execute(
                """
                SELECT COUNT(1) AS cnt FROM resumes
                WHERE user_id = ? AND is_deleted = 0
                """,
                (user_id,),
            ).fetchone()["cnt"]
            rows = conn.execute(
                """
                SELECT r.resume_id, r.filename, r.status, r.created_at, MAX(s.created_at) AS last_used_at
                FROM resumes r
                LEFT JOIN interview_sessions s ON s.resume_id = r.resume_id AND s.user_id = r.user_id
                WHERE r.user_id = ? AND r.is_deleted = 0
                GROUP BY r.resume_id, r.filename, r.status, r.created_at
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        return [dict(r) for r in rows], int(total)

    def get_resume(self, resume_id: str) -> dict | None:
        """查询单个简历。"""
        with self._session() as conn:
            row = conn.execute("SELECT * FROM resumes WHERE resume_id = ?", (resume_id,)).fetchone()
        return dict(row) if row else None

    def has_active_session_ref(self, user_id: str, resume_id: str) -> bool:
        """检查是否被进行中的面试会话引用。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT COUNT(1) AS cnt FROM interview_sessions
                WHERE user_id = ? AND resume_id = ? AND status != 'FINISHED'
                """,
                (user_id, resume_id),
            ).fetchone()
        return int(row["cnt"]) > 0

    def soft_delete_resume(self, user_id: str, resume_id: str) -> None:
        """软删除用户简历。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE resumes
                SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
                WHERE user_id = ? AND resume_id = ? AND is_deleted = 0
                """,
                (user_id, resume_id),
            )

    def create_session(self, user_id: str, payload: dict) -> dict:
        """创建面试会话记录。"""
        interview_id = f"int_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions(
                  interview_id, user_id, resume_id, session_name, question_types, job_role, difficulty, input_mode, output_mode, status, current_stage, follow_up_count, technical_count, duration_seconds, duration_updated_at, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 'SELF_INTRO', 0, 0, 0, datetime('now'), datetime('now'))
                """,
                (
                    interview_id,
                    user_id,
                    payload["resume_id"],
                    str(payload.get("session_name") or ""),
                    json.dumps(payload.get("question_types") or ["project", "technical", "scenario"], ensure_ascii=False),
                    payload["job_role"],
                    payload["difficulty"],
                    payload["input_mode"],
                    payload["output_mode"],
                ),
            )
        return {"interview_id": interview_id, "current_stage": "SELF_INTRO"}

    def create_practice_session(self, user_id: str, payload: dict) -> dict:
        """创建题库练习会话记录。"""
        practice_id = f"prac_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO practice_sessions(practice_id, user_id, job_role, mode, question_count, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (
                    practice_id,
                    user_id,
                    payload["job_role"],
                    payload["mode"],
                    int(payload["question_count"]),
                ),
            )
        return {"practice_id": practice_id, "status": "ACTIVE"}

    def create_practice_session_with_snapshots(self, user_id: str, payload: dict, question_snapshots: list[dict]) -> dict:
        """以单事务创建练习会话及其题目快照。"""
        practice_id = f"prac_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO practice_sessions(practice_id, user_id, job_role, mode, question_count, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (
                    practice_id,
                    user_id,
                    payload["job_role"],
                    payload["mode"],
                    int(payload["question_count"]),
                ),
            )
            for index, question_data in enumerate(question_snapshots, start=1):
                conn.execute(
                    """
                    INSERT INTO practice_session_questions(
                      session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"psq_{uuid.uuid4().hex[:12]}",
                        practice_id,
                        user_id,
                        index,
                        question_data.get("source_question_id"),
                        question_data.get("category"),
                        question_data["stem"],
                        question_data.get("analysis"),
                    ),
                )
        return {"practice_id": practice_id, "status": "ACTIVE"}

    def get_practice_session(self, user_id: str, practice_id: str) -> dict | None:
        """查询单个题库练习会话。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT * FROM practice_sessions
                WHERE practice_id = ? AND user_id = ?
                """,
                (practice_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def get_practice_session_by_id(self, practice_id: str) -> dict | None:
        """按练习会话标识查询题库练习会话。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT * FROM practice_sessions
                WHERE practice_id = ?
                """,
                (practice_id,),
            ).fetchone()
        return dict(row) if row else None

    def add_practice_question_snapshot(
        self,
        user_id: str,
        practice_id: str,
        question_order: int,
        question_data: dict,
    ) -> str:
        """为练习会话写入题目快照。"""
        session_question_id = f"psq_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            self._require_practice_session_owner(conn, user_id, practice_id)
            conn.execute(
                """
                INSERT INTO practice_session_questions(
                  session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_question_id,
                    practice_id,
                    user_id,
                    int(question_order),
                    question_data.get("source_question_id"),
                    question_data.get("category"),
                    question_data["stem"],
                    question_data.get("analysis"),
                ),
            )
        return session_question_id

    def list_practice_question_snapshots(self, user_id: str, practice_id: str) -> list[dict]:
        """按顺序查询用户的题目快照列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT session_question_id, practice_id, question_order, source_question_id, category, stem, analysis, created_at
                FROM practice_session_questions
                WHERE practice_id = ? AND user_id = ?
                ORDER BY question_order ASC, created_at ASC
                """,
                (practice_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_practice_session_status(self, user_id: str, practice_id: str, status: str) -> bool:
        """更新当前用户题库练习会话状态。"""
        with self._session() as conn:
            row = conn.execute(
                """
                UPDATE practice_sessions
                SET status = ?
                WHERE practice_id = ? AND user_id = ?
                """,
                (status, practice_id, user_id),
            )
        return row.rowcount > 0

    def add_practice_answer(
        self,
        user_id: str,
        practice_id: str,
        session_question_id: str,
        answer_text: str,
    ) -> str:
        """写入题库练习答案。"""
        answer_id = f"ans_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            self._require_practice_question_owner(conn, user_id, practice_id, session_question_id)
            conn.execute(
                """
                INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    answer_id,
                    practice_id,
                    session_question_id,
                    user_id,
                    answer_text,
                ),
            )
        return answer_id

    def list_practice_answers(self, user_id: str, practice_id: str) -> list[dict]:
        """按写入顺序查询用户的练习答案列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT answer_id, practice_id, session_question_id, answer_text, created_at
                FROM practice_answers
                WHERE practice_id = ? AND user_id = ?
                ORDER BY created_at ASC, answer_id ASC
                """,
                (practice_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_practice_records(self, user_id: str) -> list[dict]:
        """查询当前用户的题库练习记录列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT
                  s.practice_id,
                  s.job_role,
                  s.mode,
                  s.status,
                  s.question_count,
                  s.created_at,
                  COUNT(a.answer_id) AS answered_count
                FROM practice_sessions s
                LEFT JOIN practice_answers a
                  ON a.practice_id = s.practice_id
                 AND a.user_id = s.user_id
                WHERE s.user_id = ?
                GROUP BY s.practice_id, s.job_role, s.mode, s.status, s.question_count, s.created_at
                ORDER BY s.created_at DESC, s.practice_id DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_practice_record_detail(self, user_id: str, practice_id: str) -> dict | None:
        """按会话读取题库练习记录明细。"""
        with self._session() as conn:
            session = conn.execute(
                """
                SELECT practice_id, job_role, mode, status, question_count, created_at, NULL AS finished_at
                FROM practice_sessions
                WHERE practice_id = ? AND user_id = ?
                """,
                (practice_id, user_id),
            ).fetchone()
            if session is None:
                return None
            items = conn.execute(
                """
                SELECT
                  q.session_question_id,
                  q.question_order,
                  q.category,
                  q.stem,
                  q.analysis,
                  a.answer_text,
                  a.created_at AS answered_at
                FROM practice_session_questions q
                LEFT JOIN practice_answers a
                  ON a.practice_id = q.practice_id
                 AND a.session_question_id = q.session_question_id
                 AND a.user_id = q.user_id
                WHERE q.practice_id = ? AND q.user_id = ?
                ORDER BY q.question_order ASC, q.created_at ASC
                """,
                (practice_id, user_id),
            ).fetchall()
        return {
            "session": dict(session),
            "items": [dict(row) for row in items],
        }

    def list_question_bank_items(self, job_role: str, categories: list[str] | None = None) -> list[dict]:
        """按岗位和类别查询题库候选题。"""
        sql = """
            SELECT record_id, category, question, analysis
            FROM question_bank
            WHERE role = ?
        """
        params: list[object] = [job_role]
        normalized_categories = [item for item in (categories or []) if item]
        if normalized_categories:
            placeholders = ", ".join("?" for _ in normalized_categories)
            sql += f" AND category IN ({placeholders})"
            params.extend(normalized_categories)
        sql += " ORDER BY question_no ASC, record_id ASC"
        with self._session() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_admin_question_bank_items(
        self,
        job_role: str,
        category: str | None,
        keyword: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """按岗位、类别和关键词分页读取管理端题库列表。"""
        where = ["role = ?"]
        params: list[object] = [job_role]
        if category:
            where.append("category = ?")
            params.append(category)
        if keyword:
            where.append("(title LIKE ? OR question LIKE ? OR COALESCE(analysis, '') LIKE ?)")
            keyword_like = f"%{keyword}%"
            params.extend([keyword_like, keyword_like, keyword_like])
        where_clause = " AND ".join(where)
        with self._session() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM question_bank WHERE {where_clause}",
                    tuple(params),
                ).fetchone()[0]
            )
            rows = conn.execute(
                f"""
                SELECT record_id, role, question_no, title, category, question, analysis, source_path, updated_at
                FROM question_bank
                WHERE {where_clause}
                ORDER BY question_no ASC, record_id ASC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, limit, offset]),
            ).fetchall()
        return [dict(row) for row in rows], total

    def get_session(self, interview_id: str) -> dict | None:
        """查询单个会话。"""
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
        return dict(row) if row else None

    def pause_session(self, user_id: str, interview_id: str) -> bool:
        """将进行中的会话置为暂停。"""
        with self._session() as conn:
            row = conn.execute(
                """
                UPDATE interview_sessions
                SET status = 'PAUSED',
                    duration_seconds = duration_seconds + CAST((julianday('now') - julianday(duration_updated_at)) * 86400 AS INTEGER),
                    duration_updated_at = datetime('now')
                WHERE interview_id = ? AND user_id = ? AND status = 'ACTIVE'
                """,
                (interview_id, user_id),
            )
        return row.rowcount > 0

    def resume_session(self, user_id: str, interview_id: str) -> bool:
        """将暂停会话恢复为进行中。"""
        with self._session() as conn:
            row = conn.execute(
                """
                UPDATE interview_sessions
                SET status = 'ACTIVE',
                    duration_updated_at = datetime('now')
                WHERE interview_id = ? AND user_id = ? AND status = 'PAUSED'
                """,
                (interview_id, user_id),
            )
        return row.rowcount > 0

    def set_session_status(self, user_id: str, interview_id: str, status: str) -> bool:
        """更新会话状态，仅允许 ACTIVE 与 PAUSED 之间切换。"""
        with self._session() as conn:
            if status == "PAUSED":
                row = conn.execute(
                    """
                    UPDATE interview_sessions
                    SET status = 'PAUSED',
                        duration_seconds = duration_seconds + CAST((julianday('now') - julianday(duration_updated_at)) * 86400 AS INTEGER),
                        duration_updated_at = datetime('now')
                    WHERE interview_id = ? AND user_id = ? AND status = 'ACTIVE'
                    """,
                    (interview_id, user_id),
                )
            elif status == "ACTIVE":
                row = conn.execute(
                    """
                    UPDATE interview_sessions
                    SET status = 'ACTIVE',
                        duration_updated_at = datetime('now')
                    WHERE interview_id = ? AND user_id = ? AND status = 'PAUSED'
                    """,
                    (interview_id, user_id),
                )
            else:
                return False
        return row.rowcount > 0

    def list_paused_sessions(self, user_id: str, limit: int = 20) -> list[dict]:
        """列出用户暂停中的面试会话。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT
                  s.interview_id,
                  s.session_name,
                  s.job_role,
                  s.difficulty,
                  s.current_stage,
                  s.follow_up_count,
                  s.technical_count,
                  s.input_mode,
                  s.output_mode,
                  s.started_at,
                  s.created_at,
                  r.filename AS resume_file_name
                FROM interview_sessions s
                LEFT JOIN resumes r ON r.resume_id = s.resume_id
                WHERE s.user_id = ? AND s.status = 'PAUSED'
                ORDER BY s.created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_last_next_question(self, user_id: str, interview_id: str) -> str | None:
        """获取会话最近一轮生成的问题。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT next_question FROM interview_turns
                WHERE interview_id = ? AND user_id = ?
                ORDER BY created_at DESC, turn_id DESC
                LIMIT 1
                """,
                (interview_id, user_id),
            ).fetchone()
        if not row:
            return None
        return str(row["next_question"] or "")

    def delete_interview(self, user_id: str, interview_id: str) -> bool:
        """删除指定面试会话及其关联轮次与报告。"""
        with self._session() as conn:
            session = conn.execute(
                """
                SELECT interview_id FROM interview_sessions
                WHERE interview_id = ? AND user_id = ?
                """,
                (interview_id, user_id),
            ).fetchone()
            if not session:
                return False
            conn.execute("DELETE FROM interview_turns WHERE interview_id = ? AND user_id = ?", (interview_id, user_id))
            conn.execute("DELETE FROM interview_reports WHERE interview_id = ?", (interview_id,))
            conn.execute("DELETE FROM interview_sessions WHERE interview_id = ? AND user_id = ?", (interview_id, user_id))
        return True

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
                """
                UPDATE interview_sessions
                SET status='FINISHED',
                    current_stage='END',
                    finished_at=datetime('now'),
                    duration_seconds = duration_seconds + CASE
                      WHEN status = 'ACTIVE' THEN CAST((julianday('now') - julianday(duration_updated_at)) * 86400 AS INTEGER)
                      ELSE 0
                    END,
                    duration_updated_at = datetime('now')
                WHERE interview_id = ?
                """,
                (interview_id,),
            )

    def add_turn(
        self,
        interview_id: str,
        user_id: str,
        stage: str,
        answer_text: str,
        next_question: str,
        score: int,
        generation_mode: str = "mock",
        input_source: str | None = None,
        asr_provider: str | None = None,
        llm_provider: str | None = None,
        tts_provider: str | None = None,
        degrade_flags: list[str] | None = None,
        trace_id: str | None = None,
        latency_ms: int = 0,
    ) -> str:
        """写入单轮面试记录并返回 turn_id。"""
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_turns(
                                    turn_id, interview_id, stage, answer_text, next_question, live_score, generation_mode,
                  user_id,
                  input_source, asr_provider, llm_provider, tts_provider, degrade_flags, trace_id, latency_ms
                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    interview_id,
                    stage,
                    answer_text,
                    next_question,
                    score,
                                        generation_mode,
                    user_id,
                    input_source,
                    asr_provider,
                    llm_provider,
                    tts_provider,
                    json.dumps(degrade_flags or [], ensure_ascii=False),
                    trace_id,
                    latency_ms,
                ),
            )
        return turn_id

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

    def list_history(
        self,
        user_id: str,
        job_role: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """分页查询历史会话。"""
        where = "WHERE s.user_id = ?"
        params: list[object] = [user_id]
        if job_role:
            where += " AND s.job_role = ?"
            params.append(job_role)
        if status:
            where += " AND s.status = ?"
            params.append(status)
        with self._session() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) AS cnt FROM interview_sessions s {where}",
                params,
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""
                SELECT
                  s.interview_id,
                  s.session_name,
                  s.resume_id,
                  s.job_role,
                  s.status,
                  s.started_at,
                  s.finished_at,
                  s.duration_seconds,
                  s.duration_updated_at,
                  s.created_at,
                  r.overall_score,
                  (
                    SELECT COUNT(1) FROM interview_turns t WHERE t.interview_id = s.interview_id
                  ) AS turn_count
                FROM interview_sessions s
                LEFT JOIN interview_reports r ON r.interview_id = s.interview_id
                {where}
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], int(total)

    def get_playback(self, user_id: str, interview_id: str) -> dict | None:
        """聚合面试回放数据。"""
        first_question = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"
        with self._session() as conn:
            session = conn.execute(
                """
                SELECT interview_id, resume_id, job_role, difficulty, status, started_at, finished_at, user_id
                     , duration_seconds, duration_updated_at
                FROM interview_sessions
                WHERE interview_id = ?
                """,
                (interview_id,),
            ).fetchone()
            if not session:
                return None
            if str(session["user_id"] or "") != user_id:
                return {"forbidden": True}

            resume = conn.execute(
                """
                SELECT resume_id, filename FROM resumes
                WHERE resume_id = ? AND user_id = ?
                """,
                (session["resume_id"], user_id),
            ).fetchone()
            raw_turns = conn.execute(
                """
                SELECT
                  turn_id,
                  ROW_NUMBER() OVER (ORDER BY created_at ASC, turn_id ASC) AS sequence,
                  answer_text AS answer,
                  next_question AS next_question,
                  created_at AS question_ts,
                  created_at AS answer_ts
                FROM interview_turns
                WHERE interview_id = ? AND user_id = ?
                ORDER BY created_at ASC, turn_id ASC
                """,
                (interview_id, user_id),
            ).fetchall()

        turns: list[dict] = []
        previous_next_question = first_question
        for raw in raw_turns:
            turn = dict(raw)
            turn["question"] = previous_next_question
            previous_next_question = str(turn.get("next_question") or "")
            turn.pop("next_question", None)
            turns.append(turn)

        return {
            "session": dict(session),
            "resume": dict(resume) if resume else None,
            "turns": turns,
        }

    def create_user(self, user_id: str, email: str, password_hash: str, display_name: str, role: str) -> dict:
        """创建用户账号。"""
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO user_accounts(user_id, email, password_hash, display_name, role, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (user_id, email.lower(), password_hash, display_name, role),
            )
            row = conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)

    def get_user_by_email(self, email: str) -> dict | None:
        """按邮箱查询账号。"""
        with self._session() as conn:
            row = conn.execute("SELECT * FROM user_accounts WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        """按用户 ID 查询账号。"""
        with self._session() as conn:
            row = conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def update_user_last_login(self, user_id: str) -> None:
        """更新用户最后登录时间。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE user_accounts
                SET last_login_at = datetime('now'), updated_at = datetime('now')
                WHERE user_id = ?
                """,
                (user_id,),
            )

    def update_user_password(self, user_id: str, password_hash: str) -> None:
        """更新用户密码哈希。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE user_accounts
                SET password_hash = ?, password_changed_at = datetime('now'), updated_at = datetime('now')
                WHERE user_id = ?
                """,
                (password_hash, user_id),
            )

    def insert_refresh_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        expires_at: str,
        ip: str,
        user_agent: str,
    ) -> None:
        """写入刷新令牌。"""
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO auth_refresh_tokens(token_id, user_id, token_hash, expires_at, ip, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (token_id, user_id, token_hash, expires_at, ip, user_agent),
            )

    def get_active_refresh_token_by_hash(self, token_hash: str) -> dict | None:
        """按哈希查询有效刷新令牌。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT t.token_id, t.user_id, t.expires_at, u.role
                FROM auth_refresh_tokens t
                JOIN user_accounts u ON u.user_id = t.user_id
                WHERE t.token_hash = ?
                  AND t.revoked_at IS NULL
                  AND datetime(t.expires_at) > datetime('now')
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        return dict(row) if row else None

    def rotate_refresh_token(
        self,
        old_token_id: str,
        new_token_id: str,
        user_id: str,
        new_token_hash: str,
        expires_at: str,
        ip: str,
        user_agent: str,
    ) -> None:
        """轮换刷新令牌并撤销旧令牌。"""
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO auth_refresh_tokens(token_id, user_id, token_hash, expires_at, ip, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (new_token_id, user_id, new_token_hash, expires_at, ip, user_agent),
            )
            conn.execute(
                """
                UPDATE auth_refresh_tokens
                SET revoked_at = datetime('now'), replaced_by_token_id = ?
                WHERE token_id = ? AND revoked_at IS NULL
                """,
                (new_token_id, old_token_id),
            )

    def revoke_refresh_token(self, token_id: str) -> None:
        """撤销单个刷新令牌。"""
        with self._session() as conn:
            conn.execute(
                "UPDATE auth_refresh_tokens SET revoked_at = datetime('now') WHERE token_id = ? AND revoked_at IS NULL",
                (token_id,),
            )

    def revoke_all_refresh_tokens(self, user_id: str) -> None:
        """撤销用户全部刷新令牌。"""
        with self._session() as conn:
            conn.execute(
                "UPDATE auth_refresh_tokens SET revoked_at = datetime('now') WHERE user_id = ? AND revoked_at IS NULL",
                (user_id,),
            )

    def insert_password_reset_token(self, reset_id: str, user_id: str, token_hash: str, expires_at: str) -> None:
        """写入密码重置令牌。"""
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO auth_password_reset_tokens(reset_id, user_id, token_hash, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (reset_id, user_id, token_hash, expires_at),
            )

    def get_active_reset_token_by_hash(self, token_hash: str) -> dict | None:
        """按哈希查询有效重置令牌。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT reset_id, user_id
                FROM auth_password_reset_tokens
                WHERE token_hash = ?
                  AND used_at IS NULL
                  AND datetime(expires_at) > datetime('now')
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
        return dict(row) if row else None

    def mark_reset_token_used(self, reset_id: str, conn: sqlite3.Connection | None = None) -> None:
        """标记重置令牌已使用。"""
        if conn is not None:
            conn.execute(
                "UPDATE auth_password_reset_tokens SET used_at = datetime('now') WHERE reset_id = ?",
                (reset_id,),
            )
            return
        with self._session() as session:
            session.execute(
                "UPDATE auth_password_reset_tokens SET used_at = datetime('now') WHERE reset_id = ?",
                (reset_id,),
            )

    def reset_password_and_revoke_tokens(self, user_id: str, password_hash: str, reset_id: str) -> None:
        """事务化更新密码并撤销用户 refresh token。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE user_accounts
                SET password_hash = ?, password_changed_at = datetime('now'), updated_at = datetime('now')
                WHERE user_id = ?
                """,
                (password_hash, user_id),
            )
            conn.execute(
                "UPDATE auth_password_reset_tokens SET used_at = datetime('now') WHERE reset_id = ?",
                (reset_id,),
            )
            conn.execute(
                "UPDATE auth_refresh_tokens SET revoked_at = datetime('now') WHERE user_id = ? AND revoked_at IS NULL",
                (user_id,),
            )
