# Question Bank Sources (Task 1)

## 结论概览
本次仅完成“选择题资源调研与落盘”，候选源优先来自 GitHub，且覆盖 Java/Web 两个方向，每个方向不少于 2 个来源。

- Java: `learning-zone/java-basics`, `mertsaner/java-interview-questions`
- Web: `lydiahallie/javascript-questions`, `freeCodeCamp/Developer_Quiz_Site`

详细机器可消费清单见：`question_bank_sources.json`。

## 为什么认为这些来源相对可靠
- 平台可靠性：均为 GitHub 公共仓库，具备提交历史、Issue/PR、可追溯变更。
- 可维护性：4 个来源均有相对近期更新（见 JSON `updated_at`）。
- 可用性：均可直接通过仓库文件抓取，不依赖登录或复杂反爬。
- 合规线索：Web 两个来源 License 明确（MIT / BSD-3-Clause）；Java 两个来源虽未声明 SPDX，但来源公开、结构稳定，适合先做内部技术评估。

## 潜在风险
- 版权风险：
  - `NOASSERTION`（Java 两个来源）代表未明确开源许可证，直接商用或再分发有法律不确定性。
  - **当前策略：NOASSERTION 来源仅内部评估，不可外部分发。**
- 格式风险：
  - Markdown 题目的排版可能变更（标题层级、选项标记不一致），解析规则需容错。
  - 多语言版本可能出现题号或答案解释不一致。
- 内容风险：
  - 题目可能过时（尤其语言版本演进快，如 JS/Java 新特性）。

## 抓取建议（供后续清洗入库）
- 先做“只读镜像抓取”：固定 commit SHA 作为快照，避免上游变更导致重复入库差异。
- 为每条题目记录来源字段：`source_name`、`source_url`、`source_commit`、`license`、`fetched_at`、`compliance_status`。
- 解析策略：
  - Markdown：先按题号切分，再识别选项（A/B/C/D）与答案块。
  - 结构化数据（如 freeCodeCamp 题库文件）：优先按 topic/category 字段映射到统一模型。
- 质量门禁：入库前执行去重（题干归一化 + 选项哈希）与最小完整性校验（题干、>=2 选项、答案）。
