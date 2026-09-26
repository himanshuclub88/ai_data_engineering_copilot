"""Streamlit UI for the AI Data Engineering Copilot."""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agents.copilot_tools import CopilotTools

load_dotenv()

ROOT = Path(__file__).resolve().parent
RUNS_PATH = Path(os.getenv("RUNS_PATH", ROOT / "data" / "synthetic_runs"))

st.set_page_config(page_title="AI Data Engineering Copilot", page_icon="🛠️", layout="wide")


def get_copilot() -> CopilotTools:
    return CopilotTools(RUNS_PATH)


@st.cache_resource
def cached_copilot():
    return get_copilot()


def run_ids(copilot: CopilotTools):
    return sorted(
        p.name for p in RUNS_PATH.iterdir() if p.is_dir() and p.name.startswith("RUN_")
    )


def status_value(metadata):
    return metadata.get("execution", {}).get("status", "UNKNOWN")


def make_graph(copilot):
    """Build the LLM graph only when an LLM is configured."""
    from agents.graph import build_graph
    from llm_factory import create_llm

    return build_graph(copilot, create_llm())


st.title("🛠️ AI Data Engineering Copilot")
st.caption("DbMeta + pipeline logs + deterministic RCA + LangGraph reasoning")

copilot = cached_copilot()
ids = run_ids(copilot)

if not ids:
    st.error(f"No synthetic runs found under: {RUNS_PATH}")
    st.stop()

with st.sidebar:
    st.header("Run Explorer")
    selected_run = st.selectbox("Pipeline run", ids)
    metadata = copilot.load_metadata(selected_run)
    execution = metadata.get("execution", {})
    pipeline = metadata.get("pipeline", {})

    st.metric("Status", execution.get("status", "UNKNOWN"))
    st.write(f"**Pipeline:** {pipeline.get('name', '-')}")
    st.write(f"**Failure:** {execution.get('failure_reason') or 'None'}")
    st.divider()
    st.write("**Data path**")
    st.code(str(RUNS_PATH), language="text")


tab1, tab2, tab3, tab4 = st.tabs(["💬 Copilot", "🔎 RCA", "📊 Metadata", "📜 Logs"])

with tab1:
    st.subheader("Ask the Data Engineering Copilot")
    examples = [
        f"Why did {selected_run} fail?",
        f"Inspect {selected_run} and explain the strongest evidence.",
        f"What should I check first for {selected_run}?",
        "What are the common failure reasons across the available runs?",
    ]
    example = st.selectbox("Example question", ["Custom question"] + examples)
    question = st.text_area(
        "Question",
        value="" if example == "Custom question" else example,
        height=100,
        placeholder="e.g. Why did RUN_000005 fail and what evidence supports the RCA?",
    )

    if st.button("Run Copilot", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.spinner("Investigating metadata and logs..."):
                    graph = make_graph(copilot)
                    answer = graph.invoke({"messages": [{"role": "user", "content": question}]})
                    messages = answer.get("messages", [])
                    final = messages[-1].content if messages else "No answer returned."
                st.markdown(final)
            except Exception as exc:
                st.error("The LLM/LangGraph layer could not run.")
                st.code(str(exc))
                st.info("The deterministic RCA tab remains available without an LLM configuration.")

with tab2:
    st.subheader(f"Deterministic RCA — {selected_run}")
    diagnosis = copilot.diagnose(selected_run)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Detected root cause", diagnosis.get("root_cause", "UNKNOWN"))
    with c2:
        st.metric("Run status", status_value(metadata))

    st.markdown("### Evidence")
    evidence = diagnosis.get("evidence", [])
    if evidence:
        for item in evidence:
            st.write(f"- {item}")
    else:
        st.info("No deterministic evidence was returned.")

    st.markdown("### Log evidence")
    logs = diagnosis.get("log_evidence", [])
    if logs:
        for item in logs:
            st.code(item)
    else:
        st.info("No matching log evidence was returned.")

    st.markdown("### Raw RCA result")
    st.json(diagnosis)

with tab3:
    st.subheader(f"DbMeta-backed metadata — {selected_run}")
    st.json(metadata)

    st.markdown("### Read-only DbMeta query")
    sql = st.text_area(
        "SQL",
        value=f"SELECT * FROM execution WHERE iid = '{selected_run}'",
        height=90,
    )
    if st.button("Run DbMeta Query"):
        try:
            result = copilot.db.sql(sql)
            st.json(result)
        except Exception as exc:
            st.error(str(exc))

with tab4:
    st.subheader(f"Logs — {selected_run}")
    execution_log = copilot.logs.read(selected_run, "execution.log")
    error_log = copilot.logs.read(selected_run, "error.log")
    left, right = st.columns(2)
    with left:
        st.markdown("**execution.log**")
        st.code(execution_log or "(empty)", language="text")
    with right:
        st.markdown("**error.log**")
        st.code(error_log or "(empty)", language="text")
