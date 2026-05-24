#!/usr/bin/env bash
set -euo pipefail

# 导入入口包装：将已转换题目导入 practice_choice_questions。
rtk proxy python backend/assets/scripts/data/import_choice_questions.py "$@"
