# Agent 2 改动计划：AI 模拟面试与能力提升平台 V1

## 0. 输入与边界

- 输入文档：`devdocs/PRD.md`
- 计划类型：新需求首次落地（当前仓库无业务代码，按“从 0 到 1”拆解）
- 目标：产出可供 Agent 3 直接执行的文件/方法级改动计划，并覆盖 AC-01~AC-07

### 0.1 模板适配自检（最小检查集）

- 角色目标与边界：已明确（仅输出改动计划，不直接编码）
- 输入/输出与 DoD：已明确（输入 `devdocs/PRD.md`，输出 `.ai-workspace/*.md` + `LATEST.md`）
- 上下游依赖与门禁：已明确（本计划生成后由 Agent 3 基于 `LATEST.md` 执行）
- 与仓库规则冲突检查：
  - 注释、日志中文、接口变更后 Postman 更新要求已纳入计划
  - Agent 3 仅可基于本计划执行，符合流程门禁

## 1. 改动总览

### 1.1 实施范围（MVP）

- 用户与鉴权：支持获取当前用户信息
- 简历上传与结构化解析：支持简历入库、解析状态跟踪
- 面试会话与多轮问答：支持阶段流转、追问配额、状态查询
- 报告异步生成：结束面试触发异步任务，报告可查询
- 历史记录与个性化提问基础：历史结果参与下一次同岗位提问权重
- 题库/知识库管理接口：支持后台最小可用导入/新增

### 1.2 架构分层

- `api`：路由与请求校验
- `application`：面试流程编排、追问策略、报告生成编排
- `domain`：实体与规则（阶段、状态、追问上限）
- `infrastructure`：数据库访问、任务队列、外部能力（ASR/TTS/LLM）适配
- `tests`：按 AC 建立单元/集成用例

### 1.3 AC 映射

- AC-01：会话创建链路
- AC-02：追问决策链路
- AC-03：技术题纠错链路
- AC-04：语音输入降级链路
- AC-05：报告异步链路
- AC-06：历史结果参与选题链路
- AC-07：题库/知识库规模校验链路

## 2. 文件级改动清单（表格）

