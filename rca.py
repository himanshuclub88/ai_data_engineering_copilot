import json
from pathlib import Path

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from llm import get_llm


RCA_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a senior data engineering root-cause-analysis assistant.

Analyze exactly one pipeline execution.

Use ONLY:
1. The supplied DbMeta metadata.
2. The supplied error.log.

Do not invent:
- logs
- metrics
- tables
- files
- Spark configuration
- infrastructure details
- root causes that are not supported by evidence

Return ONLY valid JSON.

Required JSON structure:

{
    "error": "What error actually occurred",
    "root_cause": "Most likely root cause",
    "evidence": [
        "Evidence from metadata or error log"
    ],
    "fix": "Practical fix"
}

Important:
- Separate observed error from inferred root cause.
- Evidence must come from supplied information.
- If evidence is insufficient, explicitly say so.
- Keep the fix practical and specific.
""",
        ),
        (
            "human",
            """
RUN ID:
{run_id}

DBMETA METADATA:
{metadata}

ERROR LOG:
{error_log}
""",
        ),
    ]
)


def get_rca_path(run_path):
    return Path(run_path) / "rca_analysis.json"


def read_error_log(run_path):
    path = Path(run_path) / "error.log"

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def load_cached_rca(run_path):
    path = get_rca_path(run_path)

    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError:
        return None


def save_rca(run_path, analysis):
    path = get_rca_path(run_path)

    path.write_text(
        json.dumps(
            analysis,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def normalize_rca(data):
    """
    Validate the basic RCA structure.
    """

    if not isinstance(data, dict):
        raise ValueError(
            "RCA response is not a JSON object."
        )

    required = [
        "error",
        "root_cause",
        "evidence",
        "fix",
    ]

    for key in required:
        if key not in data:
            raise ValueError(
                f"RCA response missing key: {key}"
            )

    evidence = data["evidence"]

    if not isinstance(evidence, list):
        evidence = [str(evidence)]

    return {
        "error": str(data["error"]),
        "root_cause": str(data["root_cause"]),
        "evidence": [
            str(item)
            for item in evidence
        ],
        "fix": str(data["fix"]),
    }


def run_rca(
    run_path,
    run_id,
    metadata,
):
    """
    Generate RCA for one run.

    Cached RCA is returned without calling the LLM.
    """

    cached = load_cached_rca(run_path)

    if cached is not None:
        cached["cached"] = True
        return cached

    error_log = read_error_log(run_path)

    if not error_log.strip():
        analysis = {
            "error": (
                "No error log was found "
                "or the error log is empty."
            ),
            "root_cause": (
                "Insufficient evidence."
            ),
            "evidence": [
                "error.log is empty or missing."
            ],
            "fix": (
                "Inspect the execution and "
                "upstream logs before generating RCA."
            ),
            "cached": False,
        }

        save_rca(
            run_path,
            analysis,
        )

        return analysis

    parser = JsonOutputParser()

    messages = RCA_PROMPT.format_messages(
        run_id=run_id,
        metadata=json.dumps(
            metadata,
            indent=2,
            default=str,
        ),
        error_log=error_log,
    )

    response = get_llm().invoke(messages)

    raw = response.content

    if isinstance(raw, list):
        raw = "".join(
            item.get("text", str(item))
            if isinstance(item, dict)
            else str(item)
            for item in raw
        )

    parsed = parser.parse(raw)

    analysis = normalize_rca(parsed)

    analysis["cached"] = False

    save_rca(
        run_path,
        analysis,
    )

    return analysis