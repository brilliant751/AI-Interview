# Urgent-4：语音与问答链路从占位实现升级为可用实现（Agent1）

## 1. 需求摘要

### 背景与目标
当前语音与问答链路仍为占位实现：
- `backend/app/services/voice_service.py` 使用 mock ASR/TTS。
- `backend/app/services/question_workflow.py` 为模板化问题生成。

本次目标是在 **dev 环境可用** 前提下，接入真实 ASR/TTS/LLM，并保证任何上游失败时均有可观测的降级路径，不中断核心面试流程。

### 成功判定（业务口径）
- 语音输入模式下，后端可完成音频转文本（ASR）并继续提问。
- 输出语音模式下，后端可返回真实 TTS 音频地址或可下载资源。
- 下一题生成优先走真实 LLM；失败时自动降级到模板提问，且可追踪。

## 2. 范围定义（In Scope / Out of Scope）

### In Scope
- 改造 `VoiceService`：支持真实 ASR/TTS 调用（dev 环境可配置）。
- 改造 `QuestionWorkflow`：支持真实 LLM 生成下一题（保留模板兜底）。
- 扩展提交轮次接口以支持音频输入字段与降级可观测字段。
- 增加错误码与日志字段，确保排障可追踪。
- 补充必要配置项（环境变量）与默认值策略（dev 优先可用）。

### Out of Scope
- 不做 WebSocket 实时流式通话链路。
- 不做多云多供应商智能路由（仅保留 provider 配置与单活调用）。
- 不做生产级对象存储音频生命周期治理（仅满足 dev 可用与可验证）。

## 3. 接口定义（OpenAPI 风格草案）

### 3.1 提交轮次接口（改造）
- 路径：`POST /api/v1/interviews/{interview_id}/turns`
- 鉴权：`Bearer user token`（沿用现状）
- 幂等：`X-Idempotency-Key`（沿用现状）

#### Request Body（新增字段）
```json
{
  "stage": "SELF_INTRO|TECHNICAL|BEHAVIORAL",
  "answer_text": "string, optional",
  "asr_text": "string, optional",
  "answer_audio_url": "string(url), optional",
  "answer_audio_format": "wav|mp3|m4a|pcm16, optional"
}
```

#### 入参规则
- 至少满足以下之一：
  - `answer_text` 非空；
  - `asr_text` 非空；
  - `answer_audio_url` 非空（由后端执行 ASR）。
- 优先级：`asr_text` > `answer_text` > `ASR(answer_audio_url)`。
- 若三者均不可用，返回 `VALIDATE_400`。

#### Response Body（新增可观测字段）
```json
{
  "interview_id": "int_xxx",
  "stage": "TECHNICAL",
  "next_question": "...",
  "follow_up_count": 0,
  "live_score": 76,
  "output_mode": "text|voice",
  "tts_audio_url": "https://.../q_xxx.mp3",
  "pipeline_meta": {
    "asr_provider": "openai",
    "llm_provider": "openai",
    "tts_provider": "openai",
    "degrade_flags": ["TTS_FALLBACK_TEXT"],
    "trace_id": "trc_xxx"
  }
}
```

#### 错误码补充
- `UPSTREAM_TIMEOUT`：上游模型超时。
- `ASR_UPSTREAM_FAILED`：ASR 上游失败且无可用文本降级输入。
- `LLM_UPSTREAM_FAILED`：LLM 上游失败（此时服务端应自动降级模板提问，通常不抛错）。
- `TTS_UPSTREAM_FAILED`：TTS 上游失败（返回文本问题，`tts_audio_url=null`）。

### 3.2 可选健康检查接口（新增，建议）
- 路径：`GET /api/v1/admin/providers/health`
- 用途：验证 dev 环境 ASR/TTS/LLM 可用性。
- 返回示例：
```json
{
  "asr": {"provider": "openai", "status": "UP"},
  "tts": {"provider": "openai", "status": "UP"},
  "llm": {"provider": "openai", "status": "DEGRADED"}
}
```

## 4. 数据模型草案

