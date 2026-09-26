import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_api_key():
    key_path = os.getenv("LLM_API_KEY_PATH")

    if key_path:
        return Path(key_path).read_text().strip()

    return os.getenv("LLM_API_KEY")


def get_llm():
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL"),
        api_key=get_api_key(),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
    )