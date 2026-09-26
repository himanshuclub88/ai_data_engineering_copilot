import os, json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from dbmeta_adapter import list_jobs, get_db, get_tables, get_recent_runs, get_run, get_job_summary
from copilot import ask_copilot
from rca import generate_rca

load_dotenv(); DATA_ROOT = Path(os.getenv("DATA_ROOT", "./jobs")).resolve()
st.set_page_config(page_title="AI Data Engineering Copilot", layout="wide")
st.title("AI Data Engineering Copilot")

def home():
    st.session_state.pop("job", None); st.session_state.pop("run", None); st.rerun()

def job():
    st.session_state.pop("run", None); st.rerun()

def show_run(job_path, run_id):
    p = job_path / run_id; data = get_run(get_db(job_path), run_id)
    st.button("← Back to Job", on_click=job); st.header(run_id)
    tabs = st.tabs(["Metadata", "Execution Log", "Error Log", "RCA"])
    with tabs[0]:
        for name, rows in data.items(): st.subheader(name); st.dataframe(rows, use_container_width=True)
    with tabs[1]:
        f = p / "execution.log"; st.code(f.read_text(errors="replace") if f.exists() else "execution.log not found")
    with tabs[2]:
        f = p / "error.log"; st.code(f.read_text(errors="replace") if f.exists() else "error.log not found")
    with tabs[3]:
        if st.button("Generate / Refresh RCA"): st.session_state["rca"] = generate_rca(p, run_id, job_path.name)
        rca = st.session_state.get("rca")
        if not rca and (p / "rca_analysis.json").exists():
            try: rca = json.loads((p / "rca_analysis.json").read_text())
            except Exception: rca = None
        if rca:
            st.write("**Error:**", rca.get("error")); st.write("**Root Cause:**", rca.get("root_cause")); st.write("**Evidence:**", rca.get("evidence")); st.write("**Fix:**", rca.get("fix"))
        else: st.info("No RCA generated yet.")

def show_job(job_name):
    path = DATA_ROOT / job_name; db = get_db(path); s = get_job_summary(db)
    st.button("← Back to Jobs", on_click=home); st.header(job_name)
    a,b,c,d = st.columns(4); a.metric("Runs", s["total"]); b.metric("Success", s["success"]); c.metric("Failed", s["failed"]); d.metric("Other", s["other"])
    st.subheader("DbMeta Tables"); st.write(get_tables(db))
    st.subheader("Recent Runs"); st.dataframe(get_recent_runs(db), use_container_width=True)
    st.divider(); st.subheader("Copilot")
    q = st.text_input("Ask about this pipeline", placeholder="Why are failures increasing?")
    if q:
        with st.spinner("Investigating..."):
            try: result = ask_copilot(db, q, path)
            except Exception as e: st.error(str(e)); return
        st.markdown(result["answer"])
        with st.expander("Investigation Plan"): st.json(result["plan"])
        for x in result["queries"]:
            with st.expander(f"SQL {x['id']} — {x['purpose']}"):
                st.code(x["sql"], language="sql")
                if "error" in x: st.error(x["error"])
                else: st.dataframe(x["result"], use_container_width=True)
        for x in result["rcas"]:
            with st.expander(f"RCA — {x['run_id']}"): st.json(x["rca"])
    st.divider(); st.subheader("Open Run")
    runs = [r["iid"] for r in get_recent_runs(db)]
    if runs:
        selected = st.selectbox("Run", runs)
        if st.button("Open Run"): st.session_state["run"] = selected; st.rerun()

jobs = list_jobs(DATA_ROOT)
if not jobs: st.warning(f"No jobs found in {DATA_ROOT}. Set DATA_ROOT in .env.")
elif "job" not in st.session_state:
    st.subheader("Jobs")
    for x in jobs:
        if st.button(x, use_container_width=True): st.session_state["job"] = x; st.rerun()
elif "run" in st.session_state: show_run(DATA_ROOT / st.session_state["job"], st.session_state["run"])
else: show_job(st.session_state["job"])
