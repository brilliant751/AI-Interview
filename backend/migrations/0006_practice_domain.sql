-- 题库练习域持久化表结构升级
-- 说明：
-- 1. 该脚本显式重建 legacy weak practice 表，避免 CREATE TABLE IF NOT EXISTS 静默保留旧约束。
-- 2. 复制规则与仓储启动升级逻辑保持一致：保留合法数据，按 created_at/session_question_id/rowid 的稳定顺序去重。

PRAGMA foreign_keys=OFF;

DROP TABLE IF EXISTS practice_answers__legacy;
DROP TABLE IF EXISTS practice_session_questions__legacy;
DROP TABLE IF EXISTS practice_sessions__legacy;

CREATE TABLE IF NOT EXISTS practice_sessions (
  practice_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  job_role TEXT NOT NULL,
  mode TEXT NOT NULL,
  question_count INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS practice_session_questions (
  session_question_id TEXT PRIMARY KEY,
  practice_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  question_order INTEGER NOT NULL,
  source_question_id TEXT,
  category TEXT,
  stem TEXT NOT NULL,
  analysis TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS practice_answers (
  answer_id TEXT PRIMARY KEY,
  practice_id TEXT NOT NULL,
  session_question_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  answer_text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(practice_id, session_question_id)
);

ALTER TABLE practice_answers RENAME TO practice_answers__legacy;
ALTER TABLE practice_session_questions RENAME TO practice_session_questions__legacy;
ALTER TABLE practice_sessions RENAME TO practice_sessions__legacy;

CREATE TABLE IF NOT EXISTS practice_sessions (
  practice_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  job_role TEXT NOT NULL,
  mode TEXT NOT NULL,
  question_count INTEGER NOT NULL CHECK(question_count > 0),
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS practice_session_questions (
  session_question_id TEXT PRIMARY KEY,
  practice_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  question_order INTEGER NOT NULL CHECK(question_order > 0),
  source_question_id TEXT,
  category TEXT,
  stem TEXT NOT NULL,
  analysis TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(practice_id, question_order),
  UNIQUE(practice_id, session_question_id),
  FOREIGN KEY (practice_id) REFERENCES practice_sessions(practice_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS practice_answers (
  answer_id TEXT PRIMARY KEY,
  practice_id TEXT NOT NULL,
  session_question_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  answer_text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(practice_id, session_question_id),
  FOREIGN KEY (practice_id) REFERENCES practice_sessions(practice_id) ON DELETE CASCADE,
  FOREIGN KEY (practice_id, session_question_id) REFERENCES practice_session_questions(practice_id, session_question_id) ON DELETE CASCADE
);

INSERT INTO practice_sessions(practice_id, user_id, job_role, mode, question_count, status, created_at)
SELECT
  practice_id,
  user_id,
  job_role,
  mode,
  CASE WHEN question_count IS NULL OR question_count <= 0 THEN 1 ELSE question_count END,
  COALESCE(NULLIF(status, ''), 'ACTIVE'),
  COALESCE(NULLIF(created_at, ''), datetime('now'))
FROM practice_sessions__legacy
WHERE practice_id IS NOT NULL
  AND user_id IS NOT NULL
  AND job_role IS NOT NULL
  AND mode IS NOT NULL;

WITH ranked_questions AS (
  SELECT
    session_question_id,
    practice_id,
    user_id,
    question_order,
    source_question_id,
    category,
    stem,
    analysis,
    COALESCE(NULLIF(created_at, ''), datetime('now')) AS created_at,
    ROW_NUMBER() OVER (
      PARTITION BY practice_id, question_order
      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, session_question_id ASC, rowid ASC
    ) AS order_rn,
    ROW_NUMBER() OVER (
      PARTITION BY practice_id, session_question_id
      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, question_order ASC, rowid ASC
    ) AS snapshot_rn
  FROM practice_session_questions__legacy
  WHERE practice_id IS NOT NULL
    AND user_id IS NOT NULL
    AND session_question_id IS NOT NULL
    AND question_order > 0
    AND stem IS NOT NULL
    AND stem != ''
)
INSERT INTO practice_session_questions(
  session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis, created_at
)
SELECT
  q.session_question_id,
  q.practice_id,
  q.user_id,
  q.question_order,
  q.source_question_id,
  q.category,
  q.stem,
  q.analysis,
  q.created_at
FROM ranked_questions q
JOIN practice_sessions s
  ON s.practice_id = q.practice_id
 AND s.user_id = q.user_id
WHERE q.order_rn = 1
  AND q.snapshot_rn = 1;

WITH ranked_answers AS (
  SELECT
    answer_id,
    practice_id,
    session_question_id,
    user_id,
    answer_text,
    COALESCE(NULLIF(created_at, ''), datetime('now')) AS created_at,
    ROW_NUMBER() OVER (
      PARTITION BY answer_id
      ORDER BY COALESCE(NULLIF(created_at, ''), datetime('now')) ASC, rowid ASC
    ) AS answer_rn
  FROM practice_answers__legacy
  WHERE answer_id IS NOT NULL
    AND practice_id IS NOT NULL
    AND session_question_id IS NOT NULL
    AND user_id IS NOT NULL
    AND answer_text IS NOT NULL
    AND answer_text != ''
)
INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text, created_at)
SELECT
  a.answer_id,
  a.practice_id,
  a.session_question_id,
  a.user_id,
  a.answer_text,
  a.created_at
FROM ranked_answers a
JOIN practice_sessions s
  ON s.practice_id = a.practice_id
 AND s.user_id = a.user_id
JOIN practice_session_questions q
  ON q.practice_id = a.practice_id
 AND q.session_question_id = a.session_question_id
 AND q.user_id = a.user_id
WHERE a.answer_rn = 1;

DROP TABLE IF EXISTS practice_answers__legacy;
DROP TABLE IF EXISTS practice_session_questions__legacy;
DROP TABLE IF EXISTS practice_sessions__legacy;

CREATE INDEX IF NOT EXISTS idx_practice_sessions_user_created ON practice_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_practice_questions_session_order ON practice_session_questions(practice_id, question_order ASC);
CREATE INDEX IF NOT EXISTS idx_practice_answers_user_session ON practice_answers(user_id, practice_id, created_at ASC);

PRAGMA foreign_keys=ON;
