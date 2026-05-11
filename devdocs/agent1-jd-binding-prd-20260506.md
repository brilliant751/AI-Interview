# Agent1 需求与接口设计：JD 绑定面试（2026-05-06）

## 1. 需求摘要
- 目标：引入 `JD（岗位描述）` 能力，支持候选人在系统中上传 JD，或选择系统预置 JD，并在创建面试时可选绑定。
- 核心业务要求：
  - 创建面试时，用户可以“仅选方向（job_role）不绑定 JD”。
  - 若绑定 JD，面试追问需要基于 JD 关键要求进行贴合提问。
  - JD 需区分来源：`用户上传` 与 `系统预置`。
- 期望结果：提升问题与真实岗位匹配度，同时保持无 JD 场景可用。

## 2. 范围定义（In / Out）

### In Scope
- JD 数据管理最小闭环：上传、列表、查看、软删除（用户上传 JD）；系统预置 JD 只读可选。
- 创建面试接口新增 JD 绑定字段（可空）。
- 面试问题生成链路增加 JD 上下文融合逻辑。
- 历史/回放/状态接口补充 JD 绑定信息（用于 UI 展示与追溯）。
- 前端“面试准备”页新增 JD 选择区（可不选）。

### Out of Scope
- JD 自动解析（结构化抽取技能标签）复杂 NLP 流程。
- JD 多版本对比、模板编辑器、团队共享权限。
- 基于 JD 的评分维度重训（本期仅影响“提问贴合度”，不改评分模型）。

## 3. 接口定义（OpenAPI 风格草案）

### 3.1 上传用户 JD
- `POST /jds`
- Auth：`require_user`
- Request（multipart/form-data）
  - `file`: 必填，支持 `pdf/doc/docx/txt/md`（大小上限建议 5MB）
  - `job_role`: 可选，`java | web`
  - `title`: 可选，默认取文件名
- Response 200
```json
{
  "jd_id": "jd_xxx",
  "source_type": "USER_UPLOAD",
  "title": "后端开发工程师JD",
  "job_role": "java",
  "status": "READY",
  "created_at": "2026-05-06T10:00:00Z"
}
```

### 3.2 查询 JD 列表（系统+用户可见）
- `GET /jds?page=1&page_size=20&job_role=java&source_type=USER_UPLOAD|SYSTEM_PRESET`
- 规则：
  - 返回“系统预置 + 当前用户上传且未删除”的并集。
  - 系统预置记录 `is_builtin=true`，不可删除。

### 3.3 删除用户 JD
- `DELETE /jds/{jd_id}`
- 仅允许删除 `source_type=USER_UPLOAD` 且归属当前用户的数据。
- 已绑定到历史面试的 JD 执行软删除（面试记录仍保留快照字段）。

### 3.4 创建面试（扩展）
- `POST /interviews`
- 在既有字段上新增：
  - `jd_id?: string`（可空）
  - `jd_bind_mode?: "NONE" | "BIND"`（可省略；后端可由 `jd_id` 是否为空推导）
- 校验：
  - `jd_id` 为空：合法，按仅方向提问。
  - `jd_id` 非空：必须存在且当前用户可访问（本人上传或系统预置），且 `job_role` 兼容。

### 3.5 面试状态/回放/历史（扩展返回）
- `GET /interviews/{id}/status`、`GET /interviews/{id}/playback`、`GET /interviews/history`
- 新增只读字段：
  - `jd_id`
  - `jd_title`
  - `jd_source_type`

### 3.6 错误码补充
- `JD_404_NOT_FOUND`：JD 不存在
- `JD_403_FORBIDDEN`：无权访问该 JD
- `JD_409_ROLE_MISMATCH`：JD 岗位方向与面试方向不匹配
- `JD_400_INVALID_FILE`：文件类型/大小不合法

## 4. 数据模型草案

