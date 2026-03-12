# 前端基础骨架与路由体系 PRD（Agent 1）

## 1. 需求摘要

### 1.1 背景与目标
- 主要目标：搭建 `React + TypeScript + Vite` 前端工程骨架，并完成基础路由体系（登录页、首页、面试页、报告页）。
- 次要目标：制定前端 AGENTS 开发规范（组件设计、状态管理、API 调用），**规范文本最终撰写由 Agent 3 完成**。

### 1.2 业务价值
- 为后续面试流程、报告可视化、鉴权接入提供稳定前端底座。
- 建立统一开发约束，降低多人并行开发的冲突与返工成本。

### 1.3 关联里程碑
- 对齐 `plan/TASK.md` 的 KR1「前端架构」P0/P1：
  - P0：骨架 + 路由 + Zustand 基本状态
  - P1：Axios API Client（鉴权头、统一错误、刷新令牌）

## 2. 范围定义（In Scope / Out of Scope）

### 2.1 In Scope
- 初始化 `frontend` 工程，技术栈固定：
  - `React + TypeScript + Vite`
  - `Ant Design`（统一组件库）
  - `Tailwind CSS`（统一样式与响应式）
  - `Zustand`（全局状态）
  - `Axios`（统一 API 调用）
- 路由体系（占位页可运行）：
  - `/login` 登录页
  - `/` 首页
  - `/interview/:sessionId?` 面试页
  - `/report/:reportId?` 报告页
- 目录规范：`components/`、`pages/`、`services/` 等最佳实践分层。
- 文档交付：
  - `frontend/README.md`（项目结构、运行方式、开发规范）
  - `frontend/AGENTS.md`（前端 Agent 协作规范：组件、状态、API）
- 状态管理基线：
  - 用户态（登录信息、token、权限）
  - 面试会话态（当前 session、轮次、问题上下文摘要）
  - 计时态（开始/暂停/剩余秒数/超时标记）
- Axios Client 基线：
  - `baseURL`、超时、鉴权头注入
  - 统一错误映射
  - 401 场景刷新令牌与请求重放策略

### 2.2 Out of Scope
- 不包含真实业务 UI 细节与视觉稿还原（本期仅占位页）。
- 不包含后端真实接口开发与联调。
- 不包含面试对话、报告图表、代码运行等业务功能实现。
- 不包含 E2E 自动化体系与埋点平台接入（可在后续迭代）。

## 3. 接口定义（OpenAPI 风格草案）

> 说明：以下接口用于前端骨架联通设计，后端可在后续版本按此契约实现或兼容。

### 3.1 认证接口

#### POST `/api/auth/login`
- 鉴权：否
- 请求体：
  - `email: string`（必填）
  - `password: string`（必填）
- 响应 `200`：
  - `accessToken: string`
  - `refreshToken: string`
  - `expiresIn: number`
  - `user: UserProfile`
- 错误码：
  - `AUTH_401_INVALID_CREDENTIALS`
  - `AUTH_429_TOO_MANY_REQUESTS`

#### POST `/api/auth/refresh`
- 鉴权：否（使用 refresh token）
- 请求体：
  - `refreshToken: string`（必填）
- 响应 `200`：
  - `accessToken: string`
  - `refreshToken?: string`
  - `expiresIn: number`
- 错误码：
  - `AUTH_401_REFRESH_EXPIRED`

#### POST `/api/auth/logout`
- 鉴权：是
- 请求体：可空
- 响应 `200`：`{ success: true }`

### 3.2 用户信息接口

#### GET `/api/users/me`
- 鉴权：是
- 响应 `200`：`UserProfile`
- 错误码：
  - `AUTH_401_UNAUTHORIZED`

### 3.3 面试会话接口（占位）

#### GET `/api/interviews/{sessionId}`
- 鉴权：是
- 响应 `200`：
  - `sessionId: string`
  - `status: 'INIT'|'RUNNING'|'PAUSED'|'FINISHED'`
  - `currentRound: number`
  - `remainingSeconds: number`

### 3.4 报告接口（占位）

#### GET `/api/reports/{reportId}`
- 鉴权：是
- 响应 `200`：
  - `reportId: string`
  - `overallScore: number`
  - `dimensions: Array<{ key: string; score: number }>`

### 3.5 统一错误结构
- `code: string`（机器可读错误码）
- `message: string`（展示文案）
- `requestId?: string`（排查追踪）
- `details?: Record<string, unknown>`

## 4. 数据模型草案

### 4.1 UserProfile
- `id: string`（必填）
- `name: string`（必填）
- `email: string`（必填）
- `roles: string[]`（默认 `['user']`）

### 4.2 AuthState（Zustand）
- `accessToken: string | null`
- `refreshToken: string | null`
- `isAuthenticated: boolean`（默认 `false`）
- `user: UserProfile | null`
- `actions`：`setAuth`、`clearAuth`、`hydrateAuth`
- 持久化建议：仅持久化 `refreshToken` 与最小用户快照；`accessToken` 优先内存态

### 4.3 InterviewSessionState（Zustand）
- `sessionId: string | null`
- `status: 'IDLE'|'RUNNING'|'PAUSED'|'ENDED'`
- `round: number`（默认 `0`）
- `questionIds: string[]`
- `actions`：`startSession`、`updateRound`、`pauseSession`、`endSession`、`resetSession`

