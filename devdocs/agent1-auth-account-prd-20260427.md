# Agent1 PRD：登录/注册/登出/忘记密码（2026-04-27）

## 1. 需求摘要
### 1.1 背景
当前系统采用固定 token（`user-token`/`admin-token`）鉴权，可用于联调，但不具备真实账号体系能力，无法满足用户自助注册、登录态管理、密码找回、会话安全审计等线上需求。

### 1.2 目标
建设完整账号认证闭环，覆盖：
- 注册（Register）
- 登录（Login）
- 登出（Logout）
- 忘记密码（Forgot Password + Reset Password）

并与现有接口鉴权依赖（`require_user`/`require_admin`）兼容迁移。

### 1.3 成功判定
- 用户可通过账号密码登录并访问受保护接口。
- 登出后 access token 失效（或被服务端拒绝）。
- 忘记密码流程可闭环完成，不泄露账号存在性。
- 现有业务接口在迁移后不需要改业务语义，仅替换鉴权来源。

## 2. 范围定义（In Scope / Out of Scope）
### 2.1 In Scope
- 用户认证域接口：注册、登录、登出、忘记密码、重置密码。
- 账号基础模型与状态：启用/禁用、邮箱验证状态、密码更新时间。
- Token 机制：Access Token + Refresh Token。
- 密码安全：哈希存储、强度校验、重置令牌一次性与过期控制。
- 前端认证状态管理：登录态缓存、路由守卫、401 统一处理。
- 审计日志：登录成功/失败、登出、重置密码申请与完成。

### 2.2 Out of Scope
- 第三方社交登录（微信/Google/GitHub）。
- 多因素认证（MFA/TOTP/短信验证码）。
- 风控引擎（设备指纹、行为评分、IP 智能封禁）。
- 管理后台 RBAC 全量权限系统（仅保留 user/admin 角色兼容）。

## 3. 接口定义（OpenAPI 风格草案）

### 3.1 认证接口

#### 3.1.1 注册
- `POST /api/v1/auth/register`
- 鉴权：无
- Request
```json
{
  "email": "user@example.com",
  "password": "P@ssw0rd123",
  "display_name": "张三"
}
```
- Response `201`
```json
{
  "user_id": "usr_xxx",
  "email": "user@example.com",
  "email_verified": false,
  "created_at": "2026-04-27T10:00:00Z"
}
```
- 错误码
  - `AUTH_409_EMAIL_EXISTS`
  - `AUTH_400_WEAK_PASSWORD`

#### 3.1.2 登录
- `POST /api/v1/auth/login`
- 鉴权：无
- Request
```json
{
  "email": "user@example.com",
  "password": "P@ssw0rd123"
}
```
- Response `200`
```json
{
  "access_token": "jwt_access",
  "refresh_token": "jwt_refresh",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "user_id": "usr_xxx",
    "email": "user@example.com",
    "display_name": "张三",
    "role": "user"
  }
}
```
- 错误码
  - `AUTH_401_INVALID_CREDENTIALS`
  - `AUTH_403_USER_DISABLED`

#### 3.1.3 刷新令牌
- `POST /api/v1/auth/refresh`
- 鉴权：无（使用 refresh token）
- Request
```json
{
  "refresh_token": "jwt_refresh"
}
```
- Response `200`
```json
{
  "access_token": "jwt_access_new",
  "refresh_token": "jwt_refresh_new",
  "token_type": "bearer",
  "expires_in": 1800
}
```
- 幂等：否（refresh token 轮换）

#### 3.1.4 登出
- `POST /api/v1/auth/logout`
- 鉴权：`Bearer access_token`
- Request
```json
{
  "refresh_token": "jwt_refresh"
}
```
- Response `204`
- 行为：使当前 refresh token 失效，access token 进入短期黑名单（可选实现）。

### 3.2 忘记密码接口

#### 3.2.1 发起忘记密码
- `POST /api/v1/auth/forgot-password`
- 鉴权：无
- Request
```json
{
  "email": "user@example.com"
}
```
- Response `202`
```json
{
  "status": "ACCEPTED"
}
```
- 约束：无论邮箱是否存在都返回同一响应，避免账号枚举。

