# PRD：Chroma 知识库重建（Agent 1）

## 1. 需求摘要

### 1.1 背景
- 当前知识检索链路存在高风险：
- 运行时未稳定使用 Chroma 语义检索，存在 JSONL 关键词回退路径。
- 向量生成使用 64 维 Hashing Trick，不具备可靠语义表达能力。
- 分块粒度不均，存在过短与过长 chunk，影响召回与回答可读性。

### 1.2 目标
- 按指定链路重建知识索引：
- 文本分割：`qwen3.5-2b`（Ollama）。
- 文本嵌入：`nomic-embed-text`（Ollama）。
- 存储：Chroma 持久化。
- 输出可复用、可幂等、可回滚的构建流程，并提升语义检索准确率与稳定性。

### 1.3 成功标准
- 重建后运行时默认走 Chroma 检索，不依赖 JSONL 回退。
- 语义检索评测集达到发布门槛：`Hit@3 >= 0.75`、`MRR >= 0.60`。
- 构建脚本支持 `--dry-run`、增量/全量、失败重试与构建报告。

### 1.4 决策冻结（本 PRD 直接生效）
- 分块策略：规则优先 + LLM 辅助；固定 `qwen3.5-2b`、`temperature=0`。
- 分块阈值：`min_chars=200`、`max_chars=1200`、`overlap_chars=120`。
- 嵌入策略：固定 `nomic-embed-text`，按批次 `batch_size=32` 生成向量。
- 存储策略：版本化 collection（`kb_{role}_v{n}`），禁止写入旧版本 collection。
- 回退策略：禁止静默回退；仅允许“显式降级模式”且必须返回 `retrieval_mode=fallback`。
- 发布门槛：每岗位评测样本不少于 `80`，且满足 `Hit@3 >= 0.75`、`MRR >= 0.60`、回退触发率 `< 0.1%`。

## 2. 范围定义（In Scope / Out of Scope）

### 2.1 In Scope
- 重建离线知识索引构建链路（分块、嵌入、入库、报告）。
- 按岗位（`java`、`web`）重建 Chroma collection。
- 为检索服务补齐运行时依赖校验与降级策略（可观测、可告警）。
- 建立最小评测集与离线检索指标（Hit@k、MRR、召回覆盖率）。
- 更新接口文档与调试集合（涉及导入触发接口行为变更时）。

### 2.2 Out of Scope
- 题库（question bank）数据结构与评分逻辑改造。
- 新岗位数据源接入。
- 在线 rerank、混合检索（BM25+Vector）等增强方案。

## 3. 接口定义（OpenAPI 风格草案）

### 3.1 管理端触发重建
- `POST /api/v1/admin/imports/materials`
- 说明：
- 保留现有入口，内部切换为新链路。
- 鉴权：`Bearer admin-token`
- 幂等：请求头 `X-Idempotency-Key`（同 key 在 TTL 内重复提交返回同一任务）

请求示例：
```json
{
  "rebuild_mode": "full",
  "roles": ["java", "web"],
  "chunker": {
    "provider": "ollama",
    "model": "qwen3.5-2b"
  },
  "embedder": {
    "provider": "ollama",
    "model": "nomic-embed-text"
  }
}
```

响应示例（异步）：
```json
{
  "status": "ACCEPTED",
  "task_id": "kb_build_20260406_220000",
  "report_path": "backend/assets/data/reports/knowledge_vectorstore_build_report.json"
}
```

### 3.2 查询构建任务状态（新增）
- `GET /api/v1/admin/imports/materials/{task_id}`

响应示例：
```json
{
  "task_id": "kb_build_20260406_220000",
  "status": "RUNNING",
  "stage": "embedding",
  "progress": 0.64,
  "roles": {
    "java": {"total_chunks": 240, "embedded": 190},
    "web": {"total_chunks": 238, "embedded": 112}
  },
  "last_error": ""
}
```

### 3.3 错误码
- `KB_BUILD_400`：参数非法（模型名、角色、模式）。
- `KB_BUILD_409`：已有同类构建任务进行中。
- `KB_BUILD_502`：Ollama 服务不可用/超时。
- `KB_BUILD_500`：Chroma 写入失败。
- `KB_BUILD_424`：依赖未满足（如缺少 `chromadb`）。

