# URGENT 待办（Agent5 维护）

- 最后更新：2026-04-05
- 依据评审：本次 Agent5 review（工作区当前改动）
- 维护规则：仅保留“未完成”且短周期必须推进的事项；已落地项在下次 review 时删除。

## P0（阻断放行）

### 1. 数据脚本回归测试路径迁移不完整（单测失败）
- 当前状态：未完成
- 现状证据：
  - `tests/backend/test_data_scripts.py:40` 已调用 `assets/scripts/data/build_question_bank.py`
  - `tests/backend/test_data_scripts.py:46` 仍读取 `data/reports/question_bank_build_report.json`
  - 执行 `rtk python -m unittest tests/backend/test_data_scripts.py` 报 `FileNotFoundError`
- 完成标准：
  - 报告读取路径统一迁移到 `assets/data/reports/question_bank_build_report.json`
  - `rtk python -m unittest tests/backend/test_data_scripts.py` 全量通过

### 2. 迁移资产未纳入版本控制（存在“删旧未加新”发布风险）
- 当前状态：未完成
- 现状证据：
  - 当前变更删除了 `material/**`、`scripts/data/**`、`data/**` 下历史文件
  - 代码与文档已切换到 `assets/**` 路径（如 `backend/app/api/v1/admin.py`、`backend/app/core/config.py`）
  - 工作区仍为 `?? assets/`（未跟踪目录），若直接按当前跟踪集提交将导致运行资源缺失
- 完成标准：
  - `assets/material/**`、`assets/scripts/data/**`、`assets/data/**`（按仓库策略应纳入版本管理的文件）完整纳入提交
  - `git status --short` 不再出现迁移关键目录的未跟踪项
  - 在干净工作区执行一次数据脚本 dry-run 与后端启动校验通过

### 3. 前端测试门禁失败（Vitest 误收集 Playwright 用例）
- 当前状态：未完成
- 现状证据：
  - `frontend/package.json` 的 `test` 脚本为 `vitest run`
  - `frontend/vite.config.ts` 未排除 `tests/e2e/**`
  - `frontend/tests/e2e/main-flow.spec.ts` 使用 `@playwright/test`
- 完成标准：
  - `rtk npm --prefix frontend test` 通过
  - Playwright E2E 与 Vitest 单测分离执行（独立脚本与配置）

### 4. 面试阶段状态机缺失 `PROJECT_DEEP_DIVE`
- 当前状态：未完成
- 现状证据：
  - `backend/app/domain/interview_state.py` 缺少 `PROJECT_DEEP_DIVE`
  - `backend/app/services/interview_service.py` 从 `SELF_INTRO` 直接进入 `TECHNICAL`
- 完成标准：
  - 状态机补齐 `SELF_INTRO -> PROJECT_DEEP_DIVE -> TECHNICAL -> BEHAVIORAL -> END`
  - 对应接口、服务、测试用例同步覆盖

## P1（高优先）

### 5. API 契约与 PRD 不一致（路径/枚举/字段）
- 当前状态：未完成
- 现状证据：
  - PRD 报告路径为 `/api/v1/interviews/{interviewId}/report`，实现为 `/api/v1/report/{interview_id}`
  - PRD 岗位枚举为 `java_backend/web_frontend`，实现为 `java/web`
  - PRD 难度为 `1-5`，实现为 `easy/medium/hard`
- 完成标准：
  - PRD、OpenAPI、后端 schema、前端 API 类型四处一致
  - Postman 集合同步更新并可回放通过

### 6. 语音与问答链路仍为占位实现
- 当前状态：未完成
- 现状证据：
  - `backend/app/services/voice_service.py` 为 mock ASR/TTS
  - `backend/app/services/question_workflow.py` 为模板化提问
- 完成标准：
  - 接入真实 ASR/TTS/LLM（至少 dev 环境可用）
  - 失败时保留可观测的降级路径

### 7. 报告结构未达 PRD 目标
- 当前状态：未完成
- 现状证据：
  - 现有仅 `overall_score + strengths/weaknesses/suggestions`
  - 缺少 PRD 要求的维度分与亮点结构
- 完成标准：
  - 报告结构与 PRD 对齐（含维度化评分）
  - 报告接口、前端展示与文档统一

## P2（中优先）

### 8. 管理导入接口缺少异步任务化与状态追踪
- 当前状态：未完成
- 现状证据：
  - `backend/app/api/v1/admin.py` 以同步子进程串行执行导入（当前仅路径迁移到 `assets/scripts/data/**`）
- 完成标准：
  - 返回 `task_id`
  - 提供任务查询接口（运行中/成功/失败 + 错误信息）

### 9. 知识库规模未达 PRD AC-08 指标
- 当前状态：未完成
- 现状证据：
  - 当前知识记录：Java 117、Web 35
  - PRD 要求：每岗位知识记录 >= 200
- 完成标准：
  - 每岗位知识记录数 >= 200（以最新构建报告与落地索引双重核验）