#### 3.2.2 重置密码
- `POST /api/v1/auth/reset-password`
- 鉴权：无
- Request
```json
{
  "reset_token": "reset_xxx",
  "new_password": "NewP@ssw0rd123"
}
```
- Response `204`
- 错误码
  - `AUTH_401_RESET_TOKEN_INVALID`
  - `AUTH_410_RESET_TOKEN_EXPIRED`
  - `AUTH_400_WEAK_PASSWORD`

### 3.3 现有业务接口鉴权迁移约束
- 现有 `require_user` 改为校验 JWT access token，解析 `sub(user_id)` 与 `role`。
- 在迁移窗口内保留 `AI_INTERVIEW_USER_TOKEN/ADMIN_TOKEN` 兼容开关（仅 dev）。
- 未登录访问受保护接口统一返回：
```json
{
  "error": {
    "code": "AUTH_401",
    "message": "未提供认证信息"
  }
}
```

### 3.4 错误码总表（新增）
- `AUTH_400_WEAK_PASSWORD`
- `AUTH_400_EMAIL_FORMAT_INVALID`
- `AUTH_401_INVALID_CREDENTIALS`
- `AUTH_401_RESET_TOKEN_INVALID`
- `AUTH_401_REFRESH_TOKEN_INVALID`
- `AUTH_403_USER_DISABLED`
- `AUTH_409_EMAIL_EXISTS`
- `AUTH_410_RESET_TOKEN_EXPIRED`
- `AUTH_429_TOO_MANY_REQUESTS`

## 4. 数据模型草案

### 4.1 user_accounts
- `user_id` TEXT PK
- `email` TEXT UNIQUE NOT NULL
- `password_hash` TEXT NOT NULL
- `display_name` TEXT NOT NULL
- `role` TEXT NOT NULL DEFAULT `user`（枚举：`user`/`admin`）
- `status` TEXT NOT NULL DEFAULT `active`（枚举：`active`/`disabled`）
- `email_verified` INTEGER NOT NULL DEFAULT 0
- `last_login_at` DATETIME NULL
- `password_changed_at` DATETIME NOT NULL
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

### 4.2 auth_refresh_tokens
- `token_id` TEXT PK
- `user_id` TEXT NOT NULL FK
- `token_hash` TEXT NOT NULL UNIQUE
- `issued_at` DATETIME NOT NULL
- `expires_at` DATETIME NOT NULL
- `revoked_at` DATETIME NULL
- `replaced_by_token_id` TEXT NULL
- `ip` TEXT NULL
- `user_agent` TEXT NULL

### 4.3 auth_password_reset_tokens
- `reset_id` TEXT PK
- `user_id` TEXT NOT NULL FK
- `token_hash` TEXT NOT NULL UNIQUE
- `expires_at` DATETIME NOT NULL
- `used_at` DATETIME NULL
- `created_at` DATETIME NOT NULL

### 4.4 数据生命周期
- Access Token：短有效期（建议 30 分钟），不落库或仅黑名单短存。
- Refresh Token：落库存哈希，支持轮换与撤销。
- Reset Token：一次性使用，过期/使用后立即失效。

## 5. 前端交互与状态约束

### 5.1 页面与路由
- 新增页面：`/login`、`/register`、`/forgot-password`、`/reset-password`。
- 未登录访问受保护路由（`/prepare` `/interview` `/report` `/history`）重定向到 `/login`。

### 5.2 会话状态
- 登录成功：写入 access/refresh token，拉取 `me`（或登录响应 user）初始化用户态。
- access token 过期：自动尝试 `/auth/refresh` 一次；失败则清空登录态并跳转登录页。
- 登出：前端清空 token + 调用 `/auth/logout`。

### 5.3 交互细节
- 登录失败提示统一：`账号或密码错误`，不暴露具体字段。
- 忘记密码提示统一：`如邮箱存在，我们已发送重置邮件`。
- 密码强度提示前置到表单，减少提交后失败。

## 6. 非功能需求（性能/安全/可观测性/可用性）

