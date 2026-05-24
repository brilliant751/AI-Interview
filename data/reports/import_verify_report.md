# 导入核验报告（任务3）

- 时间：2026-05-23
- 中文归档：`data/converted/practice_choice_questions_zh.json`
- 英文归档：`data/raw/practice_choice_questions_en.json`
- 目标数据库：`backend/assets/data/sqlite/interview.db`

## 一、导入前验证

1. JSON 格式合法：通过（可解析为 JSON 数组）
2. 条数与 question_id 集合一致：通过
   - 中文条数：92
   - 英文条数：92
   - `question_id` 缺失：0
   - `question_id` 额外：0
3. `options` 字段可解析：通过（异常 0 条）
4. 中文 stem 抽样（启发式：`stem != 英文原文` 且包含中文字符）
   - 可用于抽样的数据量：71 条
   - 抽样 10 条：全部满足

补充观察（不阻断导入）：发现 21 条 stem 文本存在明显质量异常（如 `* * * * * *` 或重复噪声），建议后续单独修复翻译数据。

## 二、执行导入（upsert 覆盖）

执行命令：

```bash
rtk proxy python backend/assets/scripts/data/import_choice_questions.py \
  --input data/converted/practice_choice_questions_zh.json \
  --db-path backend/assets/data/sqlite/interview.db \
  --report data/reports/practice_choice_question_import_report.json
```

导入结果：

- 加载记录：92
- upsert：92
- skipped：0

## 三、导入后核验

1. 表总条数：92（通过）
2. 抽样 5 条中文 stem（通过）

| question_id | stem（截断） |
|---|---|
| 02ab4711db257b156b93cf3df029ba88ef843b3a | 我们能用哪一座建筑工能成功扩展“ dog” 类? ? 以哪一座建筑工能成功扩展“ dog” 类的“ dog” 类? ? |
| 043fb9c40e99fda16d809c84060773e40ff9b232 | 以下哪一项或哪项没有汇编? ? |
| 0d5afde5388beaecf912c3f47c67b90c9e71f085 | 麻麻? 麻麻? |
| 0f7610be94750fbe9d428cbaadadc9353e4fc6da | 哪一个是真实的呢?哪一个是真实的呢?哪一个是真实的呢?哪一个是真实的呢?哪一个是真实的呢?哪一是真实的呢? |
| 0fd56515de424a71416c8b9a55852b7f19f5ff34 | 如何强迫垃圾收集工作在某一时刻发生? 如何强迫垃圾收集工作在某一时刻发生? |

## 四、结论

本次任务要求的“验证通过后导入覆盖数据库”已完成，导入后结构与条数核验通过，且可抽样到中文 stem。
