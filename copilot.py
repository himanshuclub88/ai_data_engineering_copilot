import json
import re
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

from dbmeta_adapter import query, get_tables
from llm import get_llm
from rca import generate_rca, load_rca


PLAN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        'You are a data-engineering investigation planner. Return ONLY JSON: '
        '{{"queries":[{"purpose":"...","sql":"..."}],"run_ids":[],"needs_rca":false}}. '
        'Generate 1-5 focused SELECT queries using only the supplied DbMeta tables. '
        'Subqueries are allowed. Put explicit RUN_ IDs in run_ids. '
        'Set needs_rca=true for questions about failure cause, RCA, errors, '
        'root cause, or failure evidence.'
    ),
    (
        "human",
        "Tables: {tables}\nQuestion: {question}"
    )
])


ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Answer only from the supplied evidence. Explain facts, cite run IDs/query "
        "evidence, use RCA when present, and state uncertainty instead of inventing details."
    ),
    (
        "human",
        "Question: {question}\nEvidence:\n{evidence}"
    )
])


def _text(value):
    if hasattr(value, "content"):
        return value.content

    return str(value)


def _json(text):
    text = _text(text).strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])

        raise


def _safe_sql(sql, db):
    sql = sql.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    sql = sql.rstrip(";")

    if not re.match(r"^SELECT\b", sql, re.I):
        raise ValueError("Only SELECT statements are allowed.")

    if ";" in sql or re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE)\b",
        sql,
        re.I,
    ):
        raise ValueError("Unsafe SQL detected.")

    tables = {table.lower() for table in get_tables(db)}

    used_tables = re.findall(
        r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)",
        sql,
        re.I,
    )

    invalid_tables = [
        table for table in used_tables
        if table.lower() not in tables
    ]

    if invalid_tables:
        raise ValueError(
            f"Unknown DbMeta table(s): {', '.join(invalid_tables)}"
        )

    return sql


def _plan(db, question):
    tables = ", ".join(get_tables(db))
    

    print(tables)

    response = get_llm().invoke(
        PLAN_PROMPT.format_messages(
            tables=tables,
            question=question,
        )
    )

    plan = _json(response)
    plan["queries"] = plan.get("queries", [])[:5]
    plan["run_ids"] = plan.get("run_ids", [])
    plan["needs_rca"] = bool(plan.get("needs_rca"))

    return plan


def _run_queries(db, queries):
    results = []

    for i, query_info in enumerate(queries, 1):
        try:
            sql = _safe_sql(query_info.get("sql", ""), db)

            results.append({
                "id": i,
                "purpose": query_info.get("purpose", ""),
                "sql": sql,
                "result": query(db, sql),
            })

        except Exception as error:
            results.append({
                "id": i,
                "purpose": query_info.get("purpose", ""),
                "sql": query_info.get("sql", ""),
                "error": str(error),
            })

    return results


def _run_rcas(job_path, run_ids):
    results = []

    for run_id in run_ids:
        run_path = Path(job_path) / run_id
        rca = load_rca(run_path)

        if not rca:
            rca = generate_rca(
                run_path,
                run_id,
                Path(job_path).name,
            )

        results.append({
            "run_id": run_id,
            "rca": rca,
        })

    return results


def ask_copilot(db, question, job_path=None):
    plan = _plan(db, question)
    queries = _run_queries(db, plan["queries"])

    rcas = []

    if job_path and plan["needs_rca"]:
        rcas = _run_rcas(job_path, plan["run_ids"])

    evidence = json.dumps(
        {
            "queries": queries,
            "rcas": rcas,
        },
        indent=2,
        default=str,
    )

    response = get_llm().invoke(
        ANSWER_PROMPT.format_messages(
            question=question,
            evidence=evidence,
        )
    )

    return {
        "answer": _text(response),
        "plan": plan,
        "queries": queries,
        "rcas": rcas,
    }