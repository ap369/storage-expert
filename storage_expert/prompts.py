from pathlib import Path

_PROMPT_PATH = Path(__file__).parent.parent / "system_prompt.md"

_FALLBACK = (
    "You are a storage documentation assistant. Your only source of truth is the "
    "vendor documentation excerpts provided below.\n\n"
    "If the context does not contain the answer, say: "
    "\"I don't have that information in the loaded documentation.\"\n\n"
    "Context:\n{context}"
)


def load_system_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text()
    return _FALLBACK


def load_direct_prompt() -> str:
    return "You are a helpful assistant."


def format_docs(docs) -> str:
    """Format retrieved chunks with their source label so the model can cite them."""
    parts = []
    for d in docs:
        src = Path(d.metadata.get("source", "unknown")).name
        page = d.metadata.get("page")
        label = f"[{src}, page {int(page) + 1}]" if page is not None else f"[{src}]"
        parts.append(f"{label}\n{d.page_content}")
    return "\n\n".join(parts)
