"""面试领域 SQLite 仓储实现。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
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
                  options TEXT NOT NULL DEFAULT '[]',
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
                CREATE INDEX IF NOT EXISTS idx_practice_choice_domain_type ON practice_choice_questions(domain, question_type);
                CREATE INDEX IF NOT EXISTS idx_practice_sessions_user_created ON practice_sessions(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_practice_questions_session_order ON practice_session_questions(practice_id, question_order ASC);
                CREATE INDEX IF NOT EXISTS idx_practice_answers_user_session ON practice_answers(user_id, practice_id, created_at ASC);
        """

    def _coding_tables_sql(self) -> str:
        """返回编程练习域的表结构 DDL。"""
        return """
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

                CREATE TABLE IF NOT EXISTS coding_sessions (
                  session_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  question_id TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  last_language TEXT NOT NULL DEFAULT 'cpp',
                  last_opened_at TEXT NOT NULL DEFAULT (datetime('now')),
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                  UNIQUE(user_id, question_id),
                  FOREIGN KEY (question_id) REFERENCES coding_questions(question_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS coding_drafts (
                  draft_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  question_id TEXT NOT NULL,
                  language TEXT NOT NULL,
                  source_code TEXT NOT NULL,
                  last_result_payload TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  UNIQUE(session_id, language),
                  FOREIGN KEY (session_id) REFERENCES coding_sessions(session_id) ON DELETE CASCADE,
                  FOREIGN KEY (question_id) REFERENCES coding_questions(question_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS coding_submissions (
                  submission_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  question_id TEXT NOT NULL,
                  language TEXT NOT NULL,
                  source_code TEXT NOT NULL,
                  submit_type TEXT NOT NULL,
                  status TEXT NOT NULL,
                  passed_count INTEGER NOT NULL DEFAULT 0,
                  total_count INTEGER NOT NULL DEFAULT 0,
                  result_payload TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  FOREIGN KEY (session_id) REFERENCES coding_sessions(session_id) ON DELETE CASCADE,
                  FOREIGN KEY (question_id) REFERENCES coding_questions(question_id) ON DELETE CASCADE
                );
        """

    def _coding_indexes_sql(self) -> str:
        """返回编程练习域的索引 DDL。"""
        return """
                CREATE INDEX IF NOT EXISTS idx_coding_questions_difficulty ON coding_questions(difficulty, question_id);
                CREATE INDEX IF NOT EXISTS idx_coding_sessions_user_updated ON coding_sessions(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_coding_drafts_session_language ON coding_drafts(session_id, language);
                CREATE INDEX IF NOT EXISTS idx_coding_submissions_session_created ON coding_submissions(session_id, created_at DESC);
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
                  schedule_id TEXT,
                  source_type TEXT NOT NULL DEFAULT 'instant',
                  resume_id TEXT NOT NULL,
                  jd_id TEXT,
                  voice_tone_id TEXT NOT NULL DEFAULT '',
                  voice_tone_name TEXT NOT NULL DEFAULT '',
                  voice_tone_instructions TEXT NOT NULL DEFAULT '',
                  voice_tone_speed REAL NOT NULL DEFAULT 1.0,
                  jd_snapshot_title TEXT NOT NULL DEFAULT '',
                  jd_snapshot_content TEXT NOT NULL DEFAULT '',
                  session_name TEXT NOT NULL DEFAULT '',
                  question_types TEXT NOT NULL DEFAULT '[]',
                  job_role TEXT NOT NULL,
                  difficulty TEXT NOT NULL,
                  input_mode TEXT NOT NULL,
                  output_mode TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  scheduled_start_at TEXT,
                  current_stage TEXT NOT NULL DEFAULT 'SELF_INTRO',
                  follow_up_count INTEGER NOT NULL DEFAULT 0,
                  technical_count INTEGER NOT NULL DEFAULT 0,
                  duration_seconds INTEGER NOT NULL DEFAULT 0,
                  duration_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                  started_at TEXT NOT NULL DEFAULT (datetime('now')),
                  finished_at TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_schedules (
                  schedule_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  plan_id TEXT,
                  source_type TEXT NOT NULL DEFAULT 'single',
                  sequence_no INTEGER,
                  interview_id TEXT,
                  title TEXT NOT NULL DEFAULT '',
                  resume_id TEXT NOT NULL,
                  jd_id TEXT NOT NULL DEFAULT '',
                  job_role TEXT NOT NULL DEFAULT '',
                  difficulty TEXT NOT NULL DEFAULT 'medium',
                  input_mode TEXT NOT NULL DEFAULT 'text',
                  output_mode TEXT NOT NULL DEFAULT 'text',
                  session_name TEXT NOT NULL DEFAULT '',
                  question_types TEXT NOT NULL DEFAULT '[]',
                  voice_tone_id TEXT NOT NULL DEFAULT '',
                  duration_minutes INTEGER NOT NULL,
                  scheduled_start_at TEXT NOT NULL,
                  scheduled_end_at TEXT NOT NULL,
                  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                  status TEXT NOT NULL DEFAULT 'scheduled',
                  cancel_reason TEXT NOT NULL DEFAULT '',
                  reminder_status TEXT NOT NULL DEFAULT '{{}}',
                  calendar_sync_status TEXT NOT NULL DEFAULT '',
                  started_at TEXT,
                  completed_at TEXT,
                  cancelled_at TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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

                CREATE TABLE IF NOT EXISTS interview_turn_jobs (
                  job_id TEXT PRIMARY KEY,
                  interview_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  stage TEXT NOT NULL,
                  payload_json TEXT NOT NULL DEFAULT '{{}}',
                  result_json TEXT NOT NULL DEFAULT '{{}}',
                  error_message TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS interview_reports (
                  interview_id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  overall_score INTEGER,
                  strengths TEXT NOT NULL DEFAULT '[]',
                  weaknesses TEXT NOT NULL DEFAULT '[]',
                  suggestions TEXT NOT NULL DEFAULT '[]',
                  dimension_scores TEXT NOT NULL DEFAULT '[]',
                  jd_resume_alignment TEXT NOT NULL DEFAULT '[]',
                  question_deep_dives TEXT NOT NULL DEFAULT '[]',
                  key_risks TEXT NOT NULL DEFAULT '[]',
                  final_recommendation TEXT NOT NULL DEFAULT '',
                  error_message TEXT,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS job_descriptions (
                  jd_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  company_id TEXT,
                  source_type TEXT NOT NULL,
                  title TEXT NOT NULL,
                  job_role TEXT NOT NULL,
                  content_text TEXT NOT NULL DEFAULT '',
                  storage_path TEXT,
                  status TEXT NOT NULL DEFAULT 'READY',
                  is_deleted INTEGER NOT NULL DEFAULT 0,
                  deleted_at TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS companies (
                  company_id TEXT PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS voice_tone_profiles (
                  tone_id TEXT PRIMARY KEY,
                  tone_name TEXT NOT NULL,
                  description TEXT NOT NULL DEFAULT '',
                  base_instructions TEXT NOT NULL DEFAULT '',
                  speed REAL NOT NULL DEFAULT 1.0,
                  is_active INTEGER NOT NULL DEFAULT 1,
                  sort_order INTEGER NOT NULL DEFAULT 100,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
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
                {self._coding_tables_sql()}

                CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts(email);
                CREATE INDEX IF NOT EXISTS idx_refresh_user_expires ON auth_refresh_tokens(user_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_reset_user_expires ON auth_password_reset_tokens(user_id, expires_at);
                {self._practice_indexes_sql()}
                {self._coding_indexes_sql()}
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
            self._ensure_column(conn, "interview_sessions", "jd_id", "TEXT")
            self._ensure_column(conn, "interview_sessions", "jd_snapshot_title", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "jd_snapshot_content", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "scheduled_start_at", "TEXT")
            self._ensure_column(conn, "interview_reports", "dimension_scores", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "interview_reports", "jd_resume_alignment", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "interview_reports", "question_deep_dives", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "interview_reports", "key_risks", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "interview_reports", "final_recommendation", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "voice_tone_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "voice_tone_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "voice_tone_instructions", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "interview_sessions", "voice_tone_speed", "REAL NOT NULL DEFAULT 1.0")
            self._ensure_column(conn, "interview_sessions", "schedule_id", "TEXT")
            self._ensure_column(conn, "interview_sessions", "source_type", "TEXT NOT NULL DEFAULT 'instant'")
            self._ensure_column(conn, "job_descriptions", "company_id", "TEXT")
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
            self._ensure_column(conn, "practice_session_questions", "options", "TEXT NOT NULL DEFAULT '[]'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_created ON resumes(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON interview_sessions(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_jd_id ON interview_sessions(jd_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_schedule_id ON interview_sessions(schedule_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_user_start ON interview_schedules(user_id, scheduled_start_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_status ON interview_schedules(user_id, status, scheduled_start_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_plan_sequence ON interview_schedules(plan_id, sequence_no)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_tone_profiles_active_sort ON voice_tone_profiles(is_active, sort_order)")
            self._seed_voice_tone_profiles(conn)

    def _seed_voice_tone_profiles(self, conn: sqlite3.Connection) -> None:
        """初始化内置语气配置。"""
        tones = [
            (
                "tone_default",
                "标准面试官",
                "语气专业平衡，适合作为默认配置",
                "语气自然专业，表达清晰，句间停顿自然，避免播报腔。",
                1.0,
                1,
                10,
            ),
            (
                "tone_encouraging",
                "鼓励引导型",
                "更温和、更具鼓励感，适合新手候选人",
                "语气友好、耐心、积极，先认可再追问，保持清晰自然。",
                0.96,
                1,
                20,
            ),
            (
                "tone_challenging",
                "高压追问型",
                "更偏技术压测，语速略快，追问更直接",
                "语气冷静客观，提问直接明确，重点词轻微重读，保持礼貌。",
                1.04,
                1,
                30,
            ),
        ]
        for tone in tones:
            conn.execute(
                """
                INSERT INTO voice_tone_profiles(
                  tone_id, tone_name, description, base_instructions, speed, is_active, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tone_id) DO UPDATE SET
                  tone_name = excluded.tone_name,
                  description = excluded.description,
                  base_instructions = excluded.base_instructions,
                  speed = excluded.speed,
                  is_active = excluded.is_active,
                  sort_order = excluded.sort_order,
                  updated_at = datetime('now')
                """,
                tone,
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_user_interview_created ON interview_turns(user_id, interview_id, created_at ASC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turn_jobs_user_created ON interview_turn_jobs(user_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turn_jobs_interview_created ON interview_turn_jobs(interview_id, created_at DESC)"
            )
            conn.executescript(self._practice_indexes_sql())
            conn.executescript(self._coding_indexes_sql())
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jd_user_created ON job_descriptions(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jd_role_source ON job_descriptions(job_role, source_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jd_company_id ON job_descriptions(company_id)")
            self._seed_companies(conn)
            self._seed_preset_jds(conn)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        """确保表包含指定列，缺失则补齐。"""
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        exists = any(str(row["name"]) == column for row in rows)
        if not exists:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _safe_json_loads(self, value: object, default: object) -> object:
        """容错解析 JSON 字符串，异常时返回默认值。"""
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            parsed = json.loads(str(value))
        except Exception:
            return default
        if isinstance(parsed, str):
            # 兼容历史脏数据：字段被重复 JSON 编码（例如 "\"[{...}]\""）。
            try:
                parsed = json.loads(parsed)
            except Exception:
                return default
        if isinstance(default, list) and not isinstance(parsed, list):
            return default
        if isinstance(default, dict) and not isinstance(parsed, dict):
            return default
        return parsed

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

    def _require_coding_session_owner(self, conn: sqlite3.Connection, user_id: str, session_id: str) -> dict:
        """确保用户对编程练习会话具备访问权限。"""
        row = conn.execute(
            """
            SELECT session_id, question_id, status, last_language
            FROM coding_sessions
            WHERE session_id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("编程练习会话不存在或无权访问")
        return dict(row)

    def _seed_companies(self, conn: sqlite3.Connection) -> None:
        """初始化主流公司数据。"""
        companies = [
            ("cmp_bytedance", "字节跳动"),
            ("cmp_didi", "滴滴"),
            ("cmp_alibaba", "阿里巴巴"),
            ("cmp_tencent", "腾讯"),
            ("cmp_baidu", "百度"),
            ("cmp_meituan", "美团"),
            ("cmp_huawei", "华为"),
            ("cmp_xiaomi", "小米"),
            ("cmp_jd", "京东"),
            ("cmp_pinduoduo", "拼多多"),
            ("cmp_kuaishou", "快手"),
            ("cmp_360", "360"),
            ("cmp_netease", "网易"),
            ("cmp_bilibili", "哔哩哔哩"),
            ("cmp_xiaohongshu", "小红书"),
            ("cmp_douyin", "抖音"),
            ("cmp_citic", "中信证券"),
            ("cmp_efunds", "易方达基金"),
            ("cmp_mckinsey", "麦肯锡"),
            ("cmp_webank", "微众银行"),
            ("cmp_youzan", "有赞"),
            ("cmp_yuanfudao", "猿辅导"),
            ("cmp_huolala", "货拉拉"),
            ("cmp_shuran", "数然科技"),
            ("cmp_rongke", "融科智联"),
            ("cmp_ates", "阿特斯阳光电力"),
            ("cmp_mingsheng", "明胜品智"),
            ("cmp_tencent_games", "腾讯游戏"),
        ]
        for company_id, name in companies:
            conn.execute(
                """
                INSERT OR IGNORE INTO companies(company_id, name, status)
                VALUES (?, ?, 'ACTIVE')
                """,
                (company_id, name),
            )

    def _seed_preset_jds(self, conn: sqlite3.Connection) -> None:
        """初始化系统预置 JD 数据。"""
        presets = [
            ("jd_preset_algo_bytedance", "字节跳动", "算法实习生-推荐/搜索", "算法", "推荐算法、排序模型、用户行为分析"),
            ("jd_preset_llm_alibaba", "阿里巴巴", "大模型研发实习生", "算法", "大模型训练、SFT、RLHF、推理优化、多模态"),
            ("jd_preset_cpp_tencent", "腾讯", "C++后端开发实习生", "后端开发", "后端服务、分布式系统、高并发"),
            ("jd_preset_fe_kuaishou", "快手", "前端开发实习生", "前端开发", "Web前端、H5、跨端开发"),
            ("jd_preset_data_jd", "京东", "数据开发实习生", "数据开发", "数据仓库、ETL、数据治理、数据分析"),
            ("jd_preset_label_mingsheng", "明胜品智", "AI数据标注实习生", "数据标注", "图像/文本/语音标注与质量审核"),
            ("jd_preset_pm_meituan", "美团", "产品经理实习生", "产品", "需求调研、PRD、跨部门协同、数据分析"),
            ("jd_preset_ops_pdd", "拼多多", "电商运营实习生", "运营", "店铺运营、活动策划、用户增长"),
            ("jd_preset_content_xhs", "小红书", "内容运营实习生", "运营", "社区内容策划、创作者运营、数据复盘"),
            ("jd_preset_marketing_douyin", "抖音", "市场推广实习生", "市场", "品牌营销、活动策划、用户增长"),
            ("jd_preset_gameops_tg", "腾讯游戏", "游戏运营实习生", "运营", "版本活动、玩家运营、数据分析"),
            ("jd_preset_ib_citic", "中信证券", "投行实习生-股权承做", "金融", "IPO、再融资、并购重组、材料撰写"),
            ("jd_preset_research_efunds", "易方达基金", "行业研究实习生", "金融", "消费/科技/医药研究、报告撰写"),
            ("jd_preset_consult_mckinsey", "麦肯锡", "咨询实习生", "咨询", "战略咨询、行业研究、项目支持"),
            ("jd_preset_risk_webank", "微众银行", "风险管理实习生", "风控", "信用风险、市场风险、模型验证"),
            ("jd_preset_java_didi", "滴滴", "Java开发实习生（秋储）", "后端开发", "Java Web、业务系统开发、高可用服务"),
            ("jd_preset_java_tencent", "腾讯", "Java后台开发实习生", "后端开发", "Java后台服务、接口开发、性能优化"),
            ("jd_preset_java_youzan", "有赞", "Java Web开发实习生", "后端开发", "电商SaaS后端、接口与数据库设计"),
            ("jd_preset_java_huolala", "货拉拉", "Java后端开发实习生", "后端开发", "物流系统微服务开发、接口设计"),
        ]
        for jd_id, company_name, title, job_role, summary in presets:
            company = conn.execute("SELECT company_id FROM companies WHERE name = ? LIMIT 1", (company_name,)).fetchone()
            company_id = str(company["company_id"]) if company else None
            conn.execute(
                """
                INSERT OR IGNORE INTO job_descriptions(
                  jd_id, user_id, company_id, source_type, title, job_role, content_text, status, is_deleted
                ) VALUES (?, NULL, ?, 'SYSTEM_PRESET', ?, ?, ?, 'READY', 0)
                """,
                (jd_id, company_id, title, job_role, summary),
            )
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

    def create_session(self, user_id: str, payload: dict, jd_snapshot: dict | None = None) -> dict:
        """创建面试会话记录。"""
        interview_id = f"int_{uuid.uuid4().hex[:12]}"
        snapshot = jd_snapshot or {}
        status = str(payload.get("status") or "ACTIVE")
        scheduled_start_at = str(payload.get("scheduled_start_at") or "").strip() or None
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        started_at = scheduled_start_at or now_text
        duration_updated_at = started_at if status != "ACTIVE" else now_text
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions(
                  interview_id, user_id, schedule_id, source_type, resume_id, jd_id, voice_tone_id, voice_tone_name, voice_tone_instructions, voice_tone_speed, jd_snapshot_title, jd_snapshot_content, session_name, question_types, job_role, difficulty, input_mode, output_mode, status, scheduled_start_at, current_stage, follow_up_count, technical_count, duration_seconds, duration_updated_at, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SELF_INTRO', 0, 0, 0, ?, ?)
                """,
                (
                    interview_id,
                    user_id,
                    str(payload.get("schedule_id") or ""),
                    str(payload.get("source_type") or "instant"),
                    payload["resume_id"],
                    snapshot.get("jd_id"),
                    str(payload.get("voice_tone_id") or ""),
                    str(payload.get("voice_tone_name") or ""),
                    str(payload.get("voice_tone_instructions") or ""),
                    float(payload.get("voice_tone_speed") or 1.0),
                    str(snapshot.get("jd_snapshot_title") or ""),
                    str(snapshot.get("jd_snapshot_content") or ""),
                    str(payload.get("session_name") or ""),
                    json.dumps(payload.get("question_types") or ["project", "technical", "scenario"], ensure_ascii=False),
                    payload["job_role"],
                    payload["difficulty"],
                    payload["input_mode"],
                    payload["output_mode"],
                    status,
                    scheduled_start_at,
                    duration_updated_at,
                    started_at,
                ),
            )
        return {"interview_id": interview_id, "current_stage": "SELF_INTRO", "status": status}

    def list_active_voice_tones(self) -> list[dict]:
        """查询启用的语气配置列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT tone_id, tone_name, description, base_instructions, speed
                FROM voice_tone_profiles
                WHERE is_active = 1
                ORDER BY sort_order ASC, tone_id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_voice_tone(self, tone_id: str) -> dict | None:
        """按标识查询单个语气配置。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT tone_id, tone_name, description, base_instructions, speed, is_active
                FROM voice_tone_profiles
                WHERE tone_id = ?
                """,
                (tone_id,),
            ).fetchone()
        return dict(row) if row else None

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
                      session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, options, analysis
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"psq_{uuid.uuid4().hex[:12]}",
                        practice_id,
                        user_id,
                        index,
                        question_data.get("source_question_id"),
                        question_data.get("category"),
                        question_data["stem"],
                        json.dumps(question_data.get("options") or [], ensure_ascii=False),
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
                  session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, options, analysis
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_question_id,
                    practice_id,
                    user_id,
                    int(question_order),
                    question_data.get("source_question_id"),
                    question_data.get("category"),
                    question_data["stem"],
                    json.dumps(question_data.get("options") or [], ensure_ascii=False),
                    question_data.get("analysis"),
                ),
            )
        return session_question_id

    def list_practice_question_snapshots(self, user_id: str, practice_id: str) -> list[dict]:
        """按顺序查询用户的题目快照列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT session_question_id, practice_id, question_order, source_question_id, category, stem, options, analysis, created_at
                FROM practice_session_questions
                WHERE practice_id = ? AND user_id = ?
                ORDER BY question_order ASC, created_at ASC
                """,
                (practice_id, user_id),
            ).fetchall()
        items: list[dict] = []
        for row in rows:
            item = dict(row)
            item["options"] = self._safe_json_loads(item.get("options"), [])
            items.append(item)
        return items

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
        """按岗位读取练习专用选择题候选题（仅 single_choice）。"""
        sql = """
            SELECT question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata
            FROM practice_choice_questions
            WHERE domain = ? AND question_type = 'single_choice'
        """
        params: list[object] = [job_role]
        sql += " ORDER BY question_id ASC"
        with self._session() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        normalized_categories = {str(item).strip().lower() for item in (categories or []) if str(item).strip()}
        items: list[dict] = []
        for row in rows:
            item = dict(row)
            item["options"] = self._safe_json_loads(item.get("options"), [])
            item["answer_keys"] = self._safe_json_loads(item.get("answer_keys"), [])
            item["source"] = self._safe_json_loads(item.get("source"), {})
            item["metadata"] = self._safe_json_loads(item.get("metadata"), {})
            if normalized_categories:
                metadata_category = str((item["metadata"] or {}).get("category", "")).strip().lower()
                if metadata_category not in normalized_categories:
                    continue
            items.append(item)
        return items

    def get_practice_choice_question(self, question_id: str) -> dict | None:
        """按题目 ID 查询练习题库选择题。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata, updated_at
                FROM practice_choice_questions
                WHERE question_id = ?
                LIMIT 1
                """,
                (question_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["options"] = self._safe_json_loads(item.get("options"), [])
        item["answer_keys"] = self._safe_json_loads(item.get("answer_keys"), [])
        item["source"] = self._safe_json_loads(item.get("source"), {})
        item["metadata"] = self._safe_json_loads(item.get("metadata"), {})
        return item

    def get_practice_overview(self, user_id: str, recent_limit: int = 8) -> dict:
        """聚合题库练习首页所需的岗位统计与最近记录。"""
        with self._session() as conn:
            role_rows = conn.execute(
                """
                WITH role_base AS (
                  SELECT
                    role.job_role AS job_role,
                    COALESCE(q.total_questions, 0) AS total_questions
                  FROM (SELECT 'java' AS job_role UNION ALL SELECT 'web' AS job_role) role
                  LEFT JOIN (
                    SELECT domain AS job_role, COUNT(1) AS total_questions
                    FROM practice_choice_questions
                    WHERE question_type = 'single_choice'
                    GROUP BY domain
                  ) q ON q.job_role = role.job_role
                ),
                session_stats AS (
                  SELECT
                    s.job_role,
                    COUNT(1) AS total_sessions,
                    SUM(CASE WHEN s.status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_sessions,
                    SUM(CASE WHEN s.status = 'FINISHED' THEN 1 ELSE 0 END) AS finished_sessions,
                    COUNT(a.answer_id) AS answered_questions
                  FROM practice_sessions s
                  LEFT JOIN practice_answers a
                    ON a.practice_id = s.practice_id
                   AND a.user_id = s.user_id
                  WHERE s.user_id = ?
                  GROUP BY s.job_role
                )
                SELECT
                  b.job_role,
                  b.total_questions,
                  COALESCE(st.total_sessions, 0) AS total_sessions,
                  COALESCE(st.active_sessions, 0) AS active_sessions,
                  COALESCE(st.finished_sessions, 0) AS finished_sessions,
                  COALESCE(st.answered_questions, 0) AS answered_questions,
                  (
                    SELECT s2.practice_id
                    FROM practice_sessions s2
                    WHERE s2.user_id = ? AND s2.job_role = b.job_role AND s2.status = 'ACTIVE'
                    ORDER BY s2.created_at DESC, s2.practice_id DESC
                    LIMIT 1
                  ) AS latest_active_practice_id
                FROM role_base b
                LEFT JOIN session_stats st ON st.job_role = b.job_role
                ORDER BY b.job_role ASC
                """,
                (user_id, user_id),
            ).fetchall()
            recent_rows = conn.execute(
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
                LIMIT ?
                """,
                (user_id, recent_limit),
            ).fetchall()
        return {
            "role_stats": [dict(row) for row in role_rows],
            "recent_records": [dict(row) for row in recent_rows],
        }

    def list_admin_question_bank_items(
        self,
        job_role: str,
        category: str | None,
        keyword: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """按岗位和关键词分页读取练习专用选择题库列表。"""
        where = ["domain = ?", "question_type = 'single_choice'"]
        params: list[object] = [job_role]
        normalized_category = str(category or "").strip().lower()
        if keyword:
            where.append("(stem LIKE ? OR COALESCE(explanation, '') LIKE ?)")
            keyword_like = f"%{keyword}%"
            params.extend([keyword_like, keyword_like])
        where_clause = " AND ".join(where)
        json_category_clause = "LOWER(COALESCE(json_extract(metadata, '$.category'), '')) = ?"
        with self._session() as conn:
            use_json1 = True
            try:
                conn.execute("SELECT json_extract('{\"category\":\"x\"}', '$.category')").fetchone()
            except sqlite3.OperationalError:
                use_json1 = False

            if use_json1:
                where_with_category = where_clause
                params_with_category = [*params]
                if normalized_category:
                    where_with_category = f"{where_with_category} AND {json_category_clause}"
                    params_with_category.append(normalized_category)
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM practice_choice_questions WHERE {where_with_category}",
                        tuple(params_with_category),
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    f"""
                    SELECT question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata, updated_at
                    FROM practice_choice_questions
                    WHERE {where_with_category}
                    ORDER BY question_id ASC
                    LIMIT ? OFFSET ?
                    """,
                    tuple([*params_with_category, limit, offset]),
                ).fetchall()
            else:
                # JSON1 不可用时，先按基础条件拉全量，再以内存按 metadata.category 过滤并分页，保证 total/分页一致。
                all_rows = conn.execute(
                    f"""
                    SELECT question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata, updated_at
                    FROM practice_choice_questions
                    WHERE {where_clause}
                    ORDER BY question_id ASC
                    """,
                    tuple(params),
                ).fetchall()
                if normalized_category:
                    filtered_rows = []
                    for row in all_rows:
                        parsed_metadata = self._safe_json_loads(dict(row).get("metadata"), {})
                        row_category = str((parsed_metadata or {}).get("category", "")).strip().lower()
                        if row_category == normalized_category:
                            filtered_rows.append(row)
                else:
                    filtered_rows = list(all_rows)
                total = len(filtered_rows)
                rows = filtered_rows[offset : offset + limit]

        items: list[dict] = []
        for row in rows:
            item = dict(row)
            item["options"] = self._safe_json_loads(item.get("options"), [])
            item["answer_keys"] = self._safe_json_loads(item.get("answer_keys"), [])
            item["source"] = self._safe_json_loads(item.get("source"), {})
            item["metadata"] = self._safe_json_loads(item.get("metadata"), {})
            items.append(item)
        return items, total

    def upsert_coding_question(self, payload: dict) -> None:
        """幂等写入编程练习题。"""
        with self._session() as conn:
            conn.execute(
                """
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
                  updated_at = datetime('now')
                """,
                (
                    str(payload["question_id"]),
                    str(payload["slug"]),
                    str(payload["title"]),
                    str(payload["difficulty"]),
                    json.dumps(payload.get("topic_tags") or [], ensure_ascii=False),
                    str(payload["prompt_markdown"]),
                    str(payload["input_spec"]),
                    str(payload["output_spec"]),
                    str(payload.get("constraints_text") or ""),
                    json.dumps(payload.get("sample_cases") or [], ensure_ascii=False),
                    json.dumps(payload.get("judge_cases") or [], ensure_ascii=False),
                    json.dumps(payload.get("self_test_case") or {}, ensure_ascii=False),
                    json.dumps(payload.get("starter_codes") or {}, ensure_ascii=False),
                    json.dumps(payload.get("source") or {}, ensure_ascii=False),
                ),
            )

    def list_coding_questions(self) -> list[dict]:
        """读取编程练习题列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT question_id, slug, title, difficulty, topic_tags, prompt_markdown, input_spec, output_spec,
                       constraints_text, sample_cases, judge_cases, self_test_case, starter_codes, source, updated_at
                FROM coding_questions
                ORDER BY difficulty ASC, question_id ASC
                """
            ).fetchall()
        return [self._decode_coding_question(dict(row)) for row in rows]

    def get_coding_question(self, question_id: str) -> dict | None:
        """按题目 ID 查询编程练习题。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT question_id, slug, title, difficulty, topic_tags, prompt_markdown, input_spec, output_spec,
                       constraints_text, sample_cases, judge_cases, self_test_case, starter_codes, source, updated_at
                FROM coding_questions
                WHERE question_id = ?
                LIMIT 1
                """,
                (question_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode_coding_question(dict(row))

    def create_or_get_coding_session(self, user_id: str, question_id: str) -> dict:
        """按用户和题目获取或创建编程练习会话。"""
        with self._session() as conn:
            existing = conn.execute(
                """
                SELECT session_id, user_id, question_id, status, last_language, last_opened_at, created_at, updated_at
                FROM coding_sessions
                WHERE user_id = ? AND question_id = ?
                LIMIT 1
                """,
                (user_id, question_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE coding_sessions
                    SET last_opened_at = datetime('now'), updated_at = datetime('now')
                    WHERE session_id = ?
                    """,
                    (existing["session_id"],),
                )
                refreshed = conn.execute(
                    """
                    SELECT session_id, user_id, question_id, status, last_language, last_opened_at, created_at, updated_at
                    FROM coding_sessions
                    WHERE session_id = ?
                    """,
                    (existing["session_id"],),
                ).fetchone()
                return dict(refreshed)

            session_id = f"code_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO coding_sessions(session_id, user_id, question_id, status, last_language)
                VALUES (?, ?, ?, 'ACTIVE', 'cpp')
                """,
                (session_id, user_id, question_id),
            )
            row = conn.execute(
                """
                SELECT session_id, user_id, question_id, status, last_language, last_opened_at, created_at, updated_at
                FROM coding_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return dict(row)

    def get_coding_session(self, user_id: str, session_id: str) -> dict | None:
        """查询当前用户的编程练习会话。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT session_id, user_id, question_id, status, last_language, last_opened_at, created_at, updated_at
                FROM coding_sessions
                WHERE session_id = ? AND user_id = ?
                LIMIT 1
                """,
                (session_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def get_coding_session_by_id(self, session_id: str) -> dict | None:
        """按主键查询编程练习会话。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT session_id, user_id, question_id, status, last_language, last_opened_at, created_at, updated_at
                FROM coding_sessions
                WHERE session_id = ?
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_coding_draft(
        self,
        user_id: str,
        session_id: str,
        question_id: str,
        language: str,
        source_code: str,
        result_payload: dict,
    ) -> dict:
        """保存编程练习草稿并同步更新最近语言。"""
        draft_id = f"draft_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            self._require_coding_session_owner(conn, user_id, session_id)
            conn.execute(
                """
                INSERT INTO coding_drafts(draft_id, session_id, user_id, question_id, language, source_code, last_result_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, language) DO UPDATE SET
                  source_code = excluded.source_code,
                  last_result_payload = excluded.last_result_payload,
                  updated_at = datetime('now')
                """,
                (
                    draft_id,
                    session_id,
                    user_id,
                    question_id,
                    language,
                    source_code,
                    json.dumps(result_payload or {}, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                UPDATE coding_sessions
                SET last_language = ?, updated_at = datetime('now'), last_opened_at = datetime('now')
                WHERE session_id = ? AND user_id = ?
                """,
                (language, session_id, user_id),
            )
            row = conn.execute(
                """
                SELECT draft_id, session_id, user_id, question_id, language, source_code, last_result_payload, updated_at, created_at
                FROM coding_drafts
                WHERE session_id = ? AND language = ?
                LIMIT 1
                """,
                (session_id, language),
            ).fetchone()
        return self._decode_coding_draft(dict(row))

    def get_coding_draft(self, user_id: str, session_id: str, language: str) -> dict | None:
        """读取指定语言的编程练习草稿。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT draft_id, session_id, user_id, question_id, language, source_code, last_result_payload, updated_at, created_at
                FROM coding_drafts
                WHERE session_id = ? AND user_id = ? AND language = ?
                LIMIT 1
                """,
                (session_id, user_id, language),
            ).fetchone()
        if not row:
            return None
        return self._decode_coding_draft(dict(row))

    def list_coding_drafts(self, user_id: str, session_id: str) -> list[dict]:
        """读取当前会话的全部语言草稿。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT draft_id, session_id, user_id, question_id, language, source_code, last_result_payload, updated_at, created_at
                FROM coding_drafts
                WHERE session_id = ? AND user_id = ?
                ORDER BY language ASC
                """,
                (session_id, user_id),
            ).fetchall()
        return [self._decode_coding_draft(dict(row)) for row in rows]

    def add_coding_submission(
        self,
        user_id: str,
        session_id: str,
        question_id: str,
        language: str,
        source_code: str,
        submit_type: str,
        result_payload: dict,
    ) -> dict:
        """保存运行或提交结果。"""
        submission_id = f"sub_{uuid.uuid4().hex[:12]}"
        status = str(result_payload.get("status") or "FAILED")
        passed_count = int(result_payload.get("passed_count") or 0)
        total_count = int(result_payload.get("total_count") or 0)
        with self._session() as conn:
            self._require_coding_session_owner(conn, user_id, session_id)
            conn.execute(
                """
                INSERT INTO coding_submissions(
                  submission_id, session_id, user_id, question_id, language, source_code, submit_type,
                  status, passed_count, total_count, result_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    session_id,
                    user_id,
                    question_id,
                    language,
                    source_code,
                    submit_type,
                    status,
                    passed_count,
                    total_count,
                    json.dumps(result_payload or {}, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                UPDATE coding_sessions
                SET status = CASE WHEN ? = 'ACCEPTED' AND ? = 'SUBMIT' THEN 'SOLVED' ELSE status END,
                    last_language = ?,
                    updated_at = datetime('now'),
                    last_opened_at = datetime('now')
                WHERE session_id = ? AND user_id = ?
                """,
                (status, submit_type, language, session_id, user_id),
            )
            row = conn.execute(
                """
                SELECT submission_id, session_id, user_id, question_id, language, source_code, submit_type,
                       status, passed_count, total_count, result_payload, created_at
                FROM coding_submissions
                WHERE submission_id = ?
                LIMIT 1
                """,
                (submission_id,),
            ).fetchone()
        return self._decode_coding_submission(dict(row))

    def list_coding_records(self, user_id: str) -> list[dict]:
        """读取当前用户的编程练习记录。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT
                  s.session_id,
                  s.question_id,
                  q.title,
                  q.difficulty,
                  s.status,
                  s.last_language,
                  s.last_opened_at,
                  s.created_at,
                  (
                    SELECT status
                    FROM coding_submissions sub
                    WHERE sub.session_id = s.session_id
                    ORDER BY sub.created_at DESC, sub.submission_id DESC
                    LIMIT 1
                  ) AS latest_submission_status
                FROM coding_sessions s
                JOIN coding_questions q ON q.question_id = s.question_id
                WHERE s.user_id = ?
                ORDER BY s.updated_at DESC, s.session_id DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _decode_coding_question(self, item: dict) -> dict:
        """解析编程题 JSON 字段。"""
        item["topic_tags"] = self._safe_json_loads(item.get("topic_tags"), [])
        item["sample_cases"] = self._safe_json_loads(item.get("sample_cases"), [])
        item["judge_cases"] = self._safe_json_loads(item.get("judge_cases"), [])
        item["self_test_case"] = self._safe_json_loads(item.get("self_test_case"), {})
        item["starter_codes"] = self._safe_json_loads(item.get("starter_codes"), {})
        item["source"] = self._safe_json_loads(item.get("source"), {})
        return item

    def _decode_coding_draft(self, item: dict) -> dict:
        """解析编程练习草稿 JSON 字段。"""
        item["last_result_payload"] = self._safe_json_loads(item.get("last_result_payload"), {})
        return item

    def _decode_coding_submission(self, item: dict) -> dict:
        """解析编程练习提交 JSON 字段。"""
        item["result_payload"] = self._safe_json_loads(item.get("result_payload"), {})
        return item

    def create_jd(
        self,
        user_id: str | None,
        source_type: str,
        company_id: str | None,
        title: str,
        job_role: str,
        content_text: str,
        storage_path: str | None = None,
        status: str = "READY",
    ) -> dict:
        """创建 JD 记录。"""
        jd_id = f"jd_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO job_descriptions(
                  jd_id, user_id, company_id, source_type, title, job_role, content_text, storage_path, status, is_deleted, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
                """,
                (jd_id, user_id, company_id, source_type, title, job_role, content_text, storage_path, status),
            )
            row = conn.execute("SELECT * FROM job_descriptions WHERE jd_id = ?", (jd_id,)).fetchone()
        return dict(row) if row else {}

    def get_jd(self, jd_id: str) -> dict | None:
        """查询单个 JD。"""
        with self._session() as conn:
            row = conn.execute("SELECT * FROM job_descriptions WHERE jd_id = ?", (jd_id,)).fetchone()
        return dict(row) if row else None

    def create_schedule(self, user_id: str, payload: dict) -> dict:
        """创建单次面试预约记录。"""
        schedule_id = f"sch_{uuid.uuid4().hex[:12]}"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_schedules(
                  schedule_id, user_id, plan_id, source_type, sequence_no, interview_id, title, resume_id, jd_id, job_role,
                  difficulty, input_mode, output_mode, session_name, question_types, voice_tone_id, duration_minutes,
                  scheduled_start_at, scheduled_end_at, timezone, status, cancel_reason, reminder_status, calendar_sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', '', '{}', '')
                """,
                (
                    schedule_id,
                    user_id,
                    payload.get("plan_id"),
                    str(payload.get("source_type") or "single"),
                    payload.get("sequence_no"),
                    str(payload.get("interview_id") or ""),
                    str(payload.get("title") or payload.get("session_name") or ""),
                    str(payload.get("resume_id") or ""),
                    str(payload.get("jd_id") or ""),
                    str(payload.get("job_role") or ""),
                    str(payload.get("difficulty") or "medium"),
                    str(payload.get("input_mode") or "text"),
                    str(payload.get("output_mode") or "text"),
                    str(payload.get("session_name") or ""),
                    json.dumps(payload.get("question_types") or ["project", "technical", "scenario"], ensure_ascii=False),
                    str(payload.get("voice_tone_id") or ""),
                    int(payload.get("duration_minutes") or 0),
                    str(payload.get("scheduled_start_at") or ""),
                    str(payload.get("scheduled_end_at") or ""),
                    str(payload.get("timezone") or "Asia/Shanghai"),
                ),
            )
            row = conn.execute(
                "SELECT * FROM interview_schedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()
        return dict(row) if row else {}

    def list_schedules(
        self,
        user_id: str,
        status: str | None,
        date_from: str | None,
        date_to: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """分页查询面试预约列表。"""
        where = "WHERE s.user_id = ?"
        params: list[object] = [user_id]
        if status:
            where += " AND s.status = ?"
            params.append(status)
        if date_from:
            where += " AND s.scheduled_start_at >= ?"
            params.append(date_from)
        if date_to:
            where += " AND s.scheduled_start_at <= ?"
            params.append(date_to)
        with self._session() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) AS cnt FROM interview_schedules s {where}",
                params,
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""
                SELECT
                  s.*,
                  COALESCE(r.filename, '') AS resume_file_name,
                  COALESCE(j.title, s.jd_id, '') AS jd_title
                FROM interview_schedules s
                LEFT JOIN resumes r ON r.resume_id = s.resume_id AND r.user_id = s.user_id
                LEFT JOIN job_descriptions j ON j.jd_id = s.jd_id
                {where}
                ORDER BY s.scheduled_start_at ASC, s.created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def get_schedule(self, schedule_id: str) -> dict | None:
        """查询单个面试预约。"""
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT
                  s.*,
                  COALESCE(r.filename, '') AS resume_file_name,
                  COALESCE(j.title, s.jd_id, '') AS jd_title
                FROM interview_schedules s
                LEFT JOIN resumes r ON r.resume_id = s.resume_id AND r.user_id = s.user_id
                LEFT JOIN job_descriptions j ON j.jd_id = s.jd_id
                WHERE s.schedule_id = ?
                """,
                (schedule_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_schedule_status(self, schedule_id: str, user_id: str, status: str) -> bool:
        """更新预约状态。"""
        with self._session() as conn:
            row = conn.execute(
                """
                UPDATE interview_schedules
                SET status = ?,
                    updated_at = datetime('now'),
                    started_at = CASE WHEN ? = 'in_progress' THEN COALESCE(started_at, datetime('now')) ELSE started_at END,
                    completed_at = CASE WHEN ? = 'completed' THEN COALESCE(completed_at, datetime('now')) ELSE completed_at END,
                    cancelled_at = CASE WHEN ? = 'cancelled' THEN COALESCE(cancelled_at, datetime('now')) ELSE cancelled_at END
                WHERE schedule_id = ? AND user_id = ?
                """,
                (status, status, status, status, schedule_id, user_id),
            )
        return row.rowcount > 0

    def cancel_schedule(self, schedule_id: str, user_id: str, reason: str) -> str | None:
        """取消预约并返回取消时间。"""
        with self._session() as conn:
            row = conn.execute(
                """
                UPDATE interview_schedules
                SET status = 'cancelled',
                    cancel_reason = ?,
                    cancelled_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE schedule_id = ? AND user_id = ? AND status IN ('scheduled', 'ready')
                """,
                (reason, schedule_id, user_id),
            )
            if row.rowcount <= 0:
                return None
            cancelled = conn.execute(
                "SELECT cancelled_at FROM interview_schedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()
        return str(cancelled["cancelled_at"]) if cancelled else None

    def bind_schedule_to_interview(self, schedule_id: str, user_id: str, interview_id: str) -> None:
        """为预约绑定真实面试会话。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE interview_schedules
                SET interview_id = ?, updated_at = datetime('now')
                WHERE schedule_id = ? AND user_id = ?
                """,
                (interview_id, schedule_id, user_id),
            )
            conn.execute(
                """
                UPDATE interview_sessions
                SET schedule_id = ?, source_type = 'scheduled'
                WHERE interview_id = ? AND user_id = ?
                """,
                (schedule_id, interview_id, user_id),
            )

    def mark_schedule_in_progress(self, schedule_id: str, user_id: str) -> None:
        """标记预约为进行中。"""
        self.update_schedule_status(schedule_id=schedule_id, user_id=user_id, status="in_progress")

    def list_jds(
        self,
        user_id: str,
        job_role: str | None = None,
        source_type: str | None = None,
        title: str | None = None,
    ) -> list[dict]:
        """查询用户可见 JD（系统预置 + 用户上传）。"""
        where = "WHERE is_deleted = 0 AND (source_type = 'SYSTEM_PRESET' OR user_id = ?)"
        params: list[object] = [user_id]
        if job_role:
            where += " AND job_role = ?"
            params.append(job_role)
        if source_type:
            where += " AND source_type = ?"
            params.append(source_type)
        if title:
            where += " AND title LIKE ?"
            params.append(f"%{title}%")
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT
                  j.jd_id,
                  j.user_id,
                  j.company_id,
                  COALESCE(c.name, '') AS company_name,
                  j.source_type,
                  j.title,
                  j.job_role,
                  j.status,
                  j.content_text,
                  j.created_at,
                  j.updated_at
                FROM job_descriptions j
                LEFT JOIN companies c ON c.company_id = j.company_id
                {where}
                ORDER BY j.created_at DESC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_companies(self) -> list[dict]:
        """查询公司列表。"""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT company_id, name, status, created_at, updated_at
                FROM companies
                WHERE status = 'ACTIVE'
                ORDER BY name ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_company(self, company_id: str) -> dict | None:
        """查询单个公司。"""
        with self._session() as conn:
            row = conn.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,)).fetchone()
        return dict(row) if row else None

    def soft_delete_jd(self, user_id: str, jd_id: str) -> None:
        """软删除用户上传 JD。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE job_descriptions
                SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
                WHERE jd_id = ? AND user_id = ? AND source_type = 'USER_UPLOAD' AND is_deleted = 0
                """,
                (jd_id, user_id),
            )

    def get_session(self, interview_id: str) -> dict | None:
        """查询单个会话。"""
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_scheduled_sessions(
        self,
        user_id: str,
        scheduled_from: str | None,
        scheduled_to: str | None,
        statuses: list[str] | None = None,
    ) -> list[dict]:
        """按预约时间范围查询当前用户的预约面试。"""
        where = [
            "s.user_id = ?",
            "COALESCE(s.scheduled_start_at, '') != ''",
        ]
        params: list[object] = [user_id]
        if scheduled_from:
            where.append("datetime(s.scheduled_start_at) >= datetime(?)")
            params.append(scheduled_from)
        if scheduled_to:
            where.append("datetime(s.scheduled_start_at) <= datetime(?)")
            params.append(scheduled_to)
        normalized_statuses = [str(item).strip().upper() for item in (statuses or []) if str(item).strip()]
        if normalized_statuses:
            placeholders = ", ".join("?" for _ in normalized_statuses)
            where.append(f"s.status IN ({placeholders})")
            params.extend(normalized_statuses)
        where_clause = " AND ".join(where)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT
                  s.interview_id,
                  s.session_name,
                  s.resume_id,
                  COALESCE(r.filename, '') AS resume_file_name,
                  s.job_role,
                  s.difficulty,
                  s.status,
                  s.scheduled_start_at,
                  s.started_at,
                  s.current_stage
                FROM interview_sessions s
                LEFT JOIN resumes r ON r.resume_id = s.resume_id AND r.user_id = s.user_id
                WHERE {where_clause}
                ORDER BY datetime(s.scheduled_start_at) ASC, s.interview_id ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def start_scheduled_session(self, user_id: str, interview_id: str) -> bool:
        """将已到点的预约会话切换为进行中。"""
        with self._session() as conn:
            row = conn.execute(
                """
                UPDATE interview_sessions
                SET status = 'ACTIVE',
                    duration_updated_at = datetime('now')
                WHERE interview_id = ?
                  AND user_id = ?
                  AND status = 'SCHEDULED'
                """,
                (interview_id, user_id),
            )
        return row.rowcount > 0

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
            conn.execute(
                """
                UPDATE interview_schedules
                SET status='completed',
                    completed_at=datetime('now'),
                    updated_at=datetime('now')
                WHERE interview_id = ? AND status != 'cancelled'
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
                INSERT INTO interview_reports(
                  interview_id, status, overall_score, strengths, weaknesses, suggestions,
                  dimension_scores, jd_resume_alignment, question_deep_dives, key_risks, final_recommendation, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(interview_id) DO UPDATE SET
                  status = excluded.status,
                  overall_score = excluded.overall_score,
                  strengths = excluded.strengths,
                  weaknesses = excluded.weaknesses,
                  suggestions = excluded.suggestions,
                  dimension_scores = excluded.dimension_scores,
                  jd_resume_alignment = excluded.jd_resume_alignment,
                  question_deep_dives = excluded.question_deep_dives,
                  key_risks = excluded.key_risks,
                  final_recommendation = excluded.final_recommendation,
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
                    report.get("dimension_scores", "[]"),
                    report.get("jd_resume_alignment", "[]"),
                    report.get("question_deep_dives", "[]"),
                    report.get("key_risks", "[]"),
                    report.get("final_recommendation", ""),
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

    def list_reports(
        self,
        user_id: str,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """分页查询用户报告列表。"""
        where = "WHERE s.user_id = ?"
        params: list[object] = [user_id]
        if status:
            where += " AND r.status = ?"
            params.append(status)
        with self._session() as conn:
            total = conn.execute(
                f"""
                SELECT COUNT(1) AS cnt
                FROM interview_reports r
                JOIN interview_sessions s ON s.interview_id = r.interview_id
                {where}
                """,
                params,
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""
                SELECT
                  r.interview_id,
                  r.status,
                  r.overall_score,
                  r.updated_at,
                  s.session_name,
                  s.job_role,
                  s.difficulty,
                  s.started_at,
                  s.finished_at
                FROM interview_reports r
                JOIN interview_sessions s ON s.interview_id = r.interview_id
                {where}
                ORDER BY datetime(r.updated_at) DESC, datetime(s.started_at) DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def create_turn_job(self, interview_id: str, user_id: str, stage: str, payload: dict) -> str:
        """创建轮次异步任务并返回 job_id。"""
        job_id = f"job_{uuid.uuid4().hex[:14]}"
        payload_for_storage = dict(payload)
        if "answer_audio_bytes" in payload_for_storage:
            payload_for_storage["answer_audio_bytes"] = "<binary>"
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_turn_jobs(job_id, interview_id, user_id, status, stage, payload_json)
                VALUES (?, ?, ?, 'PROCESSING', ?, ?)
                """,
                (job_id, interview_id, user_id, stage, json.dumps(payload_for_storage, ensure_ascii=False)),
            )
        return job_id

    def update_turn_job_status(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error_message: str = "",
    ) -> None:
        """更新轮次异步任务状态。"""
        with self._session() as conn:
            conn.execute(
                """
                UPDATE interview_turn_jobs
                SET status = ?, result_json = ?, error_message = ?, updated_at = datetime('now')
                WHERE job_id = ?
                """,
                (
                    status,
                    json.dumps(result or {}, ensure_ascii=False),
                    error_message,
                    job_id,
                ),
            )

    def get_turn_job(self, job_id: str) -> dict | None:
        """查询轮次异步任务。"""
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM interview_turn_jobs WHERE job_id = ?",
                (job_id,),
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
                  COALESCE(rv.filename, '') AS resume_file_name,
                  s.jd_id,
                  s.jd_snapshot_title,
                  COALESCE(j.source_type, '') AS jd_source_type,
                  s.job_role,
                  s.difficulty,
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
                LEFT JOIN job_descriptions j ON j.jd_id = s.jd_id
                LEFT JOIN resumes rv ON rv.resume_id = s.resume_id AND rv.user_id = s.user_id
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
                SELECT s.interview_id, s.resume_id, s.job_role, s.difficulty, s.status, s.started_at, s.finished_at, s.user_id
                     , s.jd_id, s.jd_snapshot_title, COALESCE(j.source_type, '') AS jd_source_type
                     , s.duration_seconds, s.duration_updated_at
                FROM interview_sessions s
                LEFT JOIN job_descriptions j ON j.jd_id = s.jd_id
                WHERE s.interview_id = ?
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
