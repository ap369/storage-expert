import os
from pathlib import Path
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from storage_expert.providers import get_llm, get_embeddings
from storage_expert.ingest import CHROMA_PATH
from storage_expert.prompts import load_system_prompt

RAG_ENABLED = os.getenv("STORAGE_EXPERT_RAG_ENABLED", "true").lower() == "true"


def _format_docs(docs) -> str:
    return "\n\n".join(d.page_content for d in docs)


def ask_question(question: str, provider: str, model: Optional[str] = None) -> None:
    llm = get_llm(provider, model)

    if not RAG_ENABLED:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant."),
            ("human", "{input}"),
        ])
        answer = (prompt | llm | StrOutputParser()).invoke({"input": question})
        print(f"\n{answer}\n")
        return

    from langchain_chroma import Chroma
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())

    if vectorstore._collection.count() == 0:
        print("No documents ingested yet. Run:\n  storage-expert ingest --file <path/to/vendor.pdf>")
        return

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    prompt = ChatPromptTemplate.from_messages([
        ("system", load_system_prompt()),
        ("human", "{input}"),
    ])

    docs = retriever.invoke(question)
    answer = (prompt | llm | StrOutputParser()).invoke({"input": question, "context": _format_docs(docs)})

    print(f"\n{answer}\n")
    _print_sources(docs)


def _print_sources(docs) -> None:
    sources = set()
    for doc in docs:
        src = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        label = Path(src).name
        if page is not None:
            label += f" (page {int(page) + 1})"
        sources.add(label)
    if sources:
        print("Sources:", " | ".join(sorted(sources)))
