import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_api_key():
    p = os.getenv("LLM_API_KEY_PATH", "").strip()
    if p:
        p = Path(p).expanduser(); p = p if p.is_absolute() else Path.cwd() / p
        if not p.exists(): raise FileNotFoundError(f"LLM_API_KEY_PATH does not exist: {p}")
        key = p.read_text(encoding="utf-8").strip()
        if not key: raise ValueError(f"API key file is empty: {p}")
        return key
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key: raise RuntimeError("Set LLM_API_KEY or LLM_API_KEY_PATH.")
    return key

def get_llm():
    base, model = os.getenv("LLM_BASE_URL", "").strip(), os.getenv("LLM_MODEL", "").strip()
    if not base or not model: raise RuntimeError("LLM_BASE_URL and LLM_MODEL are required.")
    return ChatOpenAI(model=model, api_key=get_api_key(), base_url=base, temperature=0)
