# PRD：AI 模拟面试与能力提升平台（Agent 1 输出）

## 1. 需求摘要

本项目面向计算机相关专业学生，提供可反复练习的岗位化模拟面试能力提升平台。系统通过“简历输入 + 多轮面试 + 多维评估 + 个性化建议”的闭环，帮助用户降低面试焦虑、提升答题质量与表达能力。

核心价值：
- 为学生提供 7x24 可用的 AI 面试教练，支持文本与语音双模交互。
- 针对不同岗位提供差异化题库、知识库和评估维度。
- 输出结构化评估报告，并基于历史结果持续优化后续面试内容。

## 2. 范围定义（In Scope / Out of Scope）

### 2.1 In Scope

- 岗位化面试：至少支持 2 类岗位（示例：Java 后端、Web 前端）。
- 面试流程编排：简历上传 -> 自我介绍 -> 项目深挖 -> 技术基础 -> 行为面试 -> 结束与报告。
- 多轮追问策略：基于用户回答内容进行追问，支持追问次数上限控制。
- 多模态交互：
  - 输入：文本输入、语音输入（语音转文字）。
  - 输出：文本输出、语音播报（文字转语音）。
- 题库系统：每岗位不少于 150 道题，覆盖技术题、项目题、场景题、行为题。
- 知识库系统：每岗位不少于 200 条知识记录，支持检索增强问答（RAG）。
- 面试报告：异步生成结构化报告（评分、亮点、不足、建议）。
- 历史记录与成长：保存面试记录与报告，支持后续面试参考历史表现。

### 2.2 Out of Scope

- 企业招聘系统对接（ATS、OA、企业账号体系）。
- 真人面试官实时介入。
- 非计算机岗位（如财务、销售）题库建设。
- 跨平台客户端原生开发（iOS/Android 独立 App）作为首期硬性目标。

## 3. 接口定义（OpenAPI 风格草案）

说明：以下为 V1 逻辑接口草案，协议可采用 REST + JSON。鉴权建议为 `Bearer Token`。

### 3.1 认证与用户

#### 3.1.1 获取当前用户信息
- `GET /api/v1/users/me`
- 鉴权：需要
- 响应：`200 OK`
```json
{
  "id": "u_123",
  "name": "张三",
  "role": "student"
}
```

### 3.2 简历与面试初始化

#### 3.2.1 上传简历
- `POST /api/v1/resumes`
- 鉴权：需要
- 请求：`multipart/form-data`（`file`）
- 响应：`201 Created`
```json
{
  "resumeId": "r_001",
  "parseStatus": "SUCCESS",
  "structuredProfile": {
    "skills": ["Java", "Spring Boot"],
    "projects": ["智能问答系统"]
  }
}
```

#### 3.2.2 创建面试会话
- `POST /api/v1/interviews`
- 鉴权：需要
- 请求体：
```json
{
  "jobRole": "java_backend",
  "difficulty": 3,
  "resumeId": "r_001",
  "inputMode": "voice",
  "outputMode": "voice"
}
```
- 响应：`201 Created`
```json
{
  "interviewId": "iv_1001",
  "status": "INIT",
  "nextStep": "SELF_INTRO"
}
```

### 3.3 面试过程

#### 3.3.1 提交用户回答并获取下一轮问题
- `POST /api/v1/interviews/{interviewId}/turns`
- 鉴权：需要
- 请求体：
```json
{
  "stage": "PROJECT_DEEP_DIVE",
  "inputType": "voice",
  "asrText": "我在项目里负责接口设计和缓存优化",
  "rawText": "",
  "clientTs": "2026-04-01T20:00:00+08:00"
}
```
- 响应：`200 OK`
```json
{
  "turnId": "t_9001",
  "analysis": {
    "correctness": 0.78,
    "logic": 0.72,
    "expression": 0.66
  },
  "followUpDecision": {
    "shouldFollowUp": true,
    "reason": "答案提及缓存但未说明一致性策略",
    "remainingFollowUpQuota": 2
  },
  "nextQuestion": {
    "stage": "PROJECT_DEEP_DIVE",
    "questionText": "请说明你如何处理缓存与数据库一致性问题？"
  }
}
```