## 4. 数据模型草案

### 4.1 ChunkRecord（规范化分块中间产物）
- `chunk_id`: string，稳定主键（`role+source_path+section_path+ordinal` 哈希）。
- `role`: enum[`java`,`web`]，必填。
- `source_path`: string，必填。
- `section_path`: string，必填（标题层级路径）。
- `chunk_no`: int，必填。
- `content`: string，必填。
- `chunk_tokens`: int，必填。
- `chunk_chars`: int，必填。
- `updated_at`: datetime，必填。

### 4.2 VectorRecord（向量写入 Chroma）
- `id`: string，等于 `chunk_id`。
- `document`: string，等于 `content`。
- `embedding`: float[]，由 `nomic-embed-text` 生成。
- `metadata`: object，必填字段：
- `role`, `source_path`, `section_path`, `chunk_no`, `updated_at`, `embedding_model`, `chunk_model`.

### 4.3 BuildReport（构建报告）
- `task_id`: string，必填。
- `started_at` / `finished_at`: datetime，必填。
- `mode`: enum[`full`,`incremental`]。
- `roles`: object（每岗位统计）。
- `quality`: object（长度分布、异常块数、空块数、重复块数）。
- `retrieval_eval`: object（Hit@1/3/5、MRR、样本数）。
- `status`: enum[`SUCCESS`,`FAILED`,`PARTIAL_SUCCESS`]。
- `errors`: string[]。

## 5. 前端交互与状态约束

### 5.1 管理端页面
- 导入页需展示：
- 当前构建任务状态（运行中/失败/完成）。
- 最近一次构建报告摘要（质量与评测指标）。
- 失败时可“一键重试上次参数”。

### 5.2 状态约束
- 同一时间仅允许一个全量构建任务。
- 增量构建允许排队，不允许并发写同一 collection。
- 构建失败不覆盖现网“最后一次成功版本”的索引引用。

## 6. 非功能需求（性能/安全/可观测性/可用性）

### 6.1 性能
- 全量重建（`java+web`，约 500 chunk 级别）目标：P95 < 10 分钟（开发机基线）。
- 单批嵌入请求固定 `batch_size=32`；超过内存水位时降至 `16` 并记录告警。

### 6.2 安全
- 管理端接口仅管理员可用。
- 构建日志不输出完整原文内容，默认脱敏（路径与统计可见）。

### 6.3 可观测性
- 指标：
- `kb_build_duration_seconds`
- `kb_build_failed_total`
- `kb_embed_request_latency_ms`
- `kb_retrieval_hit_at_3`
- 日志（中文）：
- 每阶段开始/结束、重试、失败原因、任务号。

### 6.4 可用性
- 依赖不可用（Ollama/Chroma）时快速失败并返回可操作错误。
- 保留“最后一次成功构建版本”的读路径，避免构建失败影响线上检索。

## 7. 验收标准（Given-When-Then）

### AC-01 构建可执行
- Given 管理员触发全量重建。
- When 任务执行完成。
- Then `java`、`web` collection 均成功写入，报告状态为 `SUCCESS`。

### AC-02 语义检索有效
- Given 固定评测集（每岗位不少于 80 条语义改写查询，覆盖口语问法、同义改写、跨主题复合问）。
- When 执行离线评测。
- Then 必须满足 `Hit@3 >= 0.75`、`MRR >= 0.60`，且相对旧链路至少提升 `10%`。

### AC-03 运行时依赖校验
- Given 服务启动时缺失 `chromadb` 或 Ollama 不可用。
- When 执行健康检查与首次检索。
- Then 明确返回依赖错误并告警，禁止静默降级为无语义能力模式。

### AC-04 幂等与可回滚
- Given 同一参数重复提交构建任务。
- When 请求携带相同 `X-Idempotency-Key`。
- Then 返回同一任务引用；失败后可基于最近成功版本回滚。

### AC-05 报告完整性
- Given 任意一次构建结束。
- When 查询构建报告。
- Then 报告包含数据量、质量统计、评测结果、错误明细与版本信息。

