"""
Job-level AI Copilot.

The selected job is the boundary.
LLM -> SQL -> DbMeta -> results -> LLM -> answer.

No LangGraph and no custom classes.
LangChain Core is used for prompts/runnables.
"""

import json

from langchain_core.prompts import ChatPromptTemplate


SQL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a data engineering SQL assistant.

You generate SQL for the DbMeta database of ONE selected job.

Available tables:
pipeline, execution, input, output, resources, data_quality, spark

Every table has iid containing the run ID.

Generate exactly ONE read-only SQL query.
Use only the tables and fields shown in the schema.
Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or invent columns.

Return only SQL."""
    ),
    (
        "human",
        """Schema:
{schema}

User question:
{question}
"""
    ),
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Answer the user's data engineering question using ONLY the DbMeta query result.

Do not invent numbers or facts.
If the result is empty, say that the available job history does not contain the requested evidence.
Keep the answer concise and technical."""
    ),
    (
        "human",
        """Question:
{question}

SQL:
{sql}

DbMeta result:
{result}
"""
    ),
])


def get_schema(db):
    schema = {}
    for table in ["pipeline", "execution", "input", "output",
                  "resources", "data_quality", "spark"]:
        try:
            rows = db.sql(f"SELECT * FROM {table} LIMIT 1")
            schema[table] = rows
        except Exception:
            schema[table] = "unavailable"
    return schema


def generate_sql(llm, db, question):
    schema = get_schema(db)
    messages = SQL_PROMPT.format_messages(
        schema=json.dumps(schema, indent=2, default=str),
        question=question,
    )
    response = llm(messages)
    return response.content.strip().replace("```sql", "").replace("```", "").strip()


def ask_copilot(llm, db, question):
    sql = generate_sql(llm, db, question)

    lowered = sql.lower()
    blocked = ["insert ", "update ", "delete ", "drop ", "alter ", "create "]
    if any(word in lowered for word in blocked):
        raise ValueError("Only read-only DbMeta SQL is allowed.")

    result = db.sql(sql)

    messages = ANSWER_PROMPT.format_messages(
        question=question,
        sql=sql,
        result=json.dumps(result, indent=2, default=str),
    )
    response = llm(messages)

    return {
        "question": question,
        "sql": sql,
        "result": result,
        "answer": response.content.strip(),
    }