#### 3.3.2 拉取面试状态
- `GET /api/v1/interviews/{interviewId}`
- 鉴权：需要
- 响应：`200 OK`
```json
{
  "interviewId": "iv_1001",
  "status": "IN_PROGRESS",
  "currentStage": "TECHNICAL",
  "askedCount": 7,
  "maxQuestions": 12
}
```

#### 3.3.3 结束面试
- `POST /api/v1/interviews/{interviewId}/finish`
- 鉴权：需要
- 响应：`202 Accepted`
```json
{
  "interviewId": "iv_1001",
  "status": "FINISHED",
  "reportStatus": "GENERATING"
}
```

### 3.4 报告与成长

#### 3.4.1 获取面试报告
- `GET /api/v1/interviews/{interviewId}/report`
- 鉴权：需要
- 响应：`200 OK`
```json
{
  "reportId": "rp_5001",
  "overallScore": 76,
  "dimensions": {
    "technical": 80,
    "logic": 74,
    "communication": 69
  },
  "highlights": ["项目经验真实，技术栈覆盖较好"],
  "weaknesses": ["高并发场景回答深度不足"],
  "suggestions": ["补充缓存一致性方案对比", "练习 STAR 行为题表达"]
}
```

#### 3.4.2 获取用户历史面试列表
- `GET /api/v1/interviews/history?jobRole=java_backend&page=1&pageSize=10`
- 鉴权：需要
- 响应：`200 OK`
```json
{
  "total": 8,
  "items": [
    {
      "interviewId": "iv_1001",
      "jobRole": "java_backend",
      "finishedAt": "2026-04-01T20:45:00+08:00",
      "overallScore": 76
    }
  ]
}
```

### 3.5 题库与知识库管理（运营后台）

#### 3.5.1 新增题目
- `POST /api/v1/admin/questions`
- 鉴权：需要（管理员）

#### 3.5.2 导入知识记录
- `POST /api/v1/admin/knowledge/import`
- 鉴权：需要（管理员）

### 3.6 统一错误码

- `AUTH_401`：未登录或令牌失效
- `PERM_403`：权限不足
- `PARAM_400`：请求参数非法
- `NOT_FOUND_404`：资源不存在
- `STATE_409`：状态冲突（如已结束面试仍提交回答）
- `ASR_502`：语音识别服务异常
- `LLM_503`：大模型服务暂时不可用
- `REPORT_504`：报告生成超时

## 4. 数据模型草案

### 4.1 User（用户）
- `id`：string，必填，唯一标识
- `name`：string，必填
- `email`：string，选填
- `role`：enum[`student`,`admin`]，必填，默认 `student`
- `createdAt`：datetime，必填

### 4.2 Resume（简历）
- `resumeId`：string，必填
- `userId`：string，必填
- `fileUrl`：string，必填
- `structuredProfile`：json，选填（技能、项目、经历）
- `parseStatus`：enum[`PENDING`,`SUCCESS`,`FAILED`]，必填，默认 `PENDING`

### 4.3 InterviewSession（面试会话）
- `interviewId`：string，必填
- `userId`：string，必填
- `jobRole`：enum[`java_backend`,`web_frontend`, ...]，必填
- `difficulty`：int，必填，范围 1-5，默认 3
- `status`：enum[`INIT`,`IN_PROGRESS`,`FINISHED`,`REPORT_READY`]，必填
- `currentStage`：enum[`SELF_INTRO`,`PROJECT_DEEP_DIVE`,`TECHNICAL`,`BEHAVIORAL`,`END`]，必填
- `followUpMax`：int，必填，默认 3
- `startedAt`：datetime，必填
- `finishedAt`：datetime，选填

### 4.4 InterviewTurn（面试轮次）
- `turnId`：string，必填
- `interviewId`：string，必填
- `stage`：enum，必填
- `questionText`：string，必填
- `answerText`：string，必填
- `inputType`：enum[`text`,`voice`]，必填
- `scores`：json，选填（technical/logic/expression）
- `followUpCount`：int，必填，默认 0
- `createdAt`：datetime，必填

