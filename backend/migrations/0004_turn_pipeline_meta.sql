-- interview_turns 增加链路元数据字段
-- 迁移说明：
-- 1. 这些字段记录每轮面试经过了哪些 provider。
-- 2. input_source 区分 TEXT、ASR_CLIENT、ASR_SERVER 等输入来源。
-- 3. degrade_flags 保存 LLM/TTS 等降级原因，供前端和报告展示。
-- 4. trace_id 用于关联服务端结构化日志。
-- 5. latency_ms 用于评估单轮链路耗时。
-- 6. 默认值保证历史轮次也能被新响应模型读取。
ALTER TABLE interview_turns ADD COLUMN input_source TEXT;
ALTER TABLE interview_turns ADD COLUMN asr_provider TEXT;
ALTER TABLE interview_turns ADD COLUMN llm_provider TEXT;
ALTER TABLE interview_turns ADD COLUMN tts_provider TEXT;
ALTER TABLE interview_turns ADD COLUMN degrade_flags TEXT NOT NULL DEFAULT '[]';
ALTER TABLE interview_turns ADD COLUMN trace_id TEXT;
ALTER TABLE interview_turns ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0;
