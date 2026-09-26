"""
AI RCA engine.

Flow:
error.log -> LangChain Core prompt -> LLM -> structured RCA -> rca_analysis.json

If rca_analysis.json already exists, the LLM is NOT called again.
"""

import json
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate


RCA_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a data engineering incident RCA assistant.

Analyze ONLY the supplied error log and run metadata.
Do not invent evidence.

Return valid JSON with exactly these keys:
error
root_cause
evidence
fix

Rules:
- error: short technical error name.
- root_cause: concise explanation.
- evidence: array of concrete facts from the input.
- fix: array of practical engineering actions.
"""
    ),
    (
        "human",
        """RUN ID:
{run_id}

METADATA:
{metadata}

ERROR LOG:
{error_log}
"""
    ),
])


def read_error_log(run_path):
    path = Path(run_path) / "error.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def rca_path(run_path):
    return Path(run_path) / "rca_analysis.json"


def load_cached_rca(run_path):
    path = rca_path(run_path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_rca_messages(run_id, metadata, error_log):
    return RCA_PROMPT.format_messages(
        run_id=run_id,
        metadata=json.dumps(metadata, indent=2),
        error_log=error_log,
    )


def parse_rca(content):
    if isinstance(content, str):
        text = content.strip()
    else:
        text = content.content.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


def save_rca(run_path, analysis):
    path = rca_path(run_path)
    path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return analysis


def run_rca(run_path, run_id, metadata, llm):
    """Return cached RCA or generate it once with the supplied LLM."""
    cached = load_cached_rca(run_path)
    if cached is not None:
        return cached

    error_log = read_error_log(run_path)
    if not error_log.strip():
        analysis = {
            "error": "NO_ERROR_LOG",
            "root_cause": "No error log was available.",
            "evidence": [],
            "fix": [],
        }
        return save_rca(run_path, analysis)

    messages = build_rca_messages(run_id, metadata, error_log)
    response = llm(messages)
    analysis = parse_rca(response)
    return save_rca(run_path, analysis)