### 4.5 QuestionBank（题库）
- `questionId`：string，必填
- `jobRole`：enum，必填
- `type`：enum[`technical`,`project`,`scenario`,`behavioral`]，必填
- `difficulty`：int，必填，范围 1-5
- `content`：string，必填
- `tags`：string[]，选填
- `active`：bool，必填，默认 `true`

### 4.6 KnowledgeRecord（知识库记录）
- `recordId`：string，必填
- `jobRole`：enum，必填
- `sourceType`：enum[`doc`,`faq`,`example`]，必填
- `content`：string，必填
- `embedding`：vector，必填
- `metadata`：json，选填（来源、更新时间、标签）

### 4.7 InterviewReport（报告）
- `reportId`：string，必填
- `interviewId`：string，必填
- `overallScore`：int，必填，范围 0-100
- `dimensionScores`：json，必填
- `highlights`：string[]，必填
- `weaknesses`：string[]，必填
- `suggestions`：string[]，必填
- `status`：enum[`GENERATING`,`READY`,`FAILED`]，必填
- `createdAt`：datetime，必填

## 5. 验收标准（Given-When-Then）

### AC-01 岗位化面试创建成功
- Given 用户已登录且已上传简历
- When 用户选择目标岗位与难度并创建面试
- Then 系统返回 `interviewId`，状态为 `INIT`，并进入自我介绍阶段

### AC-02 多轮追问规则生效
- Given 面试处于项目深挖或行为面试阶段
- When 用户回答信息不完整且未达到追问上限
- Then 系统生成追问问题并返回剩余追问次数

### AC-03 技术题纠错与讲解
- Given 当前题型为技术基础题
- When 用户回答错误
- Then 系统在当前轮次给出错误提示与简要讲解，并可按规则停止该题追问

### AC-04 语音输入链路可用
- Given 用户选择语音输入
- When 用户提交语音
- Then 系统完成语音转文字并继续后续问答流程，失败时返回可读错误码与重试提示

### AC-05 报告异步生成
- Given 用户结束面试
- When 系统接收到结束指令
- Then 面试状态变为 `FINISHED`，报告状态变为 `GENERATING`，最终可查询到结构化报告

### AC-06 历史记录参与后续面试
- Given 用户存在历史面试记录
- When 用户发起下一次同岗位面试
- Then 系统可基于历史报告短板调整提问重点（例如增加薄弱知识点相关问题）

### AC-07 数据规模达标
- Given 系统初始数据准备完成
- When 管理员检查题库与知识库规模
- Then 每岗位题库数量不少于 150，每岗位知识记录不少于 200

## 6. 风险与待确认项（按优先级）

### P0（必须先确认）
- 评分维度权重与口径未冻结  
影响范围：报告可信度、前后轮次可比性、成长曲线有效性。
- 面试阶段切换规则缺少精确阈值（何时进入下一阶段）  
影响范围：用户体验稳定性、追问一致性、测试可重复性。
- 语音服务异常时的降级策略未明确（自动切文本/提示重试/终止）  
影响范围：面试流程可用性与完成率。

### P1（开发前确认）
- 岗位清单与首期范围未最终确定（“至少两类”需明确具体岗位）  
影响范围：题库建设、知识库标签、评估模型校准。
- 报告生成时延目标未定义（例如 10 秒内/1 分钟内）  
影响范围：异步架构与用户等待体验。
- 历史数据驱动“个性化提问”策略尚无量化规则  
影响范围：可解释性与效果评估。

### P2（迭代中确认）
- 管理后台能力边界未明确（仅导入还是可审核、版本化、回滚）  
影响范围：运营效率与数据质量治理。
- 安全与隐私策略未明确（简历与语音数据保留周期）  
影响范围：合规与用户信任。

## 7. 可交接物与 DoD

### 可交接物
- 本 PRD 文档（包含需求、范围、接口、数据模型、AC、风险）。

### 完成定义（DoD）
- 关键业务流程已覆盖且无关键歧义。
- 接口定义可直接被 Agent 2 作为改动规划输入。
- AC 可直接映射为测试用例设计输入。
- 风险与待确认项可追踪，且包含影响范围。

## 8. 落盘信息

- 目标路径：`devdocs/PRD-AI模拟面试与能力提升平台-v1.md`
- 产出角色：Agent 1（需求与接口设计）
