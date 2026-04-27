# PRD：本地模型接入方案（FunASR / DeepSeek / PaddleSpeech / Ollama）

## 1. 需求摘要

### 1.1 背景
当前项目已经具备 AI 面试主流程、题库、知识库、历史记录与报告能力，但核心生成链路仍以 OpenAI / mock 方式为主，默认运行方式对外部 API Key 依赖较强，不符合“本地模型优先、离线可运行、可控可复现”的目标。

本阶段的目标是把面试主链路真正切换为本地模型方案，形成可部署、可复用、可验证的本地 AI 面试能力。

### 1.2 目标
将以下能力真正接入并作为默认实现：
- 语音转文字：FunASR
- 面试问题生成 / 对话理解：DeepSeek（本地推理，建议通过 Ollama 托管）
- 文字转语音：PaddleSpeech
- 知识库索引 / 向量化 / 检索：Ollama + Qwen / Nomic Embedding 体系

### 1.3 目标状态
- 默认不需要 OpenAI API Key。
- 默认优先使用本地模型链路。
- 本地模型不可用时，允许按配置降级到 mock，但必须显式可见，不得静默冒充 AI 成功。
- 前端与后端都能明确感知当前链路是“本地 AI”还是“兜底模式”。

### 1.4 业务价值
- 降低外部依赖和 API 成本。
- 便于离线演示、校内部署和重复交付。
- 提高可控性与结果一致性，便于调试与评审。

## 2. 范围定义

### 2.1 In Scope
- 本地模型配置体系设计与落地。
- FunASR 接入语音识别链路。
- DeepSeek 本地推理接入面试问答与追问生成。
- PaddleSpeech 接入语音合成链路。
- Ollama 托管本地模型与 embedding 模型。
- 知识库向量化、检索与 rerank 本地化。
- 服务健康检查、降级策略与状态透传。
- 前端对本地模型状态的展示与错误提示。
- 启动脚本 / 环境变量 / 文档同步更新。

### 2.2 Out of Scope
- 训练或微调自有大模型。
- 企业级云端多租户计费。
- 移动端原生 App。
- 实时流式语音对话的低延迟优化到生产级。
- 真正面向公网的高可用集群部署。

## 3. 方案概述

### 3.1 统一原则
- 默认本地优先。
- 能本地完成的，不依赖外部 API。
- 必要时允许配置 mock 作为开发兜底，但不作为默认生产路径。
- 每个 provider 都要有独立健康检查与降级标记。

### 3.2 目标链路
- 输入：FunASR
- 面试问题生成：DeepSeek（本地）
- 知识检索：Chroma + Ollama embedding
- 输出：PaddleSpeech

### 3.3 推荐模型映射
- LLM：DeepSeek（通过 Ollama 托管），示例模型名：`deepseek-r1:8b`
- 文本切分 / 结构化辅助：`qwen3.5-2b`（通过 Ollama）
- Embedding：`nomic-embed-text`（通过 Ollama）
- ASR：FunASR
- TTS：PaddleSpeech

### 3.4 默认运行方式
- 默认 provider 配置改为本地模式。
- 不要求用户提供 OpenAI API Key。
- 仅当显式启用云端模式时，才允许配置外部 API Key。

## 4. 范围内的功能需求

### 4.1 语音转文字（ASR）
- 用户上传音频后，后端调用 FunASR 识别文本。
- 返回识别文本、置信度、耗时、provider 标识。
- 识别失败时，需给出可理解的错误信息，并允许切换到文本输入。

### 4.2 面试问题生成（LLM）
- 结合当前阶段、用户回答、岗位、知识库检索结果，由 DeepSeek 生成下一问。
- 技术题、项目深挖题、行为题的 prompt 必须分开控制。
- 同一会话中不允许长期重复同一模板问题。
- 若本地 LLM 异常，允许降级到模板，但必须标注 `LLM_FALLBACK_TEMPLATE`。

### 4.3 文字转语音（TTS）
- 面试官输出支持 PaddleSpeech 合成。
- 合成失败时可降级为纯文本输出，但必须保留降级状态。
- 返回音频地址或可播放音频内容。

