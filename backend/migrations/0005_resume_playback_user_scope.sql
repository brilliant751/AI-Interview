-- 账户归属与简历回放能力增强
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
