# AI Data Engineering Copilot

An AI-powered Data Engineering Copilot for investigating pipeline executions, failures, data-quality issues, and root causes.

The system combines **DbMeta**, **LLM-powered investigation planning**, **multiple SQL queries**, **pipeline logs**, and **automatically generated RCA** into a simple Streamlit application.

---

## Overview

The Copilot is designed around a real-world data engineering workflow:

```text
Pipeline Runs
     │
     ├── Metadata
     ├── Execution Logs
     ├── Error Logs
     └── RCA
          │
          ▼
      DbMeta
          │
          ▼
       Copilot
          │
     ┌────┴────┐
     │         │
   SQL       RCA
     │         │
     └────┬────┘
          ▼
     Investigation
          │
          ▼
       Answer
```

Instead of generating only one SQL query, the Copilot can create a small investigation plan containing **multiple focused SQL queries**.

If the question is related to a failure, the Copilot can also use an existing RCA or generate a new RCA from the run's `error.log`.

---

# Key Features

### 1. Multi-SQL Investigation

The Copilot can generate **1–5 SQL queries** for a single question.

For example:

> Why are failures increasing in this pipeline?

It may investigate:

```text
SQL 1 → Recent failed runs
SQL 2 → Failure reason distribution
SQL 3 → Data-quality problems
SQL 4 → Recent execution duration
```

The results are then combined before generating the final answer.

---

### 2. RCA Integration

The Copilot can identify questions related to:

* Root cause
* Failure cause
* Errors
* RCA
* Failure investigation
* Specific failed runs

For example:

> Why did RUN_087 fail?

The Copilot can:

```text
Identify RUN_087
       ↓
Check rca_analysis.json
       ↓
If missing
       ↓
Read error.log
       ↓
Generate RCA
       ↓
Use RCA in final answer
```

---

### 3. Automatic RCA Generation

For every run:

```text
RUN_087/
├── metadata.json
├── execution.log
├── error.log
└── rca_analysis.json
```

If `rca_analysis.json` does not exist, the RCA module can generate it from `error.log`.

Generated RCA contains:

```json
{
  "error": "...",
  "root_cause": "...",
  "evidence": [],
  "fix": "..."
}
```

The generated RCA is cached so it does not need to be regenerated every time.

---

### 4. DbMeta Integration

DbMeta provides the structured pipeline metadata.

The adapter dynamically discovers available tables:

```python
db.tables.keys()
```

The Copilot therefore does not depend on a hardcoded table list.

Example tables may include:

```text
pipeline
execution
input
output
resources
data_quality
spark
```

---

### 5. SQL Safety

The Copilot only allows read-only SQL.

Allowed:

```sql
SELECT ...
```

Blocked:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
REPLACE
MERGE
```

Multiple statements are also rejected.

Generated SQL is validated against the tables available in DbMeta before execution.

---

# Architecture

```text
                    User Question
                         │
                         ▼
                 ┌───────────────┐
                 │    Copilot    │
                 │    Planner    │
                 └───────┬───────┘
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          SQL #1       SQL #2      SQL #3
             │           │           │
             └───────────┼───────────┘
                         ▼
                    DbMeta Query
                         │
                         ▼
                      Results
                         │
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
          RCA Engine               Logs
             │                       │
             └───────────┬───────────┘
                         ▼
                  Combined Evidence
                         │
                         ▼
                  Answer Generator
                         │
                         ▼
                    Final Answer
```

---

# Project Structure

```text
ai_data_engineering_copilot/
│
├── jobs/
│   │
│   ├── SCAL_LABS_PIPELINE/
│   │   ├── RUN_001/
│   │   │   ├── metadata.json
│   │   │   ├── execution.log
│   │   │   ├── error.log
│   │   │   └── rca_analysis.json
│   │   │
│   │   ├── RUN_002/
│   │   └── ...
│   │
│   ├── HR_DATA_PLATFORM/
│   ├── SALES_DATA_PLATFORM/
│   ├── FINANCE_DATA_PLATFORM/
│   └── CUSTOMER_360_PIPELINE/
│
├── dbmeta_adapter.py
├── llm.py
├── rca.py
├── copilot.py
├── streamlit.py
│
├── .env
├── .env.example
├── .gitignore
└── requirements.txt
```

---

# Pipeline Data Structure

Each pipeline contains multiple execution runs.

Example:

```text
SCAL_LABS_PIPELINE
│
├── RUN_001
├── RUN_002
├── RUN_003
├── RUN_004
└── ...
```

Each run contains:

```text
RUN_001
├── metadata.json
├── execution.log
├── error.log
└── rca_analysis.json
```

---

# Metadata Structure

The metadata contains sections such as:

```text
pipeline
execution
input
output
resources
data_quality
spark
```

DbMeta converts these sections into queryable tables.

For example:

```text
execution
```

can contain:

```text
iid
run_id
status
start_time
end_time
duration_sec
failure_reason
```

---

# DbMeta Adapter

`dbmeta_adapter.py` provides a small interface over DbMeta.

Main functions:

```python
list_jobs()
list_runs()
get_db()
get_tables()
query()
get_run()
get_recent_runs()
get_failed_runs()
get_job_summary()
get_table_sample()
```

The adapter dynamically discovers tables instead of maintaining a hardcoded table list.

---

# LLM Configuration

The application uses an OpenAI-compatible API.

The current configuration supports providers such as xAI/Grok and other OpenAI-compatible endpoints.

`.env`:

```env
DATA_ROOT=./jobs

LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4

LLM_API_KEY_PATH=
```

Alternatively, the API key can be stored in a file:

```env
LLM_API_KEY_PATH=./secrets/grok_api_key.txt
```

Do not commit API keys to Git.

---

# RCA Flow

The RCA engine is implemented in:

```text
rca.py
```

Flow:

```text
RUN
 │
 ▼
Check rca_analysis.json
 │
 ├── Exists
 │      ↓
 │    Load cached RCA
 │
 └── Missing
        ↓
     Read error.log
        ↓
     Send to LLM
        ↓
     Generate RCA
        ↓
     Save rca_analysis.json
```

Example output:

```json
{
  "error": "Executor lost due to memory pressure",
  "root_cause": "Spark executor memory exhaustion",
  "evidence": [
    "Executor reported out-of-memory error",
    "Job processed a large partition"
  ],
  "fix": "Increase executor memory and investigate partition distribution"
}
```

---

# Copilot Investigation Flow

The Copilot is implemented in:

```text
copilot.py
```

The workflow is intentionally simple.

```text
Question
   ↓
Generate Investigation Plan
   ↓
Generate 1–5 SQL queries
   ↓
Validate SQL
   ↓
Execute SQL
   ↓
Detect RCA requirement
   ↓
Load / Generate RCA
   ↓
Combine Evidence
   ↓
Generate Final Answer
```

---

# Investigation Plan

The LLM generates a structure similar to:
