# data 目录说明（翻译链路）

本目录用于归档本次翻译链路使用到的脚本、原始数据、转换结果、模型与报告，保证可追溯与可重跑。

## 目录结构

- `data/scripts/`
  - 数据转换脚本与统一执行入口（translate/import）。
- `data/raw/`
  - 原始输入数据。
- `data/converted/`
  - 转换后的输出数据。
- `data/reports/`
  - 运行与校验报告。
- `data/models/`
  - 翻译模型文件（如 `opus-mt-en-zh-ctranslate2`）。
- `data/sqlite/`
  - 本地 SQLite 数据文件（用于翻译输入源或核验）。
- `data/normalized/`
  - 标准化后中间数据（用于题库/知识库构建）。
- `data/chroma/`
  - 向量索引数据。

## 本次链路涉及文件

- 翻译脚本：`data/scripts/translate_practice_questions.py`
- 翻译入口：`data/scripts/run_translate.sh`
- 导入入口：`data/scripts/run_import.sh`
- 原始英文：`data/raw/practice_choice_questions_en.json`
- 中文结果：`data/converted/practice_choice_questions_zh.json`
- 翻译报告：`data/reports/translation_report.json`
- 导入报告：`data/reports/practice_choice_question_import_report.json`
- 导入核验：`data/reports/import_verify_report.md`

## 执行顺序

1. 准备依赖与模型（首次）。
2. 执行翻译，生成 `raw/`、`converted/` 与翻译报告。
3. 执行导入，将 `converted/` 导入数据库并生成导入报告。
4. 查看 `reports/` 完成核验与留档。

## 重跑命令

```bash
# 0) 安装依赖（首次）
rtk pip install -r backend/requirements.txt

# 1) 翻译（从 SQLite 导出英文并翻译）
rtk data/scripts/run_translate.sh \
  --input-sqlite data/sqlite/interview.db \
  --export-raw-json data/raw/practice_choice_questions_en.json \
  --output-json data/converted/practice_choice_questions_zh.json \
  --report-json data/reports/translation_report.json \
  --model-dir data/models/opus-mt-en-zh-ctranslate2

# 2) 可选：翻译 dry-run（仅校验输入，不写 converted）
rtk data/scripts/run_translate.sh \
  --input-json data/raw/practice_choice_questions_en.json \
  --dry-run \
  --report-json data/reports/translation_report.json

# 3) 导入（幂等 upsert）
rtk data/scripts/run_import.sh \
  --input data/converted/practice_choice_questions_zh.json \
  --db-path backend/assets/data/sqlite/interview.db \
  --report data/reports/practice_choice_question_import_report.json
```

## 追溯规则

- 不直接覆盖 `data/raw/` 与 `data/converted/` 的历史样本时，建议用时间戳文件名另存。
- 每次执行至少保留一份 `data/reports/` 报告，便于比对与审计。
