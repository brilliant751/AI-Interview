# 数据流水线运行手册

本文档说明 AI-Interview 项目中材料校验、题库导入、知识库构建和选择题翻译的运行方式。文档仅记录现有流程，不改变代码行为。

## 1. 数据目录

主要目录：

- `material/`：人工维护的原始面试材料。
- `data/normalized/`：规范化后的 JSONL。
- `data/sqlite/`：SQLite 数据库。
- `data/chroma/`：本地向量索引或 Chroma 数据。
- `data/reports/`：脚本运行报告。
- `data/converted/`：翻译或重建后的中间产物。

脚本目录：

- `scripts/data/validate_materials.py`
- `scripts/data/normalize_materials.py`
- `scripts/data/build_question_bank.py`
- `scripts/data/build_knowledge_vectorstore.py`
- `scripts/data/embeddings.py`
- `data/scripts/translate_practice_questions.py`
- `data/scripts/rebuild_choice_questions_cn.py`

## 2. 推荐流水线顺序

推荐顺序：

1. 校验材料。
2. 规范化材料。
3. 构建题库。
4. 构建知识库向量索引。
5. 检查报告。
6. 启动后端验证接口。

对应命令示例：

```bash
python scripts/data/validate_materials.py --strict
python scripts/data/normalize_materials.py
python scripts/data/build_question_bank.py
python scripts/data/build_knowledge_vectorstore.py
```

如果只是检查影响，不希望写文件，可以使用 dry-run：

```bash
python scripts/data/normalize_materials.py --dry-run
python scripts/data/build_question_bank.py --dry-run
python scripts/data/build_knowledge_vectorstore.py --dry-run
```

## 3. validate_materials

用途：

- 检查题库材料是否能识别“第 X 题”。
- 检查题库是否包含“题干”和“解析”。
- 检查知识材料是否包含标题。
- 输出可追溯报告。

输出：

- 默认：`data/reports/material_validation_report.json`

常见问题：

- `QUESTION_NOT_FOUND`：题库文件缺少题号结构。
- `MISSING_PROMPT_SECTION`：缺少题干字段。
- `MISSING_ANALYSIS_SECTION`：缺少解析字段。
- `HEADING_NOT_FOUND`：知识库材料缺少标题结构。
- `EMPTY_FILE`：材料文件为空。

处理建议：

- 题库文件应使用 `## 第 1 题：标题` 或 `### 第 1 题：标题`。
- 题目正文建议包含 `题干`、`类别`、`解析`。
- 知识库文件应使用 Markdown 标题组织段落。

## 4. normalize_materials

用途：

- 将 Markdown 材料转换为 JSONL。
- 题库材料输出为 `*_question_bank.jsonl`。
- 知识材料输出为 `*_knowledge.jsonl`。

默认输出：

- `data/normalized/java_question_bank.jsonl`
- `data/normalized/java_knowledge.jsonl`
- `data/normalized/web_question_bank.jsonl`
- `data/normalized/web_knowledge.jsonl`

核心规则：

- 题库按“第 X 题”切分。
- 题干、类别、解析按标题提取。
- 知识库按标题和正文切片。
- record_id 使用 stable_id，重复执行保持稳定。

注意事项：

- 如果题干缺失，脚本可能使用标题或原文兜底。
- 如果解析缺失，导入后的 analysis 可能为空。
- 如果材料标题层级混乱，切分可能不符合预期。

## 5. build_question_bank

用途：

- 将规范化题库 JSONL 导入 SQLite。
- 初始化 `question_bank` 表。
- 支持重复执行和 upsert。

默认输入：

- `data/normalized/*_question_bank.jsonl`

默认输出：

- `data/sqlite/interview.db`
- `data/reports/question_bank_build_report.json`

报告字段：

- `total_rows`
- `inserted_or_updated`
- `failed`
- `dry_run`

注意事项：

- 如果 failed 大于 0，需要检查 JSONL 中是否有缺失字段。
- dry-run 不会写数据库。
- upsert 以 `record_id` 为主键。

## 6. build_knowledge_vectorstore

用途：

- 将规范化知识库 JSONL 构建为可检索索引。
- 优先写 JSONL 索引。
- 如果安装 Chroma，也写入 Chroma collection。

