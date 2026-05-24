# practice_choice_questions 英文转中文工具

本工具用于将 `practice_choice_questions` 题库中的英文数据批量翻译为中文，支持从 SQLite 读取或从 JSON 文件读取。

## 安装依赖

```bash
rtk pip install -r backend/requirements.txt
```

首次运行会自动从 HuggingFace 下载 `CTranslate2` 开源模型到本地目录（默认 `data/models/opus-mt-en-zh-ctranslate2`）。

## 脚本路径

- `data/scripts/translate_practice_questions.py`

## 支持字段

- `stem`
- `options`（JSON 数组内的文本，支持字符串数组与对象数组）
- `explanation`

## 示例 1：从 SQLite 读取并翻译

```bash
rtk python data/scripts/translate_practice_questions.py \
  --input-sqlite data/sqlite/interview.db \
  --output-json data/converted/practice_choice_questions_zh.json \
  --report-json data/reports/translation_report.json \
  --export-raw-json data/raw/practice_choice_questions_en.json \
  --model-repo gaudi/opus-mt-en-zh-ctranslate2
```

## 示例 2：从 JSON 读取并 dry-run

```bash
rtk python data/scripts/translate_practice_questions.py \
  --input-json data/raw/practice_choice_questions_en.json \
  --dry-run \
  --limit 5
```

dry-run 模式下不会写入翻译后的输出 JSON，但会写入报告文件用于校验。

## 输出文件

- 英文归档：`data/raw/practice_choice_questions_en.json`（SQLite 输入模式下自动导出）
- 中文归档：`data/converted/practice_choice_questions_zh.json`
- 报告文件：`data/reports/translation_report.json`

## 常见失败排查

- `no such table: practice_choice_questions`
  - 说明输入 SQLite 文件不包含目标表，请改用正确库文件（例如 `backend/assets/data/sqlite/interview.db`）或改用 `--input-json`。
- `模型目录缺少 model.bin`
  - 说明当前模型目录不是可直接用于 CTranslate2 的模型目录，请指定包含 `model.bin`、`source.spm`、`target.spm` 的本地目录，或更换可用的模型仓库。
- `options JSON 解析失败`
  - 脚本会在错误里输出 `question_id` 和 `row_index`，可据此定位坏数据并修复 `options` 字段格式。
- 报告里 `json_non_dict_items > 0`
  - 表示输入 JSON 数组中有非对象项，脚本已跳过；建议先清洗输入文件后再正式翻译。
