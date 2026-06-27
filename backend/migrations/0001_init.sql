-- 初始化核心表结构与索引
-- 迁移说明：
-- 1. 这是项目最早的基础表集合，负责让空 SQLite 数据库具备最小可运行结构。
-- 2. 后续迁移会继续补充认证、JD、预约、练习和报告字段。
-- 3. CREATE TABLE IF NOT EXISTS 保证脚本重复执行时不会破坏已有表。
-- 4. 初始表字段相对简单，服务启动时的仓储初始化会兼容更多新字段。
-- 5. journal_mode=WAL 用于提升本地开发和测试时的并发读写体验。
-- 6. 该文件应保持向后兼容，不直接删除历史字段。
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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
  generation_mode TEXT NOT NULL DEFAULT 'mock',
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

CREATE INDEX IF NOT EXISTS idx_sessions_job_role_created_at ON interview_sessions(job_role, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turns_interview_id_created_at ON interview_turns(interview_id, created_at);
CREATE INDEX IF NOT EXISTS idx_question_bank_role_no ON question_bank(role, question_no);
