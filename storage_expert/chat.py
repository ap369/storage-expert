from pathlib import Path
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from storage_expert.providers import get_llm, get_embeddings
from storage_expert.ingest import CHROMA_PATH

_CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "Given the conversation history and the latest user question, "
        "rewrite the question as a standalone question that can be understood "
        "without the history. Do not answer it — only rewrite it."
    )),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

_QA_SYSTEM = """You are an expert in enterprise storage hardware (SANs, NAS, all-flash arrays, etc.).
Use the following excerpts from vendor documentation to answer the question.
If the answer is not covered by the provided context, say so clearly — do not guess.

Context:
{context}"""

_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _QA_SYSTEM),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])


def start_chat(provider: str, model: Optional[str] = None) -> None:
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())

    if vectorstore._collection.count() == 0:
        print("No documents ingested yet. Run:\n  storage-expert ingest --file <path/to/vendor.pdf>")
        return

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    llm = get_llm(provider, model)

    history_aware_retriever = create_history_aware_retriever(llm, retriever, _CONTEXTUALIZE_PROMPT)
    chain = create_retrieval_chain(
        history_aware_retriever,
        create_stuff_documents_chain(llm, _QA_PROMPT),
    )

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

        result = chain.invoke({"input": question, "chat_history": chat_history})
        answer = result["answer"]

        print(f"\n{answer}\n")
        _print_sources(result.get("context", []))

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
