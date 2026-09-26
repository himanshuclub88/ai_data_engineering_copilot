"""Phase 4 UI/data smoke tests that do not require DbMeta, LangGraph, or an LLM."""
from pathlib import Path
import json

from agents.rca_engine import RCAEngine

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "data" / "synthetic_runs"


def main():
    run_ids = sorted(p.name for p in RUNS.iterdir() if p.is_dir() and p.name.startswith("RUN_"))
    assert len(run_ids) == 100, len(run_ids)

    metadata = json.loads((RUNS / "RUN_000005" / "metadata.json").read_text())
    execution_log = (RUNS / "RUN_000005" / "execution.log").read_text()
    error_log = (RUNS / "RUN_000005" / "error.log").read_text()

    result = RCAEngine().analyze(metadata, execution_log + "\n" + error_log)
    assert result["root_cause"] == "OUT_OF_MEMORY", result
    assert result["evidence"], result
    assert metadata["execution"]["status"] == "FAILED"

    print("Phase 4 data/UI smoke test: PASS")


if __name__ == "__main__":
    main()
