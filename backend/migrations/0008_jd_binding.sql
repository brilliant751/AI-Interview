-- JD 绑定能力：新增 JD 数据表并扩展面试会话字段

CREATE TABLE IF NOT EXISTS job_descriptions (
  jd_id TEXT PRIMARY KEY,
  user_id TEXT,
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

CREATE INDEX IF NOT EXISTS idx_jd_user_created ON job_descriptions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jd_role_source ON job_descriptions(job_role, source_type);

ALTER TABLE interview_sessions ADD COLUMN jd_id TEXT;
ALTER TABLE interview_sessions ADD COLUMN jd_snapshot_title TEXT NOT NULL DEFAULT '';
ALTER TABLE interview_sessions ADD COLUMN jd_snapshot_content TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_session_jd_id ON interview_sessions(jd_id);
