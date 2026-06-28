-- 初始化基础角色数据
-- 迁移说明：
-- 1. user-default/admin-default 是开发和早期接口测试的默认身份。
-- 2. INSERT OR IGNORE 保证重复执行不会覆盖已有角色。
-- 3. 后续认证账号体系会在 user_accounts 中保存更完整的登录信息。
-- 4. 这里保留 users 表种子，兼容仍依赖基础角色表的旧逻辑。
-- 5. 生产环境可通过真实注册/管理员创建流程生成用户。
INSERT OR IGNORE INTO users(user_id, role) VALUES
  ('user-default', 'user'),
  ('admin-default', 'admin');
