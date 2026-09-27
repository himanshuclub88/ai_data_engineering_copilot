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
        'You are a data-engineering investigation planner. '
        'Return ONLY valid JSON in this format: '
        '{{"queries":[{{"purpose":"...","sql":"..."}}],"run_ids":[],"needs_rca":false}}. '

        'The supplied Tables context contains table names, column names, '
        'and sample rows from DbMeta. Use only these tables and their columns '
        'when generating SQL. Do not invent table names or column names. '

        'Generate 1-5 focused SELECT queries that directly help answer the question. '
        'Subqueries are allowed. Avoid unnecessary queries and prefer queries '
        'that provide useful evidence for the investigation. '

        'If the question refers to a specific RUN_ ID, include that RUN_ ID '
        'in run_ids. If multiple explicit RUN_ IDs are mentioned, include all of them. '

        'Set needs_rca=true when the question involves failure cause, RCA, '
        'errors, root cause, or failure evidence. Otherwise set it to false. '

        'All SQL must be read-only SELECT statements.'

        """
        ## DBMeta SQL GENERATOR — STRICT PARSER MODE

        Generate SQL ONLY for the currently supported syntax of
        `FolderDB.sql()` / `SQLParserAdvanced`.

        The generated query MUST be directly executable by the current DBMeta parser.

        ### CRITICAL IDENTIFIER RULE — HIGHEST PRIORITY

        **NEVER use table aliases. NEVER qualify column names.**

        Every column reference MUST be a single bare identifier:

        VALID:
        `iid`
        `status`
        `failure_reason`
        `null_rate_pct`

        INVALID:
        `e.iid`
        `e.status`
        `execution.iid`
        `dq.null_rate_pct`
        `data_quality.schema_valid`

        If you generate `table.column` or `alias.column`, the query is INVALID.

        Therefore:

        INVALID:
        `SELECT e.iid, e.failure_reason FROM execution e`

        VALID:
        `SELECT iid, failure_reason FROM execution`

        INVALID:
        `WHERE e.status = 'FAILED'`

        VALID:
        `WHERE status = 'FAILED'`

        ### TABLE ALIAS RULE

        Aliases are completely forbidden.

        NEVER generate:

        `FROM execution e`
        `FROM execution AS e`
        `JOIN data_quality dq USING(iid)`
        `JOIN data_quality AS dq USING(iid)`

        ONLY:

        `FROM execution`
        `JOIN data_quality USING(iid)`

        ### SUPPORTED SQL

        ONLY use:

        * SELECT
        * FROM
        * JOIN table USING(column)
        * WHERE
        * AND
        * OR
        * NOT
        * Parentheses
        * =, !=, >, <, >=, <=
        * IN with literal values
        * NOT IN with literal values
        * CONTAINS
        * GROUP BY
        * HAVING
        * ORDER BY bare_column [ASC|DESC]
        * LIMIT integer
        * COUNT()
        * SUM()
        * MIN()
        * MAX()
        * AVG()

        Nothing else is supported.

        ### JOIN RULE

        JOIN is ONLY:

        `JOIN table USING(column)`

        The USING column must exist in both tables.

        Never use:

        * ON
        * INNER JOIN
        * LEFT JOIN
        * RIGHT JOIN
        * FULL JOIN
        * CROSS JOIN
        * aliases

        Example:

        VALID:
        `SELECT iid, failure_reason, null_rate_pct, duplicate_rate_pct, schema_valid`
        `FROM execution`
        `JOIN data_quality USING(iid)`
        `WHERE status = 'FAILED'`

        INVALID:
        `SELECT e.iid, e.failure_reason, dq.null_rate_pct`
        `FROM execution e`
        `JOIN data_quality dq USING(iid)`
        `WHERE e.status = 'FAILED'`

        ### WHERE RULE

        All columns in WHERE MUST be bare column names.

        VALID:
        `WHERE status = 'FAILED'`

        INVALID:
        `WHERE execution.status = 'FAILED'`
        `WHERE e.status = 'FAILED'`

        ### COLUMN RULE

        Use ONLY columns that actually exist in FolderDB metadata.

        NEVER invent columns.

        NEVER prefix a column with a table name or alias.

        NEVER use column aliases.

        INVALID:
        `COUNT() AS total`
        `execution.status`
        `e.status`

        VALID:
        `COUNT()`
        `status`

        ### IN RULE

        IN and NOT IN accept literal values only.

        VALID:
        `WHERE status IN ('FAILED', 'SUCCESS')`

        INVALID:
        `WHERE iid IN (SELECT iid FROM execution)`

        ### GROUP BY / HAVING

        Only existing bare columns are allowed.

        VALID:

        `SELECT environment, COUNT()`
        `FROM execution`
        `GROUP BY environment`
        `HAVING COUNT() > 1`

        ### ORDER BY

        ORDER BY accepts ONLY a bare existing column.

        VALID:
        `ORDER BY start_time DESC`

        INVALID:
        `ORDER BY execution.start_time DESC`
        `ORDER BY e.start_time DESC`
        `ORDER BY COUNT() DESC`

        ### FORBIDDEN

        NEVER generate:

        * table aliases
        * column qualification (`table.column`, `alias.column`)
        * column aliases
        * DISTINCT
        * subqueries
        * nested SELECT
        * CTE / WITH
        * EXISTS
        * NOT EXISTS
        * UNION
        * UNION ALL
        * JOIN ... ON
        * window functions
        * OVER
        * PARTITION BY
        * CASE
        * date functions
        * string functions
        * mathematical functions
        * unsupported functions
        * INSERT
        * UPDATE
        * DELETE
        * CREATE
        * DROP
        * ALTER
        * TRUNCATE

        Also never use functions such as:

        `YEAR()`
        `MONTH()`
        `WEEK()`
        `DAY()`
        `DATE_TRUNC()`
        `DATE_PART()`
        `DATEDIFF()`
        `ROW_NUMBER()`
        `RANK()`
        `LAG()`
        `LEAD()`

        unless explicitly supported by the parser.

        ### EXACTLY ONE SELECT

        The query MUST contain exactly one SELECT statement.

        No nested SELECT.
        No SELECT inside IN.
        No SELECT inside WHERE.
        No SELECT inside FROM.
        No UNION.
        No CTE.

        ### SIMPLICITY

        Generate the simplest valid query.

        Do not add unnecessary:

        * JOINs
        * conditions
        * functions
        * GROUP BY
        * columns

        ### UNSUPPORTED REQUEST

        If the request requires unsupported syntax, return exactly:

        NOT_SUPPORTED

        ### FINAL VALIDATION

        Before outputting SQL, internally verify:

        * No `alias.column`
        * No `table.column`
        * No table aliases
        * No `AS`
        * No DISTINCT
        * No subquery
        * No CTE
        * No JOIN ON
        * Exactly one SELECT
        * All tables exist
        * All columns exist
        * All JOIN USING columns exist in both tables
        * Only supported syntax is used

        If ANY validation fails, regenerate the query before returning it.
    """

        
    ),
    (
        "human",
        "Tables:\n{tables}\n\nQuestion:\n{question}"
    )
])


ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a data-engineering investigation assistant. "
        "Answer the user's question using only the supplied evidence. "

        "The evidence comes from pipeline metadata, execution records, "
        "JSON data, and logs that were converted into a queryable DbMeta representation. "
        "The SQL used internally to retrieve the evidence is an implementation detail "
        "and must NEVER be shown to the user. "

        "Do not display SQL queries, query IDs, database internals, "
        "or explain how DbMeta queried the data. "

        "Instead, explain what the available data actually shows. "
        "Use concise tables or bullet points when they make the answer clearer. "

        "When useful, include an 'Evidence' section that briefly describes "
        "the relevant facts found in the execution data or logs. "
        "Evidence should be written as natural-language observations, "
        "not SQL or database terminology. "

        "Clearly distinguish recorded facts from interpretation. "
        "Do not claim a root cause unless the available evidence supports it. "

        "If important information is missing, include a short "
        "'What we do not know' section explaining what cannot be determined "
        "from the available evidence. "

        "Do not invent logs, metrics, causes, or details."
    ),
    (
        "human",
        "Question:\n{question}\n\n"
        "Investigation Evidence:\n{evidence}"
    )
])