| 类型 | 文件路径 | 类/方法（规划） | 改动目的 | 实现要点 |
| --- | --- | --- | --- | --- |
| 新增 | `backend/src/app.py` | `create_app()` | 应用启动与路由注册 | 装配中间件、错误处理、健康检查 |
| 新增 | `backend/src/api/routes/users.py` | `get_me()` | 提供当前用户信息接口 | 鉴权上下文读取，返回标准用户结构 |
| 新增 | `backend/src/api/routes/resumes.py` | `upload_resume()` | 简历上传与解析入口 | 文件存储、异步解析触发、返回 `parseStatus` |
| 新增 | `backend/src/api/routes/interviews.py` | `create_interview()` `submit_turn()` `get_interview()` `finish_interview()` `get_history()` | 面试主流程接口 | 状态机校验、追问配额、分页查询 |
| 新增 | `backend/src/api/routes/reports.py` | `get_report()` | 报告查询 | 报告状态与结构化结果输出 |
| 新增 | `backend/src/api/routes/admin.py` | `create_question()` `import_knowledge()` | 后台题库/知识库管理 | 管理员权限校验、批量导入结果统计 |
| 新增 | `backend/src/api/schemas/*.py` | 请求/响应 DTO | 统一接口契约 | 字段约束、枚举合法性、错误信息规范 |
| 新增 | `backend/src/domain/entities/*.py` | `User` `Resume` `InterviewSession` `InterviewTurn` `InterviewReport` | 领域模型落地 | 与 PRD 数据模型字段对齐 |
| 新增 | `backend/src/domain/services/follow_up_policy.py` | `decide_follow_up()` | AC-02 追问规则 | 基于完整性/正确性分数与剩余额度决策 |
| 新增 | `backend/src/domain/services/stage_machine.py` | `next_stage()` | 阶段切换控制 | 固定阶段顺序 + 边界校验 |
| 新增 | `backend/src/application/interview_service.py` | `start_session()` `process_turn()` `finish_session()` | 面试用例编排 | 聚合题库、知识库、评分与状态流转 |
| 新增 | `backend/src/application/report_service.py` | `enqueue_report_generation()` `build_report()` | 报告异步生成 | 任务入队、结果回写、失败重试 |
| 新增 | `backend/src/application/personalization_service.py` | `build_focus_tags()` | 历史短板参与选题 | 提取历史弱项标签，影响下一场选题 |
| 新增 | `backend/src/infrastructure/repositories/*.py` | 各实体 Repo | 数据持久化 | CRUD、分页、事务边界 |
| 新增 | `backend/src/infrastructure/queue/report_worker.py` | `consume_report_jobs()` | 报告任务消费 | 幂等执行、失败重试、超时标记 |
| 新增 | `backend/src/infrastructure/adapters/asr_adapter.py` | `speech_to_text()` | 语音转文字 | 异常映射 `ASR_502` + 文本降级提示 |
| 新增 | `backend/src/infrastructure/adapters/llm_adapter.py` | `ask_question()` `score_answer()` | 题目生成与回答评分 | 统一超时、失败映射 `LLM_503` |
| 新增 | `backend/src/infrastructure/adapters/tts_adapter.py` | `synthesize_text()` | 文字转语音 | 非阻断，失败可回落文本 |
| 新增 | `backend/src/common/errors.py` | `BusinessError` `to_error_response()` | 统一错误码输出 | 映射 AUTH/PERM/PARAM/STATE/ASR/LLM/REPORT |
| 新增 | `backend/src/common/logging.py` | `get_logger()` | 统一日志规范 | 日志内容中文，含 requestId |
| 新增 | `backend/migrations/001_init_schema.sql` | DDL | 初始化核心表 | 用户、简历、会话、轮次、报告、题库、知识库 |
| 新增 | `backend/migrations/002_seed_minimum_data.sql` | DML | 最小初始化数据 | 2 岗位基础题库与知识库种子 |
| 新增 | `backend/migrations/003_indexes_and_constraints.sql` | DDL | 性能与约束 | 高频查询索引、唯一约束、外键完整性 |
| 新增 | `backend/tests/unit/test_follow_up_policy.py` | 单测 | 覆盖追问决策 | 正常/异常/边界路径 |
| 新增 | `backend/tests/unit/test_stage_machine.py` | 单测 | 覆盖阶段流转 | 合法流转与非法状态 |
| 新增 | `backend/tests/integration/test_interview_flow.py` | 集成测试 | 覆盖 AC-01/02/05 | 创建->问答->结束->报告 |
| 新增 | `backend/tests/integration/test_voice_fallback.py` | 集成测试 | 覆盖 AC-04 | ASR 失败降级与错误码 |
| 新增 | `backend/tests/integration/test_history_personalization.py` | 集成测试 | 覆盖 AC-06 | 历史短板影响选题权重 |
| 新增 | `backend/tests/integration/test_data_scale_guard.py` | 集成测试 | 覆盖 AC-07 | 每岗位题库>=150、知识>=200 |
| 新增 | `prompts/sirius-api.postman.json` | Postman Collection | 同步接口契约 | 覆盖 PRD 所有接口与示例 |
| 视情况新增 | `prompts/Interview-api.postman.json` | Postman Collection | 兼容仓库历史命名 | 若项目约定需要双文件则同步维护 |
| 新增 | `docs/backend-architecture.md` | 架构文档 | 便于 Agent5 评审 | 领域边界、调用链、回滚方案 |

## 3. 关键逻辑伪代码

### 3.1 提交回答与追问决策（AC-02/03）