### 4.4 TimerState（Zustand）
- `startedAt: number | null`
- `remainingSeconds: number`
- `isRunning: boolean`
- `isTimeout: boolean`
- `actions`：`start`、`tick`、`pause`、`resume`、`reset`

## 5. 验收标准（Given-When-Then）

### AC-1 工程可启动
- Given 已安装 Node 与包管理器
- When 执行安装与启动命令
- Then 本地可成功启动页面，且无阻断级报错

### AC-2 路由占位页可访问
- Given 应用已启动
- When 访问 `/login`、`/`、`/interview/123`、`/report/456`
- Then 均可渲染对应页面占位内容，且无白屏

### AC-3 路由守卫行为
- Given 未登录状态
- When 访问受保护页面（`/`、`/interview/*`、`/report/*`）
- Then 自动重定向到 `/login`

### AC-4 登录态持久化
- Given 已成功登录并写入状态
- When 浏览器刷新
- Then 必要会话信息可恢复（至少用户身份与 refresh token）

### AC-5 Zustand 状态完整性
- Given 面试会话进行中
- When 执行会话切换、计时开始/暂停/恢复
- Then `auth/interview/timer` 三类状态按预期更新且互不污染

### AC-6 Axios 拦截器生效
- Given 已配置 Axios 实例
- When 发起 API 请求与异常响应
- Then 自动附加认证信息，统一输出错误结构；401 时触发刷新并可重试原请求

### AC-7 文档交付完整
- Given 前端目录初始化完成
- When 检查文档
- Then 存在 `frontend/README.md` 与 `frontend/AGENTS.md`，且内容覆盖组件设计、状态管理、API 调用规范

## 6. 非功能要求与实施约束

### 6.1 技术约束
- UI 组件统一采用 `Ant Design`，减少重复造轮子。
- 样式统一采用 `Tailwind CSS`，要求具备移动端基础响应式。
- API 访问统一走 Axios Client，禁止页面内直接裸调 `fetch/axios`。

### 6.2 质量约束
- 代码风格与 lint 规则需可在 CI 执行。
- 路由切换错误率目标：`0`。
- 关键状态丢失率目标：`<= 1%`（本地开发基线）。

## 7. 风险与待确认项（按优先级）

### P0
- 路由方案待确认：是否明确采用 `react-router-dom v6+`。
  - 影响：页面跳转、守卫实现、懒加载写法全部受影响。
- 已确认：是
- Token 刷新策略待确认：并发 401 风暴时是否采用队列去重。
  - 影响：可能出现重复刷新、请求雪崩或覆盖新 token。
- 已确认：是

### P1
- 持久化介质待确认：`localStorage` vs `sessionStorage`。
  - 影响：登录态生命周期、安全与用户体验差异。
- 已确认：按需选用，符合最佳实践
- AGENTS 规范粒度待确认：是否包含组件模板、命名规则、目录门禁。
  - 影响：后续多人协作一致性和评审成本。
- 已确认：是

### P2
- Ant Design 与 Tailwind 组合规范待确认：原子类与组件样式冲突边界。
  - 影响：样式覆盖复杂度与可维护性。
- 已确认：
组件外层布局：用 Tailwind（flex/grid/gap/margin/响应式）
组件内观与状态：优先用 Antd token/props（type/size/variant）
仅在外层容器用 Tailwind 改尺寸与间距，不直接覆盖 .ant-btn 等核心类
需要主题统一时，先改 Antd Theme Token，再考虑 Tailwind 补充
禁止在业务代码里大量写 .ant-* 选择器覆盖

## 8. 交接给 Agent 2 的可交接物
- 本 PRD 已定义可执行范围、路由与状态边界、接口草案、AC 与风险。
- Agent 2 可据此拆解为：
  - 文件级改动计划（`frontend` 初始化与目录）
  - 路由与守卫实现顺序
  - Zustand store 与 Axios client 的实施顺序
  - README/AGENTS 文档生成计划

## 9. 完成定义（DoD）
- 需求边界清晰，无关键歧义。
- 接口与状态模型可直接用于开发与测试设计。
- 验收标准覆盖正常流、异常流、边界流。
- 风险项均附影响范围并可追踪。
- 文档已落盘至 `devdocs/frame`。

## 10. Context7 核对记录（本次）
- `libraryId=/vitejs/vite`，关键词：`React + TypeScript scaffold`, `create vite command`, `Node version baseline`
- `libraryId=/pmndrs/zustand`，关键词：`TypeScript store pattern`, `slices pattern`, `persist middleware`
- `libraryId=/axios/axios-docs`，关键词：`axios.create`, `request/response interceptors`, `401 refresh and retry`

关键结论：
- Vite 推荐通过 `create-vite` 脚手架创建项目；当前文档显示 Node 版本基线需较新（文档片段为 `20.19+ / 22.12+`）。
- Zustand 推荐以 `TypeScript + persist` 组合实现可恢复状态，并建议在“组合后的总 store”层应用中间件。
- Axios 官方文档支持通过实例拦截器处理鉴权头、统一错误与 401 后刷新重试。

版本适用说明：
- 本 PRD 以当前 Context7 返回的官方文档片段为准；具体落地版本应在 Agent 2 规划时与仓库锁定版本再次对齐。

## 11. 落盘信息
- 目标路径：`devdocs/frame/prd-frontend-foundation-react-ts-vite.md`
- 产出角色：Agent 1（需求与接口设计）
