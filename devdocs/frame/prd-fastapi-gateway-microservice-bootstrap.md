# PRD：FastAPI 网关与基础微服务骨架（Agent1）

## 1. 需求摘要

### 1.1 背景与目标
- 主要目标：搭建 FastAPI 网关与基础微服务目录结构，包含健康检查与配置加载能力。
- 次要目标：提出服务间调用规范（请求超时、重试、错误码映射）与日志规范；规范落地实现由 Agent3 执行。
- 对齐任务来源：`plan/TASK.md` 中“后端架构”模块 `P0` 条目。

### 1.2 成功标准（本阶段）
- 完成网关与两个基础微服务（`auth`、`user`）骨架目录定义。
- 明确统一响应体格式并作为网关/服务接口基线。
- 明确健康检查、配置加载、日志输出规范与最低验收标准。

## 2. 范围定义（In/Out）

### 2.1 In Scope
- FastAPI 网关服务基础结构设计。
- `services/auth` 与 `services/user` 基础结构设计（代码放置于 `<service_name>/src`）。
- 统一返回体协议定义：

```json
{
  "code": 200,
  "message": "ok",
  "data": {}
}
```

- 健康检查接口定义（网关 + 两个服务）。
- 配置加载方案定义（`.env` + 环境变量，类型校验）。
- 日志规范定义（级别、格式、输出位置、字段约定）。
- 服务间调用规范提议（超时、重试、错误码映射）。

### 2.2 Out of Scope
- 具体业务接口（注册、登录、用户信息 CRUD）实现。
- 数据库表结构与迁移脚本实现。
- 服务调用重试与熔断代码实现（由 Agent3 在实现阶段完成）。
- 可观测系统（ELK/Prometheus/Tracing）部署实现。

## 3. 接口定义（OpenAPI 风格草案）

## 3.1 统一响应体模型

### 3.1.1 `ApiResponse<T>`
- `code: int`：业务状态码（与 HTTP 状态码同语义分层，取值范围 2xx/3xx/4xx/5xx）。
- `message: str`：说明信息。
- `data: T | null`：业务数据。

### 3.1.2 状态码约定
- 成功：`code=200`（HTTP 200）。
- 参数错误：`code=400`（HTTP 400）。
- 未认证：`code=401`（HTTP 401）。
- 无权限：`code=403`（HTTP 403）。
- 资源不存在：`code=404`（HTTP 404）。
- 下游超时：`code=504`（HTTP 504）。
- 下游不可用/异常：`code=502`（HTTP 502）。
- 服务内部错误：`code=500`（HTTP 500）。

## 3.2 网关接口（gateway）

### 3.2.1 健康检查
- 方法与路径：`GET /health`
- 鉴权：否
- 请求参数：无
- 响应示例：

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "service": "gateway",
    "status": "up",
    "version": "0.1.0"
  }
}
```

### 3.2.2 就绪检查（可选但推荐）
- 方法与路径：`GET /ready`
- 鉴权：否
- 说明：检测关键依赖（配置加载、下游服务探测）是否可用。

## 3.3 认证服务接口（auth）

### 3.3.1 健康检查
- 方法与路径：`GET /health`
- 鉴权：否
- 响应体：遵循统一响应体。

### 3.3.2 配置自检（仅开发/测试环境）
- 方法与路径：`GET /internal/config-check`
- 鉴权：内部鉴权或仅非生产开放
- 说明：返回脱敏后的关键配置加载状态。

## 3.4 用户服务接口（user）

### 3.4.1 健康检查
- 方法与路径：`GET /health`
- 鉴权：否
- 响应体：遵循统一响应体。

### 3.4.2 配置自检（仅开发/测试环境）
- 方法与路径：`GET /internal/config-check`
- 鉴权：内部鉴权或仅非生产开放
- 说明：返回脱敏后的关键配置加载状态。

## 3.5 网关到下游错误映射规范（提议）
- 下游连接失败：映射为 `502`，`message="downstream connect error"`。
- 下游请求超时：映射为 `504`，`message="downstream timeout"`。
- 下游返回 4xx：原样透传业务语义，封装为统一响应体。
- 下游返回 5xx：网关统一映射为 `502`（可保留原始 `trace_id` 便于追踪）。

## 4. 数据模型草案

## 4.1 配置模型（每服务 `Settings`）
- `app_name: str`（必填）
- `app_env: str`（枚举：`local`/`dev`/`test`/`prod`，默认 `dev`）
- `host: str`（默认 `0.0.0.0`）
- `port: int`（必填）
- `log_level: str`（枚举：`DEBUG`/`INFO`/`WARNING`/`ERROR`，默认 `INFO`）
- `request_timeout_seconds: float`（默认 `3.0`）
- `request_retry_times: int`（默认 `2`）
- `request_retry_backoff_ms: int`（默认 `200`）

## 4.2 日志模型（结构化字段）
- `timestamp`：ISO8601 时间戳。
- `level`：日志级别。
- `service`：服务名（gateway/auth/user）。
- `env`：运行环境。
- `trace_id`：链路追踪 ID。
- `span_id`：当前调用片段 ID（可选）。
- `path`：请求路径。
- `method`：HTTP 方法。
- `status_code`：HTTP 状态码。
- `latency_ms`：耗时。
- `message`：日志信息（除专有名词外使用中文）。

## 5. 验收标准（Given-When-Then）

### AC-1 目录结构
- Given：初始化后端代码仓库
- When：执行骨架创建
- Then：存在 `services/auth/src`、`services/user/src`、`gateway/src`，且具备可启动入口

### AC-2 健康检查
- Given：网关、`auth`、`user` 服务已启动
- When：分别请求 `/health`
- Then：全部返回 HTTP 200，响应体符合统一结构，`code=200`

### AC-3 配置加载
- Given：提供合法 `.env` 与环境变量
- When：服务启动
- Then：配置加载成功并通过类型校验；缺失必填项时启动失败并输出错误日志

### AC-4 统一返回体
- Given：任一接口正常或异常返回
- When：客户端接收响应
- Then：响应均满足 `{code, message, data}` 结构

### AC-5 服务调用规范（联调验收）
- Given：网关调用下游服务
- When：出现正常、超时、5xx 三类场景
- Then：分别返回统一结构且映射符合约定（正常=200，超时=504，5xx=502）

### AC-6 日志规范
- Given：服务接收一次请求并完成响应
- When：查看控制台与文件日志
- Then：日志包含规定字段、级别正确、输出位置符合规范，日志正文除专有名词外为中文

## 6. 目录结构建议（最佳实践基线）

```text
backend/
  gateway/
    src/
      api/
      core/
      middleware/
      models/
      clients/
      main.py
    tests/
    .env.example
    requirements.txt
  services/
    auth/
      src/
        api/
        core/
        models/
        main.py
      tests/
      .env.example
      requirements.txt
    user/
      src/
        api/
        core/
        models/
        main.py
      tests/
      .env.example
      requirements.txt
  shared/
    utils/
    schemas/
    logging/
