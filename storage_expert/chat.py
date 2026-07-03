import os
from pathlib import Path
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from storage_expert.providers import get_llm, get_embeddings
from storage_expert.ingest import CHROMA_PATH
from storage_expert.prompts import load_system_prompt

RAG_ENABLED = os.getenv("STORAGE_EXPERT_RAG_ENABLED", "true").lower() == "true"

_CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "Given the conversation history and the latest user question, "
        "rewrite the question as a standalone question that can be understood "
        "without the history. Do not answer it — only rewrite it."
    )),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", load_system_prompt()),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

_DIRECT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])


def _format_docs(docs) -> str:
    return "\n\n".join(d.page_content for d in docs)


def start_chat(provider: str, model: Optional[str] = None) -> None:
    llm = get_llm(provider, model)

    if RAG_ENABLED:
        from langchain_chroma import Chroma
        vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())

        if vectorstore._collection.count() == 0:
            print("No documents ingested yet. Run:\n  storage-expert ingest --file <path/to/vendor.pdf>")
            return

        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        contextualize_chain = _CONTEXTUALIZE_PROMPT | llm | StrOutputParser()
        qa_chain = _QA_PROMPT | llm | StrOutputParser()
    else:
        direct_chain = _DIRECT_PROMPT | llm | StrOutputParser()

    chat_history = []
    print(f"Storage Expert Chat [{provider}] — type 'exit' to quit\n")

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if RAG_ENABLED:
            standalone_q = (
                contextualize_chain.invoke({"input": question, "chat_history": chat_history})
                if chat_history else question
            )
            docs = retriever.invoke(standalone_q)
            answer = qa_chain.invoke({
                "input": question,
                "chat_history": chat_history,
                "context": _format_docs(docs),
            })

            print(f"\n{answer}\n")
            _print_sources(docs)
        else:
            answer = direct_chain.invoke({
                "input": question,
                "chat_history": chat_history,
            })
            print(f"\n{answer}\n")

        chat_history.extend([HumanMessage(content=question), AIMessage(content=answer)])


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
        print("Sources:", " | ".join(sorted(sources)), "\n")