### 4.1 配置模型（`Settings`）
新增配置项（`AI_INTERVIEW_` 前缀）：
- `OPENAI_API_KEY`：字符串，dev 必填（若 provider=openai）。
- `ASR_MODEL`：默认 `whisper-1`。
- `TTS_MODEL`：默认 `tts-1`。
- `TTS_VOICE`：默认 `alloy`。
- `LLM_MODEL`：默认 `gpt-5.2`（可按环境覆盖）。
- `PROVIDER_TIMEOUT_SECONDS`：默认 `20`。
- `PROVIDER_MAX_RETRIES`：默认 `2`。

### 4.2 轮次记录扩展（`interview_turns`）
建议新增列：
- `input_source`：`TEXT|ASR_CLIENT|ASR_SERVER`。
- `asr_provider`：文本，可空。
- `llm_provider`：文本，可空。
- `tts_provider`：文本，可空。
- `degrade_flags`：JSON 字符串，默认 `[]`。
- `trace_id`：文本，可空。
- `latency_ms`：整数，可空（端到端处理时延）。

## 5. 验收标准（Given-When-Then）

1. 正常语音输入链路
- Given：`input_mode=voice` 且提交 `answer_audio_url`
- When：调用 `POST /interviews/{id}/turns`
- Then：后端完成 ASR + LLM，返回 `next_question`，若 `output_mode=voice` 返回非空 `tts_audio_url`

2. LLM 失败降级
- Given：LLM 上游超时或 5xx
- When：提交有效回答
- Then：接口仍返回 200，`next_question` 由模板生成，`pipeline_meta.degrade_flags` 包含 `LLM_FALLBACK_TEMPLATE`

3. TTS 失败降级
- Given：`output_mode=voice` 且 TTS 上游失败
- When：生成下一题
- Then：返回 200，`next_question` 非空、`tts_audio_url=null`，并记录 `TTS_FALLBACK_TEXT`

4. ASR 失败且无文本兜底
- Given：仅传 `answer_audio_url`，ASR 上游失败
- When：提交轮次
- Then：返回 502（或 424），错误码 `ASR_UPSTREAM_FAILED`，错误信息可追踪上游调用结果

5. 可观测性
- Given：任意一轮请求
- When：请求完成
- Then：日志中可按 `trace_id/interview_id/turn_id` 关联主路径与降级路径，并可定位具体 provider 与耗时

## 6. 风险与待确认项（按优先级）

### P0
- OpenAI 凭证与网络连通性是否在 dev 环境已具备。
  - 影响：无可用密钥时无法达成“真实接入”。

### P0
- `answer_audio_url` 的来源可信度与可访问性（内网 URL、临时签名 URL、过期策略）。
  - 影响：ASR 入口稳定性。

### P1
- `LLM_MODEL` 具体选型是否统一为 `gpt-5.2`，或允许按岗位切换。
  - 影响：问题质量稳定性与成本。

### P1
- 是否新增独立 ASR 接口（如 `POST /voice/asr`）供前端预检。
  - 影响：前后端职责边界和时延分布。

### P2
- 是否在当前阶段接入 metrics（如 Prometheus），或仅依赖结构化日志。
  - 影响：可观测深度与运维复杂度。

## 7. Context7 查询记录（按仓库约定）

- `libraryId`: `/openai/openai-python`
- 查询关键词：
  - `audio transcription ASR`
  - `audio speech TTS`
  - `chat completions / text generation`
  - `retry timeout error handling`

### 关键结论
- 可用统一 Python SDK 完成 ASR/TTS/LLM 接入，满足 dev 期快速落地。
- SDK 支持超时与重试参数，默认有重试能力，适合构建“主路径失败 -> 降级路径”策略。
- 推荐通过环境变量管理 API Key，避免密钥入库。

### 适用版本/日期
- 本文档基于 Context7 可检索到的 `openai-python` 文档与版本索引（含 `v2.11.0`）整理。
- 产出日期：2026-04-06（Asia/Shanghai）。

## 8. 落盘信息
- 目标路径：`devdocs/agent1-urgent-voice-qa-real-integration-20260406.md`
- 状态：已落盘，可直接交接 Agent 2 拆解改动计划。
