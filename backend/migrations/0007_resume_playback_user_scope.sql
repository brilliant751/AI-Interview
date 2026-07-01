-- 账户归属与简历回放能力增强
-- 迁移说明：
-- 1. 给 resumes/interview_sessions/interview_turns 补充 user_id，实现用户数据隔离。
-- 2. 简历增加软删除字段，防止历史面试引用文件时直接丢失记录。
-- 3. started_at/finished_at 支持历史列表、报告页和回放页展示时间线。
-- 4. 对历史空 user_id 回填 user-default，兼容旧开发数据。
-- 5. 该迁移以 UPDATE 回填为主，不删除任何历史会话。
-- 6. 后续接口会基于 user_id 做访问控制。
ALTER TABLE resumes ADD COLUMN user_id TEXT;
ALTER TABLE resumes ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE resumes ADD COLUMN deleted_at TEXT;
ALTER TABLE resumes ADD COLUMN updated_at TEXT;

ALTER TABLE interview_sessions ADD COLUMN user_id TEXT;
ALTER TABLE interview_sessions ADD COLUMN started_at TEXT;
ALTER TABLE interview_sessions ADD COLUMN finished_at TEXT;

ALTER TABLE interview_turns ADD COLUMN user_id TEXT;

UPDATE resumes
SET user_id = COALESCE(NULLIF(user_id, ''), 'user-default')
WHERE user_id IS NULL OR user_id = '';

UPDATE resumes
SET updated_at = COALESCE(NULLIF(updated_at, ''), datetime('now'))
WHERE updated_at IS NULL OR updated_at = '';

UPDATE interview_sessions
SET user_id = COALESCE(NULLIF(user_id, ''), 'user-default')
WHERE user_id IS NULL OR user_id = '';

UPDATE interview_sessions
SET started_at = COALESCE(NULLIF(started_at, ''), created_at)
WHERE started_at IS NULL OR started_at = '';

UPDATE interview_turns
SET user_id = (
  SELECT s.user_id FROM interview_sessions s WHERE s.interview_id = interview_turns.interview_id
)
WHERE user_id IS NULL OR user_id = '';

CREATE INDEX IF NOT EXISTS idx_resumes_user_created ON resumes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON interview_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turns_user_interview_created ON interview_turns(user_id, interview_id, created_at ASC);
