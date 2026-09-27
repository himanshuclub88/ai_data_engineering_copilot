import json
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from llm import get_llm

RCA_FILE = Path("RCA.json")

RCA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 'You are a data-engineering RCA analyst. Analyze the supplied pipeline error log. Return ONLY valid JSON with exactly these keys: error, root_cause, evidence, fix. evidence must be a JSON array. Do not invent evidence. If evidence is insufficient, say so.'),
    ("human", "Job: {job}\nRun: {run_id}\nError log:\n{log}")
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

def generate_rca(run_path, run_id, job=""):

    run_path = Path(run_path)
    log_file = run_path / "execution.log"
    error_log = run_path / "error.log"
    metadata_json = run_path / "metadata.json"
    key = f"{run_path}"

    if RCA_FILE.exists():
        try:
            rcas = json.loads(RCA_FILE.read_text(encoding="utf-8"))
            if key in rcas:
                data = rcas[key]
                data["cached"] = True
                return data
        except Exception: pass

    if not log_file.exists(): 
        data = _fallback("error.log was not found.")
    else:
        log = log_file.read_text(encoding="utf-8", errors="replace").strip()
        if not log: 
            data = _fallback("error.log is empty.")
        else:
            try:
                data = _json(get_llm().invoke(RCA_PROMPT.format_messages(job=job, run_id=run_id, log=log)).content)
                data = {k: data.get(k, "") for k in ("error", "root_cause", "evidence", "fix")}
                data["evidence"] = data["evidence"] if isinstance(data["evidence"], list) else [str(data["evidence"])]
                data["cached"] = False
            except Exception as e: data = _fallback(f"RCA generation failed: {e}")
    
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
