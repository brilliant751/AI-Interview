-- 新增语气配置表与会话语气快照字段

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

CREATE INDEX IF NOT EXISTS idx_voice_tone_profiles_active_sort
  ON voice_tone_profiles(is_active, sort_order);

ALTER TABLE interview_sessions ADD COLUMN voice_tone_id TEXT NOT NULL DEFAULT '';
ALTER TABLE interview_sessions ADD COLUMN voice_tone_name TEXT NOT NULL DEFAULT '';
ALTER TABLE interview_sessions ADD COLUMN voice_tone_instructions TEXT NOT NULL DEFAULT '';
ALTER TABLE interview_sessions ADD COLUMN voice_tone_speed REAL NOT NULL DEFAULT 1.0;

INSERT INTO voice_tone_profiles(tone_id, tone_name, description, base_instructions, speed, is_active, sort_order)
VALUES
  ('tone_default', '标准面试官', '语气专业平衡，适合作为默认配置', '语气自然专业，表达清晰，句间停顿自然，避免播报腔。', 1.0, 1, 10),
  ('tone_encouraging', '鼓励引导型', '更温和、更具鼓励感，适合新手候选人', '语气友好、耐心、积极，先认可再追问，保持清晰自然。', 0.96, 1, 20),
  ('tone_challenging', '高压追问型', '更偏技术压测，语速略快，追问更直接', '语气冷静客观，提问直接明确，重点词轻微重读，保持礼貌。', 1.04, 1, 30)
ON CONFLICT(tone_id) DO UPDATE SET
  tone_name = excluded.tone_name,
  description = excluded.description,
  base_instructions = excluded.base_instructions,
  speed = excluded.speed,
  is_active = excluded.is_active,
  sort_order = excluded.sort_order,
  updated_at = datetime('now');
