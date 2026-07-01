import logging
import os
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from storage_expert.ingest import ingest_file, CHROMA_PATH
from storage_expert.providers import get_embeddings, get_llm

app = FastAPI(title="Storage Expert")

STATIC_DIR = Path(__file__).parent / "static"
VENDOR_DIR = Path(__file__).parent.parent / "vendor_pdfs"
VENDOR_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_sessions: Dict[str, List] = {}


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/documents")
def list_documents():
    from langchain_chroma import Chroma
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
    results = vectorstore._collection.get()
    sources = set()
    for meta in results.get("metadatas", []):
        if meta and "source" in meta:
            sources.add(Path(meta["source"]).name)
    return {"documents": sorted(sources)}


@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    size_mb = len(content) / 1_048_576
    logger.info("Upload received: %s (%.1f MB)", file.filename, size_mb)

    # Check if already ingested by original filename
    from langchain_chroma import Chroma
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
    all_meta = vectorstore._collection.get()
    existing_names = {Path(m["source"]).name for m in all_meta.get("metadatas", []) if m and "source" in m}
    if file.filename in existing_names:
        return {"status": "skipped", "filename": file.filename, "chunks_stored": 0}

    # Save to vendor_pdfs/ for permanent storage
    saved_path = VENDOR_DIR / file.filename
    with open(saved_path, "wb") as f:
        f.write(content)
    logger.info("Saved to vendor_pdfs/%s", file.filename)

    try:
        before = vectorstore._collection.count()
        ingest_file(str(saved_path))
        after = vectorstore._collection.count()
        chunks_stored = after - before
    except Exception:
        saved_path.unlink(missing_ok=True)
        raise

    return {"status": "ok", "filename": file.filename, "chunks_stored": chunks_stored}


class ChatRequest(BaseModel):
    message: str
    session_id: str


_CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "Given the conversation history and the latest user question, "
        "rewrite the question as a standalone question. Do not answer it."
    )),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert in enterprise storage hardware.
Use the following excerpts from vendor documentation to answer the question.
If the answer is not in the context, say so clearly.

Context:
{context}"""),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])


@app.post("/chat")
def chat(req: ChatRequest):
    provider = os.getenv("STORAGE_EXPERT_PROVIDER", "claude")

    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
    if vectorstore._collection.count() == 0:
        return {"answer": "No documents in the knowledge base yet. Upload a PDF using the sidebar.", "sources": []}

    retriever = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": 5, "score_threshold": 0.3},
    )
    llm = get_llm(provider)

    history_aware_retriever = create_history_aware_retriever(llm, retriever, _CONTEXTUALIZE_PROMPT)
    chain = create_retrieval_chain(
        history_aware_retriever,
        create_stuff_documents_chain(llm, _QA_PROMPT),
    )

    chat_history = _sessions.get(req.session_id, [])
    result = chain.invoke({"input": req.message, "chat_history": chat_history})
    answer = result["answer"]

    sources = set()
    for doc in result.get("context", []):
        src = doc.metadata.get("source", "")
        page = doc.metadata.get("page")
        label = Path(src).name
        if page is not None:
            label += f" (page {int(page) + 1})"
        sources.add(label)

    _sessions[req.session_id] = chat_history + [
        HumanMessage(content=req.message),
        AIMessage(content=answer),
    ]

    return {"answer": answer, "sources": sorted(sources)}
