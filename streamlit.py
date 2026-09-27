import os
import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

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

DATA_ROOT = Path(
    os.getenv("DATA_ROOT", "./jobs")
).resolve()

st.set_page_config(
    page_title="AI Data Engineering Copilot",
    layout="wide",
)

st.title("AI Data Engineering Copilot")


def home():
    st.session_state.pop("job", None)
    st.session_state.pop("run", None)
    st.rerun()


def clear_run():
    st.session_state.pop("run", None)
    st.rerun()


@st.dialog("Run Details", width="large")
def show_run_dialog(job_path, run_id):
    run_path = job_path / run_id
    db = get_db(job_path)
    data = get_run(db, run_id)

    execution_rows = data.get("execution", [])
    execution = execution_rows[0] if execution_rows else {}

    status = execution.get("status", "UNKNOWN")
    start_time = execution.get("start_time", "N/A")
    end_time = execution.get("end_time", "N/A")
    duration = execution.get("duration_sec", "N/A")

    if status == "FAILED":
        st.error(f"🔴 FAILED  •  {run_id}")
    elif status == "SUCCESS":
        st.success(f"🟢 SUCCESS  •  {run_id}")
    else:
        st.info(f"🟡 {status}  •  {run_id}")

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("Run ID")
        st.write(run_id)

        st.caption("Start Time")
        st.write(start_time)

    with col2:
        st.caption("End Time")
        st.write(end_time)

        st.caption("Duration")
        st.write(f"{duration} sec")

    with col3:
        st.caption("Status")
        st.write(status)

        st.caption("Job")
        st.write(job_path.name)

    st.divider()

    logs_col, rca_col = st.columns(2)

    with logs_col:
        show_logs = st.toggle(
            "📄 View Logs",
            key=f"logs_{run_id}",
        )

    with rca_col:
        generate_rca_clicked = st.button(
            "🟢 Generate RCA",
            key=f"generate_rca_{run_id}",
            width="stretch",
        )

    if show_logs:
        st.divider()

        st.subheader("Execution Log")

        execution_log = run_path / "execution.log"

        if execution_log.exists():
            st.code(
                execution_log.read_text(
                    errors="replace"
                ),
                language="text",
            )
        else:
            st.info("Execution log not found.")

    if generate_rca_clicked:
        with st.spinner("Generating RCA..."):
            rca = generate_rca(
                run_path,
                run_id,
                job_path.name,
            )

        st.session_state[f"rca_{run_id}"] = rca

    rca = st.session_state.get(f"rca_{run_id}")

    if rca is not None:
        st.divider()

        st.subheader("Root Cause Analysis")

        error_log = run_path / "error.log"

        if error_log.exists():
            st.caption("Error Log")

            st.code(
                error_log.read_text(
                    errors="replace"
                ),
                language="text",
            )
        else:
            st.info("Error log not found.")

        st.divider()

        error_col, root_cause_col = st.columns(2)

        with error_col:
            st.caption("Error")
            st.write(
                rca.get("error", "N/A")
            )

        with root_cause_col:
            st.caption("Root Cause")
            st.write(
                rca.get("root_cause", "N/A")
            )

        st.caption("Evidence")
        st.write(
            rca.get("evidence", "N/A")
        )

        st.caption("Recommended Fix")
        st.write(
            rca.get("fix", "N/A")
        )

        st.divider()

        metadata_col, _ = st.columns([1, 4])

        with metadata_col:
            with st.popover("📋 Metadata"):
                st.json(data)


@st.dialog("AI Copilot", width="large")
def show_copilot(db, job_path):
    st.subheader("Pipeline Investigation")

    question = st.text_area(
        "Ask about this pipeline",
        placeholder=(
            "Why are failures increasing?\n"
            "What caused RUN_001 to fail?\n"
            "Show me the failed runs."
        ),
        height=120,
    )

    if st.button(
        "Run Investigation",
        type="primary",
        width="stretch",
    ):
        if not question.strip():
            st.warning("Please enter a question.")
            return

        with st.spinner("Investigating..."):
            try:
                result = ask_copilot(
                    db,
                    question,
                    job_path,
                )
            except Exception as e:
                st.error(str(e))
                return

        st.divider()

        st.subheader("Answer")
        st.markdown(result["answer"])

        with st.expander("Investigation Plan"):
            st.json(result["plan"])

        if result["queries"]:
            st.subheader("Evidence")

            for query_result in result["queries"]:
                with st.expander(
                    f"SQL {query_result['id']} — "
                    f"{query_result['purpose']}"
                ):
                    st.code(
                        query_result["sql"],
                        language="sql",
                    )

                    if "error" in query_result:
                        st.error(
                            query_result["error"]
                        )
                    else:
                        st.dataframe(
                            query_result["result"],
                            width="stretch",
                        )

        if result["rcas"]:
            st.subheader("RCA")

            for rca in result["rcas"]:
                with st.expander(
                    f"RCA — {rca['run_id']}"
                ):
                    st.json(rca["rca"])


def show_job(job_name):
    job_path = DATA_ROOT / job_name
    db = get_db(job_path)
    summary = get_job_summary(db)

    st.button(
        "← Back to Jobs",
        on_click=home,
    )

    st.header(job_name)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Runs",
            summary["total"],
        )

    with col2:
        st.metric(
            "Success",
            summary["success"],
        )

    with col3:
        st.metric(
            "Failed",
            summary["failed"],
        )

    with col4:
        st.metric(
            "Other",
            summary["other"],
        )

    st.divider()

    copilot_col, _ = st.columns([1, 5])

    with copilot_col:
        if st.button(
            "🤖 Copilot",
            type="primary",
            width="stretch",
        ):
            show_copilot(
                db,
                job_path,
            )

    st.divider()

    st.subheader("Recent Runs")

    runs = get_recent_runs(db)
    runs = runs[:365]

    if not runs:
        st.info("No runs found.")
        return

    for run in runs:
        run_id = run.get(
            "iid",
            "UNKNOWN",
        )

        status = run.get(
            "status",
            "UNKNOWN",
        )

        if status == "FAILED":
            status_icon = "🔴"
        elif status == "SUCCESS":
            status_icon = "🟢"
        else:
            status_icon = "🟡"

        col1, col2, col3, col4 = st.columns(
            [1.5, 1.5, 2, 1]
        )

        with col1:
            st.write(
                f"**{status_icon} {run_id}**"
            )

        with col2:
            st.write(status)

        with col3:
            st.write(
                run.get(
                    "start_time",
                    "",
                )
            )

        with col4:
            if st.button(
                "View",
                key=f"run_{run_id}",
            ):
                show_run_dialog(
                    job_path,
                    run_id,
                )


jobs = list_jobs(DATA_ROOT)

if not jobs:
    st.warning(
        f"No jobs found in {DATA_ROOT}. "
        "Set DATA_ROOT in .env."
    )

elif "job" not in st.session_state:
    st.subheader("Jobs")

    for job_name in jobs:
        if st.button(
            job_name,
            width="stretch",
        ):
            st.session_state["job"] = job_name
            st.rerun()

else:
    show_job(
        st.session_state["job"]
    )