```text
function submit_turn(interview_id, payload):
    session = repo.get_session(interview_id)
    assert session.status in [INIT, IN_PROGRESS], else STATE_409

    normalized_answer = payload.rawText
    if payload.inputType == "voice":
        normalized_answer = asr_adapter.speech_to_text(payload.audio)
        if asr failed:
            raise ASR_502 with retry_hint

    scoring = llm_adapter.score_answer(question=session.current_question, answer=normalized_answer)

    follow_up = follow_up_policy.decide_follow_up(
        stage=payload.stage,
        score=scoring,
        follow_up_used=session.follow_up_used,
        follow_up_max=session.follow_up_max
    )

    if payload.stage == TECHNICAL and scoring.correctness < threshold:
        explanation = build_short_explanation(session.current_question)
    else:
        explanation = null

    next_question = question_selector.select(
        stage=payload.stage,
        should_follow_up=follow_up.should_follow_up,
        weakness_tags=get_history_weakness_tags(session.user_id, session.job_role)
    )

    repo.save_turn(...)
    repo.update_session(...)
    return response(turn_id, scoring, follow_up, next_question, explanation)
```

### 3.2 结束面试与异步报告（AC-05）

```text
function finish_interview(interview_id):
    session = repo.get_session(interview_id)
    assert session.status != FINISHED, else STATE_409

    session.status = FINISHED
    repo.update_session(session)

    report = report_repo.create(interview_id, status=GENERATING)
    queue.enqueue("report_generation", { interview_id, report_id: report.id })

    return { interviewId: interview_id, status: "FINISHED", reportStatus: "GENERATING" }

worker report_generation(job):
    data = repo.load_interview_full(job.interview_id)
    summary = report_service.build_report(data)
    report_repo.mark_ready(job.report_id, summary)
```

### 3.3 历史短板参与提问（AC-06）

```text
function build_focus_tags(user_id, job_role):
    history_reports = report_repo.list_recent(user_id, job_role, limit=5)
    weakness_tags = aggregate_top_tags(history_reports.weaknesses)
    return weakness_tags

function select_question(stage, should_follow_up, weakness_tags):
    if should_follow_up:
        return follow_up_question_generator.from_last_answer()
    return question_bank.pick_by(stage=stage, priority_tags=weakness_tags)
```

## 4. 数据库变更计划

### 4.1 DDL（核心表）

- `users(id, name, email, role, created_at)`
- `resumes(resume_id, user_id, file_url, structured_profile_json, parse_status, created_at)`
- `interview_sessions(interview_id, user_id, job_role, difficulty, status, current_stage, follow_up_max, follow_up_used, started_at, finished_at)`
- `interview_turns(turn_id, interview_id, stage, question_text, answer_text, input_type, scores_json, follow_up_count, created_at)`
- `interview_reports(report_id, interview_id, overall_score, dimension_scores_json, highlights_json, weaknesses_json, suggestions_json, status, created_at)`
- `question_bank(question_id, job_role, type, difficulty, content, tags_json, active, created_at)`
- `knowledge_records(record_id, job_role, source_type, content, embedding, metadata_json, created_at)`

### 4.2 索引与约束

- `interview_sessions(user_id, job_role, started_at desc)`
- `interview_turns(interview_id, created_at)`
- `question_bank(job_role, type, difficulty, active)`
- `knowledge_records(job_role, source_type)`
- 唯一约束：`resumes(resume_id)`、`interview_reports(interview_id)`

### 4.3 迁移顺序

1. `001_init_schema.sql`（建表）
2. `003_indexes_and_constraints.sql`（索引与约束）
3. `002_seed_minimum_data.sql`（种子数据）

### 4.4 兼容策略

- 所有新增字段提供默认值（避免读写空值异常）
- 报告状态机允许 `GENERATING -> READY/FAILED` 幂等更新
- `embedding` 字段可先支持空占位，后续批量补齐

## 5. 实施步骤（Step-by-step）

