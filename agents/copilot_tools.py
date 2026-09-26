import json
from pathlib import Path

from db.dbmeta_adapter import DbMetaAdapter
from logs.log_reader import LogReader
from agents.rca_engine import RCAEngine


class CopilotTools:
    """Application service layer shared by CLI, LangGraph and future UI."""

    def __init__(self, runs_path):
        self.runs_path = Path(runs_path)
        self.db = DbMetaAdapter(self.runs_path)
        self.logs = LogReader(self.runs_path)
        # Backward-compatible aliases used by Phase 2 code.
        self.log_reader = self.logs
        self.rca = RCAEngine()

    def load_metadata(self, run_id):
        path = self.runs_path / run_id / "metadata.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def inspect_run(self, run_id):
        metadata = self.load_metadata(run_id)
        logs = self.logs.read(run_id, "execution.log")
        errors = self.logs.read(run_id, "error.log")

        return {
            "run_id": run_id,
            "metadata": metadata,
            "execution_log": logs,
            "error_log": errors,
        }

    def diagnose(self, run_id):
        data = self.inspect_run(run_id)
        return self.rca.analyze(
            data["metadata"],
            data["execution_log"] + "\n" + data["error_log"],
        )