def _text(value):
    if hasattr(value, "content"):
        return value.content

    return str(value)


def _build_answer_evidence(queries, rcas):
    evidence = []

    for query_result in queries:
        if "error" in query_result:
            continue

        evidence.append({
            "purpose": query_result["purpose"],
            "data": query_result["result"],
        })

    return {
        "observations": evidence,
        "rcas": rcas,
    }

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
    table_context = []

    for table_name, table_data in db.tables.items():
        if not table_data:
            continue

        columns = list(table_data[0].keys())
        sample_rows = table_data[:2]

        table_context.append({
            "table": table_name,
            "columns": columns,
            "sample_rows": sample_rows,
        })

    tables = json.dumps(
        table_context,
        indent=2,
        default=str,
    )

    # print(tables)

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

    queries = _run_queries(
        db,
        plan["queries"],
    )

    rcas = []

    if job_path and plan["needs_rca"]:
        rcas = _run_rcas(
            job_path,
            plan["run_ids"],
        )

    answer_evidence = _build_answer_evidence(
        queries,
        rcas,
    )

    evidence = json.dumps(
        answer_evidence,
        indent=2,
        default=str,
    )

    answer = _text(
        get_llm().invoke(
            ANSWER_PROMPT.format_messages(
                question=question,
                evidence=evidence,
            )
        )
    )

    return {
        "answer": answer,
        "plan": plan,
        "queries": queries,
        "rcas": rcas,
    }