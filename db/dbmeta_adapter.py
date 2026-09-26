from pathlib import Path

from dbmeta import FolderDB



class DbMetaAdapter:
    """Thin adapter around the user's DbMeta FolderDB implementation."""

    def __init__(self, base_path):
        self.base_path = Path(base_path)

        if FolderDB is None:
            raise ImportError(
                "DbMeta is not installed/importable. Install your local DbMeta "
                "package or add its source directory to PYTHONPATH."
            )

        self.db = FolderDB(
            base_path=str(self.base_path),
            base_metadata="metadata.json",
        )

    @property
    def tables(self):
        return list(self.db.tables.keys())

    def sql(self, query):
        return self.db.sql(query)

    def failed_runs(self, limit=20):
        query = f"""
        SELECT iid, status, duration_sec, failure_reason
        FROM execution
        WHERE status = 'FAILED'
        ORDER BY duration_sec DESC
        LIMIT {int(limit)}
        """
        return self.sql(query)

    def run_metadata(self, run_id):
        result = self.sql(
            f"SELECT * FROM execution WHERE iid = '{run_id}'"
        )
        return result
