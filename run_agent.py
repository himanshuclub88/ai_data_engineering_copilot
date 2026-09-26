"""CLI entry point for the LangGraph AI Data Engineering Copilot."""
from agents.copilot_tools import CopilotTools
from agents.graph import ask, build_graph
from db.dbmeta_adapter import DbMetaAdapter
from logs.log_reader import LogReader
from llm_factory import build_llm


def main():
    copilot = CopilotTools(DbMetaAdapter("data/synthetic_runs"), LogReader("data/synthetic_runs"))
    graph = build_graph(copilot, build_llm())
    question = input("Copilot> ").strip()
    print("\n" + ask(graph, question))


if __name__ == "__main__":
    main()
