# AI Data Engineering Copilot — Synthetic Data

This dataset is designed to be consumed by DbMeta.

## Run structure

Each pipeline run has:

- `metadata.json` — structured metadata for DbMeta
- `execution.log` — normal execution timeline
- `error.log` — scenario-specific failure evidence
- `audit.json` — auxiliary audit information

Example:

```python
from dbmeta import FolderDB

db = FolderDB(
    base_path="data/synthetic_runs",
    base_metadata="metadata.json"
)

print(db.tables.keys())
print(db.execution.all())
print(db.input.all())
print(db.resources.all())
```

## Important

The generated metadata and logs are correlated. A `DATA_SKEW` run, for example,
contains skew-related resource metrics and a corresponding log/error message.

## Current scenarios

- SUCCESS
- SCHEMA_MISMATCH
- PARTITION_MISSING
- OUT_OF_MEMORY
- DATA_SKEW
- SOURCE_TIMEOUT
- BAD_FILE_FORMAT
- PERMISSION_DENIED
- DUPLICATE_DATA
- NULL_SPIKE


## Phase 2 — Data + Log + RCA layers

```text
DbMetaAdapter
     |
     +---- structured metadata / SQL
     |
LogReader
     |
     +---- execution.log / error.log
     |
RCAEngine
     |
     +---- correlated evidence
     |
CopilotTools
     |
     +---- interface for future LangGraph agents
```

The RCA engine is intentionally deterministic at this stage. The next layer
will put LangGraph/LLM reasoning on top of these tools.

## Phase 3 — LangGraph Agent

Phase 3 adds an LLM-driven orchestration layer without replacing the deterministic evidence layer.

```text
User question
     |
     v
 LangGraph Agent
     |
     +---- inspect_run ------> metadata + execution/error logs
     +---- query_metadata ---> DbMeta SQL
     +---- search_logs ------> execution.log / error.log
     +---- diagnose_run -----> deterministic RCA
     |
     v
 Evidence-grounded answer
```

### Run

1. Install dependencies from `requirements.txt`.
2. Make the user's `DbMeta` package/source importable as `dbmeta`.
3. Copy `.env.example` to `.env` and configure the chosen provider.
4. Run from this project directory:

```bash
python run_agent.py
```

Example questions:

- `Why did RUN_000005 fail?`
- `What evidence supports the root cause of RUN_000005?`
- `Find failed runs caused by schema mismatch.`
- `Compare the resource behavior of RUN_000005 with a successful run.`

The LLM is deliberately not trusted to calculate the RCA itself. It calls the deterministic tools and synthesizes their returned evidence.
