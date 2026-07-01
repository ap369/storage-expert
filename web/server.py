import os
import uuid
import tempfile
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from storage_expert.ingest import ingest_file, CHROMA_PATH
from storage_expert.providers import get_embeddings

app = FastAPI(title="Storage Expert")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory session store: {session_id: [HumanMessage, AIMessage, ...]}
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

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from langchain_chroma import Chroma
        vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
        before = vectorstore._collection.count()
        ingest_file(tmp_path)
        after = vectorstore._collection.count()
        chunks_stored = after - before
    finally:
        os.unlink(tmp_path)

    return {"status": "ok", "filename": file.filename, "chunks_stored": chunks_stored}
