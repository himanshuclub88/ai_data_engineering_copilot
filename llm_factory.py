"""LLM factory. Supports OpenAI-compatible endpoints and Azure OpenAI."""
from __future__ import annotations

import os


def build_llm():
    provider = os.getenv("LLM_PROVIDER", "azure").lower()

    if provider == "azure":
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            temperature=0,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-5"),
            api_key=os.environ["OPENAI_API_KEY"],
            temperature=0,
        )

    if provider == "compatible":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.environ["COMPATIBLE_MODEL"],
            api_key=os.environ["COMPATIBLE_API_KEY"],
            base_url=os.environ["COMPATIBLE_BASE_URL"],
            temperature=0,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
