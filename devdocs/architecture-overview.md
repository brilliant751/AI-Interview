# AI-Interview 架构说明

本文档用于说明 AI-Interview 项目的主要模块边界、运行时依赖和数据流。它不定义新的产品需求，只记录当前代码结构，方便小组成员理解项目并定位问题。

## 1. 总体结构

项目采用前后端分离结构：

- `frontend/`：React + Vite + Ant Design 前端应用。
- `backend/`：FastAPI 后端服务，负责认证、简历、JD、面试、练习、报告、管理端导入等接口。
- `scripts/data/`：离线材料规范化、题库导入、知识库索引构建脚本。
- `data/scripts/`：选择题翻译、中文题库重建等离线数据处理脚本。
- `tests/backend/`：后端单元测试和集成测试。
- `devdocs/`：需求、运行手册、报告模板和工程说明。
- `backend/migrations/`：SQLite 数据库迁移 SQL。

核心运行路径是：

1. 用户在前端登录。
2. 用户上传简历或选择已有简历。
3. 用户选择岗位方向或绑定 JD。
4. 前端调用后端创建面试会话。
5. 后端保存会话快照并返回首题。
6. 用户提交文本或语音回答。
7. 后端执行 ASR、RAG、LLM、TTS 等链路，生成下一题。
8. 面试结束后后端异步生成报告。
9. 前端查询报告并展示结构化结果。

## 2. 后端分层

后端主要分为以下几层：

- `api/v1/`：HTTP 路由层。
- `models/schemas.py`：请求和响应模型。
- `services/`：业务编排层。
- `repositories/`：SQLite 数据访问层。
- `core/`：配置、错误、日志、安全等基础设施。
- `domain/`：领域规则，例如面试状态机。

路由层只负责协议转换和依赖注入。它不应该直接写复杂业务逻辑，也不应该绕过服务层直接修改状态。

服务层负责业务规则。例如：

- `InterviewService`：会话创建、轮次提交、阶段推进、语音降级、报告触发。
- `PracticeService`：题库练习创建、答题推进、记录查询。
- `CodingPracticeService`：编程题列表、会话恢复、运行和提交。
- `InterviewScheduleService`：预约创建、状态懒刷新、日历链接、开始预约。
- `ReportService`：结构化报告生成和规则回退报告。
- `QuestionWorkflow`：下一题生成、模板兜底和模型输出清理。

仓储层统一封装 SQLite 读写。服务层不直接拼 SQL，避免权限和事务逻辑分散。

## 3. 前端分层

前端主要分为：

- `api/`：接口类型和请求函数。
- `stores/`：Zustand 全局状态。
- `pages/`：页面级组件。
- `components/`：可复用组件。
- `hooks/`：通用 Hook。
- `utils/`：纯工具函数。
- `monaco/`：Monaco 编辑器配置。

前端数据来源分为两类：

- 远端状态：React Query 管理，例如简历列表、预约列表、报告、题库记录。
- 当前会话状态：Zustand 管理，例如当前面试题目、当前练习题、认证信息。

前端不应自行推导关键业务状态，例如面试下一阶段、练习下一题、报告是否完成。这些状态应以后端返回为准。

## 4. 面试流程

面试流程的主要后端入口是 `InterviewService`。

创建会话时，后端会校验：

- 简历是否存在。
- 简历是否属于当前用户。
- 是否提供岗位方向或 JD。
- JD 是否存在且有权限访问。
- JD 岗位方向是否与面试方向一致。
- 预约时间是否合法。
- 语气配置是否可用。

提交回答时，后端会校验：

- 会话是否存在。
- 用户是否有权访问会话。
- 会话是否已经结束、暂停或未到预约时间。
- 提交阶段是否等于当前阶段。
- 回答内容是否为空。

然后服务层执行：

1. 解析回答来源。
2. 提取简历相关片段。
3. 检索知识库材料。
4. 合并 JD、简历和知识库上下文。
5. 根据状态机计算下一阶段。
6. 调用 LLM 或模板生成下一题。
7. 按输出模式尝试 TTS。
8. 写入轮次记录。
9. 更新会话阶段或触发报告生成。

