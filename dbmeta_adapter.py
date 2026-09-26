"""
DbMeta adapter for job-scoped metadata.

No custom classes. Each job gets its own FolderDB instance.
"""

from pathlib import Path
from dbmeta import FolderDB


TABLES = [
    "pipeline",
    "execution",
    "input",
    "output",
    "resources",
    "data_quality",
    "spark",
]


def list_jobs(data_root):
    root = Path(data_root)
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def list_runs(job_path):
    job = Path(job_path)
    return sorted(
        p.name for p in job.iterdir()
        if p.is_dir() and p.name.startswith("RUN_")
    )


def get_db(job_path):
    """Create a DbMeta database for exactly one job."""
    return FolderDB(
        base_path=str(job_path),
        base_metadata="metadata.json",
    )


def query(db, sql):
    """Run a DbMeta SQL query."""
    return db.sql(sql)


def get_run(db, run_id):
    """Read the structured metadata for one run."""
    result = {}
    for table in TABLES:
        rows = query(
            db,
            f"SELECT * FROM {table} WHERE iid = '{run_id}'"
        )
        result[table] = rows
    return result


def get_recent_runs(db, limit=20):
    """Return recent runs from the job execution table."""
    return query(
        db,
        "SELECT iid, status, failure_reason, start_time, duration_sec "
        f"FROM execution ORDER BY start_time DESC LIMIT {int(limit)}"
    )


def get_failed_runs(db, limit=100):
    """Return failed runs for the selected job."""
    return query(
        db,
        "SELECT iid, status, failure_reason, start_time, duration_sec "
        f"FROM execution WHERE status = 'FAILED' "
        f"ORDER BY start_time DESC LIMIT {int(limit)}"
    )
