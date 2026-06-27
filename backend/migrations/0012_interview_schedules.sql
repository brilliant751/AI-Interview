-- 单次模拟面试预约 MVP
-- 迁移说明：
-- 1. interview_schedules 保存预约日历事件和其关联面试会话。
-- 2. source_type/plan_id/sequence_no 为未来多场计划预约预留。
-- 3. scheduled_start_at/end_at/timezone 共同描述用户看到的预约时间。
-- 4. status 覆盖 scheduled、ready、in_progress、completed、missed、cancelled。
-- 5. calendar_token 用于日历文件下载或外部订阅场景。
-- 6. cancel_reason/cancelled_at 保留取消审计信息。
-- 7. interview_id 为空表示尚未真正开始面试。

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
  reminder_status TEXT NOT NULL DEFAULT '{}',
  calendar_sync_status TEXT NOT NULL DEFAULT '',
  started_at TEXT,
  completed_at TEXT,
  cancelled_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE interview_sessions ADD COLUMN schedule_id TEXT;
ALTER TABLE interview_sessions ADD COLUMN source_type TEXT NOT NULL DEFAULT 'instant';

CREATE INDEX IF NOT EXISTS idx_session_schedule_id ON interview_sessions(schedule_id);
CREATE INDEX IF NOT EXISTS idx_schedules_user_start ON interview_schedules(user_id, scheduled_start_at DESC);
CREATE INDEX IF NOT EXISTS idx_schedules_status ON interview_schedules(user_id, status, scheduled_start_at DESC);
CREATE INDEX IF NOT EXISTS idx_schedules_plan_sequence ON interview_schedules(plan_id, sequence_no);
