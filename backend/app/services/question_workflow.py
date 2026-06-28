"""问题生成工作流服务。"""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from app.services.providers import OllamaProviderClient, OpenAIProviderClient


# 问题生成工作流提供两条路径：
# 1. provider 可用时调用 OpenAI/Ollama 生成更贴合简历、JD 和历史上下文的追问。
# 2. provider 不可用或未启用时使用模板问题，保证面试流程仍能完整走完。
# 3. LangGraph 是可选增强，缺失依赖时 _build_graph 返回 None，不影响模板兜底。
# 4. 所有模型输出都会经过清理，尽量得到“可以直接说出口”的单句问题。
# 5. JD、简历、知识库引用会按优先级进入 prompt，避免通用知识压过岗位要求。
class _WorkflowState(TypedDict):
    """问题生成工作流状态。"""

    answer: str
    references: list[dict[str, Any]]
    question: str
    stage: str
    technical_count: int
    follow_up_count: int


class QuestionWorkflow:
    """基于 LangGraph 与 provider 的问题生成工作流。"""

    def __init__(self) -> None:
        """初始化工作流编译结果。"""
        from app.core.config import get_settings

        settings = get_settings()
        self.settings = settings
        self.llm_provider = settings.llm_provider
        self._openai_client: Optional[OpenAIProviderClient] = None
        self._ollama_client: Optional[OllamaProviderClient] = None
        self._graph = self._build_graph()

    def _build_graph(self):  # type: ignore[no-untyped-def]
        """构建并编译 LangGraph，若不可用则返回 None。"""
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            # LangGraph 不是主流程硬依赖；缺失时退回普通模板逻辑。
            # 这样 CI 或轻量部署环境无需额外安装图编排库也能运行。
            return None

        def compose(state: _WorkflowState) -> dict:
            # compose 节点是最小可运行图，只根据阶段、回答摘要和引用标题生成追问。
            # 复杂 provider 生成逻辑放在 generate_by_llm 中，图节点用于本地兜底。
            ref_hint = state["references"][0]["title"] if state["references"] else "岗位基础能力"
            answer_hint = state["answer"].strip().replace("\n", " ")[:24]
            if state["stage"] == "PROJECT_DEEP_DIVE":
                question = f"你提到“{answer_hint}”，请结合项目背景具体说明你主导的关键决策，以及如何评估结果。"
            elif state["stage"] == "TECHNICAL":
                question = f"围绕“{ref_hint}”，结合你刚才的回答“{answer_hint}”，请继续深入说明技术实现细节。"
            elif state["stage"] == "BEHAVIORAL":
                question = f"回到“{answer_hint}”这个经历，你是如何协调团队并推进最终结果的？"
            else:
                question = f"基于你刚才的回答，请展开说明你在“{ref_hint}”上的实践细节。"
            return {"question": question}

        graph = StateGraph(_WorkflowState)
        graph.add_node("compose", compose)
        graph.add_edge(START, "compose")
        graph.add_edge("compose", END)
        return graph.compile()

    def _get_openai_client(self) -> OpenAIProviderClient:
        """惰性初始化 OpenAI provider 客户端。"""
        if self._openai_client is None:
            self._openai_client = OpenAIProviderClient()
        return self._openai_client

    def _get_ollama_client(self) -> OllamaProviderClient:
        """惰性初始化 Ollama provider 客户端。"""
        if self._ollama_client is None:
            self._ollama_client = OllamaProviderClient()
        return self._ollama_client

    def _pick_reference_hint(self, references: list[dict[str, Any]]) -> str:
        """从检索结果中挑选更稳定的主题标题。"""
        for reference in references:
            title = str(reference.get("title", "")).strip()
            if title and title != "知识片段":
                return title
        return "岗位基础能力"

    def _build_reference_context(self, references: list[dict[str, Any]], limit: int = 3) -> str:
        """构建统一的参考上下文（JD/简历/知识库）。"""
        if not references:
            return "无"

        def _priority(reference: dict[str, Any]) -> int:
            # Prompt 中参考资料的优先级：JD > 简历 > 知识库。
            # JD 定义岗位要求，简历定义候选人事实，知识库只提供通用补充。
            source = str(reference.get("source_path") or "").lower()
            retrieval_mode = str(reference.get("retrieval_mode") or "").lower()
            if source == "jd" or retrieval_mode == "jd":
                return 0
            if source == "resume" or retrieval_mode == "resume":
                return 1
            return 2

        contexts: list[str] = []
        for ref in sorted(references, key=_priority)[:limit]:
            title = str(ref.get("title") or "参考片段").strip() or "参考片段"
            content = str(ref.get("content") or "").strip().replace("\n", " ")
            if content:
                contexts.append(f"- {title}：{content[:180]}")
            else:
                contexts.append(f"- {title}")
        return "\n".join(contexts) if contexts else "无"

    def _sanitize_spoken_question(self, text: str) -> str:
        """清理模型可能返回的装饰性内容，保留可直接说出口的一句问句。"""
        # 模型有时会返回 markdown、解释、追问意图等额外文本。
        # 面试官语音播报只需要自然问题，因此这里过滤装饰性内容和代码块标记。
        normalized = (text or "").strip()
        if not normalized:
            return normalized
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        filtered = [
            line
            for line in lines
            if ("追问意图" not in line and not line.startswith("*(") and not line.startswith("（追问意图"))
        ]
        merged = " ".join(filtered) if filtered else normalized
        cleaned = merged.replace("**", "").replace("```", "").strip()
        return cleaned

    def generate_template(
        self,
        answer: str,
        references: list[dict[str, Any]],
        stage: str,
        difficulty: str = "medium",
        technical_count: int = 0,
        follow_up_count: int = 0,
    ) -> str:
        """基于模板生成问题，作为兜底方案。"""
        ref_hint = self._pick_reference_hint(references)
        answer_hint = answer.strip().replace("\n", " ")[:24]
        difficulty_hint_map = {
            "easy": "请保持基础难度，先核验核心概念与实际参与度。",
            "medium": "请保持标准难度，兼顾实现细节、取舍与结果。",
            "hard": "请提高难度，深入追问边界条件、故障排查与优化证据。",
        }
        difficulty_hint = difficulty_hint_map.get(difficulty, difficulty_hint_map["medium"])

        if stage == "TECHNICAL":
            prompts = [
                f"{difficulty_hint} 基于你刚才提到的“{answer_hint}”，请展开说明你在“{ref_hint}”上的技术方案和实现细节。",
                f"{difficulty_hint} 你在“{ref_hint}”里具体负责了哪些部分？结合你刚才提到的“{answer_hint}”，说说遇到过什么技术难点以及怎么解决的。",
                f"{difficulty_hint} 如果围绕“{ref_hint}”继续深入，结合你刚才的回答“{answer_hint}”，你会如何优化当前方案的性能、稳定性或可维护性？",
            ]
            return prompts[technical_count % len(prompts)]

        if stage == "PROJECT_DEEP_DIVE":
            prompts = [
                f"结合你刚才提到的“{answer_hint}”，请详细说明项目背景、你的职责边界和关键目标。",
                f"围绕“{ref_hint}”，你在项目里做过最关键的技术决策是什么，为什么这样选？",
                f"如果回到那个项目阶段，针对你提到的“{answer_hint}”，你会优先优化哪一块，预期收益是什么？",
            ]
            return prompts[technical_count % len(prompts)]

        if stage == "BEHAVIORAL":
            prompts = [
                f"结合你刚才提到的经历“{answer_hint}”，请说明你在协作中是如何推进结果的。",
                f"请举例说明你在类似“{ref_hint}”的场景下，如何处理沟通、冲突或时间压力。",
                "回顾你刚才的回答，那个经历里你做得最关键的一步是什么，为什么？",
            ]
            return prompts[follow_up_count % len(prompts)]

        if self._graph is None:
            return f"基于你刚才的回答，请展开说明你在“{ref_hint}”上的实践细节。"

        output = self._graph.invoke(
            {
                "answer": answer,
                "references": references,
                "question": "",
                "stage": stage,
                "technical_count": technical_count,
                "follow_up_count": follow_up_count,
            }
        )
        return output["question"]

    def generate_by_llm(
        self,
        answer: str,
        references: list[dict[str, Any]],
        stage: str,
        difficulty: str = "medium",
        history_messages: list[dict[str, str]] | None = None,
        job_role: str = "",
        jd_content: str = "",
        resume_content: str = "",
        trace_id: str = "",
        interview_id: str = "",
    ) -> str:
        """调用 LLM 生成问题。"""
        # provider 分支在这里集中处理，上层 InterviewService 只关心 generate() 返回一句问题。
        # OpenAI provider 已经封装了更复杂的消息结构，所以这里直接透传上下文参数。
        # Ollama provider 使用本地 /api/chat，需要在当前方法内组装完整 prompt。
        if self.llm_provider == "openai":
            return self._get_openai_client().generate_question(
                answer=answer,
                references=references,
                stage=stage,
                difficulty=difficulty,
                history_messages=history_messages or [],
                job_role=job_role,
                jd_content=jd_content,
                resume_content=resume_content,
                trace_id=trace_id,
                interview_id=interview_id,
            )
        if self.llm_provider == "ollama":
            # Ollama prompt 需要尽量短而明确：
            # JD/简历/知识库按优先级进入 ref_context，历史对话保持 role/content 格式。
            # 输出要求限制为“一句中文问句”，减少模型返回分析段落的概率。
            ref_titles = "；".join(ref.get("title", "") for ref in references[:3] if ref.get("title"))
            ref_hint = ref_titles or "岗位基础能力"
            ref_context = self._build_reference_context(references=references)
            dialogue_context = ""
            for message in history_messages or []:
                role = str(message.get("role") or "").strip()
                content = str(message.get("content") or "").strip()
                if role and content:
                    dialogue_context += f"role: {role}\ncontent: {content}\n\n"
            role_or_jd = (jd_content or "").strip() or f"岗位方向：{job_role or '未提供'}"
            difficulty_hint_map = {
                "easy": "基础难度：优先核验基础概念与实际参与度。",
                "medium": "标准难度：兼顾实现细节、方案取舍与结果评估。",
                "hard": "高难度：深入追问边界条件、故障排查、性能优化与反思。",
            }
            difficulty_hint = difficulty_hint_map.get(difficulty, difficulty_hint_map["medium"])
            prefix = ""
            if stage == "PROJECT_DEEP_DIVE" and (resume_content or "").strip():
                # 项目深挖阶段才把较长简历内容放入 prompt。
                # 其他阶段过多简历文本会稀释技术/JD 追问重点，也会增加本地模型负担。
                prefix = (
                    "【简历内容（仅项目经历轮使用）】\n"
                    f"{resume_content[:2400]}\n"
                    "请围绕候选人简历项目经历进行追问。\n\n"
                )
            prompt = (
                "你是资深中文技术面试官。你的回答就是面试官现场说出的下一句提问。\n"
                "请像真人一样自然说话，口语化、简洁、直接，不要写成说明文。\n"
                f"{prefix}"
                f"岗位方向或岗位描述：{role_or_jd}\n"
                f"当前阶段：{stage}\n"
                f"面试难度：{difficulty}（{difficulty_hint}）\n"
                f"历史对话（固定格式）：\n{dialogue_context}"
                f"参考主题：{ref_hint}\n"
                f"参考资料（含JD与简历）：\n{ref_context}\n"
                "要求：只输出一句中文口语化问句，禁止输出“追问意图”、括号解释、分点、Markdown 标题或加粗。"
            )
            return self._get_ollama_client().generate_question(prompt)
        raise RuntimeError("当前 LLM provider 未实现真实调用")

    def generate(
        self,
        answer: str,
        references: list[dict[str, Any]],
        stage: str,
        difficulty: str = "medium",
        technical_count: int = 0,
        follow_up_count: int = 0,
        history_messages: list[dict[str, str]] | None = None,
        job_role: str = "",
        jd_content: str = "",
        resume_content: str = "",
        trace_id: str = "",
        interview_id: str = "",
    ) -> str:
        """统一生成入口：openai 优先，失败由上层降级。"""
        # generate 负责统一“真实 provider 或模板”的出口。
        # 真实 provider 的异常不在这里吞掉，交给 InterviewService 记录 degrade_flags。
        # 无论哪条路径，最后都清理成适合语音播报的问句。
        if self.llm_provider in {"openai", "ollama"}:
            question = self.generate_by_llm(
                answer=answer,
                references=references,
                stage=stage,
                difficulty=difficulty,
                history_messages=history_messages,
                job_role=job_role,
                jd_content=jd_content,
                resume_content=resume_content,
                trace_id=trace_id,
                interview_id=interview_id,
            )
            return self._sanitize_spoken_question(question)
        question = self.generate_template(
            answer=answer,
            references=references,
            stage=stage,
            difficulty=difficulty,
            technical_count=technical_count,
            follow_up_count=follow_up_count,
        )
        return self._sanitize_spoken_question(question)

    def health(self) -> dict[str, str]:
        """返回 LLM provider 健康状态。"""
        if self.llm_provider == "ollama":
            try:
                return {"llm": self._get_ollama_client().health()["status"]}
            except Exception:
                return {"llm": "DOWN"}
        if self.llm_provider != "openai":
            return {"llm": "UP"}
        try:
            return {"llm": self._get_openai_client().health()}
        except Exception:
            return {"llm": "DOWN"}

    def health_details(self) -> dict[str, Any]:
        """返回 LLM provider 详细健康信息。"""
        if self.llm_provider == "ollama":
            return self._get_ollama_client().health()
        if self.llm_provider == "openai":
            status = self._get_openai_client().health()
            return {
                "status": status,
                "provider": "openai",
                "model": self.settings.llm_model,
                "latency_ms": 0,
                "error_message": "" if status == "UP" else "缺少 OpenAI 兼容密钥",
            }
        return {
            "status": "UP",
            "provider": self.llm_provider,
            "model": self.settings.llm_model,
            "latency_ms": 0,
            "error_message": "",
        }
