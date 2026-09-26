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

```json
{
  "queries": [
    {
      "purpose": "Find recent failed runs",
      "sql": "SELECT ..."
    },
    {
      "purpose": "Find failure reason distribution",
      "sql": "SELECT ..."
    }
  ],
  "run_ids": [
    "RUN_087"
  ],
  "needs_rca": true
}
```

The Python code then executes the plan.

The LLM does **not** directly control the database.

---

# Example Questions

The Copilot can answer questions such as:

### Failure Analysis

```text
Why are failures increasing?
```

```text
What is the most common failure reason?
```

```text
Show me recent failed runs.
```

### RCA

```text
Why did RUN_087 fail?
```

```text
What caused the DATA_SKEW failure?
```

```text
Give me the root cause of the latest failure.
```

### Historical Analysis

```text
Which failure reason occurred most frequently?
```

```text
Compare recent failures with older failures.
```

```text
Which runs had the longest duration?
```

### Data Quality

```text
Are recent failures related to data quality?
```

```text
Which runs had null spikes?
```

---

# Streamlit UI

The application has three main levels.

```text
Home
 │
 ├── Job 1
 ├── Job 2
 ├── Job 3
 └── ...
```

Selecting a job:

```text
Job
 │
 ├── Summary
 ├── DbMeta Tables
 ├── Recent Runs
 ├── Copilot
 └── Open Run
```

Selecting a run:

```text
Run
 │
 ├── Metadata
 ├── Execution Log
 ├── Error Log
 └── RCA
```

---

# Copilot UI

The job page provides a Copilot input.

Example:

```text
Ask about this pipeline:

Why are failures increasing?
```

The UI displays:

```text
Final Answer
────────────

...

Investigation Plan
──────────────────

...

SQL 1
─────
SELECT ...

Result
...

SQL 2
─────
SELECT ...

Result
...

RCA — RUN_087
─────────────

Root Cause
...

Evidence
...

Fix
...
```

This makes the investigation transparent instead of hiding the generated SQL and evidence.

---

# Installation

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Environment Setup

Copy:

```text
.env.example
```

to:

```text
.env
```

Configure:

```env
DATA_ROOT=./jobs
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4
```

---

# Run the Application

From the project directory:

```bash
streamlit run streamlit.py
```

The application opens the Streamlit interface.

---

# Design Principles

The project intentionally follows a simple architecture.

### No LangGraph

The project does not require a graph-based agent framework.

### No Custom Agent Classes

The workflow is implemented using small Python functions.

### LangChain Core

LangChain Core is used for:

* Prompt templates
* LLM invocation

### Python Controls Execution

The LLM generates the investigation plan, but Python controls:

* SQL validation
* Database execution
* RCA generation
* File access
* Evidence collection

### Compact Code

The implementation intentionally keeps functions small and compact.

The goal is:

```text
Simple
Readable
Debuggable
Extendable
```

rather than introducing unnecessary abstractions.

---

# Security Considerations

Never commit:

```text
.env
API keys
secrets/
```

The `.gitignore` already excludes common secret files.

SQL execution is restricted to read-only `SELECT` statements.

The Copilot also validates referenced DbMeta tables before execution.

---

# Future Improvements

Possible future additions include:

```text
Column-level schema discovery
        ↓
Better SQL validation
        ↓
Failure pattern detection
        ↓
RCA history search
        ↓
Run-to-run comparison
        ↓
Data-quality trend analysis
        ↓
Automated remediation suggestions
```

Another useful improvement would be allowing Copilot to compare two specific runs:

```text
Compare RUN_087 with RUN_092.
Why did one succeed while the other failed?
```

This could combine:

```text
metadata
execution
data quality
spark metrics
logs
RCA
```

into one investigation.

---

# Technology Stack

| Component       | Technology            |
| --------------- | --------------------- |
| UI              | Streamlit             |
| Metadata Query  | DbMeta                |
| LLM Framework   | LangChain Core        |
| LLM Interface   | OpenAI-compatible API |
| LLM             | Configurable          |
| Language        | Python                |
| Structured Data | JSON                  |
| RCA Storage     | JSON                  |
| SQL             | DbMeta SQL            |

---

# Summary

The AI Data Engineering Copilot provides a simple interface for investigating pipeline executions.

Its core workflow is:

```text
User Question
      ↓
Investigation Planning
      ↓
Multiple SQL Queries
      ↓
DbMeta Results
      ↓
RCA / Logs
      ↓
Combined Evidence
      ↓
LLM Reasoning
      ↓
Engineering Answer
```

The main goal is not simply to generate SQL.

The goal is to help a data engineer **investigate why a pipeline behaved the way it did**, using structured metadata, historical executions, logs, and RCA evidence together.