### 4.4 知识库与检索
- 使用 Ollama 体系完成本地 embedding 与必要的本地文本处理。
- 使用 Chroma 完成向量检索。
- 根据岗位（Java / Web）返回相关知识片段。
- 允许在检索结果上增加本地 rerank 逻辑。

### 4.5 状态可观测
- 后端必须提供 provider 健康检查。
- 前端必须展示当前链路是本地 AI、兜底模板还是异常状态。
- 每轮面试返回中必须包含 provider 状态和降级标记。

## 5. 接口定义

### 5.1 环境变量契约

#### 必填 / 默认项
- `AI_INTERVIEW_LLM_PROVIDER=ollama`
- `AI_INTERVIEW_ASR_PROVIDER=funasr`
- `AI_INTERVIEW_TTS_PROVIDER=paddlespeech`
- `AI_INTERVIEW_LLM_MODEL=deepseek-r1:8b`
- `AI_INTERVIEW_EMBED_MODEL=nomic-embed-text`
- `AI_INTERVIEW_SPLIT_MODEL=qwen3.5-2b`

#### 本地服务地址
- `AI_INTERVIEW_OLLAMA_BASE_URL=http://localhost:11434`
- `AI_INTERVIEW_FUNASR_BASE_URL=http://localhost:<funasr_port>`
- `AI_INTERVIEW_PADDLESPEECH_BASE_URL=http://localhost:<paddlespeech_port>`

#### 兼容项
- `AI_INTERVIEW_OPENAI_API_KEY`：仅在显式启用云端模式时使用，默认本地模式不要求。

### 5.2 内部 provider 接口草案

#### ASR Provider
- 输入：音频 URL / 音频二进制、音频格式
- 输出：
```json
{
  "text": "识别文本",
  "confidence": 0.95,
  "provider": "funasr",
  "latency_ms": 1234
}
```

#### LLM Provider
- 输入：
```json
{
  "answer": "候选人回答",
  "stage": "TECHNICAL",
  "job_role": "java",
  "references": [
    { "title": "缓存一致性", "content": "..." }
  ],
  "difficulty": "medium"
}
```
- 输出：
```json
{
  "question": "下一题",
  "provider": "ollama-deepseek",
  "latency_ms": 980
}
```

#### TTS Provider
- 输入：待合成文本、音色、采样格式
- 输出：音频 URL / base64 / 本地文件路径

#### Health Check
- `GET /api/v1/admin/providers/health`
- 返回各 provider 的状态：`UP | DOWN | DEGRADED`

## 6. 数据模型草案

### 6.1 ProviderConfig
- `llm_provider`：enum[`ollama`,`openai`,`mock`]
- `asr_provider`：enum[`funasr`,`openai`,`mock`]
- `tts_provider`：enum[`paddlespeech`,`openai`,`mock`]
- `llm_model`：string，默认 `deepseek-r1:8b`
- `embed_model`：string，默认 `nomic-embed-text`
- `split_model`：string，默认 `qwen3.5-2b`
- `base_url`：string，按 provider 分别配置
- `timeout_seconds`：number，默认 20
- `max_retries`：number，默认 2

### 6.2 ProviderHealth
- `provider`：string
- `status`：enum[`UP`,`DOWN`,`DEGRADED`]
- `latency_ms`：number，选填
- `error_message`：string，选填

### 6.3 InterviewTurn 增强字段
- `asr_provider`
- `llm_provider`
- `tts_provider`
- `degrade_flags`
- `trace_id`
- `latency_ms`
- `generation_mode`：enum[`local_ai`,`fallback_template`,`mock`]

### 6.4 数据生命周期
- 音频仅在必要期间保留，完成识别后可配置清理。
- 检索索引和模型元数据保留，用于复现与调试。
- 每轮面试保留 provider 轨迹，方便后续排障。

## 7. 前端交互与状态约束

### 7.1 页面展示
- 面试页面必须显示当前 provider 状态。
- 当系统运行在本地 AI 模式时，显式标记“本地 AI”。
- 当发生降级时，标记“兜底模板”。

