import os
from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# The openai client rejects an empty api_key at construction; keyless endpoints
# (e.g. local Ollama) accept any placeholder value.
_KEYLESS_PLACEHOLDER = "not-needed"


def _api_url() -> str:
    url = os.getenv("API_URL")
    if not url:
        raise ValueError("API_URL environment variable is not set")
    return url


@lru_cache(maxsize=None)
def get_llm(model: str | None = None):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError(
            "API_KEY environment variable is not set "
            "(for keyless endpoints like local Ollama, set any placeholder value)"
        )
    return ChatOpenAI(
        base_url=_api_url(),
        api_key=api_key,
        model=model if model is not None else os.getenv("LLM_MODEL", "gpt-4o"),
    )


@lru_cache(maxsize=1)
def get_embeddings():
    embed_key = os.getenv("EMBED_API_KEY")
    if embed_key is None:
        embed_key = os.getenv("API_KEY")
    base_url = os.getenv("EMBED_API_URL") or _api_url()
    return OpenAIEmbeddings(
        base_url=base_url,
        api_key=embed_key or _KEYLESS_PLACEHOLDER,
        model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        # Non-OpenAI endpoints require plain-string inputs; keep tiktoken
        # length safety only when talking to OpenAI itself.
        check_embedding_ctx_length="api.openai.com" in base_url,
    )
