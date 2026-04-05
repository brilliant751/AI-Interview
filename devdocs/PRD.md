# PRD：AI 模拟面试与能力提升平台（Agent 1）

## 1. 需求摘要

### 1.1 背景与目标
随着计算机相关专业学生就业竞争加剧，学生在技术面试准备中普遍存在真实练习不足、反馈滞后、岗位针对性弱、综合能力难量化等问题。本项目建设一个可反复练习的 AI 模拟面试平台，形成“练习-评估-提升”闭环。

### 1.2 业务目标
- 为学生提供随时可用的岗位化 AI 面试教练，降低面试焦虑。
- 通过多轮模拟与即时反馈，提升技术表达、逻辑与应变能力。
- 基于历史记录生成个性化提升建议，持续提升面试表现。

### 1.3 首期建设目标（MVP）
- 支持至少 2 类技术岗位（Java 后端、Web 前端）。
- 完成“简历上传 -> 面试开始 -> 多阶段提问 -> 结束 -> 异步报告”的全流程。
- 支持语音/文本双输入与文本/语音双输出。
- 建成岗位题库与知识库，支撑动态提问与解释反馈。

## 2. 范围定义（In Scope / Out of Scope）

### 2.1 In Scope
- 岗位化题库：每岗位 >=150 题，覆盖技术题、项目深挖题、场景题、行为题。
- 岗位化知识库：每岗位 >=200 条知识记录，支持 RAG 检索增强。
- 面试主流程：
  - 用户上传简历。
  - 用户进入面试并完成自我介绍。
  - 项目经历提问与追问。
  - 技术基础提问（3-5 题，按难度动态抽题）。
  - 行为面试提问（开放题最多追问 3 次）。
  - 结束面试并异步生成报告。
- 面试单位循环：语音转文字（ASR）-> LLM 生成 -> 文字转语音（TTS）。
- 评估与反馈：
  - 内容维度：技术正确性、知识深度、逻辑严谨性、岗位匹配度。
  - 表达维度：语速、清晰度、自信度。
  - 结构化报告：得分、亮点、不足、改进建议。
- 历史沉淀：保存面试记录和报告，下一次面试参考历史短板调整策略。
- 数据前置构建（离线）：基于 `assets/material/` 的题库与知识材料，离线完成标准化、校验、入库与向量化，再进入联调开发。

### 2.2 Out of Scope
- 非计算机类岗位面试体系建设。
- 企业 ATS/招聘系统对接。
- 真人面试官在线介入。
- 移动端原生 App（iOS/Android）首期独立交付。

## 3. 接口定义（OpenAPI 风格草案）

说明：协议为 HTTP+JSON；鉴权采用 Bearer Token；所有写接口要求 `X-Idempotency-Key`，用于防重复提交。

### 3.1 简历与会话初始化

#### 3.1.1 上传简历
- `POST /api/v1/resumes`
- 请求：`multipart/form-data`（`file`）
- 响应：`201 Created`
```json
{
  "resumeId": "r_1001",
  "parseStatus": "SUCCESS",
  "structuredProfile": {
    "skills": ["Java", "Spring Boot"],
    "projects": ["智能问答系统"]
  }
}
```

#### 3.1.2 创建面试
- `POST /api/v1/interviews`
- 请求体：
```json
{
  "jobRole": "java_backend",
  "difficulty": 3,
  "resumeId": "r_1001",
  "inputMode": "voice",
  "outputMode": "voice"
}
```
- 响应：`201 Created`
```json
{
  "interviewId": "iv_2001",
  "status": "INIT",
  "currentStage": "SELF_INTRO",
  "followUpMax": 3
}
```

### 3.2 面试过程

#### 3.2.1 提交回答并获取下一问
- `POST /api/v1/interviews/{interviewId}/turns`
- 请求体：
```json
{
  "stage": "PROJECT_DEEP_DIVE",
  "inputType": "voice",
  "asrText": "我在项目中负责接口设计和缓存优化",
  "rawText": "",
  "clientTs": "2026-04-01T21:00:00+08:00"
}
```
- 响应：`200 OK`
```json
{
  "turnId": "t_3001",
  "nextQuestion": {
    "stage": "PROJECT_DEEP_DIVE",
    "questionText": "请说明你如何处理缓存与数据库一致性？"
  },
  "followUpDecision": {
    "shouldFollowUp": true,
    "remainingFollowUpQuota": 2,
    "reason": "一致性策略描述不足"
  },
  "liveScore": {
    "technical": 0.76,
    "logic": 0.72,
    "expression": 0.65
  }
}
```

