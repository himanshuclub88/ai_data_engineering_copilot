# Phase 4 — Streamlit Copilot UI

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The default data directory is:

```text
data/synthetic_runs
```

Override it with:

```text
RUNS_PATH=/path/to/synthetic_runs
```

## UI

- **Copilot** — natural-language LangGraph investigation.
- **RCA** — deterministic root-cause analysis and evidence.
- **Metadata** — raw run metadata and read-only DbMeta SQL.
- **Logs** — execution and error logs.

The RCA, metadata and log views do not require an LLM. The Copilot tab requires the provider configuration from `.env.example`.
