# 前后端契约说明

本文档记录 AI-Interview 前端和后端之间的主要接口契约、状态字段和错误处理约定。它用于降低联调成本，不改变现有接口行为。

## 1. 通用请求约定

前端统一使用 `frontend/src/api/client.ts` 中的 `apiClient`。

通用行为：

- 自动设置 `baseURL`。
- 自动设置请求超时。
- 自动注入 `Authorization: Bearer <accessToken>`。
- 自动注入 `X-Idempotency-Key`。
- 401 时尝试 refresh token。
- refresh 成功后重放原请求。
- refresh 失败后清理本地会话并跳转登录页。

后端统一使用 `/api/v1` 前缀。

## 2. 错误响应

后端业务错误使用统一结构：

```json
{
  "error": {
    "code": "STATE_409",
    "message": "面试已结束，禁止继续提交"
  }
}
```

前端通过 `parseApiError(error)` 解析：

- `code`
- `message`

页面应优先展示 `message`，必要时根据 `code` 做特殊提示。

## 3. 幂等键

前端每个请求默认带 `X-Idempotency-Key`。

后端目前在这些场景中重点使用：

- 创建面试。
- 提交轮次。
- 上传简历。
- 上传 JD。
- 创建预约。
- 触发导入任务。

幂等键用于处理：

- 用户重复点击按钮。
- 网络重试。
- 页面请求被浏览器重复发送。

前端如果需要保证同一个按钮动作多次重试使用同一个 key，可以自行传入固定 key。

## 4. 认证契约

