import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
RUNS = ROOT / "data" / "synthetic_runs"


def test_run_count():
    runs = [p for p in RUNS.iterdir() if p.is_dir()]
    assert len(runs) == 100


def test_required_files():
    for run in RUNS.iterdir():
        if not run.is_dir():
            continue

        assert (run / "metadata.json").exists()
        assert (run / "execution.log").exists()
        assert (run / "error.log").exists()
        assert (run / "audit.json").exists()


def test_metadata_shape():
    sample = next(p for p in RUNS.iterdir() if p.is_dir())
    metadata = json.loads(
        (sample / "metadata.json").read_text(encoding="utf-8")
    )

    assert "pipeline" in metadata
    assert "execution" in metadata
    assert "input" in metadata
    assert "output" in metadata
    assert "resources" in metadata
    assert "data_quality" in metadata
