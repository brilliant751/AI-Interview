# data/scripts 说明

本目录统一存放本次翻译链路的数据转换脚本与可执行入口，避免执行命令分散在多个目录。

## 脚本清单

- `translate_practice_questions.py`
  - 英文选择题翻译脚本（核心实现）。
- `run_translate.sh`
  - 翻译包装入口，透传参数到 `translate_practice_questions.py`。
- `run_import.sh`
  - 导入包装入口，透传参数到 `backend/assets/scripts/data/import_choice_questions.py`。

## 典型执行

```bash
# 1) 从 SQLite 导出英文并翻译为中文
rtk data/scripts/run_translate.sh \
  --input-sqlite data/sqlite/interview.db \
  --export-raw-json data/raw/practice_choice_questions_en.json \
  --output-json data/converted/practice_choice_questions_zh.json \
  --report-json data/reports/translation_report.json

# 2) 将中文转换结果导入数据库（幂等 upsert）
rtk data/scripts/run_import.sh \
  --input data/converted/practice_choice_questions_zh.json \
  --db-path backend/assets/data/sqlite/interview.db \
  --report data/reports/practice_choice_question_import_report.json
```

## 可追溯性约定

- 翻译输入原始数据统一落在 `data/raw/`。
- 翻译输出统一落在 `data/converted/`。
- 执行报告统一落在 `data/reports/`。
