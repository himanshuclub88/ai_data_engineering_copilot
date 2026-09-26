"""Phase 3 structural test; does not call an external LLM."""
from agents.copilot_tools import CopilotTools
from db.dbmeta_adapter import DbMetaAdapter
from logs.log_reader import LogReader
from agents.graph import build_tools


class FakeLLM:
    def bind_tools(self, tools):
        return self


root = "data/synthetic_runs"
copilot = CopilotTools(DbMetaAdapter(root), LogReader(root))
tools = build_tools(copilot)
assert {t.name for t in tools} == {"inspect_run", "query_metadata", "search_logs", "diagnose_run"}

result = copilot.diagnose("RUN_000005")
assert result["scenario"] == "OUT_OF_MEMORY"
assert result["root_cause"]
print("Phase 3 tool-layer test: PASS")
print("Tools:", [t.name for t in tools])
