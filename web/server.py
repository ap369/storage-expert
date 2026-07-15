import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from openai import APIConnectionError
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from storage_expert.config import RAG_ENABLED

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from storage_expert.ingest import ingest_file, CHROMA_PATH
from storage_expert.providers import get_embeddings, get_llm
from storage_expert.mcp_client import get_mcp_tools, probe_servers
from storage_expert.auth import init_db, verify_user
from storage_expert.prompts import load_system_prompt, load_direct_prompt, format_docs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Storage Expert", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "change-me"),
    https_only=False,
)

@app.exception_handler(APIConnectionError)
async def api_connection_error(request: Request, exc: APIConnectionError):
    logger.error("Model API unreachable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Cannot reach the model API (LLM or embeddings endpoint). Check that the configured services are running."},
    )


STATIC_DIR = Path(__file__).parent / "static"
VENDOR_DIR = Path(__file__).parent.parent / "vendor_pdfs"
VENDOR_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_sessions: Dict[str, List] = {}


def require_auth(request: Request):
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/login")
def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not verify_user(username, password):
        return RedirectResponse("/login?error=1", status_code=303)
    request.session["user"] = username
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def index(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login")
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/config")
async def get_config():
    return {"rag_enabled": RAG_ENABLED}


@app.get("/documents", dependencies=[Depends(require_auth)])
def list_documents():
    if not RAG_ENABLED:
        return {"documents": []}
    from langchain_chroma import Chroma
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
    results = vectorstore._collection.get()
    sources = set()
    for meta in results.get("metadatas", []):
        if meta and "source" in meta:
            sources.add(Path(meta["source"]).name)
    return {"documents": sorted(sources)}


@app.get("/mcp-servers", dependencies=[Depends(require_auth)])
async def mcp_servers_status():
    return {"servers": await probe_servers()}


@app.post("/ingest", dependencies=[Depends(require_auth)])
async def ingest_pdf(file: UploadFile = File(...)):
    if not RAG_ENABLED:
        raise HTTPException(status_code=503, detail="RAG is disabled. Set STORAGE_EXPERT_RAG_ENABLED=true to enable PDF ingestion.")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    size_mb = len(content) / 1_048_576
    logger.info("Upload received: %s (%.1f MB)", file.filename, size_mb)

    # Check if already ingested — same key (absolute source path) as ingest_file
    saved_path = VENDOR_DIR / file.filename
    from langchain_chroma import Chroma
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
    existing = vectorstore._collection.get(where={"source": str(saved_path.resolve())})
    if existing["ids"]:
        return {"status": "skipped", "filename": file.filename, "chunks_stored": 0}

    # Save to vendor_pdfs/ for permanent storage
    with open(saved_path, "wb") as f:
        f.write(content)
    logger.info("Saved to vendor_pdfs/%s", file.filename)

    try:
        chunks_stored = ingest_file(str(saved_path))
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
    ("system", load_system_prompt()),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

_DIRECT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", load_direct_prompt()),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])


@app.post("/chat", dependencies=[Depends(require_auth)])
async def chat(req: ChatRequest):
    try:
        llm = get_llm()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    chat_history = _sessions.get(req.session_id, [])

    if RAG_ENABLED:
        from langchain_chroma import Chroma
        vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
        if vectorstore._collection.count() == 0:
            return {"answer": "No documents in the knowledge base yet. Upload a PDF using the sidebar.", "sources": []}

        retriever = vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 5, "score_threshold": 0.3},
        )
        mcp_tools = await get_mcp_tools()

        if mcp_tools:
            try:
                from langgraph.prebuilt import create_react_agent
                from langchain_core.tools.retriever import create_retriever_tool

                rag_tool = create_retriever_tool(
                    retriever,
                    name="search_vendor_documents",
                    description="Search the vendor PDF knowledge base for storage specs, features, and compatibility information.",
                )
                # Same grounding rules as the RAG chain; the tool replaces inline context
                agent_prompt = load_system_prompt().replace(
                    "{context}",
                    "Use the search_vendor_documents tool to retrieve documentation "
                    "excerpts before answering technical questions.",
                )
                agent = create_react_agent(llm, [rag_tool] + mcp_tools, prompt=agent_prompt)
                result = await agent.ainvoke({
                    "messages": chat_history + [HumanMessage(content=req.message)]
                })
                answer = result["messages"][-1].content
                sources = []
            except Exception as e:
                logger.warning("MCP agent failed (%s: %s), falling back to RAG", type(e).__name__, e)
                mcp_tools = []

        if not mcp_tools:
            contextualize_chain = _CONTEXTUALIZE_PROMPT | llm | StrOutputParser()
            standalone_q = (
                await contextualize_chain.ainvoke({"input": req.message, "chat_history": chat_history})
                if chat_history else req.message
            )
            docs = await retriever.ainvoke(standalone_q)
            answer = await (_QA_PROMPT | llm | StrOutputParser()).ainvoke({
                "input": req.message,
                "chat_history": chat_history,
                "context": format_docs(docs),
            })

            sources = set()
            for doc in docs:
                src = doc.metadata.get("source", "")
                page = doc.metadata.get("page")
                label = Path(src).name
                if page is not None:
                    label += f" (page {int(page) + 1})"
                sources.add(label)
            sources = sorted(sources)

    else:
        mcp_tools = await get_mcp_tools()

        if mcp_tools:
            try:
                from langgraph.prebuilt import create_react_agent
                agent = create_react_agent(llm, mcp_tools, prompt=load_direct_prompt())
                result = await agent.ainvoke({
                    "messages": chat_history + [HumanMessage(content=req.message)]
                })
                answer = result["messages"][-1].content
            except Exception as e:
                logger.warning("MCP agent failed (%s: %s), falling back to direct LLM", type(e).__name__, e)
                mcp_tools = []

        if not mcp_tools:
            answer = await (_DIRECT_PROMPT | llm | StrOutputParser()).ainvoke({
                "input": req.message,
                "chat_history": chat_history,
            })

        sources = []

    _sessions[req.session_id] = chat_history + [
        HumanMessage(content=req.message),
        AIMessage(content=answer),
    ]

    return {"answer": answer, "sources": sources}