默认输入：

- `data/normalized/*_knowledge.jsonl`

默认输出：

- `data/chroma/kb_java/knowledge_index.jsonl`
- `data/chroma/kb_web/knowledge_index.jsonl`
- `data/reports/knowledge_vectorstore_build_report.json`

Embedding 来源：

- Ollama embedding。
- hash fallback。

报告字段：

- `total_rows`
- `written_rows`
- `dimension`
- `roles`
- `embedding_providers`
- `dry_run`

注意事项：

- 如果 `embedding_providers.hash_fallback` 很高，说明 Ollama 不可用或调用失败。
- hash fallback 可以保证流程可运行，但语义检索质量不如真实 embedding。
- Chroma 缺失时脚本仍应写 JSONL 索引。

## 7. 选择题翻译脚本

`data/scripts/translate_practice_questions.py` 用于把英文选择题翻译为中文。

输入方式：

- SQLite 表 `practice_choice_questions`
- JSON 数组文件

输出：

- 翻译后的 JSON。
- 翻译报告 JSON。

依赖：

- `ctranslate2`
- `sentencepiece`
- `huggingface_hub`

注意事项：

- 该脚本使用本地模型，不依赖在线翻译服务。
- 首次运行可能需要下载模型。
- dry-run 可用于估算翻译量。

## 8. 可靠来源题库重建脚本

`data/scripts/rebuild_choice_questions_cn.py` 用于从可靠来源题库重建中文选择题。

核心规则：

- 判断文本是否主要为英文。
- 只翻译英文文本。
- 保留已有中文文本。
- 保留选项 key。
- 输出重建报告。

依赖：

- `argostranslate`

注意事项：

- 如果 Argos en->zh 包未安装，脚本会尝试安装或提示错误。
- 判断英文采用字符比例，规则偏保守。
- 不建议对已经人工校对过的中文题目再次批量翻译。

## 9. 管理端导入接口

管理端页面会触发材料导入任务：

- `/admin/imports/materials`
- `/practice/questions/upload`
- `/practice/questions`

这些接口不直接阻塞等待脚本完成，而是返回任务 ID。

前端应轮询任务状态：

- `PENDING`
- `RUNNING`
- `SUCCESS`
- `FAILED`
- `PARTIAL_SUCCESS`

终态后停止轮询。

## 10. 常见故障

### 10.1 题库为空

可能原因：

- normalize 没有生成 question_bank JSONL。
- build_question_bank 输入目录不正确。
- 材料文件缺少“第 X 题”标题。
- 导入报告中 failed 大于 0。

排查：

```bash
ls data/normalized
cat data/reports/question_bank_build_report.json
```

### 10.2 知识库检索失败

可能原因：

- Chroma 目录为空。
- alias 或 collection 不存在。
- 没有构建对应岗位的知识索引。
- fallback 关闭。

排查：

```bash
cat data/reports/knowledge_vectorstore_build_report.json
find data/chroma -maxdepth 3 -type f
```

### 10.3 导入任务一直 RUNNING

可能原因：

- 后台脚本卡住。
- 本地模型调用无响应。
- 大文件处理时间较长。
- 任务状态没有被正确回写。

排查：

- 查看后端日志。
- 查看任务 last_error。
- 查看 report_path。
- 用 dry-run 单独执行脚本。

### 10.4 翻译结果不理想

可能原因：

- 本地翻译模型质量有限。
- 技术词被错误翻译。
- 混合中英文判断不准确。

处理：

- 保留英文技术词。
- 对重点题目人工校对。
- 使用 report 中的统计字段定位翻译字段。

## 11. 提交数据变更建议

如果提交材料或数据脚本结果，建议同时提交：

- 原始材料变更。
- normalized 输出。
- 构建报告。
- 数据库迁移或导入说明。

不建议提交：

- 本地临时日志。
- 大模型缓存。
- 无关 Chroma 二进制缓存。
- 开发机绝对路径。

## 12. 安全注意事项

材料和报告中可能包含：

- 简历内容。
- 公司岗位描述。
- 面试回答。
- 模型生成评估。

提交前应检查是否包含真实个人隐私数据。

