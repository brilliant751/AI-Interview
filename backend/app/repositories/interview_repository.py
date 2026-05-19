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
                  jd_id TEXT,
                  jd_snapshot_title TEXT NOT NULL DEFAULT '',
                  jd_snapshot_content TEXT NOT NULL DEFAULT '',
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_created ON resumes(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON interview_sessions(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_jd_id ON interview_sessions(jd_id)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_user_interview_created ON interview_turns(user_id, interview_id, created_at ASC)"
            )
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
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions(
                  interview_id, user_id, resume_id, jd_id, jd_snapshot_title, jd_snapshot_content, session_name, question_types, job_role, difficulty, input_mode, output_mode, status, current_stage, follow_up_count, technical_count, duration_seconds, duration_updated_at, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 'SELF_INTRO', 0, 0, 0, datetime('now'), datetime('now'))
                """,
                (
                    interview_id,
                    user_id,
                    payload["resume_id"],
                    snapshot.get("jd_id"),
                    str(snapshot.get("jd_snapshot_title") or ""),
                    str(snapshot.get("jd_snapshot_content") or ""),
                    str(payload.get("session_name") or ""),
                    json.dumps(payload.get("question_types") or ["project", "technical", "scenario"], ensure_ascii=False),
                    payload["job_role"],
                    payload["difficulty"],
                    payload["input_mode"],
                    payload["output_mode"],
                ),
            )
        return {"interview_id": interview_id, "current_stage": "SELF_INTRO"}

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
                  s.jd_id,
                  s.jd_snapshot_title,
                  COALESCE(j.source_type, '') AS jd_source_type,
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
                LEFT JOIN job_descriptions j ON j.jd_id = s.jd_id
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