1. 初始化后端目录骨架与应用入口，打通健康检查。
2. 实现统一错误码与日志组件，确保全链路可观测。
3. 落地数据库迁移脚本并执行本地初始化。
4. 实现领域模型与 Repo 层，完成基础 CRUD。
5. 实现会话创建/状态查询/提交轮次/结束面试接口。
6. 实现追问策略与阶段状态机，接入 `submit_turn`。
7. 实现 ASR/LLM/TTS 适配器与异常映射。
8. 接入报告异步任务（入队 + worker + 状态回写）。
9. 实现历史记录与个性化提问标签聚合。
10. 实现后台题库与知识库管理接口。
11. 更新 Postman：`prompts/sirius-api.postman.json`（必要时同步 `prompts/Interview-api.postman.json`）。
12. 编写并执行单元/集成测试，补齐覆盖率。

### 5.1 联调顺序

1. 用户/鉴权 -> 2) 简历上传 -> 3) 面试会话 -> 4) 轮次提交 -> 5) 结束与报告 -> 6) 历史与个性化 -> 7) 管理后台导入

## 6. 风险、回滚与兼容策略

### 6.1 关键风险

- 评分口径未冻结导致报告前后不可比
- 阶段切换阈值不明确导致问答流程不稳定
- 语音服务波动导致会话中断
- 报告异步任务堆积导致超时
- 仓库 Postman 文件命名存在双约定（`sirius-api` 与 `Interview-api`）

### 6.2 风险缓解

- 固化评分配置中心（版本化权重 + 生效时间）
- 阶段切换规则参数化并加审计日志
- ASR/TTS 失败统一回落文本链路
- 报告任务设置超时、重试与死信队列
- 在实施前由负责人确认 Postman 以哪个文件为主，避免并行维护冲突

### 6.3 回滚点

- 回滚点 A：完成数据库迁移后（可回滚到空库快照）
- 回滚点 B：完成会话主链路后（保留只读查询接口）
- 回滚点 C：接入异步报告后（关闭 worker 开关，保留同步占位）

### 6.4 兼容策略

- 所有接口返回统一错误结构和 `requestId`
- 状态变更采用显式枚举，拒绝隐式字符串
- 历史个性化策略支持开关控制，默认可关闭

## 7. 测试关注点

- 接口正确性：状态码、字段完整性、错误码一致性
- 状态机边界：已结束会话禁止继续提交（`STATE_409`）
- 追问配额边界：达到上限后必须停止追问
- 技术题纠错：低正确率时返回纠错讲解
- 语音链路：ASR 失败返回 `ASR_502` 且提示重试
- 异步报告：`FINISHED -> GENERATING -> READY/FAILED` 状态闭环
- 个性化提问：历史弱项确实影响后续选题
- 数据规模门禁：每岗位题库>=150、知识记录>=200
- 覆盖率目标：单元+集成总体不低于 80%

## 8. 可交接物、DoD、风险与待确认项

### 8.1 可交接物

- 本计划文档（供 Agent 3 直接执行）
- `.ai-workspace/LATEST.md` 最新计划指针

### 8.2 完成定义（DoD）

- 开发可按本计划直接编码，无需二次拆解
- 每个改动点映射到 PRD 范围与 AC
- 包含数据库迁移顺序、回滚点、联调顺序
- 已覆盖接口文档同步要求（Postman）

### 8.3 待确认项（执行前）

- 后端技术栈最终选择（不影响当前分层计划）
- 报告生成时延 SLO（影响队列并发配置）
- Postman 主文件命名约定（`sirius-api` 或 `Interview-api`）

## 9. 落盘信息

- 目标路径：`.ai-workspace/plan-agent2-prd-v1-20260401.md`
- 产出角色：Agent 2（代码改动规划）
- 供执行角色：Agent 3（开发实现）

## 10. LATEST.md 更新信息

- 目标路径：`.ai-workspace/LATEST.md`
- 指向内容：`plan-agent2-prd-v1-20260401.md`
