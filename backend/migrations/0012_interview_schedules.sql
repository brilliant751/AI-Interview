-- 单次模拟面试预约 MVP

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
