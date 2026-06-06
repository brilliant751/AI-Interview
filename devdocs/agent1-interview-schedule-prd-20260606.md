# Agent1 需求与接口设计：面试日程预约（2026-06-06）

## 1. 需求摘要
- 在现有 AI 面试大厅中新增“面试预约”能力，允许用户提前选择未来日期与时间创建面试日程。
- 用户预约时即可填写当前面试支持的全部参数，包括简历、岗位方向或 JD、难度、输入模式、面试名称、题目类型等。
- 用户登录后，如果当天存在预约中的面试，前端需弹出通知提醒。
- 到达预约时间后，用户可从前端直接开始对应面试；未到开始时间不得提前进入答题态。

## 2. 范围定义（In/Out）
- In Scope
  - 后端为面试会话增加预约开始时间与 `SCHEDULED` 状态。
  - 新增预约列表查询接口，供日历与登录提醒复用。
  - 新增“开始预约面试”接口，只有到点后才允许切换到正式面试。
  - 前端在面试大厅新增日历视图、预约明细与开始入口。
  - 前端登录后弹出当天预约提醒。
  - 同步更新 OpenAPI 与 Postman。
- Out of Scope
  - 短信、邮件、站外推送提醒。
  - 多人协同面试、面试官排班。
  - 自动在预约时刻强制跳转进面试。

## 3. 接口定义
- `POST /api/v1/interviews`
  - 新增可选字段 `scheduled_start_at`。
  - 未传时保持“立即开始”现有行为。
  - 传入未来时间时创建 `SCHEDULED` 会话，不可直接提交轮次。
- `GET /api/v1/interviews/schedules`
  - 按时间范围查询当前用户预约面试列表。
  - 供日历面板、当天提醒、开始入口共用。
- `POST /api/v1/interviews/{interview_id}/start`
  - 将已到预约时间的 `SCHEDULED` 会话切换到 `ACTIVE` 并返回当前题目。

## 4. 数据模型草案
- `interview_sessions`
  - 新增 `scheduled_start_at TEXT`
  - `status` 扩展支持 `SCHEDULED`
- `InterviewCreateRequest`
  - 新增 `scheduled_start_at?: string`
- `InterviewCreateResponse`
  - 新增 `status`
  - 新增 `scheduled_start_at`
- `InterviewStatusResponse`
  - 新增 `scheduled_start_at`
  - 新增 `start_available`
- 新增预约列表响应模型
  - 包含 `interview_id`、`session_name`、`scheduled_start_at`、`status`、`job_role`、`difficulty`、`resume_file_name`、`start_available`

## 5. 前端交互与状态约束
- 面试大厅展示月历组件，用户可查看某天已有预约并点击查看详情。
- 创建面试弹窗支持切换“立即开始 / 预约开始”。
- 预约模式下必须填写未来时间，且前端禁止选择过去时间。
- 未到预约时间时，“开始面试”按钮置灰并给出明确提示。
- 登录后若当天存在预约面试，弹出通知，通知内可跳转到面试大厅。

## 6. 非功能需求
- 不新增额外第三方 UI 依赖，优先复用现有 `antd` 能力。
- 查询预约列表时只拉取当前视图所需时间范围，避免无界拉取。
- 所有日志与错误提示保持中文。

## 7. 验收标准（Given-When-Then）
- Given 用户填写完整参数并选择未来时间，When 提交创建，Then 返回 `SCHEDULED` 会话且日历中可见。
- Given 用户预约了今天的面试，When 用户登录成功进入系统，Then 前端弹出当天预约提醒。
- Given 预约时间未到，When 用户尝试开始面试，Then 前后端均阻止并提示未到开始时间。
- Given 预约时间已到，When 用户点击开始面试，Then 会话切换为 `ACTIVE` 并进入答题页。
- Given 用户未选择预约时间且直接创建，When 提交成功，Then 保持现有立即开始行为不回归。

## 8. 风险与待确认项
- 风险：现有面试大厅与答题页复用同一页面，状态切换处理不当会导致创建成功后仍停留大厅。
- 风险：前后端时区不统一会导致“今天提醒”或“是否到点”判断偏差，因此需统一以 ISO 时间传输并显式按范围查询。

## 9. 落盘信息
- `devdocs/agent1-interview-schedule-prd-20260606.md`
