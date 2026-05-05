# Agent1 PRD：语音能力切换为 pip 安装后 SDK 直连模式（2026-04-11）

## 1. 需求摘要

### 1.1 背景
当前项目中的 FunASR / PaddleSpeech 采用“外部 HTTP 服务”模式：
- 后端通过 `funasr_base_url` 调用 `/asr`
- 后端通过 `paddlespeech_base_url` 调用 `/tts`
- `start.sh` 仅做可达性检查，不负责服务进程管理

该模式对本地服务编排依赖较强，开发环境启动复杂，且接口约定耦合第三方服务网关实现。

### 1.2 目标
将语音能力切换为“pip 安装后在后端进程内直接调用 SDK”的模式，保留现有业务 API 形态与降级能力，降低部署复杂度并提升可控性。

### 1.3 成功判定
- ASR/TTS 不再依赖外部 `funasr_base_url` / `paddlespeech_base_url` 才能工作。
- 后端通过 Python SDK 直接执行识别与合成。
- 现有面试主流程 API 不破坏兼容，前端无需改协议即可继续使用。
- 上游失败时仍能走可观测降级路径（文本兜底、模板兜底、错误码可追踪）。

## 2. 范围定义（In Scope / Out of Scope）

### 2.1 In Scope
- 后端语音 provider 实现重构：
  - FunASR：由 HTTP 上传音频改为 SDK 直调。
  - PaddleSpeech：由 HTTP `/tts` 改为 SDK 直调。
- 配置模型重构：
  - 新增 SDK 模式配置项（模型名、设备、采样率、音色等）。
  - 标记并逐步废弃 URL 型配置项。
- 健康检查机制重构：
  - 从“远程 `/health` 可达性”改为“本地 SDK 初始化 + 最小调用自检”。
- 兼容当前 `InterviewService` 的调用协议与 `pipeline_meta` 输出。
- 补齐异常分类与日志字段，确保排障一致性。
- 更新 API 文档和 Postman 集合中的 provider 状态说明（接口路径可不变）。

### 2.2 Out of Scope
- 不新增实时流式 ASR（WebSocket/RTC）能力。
- 不引入新的第三方语音供应商编排。
- 不做生产级 GPU 调度平台建设（仅定义必要配置位）。
- 不改动前端页面交互流程。

## 3. 接口定义（HTTP + 内部契约）

### 3.1 外部 HTTP 接口（保持兼容）

#### 3.1.1 提交轮次
- 路径：`POST /api/v1/interviews/{interview_id}/turns`
- 变更策略：请求/响应字段保持兼容，不新增破坏性字段。

请求关键字段（现有）：
```json
{
  "stage": "SELF_INTRO|PROJECT_DEEP_DIVE|TECHNICAL|BEHAVIORAL",
  "asr_text": "string, optional",
  "answer_text": "string, optional",
  "answer_audio_url": "string, optional"
}
```

输入优先级（保持）：
- `asr_text` > `answer_text` > 服务端 ASR

响应关键字段（现有）：
```json
{
  "next_question": "string",
  "tts_audio_url": "string|null",
  "pipeline_meta": {
    "providers": {"asr": "funasr|...", "llm": "...", "tts": "paddlespeech|..."},
    "provider_status": {"asr": "UP|DOWN|UNKNOWN", "llm": "UP|DOWN|UNKNOWN", "tts": "UP|DOWN|UNKNOWN"},
    "degrade_flags": ["string"]
  }
}
```

#### 3.1.2 Provider 健康检查
- 路径：`GET /api/v1/admin/providers/health`
- 语义变更：
  - 原语义：远程 URL 服务可达。
  - 新语义：SDK 初始化成功 + 最小能力可用。

### 3.2 内部 Provider 契约（新增统一约束）

#### 3.2.1 ASR Provider（内部）
- `transcribe_audio_bytes(audio_bytes: bytes, filename: str) -> dict`
- 返回：
```json
{
  "text": "string",
  "confidence": 0.0,
  "provider": "funasr",
  "latency_ms": 0
}
```

#### 3.2.2 TTS Provider（内部）
- `synthesize(text: str) -> bytes`
- 返回：WAV/PCM/MP3 二进制（由调用方统一封装 data URL）

#### 3.2.3 健康检查（内部）
- `health() -> dict`
- 返回：
```json
{
  "status": "UP|DOWN",
  "provider": "funasr|paddlespeech",
  "model": "string",
  "latency_ms": 0,
  "error_message": "string"
}
```

### 3.3 错误码约定
- `UPSTREAM_TIMEOUT`：模型推理超时。
- `ASR_UPSTREAM_FAILED`：ASR 执行失败。
- `TTS_UPSTREAM_FAILED`：TTS 执行失败。
- `VALIDATE_400`：缺少可处理输入。

约束：错误码保持现有语义，不因切换到 SDK 模式而改变对前端契约。

## 4. 数据模型草案

### 4.1 配置模型（Settings）
建议新增/保留字段：
- `AI_INTERVIEW_ASR_PROVIDER`：默认 `funasr`
- `AI_INTERVIEW_TTS_PROVIDER`：默认 `paddlespeech`
- `AI_INTERVIEW_ASR_MODEL`：默认 `paraformer-zh`
- `AI_INTERVIEW_TTS_MODEL`：默认 `fastspeech2_csmsc`
- `AI_INTERVIEW_PROVIDER_TIMEOUT_SECONDS`：默认 `20`
- `AI_INTERVIEW_ASR_DEVICE`：`cpu|cuda`，默认 `cpu`
- `AI_INTERVIEW_TTS_DEVICE`：`cpu|cuda`，默认 `cpu`
- `AI_INTERVIEW_TTS_SAMPLE_RATE`：默认 `24000`

