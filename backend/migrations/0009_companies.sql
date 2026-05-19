-- 公司表与 JD 绑定公司字段

CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE job_descriptions ADD COLUMN company_id TEXT;

CREATE INDEX IF NOT EXISTS idx_jd_company_id ON job_descriptions(company_id);

