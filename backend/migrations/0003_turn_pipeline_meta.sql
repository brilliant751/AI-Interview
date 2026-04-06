-- interview_turns 增加链路元数据字段
ALTER TABLE interview_turns ADD COLUMN input_source TEXT;
ALTER TABLE interview_turns ADD COLUMN asr_provider TEXT;
ALTER TABLE interview_turns ADD COLUMN llm_provider TEXT;
ALTER TABLE interview_turns ADD COLUMN tts_provider TEXT;
ALTER TABLE interview_turns ADD COLUMN degrade_flags TEXT NOT NULL DEFAULT '[]';
ALTER TABLE interview_turns ADD COLUMN trace_id TEXT;
ALTER TABLE interview_turns ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0;
