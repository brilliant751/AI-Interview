-- 开发环境默认管理员账号回填（幂等）
-- 默认密码哈希对应示例密码：Admin1234

INSERT OR IGNORE INTO user_accounts(
  user_id,
  email,
  password_hash,
  display_name,
  role,
  status,
  email_verified,
  created_at,
  updated_at
) VALUES (
  'admin-default',
  'admin@local',
  'pbkdf2_sha256$120000$0fc674386f5d6d6e9644a35f960e3d6f$9f2e7d69ea8909ed357fb0533c4c2d7d1880174226209ef26d44a0827991ce5d',
  '系统管理员',
  'admin',
  'active',
  1,
  datetime('now'),
  datetime('now')
);
