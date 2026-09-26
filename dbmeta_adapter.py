from pathlib import Path
from dbmeta import FolderDB

def list_jobs(data_root):
    root = Path(data_root)
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")) if root.exists() else []

def list_runs(job_path):
    p = Path(job_path)
    return sorted(x.name for x in p.iterdir() if x.is_dir() and x.name.startswith("RUN_")) if p.exists() else []

def get_db(job_path): return FolderDB(base_path=str(job_path), base_metadata="metadata.json")
def get_tables(db): return list(db.tables.keys())
def query(db, sql): return db.sql(sql).all()
def get_run(db, run_id): return {t: query(db, f"SELECT * FROM {t} WHERE iid = '{run_id}'") for t in db.tables.keys()}

def get_recent_runs(db, limit=20):
    return query(db, f"SELECT iid, status, failure_reason, start_time, duration_sec FROM execution ORDER BY start_time DESC LIMIT {max(1, int(limit))}")

def get_failed_runs(db, limit=100):
    return query(db, f"SELECT iid, status, failure_reason, start_time, duration_sec FROM execution WHERE status = 'FAILED' ORDER BY start_time DESC LIMIT {max(1, int(limit))}")

def get_job_summary(db):
    rows = query(db, "SELECT status, COUNT(*) AS run_count FROM execution GROUP BY status")
    out = {"total": 0, "success": 0, "failed": 0, "other": 0}
    for r in rows:
        s, n = str(r.get("status", "")).upper(), int(r.get("run_count", 0) or 0)
        out["total"] += n
        out["success" if s == "SUCCESS" else "failed" if s == "FAILED" else "other"] += n
    return out

def get_table_sample(db, table_name, limit=5):
    if table_name not in db.tables: raise ValueError(f"Unknown DbMeta table: {table_name}")
    return query(db, f"SELECT * FROM {table_name} LIMIT {max(1, int(limit))}")
