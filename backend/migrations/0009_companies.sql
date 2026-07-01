-- 公司表与 JD 绑定公司字段
-- 迁移说明：
-- 1. companies 是 JD 的基础资料表，用于按公司维护岗位描述。
-- 2. name 使用 UNIQUE，避免重复创建同名公司。
-- 3. job_descriptions.company_id 是弱绑定字段，便于旧数据保持为空。
-- 4. status 预留启停能力，后续管理端可以隐藏停用公司。
-- 5. idx_jd_company_id 用于岗位库按公司筛选。

CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE job_descriptions ADD COLUMN company_id TEXT;

CREATE INDEX IF NOT EXISTS idx_jd_company_id ON job_descriptions(company_id);
