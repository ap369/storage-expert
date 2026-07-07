import os
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

_DEFAULT_API_URL = "https://api.openai.com/v1"


def get_llm(model: Optional[str] = None):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable is not set")
    return ChatOpenAI(
        base_url=os.getenv("API_URL", _DEFAULT_API_URL),
        api_key=api_key,
        model=model if model is not None else os.getenv("LLM_MODEL", "gpt-4o"),
    )


def get_embeddings():
    embed_key = os.getenv("EMBED_API_KEY")
    api_key = embed_key if embed_key is not None else os.getenv("API_KEY", "")
    return OpenAIEmbeddings(
        base_url=os.getenv("EMBED_API_URL") or os.getenv("API_URL", _DEFAULT_API_URL),
        api_key=api_key,
        model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        check_embedding_ctx_length=False,
    )
