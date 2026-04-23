# URGENT 待办（Agent5 维护）

- 最后更新：2026-04-05
- 依据评审：本次 Agent5 复验（P2-6）
- 维护规则：仅保留“未完成”且短周期必须推进的事项；已落地项在下次 review 时删除。

## P0（阻断放行）

### 1. 面试阶段状态机缺失 `PROJECT_DEEP_DIVE`
- 当前状态：未完成
- 现状证据：
  - `backend/app/domain/interview_state.py` 缺少 `PROJECT_DEEP_DIVE`
  - `backend/app/services/interview_service.py` 从 `SELF_INTRO` 直接进入 `TECHNICAL`
- 完成标准：
  - 状态机补齐 `SELF_INTRO -> PROJECT_DEEP_DIVE -> TECHNICAL -> BEHAVIORAL -> END`
  - 对应接口、服务、测试用例同步覆盖

## P1（高优先）

### 2. API 契约与 PRD 不一致（路径/枚举/字段）
- 当前状态：未完成
- 现状证据：
  - PRD 报告路径为 `/api/v1/interviews/{interviewId}/report`，实现为 `/api/v1/report/{interview_id}`
  - PRD 岗位枚举为 `java_backend/web_frontend`，实现为 `java/web`
  - PRD 难度为 `1-5`，实现为 `easy/medium/hard`
- 完成标准：
  - PRD、OpenAPI、后端 schema、前端 API 类型四处一致
  - Postman 集合同步更新并可回放通过

### 3. 语音与问答链路仍为占位实现
- 当前状态：未完成
- 现状证据：
  - `backend/app/services/voice_service.py` 为 mock ASR/TTS
  - `backend/app/services/question_workflow.py` 为模板化提问
- 完成标准：
  - 接入真实 ASR/TTS/LLM（至少 dev 环境可用）
  - 失败时保留可观测的降级路径

### 4. 报告结构未达 PRD 目标
- 当前状态：未完成
- 现状证据：
  - 现有仅 `overall_score + strengths/weaknesses/suggestions`
  - 缺少 PRD 要求的维度分与亮点结构
- 完成标准：
  - 报告结构与 PRD 对齐（含维度化评分）
  - 报告接口、前端展示与文档统一

## P2（中优先）

### 5. 管理导入接口缺少异步任务化与状态追踪
- 当前状态：未完成
- 现状证据：
  - `backend/app/api/v1/admin.py` 以同步子进程串行执行导入（当前仅路径迁移到 `backend/assets/scripts/data/**`）
- 完成标准：
  - 返回 `task_id`
  - 提供任务查询接口（运行中/成功/失败 + 错误信息）
