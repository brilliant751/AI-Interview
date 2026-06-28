-- 开发环境默认管理员账号回填（幂等）
-- 默认密码哈希对应示例密码：Admin1234
-- 迁移说明：
-- 1. 该账号只用于本地开发和课程演示的管理端入口。
-- 2. INSERT OR IGNORE 避免覆盖已经修改过的管理员账号。
-- 3. 密码以 PBKDF2 哈希保存，不在数据库中保存明文。
-- 4. 生产环境应通过独立初始化流程创建真实管理员。
-- 5. email_verified=1 是为了跳过演示环境中的邮箱验证步骤。
-- 6. 若后续变更示例密码，需要同步更新开发文档。

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
