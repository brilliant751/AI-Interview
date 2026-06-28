-- interview_turns 增加 generation_mode 字段
-- 迁移说明：
-- 1. generation_mode 标记本轮问题来自 local_ai、fallback_template 还是 mock。
-- 2. 默认 mock 兼容历史数据，避免旧轮次读取时报空。
-- 3. 前端使用该字段展示当前提问模式。
-- 4. 报告和排障也可以根据该字段判断模型调用质量。
-- 5. 该字段不影响状态机，只描述生成来源。
ALTER TABLE interview_turns ADD COLUMN generation_mode TEXT NOT NULL DEFAULT 'mock';
