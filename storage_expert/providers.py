import os
from typing import Optional


def get_llm(provider: str, model: Optional[str] = None):
    if provider == "claude":
        from langchain_anthropic import ChatAnthropic
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        return ChatAnthropic(model=model or "claude-sonnet-4-6", api_key=key)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return ChatOpenAI(model=model or "gpt-4o", api_key=key)

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model or "llama3")

    elif provider == "groq":
        from langchain_groq import ChatGroq
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        return ChatGroq(model=model or "llama-3.3-70b-versatile", api_key=key)

    elif provider == "custom":
        from langchain_openai import ChatOpenAI
        url = os.getenv("CUSTOM_API_URL")
        key = os.getenv("CUSTOM_API_KEY")
        if not url:
            raise ValueError("CUSTOM_API_URL environment variable not set")
        if not key:
            raise ValueError("CUSTOM_API_KEY environment variable not set")
        return ChatOpenAI(
            model=model or os.getenv("CUSTOM_API_MODEL", "default"),
            base_url=url,
            api_key=key,
        )

    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose: claude, openai, ollama, groq, custom")


def get_embeddings():
    backend = os.getenv("STORAGE_EXPERT_EMBEDDINGS", "huggingface")

    if backend == "openai":
        from langchain_openai import OpenAIEmbeddings
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        return OpenAIEmbeddings(api_key=key)

    elif backend == "ollama":
        from langchain_ollama import OllamaEmbeddings
        embed_model = os.getenv("STORAGE_EXPERT_EMBEDDINGS_MODEL", "nomic-embed-text")
        return OllamaEmbeddings(model=embed_model)

    else:  # huggingface (default)
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
