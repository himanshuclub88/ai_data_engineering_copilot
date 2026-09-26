"""
Streamlit UI for the AI Data Engineering Copilot.

Jobs -> Runs -> Metadata / Logs / RCA
Job page -> Copilot
"""

import json
import os
from pathlib import Path

import streamlit as st
from openai import AzureOpenAI

from dbmeta_adapter import get_db, get_run, get_recent_runs, list_jobs
from rca import run_rca
from copilot import ask_copilot
from agent_moudle import get_llm as call_llm



DATA_ROOT = Path(os.getenv("DATA_ROOT"))




def show_home():
    st.title("AI Data Engineering Copilot")
    st.subheader("Jobs")

    for job in list_jobs(DATA_ROOT):
        if st.button(job, use_container_width=True):
            st.session_state["job"] = job
            st.session_state.pop("run", None)
            st.rerun()


def show_job(job):
    st.title(job)

    db = get_db(DATA_ROOT / job)

    st.subheader("Recent Runs")

    for row in get_recent_runs(db, 20):
        run_id = row.get("iid")
        status = row.get("status")
        failure = row.get("failure_reason") or "-"

        if st.button(
            f"{run_id} | {status} | {failure}",
            use_container_width=True,
        ):
            st.session_state["run"] = run_id
            st.rerun()

    st.divider()
    st.subheader("Copilot")

    question = st.text_input(
        "Ask anything about this job's history",
        placeholder="Why did the latest run fail?",
    )

    if st.button("Ask Copilot") and question:
        with st.spinner("Analyzing job history..."):
            result = ask_copilot(call_llm, db, question)

        st.write(result["answer"])

        with st.expander("DbMeta SQL"):
            st.code(result["sql"], language="sql")

        with st.expander("Raw DbMeta Result"):
            st.json(result["result"])


def show_run(job, run_id):
    st.title(f"{job} / {run_id}")

    job_path = DATA_ROOT / job
    run_path = job_path / run_id
    db = get_db(job_path)
    metadata = get_run(db, run_id)

    tab_meta, tab_log, tab_error, tab_rca = st.tabs(
        ["Metadata", "Execution Log", "Error Log", "RCA"]
    )

    with tab_meta:
        st.json(metadata)

    with tab_log:
        st.code((run_path / "execution.log").read_text(encoding="utf-8"))

    with tab_error:
        st.code((run_path / "error.log").read_text(encoding="utf-8"))

    with tab_rca:
        cached = run_path / "rca_analysis.json"

        if cached.exists():
            st.success("Cached RCA loaded. No LLM call required.")
            st.json(json.loads(cached.read_text(encoding="utf-8")))
        elif st.button("Generate RCA"):
            with st.spinner("Analyzing error log..."):
                analysis = run_rca(
                    run_path,
                    run_id,
                    metadata,
                    call_llm,
                )
            st.json(analysis)

    if st.button("← Back to Job"):
        st.session_state.pop("run", None)
        st.rerun()


def main():
    st.set_page_config(
        page_title="AI Data Engineering Copilot",
        layout="wide",
    )

    if "job" not in st.session_state:
        show_home()
    elif "run" in st.session_state:
        show_run(st.session_state["job"], st.session_state["run"])
    else:
        show_job(st.session_state["job"])


if __name__ == "__main__":
    main()