### 7.2 错误提示
- FunASR 不可用时，提示用户切换文本输入。
- PaddleSpeech 不可用时，允许继续文本输出。
- DeepSeek / Ollama 不可用时，提示当前进入模板兜底，不应隐藏。

### 7.3 兼容性
- 桌面端 Chromium 浏览器优先。
- 前端与后端的 provider 状态需实时同步或轮询同步。

## 8. 非功能需求

### 8.1 性能
- 单轮问答总响应目标：P95 <= 5 秒（本地推理场景下可接受略高于云端，但需稳定）。
- ASR / TTS 单次调用应有超时保护。

### 8.2 可用性
- 任一 provider 不可用时，应明确降级，不得静默失败。
- 本地服务启动后应能通过 health check 自动发现异常。

### 8.3 安全
- 默认模式不要求外部 API Key。
- 不在日志中输出明文音频内容、密钥或完整简历原文。
- 本地服务地址和端口需支持环境变量配置。

### 8.4 可观测性
- 每次调用必须记录 provider 名称、耗时、降级标记。
- 需输出面试链路日志，便于定位“为什么走兜底”。

### 8.5 可部署性
- 支持本机一键启动。
- 支持本地离线演示。
- 支持模型下载失败时给出明确提示。

## 9. 验收标准

### 9.1 正常流
- Given 已配置本地服务且 Ollama / FunASR / PaddleSpeech 可用
- When 用户上传简历并进入面试，提交一轮回答
- Then 后端返回的 `pipeline_meta.providers` 中对应 provider 不是 `mock`
- And `generation_mode` 应为 `local_ai`
- And 返回题目内容应来自本地 LLM 生成，而非固定模板

### 9.2 ASR 验收
- Given 用户使用语音输入
- When FunASR 服务可用
- Then 系统返回识别文本并继续面试
- And `asr_provider` 标识为 `funasr`

### 9.3 LLM 验收
- Given Ollama 与 DeepSeek 可用
- When 用户完成自我介绍后进入技术追问
- Then 下一问由本地 LLM 生成
- And 连续三轮问题不应完全相同

### 9.4 TTS 验收
- Given 用户选择语音输出
- When PaddleSpeech 服务可用
- Then 返回可播放音频地址或音频内容
- And `tts_provider` 标识为 `paddlespeech`

### 9.5 降级验收
- Given 某个本地 provider 不可用
- When 用户继续面试
- Then 系统必须明确显示降级状态
- And 不得把 `mock` 误标为本地 AI 成功

### 9.6 配置验收
- Given 本地模式默认启用
- When 用户未配置 OpenAI API Key
- Then 本地模式仍可启动并工作
- And 不会因为缺少 OpenAI Key 阻断本地模型链路

## 10. 风险与待确认项

### 10.1 风险
1. **模型体积与启动成本高**
   - 影响：首次启动慢、磁盘占用高、内存压力大。
2. **不同平台兼容性**
   - 影响：macOS / Linux / x86 / ARM 表现可能不同。
3. **本地服务协议未统一**
   - 影响：FunASR / PaddleSpeech / Ollama 的对接需要适配层。
4. **DeepSeek 输出稳定性**
   - 影响：生成问题可能需要 prompt 约束与后处理。
5. **离线部署路径复杂**
   - 影响：本机可运行，但团队成员机器环境不一致。

### 10.2 待确认项
1. FunASR 与 PaddleSpeech 采用“本地进程调用”还是“本地 HTTP 服务调用”。
   - 影响范围：后端 provider 适配层、启动脚本、健康检查。
2. Ollama 模型列表是否固定为 `deepseek-r1:8b / qwen3.5-2b / nomic-embed-text`。
   - 影响范围：模型下载脚本、文档、默认配置。
3. 是否保留 OpenAI 作为显式可选 fallback。
   - 影响范围：配置系统、健康检查、兜底策略、测试矩阵。
4. 音频上传/返回是否统一使用本地文件路径或 base64。
   - 影响范围：前端播放逻辑、后端存储策略。

## 11. 落盘信息

- 目标路径：`devdocs/agent1-local-model-integration-prd.md`
- 文档状态：已创建
- 适用角色：Agent 1（需求与接口设计）
- 供后续 Agent 2 作为改造计划输入
