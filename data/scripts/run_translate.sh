#!/usr/bin/env bash
set -euo pipefail

# 翻译入口包装：将英文选择题翻译为中文，并输出报告。
rtk python data/scripts/translate_practice_questions.py "$@"
