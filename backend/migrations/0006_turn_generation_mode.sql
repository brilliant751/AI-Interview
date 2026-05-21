-- interview_turns 增加 generation_mode 字段
ALTER TABLE interview_turns ADD COLUMN generation_mode TEXT NOT NULL DEFAULT 'mock';
