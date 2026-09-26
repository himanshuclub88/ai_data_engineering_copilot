from pathlib import Path

from agents.copilot_tools import CopilotTools

ROOT = Path(__file__).parent
RUNS = ROOT / "data" / "synthetic_runs"

tools = CopilotTools(RUNS)

run_id = "RUN_000001"

print("=== RUN ===")
print(tools.inspect_run(run_id))

print("\n=== RCA ===")
print(tools.diagnose(run_id))
