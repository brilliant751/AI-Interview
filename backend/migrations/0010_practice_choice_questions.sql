-- 练习题库与面试题库解耦：新增 practice_choice_questions
-- 迁移说明：
-- 1. practice_choice_questions 专门服务选择题练习，不再复用面试问答题库。
-- 2. question_type 目前固定 single_choice，保留字段用于未来扩展多选或判断题。
-- 3. options/answer_keys/source/metadata 使用 JSON 字符串存储。
-- 4. explanation 保存答题解析，练习记录页可以直接展示。
-- 5. domain 对应岗位方向或技术域，索引用于快速筛题。
-- 6. updated_at 支持后续导入脚本做增量更新和审计。
CREATE TABLE IF NOT EXISTS practice_choice_questions (
  question_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  question_type TEXT NOT NULL CHECK(question_type = 'single_choice'),
  stem TEXT NOT NULL,
  options TEXT NOT NULL DEFAULT '[]',
  answer_keys TEXT NOT NULL DEFAULT '[]',
  explanation TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '{}',
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_practice_choice_domain_type
ON practice_choice_questions(domain, question_type);