建议废弃字段（兼容期保留读取）：
- `AI_INTERVIEW_FUNASR_BASE_URL`
- `AI_INTERVIEW_PADDLESPEECH_BASE_URL`

### 4.2 面试轮次记录（保持兼容）
沿用当前 `interview_turns` 中与链路可观测相关字段：
- `input_source`
- `asr_provider`
- `llm_provider`
- `tts_provider`
- `degrade_flags`
- `trace_id`
- `latency_ms`

本需求不强制新增表字段；如实现期发现字段不足，由 Agent2 在计划中补充迁移方案。

## 5. 前端交互与状态约束

- 前端请求协议不变，继续按当前输入优先级传参。
- 前端仍通过 `pipeline_meta.provider_status` 展示 provider 状态。
- 在 `tts_audio_url` 为空时，前端必须回退文字播报展示，不阻塞下一题流程。
- 若 `ASR_UPSTREAM_FAILED` 且用户未输入文本，前端提示“语音识别失败，请重试或切换文本输入”。

## 6. 非功能需求

### 6.1 性能
- 单轮 ASR + LLM + TTS 链路，P95 响应时间目标 <= 8s（dev 基线）。
- 单次 SDK 初始化不得阻塞主请求超过 2s，需使用惰性初始化与缓存实例。

### 6.2 可用性
- 任一 provider 失败不应导致主流程整体不可用：
  - LLM 失败 -> 模板问题兜底
  - TTS 失败 -> 文本兜底
  - ASR 失败 -> 若无文本输入则明确错误返回

### 6.3 可观测性
- 日志必须包含：`trace_id`, `interview_id`, `turn_id`, `provider`, `latency_ms`, `degrade_flags`。
- provider 健康检查输出需区分“初始化失败”和“推理失败”。

### 6.4 安全
- 不在日志打印完整音频内容或敏感文本。
- 依赖版本需固定主次版本范围，防止 SDK 行为漂移。

## 7. 验收标准（Given-When-Then）

1. ASR SDK 正常链路
- Given：`asr_provider=funasr` 且安装了依赖
- When：提交包含音频内容的轮次
- Then：后端返回非空识别文本并进入下一题生成

2. TTS SDK 正常链路
- Given：`tts_provider=paddlespeech` 且安装了依赖
- When：输出模式为语音
- Then：返回可播放的 `tts_audio_url`（data URL 或可下载 URL）

3. LLM 与 TTS 降级链路
- Given：LLM 或 TTS 任一执行失败
- When：提交有效回答
- Then：接口仍返回 200，`degrade_flags` 含对应标记，流程不中断

4. ASR 失败错误链路
- Given：仅有音频输入且 ASR 推理失败
- When：提交轮次
- Then：返回 `ASR_UPSTREAM_FAILED`，并提供可读中文错误信息

5. 健康检查语义
- Given：SDK 安装完整但模型加载失败
- When：调用 provider 健康检查
- Then：返回 `DOWN` 且 `error_message` 可定位问题

6. 向后兼容
- Given：前端不改代码
- When：走完整一轮面试
- Then：前端页面可正常消费响应，不出现字段缺失导致的渲染错误

## 8. 风险与待确认项（按优先级）

### P0
- FunASR / PaddleSpeech Python SDK 在当前 Python 版本（>=3.11）下的兼容性需确认。
- 影响：若不兼容，将阻塞“纯 SDK 直连”目标。

### P0
- 模型文件下载与本地缓存策略未统一（首次冷启动耗时可能过大）。
- 影响：启动慢、健康检查误判、体验不稳定。

### P1
- CPU 环境下 TTS/ASR 时延可能超出目标。
- 影响：语音模式体验下降，需要明确降级或提示策略。

### P1
- 音频格式兼容矩阵（wav/mp3/m4a）在 SDK 侧解析能力需统一。
- 影响：部分浏览器录音结果无法识别。

### P2
- 现有 `start.sh` 对 URL 可达性的检查逻辑需调整，否则会出现“服务可用但检查报错”。
- 影响：开发者误判系统健康状态。

## 9. 可交接物、DoD 与落盘信息

### 9.1 可交接物
- 本 PRD 文档（供 Agent2 产出改动计划）。
- 接口兼容与语义变更清单（以本 PRD 第 3 节为准）。
- 验收标准清单（以本 PRD 第 7 节为准）。

### 9.2 完成定义（DoD）
- 需求边界清晰：已明确 In/Out Scope。
- 契约可执行：外部接口与内部 provider 契约均已定义。
- 验收可测试：Given-When-Then 覆盖正常、异常、降级、兼容。
- 风险可追踪：每项风险均标注优先级与影响。
- 文档已写入 `devdocs/`，可被 Agent2 直接引用。

### 9.3 待确认执行约束（交接 Agent2/Agent3）
- 若涉及接口字段或语义变更，必须同步更新：
  - `openapi/openapi.yaml`
  - `postman/AI-Interview.postman_collection.json`
- 迁移期是否保留 URL 模式作为 feature flag 需在 Agent2 计划中明确。

### 9.4 落盘信息
- 目标路径：`devdocs/agent1-prd-sdk-direct-integration-20260411.md`
- 产出角色：Agent1（需求与接口设计）
- 状态：已完成，可进入 Agent2 规划阶段
