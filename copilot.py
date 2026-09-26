import json
import re

from langchain_core.prompts import ChatPromptTemplate

from dbmeta_adapter import query, get_tables
from agent_moudle import get_llm


SQL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a SQL generator for a data engineering pipeline database.

The database is DbMeta.

AVAILABLE TABLES:

{schema}

Generate exactly ONE read-only SELECT statement.

Rules:

1. Only SELECT is allowed.
2. Use only tables shown in AVAILABLE TABLES.
3. Do not use:
   INSERT
   UPDATE
   DELETE
   DROP
   ALTER
   CREATE
   TRUNCATE
   MERGE
4. Do not generate multiple SQL statements.
5. Prefer simple SQL.
6. Do not invent table names.
7. Do not invent column names.
8. If the question asks for latest records, use ORDER BY start_time DESC when appropriate.
9. Return ONLY SQL.
10. Do not use markdown code fences.

Example:

Question:
Show the latest 5 failed runs.

SQL:
SELECT iid, status, failure_reason, start_time, duration_sec
FROM execution
WHERE status = 'FAILED'
ORDER BY start_time DESC
LIMIT 5
""",
        ),
        (
            "human",
            "Question: {question}",
        ),
    ]
)


ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an AI data engineering copilot.

Answer the user's question using ONLY the DbMeta result.

Rules:

- Do not invent values.
- Do not assume information that is not in the result.
- If the result is empty, say that no matching data was found.
- Explain the result in practical data-engineering language.
- Mention run IDs, failure reasons, timings, or metrics when useful.
- Do not claim that you inspected logs unless the result contains log information.
""",
        ),
        (
            "human",
            """
USER QUESTION:

{question}

SQL:

{sql}

DBMETA RESULT:

{result}
""",
        ),
    ]
)


BLOCKED_SQL = re.compile(
    r"\b("
    r"insert|"
    r"update|"
    r"delete|"
    r"drop|"
    r"alter|"
    r"create|"
    r"truncate|"
    r"replace|"
    r"merge"
    r")\b",
    re.IGNORECASE,
)


def build_schema(db):
    """
    Build a dynamic schema description from DbMeta.

    We don't hardcode table names.
    """

    tables = get_tables(db)

    lines = []

    for table_name in tables:
        lines.append(
            f"- {table_name}"
        )

    return "\n".join(lines)


def clean_sql(sql):
    """
    Clean and validate LLM-generated SQL.
    """

    if not sql:
        raise ValueError(
            "LLM returned empty SQL."
        )

    sql = sql.strip()

    if sql.startswith("```"):
        sql = re.sub(
            r"^```(?:sql)?\s*",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        sql = re.sub(
            r"\s*```$",
            "",
            sql,
        )

    sql = sql.strip()

    if sql.endswith(";"):
        sql = sql[:-1].strip()

    if ";" in sql:
        raise ValueError(
            "Only one SQL statement is allowed."
        )

    if not sql.lower().startswith("select "):
        raise ValueError(
            "Copilot generated a non-SELECT statement."
        )

    if BLOCKED_SQL.search(sql):
        raise ValueError(
            "Copilot generated a blocked SQL operation."
        )

    return sql


def validate_tables(sql, db):
    """
    Make sure every FROM/JOIN table exists in DbMeta.

    This is a second safety layer after the LLM.
    """

    available = {
        table.lower()
        for table in get_tables(db)
    }

    referenced = re.findall(
        r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
        sql,
        flags=re.IGNORECASE,
    )

    for table_name in referenced:
        if table_name.lower() not in available:
            raise ValueError(
                f"SQL references unknown table: {table_name}"
            )


def generate_sql(db, question):
    """
    Ask the LLM to generate one SELECT query.
    """

    schema = build_schema(db)

    messages = SQL_PROMPT.format_messages(
        schema=schema,
        question=question,
    )

    response = get_llm().invoke(messages)

    sql = clean_sql(
        response.content
    )

    validate_tables(
        sql,
        db,
    )

    return sql


def generate_answer(
    question,
    sql,
    result,
):
    """
    Ask the LLM to explain the DbMeta result.
    """

    messages = ANSWER_PROMPT.format_messages(
        question=question,
        sql=sql,
        result=json.dumps(
            result,
            indent=2,
            default=str,
        ),
    )

    response = get_llm().invoke(messages)

    return str(
        response.content
    ).strip()


def ask_copilot(db, question):
    """
    Complete Copilot flow:

    User question
        ↓
    LLM generates SQL
        ↓
    SQL validation
        ↓
    DbMeta execution
        ↓
    LLM explains result
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    sql = generate_sql(
        db,
        question,
    )

    result = query(
        db,
        sql,
    )

    answer = generate_answer(
        question,
        sql,
        result,
    )

    return {
        "question": question,
        "sql": sql,
        "result": result,
        "answer": answer,
    }