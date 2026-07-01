from pathlib import Path
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

from storage_expert.providers import get_llm, get_embeddings
from storage_expert.ingest import CHROMA_PATH

_SYSTEM_PROMPT = """You are an expert in enterprise storage hardware (SANs, NAS, all-flash arrays, etc.).
Use the following excerpts from vendor documentation to answer the question.
If the answer is not covered by the provided context, say so clearly — do not guess.

Context:
{context}"""


def ask_question(question: str, provider: str, model: Optional[str] = None) -> None:
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())

    if vectorstore._collection.count() == 0:
        print("No documents ingested yet. Run:\n  storage-expert ingest --file <path/to/vendor.pdf>")
        return

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    llm = get_llm(provider, model)

    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("human", "{input}"),
    ])

    chain = create_retrieval_chain(retriever, create_stuff_documents_chain(llm, prompt))
    result = chain.invoke({"input": question})

    print(f"\n{result['answer']}\n")
    _print_sources(result.get("context", []))


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