### 6.1 性能
- 登录/注册/刷新 P95 < 300ms（不含邮件发送）。
- 忘记密码发起接口同步返回，邮件异步投递。

### 6.2 安全
- 密码仅存哈希，不存明文。
- Reset/Refresh token 仅存哈希，防止库泄露后直接重放。
- 所有认证相关接口启用限流（按 IP + 账号维度）。
- 错误返回避免账号枚举与时序侧信道。

### 6.3 可观测性
- 指标：登录成功率、401 比例、重置密码成功率、refresh 成功率。
- 日志：认证事件日志（中文），字段含 `event/user_id/ip/ua/result/reason`。

### 6.4 可用性
- 刷新令牌轮换失败可回退一次重登引导。
- 邮件渠道异常不影响核心登录能力。

## 7. 验收标准（Given-When-Then）

### AC-01 注册成功
- Given 新邮箱未注册
- When 调用 `POST /auth/register`
- Then 返回 `201` 且可用该账号登录。

### AC-02 注册冲突
- Given 邮箱已注册
- When 再次注册同邮箱
- Then 返回 `409 AUTH_409_EMAIL_EXISTS`。

### AC-03 登录成功
- Given 账号存在且密码正确
- When 调用 `POST /auth/login`
- Then 返回 `access_token + refresh_token`，可访问受保护接口。

### AC-04 登录失败
- Given 密码错误
- When 登录
- Then 返回 `401 AUTH_401_INVALID_CREDENTIALS`。

### AC-05 登出失效
- Given 用户已登录
- When 调用 `POST /auth/logout`
- Then refresh token 失效，后续 refresh 请求返回 401。

### AC-06 忘记密码防枚举
- Given 任意邮箱输入
- When 调用 `POST /auth/forgot-password`
- Then 均返回 `202`，响应文案一致。

### AC-07 重置密码闭环
- Given reset token 有效
- When 调用 `POST /auth/reset-password`
- Then 返回 `204` 且旧密码不可再登录。

### AC-08 过期 token 拦截
- Given reset token 过期
- When 调用重置接口
- Then 返回 `410 AUTH_410_RESET_TOKEN_EXPIRED`。

### AC-09 路由守卫
- Given 用户未登录
- When 访问 `/interview`
- Then 前端自动跳转 `/login`。

## 8. 风险与待确认项（按优先级）

### P0
- 重置密码邮件通道选型未定（SMTP/第三方服务），影响忘记密码可用性。
- token 黑名单策略（仅 refresh 撤销 vs access 黑名单）未定，影响登出实时性与存储成本。

### P1
- 账号唯一标识策略（仅 email vs 用户名+email）未定，影响注册与登录表单设计。
- 是否启用邮箱验证后才可使用核心功能未定，影响转化与风控平衡。

### P2
- 密码规则强度门槛（长度/字符集/历史密码复用）需产品安全策略确认。

## 9. 可交接物、DoD 与落盘信息

### 9.1 可交接物
- 认证域接口契约（HTTP 请求/响应/错误码）。
- 数据模型草案（账户、refresh token、reset token）。
- 前端状态流与路由守卫约束。
- Given-When-Then 验收标准集。

### 9.2 完成定义（DoD）
- 无关键歧义，接口可直接进入 Agent2 规划。
- AC 可直接映射 Agent4 测试用例。
- 风险与待确认项可追踪且标注影响范围。
- 文档已落盘 `devdocs/`，可供后续 Agent 直接引用。

### 9.3 Context7 查询记录（按仓库约定）
- `libraryId`: `/fastapi/fastapi`
- 查询关键词：
  - `OAuth2PasswordBearer login JWT token`
  - `password hashing pwdlib argon2`
- 关键结论：
  - 登录接口标准返回 `access_token` + `token_type=bearer`。
  - 推荐 JWT + `sub` claim 标识用户，并在依赖中统一解码校验。
  - 密码需哈希存储，推荐现代哈希方案（Argon2）。
- 适用版本：FastAPI 文档示例（查询时可用版本含 `0.128.0`）。

### 9.4 落盘信息
- 目标路径：`devdocs/agent1-auth-account-prd-20260427.md`
- 产出角色：Agent 1（需求与接口设计）