登录响应：

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "...",
  "user": {
    "user_id": "usr_xxx",
    "email": "user@example.com",
    "display_name": "用户名",
    "role": "user",
    "status": "active"
  }
}
```

前端保存：

- `ai_interview_access_token`
- `ai_interview_refresh_token`
- `ai_interview_user`

如果三者不完整，前端应视为未登录。

## 5. 简历契约

上传简历：

- 方法：`POST /resumes`
- Content-Type：`multipart/form-data`
- 字段：`file`

响应：

```json
{
  "resume_id": "res_xxx",
  "parse_status": "READY"
}
```

简历列表：

- 方法：`GET /resumes`
- 参数：`page`, `page_size`

简历文件预览：

- 方法：`GET /resumes/{resume_id}/file`
- 前端使用 `responseType: "blob"`。

## 6. JD 契约

上传 JD：

- 方法：`POST /jds`
- Content-Type：`multipart/form-data`

支持字段：

- `job_role`
- `title`
- `file`
- `content_text`
- `company_id`

JD 列表：

- 方法：`GET /jds`
- 可选参数：`job_role`, `source_type`, `title`

前端应允许两种来源：

- 系统预置 JD。
- 用户上传 JD。

## 7. 面试创建契约

创建面试：

- 方法：`POST /interviews`

请求关键字段：

- `resume_id`
- `job_role`
- `difficulty`
- `input_mode`
- `output_mode`
- `session_name`
- `question_types`
- `jd_id`
- `scheduled_start_at`
- `voice_tone_id`

响应关键字段：

- `interview_id`
- `status`
- `current_stage`
- `first_question`
- `scheduled_start_at`
- `tts_audio_url`
- `voice_tone_id`
- `voice_tone_name`

如果 `status=ACTIVE`，前端进入面试页。

如果 `status=SCHEDULED`，前端提示预约成功，不进入作答页。

## 8. 面试轮次契约

文本提交：

- 方法：`POST /interviews/{interview_id}/turns`

请求字段：

- `stage`
- `answer_text`
- `asr_text`
- `answer_audio_url`
- `answer_audio_format`

响应不是下一题，而是异步任务：

```json
{
  "interview_id": "int_xxx",
  "job_id": "turn_job_xxx",
  "status": "PROCESSING"
}
```

前端随后轮询：

- 方法：`GET /interviews/{interview_id}/turn-jobs/{job_id}`

任务状态：

- `PROCESSING`
- `READY`
- `FAILED`

`READY` 时 `result` 包含：

- `stage`
- `next_question`
- `follow_up_count`
- `live_score`
- `output_mode`
- `tts_audio_url`
- `pipeline_meta`

## 9. 音频轮次契约

音频提交：

- 方法：`POST /interviews/{interview_id}/turns/audio`
- Content-Type：`multipart/form-data`

字段：

- `stage`
- `file`

响应同样是异步任务。

## 10. Pipeline Meta 契约

`pipeline_meta` 用于前端展示当前链路状态。

字段：

- `input_source`
- `providers`
- `provider_status`
- `degrade_flags`
- `trace_id`
- `latency_ms`
- `generation_mode`

`generation_mode` 取值：

- `local_ai`
- `fallback_template`
- `mock`

前端不应根据 `providers` 猜测生成模式，应直接使用 `generation_mode`。

## 11. 面试状态契约

状态接口：

- 方法：`GET /interviews/{interview_id}/status`

用途：

- 刷新页面后恢复当前题。
- 轮询会话是否结束。
- 获取累计时长。
- 恢复暂停会话。

关键字段：

- `interview_id`
- `status`
- `current_stage`
- `current_question`
- `follow_up_count`
- `duration_seconds`
- `duration_updated_at`
- `input_mode`
- `output_mode`
- `tts_audio_url`

前端显示时长时，应以 `duration_seconds + 当前增量` 计算 ACTIVE 状态下的实时秒数。

## 12. 预约契约

预约管理接口使用 schedule 维度：

- `POST /interview-schedules`
- `GET /interview-schedules`
- `GET /interview-schedules/{schedule_id}`
- `POST /interview-schedules/{schedule_id}/cancel`
- `POST /interview-schedules/{schedule_id}/start`
- `GET /interview-schedules/{schedule_id}/calendar.ics`

面试大厅和提醒使用 interview session 维度：

- `GET /interviews/schedules`
- `POST /interviews/{interview_id}/start`

两套接口不要混用 ID：

- `schedule_id` 用于预约管理。
- `interview_id` 用于面试会话。

## 13. 报告契约

查询报告：

- 方法：`GET /report/{interview_id}`

状态：

- `GENERATING`
- `READY`
- `FAILED`

`READY` 状态下主要字段：

- `overall_score`
- `strengths`
- `weaknesses`
- `suggestions`
- `dimension_scores`
- `jd_resume_alignment`
- `question_deep_dives`
- `key_risks`
- `final_recommendation`

报告列表：

- 方法：`GET /report`
- 参数：`page`, `page_size`, `status`

重试报告：

- 方法：`POST /report/{interview_id}/retry`

## 14. 题库练习契约

创建练习：

- 方法：`POST /practice/sessions`

请求：

- `job_role`
- `mode`
- `question_count`
- `category_filters`

响应包含当前题：

- `practice_id`
- `status`
- `completed_count`
- `current_question`
- `question_strategy`

提交答案：

- 方法：`POST /practice/sessions/{practice_id}/answers`

请求：

- `session_question_id`
- `answer_text`

响应包含下一题或结束状态。

## 15. 编程练习契约

题目列表：

- 方法：`GET /coding-practice/questions`

创建或恢复 session：

- 方法：`POST /coding-practice/sessions`
- 请求：`question_id`

自测：

- 方法：`POST /coding-practice/sessions/{session_id}/run`

正式提交：

- 方法：`POST /coding-practice/sessions/{session_id}/submit`

请求：

- `language`
- `source_code`

响应：

- `status`
- `passed_count`
- `total_count`
- `message`
- `results`
- `compile_output`

## 16. 管理端导入契约

材料导入：

- 方法：`POST /admin/imports/materials`

响应：

- `task_id`
- `status`
- `stage`
- `progress`
- `idempotency_hit`

查询任务：

- 方法：`GET /admin/imports/materials/{task_id}`

题库管理导入：

- `POST /practice/questions/upload`
- `POST /practice/questions`
- `GET /practice/questions/import-tasks/{task_id}`

任务终态：

- `SUCCESS`
- `FAILED`
- `PARTIAL_SUCCESS`

前端在终态后应停止轮询。

