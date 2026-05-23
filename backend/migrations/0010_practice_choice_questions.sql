-- 练习题库与面试题库解耦：新增 practice_choice_questions
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