```

说明：`<service_name>/src` 为强制代码目录，测试与配置样例分离，便于 CI 与容器化。

## 7. 日志规范（提议，供 Agent3 实施）
- 日志级别：
  - `DEBUG`：本地调试细节，不进生产默认级别。
  - `INFO`：关键业务流与服务状态。
  - `WARNING`：可恢复异常与重试事件。
  - `ERROR`：请求失败、下游异常、启动失败。
- 日志格式：优先 JSON 行日志（便于采集）；开发环境可附加人类可读格式。
- 输出位置：
  - 本地开发：控制台 + `logs/<service>.log`
  - 容器环境：标准输出（stdout/stderr）为主，文件输出可选
- 字段最小集：`timestamp, level, service, trace_id, path, method, status_code, latency_ms, message`
- 内容语言：除专有名词、库名、错误类型外，日志内容使用中文。

## 8. 服务间调用规范（提议，供 Agent3 实施）
- 客户端：统一使用异步 HTTP 客户端（如 `httpx.AsyncClient`）进行服务间调用。
- 超时：默认总超时 `3s`，并细分 `connect/read/write/pool` 超时。
- 重试：仅对幂等请求重试，默认最多 `2` 次，指数退避（如 `200ms -> 400ms`）。
- 熔断与降级：本阶段可先不实现熔断器，需预留钩子（中间件/客户端包装层）。
- 错误映射：网关统一封装下游错误，不泄露内部堆栈到客户端。

## 9. 风险与待确认项（按优先级）
- `P0` 风险：`code` 字段是否严格等于 HTTP 状态码。
  - 影响：前后端错误处理分支、监控统计口径。
  - 建议：本阶段保持一致（`code == HTTP status`），减少双重语义。
- `P0` 待确认：网关聚合接口是否需要“部分成功”语义。
  - 影响：`data` 结构与错误码策略复杂度上升。
- `P1` 风险：重试策略若覆盖非幂等请求，可能导致重复写入。
  - 影响：数据一致性风险。
- `P1` 待确认：日志是否必须接入集中化系统（ELK/Loki）。
  - 影响：部署与运维成本。
- `P1` 待确认：接口变更后的 Postman 同步目标文件名存在约定冲突（`prompts/Interview-api.postman.json` 与 `prompts/sirius-api.postman.json`）。
  - 影响：交付清单不一致，可能导致评审阻塞。

## 10. 交接物与 DoD

### 可交接物
- 本 PRD 文档（可直接供 Agent2 生成改动计划）。
- 统一返回体、目录规范、日志规范、服务调用规范提议。

### 完成定义（DoD）
- 需求边界明确，接口与规范可执行。
- AC 覆盖正常流、异常流、边界路径（超时/5xx）。
- 风险与待确认项均给出影响范围。
- 文档已落盘到 `devdocs/frame/`。

## 11. 参考依据（Context7）
- `libraryId=/fastapi/fastapi`，关键词：`lifespan`, `response models`, `events best practice`
  - 结论：推荐使用 `lifespan` 管理启动/关闭生命周期；可用响应模型统一接口结构。
- `libraryId=/encode/httpx`，关键词：`timeout`, `Timeout`, `TimeoutException`
  - 结论：应显式配置细粒度超时，并对超时/连接异常分别捕获处理。
- `libraryId=/pydantic/pydantic-settings`，关键词：`BaseSettings`, `env_file`, `env_prefix`, `env_nested_delimiter`
  - 结论：配置加载建议使用 `BaseSettings` + `SettingsConfigDict`，支持 `.env`、前缀、嵌套环境变量与类型校验。

## 12. 落盘信息
- 目标路径：`devdocs/frame/prd-fastapi-gateway-microservice-bootstrap.md`
