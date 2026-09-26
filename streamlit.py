import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from dbmeta_adapter import (
    get_db,
    get_job_summary,
    get_recent_runs,
    get_run,
    get_tables,
    list_jobs,
)

from copilot import ask_copilot

from rca import run_rca


load_dotenv()


DATA_ROOT = Path(
    os.getenv(
        "DATA_ROOT",
        "./jobs",
    )
).resolve()


def read_text(path):
    """
    Safely read a text file.
    """

    path = Path(path)

    if not path.exists():
        return f"{path.name} not found."

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def go_home():
    st.session_state.pop(
        "job",
        None,
    )

    st.session_state.pop(
        "run",
        None,
    )

    st.session_state.pop(
        "copilot_result",
        None,
    )

    st.rerun()


def go_job(job):
    st.session_state["job"] = job

    st.session_state.pop(
        "run",
        None,
    )

    st.session_state.pop(
        "copilot_result",
        None,
    )

    st.rerun()


def go_run(run_id):
    st.session_state["run"] = run_id
    st.rerun()


def show_home():
    st.title(
        "AI Data Engineering Copilot"
    )

    st.caption(
        "Pipeline execution intelligence "
        "powered by DbMeta + LLM"
    )

    if not DATA_ROOT.exists():
        st.error(
            f"DATA_ROOT does not exist:\n{DATA_ROOT}"
        )

        st.info(
            "Check DATA_ROOT in your .env file."
        )

        return

    jobs = list_jobs(
        DATA_ROOT
    )

    if not jobs:
        st.warning(
            f"No jobs found under:\n{DATA_ROOT}"
        )

        return

    st.subheader(
        "Jobs"
    )

    for job in jobs:

        if st.button(
            job,
            key=f"job_{job}",
            use_container_width=True,
        ):
            go_job(job)


def show_job(job):
    job_path = DATA_ROOT / job

    db = get_db(
        job_path
    )

    st.button(
        "← All Jobs",
        on_click=go_home,
    )

    st.title(job)

    # -----------------------------
    # Summary
    # -----------------------------

    summary = get_job_summary(
        db
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Runs",
        summary["total"],
    )

    col2.metric(
        "Successful",
        summary["success"],
    )

    col3.metric(
        "Failed",
        summary["failed"],
    )

    col4.metric(
        "Other",
        summary["other"],
    )

    # -----------------------------
    # Tables
    # -----------------------------

    with st.expander(
        "DbMeta Tables"
    ):
        st.write(
            get_tables(db)
        )

    st.divider()

    # -----------------------------
    # Recent Runs
    # -----------------------------

    st.subheader(
        "Recent Runs"
    )

    rows = get_recent_runs(
        db,
        20,
    )

    if not rows:
        st.info(
            "No execution records found."
        )

    else:

        for row in rows:

            run_id = row.get(
                "iid",
                "-",
            )

            status = row.get(
                "status",
                "-",
            )

            failure = row.get(
                "failure_reason"
            ) or "SUCCESS"

            start_time = row.get(
                "start_time",
                "-",
            )

            duration = row.get(
                "duration_sec",
                "-",
            )

            label = (
                f"{run_id} | "
                f"{status} | "
                f"{failure} | "
                f"{start_time} | "
                f"{duration}s"
            )

            if st.button(
                label,
                key=f"run_{job}_{run_id}",
                use_container_width=True,
            ):
                go_run(
                    run_id
                )

    st.divider()

    # -----------------------------
    # Copilot
    # -----------------------------

    st.subheader(
        "🤖 Copilot"
    )

    question = st.text_input(
        "Ask about this job's history",
        placeholder=(
            "Why did the latest run fail?"
        ),
        key=f"question_{job}",
    )

    if st.button(
        "Ask Copilot",
        type="primary",
    ):

        if not question.strip():

            st.warning(
                "Enter a question first."
            )

        else:

            with st.spinner(
                "Analyzing job history..."
            ):

                try:

                    result = ask_copilot(
                        db,
                        question,
                    )

                    st.session_state[
                        "copilot_result"
                    ] = result

                except Exception as exc:

                    st.error(
                        f"Copilot error: {exc}"
                    )

    result = st.session_state.get(
        "copilot_result"
    )

    if result:

        st.markdown(
            "### Answer"
        )

        st.write(
            result["answer"]
        )

        with st.expander(
            "Generated DbMeta SQL"
        ):

            st.code(
                result["sql"],
                language="sql",
            )

        with st.expander(
            "DbMeta Result"
        ):

            st.json(
                result["result"]
            )


def show_run(
    job,
    run_id,
):
    job_path = DATA_ROOT / job

    run_path = (
        job_path / run_id
    )

    db = get_db(
        job_path
    )

    st.button(
        "← Back to Job",
        on_click=lambda: (
            st.session_state.pop(
                "run",
                None,
            ),
            st.rerun(),
        ),
    )

    st.title(
        f"{job} / {run_id}"
    )

    # -----------------------------
    # Metadata
    # -----------------------------

    metadata = get_run(
        db,
        run_id,
    )

    tab_metadata, tab_execution, tab_error, tab_rca = st.tabs(
        [
            "Metadata",
            "Execution Log",
            "Error Log",
            "RCA",
        ]
    )

    # -----------------------------
    # Metadata
    # -----------------------------

    with tab_metadata:

        st.json(
            metadata
        )

    # -----------------------------
    # Execution Log
    # -----------------------------

    with tab_execution:

        st.code(
            read_text(
                run_path / "execution.log"
            )
        )

    # -----------------------------
    # Error Log
    # -----------------------------

    with tab_error:

        st.code(
            read_text(
                run_path / "error.log"
            )
        )

    # -----------------------------
    # RCA
    # -----------------------------

    with tab_rca:

        cached_path = (
            run_path /
            "rca_analysis.json"
        )

        if cached_path.exists():

            st.success(
                "Cached RCA loaded. "
                "No LLM call required."
            )

            st.json(
                json.loads(
                    cached_path.read_text(
                        encoding="utf-8"
                    )
                )
            )

        else:

            st.info(
                "RCA has not been generated "
                "for this run."
            )

            if st.button(
                "Generate RCA",
                type="primary",
            ):

                with st.spinner(
                    "Analyzing error log..."
                ):

                    try:

                        analysis = run_rca(
                            run_path,
                            run_id,
                            metadata,
                        )

                        st.success(
                            "RCA generated "
                            "and cached."
                        )

                        st.json(
                            analysis
                        )

                    except Exception as exc:

                        st.error(
                            f"RCA error: {exc}"
                        )


def main():

    st.set_page_config(
        page_title=(
            "AI Data Engineering Copilot"
        ),
        page_icon="🤖",
        layout="wide",
    )

    if "job" not in st.session_state:

        show_home()

    elif "run" in st.session_state:

        show_run(
            st.session_state["job"],
            st.session_state["run"],
        )

    else:

        show_job(
            st.session_state["job"]
        )


if __name__ == "__main__":
    main()