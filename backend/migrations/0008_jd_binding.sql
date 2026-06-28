-- JD 绑定能力：新增 JD 数据表并扩展面试会话字段
-- 迁移说明：
-- 1. job_descriptions 保存系统预置和用户上传的岗位描述。
-- 2. interview_sessions 保存 JD 快照，避免会话中途 JD 被修改影响提问。
-- 3. source_type 区分 SYSTEM_PRESET 和 USER_UPLOAD，便于权限判断。
-- 4. storage_path 支持文件型 JD，content_text 支持直接粘贴文本。
-- 5. jd_snapshot_content 是报告和问题生成的重要上下文来源。
-- 6. 相关索引提升按用户、岗位和来源筛选 JD 的性能。

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
