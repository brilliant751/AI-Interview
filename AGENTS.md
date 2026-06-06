# Repository Guidelines

## General

### Basic Rules

- 不要改动未指定的业务代码

### Coding

- 根据现有代码，保持代码风格
- 可复用的代码抽象成方法
- 类内可复用的方法抽象成类内的工具方法
- 跨类可复用的方法抽象成utils/下的全局工具方法
- 每个方法级函数或对象都要添加注释，采用对应语言的主流标准格式，可省略param和return
- 新增或修改函数、类等对象时必须要对应更新注释
- 在记录日志时，除了专有名词可以用英文缩写，其他内容全部用中文


## Additional

## Post Coding

- 每次如果有新的接口添加，或有接口经过任何改动，都需要同步更新对应的 API 集合与文档（如 Postman Collection / OpenAPI，缺失时需创建）
- 接口文档文件需保持官方支持的标准 JSON/YAML 格式

## URGENT.md

- 在项目根目录维护一个 `URGENT.md` 文档
- 用于记录短周期内迫切需要完成的需求
- 由agent5维护
- Agent5 每次完成 review 后，必须同步更新 `URGENT.md`
- 更新 `URGENT.md` 时必须执行以下动作：
  - 核对现有 urgent 条目，已落地项必须删除
  - 未完全落地项必须根据当前实现状态更新描述与验收标准
  - 新发现的 urgent 需求必须新增，并按紧急程度评级（`P0`/`P1`/`P2`）
- `URGENT.md` 必须保持“仅含当前未完成 urgent 事项”，不得粘贴整份评审报告

## Material 数据源约定

- 岗位材料统一放在 `backend/assets/material/` 目录，并按岗位拆分子目录。
- 当前材料位置：
  - Java 题库：`backend/assets/material/java/java-interview/`
  - Java 知识库：`backend/assets/material/java/java-knowledge/`
  - Web 题库：`backend/assets/material/web/interview.md`
  - Web 知识库：`backend/assets/material/web/knowledge.md`
  - 编程练习题库：`backend/assets/material/coding/programming_practice_questions.json`
- 任何 Agent 规划/实现“题库导入、知识库向量化、检索构建”任务时，必须以上述路径为唯一输入来源，若新增来源需先在本文件登记。
- 数据导入必须提供可复用脚本（支持重复执行、幂等、失败重试、校验报告），禁止仅通过一次性手工导入完成交付。

## Multi-Agent Workflow

### Goal

- 采用 5 个固定 Agent 的协作模式，覆盖需求、设计、前后端实现、数据与基础设施、测试、评审全链路，确保过程可追踪、可交接、可复用。

### Prompt Location

- 5 个 Agent 的通用提示词模板统一存放在 `prompts/agents/` 目录。
- 每个新 thread 开始时，必须先注入对应 Agent 的角色提示词，再下发具体任务。
- 角色提示词负责“身份与职责对齐”；本 `AGENTS.md` 负责“项目共性规则约束”。

### Agent Startup Protocol

- 每个 Agent 在确认自身身份后，必须先主动阅读 `prompts/agents/` 下对应模板，再开始任何执行动作。
- 模板映射关系如下：
  - Agent 1 -> `prompts/agents/agent1-requirement-interface.md`
  - Agent 2 -> `prompts/agents/agent2-change-plan.md`
  - Agent 3 -> `prompts/agents/agent3-implementation.md`
  - Agent 4 -> `prompts/agents/agent4-testing-qa.md`
  - Agent 5 -> `prompts/agents/agent5-review-architecture.md`
- 若角色与模板不匹配，或模板缺失，当前 Agent 不得开始工作，需先修复模板映射。
- Agent 开工前需完成模板适配自检（最小检查集）：
  - 是否明确角色目标与边界（做什么/不做什么）
  - 是否明确输入、输出格式与 DoD
  - 是否明确上下游依赖与门禁（特别是 Agent 2 -> Agent 3 的 `LATEST.md` 约束）
  - 是否与本仓库通用规则冲突（注释、日志语言、接口变更后文档更新等）
- 若模板不满足上述检查项，Agent 需先补齐模板再执行任务。

### Agent Roles

- Agent 1：需求与接口设计 Agent  
  负责需求澄清、边界定义、跨端交互与接口契约、数据模型草案、非功能需求与验收标准（AC）。
- Agent 2：代码改动规划 Agent  
  负责输出全栈改动计划（前端/后端/数据/基建）、关键流程设计、实施顺序、发布与回滚策略。
- Agent 3：开发实现 Agent  
  负责严格按 Agent 2 计划实现代码与配置（含前端、后端、数据与基础设施相关实现），并记录与计划差异。
- Agent 4：测试与质量 Agent  
  负责基于 AC 设计并执行分层测试（单元/集成/端到端/回归/非功能），输出缺陷分级与放行结论。
- Agent 5：评审与架构守卫 Agent  
  负责最终审查正确性、安全性、性能、可维护性与架构一致性，并给出准入意见。

- Agent 1 的产出必须是 Markdown 文件，并落盘到 `devdocs/` 目录。
- Agent 2 的产出必须是 Markdown 文件，并落盘到 `.ai-workspace/` 目录。
- Agent 2 每次产出后必须同步更新 `.ai-workspace/LATEST.md`，用于声明最新可执行计划文件。
- Agent 3 只能基于 `.ai-workspace/` 下由 Agent 2 最新产出的“新需求改动计划”执行代码与配置编辑。
- 若 `.ai-workspace/LATEST.md` 不存在，或其指向的计划文件不存在，Agent 3 不得开始实现。
- Agent 4 只能改动 测试文件，不得改动 业务代码。
- Agent 4 编写与维护的测试必须符合最佳实践（可读、可复现、稳定、覆盖正常/异常/边界路径）。
- Agent 4 必须自动执行测试命令并记录结果（含前端、后端、端到端与质量门禁结果，按项目实际适用）。
- Agent 4 在执行前端端到端测试时，必须直接使用 Playwright MCP 工具链执行与取证；非必要不使用本地 Playwright CLI 命令替代。
- Agent 4 目标测试覆盖率不低于 80%（若仓库已有更高门槛，以仓库门槛为准）。

### Process Gates

- 未完成 Agent 1 输出前，不允许进入 Agent 2。
- 未完成 Agent 2 输出前，不允许进入 Agent 3。
- Agent 3 不得跳过 Agent 2 计划直接实现；如需偏离，必须记录“差异原因与影响”。
- 只有 Agent 3 可以修改业务与实现相关代码/配置（测试代码除外）。
- Agent 4 在提交测试结论前必须完成“编写或更新测试 + 自动执行”。
- Agent 4 的测试结论与 Agent 5 的评审结论，作为是否合并的最终依据。
- Agent 5 在输出最终评审结论前，必须完成 `URGENT.md` 的核对与更新；未更新不得给出最终放行意见。

### Deliverables

- 每个 Agent 的输出必须包含：可交接物、完成定义（DoD）、风险与待确认项（如有）。
- 接口有新增或修改时，除代码变更外，仍必须同步更新对应接口文档与调试集合，并保证内容可导入、可校验、可追溯。
