-- 新增认证账号体系表结构与索引
-- 迁移说明：
-- 1. user_accounts 承载正式邮箱账号、密码哈希、角色和状态。
-- 2. auth_refresh_tokens 支持 refresh token 轮换、撤销和过期控制。
-- 3. password_reset_tokens 支持忘记密码流程，token_hash 避免明文 token 入库。
-- 4. auth_audit_logs 记录认证事件，方便排查登录失败和异常重置。
-- 5. 索引用于邮箱登录、token 查询和审计列表检索。
-- 6. 所有 token 表都用哈希字段做唯一约束，降低泄漏后的风险。

CREATE TABLE IF NOT EXISTS user_accounts (
  user_id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  status TEXT NOT NULL DEFAULT 'active',
  email_verified INTEGER NOT NULL DEFAULT 0,
  last_login_at TEXT,
  password_changed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
  token_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  issued_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  replaced_by_token_id TEXT,
  ip TEXT,
  user_agent TEXT
);

CREATE TABLE IF NOT EXISTS auth_password_reset_tokens (
  reset_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts(email);
CREATE INDEX IF NOT EXISTS idx_refresh_user_expires ON auth_refresh_tokens(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_reset_user_expires ON auth_password_reset_tokens(user_id, expires_at);
