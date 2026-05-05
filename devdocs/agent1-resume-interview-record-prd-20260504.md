# Agent1 PRD：账户关联的简历管理与面试记录回放（2026-05-04）

## 1. 需求摘要
### 1.1 背景
当前系统已有简历上传与面试流程，但“简历归属账户管理”和“完整面试问答回放”能力不足，用户无法在账号维度统一管理自己的简历与历史面试过程。

### 1.2 目标
- 建立“账户 -> 简历 -> 面试会话 -> 面试轮次问答”的完整归属链路。
- 提供简历管理界面能力（列表、上传、删除）。
- 保存每次面试的完整问答与关键元数据，并支持按会话回放查看。

### 1.3 成功判定
- 用户仅能看到和操作自己的简历与面试记录。
- 删除简历后，系统行为可预期（受引用限制或软删除）。
- 面试历史可查看到每一轮问答内容（含时间顺序），支持回放浏览。

## 2. 范围定义（In Scope / Out of Scope）
### 2.1 In Scope
- 账号隔离：所有简历、面试会话、问答轮次必须绑定 `user_id`。
- 简历管理：上传、列表查询、删除。
- 面试记录留存：保存会话基础信息与轮次问答内容。
- 回放查看：会话列表 + 会话详情（按轮次展示问答）。
- 接口契约与错误码扩展。

### 2.2 Out of Scope
- 简历在线编辑（仅上传/删除/查看元数据）。
- 面试回放音频播放器高级能力（倍速、波形、片段裁剪）。
- 跨账号共享简历或会话。
- 面试记录导出 PDF/Word。

## 3. 接口定义（OpenAPI 风格草案）

### 3.1 鉴权与通用约束
- 所有接口需 `Bearer access_token`。
- 服务端从 token 解析 `user_id`，禁止通过请求参数传入目标用户。
- 所有查询默认只返回当前 `user_id` 的数据。

### 3.2 简历管理

#### 3.2.1 上传简历（保持路径，补充归属语义）
- `POST /api/v1/resumes`
- Content-Type: `multipart/form-data`
- Request
  - `file`: pdf/doc/docx（必填）
- Response `201`
```json
{
  "resume_id": "res_123",
  "file_name": "张三-后端简历.pdf",
  "parse_status": "PARSED",
  "created_at": "2026-05-04T10:00:00Z"
}
```
- 错误码
  - `RESUME_400_FILE_TYPE_UNSUPPORTED`
  - `RESUME_400_FILE_TOO_LARGE`
  - `AUTH_401`

#### 3.2.2 简历列表
- `GET /api/v1/resumes?page=1&page_size=10`
- Response `200`
```json
{
  "items": [
    {
      "resume_id": "res_123",
      "file_name": "张三-后端简历.pdf",
      "parse_status": "PARSED",
      "created_at": "2026-05-04T10:00:00Z",
      "last_used_at": "2026-05-04T12:10:00Z"
    }
  ],
  "page": 1,
  "page_size": 10,
  "total": 1
}
```

#### 3.2.3 删除简历
- `DELETE /api/v1/resumes/{resume_id}`
- Response `204`
- 规则：
  - 若存在进行中的面试会话引用该简历，返回 `409`。
  - 若仅被已完成会话引用，允许软删除简历文件与列表可见性，历史会话保留“简历快照摘要”。
- 错误码
  - `RESUME_404_NOT_FOUND`
  - `RESUME_403_FORBIDDEN`
  - `RESUME_409_IN_USE`

### 3.3 面试记录与回放

#### 3.3.1 面试历史列表（增强）
- `GET /api/v1/interviews/history?page=1&page_size=10&job_role=java`
- Response `200`
```json
{
  "items": [
    {
      "interview_id": "int_001",
      "resume_id": "res_123",
      "job_role": "java",
      "status": "FINISHED",
      "started_at": "2026-05-04T12:00:00Z",
      "finished_at": "2026-05-04T12:40:00Z",
      "turn_count": 12
    }
  ],
  "page": 1,
  "page_size": 10,
  "total": 1
}
```

#### 3.3.2 面试回放详情（新增）
- `GET /api/v1/interviews/{interview_id}/playback`
- Response `200`
```json
{
  "interview_id": "int_001",
  "resume": {
    "resume_id": "res_123",
    "file_name": "张三-后端简历.pdf"
  },
  "meta": {
    "job_role": "java",
    "difficulty": "medium",
    "status": "FINISHED",
    "started_at": "2026-05-04T12:00:00Z",
    "finished_at": "2026-05-04T12:40:00Z"
  },
  "turns": [
    {
      "turn_id": "turn_001",
      "sequence": 1,
      "question": "请先做一个自我介绍。",
      "answer": "我有三年 Java 开发经验...",
      "question_ts": "2026-05-04T12:01:00Z",
      "answer_ts": "2026-05-04T12:02:10Z"
    }
  ]
}
```
- 错误码
  - `INTERVIEW_404_NOT_FOUND`
  - `INTERVIEW_403_FORBIDDEN`

### 3.4 幂等与一致性约束
- 上传简历：非幂等；可通过文件 hash 做重复提示（非阻断）。
- 删除简历：幂等；重复删除返回 `204` 或 `404`（建议 `204`）。
- 回放查询：只读幂等。

## 4. 数据模型草案

