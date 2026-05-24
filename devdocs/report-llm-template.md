# 面试报告 LLM 模板（当前生效）

## System Prompt
你是资深技术面试官与评估专家。请基于输入数据输出结构化面试报告。所有判断必须有证据，未出现证据必须标注为未验证。只输出 JSON，不要输出其他文本。

## User Payload（JSON）
```json
{
  "job_role": "<岗位方向>",
  "difficulty": "<难度>",
  "jd_text": "<JD文本截断>",
  "resume_text": "<简历文本截断>",
  "turns": [
    {
      "question_no": 1,
      "stage": "TECHNICAL",
      "question": "<题目>",
      "answer": "<回答>",
      "score": 78,
      "intent_hint": "<阶段意图提示>"
    }
  ],
  "precomputed_dimension_scores": {
    "技术深度": 4,
    "架构设计": 3,
    "工程质量": 4,
    "性能意识": 3,
    "稳定性与容错": 3,
    "安全与风控": 2,
    "业务理解": 4,
    "问题分析与取舍": 4,
    "沟通表达": 3,
    "协作推进": 3,
    "学习敏捷性": 4,
    "岗位匹配度": 4
  }
}
```

## 输出 Schema（核心）
- strengths: string[]
- weaknesses: string[]
- suggestions: string[]
- final_recommendation: string
- key_risks: string[]
- dimension_scores: [{dimension, capability_score, match_score, confidence, evidence}]
- jd_resume_alignment: [{jd_skill, priority, resume_evidence, answer_evidence, status, note}]
- question_deep_dives: [{question_no, question, intent, answer_summary, hit_rate, depth_level, resume_relevance, jd_relevance, strengths, gaps, follow_up_questions}]

## 说明
- 当前实现位置：`backend/app/services/report_service.py`
- OpenAI 结构化输出调用：`backend/app/services/providers/openai_provider.py` 的 `generate_report_json`
- 失败兜底：自动回退规则报告（同文件 `_fallback_report`）