#### 3.2.2 获取面试状态
- `GET /api/v1/interviews/{interviewId}`
- 响应：`200 OK`
```json
{
  "interviewId": "iv_2001",
  "status": "IN_PROGRESS",
  "currentStage": "TECHNICAL",
  "askedCount": 6,
  "recommendedTotal": 10
}
```

#### 3.2.3 结束面试
- `POST /api/v1/interviews/{interviewId}/finish`
- 响应：`202 Accepted`
```json
{
  "interviewId": "iv_2001",
  "status": "FINISHED",
  "reportStatus": "GENERATING"
}
```

### 3.3 报告与历史

#### 3.3.1 获取报告
- `GET /api/v1/interviews/{interviewId}/report`
- 响应：`200 OK`
```json
{
  "reportId": "rp_8001",
  "overallScore": 78,
  "dimensions": {
    "technical": 81,
    "logic": 75,
    "communication": 73,
    "jobFit": 82
  },
  "highlights": ["项目经历真实且可量化"],
  "weaknesses": ["高并发问题分析深度不足"],
  "suggestions": ["补充缓存一致性方案对比", "按 STAR 结构回答行为题"]
}
```

#### 3.3.2 查询历史面试
- `GET /api/v1/interviews/history?jobRole=java_backend&page=1&pageSize=10`
- 响应：`200 OK`
```json
{
  "total": 5,
  "items": [
    {
      "interviewId": "iv_2001",
      "finishedAt": "2026-04-01T21:30:00+08:00",
      "overallScore": 78
    }
  ]
}
```

### 3.4 题库与知识库（后台）
- `POST /api/v1/admin/questions`：新增/导入题库题目。
- `POST /api/v1/admin/knowledge/import`：导入知识记录并触发向量化。

### 3.5 统一错误码
- `AUTH_401`：鉴权失败。
- `PERM_403`：权限不足。
- `PARAM_400`：参数错误。
- `NOT_FOUND_404`：资源不存在。
- `STATE_409`：状态冲突（面试已结束仍提交轮次）。
- `ASR_502`：语音识别服务异常。
- `LLM_503`：问答服务异常。
- `TTS_502`：语音播报服务异常。
- `REPORT_504`：报告生成超时。

## 4. 数据模型草案

### 4.1 User
- `id`：string，必填。
- `name`：string，必填。
- `role`：enum[`student`,`admin`]，默认 `student`。
- `createdAt`：datetime，必填。

### 4.2 Resume
- `resumeId`：string，必填。
- `userId`：string，必填。
- `fileUrl`：string，必填。
- `structuredProfile`：json，选填。
- `parseStatus`：enum[`PENDING`,`SUCCESS`,`FAILED`]，默认 `PENDING`。
- `createdAt`：datetime，必填。

### 4.3 InterviewSession
- `interviewId`：string，必填。
- `userId`：string，必填。
- `jobRole`：enum[`java_backend`,`web_frontend`]，必填。
- `difficulty`：int，范围 1-5，默认 3。
- `status`：enum[`INIT`,`IN_PROGRESS`,`FINISHED`,`REPORT_READY`,`REPORT_FAILED`]。
- `currentStage`：enum[`SELF_INTRO`,`PROJECT_DEEP_DIVE`,`TECHNICAL`,`BEHAVIORAL`,`END`]。
- `followUpMax`：int，默认 3。
- `startedAt`：datetime，必填。
- `finishedAt`：datetime，选填。

### 4.4 InterviewTurn
- `turnId`：string，必填。
- `interviewId`：string，必填。
- `stage`：enum，必填。
- `questionText`：string，必填。
- `answerText`：string，必填。
- `inputType`：enum[`text`,`voice`]，必填。
- `scores`：json，选填。
- `followUpCount`：int，默认 0。
- `createdAt`：datetime，必填。

### 4.5 QuestionBank（SQLite）
- `questionId`：string，必填。
- `jobRole`：enum，必填。
- `type`：enum[`technical`,`project`,`scenario`,`behavioral`]，必填。
- `difficulty`：int，范围 1-5。
- `content`：text，必填。
- `tags`：json/array，选填。
- `isActive`：bool，默认 `true`。

### 4.6 KnowledgeRecord（Chroma）
- `recordId`：string，必填。
- `jobRole`：enum，必填。
- `content`：text，必填。
- `metadata`：json，包含来源、标签、更新时间。
- `embedding`：vector，必填。

