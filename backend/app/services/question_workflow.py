"""问题生成工作流服务。"""

from __future__ import annotations

from typing import Any, TypedDict


class _WorkflowState(TypedDict):
    """问题生成工作流状态。"""

    answer: str
    references: list[dict[str, Any]]
    question: str


class QuestionWorkflow:
    """基于 LangGraph 的可降级问题生成工作流。"""

    def __init__(self) -> None:
        """初始化工作流编译结果。"""
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

    def generate(self, answer: str, references: list[dict[str, Any]]) -> str:
        """生成下一题。"""
        if self._graph is None:
            ref_hint = references[0]["title"] if references else "岗位基础能力"
            return f"基于你刚才的回答，请展开说明你在“{ref_hint}”上的实践细节。"
        output = self._graph.invoke({"answer": answer, "references": references, "question": ""})
        return output["question"]

