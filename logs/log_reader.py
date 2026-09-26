from pathlib import Path


class LogReader:
    """Searches execution/error logs inside synthetic run folders."""

    def __init__(self, runs_path):
        self.runs_path = Path(runs_path)

    def read(self, run_id, filename="execution.log"):
        path = self.runs_path / run_id / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def search(self, query, run_id=None):
        folders = (
            [self.runs_path / run_id]
            if run_id
            else sorted(self.runs_path.iterdir())
        )

        matches = []
        q = query.lower()

        for folder in folders:
            if not folder.is_dir():
                continue

            for filename in ("execution.log", "error.log"):
                path = folder / filename
                if not path.exists():
                    continue

                for line_no, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1
                ):
                    if q in line.lower():
                        matches.append({
                            "iid": folder.name,
                            "file": filename,
                            "line": line_no,
                            "text": line,
                        })

        return matches
