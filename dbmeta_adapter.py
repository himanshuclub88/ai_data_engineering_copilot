from pathlib import Path
from dbmeta import FolderDB


def list_jobs(data_root):
    """
    Return all job directories under DATA_ROOT.
    """

    root = Path(data_root)

    if not root.exists():
        return []

    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def list_runs(job_path):
    """
    Return all RUN_xxx directories for a job.
    """

    job = Path(job_path)

    if not job.exists():
        return []

    return sorted(
        path.name
        for path in job.iterdir()
        if path.is_dir() and path.name.startswith("RUN_")
    )


def get_db(job_path):
    """
    Create a DbMeta database for one job.

    Each job has its own FolderDB.
    """

    return FolderDB(
        base_path=str(job_path),
        base_metadata="metadata.json",
    )


def get_tables(db):
    """
    Return all tables discovered by DbMeta.

    DbMeta is the source of truth.
    No hardcoded table list is required.
    """

    return list(db.tables.keys())


def query(db, sql):
    """
    Execute DbMeta SQL and return materialized rows.

    DbMeta returns TableQuery from db.sql().
    .all() converts it to list[dict].
    """

    return db.sql(sql).all()


def get_run(db, run_id):
    """
    Get all structured metadata for one run.

    Every table discovered by DbMeta is queried dynamically.
    """

    result = {}

    for table_name in db.tables.keys():
        result[table_name] = query(
            db,
            f"SELECT * FROM {table_name} WHERE iid = '{run_id}'",
        )

    return result


def get_recent_runs(db, limit=20):
    """
    Return the most recent pipeline executions.
    """

    limit = max(1, int(limit))

    return query(
        db,
        "SELECT iid, status, failure_reason, start_time, duration_sec "
        "FROM execution "
        "ORDER BY start_time DESC "
        f"LIMIT {limit}",
    )


def get_failed_runs(db, limit=100):
    """
    Return failed runs ordered from newest to oldest.
    """

    limit = max(1, int(limit))

    return query(
        db,
        "SELECT iid, status, failure_reason, start_time, duration_sec "
        "FROM execution "
        "WHERE status = 'FAILED' "
        "ORDER BY start_time DESC "
        f"LIMIT {limit}",
    )


def get_job_summary(db):
    """
    Return basic success/failure counts.
    """

    rows = query(
        db,
        "SELECT status, COUNT(*) AS run_count "
        "FROM execution "
        "GROUP BY status",
    )

    summary = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "other": 0,
    }

    for row in rows:
        status = str(row.get("status", "")).upper()
        count = int(row.get("run_count", 0) or 0)

        summary["total"] += count

        if status == "SUCCESS":
            summary["success"] += count
        elif status == "FAILED":
            summary["failed"] += count
        else:
            summary["other"] += count

    return summary


def get_table_sample(db, table_name, limit=5):
    """
    Return a small sample from a DbMeta table.

    Useful for debugging and Copilot schema discovery.
    """

    if table_name not in db.tables:
        raise ValueError(f"Unknown DbMeta table: {table_name}")

    limit = max(1, int(limit))

    return query(
        db,
        f"SELECT * FROM {table_name} LIMIT {limit}",
    )