### 4.1 新表：`job_descriptions`
- `jd_id TEXT PK`
- `user_id TEXT NULL`（系统预置为空，用户上传为 owner）
- `source_type TEXT NOT NULL`（`SYSTEM_PRESET | USER_UPLOAD`）
- `title TEXT NOT NULL`
- `job_role TEXT NOT NULL`（`java|web`）
- `content_text TEXT NOT NULL DEFAULT ''`
- `storage_path TEXT NULL`
- `status TEXT NOT NULL DEFAULT 'READY'`
- `is_deleted INTEGER NOT NULL DEFAULT 0`
- `deleted_at TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### 4.2 变更表：`interview_sessions`
- 新增字段：
  - `jd_id TEXT NULL`
  - `jd_snapshot_title TEXT NOT NULL DEFAULT ''`
  - `jd_snapshot_content TEXT NOT NULL DEFAULT ''`
- 设计说明：
  - 采用快照字段，避免 JD 后续删除/修改导致历史回放语义漂移。

## 5. 前端交互与状态约束
- 页面：`InterviewPreparePage`
- 交互新增：
  - “岗位描述（可选）”选择器：支持“无 JD（默认）/系统预置/我的上传”。
  - 上传入口：可在弹窗内直接上传并刷新列表。
  - 兼容性约束：当 `job_role` 切换时，若当前选中 JD 不匹配则清空并提示。
- 状态流转：
  - 未选 JD -> 可直接创建会话。
  - 已选 JD -> 创建会话携带 `jd_id`。
- 错误提示：
  - JD 删除或无权限：提示“所选 JD 不可用，请重新选择”。

## 6. 非功能需求
- 性能：创建面试接口新增 JD 校验，P95 增幅不超过 80ms。
- 安全：
  - JD 与简历一样按用户隔离，系统预置只读。
  - 上传文件仅允许白名单类型并做大小限制。
- 可观测性：
  - 在面试链路日志增加 `jd_id`、`jd_source_type`、`jd_bind_mode`。
  - 中文日志要求：除专有名词外，日志内容使用中文。
- 可用性：无 JD 场景必须与现有行为兼容。

## 7. 验收标准（Given-When-Then）
1. Given 用户未选择 JD，When 创建面试，Then 会话创建成功且按 `job_role` 正常出题。
2. Given 用户选择系统预置 JD，When 创建面试，Then 会话创建成功并在追问中体现 JD 关键词方向。
3. Given 用户上传个人 JD 并绑定，When 进入 TECHNICAL 阶段，Then 至少一条追问需关联 JD 关键职责/技能。
4. Given 绑定了不匹配方向的 JD，When 创建面试，Then 返回 `JD_409_ROLE_MISMATCH`。
5. Given 用户尝试绑定他人上传 JD，When 创建面试，Then 返回 `JD_403_FORBIDDEN`。
6. Given 已绑定 JD 的面试记录，When 原 JD 被软删除，Then 历史回放仍可看到 JD 标题快照。
7. Given 用户仅选方向不绑定 JD，When 完成整场面试，Then 报告链路与当前版本一致不回归。

## 8. 风险与待确认项（按优先级）
- P0【待确认】当前系统是否仍强制 `resume_id` 必填。
  - 影响：若后续要支持“仅 JD 无简历面试”，需同步调整 `InterviewCreateRequest`、鉴权与首题策略。
- P1【风险】JD 文本过长可能导致提问提示词噪声。
  - 建议：Agent2/3 实施时加入 JD 截断与关键句抽取（例如 2-5 条）。
- P1【风险】系统预置 JD 的维护来源未明确。
  - 建议：先以仓库静态文件目录落地，后续再接后台管理。
- P2【待确认】是否允许一个会话同时绑定“简历 + JD”。
  - 当前假设：允许，并在提问时将简历要点与 JD 要点共同作为 references。

## 9. 可交接物与 DoD
- 可交接物：
  - 本文档（Agent1 需求与接口草案）
  - 可直接给 Agent2 拆分为前后端+数据迁移计划
- DoD：
  - 需求边界、接口、数据结构、AC、风险均已明确。
  - 已标注关键待确认项，不阻塞 Agent2 制定实施计划。

## 10. 落盘信息
- 目标路径：`devdocs/agent1-jd-binding-prd-20260506.md`