### AC-06 回退与可观测门禁
- Given 系统运行在生产模式。
- When 发生语义检索依赖故障。
- Then 不得静默切换为关键词模式；必须返回依赖错误并触发告警，回退触发率必须低于 `0.1%`。

## 8. 风险闭环（已决策并要求落地）

### P0
- 风险 R1：`qwen3.5-2b` 分块输出漂移（状态：已决策）
- 含义：同一输入多次构建得到不同 chunk 边界，导致索引版本不可比。
- 成因：仅依赖自然语言提示做 LLM 分块，参数或上下文轻微变化会引起结果漂移。
- 影响：评测不可重复、召回结果波动、回归难定位。
- 解决决策：
- 强制采用“规则优先 + LLM 辅助”分块策略。
- 强制固定参数：`temperature=0`、`min_chars=200`、`max_chars=1200`、`overlap_chars=120`。
- 构建报告必须输出 chunk 签名与漂移率；漂移率 > `1%` 判定构建失败。

- 风险 R2：`nomic-embed-text` 与现存 Chroma collection 维度冲突（状态：已决策）
- 含义：新向量无法安全写入旧 collection。
- 成因：collection 维度由首批写入向量锁定，旧链路为 64 维哈希向量，新模型维度不同。
- 影响：构建失败或查询异常，线上可用性受损。
- 解决决策：
- 仅允许写入新版本 collection（`kb_{role}_v{n}`），禁止对旧 collection 混写。
- 上线采用“构建成功后切指针”方式发布；失败自动保留旧版本。
- 任务执行前必须通过维度一致性检查，失败立即中止并告警。

### P1
- 风险 R3：Ollama 运行资源差异导致构建时长/稳定性波动（状态：已决策）
- 含义：不同环境的构建耗时与成功率不稳定。
- 成因：CPU/内存/模型冷启动/并发参数差异，导致分块与嵌入吞吐变化明显。
- 影响：任务超时、失败重试频发、环境间结果不一致。
- 解决决策：
- 固定 `batch_size=32`（资源紧张自动降到 `16`），并记录降级日志。
- 强制实现 checkpoint 断点续跑与分阶段重试。
- 构建任务异步化，必须提供任务进度查询接口。
- 生产环境构建节点规格固定，禁止临时混用低配节点。

- 风险 R4：检索回退策略不清晰（静默回退掩盖故障，状态：已决策）
- 含义：系统看似可用，但实际已退化为关键词检索。
- 成因：语义链路异常时自动走 JSONL 回退，缺少强告警与门禁。
- 影响：检索质量显著下降但不易被发现，线上结果不可控。
- 解决决策：
- 生产模式默认禁止静默回退。
- 临时降级必须显式返回 `retrieval_mode=fallback` 且触发告警。
- 回退触发率阈值固定为 `< 0.1%`，超阈值阻断发布。

### P2
- 风险 R5：评测集覆盖不足导致指标失真（状态：已决策）
- 含义：离线分数高但线上真实检索体验不稳定。
- 成因：评测样本偏“标准问法”，缺少口语化、同义改写、跨主题复合问题。
- 影响：质量被高估，发布后暴露长尾召回问题。
- 解决决策：
- 评测集版本化并扩充到每岗位不少于 `80` 条。
- 样本必须覆盖：术语改写、口语问法、错别字、跨主题复合问。
- 每次构建必须输出失败样本 Top20 并进入复盘清单。

## 9. 可交接物与 DoD

### 9.1 可交接物
- 本 PRD 文档（Agent 2 可直接引用）。
- 统一构建任务契约草案（请求/响应/状态/错误码）。
- 数据模型草案（ChunkRecord、VectorRecord、BuildReport）。
- 验收标准与风险清单。

### 9.2 完成定义（DoD）
- 需求边界清晰，In/Out 明确。
- 接口契约可直接进入改动计划与实现拆分。
- AC 可直接转换为 Agent 4 测试用例。
- 风险项均有影响说明且可追踪。

## 10. 落盘信息

- 目标路径：`devdocs/PRD-chroma-rebuild-agent1.md`
- 角色：Agent 1（需求与接口设计）
- 关联输入：本轮 Chroma 构建链路 review 结论
