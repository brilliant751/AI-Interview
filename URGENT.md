# URGENT 待办（Agent5 维护）

- 最后更新：2026-04-27
- 依据评审：认证账号体系落地评审（Agent5）
- 维护规则：仅保留“未完成”且短周期必须推进的事项；已落地项在下次 review 时删除。

## P0（阻断放行）

无。

### 2. 前端布局组件触发无限更新，单测直接失败
- 当前状态：未完成
- 现状证据：
  - `frontend/src/components/AppLayout.tsx` 使用 Zustand selector 返回新对象（第 14-19 行）
  - 执行 `cd frontend && npm test` 失败，报错 `Maximum update depth exceeded`
- 完成标准：
  - 修复 `AppLayout` 对 `useAuthStore` 的订阅方式，避免渲染环触发
  - `frontend/src/components/AppLayout.test.tsx` 稳定通过，`npm test` 全绿

### 3. 后端测试/运行环境与项目门槛不一致（Python 3.9 vs 3.11+）
- 当前状态：未完成
- 现状证据：
  - `backend/pyproject.toml` 明确 `requires-python = ">=3.11"`
  - 当前 `.venv` 为 Python 3.9.6，执行 `./.venv/bin/python -m pytest -q tests/backend/test_security_compat.py tests/backend/test_auth_service.py` 在收集阶段报 `Unable to evaluate type annotation 'str | None'`
- 完成标准：
  - 开发与 CI 统一到 Python 3.11+
  - 后端测试可完整收集并执行，不再因类型注解版本不兼容阻塞

## P1（高优先）

### 4. API 契约与 PRD 不一致（路径/枚举/字段）
- 当前状态：未完成
- 现状证据：
  - PRD 报告路径为 `/api/v1/interviews/{interviewId}/report`，实现为 `/api/v1/report/{interview_id}`
  - PRD 岗位枚举为 `java_backend/web_frontend`，实现为 `java/web`
  - PRD 难度为 `1-5`，实现为 `easy/medium/hard`
- 完成标准：
  - PRD、OpenAPI、后端 schema、前端 API 类型四处一致
  - Postman 集合同步更新并可回放通过

### 5. 本地问答链路的阶段控制未闭环
- 当前状态：未完成
- 现状证据：
  - `backend/app/services/question_workflow.py` 中 `generate()` 对 `openai/ollama` 直接走 `generate_by_llm()`，`stage/technical_count/follow_up_count` 没有参与真实 LLM 提示词控制
  - `backend/app/services/rag_service.py` 只有在 `llm_provider == "ollama"` 时才走本地 embedding，其他配置会退回 hashing trick，导致检索质量与健康状态不一致
- 完成标准：
  - 真实 LLM 分支必须按阶段和轮次注入差异化 prompt
  - embedding provider 必须独立于 LLM provider 配置，且 fallback 要能被 health 明确暴露
  - 对应接口与测试用例同步覆盖

### 6. 报告结构未达 PRD 目标
- 当前状态：未完成
- 现状证据：
  - 现有仅 `overall_score + strengths/weaknesses/suggestions`
  - 缺少 PRD 要求的维度分与亮点结构
- 完成标准：
  - 报告结构与 PRD 对齐（含维度化评分）
  - 报告接口、前端展示与文档统一

### 7. 管理员账号不可达，管理接口在默认配置下不可用
- 当前状态：未完成
- 现状证据：
  - 默认仅支持注册 `role=user`，无管理员提升路径
  - `backend/migrations/0004_auth_backfill_dev_admin.sql` 未被应用启动流程执行（代码中无迁移执行入口）
  - `auth_enable_dev_static_token` 默认关闭后，旧 `admin-token` 也不可用
- 完成标准：
  - 提供可审计的管理员初始化或提权机制（至少覆盖 dev 启动场景）
  - 管理导入接口在默认开发流程可登录可访问，并有自动化用例覆盖

## P2（中优先）

### 8. 管理导入接口缺少异步任务化与状态追踪
- 当前状态：未完成
- 现状证据：
  - `backend/app/api/v1/admin.py` 以同步子进程串行执行导入（当前仅路径迁移到 `backend/assets/scripts/data/**`）
- 完成标准：
  - 返回 `task_id`
  - 提供任务查询接口（运行中/成功/失败 + 错误信息）

### 6. 本地 provider 客户端受系统代理影响
- 当前状态：未完成
- 现状证据：
  - `backend/app/services/providers/funasr_provider.py`、`backend/app/services/providers/ollama_provider.py`、`backend/app/services/providers/paddlespeech_provider.py` 使用默认 `httpx.Client(...)`
  - `backend/app/services/voice_service.py` 的 `_download_audio()` 使用默认 `httpx.get(...)`
  - 在 macOS 带 `ALL_PROXY/HTTP_PROXY` 的环境里，httpx 会继承 SOCKS 代理；若缺少 `socksio`，provider 初始化和回归测试会直接失败
- 完成标准：
  - 本地 provider 客户端默认不继承系统代理，或在启动脚本/文档中显式清理代理环境
  - 相关测试在代理环境下可稳定通过
