# API 接口说明

更新时间：2026-06-28

本文按业务域整理 AI-Interview 的主要 API。完整机器可读契约以 `openapi/openapi.yaml` 和运行时 Swagger `/docs` 为准。

## 1. 基础约定

默认前缀：

```text
/api/v1
```

默认本地地址：

```text
http://localhost:18500/api/v1
```

如果使用旧后端脚本，后端可能在 `8000`：

```text
http://localhost:8000/api/v1
```

## 2. 鉴权

除登录、注册、找回密码、重置密码等公开接口外，业务接口通常需要：

```http
Authorization: Bearer <access_token>
```

登录接口会返回：

- `access_token`
- `refresh_token`
- `expires_in`
- `user`

前端会在 401 时调用 refresh 接口换取新 token。

## 3. 幂等

前端会为请求自动添加：

```http
X-Idempotency-Key: <uuid>
```

后端部分写接口会使用幂等键避免重复提交。管理员触发导入任务、创建题库任务等场景尤其需要幂等。

## 4. 错误格式

后端统一错误通常形如：

```json
{
  "error": {
    "code": "AUTH_401_INVALID_CREDENTIALS",
    "message": "账号或密码错误"
  }
}
```

前端使用 `parseApiError` 解析错误，并展示中文提示。

## 5. 认证接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` | 注册账号 |
| POST | `/auth/login` | 登录并签发 token |
| POST | `/auth/refresh` | 刷新 access token 并轮换 refresh token |
| POST | `/auth/logout` | 登出并撤销 refresh token |
| POST | `/auth/forgot-password` | 发起找回密码流程 |
| POST | `/auth/reset-password` | 使用 reset token 重置密码 |
| GET | `/auth/me` | 获取当前用户 |

注册请求：

```json
{
  "email": "user@example.com",
  "password": "Password123",
  "display_name": "张三"
}
```

登录请求：

```json
{
  "email": "user@example.com",
  "password": "Password123"
}
```

## 6. 简历接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/resumes` | 上传简历 |
| GET | `/resumes` | 分页查询简历 |
| GET | `/resumes/{resume_id}/file` | 获取简历原文件 |
| DELETE | `/resumes/{resume_id}` | 删除简历 |

上传使用 `multipart/form-data`，字段名为 `file`。支持 PDF、DOC、DOCX。

## 7. 公司与 JD 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/companies` | 查询公司列表 |
| POST | `/jds` | 新增岗位描述 |
| GET | `/jds` | 查询岗位描述 |
| DELETE | `/jds/{jd_id}` | 删除用户上传 JD |

JD 上传使用 `multipart/form-data`，常用字段：

- `job_role`
- `title`
- `content_text`
- `company_id`
- `file`

## 8. 面试接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/interviews` | 创建面试会话 |
| GET | `/interviews/voice-tones` | 查询面试官语气配置 |
| POST | `/interviews/{interview_id}/turns` | 提交文本轮次 |
| POST | `/interviews/{interview_id}/turns/audio` | 提交音频轮次 |
| GET | `/interviews/{interview_id}/turn-jobs/{job_id}` | 查询轮次任务结果 |
| GET | `/interviews/{interview_id}/turns` | 查询轮次列表 |
| POST | `/interviews/{interview_id}/finish` | 结束面试并触发报告 |
| POST | `/interviews/{interview_id}/pause` | 暂停面试 |
| POST | `/interviews/{interview_id}/resume` | 恢复面试 |
| GET | `/interviews/schedules` | 查询会话级预约列表 |
| POST | `/interviews/{interview_id}/start` | 开始已预约会话 |
| GET | `/interviews/paused` | 查询暂停面试 |
| GET | `/interviews/{interview_id}/status` | 查询会话状态 |
| GET | `/interviews/{interview_id}/playback` | 查询面试回放 |

创建面试请求示例：

```json
{
  "resume_id": "res_xxx",
  "job_role": "java",
  "difficulty": "medium",
  "input_mode": "text",
  "output_mode": "text",
  "session_name": "Java 后端模拟面试",
  "question_types": ["project", "technical", "scenario"],
  "jd_id": "",
  "voice_tone_id": ""
}
```

提交文本轮次请求：

```json
{
  "stage": "SELF_INTRO",
  "answer_text": "我主要负责后端接口和缓存优化..."
}
```

音频轮次使用 `multipart/form-data`：

