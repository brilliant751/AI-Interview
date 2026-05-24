"""问题生成工作流服务。"""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from app.services.providers import OllamaProviderClient, OpenAIProviderClient


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
            return None

        def compose(state: _WorkflowState) -> dict:
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

    def generate_template(
        self,
        answer: str,
        references: list[dict[str, Any]],
        stage: str,
        technical_count: int = 0,
        follow_up_count: int = 0,
    ) -> str:
        """基于模板生成问题，作为兜底方案。"""
        ref_hint = self._pick_reference_hint(references)
        answer_hint = answer.strip().replace("\n", " ")[:24]

        if stage == "TECHNICAL":
            prompts = [
                f"基于你刚才提到的“{answer_hint}”，请展开说明你在“{ref_hint}”上的技术方案和实现细节。",
                f"你在“{ref_hint}”里具体负责了哪些部分？结合你刚才提到的“{answer_hint}”，说说遇到过什么技术难点以及怎么解决的。",
                f"如果围绕“{ref_hint}”继续深入，结合你刚才的回答“{answer_hint}”，你会如何优化当前方案的性能、稳定性或可维护性？",
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
        history_messages: list[dict[str, str]] | None = None,
        job_role: str = "",
        jd_content: str = "",
        resume_content: str = "",
        trace_id: str = "",
        interview_id: str = "",
    ) -> str:
        """调用 LLM 生成问题。"""
        if self.llm_provider == "openai":
            return self._get_openai_client().generate_question(
                answer=answer,
                references=references,
                stage=stage,
                history_messages=history_messages or [],
                job_role=job_role,
                jd_content=jd_content,
                resume_content=resume_content,
                trace_id=trace_id,
                interview_id=interview_id,
            )
        if self.llm_provider == "ollama":
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
            prefix = ""
            if stage == "PROJECT_DEEP_DIVE" and (resume_content or "").strip():
                prefix = (
                    "【简历内容（仅项目经历轮使用）】\n"
                    f"{resume_content[:2400]}\n"
                    "请围绕候选人简历项目经历进行追问。\n\n"
                )
            prompt = (
                "你是资深中文技术面试官，请基于完整历史对话生成一个追问问题。\n"
                f"{prefix}"
                f"岗位方向或岗位描述：{role_or_jd}\n"
                f"当前阶段：{stage}\n"
                f"历史对话（固定格式）：\n{dialogue_context}"
                f"参考主题：{ref_hint}\n"
                f"参考资料（含JD与简历）：\n{ref_context}\n"
                "要求：只输出一句中文问题，并优先验证候选人经历与JD要求的匹配度。"
            )
            return self._get_ollama_client().generate_question(prompt)
        raise RuntimeError("当前 LLM provider 未实现真实调用")

    def generate(
        self,
        answer: str,
        references: list[dict[str, Any]],
        stage: str,
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
        if self.llm_provider in {"openai", "ollama"}:
            return self.generate_by_llm(
                answer=answer,
                references=references,
                stage=stage,
                history_messages=history_messages,
                job_role=job_role,
                jd_content=jd_content,
                resume_content=resume_content,
                trace_id=trace_id,
                interview_id=interview_id,
            )
        return self.generate_template(
            answer=answer,
            references=references,
            stage=stage,
            technical_count=technical_count,
            follow_up_count=follow_up_count,
        )

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
