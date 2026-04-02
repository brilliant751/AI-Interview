"""面试报告聚合服务。"""

from __future__ import annotations

import json


class ReportService:
    """聚合面试轮次并输出结构化报告。"""

    def build_report(self, turns: list[dict]) -> dict:
        """根据轮次评分构建报告。"""
        if not turns:
            return {
                "status": "FAILED",
                "overall_score": None,
                "strengths": "[]",
                "weaknesses": "[]",
                "suggestions": "[]",
                "error_message": "无可用轮次数据，无法生成报告",
            }

        scores = [int(t["live_score"]) for t in turns]
        overall = int(sum(scores) / len(scores))
        strengths = []
        weaknesses = []
        suggestions = []
        if overall >= 80:
            strengths.append("整体表达与答题结构较好")
            suggestions.append("继续保持，提升案例深度与量化表达")
        elif overall >= 60:
            strengths.append("基础知识掌握较稳定")
            weaknesses.append("回答深度与场景落地不足")
            suggestions.append("每道题补充项目中的真实实践与权衡")
        else:
            weaknesses.append("核心概念理解不完整")
            suggestions.append("建议按岗位题库进行分模块复盘并重新演练")

        return {
            "status": "READY",
            "overall_score": overall,
            "strengths": json.dumps(strengths, ensure_ascii=False),
            "weaknesses": json.dumps(weaknesses, ensure_ascii=False),
            "suggestions": json.dumps(suggestions, ensure_ascii=False),
            "error_message": None,
        }

