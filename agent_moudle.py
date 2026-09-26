import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


load_dotenv()


def get_api_key():
    """
    Get API key either from:

    1. LLM_API_KEY
    2. LLM_API_KEY_PATH
    """

    key_path = os.getenv("LLM_API_KEY_PATH", "").strip()

    if key_path:
        path = Path(key_path).expanduser()

        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            raise FileNotFoundError(
                f"LLM_API_KEY_PATH does not exist: {path}"
            )

        key = path.read_text(
            encoding="utf-8"
        ).strip()

        if not key:
            raise ValueError(
                f"API key file is empty: {path}"
            )

        return key

    key = os.getenv("LLM_API_KEY", "").strip()

    if not key:
        raise RuntimeError(
            "LLM API key is missing. "
            "Set LLM_API_KEY or LLM_API_KEY_PATH."
        )

    return key


def get_llm():
    """
    Create the OpenAI-compatible LangChain LLM.
    """

    base_url = os.getenv(
        "LLM_BASE_URL",
        ""
    ).strip()

    model = os.getenv(
        "LLM_MODEL",
        ""
    ).strip()

    if not base_url:
        raise RuntimeError(
            "LLM_BASE_URL is missing."
        )

    if not model:
        raise RuntimeError(
            "LLM_MODEL is missing."
        )

    return ChatOpenAI(
        model=model,
        api_key=get_api_key(),
        base_url=base_url,
        temperature=0,
    )