### 4.1 resumes（新增/调整）
- `resume_id` TEXT PK
- `user_id` TEXT NOT NULL INDEX
- `file_name` TEXT NOT NULL
- `storage_path` TEXT NOT NULL
- `file_hash` TEXT NULL
- `parse_status` TEXT NOT NULL（`PENDING`/`PARSED`/`FAILED`）
- `is_deleted` INTEGER NOT NULL DEFAULT 0
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL
- `deleted_at` DATETIME NULL

### 4.2 interviews（调整）
- `interview_id` TEXT PK
- `user_id` TEXT NOT NULL INDEX
- `resume_id` TEXT NOT NULL
- `job_role` TEXT NOT NULL
- `difficulty` TEXT NOT NULL
- `status` TEXT NOT NULL（`INIT`/`IN_PROGRESS`/`FINISHED`/`REPORT_READY`/`REPORT_FAILED`）
- `started_at` DATETIME NOT NULL
- `finished_at` DATETIME NULL
- `created_at` DATETIME NOT NULL

### 4.3 interview_turns（增强）
- `turn_id` TEXT PK
- `interview_id` TEXT NOT NULL INDEX
- `user_id` TEXT NOT NULL INDEX（冗余字段，便于按用户过滤）
- `sequence` INTEGER NOT NULL
- `question_text` TEXT NOT NULL
- `answer_text` TEXT NOT NULL
- `question_ts` DATETIME NOT NULL
- `answer_ts` DATETIME NULL
- `created_at` DATETIME NOT NULL

### 4.4 数据生命周期
- 简历：默认长期保留；用户删除后软删除并隐藏。
- 面试记录：默认长期保留，用于历史回放与能力分析。
- 审计日志：至少保留 180 天（鉴权失败、越权访问、删除操作）。

## 5. 前端交互与状态约束

### 5.1 页面与信息架构
- 新增“简历管理”页：列表、上传、删除。
- 历史记录页增强：支持点击进入“回放详情”。
- 回放详情页：按 `sequence` 时间顺序展示问答流。

### 5.2 关键状态流
- 简历管理：`LOADING -> READY -> UPLOADING/DELETING -> READY`。
- 回放页面：`LOADING -> READY | EMPTY | ERROR`。
- 删除确认：必须二次确认，文案提示“删除后不可在新面试中使用”。

### 5.3 错误提示与可用性
- `401`：跳登录并保留返回路径。
- `403`：提示“无权限访问该资源”。
- `409`（简历被引用）：提示“该简历存在进行中的面试，暂不可删除”。
- 移动端适配：回放问答卡片支持折叠，避免长文本遮挡。

## 6. 非功能需求（性能/安全/可观测性/可用性）
- 性能：
  - 简历列表 P95 < 300ms（10 条分页）。
  - 回放详情 P95 < 500ms（50 轮以内）。
- 安全：
  - 严格按 `user_id` 做数据权限过滤。
  - 文件上传限制大小与类型，防止恶意文件。
  - 日志不打印完整简历正文与敏感个人信息。
- 可观测性：
  - 关键日志字段：`trace_id`, `user_id`, `resume_id`, `interview_id`, `action`, `status`。
  - 监控指标：上传成功率、删除失败率、回放查询失败率。
- 可用性：
  - 回放数据读取失败需可重试。
  - 删除操作需有明确结果反馈。

## 7. 验收标准（Given-When-Then）

### AC-01 账号隔离
- Given 用户 A 与用户 B 均已登录。
- When 用户 A 查询简历列表与面试历史。
- Then 返回结果不包含用户 B 的任何数据。

### AC-02 简历上传与列表
- Given 用户已登录。
- When 上传合法 PDF 简历。
- Then 返回 `201` 且列表可见新简历。

### AC-03 简历删除
- Given 用户有一个未被进行中面试引用的简历。
- When 执行删除。
- Then 返回 `204` 且列表不再展示该简历。

### AC-04 删除冲突保护
- Given 该简历被进行中的面试会话使用。
- When 执行删除。
- Then 返回 `409 RESUME_409_IN_USE`。

### AC-05 面试问答留存
- Given 用户完成一场面试并产生多轮问答。
- When 查询回放详情。
- Then 返回完整轮次问答，顺序与时间戳正确。

### AC-06 越权访问拦截
- Given 用户 A 拥有 `interview_id=int_001`，用户 B 无权限。
- When 用户 B 访问 `/interviews/int_001/playback`。
- Then 返回 `403`。

## 8. 风险与待确认项（按优先级）

### P0
- 待确认：删除简历时是否允许“强制删除并保留历史快照”。
  - 影响：删除接口语义、数据一致性与用户认知。

### P1
- 待确认：回放是否需要包含音频 URL（若后续支持语音回放）。
  - 影响：存储成本、鉴权签名策略、前端播放器复杂度。

### P1
- 风险：历史数据可能缺少 `user_id` 字段，迁移脚本复杂。
  - 影响：账号隔离上线时间与数据准确性。

### P2
- 待确认：简历数量上限（每用户最大份数）与单文件大小上限。
  - 影响：存储容量规划与上传失败体验。

## 9. 落盘信息
- 目标路径：`devdocs/agent1-resume-interview-record-prd-20260504.md`
- 该文档可直接作为 Agent 2 的改动计划输入。

## 10. DoD
- 已明确需求边界（In/Out）。
- 已定义可实现的接口契约、错误码、幂等与一致性规则。
- 已提供可测试的 AC（正常/异常/边界）。
- 已给出风险与待确认项并标注影响范围。
