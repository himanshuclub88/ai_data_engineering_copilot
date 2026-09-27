import os
from pathlib import Path
from copy import deepcopy
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dbmeta_adapter import (
    list_jobs,
    get_db,
    get_recent_runs,
    get_run,
    get_job_summary,
)
from copilot import ask_copilot
from rca import generate_rca


load_dotenv()

DATA_ROOT = Path(os.getenv("DATA_ROOT", "./jobs")).resolve()

app = FastAPI(
    title="AI Data Engineering Copilot API",
    description="Backend API for the AI Data Engineering Copilot.",
    version="1.0.0",
)

# Temporary CORS configuration for local frontend development.
# Restrict this to your actual frontend origin before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CopilotRequest(BaseModel):
    question: str = Field(..., min_length=1)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def get_job_path(job_name: str) -> Path:
    """Resolve a job directory without allowing paths outside DATA_ROOT."""
    job_path = (DATA_ROOT / job_name).resolve()

    try:
        job_path.relative_to(DATA_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job name")

    if not job_path.exists() or not job_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Job not found: {job_name}")

    return job_path


def make_json_safe(value: Any) -> Any:
    """Convert pandas/numpy/Python objects into JSON-compatible values."""
    if isinstance(value, pd.DataFrame):
        return [make_json_safe(row) for row in value.to_dict(orient="records")]

    if isinstance(value, pd.Series):
        return [make_json_safe(item) for item in value.tolist()]

    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    # numpy scalar support without requiring numpy as a direct dependency.
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass

    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except (ValueError, TypeError):
            pass

    return value


def load_run(job_name: str, run_id: str):
    job_path = get_job_path(job_name)
    db = get_db(job_path)

    try:
        data = get_run(db, run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Run not found: {run_id}",
        )

    return job_path, data


# -----------------------------------------------------------------------------
# Health / root
# -----------------------------------------------------------------------------


@app.get("/")
def root():
    return {
        "name": "AI Data Engineering Copilot API",
        "version": app.version,
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_root": str(DATA_ROOT),
    }


# -----------------------------------------------------------------------------
# Jobs
# -----------------------------------------------------------------------------


@app.get("/api/jobs")
def get_jobs():
    """Return the same jobs discovered by the Streamlit application."""
    try:
        jobs = list_jobs(DATA_ROOT)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "jobs": jobs,
        "count": len(jobs),
    }


@app.get("/api/jobs/{job_name}/summary")
def get_job_summary_api(job_name: str):
    job_path = get_job_path(job_name)

    try:
        db = get_db(job_path)
        summary = get_job_summary(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return make_json_safe(summary)


# -----------------------------------------------------------------------------
# Runs
# -----------------------------------------------------------------------------


@app.get("/api/jobs/{job_name}/runs")
def get_runs(
    job_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=365),
):
    """
    Return paginated runs.

    The existing Streamlit application loads recent runs, limits them to 365,
    and then performs pagination. This endpoint keeps that behavior.
    """
    job_path = get_job_path(job_name)

    try:
        db = get_db(job_path)
        runs = get_recent_runs(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    runs = runs[:365]
    total_runs = len(runs)
    total_pages = max(1, (total_runs + page_size - 1) // page_size)

    if page > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page} does not exist. Total pages: {total_pages}",
        )

    start = (page - 1) * page_size
    end = start + page_size
    page_runs = runs[start:end]

    # Preserve the Streamlit behavior of filling missing execution details.
    normalized_runs = []

    for run in page_runs:
        run = dict(run)
        run_id = run.get("iid", "UNKNOWN")

        status = run.get("status", "UNKNOWN")
        start_time = run.get("start_time", "N/A")
        end_time = run.get("end_time")
        duration = run.get("duration_sec", "N/A")

        if not end_time:
            try:
                run_data = get_run(db, run_id)
                execution_rows = run_data.get("execution", [])

                if execution_rows:
                    execution = execution_rows[0]
                    start_time = execution.get("start_time", start_time)
                    end_time = execution.get("end_time", end_time)
                    duration = execution.get("duration_sec", duration)
                    status = execution.get("status", status)
            except Exception:
                # Same behavior as the current Streamlit code: ignore lookup
                # failures and keep the values already available.
                pass

        run["iid"] = run_id
        run["status"] = status
        run["start_time"] = start_time
        run["end_time"] = end_time
        run["duration_sec"] = duration

        normalized_runs.append(make_json_safe(run))

    return {
        "page": page,
        "page_size": page_size,
        "total": total_runs,
        "total_pages": total_pages,
        "showing": {
            "from": start + 1 if total_runs else 0,
            "to": min(end, total_runs),
        },
        "runs": normalized_runs,
    }


@app.get("/api/jobs/{job_name}/runs/{run_id}")
def get_run_details(job_name: str, run_id: str):
    """Return complete run metadata used by the Run Details dialog."""
    job_path, data = load_run(job_name, run_id)

    execution_rows = data.get("execution", [])
    execution = execution_rows[0] if execution_rows else {}

    return {
        "run_id": run_id,
        "job": job_path.name,
        "status": execution.get("status", "UNKNOWN"),
        "start_time": execution.get("start_time", "N/A"),
        "end_time": execution.get("end_time", "N/A"),
        "duration_sec": execution.get("duration_sec", "N/A"),
        "data": make_json_safe(data),
    }


@app.get("/api/jobs/{job_name}/runs/{run_id}/metadata")
def get_run_metadata(job_name: str, run_id: str):
    """Return the complete metadata object shown by the Streamlit Metadata popover."""
    _, data = load_run(job_name, run_id)
    return make_json_safe(data)


@app.get("/api/jobs/{job_name}/runs/{run_id}/logs")
def get_run_logs(job_name: str, run_id: str):
    """Return execution.log and error.log content for a run."""
    job_path = get_job_path(job_name)
    run_path = job_path / run_id

    if not run_path.exists() or not run_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    execution_log = run_path / "execution.log"
    error_log = run_path / "error.log"

    def read_log(path: Path):
        if not path.exists():
            return None
        return path.read_text(errors="replace")

    return {
        "run_id": run_id,
        "execution_log": read_log(execution_log),
        "error_log": read_log(error_log),
    }


# -----------------------------------------------------------------------------
# RCA
# -----------------------------------------------------------------------------


@app.post("/api/jobs/{job_name}/runs/{run_id}/rca")
def generate_run_rca(job_name: str, run_id: str):
    """Generate RCA using the same existing generate_rca function."""
    job_path = get_job_path(job_name)
    run_path = job_path / run_id

    if not run_path.exists() or not run_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    try:
        rca = generate_rca(
            run_path,
            run_id,
            job_path.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "run_id": run_id,
        "rca": make_json_safe(rca),
    }


# -----------------------------------------------------------------------------
# AI Copilot
# -----------------------------------------------------------------------------


@app.post("/api/jobs/{job_name}/copilot")
def run_copilot(job_name: str, request: CopilotRequest):
    """Run the existing AI Copilot investigation flow."""
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    job_path = get_job_path(job_name)

    try:
        db = get_db(job_path)
        result = ask_copilot(
            db,
            question,
            job_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # The current Streamlit UI creates a display version of the plan by
    # renaming sql -> SQL and adding an action field. Preserve that behavior
    # while also returning the original result.
    response = deepcopy(result)

    plan = response.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("queries"), list):
        for query in plan["queries"]:
            if isinstance(query, dict):
                query["action"] = "Data sets created for analytics"
                if "sql" in query:
                    query["SQL"] = query.pop("sql")

    return make_json_safe(response)
