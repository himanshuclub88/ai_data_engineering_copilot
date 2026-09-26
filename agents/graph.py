"""LangGraph orchestration for the AI Data Engineering Copilot."""
from __future__ import annotations

import json
import os
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agents.copilot_tools import CopilotTools


SYSTEM_PROMPT = """You are an AI Data Engineering Copilot.

Your job is to investigate synthetic enterprise pipeline runs using ONLY evidence returned by
DbMeta metadata queries, log search, and deterministic RCA tools.

Rules:
1. Never invent a metric, log line, table, run id, or root cause.
2. For a specific failed run, inspect metadata and logs before concluding.
3. Prefer deterministic RCA evidence when it exists.
4. Clearly separate observed evidence from your explanation.
5. If evidence is insufficient, say exactly what is missing.
6. Keep recommendations practical for a data engineer.
"""


def build_tools(copilot: CopilotTools):
    @tool
    def inspect_run(run_id: str) -> str:
        """Inspect one pipeline run: metadata plus execution/error logs."""
        return json.dumps(copilot.inspect_run(run_id), default=str)

    @tool
    def query_metadata(sql: str) -> str:
        """Run a read-only SQL query against the DbMeta metadata layer."""
        return json.dumps(copilot.db.sql(sql), default=str)

    @tool
    def search_logs(query: str, run_id: str | None = None) -> str:
        """Search execution.log and error.log for a text query, optionally within one run."""
        return json.dumps(copilot.logs.search(query, run_id=run_id), default=str)

    @tool
    def diagnose_run(run_id: str) -> str:
        """Run deterministic evidence-based RCA for one pipeline run."""
        return json.dumps(copilot.diagnose(run_id), default=str)

    return [inspect_run, query_metadata, search_logs, diagnose_run]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_graph(copilot: CopilotTools, llm):
    tools = build_tools(copilot)
    model = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent(state: AgentState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = model.invoke(messages)
        return {"messages": [response]}

    def route(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route)
    graph.add_edge("tools", "agent")
    return graph.compile()


def ask(graph, question: str):
    result = graph.invoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content
