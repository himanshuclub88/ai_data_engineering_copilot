import json
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from llm import get_llm

RCA_FILE = Path("RCA.json")

RCA_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a data-engineering Root Cause Analysis (RCA) analyst.

Analyze the supplied information for a single pipeline run and determine
what happened, why it happened, and what can be done to fix it.

You will receive three types of information:

1. Metadata
   - Describes the pipeline/run configuration and execution information.
   - Use it to understand the context of the run.

2. Execution log
   - Shows what happened during pipeline execution.
   - Use it to understand the execution flow and identify where the
     failure occurred.

3. Error log
   - Contains error messages and failure details.
   - Treat explicit error messages as strong evidence.

Use ALL available information together.

Important rules:

- Return ONLY valid JSON.
- Return exactly these keys:
  error, root_cause, evidence, fix
- "evidence" MUST be a JSON array of strings.
- Do not invent logs, metrics, errors, timestamps, causes, or fixes.
- Every important RCA conclusion must be supported by the supplied data.
- Clearly distinguish between an observed fact and an inference.
- If the exact root cause is not available in the evidence, say:
  "Insufficient evidence to determine the exact root cause."
- Do not assume a generic Spark/Hadoop/Azure failure unless the supplied
  evidence supports it.
- If multiple possible causes exist, explain that the evidence does not
  conclusively distinguish between them.
- Prefer specific evidence from the logs over generic assumptions.
- Use metadata only when it helps explain or validate the failure.
- Do not reproduce the complete logs in the response.
- Keep the evidence concise and directly relevant to the RCA.
- The fix should address the identified root cause when the root cause
  is sufficiently supported.
- If the root cause is uncertain, provide a cautious next investigation
  step instead of inventing a fix.

The output must have this structure:

{
  "error": "specific observed error",
  "root_cause": "supported root cause or insufficient evidence",
  "evidence": [
    "Relevant observation from the execution log",
    "Relevant observation from the error log",
    "Relevant metadata observation"
  ],
  "fix": "Recommended fix or next investigation step"
}
        """
    ),
    (
        "human",
        """
Job: {job}
Run: {run_id}

================ METADATA ================
{metadata}

================ EXECUTION LOG ================
{execution_log}

================ ERROR LOG ================
{error_log}
        """
    )
])

def _json(text):
    text = text.strip().replace("```json", "").replace("```", "").strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a: return json.loads(text[a:b + 1])
        raise

def _fallback(msg):
    return {"error": "RCA unavailable", "root_cause": "Insufficient evidence", "evidence": [msg], "fix": "Inspect the execution and error logs manually.", "cached": False}

def _read_file(path):
    if not path.exists():   return ""
    return path.read_text(encoding="utf-8", errors="replace",).strip()


def generate_rca(run_path, run_id, job=""):

    run_path = Path(run_path)
    print(run_path)
    log_file = run_path / "execution.log"
    error_log = run_path / "error.log"
    metadata_json = run_path / "metadata.json"
    key = f"{run_path}"

    metadata = _read_file(metadata_json)
    execution_log = _read_file(log_file)
    error_log = _read_file(error_log)

    if RCA_FILE.exists():
        try:
            rcas = json.loads(RCA_FILE.read_text(encoding="utf-8"))
            if key in rcas:
                data = rcas[key]
                data["cached"] = True
                return data
        except Exception: pass

    if not log_file.exists(): 
        execution_log = "error.log was not found."
    else:
        if not execution_log: 
            execution_log = "error.log is empty."
        else:            

            try:
                response = get_llm().invoke(
                    RCA_PROMPT.format_messages(
                        job=job,
                        run_id=run_id,
                        metadata=metadata or "Metadata not available.",
                        execution_log=(execution_log),
                        error_log=(error_log or "Error log not available."))
                    )

                data = _json(response.content)
                data = {k: data.get(k, "") for k in ("error", "root_cause", "evidence", "fix")}
                data["evidence"] = data["evidence"] if isinstance(data["evidence"], list) else [str(data["evidence"])]
                data["cached"] = False
            except Exception as e: 
                data = _fallback(f"RCA generation failed: {e}")
                print(e)
    
    rcas = {}
    if RCA_FILE.exists():
        try:
            rcas = json.loads(RCA_FILE.read_text(encoding="utf-8"))
        except Exception:
            rcas = {}

    rcas[key] = data
    RCA_FILE.write_text(
        json.dumps(rcas,indent=2,ensure_ascii=False),
        encoding="utf-8",
        )
    
    return data


def load_rca(run_path):
    try:
        rcas = json.loads(RCA_FILE.read_text(encoding="utf-8")) if RCA_FILE.exists() else {}
        key = f"{run_path}"
        return rcas.get(key)
    except Exception:
        return None
