"""面试报告聚合服务。"""

from __future__ import annotations

import json
import re
from collections import Counter

from app.core.config import get_settings
from app.services.providers import OllamaProviderClient, OpenAIProviderClient

INTERVIEW_FIRST_QUESTION = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"


# ReportService 将面试轮次整理成结构化报告：
# 1. 优先调用 LLM 生成优势、风险、建议和深挖分析。
# 2. LLM 不可用时使用规则算法生成可解释的兜底报告。
# 3. 12 维能力分使用回答长度、阶段分布、live_score 等稳定特征估算。
# 4. 输出字段全部保持 JSON 字符串，兼容当前数据库 report 表结构。
# 5. 报告侧不再推进面试状态，只读取轮次并写入最终报告内容。
class ReportService:
    """聚合面试轮次并输出结构化报告。"""

    def __init__(self) -> None:
        """初始化报告服务依赖。"""
        self.settings = get_settings()
        self.llm_provider = self.settings.llm_provider
        self._openai_client: OpenAIProviderClient | None = None
        self._ollama_client: OllamaProviderClient | None = None

    def _get_openai_client(self) -> OpenAIProviderClient:
        """惰性初始化 OpenAI 客户端。"""
        if self._openai_client is None:
            self._openai_client = OpenAIProviderClient()
        return self._openai_client

    def _get_ollama_client(self) -> OllamaProviderClient:
        """惰性初始化 Ollama 客户端。"""
        if self._ollama_client is None:
            self._ollama_client = OllamaProviderClient()
        return self._ollama_client

    def _extract_tokens(self, text: str) -> list[str]:
        """提取中英文关键词。"""
        return re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+#._-]{1,}", (text or "").lower())

    def _default_failed_report(self) -> dict:
        """返回统一失败报告。"""
        return {
            "status": "FAILED",
            "overall_score": None,
            "strengths": "[]",
            "weaknesses": "[]",
            "suggestions": "[]",
            "dimension_scores": "[]",
            "jd_resume_alignment": "[]",
            "question_deep_dives": "[]",
            "key_risks": "[]",
            "final_recommendation": "",
            "error_message": "无可用轮次数据，无法生成报告",
        }

    def _fit_level(self, overall_score: int) -> str:
        """估算推荐结论。"""
        if overall_score >= 85:
            return "推荐"
        if overall_score >= 70:
            return "有条件推荐"
        return "存疑"

    def _confidence_level(self, turns: list[dict]) -> str:
        """估算置信度。"""
        if len(turns) >= 6:
            return "高"
        if len(turns) >= 3:
            return "中"
        return "低"

    def _calc_12d_scores(self, turns: list[dict]) -> dict[str, int]:
        """基于轮次数据计算 12 维能力分。"""
        # 这里不是机器学习评分，而是可解释的启发式估算。
        # live_score 表示每轮即时表现，阶段占比表示面试覆盖面，回答长度表示展开程度。
        # 最终压缩到 1-5 档，便于报告 UI 展示雷达图或分项条。
        answers = [str(turn.get("answer_text") or "").strip() for turn in turns]
        scores = [int(turn.get("live_score") or 0) for turn in turns]
        avg_score = int(sum(scores) / max(len(scores), 1))
        avg_len = int(sum(len(item) for item in answers) / max(len(answers), 1))
        stage_counts = Counter(str(turn.get("stage") or "") for turn in turns)
        long_answer_ratio = sum(1 for item in answers if len(item) >= 80) / max(len(answers), 1)
        technical_ratio = stage_counts.get("TECHNICAL", 0) / max(len(turns), 1)
        project_ratio = stage_counts.get("PROJECT_DEEP_DIVE", 0) / max(len(turns), 1)
        behavioral_ratio = stage_counts.get("BEHAVIORAL", 0) / max(len(turns), 1)
        token_count = len(self._extract_tokens(" ".join(answers)))

        def clamp(raw_value: float) -> int:
            return min(5, max(1, int(round(raw_value))))

        return {
            "技术深度": clamp(avg_score / 20),
            "架构设计": clamp((avg_score * 0.7 + technical_ratio * 100 * 0.3) / 20),
            "工程质量": clamp((avg_score * 0.7 + long_answer_ratio * 100 * 0.3) / 20),
            "性能意识": clamp((avg_score * 0.65 + technical_ratio * 100 * 0.35) / 20),
            "稳定性与容错": clamp((avg_score * 0.6 + technical_ratio * 100 * 0.4) / 20),
            "安全与风控": clamp((avg_score * 0.55 + behavioral_ratio * 100 * 0.45) / 20),
            "业务理解": clamp((avg_score * 0.6 + project_ratio * 100 * 0.4) / 20),
            "问题分析与取舍": clamp((avg_score * 0.75 + long_answer_ratio * 100 * 0.25) / 20),
            "沟通表达": clamp(avg_len / 28),
            "协作推进": clamp((avg_score * 0.6 + behavioral_ratio * 100 * 0.4) / 20),
            "学习敏捷性": clamp((avg_score * 0.65 + min(token_count, 400) / 4 * 0.35) / 20),
            "岗位匹配度": clamp((avg_score * 0.8 + project_ratio * 100 * 0.2) / 20),
        }

    def _derive_intent(self, stage: str) -> str:
        """根据阶段动态生成问题意图。"""
        intent_map = {
            "SELF_INTRO": "评估候选人经历抽象与岗位相关性表达",
            "PROJECT_DEEP_DIVE": "评估项目真实性、技术取舍与落地深度",
            "TECHNICAL": "评估技术原理掌握、边界意识与问题拆解能力",
            "BEHAVIORAL": "评估沟通协作、复盘能力与行为模式",
            "END": "评估总结能力与整体稳定性",
        }
        return intent_map.get(stage, "评估回答结构化程度与岗位贴合度")

    def _build_llm_schema(self) -> dict:
        """构建 LLM 输出 JSON Schema。"""
        # 通过 JSON Schema 约束模型输出，减少解析失败和字段缺失。
        # 如果 provider 不支持严格 schema，后续解析逻辑也会做兜底修正。
        return {
            "type": "object",
            "properties": {
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "suggestions": {"type": "array", "items": {"type": "string"}},
                "final_recommendation": {"type": "string"},
                "key_risks": {"type": "array", "items": {"type": "string"}},
                "dimension_scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {"type": "string"},
                            "capability_score": {"type": "integer"},
                            "match_score": {"type": "integer"},
                            "confidence": {"type": "string"},
                            "evidence": {"type": "string"},
                        },
                        "required": ["dimension", "capability_score", "match_score", "confidence", "evidence"],
                        "additionalProperties": False,
                    },
                },
                "jd_resume_alignment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "jd_skill": {"type": "string"},
                            "priority": {"type": "string"},
                            "resume_evidence": {"type": "string"},
                            "answer_evidence": {"type": "string"},
                            "status": {"type": "string"},
                            "note": {"type": "string"},
                        },
                        "required": [
                            "jd_skill",
                            "priority",
                            "resume_evidence",
                            "answer_evidence",
                            "status",
                            "note",
                        ],
                        "additionalProperties": False,
                    },
                },
                "question_deep_dives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_no": {"type": "integer"},
                            "question": {"type": "string"},
                            "intent": {"type": "string"},
                            "answer_summary": {"type": "string"},
                            "hit_rate": {"type": "integer"},
                            "depth_level": {"type": "string"},
                            "resume_relevance": {"type": "string"},
                            "jd_relevance": {"type": "string"},
                            "strengths": {"type": "string"},
                            "gaps": {"type": "string"},
                            "follow_up_questions": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "question_no",
                            "question",
                            "intent",
                            "answer_summary",
                            "hit_rate",
                            "depth_level",
                            "resume_relevance",
                            "jd_relevance",
                            "strengths",
                            "gaps",
                            "follow_up_questions",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "strengths",
                "weaknesses",
                "suggestions",
                "final_recommendation",
                "key_risks",
                "dimension_scores",
                "jd_resume_alignment",
                "question_deep_dives",
            ],
            "additionalProperties": False,
        }

    def _build_llm_messages(
        self,
        turns: list[dict],
        session: dict | None,
        resume_text: str,
        precomputed_12d: dict[str, int],
    ) -> list[dict[str, str]]:
        """构建报告生成 Prompt 消息。"""
        # 报告 prompt 控制输入规模，只截取前 8 轮和每轮前 400 字回答。
        # 这样可以覆盖主要表现，同时避免长面试把上下文窗口全部占满。
        # precomputed_12d 作为规则分数传入，要求 LLM 在结构化报告中参考稳定基线。
        jd_text = str((session or {}).get("jd_snapshot_content") or "")
        history_items = []
        question = INTERVIEW_FIRST_QUESTION
        for index, turn in enumerate(turns[:8], start=1):
            stage = str(turn.get("stage") or "")
            answer = str(turn.get("answer_text") or "").strip()
            score = int(turn.get("live_score") or 0)
            next_question = str(turn.get("next_question") or "").strip()
            history_items.append(
                {
                    "question_no": index,
                    "stage": stage,
                    "question": question,
                    "answer": answer[:400],
                    "score": score,
                    "intent_hint": self._derive_intent(stage),
                }
            )
            question = next_question or question
        user_payload = {
            # user_payload 使用 JSON 序列化传给模型。
            # 这种结构比自然语言拼接更稳定，模型更容易按字段输出证据化报告。
            "job_role": str((session or {}).get("job_role") or ""),
            "difficulty": str((session or {}).get("difficulty") or ""),
            "jd_text": jd_text[:2400],
            "resume_text": (resume_text or "")[:2400],
            "turns": history_items,
            "precomputed_dimension_scores": precomputed_12d,
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是资深技术面试官与评估专家。"
                    "请基于输入数据输出结构化面试报告。"
                    "所有判断必须有证据，未出现证据必须标注为未验证。"
                    "只输出 JSON，不要输出其他文本。"
                ),
            },
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

    def _normalize_dimension_scores(self, llm_scores: list[dict], turns: list[dict]) -> list[dict]:
        """归一化维度评分并确保 12 维都存在。"""
        # LLM 可能漏掉部分维度或输出越界分值。
        # 这里用规则预计算分数补齐所有 12 个维度，并把分值限制在 1-5。
        # confidence 默认取决于轮次数量，避免短面试报告显示过高置信度。
        confidence = self._confidence_level(turns)
        precomputed = self._calc_12d_scores(turns)
        mapped = {str(item.get("dimension") or ""): item for item in llm_scores}
        normalized: list[dict] = []
        for dimension_name, base_score in precomputed.items():
            item = mapped.get(dimension_name, {})
            capability_score = int(item.get("capability_score") or base_score)
            match_score = int(item.get("match_score") or max(1, base_score - 1))
            normalized.append(
                {
                    "dimension": dimension_name,
                    "capability_score": min(5, max(1, capability_score)),
                    "match_score": min(5, max(1, match_score)),
                    "confidence": str(item.get("confidence") or confidence),
                    "evidence": str(item.get("evidence") or f"基于轮次数据计算得到基础分 {base_score}"),
                }
            )
        return normalized

    def _fallback_report(self, turns: list[dict], session: dict | None = None, resume_text: str = "") -> dict:
        """规则回退报告生成。"""
        # 当 LLM 不可用或解析失败时，仍然要给用户一份可读报告。
        # 回退报告完全基于轮次分数、回答长度、阶段分布和 JD/简历 token 匹配。
        # 其目标是“可解释、不断流程”，不是替代人工最终判断。
        raw_scores = [int(turn.get("live_score") or 0) for turn in turns]
        overall_score = int(sum(raw_scores) / len(raw_scores))
        confidence = self._confidence_level(turns)
        precomputed_12d = self._calc_12d_scores(turns)
        dimension_scores = self._normalize_dimension_scores([], turns)
        low_dimensions = [name for name, score in precomputed_12d.items() if score <= 2]

        strengths = []
        weaknesses = []
        suggestions = []
        key_risks = []
        if overall_score >= 80:
            strengths.append(f"整体稳定，当前平均分 {overall_score}，回答质量波动较小")
        else:
            weaknesses.append(f"整体稳定性一般，当前平均分 {overall_score}，建议补强核心题表现")
        if low_dimensions:
            weaknesses.append("低分维度：" + "、".join(low_dimensions))
            suggestions.append("下一轮优先追问低分维度，重点验证可落地案例与指标结果")
            key_risks.append("多个能力维度得分偏低，岗位匹配存在不确定性")
        suggestions.append("建议在最终结论前由面试官复核关键题原始问答与项目真实性证据")
        if not key_risks:
            key_risks.append("未发现高优先级风险，建议保持标准化复核流程")

        question = INTERVIEW_FIRST_QUESTION
        deep_dives: list[dict] = []
        for index, turn in enumerate(turns[:3], start=1):
            # 深挖分析最多取前三轮，避免回退报告过长。
            # 每条分析都保留问题、回答摘要、命中率、深度等级和建议追问。
            stage = str(turn.get("stage") or "")
            answer = str(turn.get("answer_text") or "").strip()
            score = int(turn.get("live_score") or 0)
            next_question = str(turn.get("next_question") or "").strip()
            deep_dives.append(
                {
                    "question_no": index,
                    "question": question,
                    "intent": self._derive_intent(stage),
                    "answer_summary": answer[:220] if answer else "无有效回答",
                    "hit_rate": min(100, max(30, score)),
                    "depth_level": "概念+实现+取舍" if len(answer) >= 140 else ("概念+实现" if len(answer) >= 70 else "概念"),
                    "resume_relevance": "高" if stage in {"SELF_INTRO", "PROJECT_DEEP_DIVE"} else "中",
                    "jd_relevance": "高" if stage in {"TECHNICAL", "PROJECT_DEEP_DIVE"} else "中",
                    "strengths": "回答信息量较好" if len(answer) >= 90 else "回答完成度基础可用",
                    "gaps": "建议补充量化指标和失败复盘",
                    "follow_up_questions": [
                        "请补充该方案上线后的指标变化与验证方法",
                        "如果出现线上回退场景，你会如何快速定位并恢复？",
                    ],
                }
            )
            question = next_question or question

        jd_text = str((session or {}).get("jd_snapshot_content") or "")
        jd_tokens = list(dict.fromkeys(self._extract_tokens(jd_text)))[:8]
        resume_token_set = set(self._extract_tokens(resume_text or ""))
        answer_text = " ".join(str(turn.get("answer_text") or "") for turn in turns).lower()
        alignment = []
        for token in jd_tokens or ["岗位关键能力"]:
            # JD 对齐使用简单 token 命中规则。
            # 未命中不代表候选人一定不具备能力，只表示当前回答中缺少证据。
            alignment.append(
                {
                    "jd_skill": token,
                    "priority": "Must",
                    "resume_evidence": "简历已提及" if token in resume_token_set else "简历未明确提及",
                    "answer_evidence": "回答已覆盖" if token in answer_text else "回答未覆盖",
                    "status": "已验证" if token in answer_text else "未验证",
                    "note": "建议结合原始上下文确认语义一致性",
                }
            )

        return {
            "status": "READY",
            "overall_score": overall_score,
            "strengths": json.dumps(strengths, ensure_ascii=False),
            "weaknesses": json.dumps(weaknesses, ensure_ascii=False),
            "suggestions": json.dumps(suggestions, ensure_ascii=False),
            "dimension_scores": json.dumps(dimension_scores, ensure_ascii=False),
            "jd_resume_alignment": json.dumps(alignment, ensure_ascii=False),
            "question_deep_dives": json.dumps(deep_dives, ensure_ascii=False),
            "key_risks": json.dumps(key_risks, ensure_ascii=False),
            "final_recommendation": f"{self._fit_level(overall_score)}（置信度：{confidence}）",
            "error_message": None,
        }

    def _generate_by_llm(self, turns: list[dict], session: dict | None, resume_text: str) -> dict | None:
        """通过大模型生成结构化报告。"""
        precomputed_12d = self._calc_12d_scores(turns)
        messages = self._build_llm_messages(turns, session, resume_text, precomputed_12d)
        schema = self._build_llm_schema()
        if self.llm_provider == "openai":
            payload = self._get_openai_client().generate_report_json(messages, schema=schema)
        elif self.llm_provider == "ollama":
            prompt = (
                "你是资深技术面试官与评估专家。请根据以下 JSON 输入生成符合 schema 的 JSON 输出。\n"
                f"schema={json.dumps(schema, ensure_ascii=False)}\n"
                f"input={messages[-1]['content']}"
            )
            raw = self._get_ollama_client().generate_question(prompt)
            payload = json.loads(raw)
        else:
            return None

        dimension_scores = self._normalize_dimension_scores(payload.get("dimension_scores", []), turns)
        raw_scores = [int(turn.get("live_score") or 0) for turn in turns]
        overall_score = int(sum(raw_scores) / len(raw_scores))
        return {
            "status": "READY",
            "overall_score": overall_score,
            "strengths": json.dumps(payload.get("strengths", []), ensure_ascii=False),
            "weaknesses": json.dumps(payload.get("weaknesses", []), ensure_ascii=False),
            "suggestions": json.dumps(payload.get("suggestions", []), ensure_ascii=False),
            "dimension_scores": json.dumps(dimension_scores, ensure_ascii=False),
            "jd_resume_alignment": json.dumps(payload.get("jd_resume_alignment", []), ensure_ascii=False),
            "question_deep_dives": json.dumps(payload.get("question_deep_dives", []), ensure_ascii=False),
            "key_risks": json.dumps(payload.get("key_risks", []), ensure_ascii=False),
            "final_recommendation": str(
                payload.get("final_recommendation")
                or f"{self._fit_level(overall_score)}（置信度：{self._confidence_level(turns)}）"
            ),
            "error_message": None,
        }

    def build_report(self, turns: list[dict], session: dict | None = None, resume_text: str = "") -> dict:
        """根据轮次评分构建报告。"""
        if not turns:
            return self._default_failed_report()
        try:
            llm_report = self._generate_by_llm(turns, session=session, resume_text=resume_text)
            if llm_report:
                return llm_report
        except Exception:
            pass
        return self._fallback_report(turns, session=session, resume_text=resume_text)