- `stage`
- `file`

## 9. 面试预约接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/interview-schedules` | 创建预约 |
| GET | `/interview-schedules` | 查询预约列表 |
| GET | `/interview-schedules/{schedule_id}` | 查询预约详情 |
| POST | `/interview-schedules/{schedule_id}/cancel` | 取消预约 |
| POST | `/interview-schedules/{schedule_id}/start` | 开始预约面试 |
| GET | `/interview-schedules/{schedule_id}/calendar.ics` | 下载日历文件 |

创建预约请求示例：

```json
{
  "title": "周一晚 Java 面试",
  "scheduled_start_at": "2026-06-28T20:00:00.000Z",
  "duration_minutes": 45,
  "resume_id": "res_xxx",
  "job_role": "java",
  "difficulty": "medium",
  "input_mode": "text",
  "output_mode": "text",
  "question_types": ["project", "technical", "scenario"]
}
```

## 10. 历史与报告接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/interviews/history` | 查询历史面试 |
| DELETE | `/interviews/history/{interview_id}` | 删除历史面试 |
| GET | `/report` | 查询报告列表 |
| GET | `/report/{interview_id}` | 查询报告详情 |
| POST | `/report/{interview_id}/retry` | 重试报告生成 |

报告状态：

- `GENERATING`
- `READY`
- `FAILED`

## 11. 题库练习接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/practice/sessions` | 创建练习会话 |
| GET | `/practice/sessions/{practice_id}` | 查询练习会话 |
| POST | `/practice/sessions/{practice_id}/answers` | 提交练习答案 |
| POST | `/practice/sessions/{practice_id}/finish` | 结束练习 |
| GET | `/practice/records` | 查询练习记录 |
| GET | `/practice/overview` | 查询题库练习概览 |
| GET | `/practice/sessions/{practice_id}/records` | 查询单场练习明细 |

创建练习请求：

```json
{
  "job_role": "java",
  "mode": "sequence",
  "question_count": 10,
  "category_filters": ["technical", "project"]
}
```

## 12. 题库管理接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/practice/questions` | 管理端题库分页查询 |
| GET | `/practice/admin/question-bank` | 管理端题库分页查询兼容路径 |
| POST | `/practice/questions/upload` | 上传 Markdown 题库 |
| POST | `/practice/questions` | 单题录入 |
| GET | `/practice/questions/import-tasks/{task_id}` | 查询题库导入任务 |
| GET | `/practice/admin/import-tasks/{task_id}` | 查询导入任务兼容路径 |

上传 Markdown 使用 `multipart/form-data`：

- `job_role`
- `file`

## 13. 编程练习接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/coding-practice/questions` | 查询编程题列表 |
| POST | `/coding-practice/sessions` | 创建或恢复编程练习会话 |
| GET | `/coding-practice/sessions/{session_id}` | 查询会话详情 |
| POST | `/coding-practice/sessions/{session_id}/run` | 运行自测 |
| POST | `/coding-practice/sessions/{session_id}/submit` | 正式提交 |
| GET | `/coding-practice/records` | 查询编程练习记录 |

运行或提交请求：

```json
{
  "language": "cpp",
  "source_code": "#include <bits/stdc++.h>\nint main(){return 0;}"
}
```

返回结果状态可能包括：

- `ACCEPTED`
- `COMPILE_ERROR`
- `RUNTIME_ERROR`
- `TIME_LIMIT_EXCEEDED`
- `WRONG_ANSWER`

## 14. 管理端接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/imports/materials` | 触发材料导入/知识库重建 |
| GET | `/admin/imports/materials/{task_id}` | 查询导入任务 |
| GET | `/admin/providers/health` | 查询 provider 健康状态 |

触发材料导入请求：

```json
{
  "rebuild_mode": "full",
  "roles": ["java", "web"],
  "dry_run": false,
  "chunk_model": "qwen2.5:7b",
  "embedding_model": "nomic-embed-text",
  "task_type": "full_pipeline"
}
```

## 15. 调试方式

### Swagger

启动后端后访问：

```text
http://localhost:18500/docs
```

### Postman

导入：

- `postman/AI-Interview.postman_collection.json`
- `postman/AI-Interview.postman_environment.json`

### PowerShell 快速验证注册接口

```powershell
$body = @{
  email = "demo@example.com"
  password = "Password123"
  display_name = "Demo"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:18500/api/v1/auth/register" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

