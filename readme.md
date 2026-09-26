# AI Data Engineering Copilot

An AI-powered assistant for analyzing **data engineering pipeline execution history**.

The application combines **DbMeta**, **LLM reasoning**, pipeline logs, and **Streamlit** to help data engineers investigate failed runs, understand pipeline history, and generate root-cause analysis.

---

## Overview

The AI Data Engineering Copilot provides two main capabilities:

### 1. Pipeline Run Investigation

For every pipeline job, the application provides:

* Recent pipeline runs
* Run status
* Failure reason
* Execution time
* Structured pipeline metadata
* Execution logs
* Error logs
* Root Cause Analysis (RCA)

### 2. AI Copilot

The Copilot allows users to ask questions about a job's execution history.

Example questions:

```text
Why did the latest run fail?

Show me the last 5 failed runs.

Which failure reason occurred most frequently?

Which runs took more than 5 minutes?

Show me the latest successful run.

What happened to RUN_087?
```

The Copilot converts the question into a **read-only DbMeta SQL query**, executes it, and then explains the result.

---

# Architecture

```text
                         ┌─────────────────────┐
                         │      Streamlit      │
                         │        UI           │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
                  ▼                                   ▼
             Job / Runs                           Copilot
                  │                                   │
                  │                              User Question
                  │                                   │
                  │                                   ▼
                  │                                  LLM
                  │                                   │
                  │                              Generate SQL
                  │                                   │
                  │                                   ▼
                  │                                DbMeta
                  │                                   │
                  │                              Query Result
                  │                                   │
                  │                                   ▼
                  │                                  LLM
                  │                                   │
                  │                                   ▼
                  │                                 Answer
                  │
                  │
                  ├──────────────► DbMeta
                  │                 │
                  │                 └── Structured Metadata
                  │
                  └──────────────► Filesystem
                                    │
                                    ├── execution.log
                                    ├── error.log
                                    └── rca_analysis.json
                                             │
                                             ▼
                                            RCA
                                             │
                                             ▼
                                            LLM
```

---

# Core Design

The application deliberately avoids unnecessary agent frameworks.

There is:

* No LangGraph
* No custom Agent class
* No multi-agent architecture
* No autonomous tool loop

Instead, the system uses a simple deterministic flow.

## Copilot

```text
User Question
      ↓
LLM
      ↓
Read-only SQL
      ↓
SQL Validation
      ↓
DbMeta
      ↓
Query Result
      ↓
LLM
      ↓
Natural Language Answer
```

## RCA

```text
Run
 │
 ├── DbMeta Metadata
 │
 └── error.log
       │
       ▼
      LLM
       │
       ▼
RCA JSON
       │
       ▼
rca_analysis.json
```

---

# Project Structure

```text
ai_data_engineering_copilot/
│
├── dbmeta_adapter.py
├── llm.py
├── rca.py
├── copilot.py
├── streamlit.py
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
├── secrets/
│   └── grok_api_key.txt
│
├── .env
├── .env.example
├── .gitignore
└── requirements.txt
```

---

# Data Model

Each job contains multiple pipeline runs.

Example:

```text
SCAL_LABS_PIPELINE
│
├── RUN_001
├── RUN_002
├── RUN_003
├── ...
└── RUN_100
```

Each run contains:

```text
RUN_001/
│
├── metadata.json
├── execution.log
├── error.log
└── rca_analysis.json
```

---

# DbMeta

DbMeta is used as the structured metadata query layer.

Each job gets its own `FolderDB`.

```python
db = FolderDB(
    base_path=str(job_path),
    base_metadata="metadata.json",
)
```

The application dynamically discovers tables using:

```python
db.tables.keys()
```

Therefore, tables are **not hardcoded** in the application.

For example, if DbMeta discovers:

```text
pipeline
execution
input
output
resources
data_quality
spark
```

the application automatically works with those tables.

If another table is added later, it can be discovered without modifying the table list.

---

# DbMeta Query Example

To retrieve recent runs:

```sql
SELECT iid,
       status,
       failure_reason,
       start_time,
       duration_sec
FROM execution
ORDER BY start_time DESC
LIMIT 5
```

DbMeta returns the query result as rows.

The adapter materializes the result using:

```python
db.sql(sql).all()
```

---

# AI Copilot

The Copilot operates at the **job level**.

For example:

```text
SCAL_LABS_PIPELINE
│
├── Recent Runs
│
├── Failed Runs
│
└── Copilot
```

A user can ask:

```text
Why did the latest run fail?
```

The system performs:

```text
Question
   ↓
LLM generates SQL
   ↓
SQL validation
   ↓
DbMeta
   ↓
Result
   ↓
LLM explanation
```

The generated SQL is also displayed in the UI so that the user can inspect what the Copilot queried.

---

# SQL Safety

The Copilot is restricted to read-only SQL.

The application blocks operations such as:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
MERGE
```

The generated query must:

```text
START WITH SELECT
```

and only reference tables available through:

```python
db.tables.keys()
```

The application also checks the tables referenced in:

```sql
FROM
JOIN
```

against the actual DbMeta tables.

---

# Root Cause Analysis

RCA is generated for an individual failed run.

The RCA process uses:

```text
DbMeta Metadata
+
error.log
```

The LLM generates:

```json
{
    "error": "Observed error",
    "root_cause": "Likely root cause",
    "evidence": [
        "Evidence from metadata or error log"
    ],
    "fix": "Recommended fix"
}
```

The result is stored in:

```text
RUN_xxx/rca_analysis.json
```

---

# RCA Caching

RCA results are cached.

For example:

```text
RUN_087/
├── metadata.json
├── execution.log
├── error.log
└── rca_analysis.json
```

If `rca_analysis.json` already exists:

```text
Streamlit
    ↓