### 4.7 InterviewReport
- `reportId`：string，必填。
- `interviewId`：string，必填。
- `overallScore`：int，范围 0-100。
- `dimensionScores`：json，必填。
- `highlights`：string[]，必填。
- `weaknesses`：string[]，必填。
- `suggestions`：string[]，必填。
- `status`：enum[`GENERATING`,`READY`,`FAILED`]。
- `createdAt`：datetime，必填。

### 4.8 数据生命周期
- 面试中间缓存：当前会话保存“简历摘要 + 自我介绍 + 历次回答”。
- 面试结束后：写入历史记录，触发异步报告任务。
- 下一次面试：读取历史短板标签，调整提问策略与难度。

## 5. 前端交互与状态约束

### 5.1 页面与状态机
- 页面流转：简历上传页 -> 面试准备页 -> 面试对话页 -> 报告页 -> 历史页。
- 面试状态：`INIT` -> `IN_PROGRESS` -> `FINISHED` -> `REPORT_READY/REPORT_FAILED`。
- 阶段状态：`SELF_INTRO` -> `PROJECT_DEEP_DIVE` -> `TECHNICAL` -> `BEHAVIORAL` -> `END`。

### 5.2 交互约束
- 用户未完成自我介绍，不进入项目深挖阶段。
- 技术基础阶段题量控制在 3-5 题。
- 场景/行为开放题追问次数上限 3 次。
- 任一阶段超时或服务异常，允许用户重试或切换文本模式继续。

### 5.3 反馈与可用性
- 错误提示需用户可理解，不暴露内部堆栈。
- 语音识别失败时提供“转文本输入”快捷入口。
- 报告生成中需可视化进度态（轮询或事件推送均可）。

### 5.4 可访问性与兼容性
- 文本输入与关键按钮支持键盘操作。
- 核心流程兼容主流 Chromium 内核浏览器最新两个大版本。

## 6. 非功能需求（性能/安全/可观测性/可用性）

### 6.1 性能
- 单轮提问响应目标：P95 <= 3 秒（不含用户说话时长）。
- 结束后报告生成目标：P95 <= 60 秒。

### 6.2 安全与隐私
- 用户数据按用户隔离访问，严格鉴权。
- 简历与面试文本需可配置保留周期与清理策略。
- 日志中禁止记录明文敏感信息。

### 6.3 可观测性
- 关键链路埋点：上传、创建会话、每轮问答、结束、报告生成。
- 指标：请求成功率、ASR/LLM/TTS 错误率、报告生成时长、会话完成率。

### 6.4 可用性
- 外部模型服务异常时，系统需提供降级与重试路径。
- 异步任务失败需可重试，且可追踪失败原因。

## 7. 技术栈选型与版本基线（冻结）

本节为项目级技术决策，后续实现需默认遵循；如需替换，需在 Agent 2 计划中记录偏差原因与影响。

### 7.1 选型结论（最终）
- 前端框架：`React 18 + TypeScript + Vite`。
- 组件库：`Ant Design 5`。
- 前端状态管理：`Zustand 5`（客户端状态）+ `TanStack Query 5`（服务端状态缓存与请求状态）。
- 前端路由：`react-router-dom 6`。
- 后端框架：`FastAPI`（Python 3.11+，Pydantic v2）。
- 关系数据库：`SQLite`（MVP 阶段主存储）。
- 向量数据库：`Chroma`（持久化模式）。
- Agent 框架：`LangChain + LangGraph`（LangGraph 负责多节点编排与状态机，LangChain 负责模型/工具/RAG 集成）。
- 检索与编排：`LangChain`（Retriever、Prompt、Chain/Runnable）。
- 语音链路：`FunASR`（ASR）+ `PaddleSpeech`（TTS）。

### 7.2 对用户候选方案的调整
- 保留：`React + Zustand + AntDesign + SQLite + Chroma + Langchain + FastApi` 主干方向。
- 调整 1：新增 `LangGraph` 作为 Agent 编排层，避免仅靠单链路调用难以维护复杂多阶段面试流程。
- 调整 2：新增 `TanStack Query` 管理服务端状态；`Zustand` 只承担会话、UI 与流程状态，避免状态职责混杂。
- 调整 3：后端异步建议采用“FastAPI 接口层 + 后台任务 worker（报告生成）”分层，避免报告生成阻塞主请求线程。

### 7.3 分层职责（最佳实践约束）
- React/Ant Design：页面渲染、交互组件、表单与反馈提示。
- Zustand：本地会话态（当前面试阶段、追问计数、UI 控制态）。
- TanStack Query：接口请求、缓存、重试、失效与刷新。
- FastAPI：鉴权、会话编排 API、错误码与幂等控制。
- SQLite：用户、简历、会话、轮次、报告等结构化数据。
- Chroma：岗位知识向量索引与 TopK 召回。
- LangChain/LangGraph：问题生成、工具调用、检索增强、流程状态迁移。

