-- 初始化基础角色数据
INSERT OR IGNORE INTO users(user_id, role) VALUES
  ('user-default', 'user'),
  ('admin-default', 'admin');

