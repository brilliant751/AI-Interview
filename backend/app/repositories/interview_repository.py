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
                  user_id TEXT,
                  filename TEXT NOT NULL,
                  storage_path TEXT,
                  status TEXT NOT NULL DEFAULT 'PENDING',
                  is_deleted INTEGER NOT NULL DEFAULT 0,
                  deleted_at TEXT,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_sessions (
                  interview_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  resume_id TEXT NOT NULL,
                  job_role TEXT NOT NULL,
                  difficulty TEXT NOT NULL,
                  input_mode TEXT NOT NULL,
                  output_mode TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  current_stage TEXT NOT NULL DEFAULT 'SELF_INTRO',
                  follow_up_count INTEGER NOT NULL DEFAULT 0,
                  technical_count INTEGER NOT NULL DEFAULT 0,
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

                CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts(email);
                CREATE INDEX IF NOT EXISTS idx_refresh_user_expires ON auth_refresh_tokens(user_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_reset_user_expires ON auth_password_reset_tokens(user_id, expires_at);
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
            self._ensure_column(conn, "interview_sessions", "user_id", "TEXT")
            self._ensure_column(conn, "interview_sessions", "started_at", "TEXT")
            self._ensure_column(conn, "interview_sessions", "finished_at", "TEXT")
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_created ON resumes(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON interview_sessions(user_id, created_at DESC)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_user_interview_created ON interview_turns(user_id, interview_id, created_at ASC)"
            )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        """确保表包含指定列，缺失则补齐。"""
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        exists = any(str(row["name"]) == column for row in rows)
        if not exists:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def create_resume(self, user_id: str, filename: str, storage_path: str) -> dict:
        """创建简历记录。"""
        resume_id = f"res_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO resumes(resume_id, user_id, filename, storage_path, status, updated_at)
                VALUES (?, ?, ?, ?, 'READY', datetime('now'))
                """,
                (resume_id, user_id, filename, storage_path),
            )
        return {"resume_id": resume_id, "status": "READY"}

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
                  interview_id, user_id, resume_id, job_role, difficulty, input_mode, output_mode, status, current_stage, follow_up_count, technical_count, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 'SELF_INTRO', 0, 0, datetime('now'))
                """,
                (
                    interview_id,
                    user_id,
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
                """
                UPDATE interview_sessions
                SET status='FINISHED', current_stage='END', finished_at=datetime('now')
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

    def list_history(self, user_id: str, job_role: str | None, offset: int, limit: int) -> tuple[list[dict], int]:
        """分页查询历史会话。"""
        where = "WHERE s.user_id = ?"
        params: list[object] = [user_id]
        if job_role:
            where += " AND s.job_role = ?"
            params.append(job_role)
        with self._session() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) AS cnt FROM interview_sessions s {where}",
                params,
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""
                SELECT
                  s.interview_id,
                  s.resume_id,
                  s.job_role,
                  s.status,
                  s.started_at,
                  s.finished_at,
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
        with self._session() as conn:
            session = conn.execute(
                """
                SELECT interview_id, resume_id, job_role, difficulty, status, started_at, finished_at, user_id
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
            turns = conn.execute(
                """
                SELECT
                  turn_id,
                  ROW_NUMBER() OVER (ORDER BY created_at ASC, turn_id ASC) AS sequence,
                  next_question AS question,
                  answer_text AS answer,
                  created_at AS question_ts,
                  created_at AS answer_ts
                FROM interview_turns
                WHERE interview_id = ? AND user_id = ?
                ORDER BY created_at ASC, turn_id ASC
                """,
                (interview_id, user_id),
            ).fetchall()

        return {
            "session": dict(session),
            "resume": dict(resume) if resume else None,
            "turns": [dict(r) for r in turns],
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