### 7.4 数据与存储策略
- SQLite 开启 WAL 模式，降低读写阻塞风险。
- SQLite 仅用于 MVP 与中小规模并发；当并发与数据量超阈值时，迁移至 PostgreSQL（作为 P1 预案）。
- Chroma 按岗位维度拆分 collection，metadata 必须包含岗位、题型、难度与更新时间。
- 会话写库采用“轮次级落盘 + 报告异步写回”，避免长事务。

### 7.5 版本基线（建议）
- Node.js：`20 LTS`。
- React：`18.x`。
- Ant Design：`5.x`。
- Zustand：`5.x`。
- TanStack Query：`5.x`。
- Python：`3.11+`。
- FastAPI：`0.115+`（Pydantic v2 生态）。
- LangChain：`1.x`（如落地需兼容 LangGraph 当前稳定版本）。
- Chroma：使用当前稳定版并锁定次版本，避免向量索引行为漂移。

### 7.6 Context7 核对记录（本次）
- `libraryId=/fastapi/fastapi`，关键词：`lifespan`, `APIRouter dependencies`, `Pydantic v2`。
- `libraryId=/websites/langchain`，关键词：`LangGraph agent workflows`, `tool calling`, `stateful graph`。
- `libraryId=/pmndrs/zustand`，关键词：`slices pattern`, `persist middleware`, `selector optimization`。
- `libraryId=/chroma-core/chroma`，关键词：`collection upsert`, `ids`, `metadata`, `Persistent client`。
- `libraryId=/websites/sqlite_docs`，关键词：`WAL`, `transaction`, `bulk import`, `indexing`。
- `libraryId=/websites/langchain`，关键词：`document loader`, `text splitter`, `metadata preserving`, `vector ingestion`。

关键结论：
- FastAPI 推荐使用 `lifespan` 管理应用生命周期，并通过 `APIRouter` + 依赖注入做模块化。
- LangChain 官方生态中，复杂 Agent 更推荐以 LangGraph 做有状态编排。
- Zustand 推荐 slices 模式与 selector 精细订阅，persist 在合并后的总 store 层应用。
- Chroma 推荐使用稳定 `id + metadata` 与 `upsert` 策略支持可重复导入。
- SQLite 推荐导入阶段使用事务与 WAL 模式，降低锁冲突并提升批量写入稳定性。
- LangChain 文档加载/切分流程强调保留 `source` 等 metadata，便于后续追溯与过滤检索。

### 7.7 材料可导入性抽检结论（基于 assets/material）

抽检样本：
- `assets/material/java/java-interview/high-concurrency.md`（结构正常，含“题干/类别/解析”）
- `assets/material/web/interview.md`（结构正常，含“第N题 + 题干/类别/解析”）
- `assets/material/web/knowledge.md`（结构可解析，但为“主题 + 编号问答”格式）
- `assets/material/java/java-interview/java-interview-additional.md`（已修复，结构可解析）

结构一致性结论：
- Java 题库（`assets/material/java/java-interview/`）全部文件满足关键标题可提取要求（`题干/类别/解析`），可进入自动导入流程。
- Web 题库（`assets/material/web/interview.md`）满足关键标题可提取要求（`第N题 + 题干/类别/解析`）。
- Java 知识库（`assets/material/java/java-knowledge/`）为层级标题结构（H1/H2/H3），可按标题分段导入。
- Web 知识库（`assets/material/web/knowledge.md`）为“`## 主题 + 编号问答`”结构，可导入，但解析规则需与 Java 知识库分开实现。

### 7.8 数据前置流程与脚本化要求（强制）

本项目将“题库数据库构建 + 向量知识库构建”设为开发前置门禁（G0），必须离线完成。

G0 必须产出：
- 标准化中间产物：`JSONL/JSON`（题库、知识库分开）。
- SQLite 数据库文件（题库主存储）。
- Chroma 持久化目录（知识向量索引）。
- 数据质量报告（通过数/失败数/失败原因/样本路径）。

脚本交付要求（可复用）：
- 必须提供可重复执行脚本，建议路径：
  - `assets/scripts/data/normalize_materials.py`
  - `assets/scripts/data/build_question_bank.py`
  - `assets/scripts/data/build_knowledge_vectorstore.py`
  - `assets/scripts/data/validate_materials.py`