Load cached RCA
    ↓
No LLM call
```

If it does not exist:

```text
Streamlit
    ↓
Read error.log
    ↓
Read DbMeta metadata
    ↓
LLM
    ↓
Save rca_analysis.json
```

This avoids repeatedly calling the LLM for the same run.

---

# LLM Configuration

The project uses `langchain-openai` with an **OpenAI-compatible API**.

This allows providers such as xAI/Grok and other compatible providers to be configured without changing the application code.

The LLM configuration is centralized in:

```text
llm.py
```

---

# Environment Configuration

Create a `.env` file in the project root.

## API Key Directly in `.env`

```env
DATA_ROOT=./jobs

LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4

LLM_API_KEY_PATH=
```

---

## API Key From File

Alternatively:

```env
DATA_ROOT=./jobs

LLM_API_KEY=
LLM_API_KEY_PATH=./secrets/grok_api_key.txt

LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4
```

Then:

```text
secrets/
└── grok_api_key.txt
```

contains only:

```text
your-api-key
```

---

# Installation

Create and activate your virtual environment.

Then install the dependencies:

```bash
pip install -r requirements.txt
```

---

# Requirements

```text
dbmeta
langchain-core
langchain-openai
openai
streamlit
python-dotenv
```

---

# Running the Application

From the project root:

```bash
streamlit run streamlit.py
```

The application will open in Streamlit.

---

# Application Flow

## Home

```text
AI Data Engineering Copilot

Jobs

SCAL_LABS_PIPELINE
HR_DATA_PLATFORM
SALES_DATA_PLATFORM
FINANCE_DATA_PLATFORM
CUSTOMER_360_PIPELINE
```

Select a job.

---

## Job Page

The job page displays:

```text
SCAL_LABS_PIPELINE

Total Runs     Successful     Failed     Other
    100             82           18         0
```

Then:

```text
Recent Runs

RUN_100 | FAILED  | DATA_SKEW
RUN_099 | SUCCESS | SUCCESS
RUN_098 | FAILED  | OOM
...
```

The user can select any run.

---

# Run Page

Each run contains four sections:

```text
Metadata
Execution Log
Error Log
RCA
```

### Metadata

Displays the structured information retrieved from DbMeta.

### Execution Log

Displays:

```text
execution.log
```

### Error Log

Displays:

```text
error.log
```

### RCA

Displays either:

```text
Cached RCA
```

or allows:

```text
Generate RCA
```

---

# Example Copilot Questions

The Copilot can answer questions such as:

### Run Investigation

```text
Why did the latest run fail?
```

```text
What happened in RUN_087?
```

```text
Show the last 5 failed runs.
```

### Performance

```text
Which runs took the longest?
```

```text
Show runs that took more than 300 seconds.
```

### Failure Analysis

```text
What failure reasons occurred recently?
```

```text
Show all failed runs caused by DATA_SKEW.
```

### Pipeline History

```text
Show the latest successful run.
```

```text
How many runs failed?
```

```text
What is the execution history of this pipeline?
```

---

# Design Principles

## 1. DbMeta is the Source of Truth

Structured pipeline information comes from DbMeta.

```text
DbMeta
   ↓
Structured metadata
```

---

## 2. Logs Stay as Files

Logs are not forced into DbMeta.

```text
execution.log
error.log
```

remain normal files.

---

## 3. LLM Does Reasoning

The LLM does not become the database.

Instead:

```text
LLM
 ↓
SQL
 ↓
DbMeta
```

The actual data comes from DbMeta.

---

## 4. RCA Is Cached

Once RCA is generated:

```text
rca_analysis.json
```

is reused.

---

## 5. Dynamic Tables

The application discovers tables using:

```python
db.tables.keys()
```

instead of maintaining a manual table list.

---

## 6. Provider Independent

The application does not directly depend on an xAI-specific SDK.

LLM configuration is controlled through:

```env
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

---

# Security

Do not commit API keys.

The following files/directories are ignored:

```text
.env
secrets/
*_api_key.txt
*.key
*.pem
```

Keep secrets outside Git.

Example:

```text
secrets/
└── grok_api_key.txt
```

and make sure `secrets/` is included in `.gitignore`.

---

# Future Improvements

Possible future enhancements:

* Dynamic DbMeta column/schema discovery
* Failure trend visualization
* Pipeline performance dashboards
* Failure-pattern detection
* Automatic RCA generation after failed runs
* Run comparison
* Spark resource analysis
* Data-quality trend analysis
* Pipeline dependency analysis
* Historical RCA search
* Export RCA reports
* Authentication and role-based access
* Additional LLM providers

---

# Technology Stack

| Component       | Technology                              |
| --------------- | --------------------------------------- |
| UI              | Streamlit                               |
| Structured Data | DbMeta                                  |
| LLM Integration | LangChain OpenAI-compatible             |
| LLM             | Configurable OpenAI-compatible provider |
| Configuration   | python-dotenv                           |
| Language        | Python                                  |
| Logs            | Filesystem                              |
| RCA Cache       | JSON                                    |

---

# Summary

The AI Data Engineering Copilot provides a simple interface for investigating data pipeline executions.

The core architecture is:

```text
                 AI Data Engineering Copilot
                           │
             ┌─────────────┴─────────────┐
             │                           │
          DbMeta                      Files
             │                           │
      Structured Data              Logs / RCA
             │                           │
             └─────────────┬─────────────┘
                           │
                          LLM
                           │
              ┌────────────┴────────────┐
              │                         │
            RCA                     Copilot
              │                         │
       Root Cause                  SQL + Answer
```

The goal is not to create a complex autonomous agent.

The goal is to provide a **simple, transparent, and practical AI assistant for data engineering operations**.

```
```
