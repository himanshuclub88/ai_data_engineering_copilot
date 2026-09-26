import json, re
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from dbmeta_adapter import query, get_tables
from llm import get_llm
from rca import generate_rca, load_rca

PLAN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 'You are a data-engineering investigation planner. Return ONLY JSON: {"queries":[{"purpose":"...","sql":"..."}],"run_ids":[],"needs_rca":false}. Generate 1-5 focused SELECT queries using only the supplied DbMeta tables. Subqueries are allowed. Put explicit RUN_ IDs in run_ids. Set needs_rca=true for questions about failure cause, RCA, errors, root cause, or failure evidence.'),
    ("human", "Tables: {tables}\nQuestion: {question}")
])
ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "Answer only from the supplied evidence. Explain facts, cite run IDs/query evidence, use RCA when present, and state uncertainty instead of inventing details."),
    ("human", "Question: {question}\nEvidence:\n{evidence}")
])

def _text(x): return x.content if hasattr(x, "content") else str(x)

def _json(text):
    text = _text(text).strip().replace("```json", "").replace("```", "").strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a: return json.loads(text[a:b + 1])
        raise

def _safe_sql(sql, db):
    sql = sql.strip().replace("```sql", "").replace("```", "").strip().rstrip(";")
    if not re.match(r"^SELECT\b", sql, re.I): raise ValueError("Only SELECT statements are allowed.")
    if ";" in sql or re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE)\b", sql, re.I): raise ValueError("Unsafe SQL detected.")
    tables = {t.lower() for t in get_tables(db)}
    used = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)", sql, re.I)
    bad = [t for t in used if t.lower() not in tables]
    if bad: raise ValueError(f"Unknown DbMeta table(s): {', '.join(bad)}")
    return sql

def _plan(db, question):
    plan = _json(get_llm().invoke(PLAN_PROMPT.format_messages(tables=", ".join(get_tables(db)), question=question)))
    plan["queries"] = plan.get("queries", [])[:5]
    plan["run_ids"] = plan.get("run_ids", [])
    plan["needs_rca"] = bool(plan.get("needs_rca"))
    return plan

def _run_queries(db, queries):
    out = []
    for i, q in enumerate(queries, 1):
        try:
            sql = _safe_sql(q.get("sql", ""), db); out.append({"id": i, "purpose": q.get("purpose", ""), "sql": sql, "result": query(db, sql)})
        except Exception as e: out.append({"id": i, "purpose": q.get("purpose", ""), "sql": q.get("sql", ""), "error": str(e)})
    return out

def _run_rcas(job_path, run_ids):
    return [{"run_id": rid, "rca": load_rca(Path(job_path) / rid) or generate_rca(Path(job_path) / rid, rid, Path(job_path).name)} for rid in run_ids]

def ask_copilot(db, question, job_path=None):
    plan = _plan(db, question); queries = _run_queries(db, plan["queries"])
    rcas = _run_rcas(job_path, plan["run_ids"]) if job_path and plan["needs_rca"] else []
    evidence = json.dumps({"queries": queries, "rcas": rcas}, indent=2, default=str)
    answer = _text(get_llm().invoke(ANSWER_PROMPT.format_messages(question=question, evidence=evidence)))
    return {"answer": answer, "plan": plan, "queries": queries, "rcas": rcas}
