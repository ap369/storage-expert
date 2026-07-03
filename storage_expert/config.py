import os

RAG_ENABLED: bool = os.getenv("STORAGE_EXPERT_RAG_ENABLED", "true").lower() == "true"
