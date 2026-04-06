"""问题生成工作流服务。"""

from __future__ import annotations

from typing import Any, TypedDict

from app.services.providers import OpenAIProviderClient


class _WorkflowState(TypedDict):
    """问题生成工作流状态。"""

    answer: str
    references: list[dict[str, Any]]
    question: str


class QuestionWorkflow:
    """基于 LangGraph 与 provider 的问题生成工作流。"""

    def __init__(self) -> None:
        """初始化工作流编译结果。"""
        from app.core.config import get_settings

        settings = get_settings()
        self.llm_provider = settings.llm_provider
        self._openai_client: OpenAIProviderClient | None = None
        self._graph = self._build_graph()

    def _build_graph(self):  # type: ignore[no-untyped-def]
        """构建并编译 LangGraph，若不可用则返回 None。"""
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return None

        def compose(state: _WorkflowState) -> dict:
            ref_hint = state["references"][0]["title"] if state["references"] else "岗位基础能力"
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

    def generate_template(self, answer: str, references: list[dict[str, Any]]) -> str:
        """基于模板生成问题，作为兜底方案。"""
        if self._graph is None:
            ref_hint = references[0]["title"] if references else "岗位基础能力"
            return f"基于你刚才的回答，请展开说明你在“{ref_hint}”上的实践细节。"
        output = self._graph.invoke({"answer": answer, "references": references, "question": ""})
        return output["question"]

    def generate_by_llm(self, answer: str, references: list[dict[str, Any]]) -> str:
        """调用 LLM 生成问题。"""
        if self.llm_provider != "openai":
            raise RuntimeError("当前 LLM provider 非 openai，不走真实调用")
        return self._get_openai_client().generate_question(answer=answer, references=references)

    def generate(self, answer: str, references: list[dict[str, Any]]) -> str:
        """统一生成入口：openai 优先，失败由上层降级。"""
        if self.llm_provider == "openai":
            return self.generate_by_llm(answer=answer, references=references)
        return self.generate_template(answer=answer, references=references)

    def health(self) -> dict[str, str]:
        """返回 LLM provider 健康状态。"""
        if self.llm_provider != "openai":
            return {"llm": "UP"}
        try:
            return {"llm": self._get_openai_client().health()}
        except Exception:
            return {"llm": "DOWN"}