## 5. 状态机

当前面试阶段包括：

- `SELF_INTRO`
- `PROJECT_DEEP_DIVE`
- `TECHNICAL`
- `BEHAVIORAL`
- `END`

允许迁移：

- `SELF_INTRO -> PROJECT_DEEP_DIVE`
- `PROJECT_DEEP_DIVE -> TECHNICAL`
- `TECHNICAL -> TECHNICAL`
- `TECHNICAL -> BEHAVIORAL`
- `TECHNICAL -> END`
- `BEHAVIORAL -> BEHAVIORAL`
- `BEHAVIORAL -> END`

状态机规则放在 `backend/app/domain/interview_state.py`。服务层可以计算目标阶段，但必须经过状态机校验。

## 6. Provider 设计

项目支持多类可插拔 provider：

- LLM：mock、OpenAI 兼容接口、Ollama。
- ASR：mock、OpenAI、FunASR。
- TTS：mock、OpenAI、PaddleSpeech。
- Embedding：Ollama 或 hash fallback。

服务层应把 provider 当成可失败的增强能力：

- LLM 失败时可以降级为模板问题。
- TTS 失败时可以降级为文本题目。
- ASR 失败时应返回可理解错误。
- Embedding 不可用时可按配置决定是否 fallback。

前端通过 provider health 展示当前模式，避免用户误以为所有能力都在线。

## 7. 报告生成

报告生成分为两条路径：

- LLM 报告：根据轮次、JD、简历和预计算分数生成结构化报告。
- 规则回退报告：当 LLM 不可用时，基于轮次分数、回答长度、阶段分布和 token 命中生成报告。

报告字段包括：

- 总分。
- 优势。
- 不足。
- 建议。
- 12 维能力分。
- JD/简历匹配。
- 问题深挖分析。
- 关键风险。
- 最终建议。

报告生成由 `ReportWorker` 异步执行，接口先返回 `GENERATING` 状态，前端轮询或刷新报告页获取结果。

## 8. 预约流程

预约功能由 `InterviewScheduleService` 管理。

预约表记录：

- 用户。
- 简历。
- JD。
- 岗位方向。
- 难度。
- 输入输出模式。
- 预约开始和结束时间。
- 时区。
- 当前状态。

预约状态通过查询时懒刷新：

- 未到时间：`scheduled`
- 临近开始窗口：`ready`
- 已开始：`in_progress`
- 已完成：`completed`
- 超时未开始：`missed`
- 用户取消：`cancelled`

这种设计避免额外引入定时任务，适合课程项目和单进程部署。

## 9. 练习流程

题库练习和编程练习是两条独立流程。

题库练习：

- 从 `practice_choice_questions` 或题库数据中选题。
- 创建练习时保存题目快照。
- 按当前题顺序提交答案。
- 完成后可查看记录和解析。

编程练习：

- 题目来自内置 JSON 材料。
- 应用启动时同步到 SQLite。
- 用户进入题目时创建或恢复 session。
- RUN 运行自测用例。
- SUBMIT 运行正式判题用例。

## 10. 数据脚本

材料流水线大致为：

1. `validate_materials.py` 检查材料结构。
2. `normalize_materials.py` 将 Markdown 材料转换为 JSONL。
3. `build_question_bank.py` 将题库 JSONL 导入 SQLite。
4. `build_knowledge_vectorstore.py` 构建知识库向量索引。

这些脚本应保持幂等。重复运行不应生成重复主键或破坏历史数据。

## 11. 设计原则

当前项目应继续遵守这些原则：

- 前端不绕过 API 契约。
- 后端路由不直接写复杂业务。
- 服务层不直接拼 SQL。
- 数据库写入集中到仓储。
- 外部 provider 失败要可降级或可解释。
- 测试默认不依赖真实模型服务。
- 离线脚本输出报告，方便排查导入问题。