- 脚本必须支持：
  - 幂等导入（同一条数据重复执行不产生重复记录，使用稳定主键与 `upsert`）。
  - `--dry-run` 模式（仅校验不写入）。
  - 增量导入（按文件变更或 hash）。
  - 失败不中断全量任务（记录错误并输出报告）。

数据建模与入库要求：
- 题库主键建议：`role + source_file + question_no` 的稳定组合键。
- 题库字段至少包含：`role/type/question/stem/analysis/source_path/source_heading`。
- 知识分块必须保留 metadata：`role/topic/source_path/chunk_id/updated_at`。
- 向量写入 Chroma 使用 `upsert`，并按岗位拆分 collection（如 `kb_java`, `kb_web`）。
- SQLite 导入阶段必须使用事务，初始化时启用 `WAL` 和必要索引。

异常数据处理要求：
- 校验脚本需输出“可导入/需修复/已忽略”三类结果，并给出文件级原因。

## 8. 验收标准（Given-When-Then）

### AC-00 数据前置门禁通过
- Given `assets/material/` 已提供岗位题库与知识库材料。
- When 执行离线数据构建脚本。
- Then 生成标准化产物、SQLite、Chroma 持久化目录与质量报告，且阻断级错误为 0。

### AC-01 岗位化会话创建
- Given 用户已登录且简历上传成功。
- When 用户选择岗位与难度并开始面试。
- Then 返回 `interviewId`，状态为 `INIT`，并进入 `SELF_INTRO`。

### AC-02 面试单位循环可用
- Given 用户选择语音输入与语音输出。
- When 用户完成一轮回答。
- Then 系统完成 ASR -> LLM -> TTS，并返回下一问。

### AC-03 项目追问规则生效
- Given 当前处于项目深挖阶段且回答不完整。
- When 追问次数未达到上限。
- Then 系统生成追问并返回剩余追问次数。

### AC-04 技术阶段题量与纠错
- Given 当前处于技术基础阶段。
- When 完成提问流程。
- Then 系统总提问数在 3-5 题范围；错误回答可当场指出并讲解。

### AC-05 行为题追问上限
- Given 当前为场景/行为开放题。
- When 触发连续追问。
- Then 追问次数不超过 3 次，达到上限后自动切换下一环节。

### AC-06 异步报告生成
- Given 用户执行结束面试。
- When 接口返回成功。
- Then 会话状态为 `FINISHED`，报告状态为 `GENERATING`，最终可查询结构化报告。

### AC-07 历史记录驱动下一轮
- Given 用户已有历史报告与短板标签。
- When 用户发起下一次同岗位面试。
- Then 系统优先抽取与短板相关的题目或知识点。

### AC-08 数据规模达标
- Given 完成初始化数据导入。
- When 运营检查岗位资源规模。
- Then 每岗位题库 >=150 题，知识记录 >=200 条。

## 9. 风险与待确认项（按优先级）

### P0
- 评分维度权重与分数解释口径尚未冻结。
  - 影响：报告可信度、跨场次可比性、成长曲线准确性。
- 阶段切换和“回答正确/错误”判定阈值未量化。
  - 影响：追问稳定性、测试可重复性、用户体验一致性。
- 报告生成 Agent 的接口契约未明确（输入字段、幂等、重试）。
  - 影响：异步链路稳定性与可追踪性。
- `java-interview-additional.md` 历史编码问题已修复，需在数据校验脚本中保留编码巡检规则避免回归。
  - 影响：若回归会影响题库导入完整性与离线门禁通过率。

### P1
- 首期岗位清单待最终确认（仅“至少两类”）。
  - 影响：题库建设计划、标注口径、验收边界。
- 语音链路异常降级策略细节待定（自动切文本/手动切换）。
  - 影响：面试完成率与中断率。
- 历史短板到提问策略的映射规则待量化。
  - 影响：个性化效果可解释性与评估方式。
- SQLite 并发写入能力与锁竞争风险（高并发时）。
  - 影响：会话写入延迟、报告落盘失败率、扩展性上限。

### P2
- 题库/知识库后台是否需要审核流、版本化与回滚能力未确定。
  - 影响：数据治理成本与线上稳定性。
- 数据保留周期与脱敏策略待与合规要求对齐。
  - 影响：隐私风险与审计成本。

## 10. 落盘信息

- 目标路径：`devdocs/PRD.md`
- 角色：Agent 1（需求与接口设计）
- 输入来源：`plan/Requirement.md`、`plan/Logic.md`
- 可交接物：本 PRD 可直接供 Agent 2 输出改动计划使用
