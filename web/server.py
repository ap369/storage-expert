import os
import tempfile
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from storage_expert.ingest import ingest_file, CHROMA_PATH
from storage_expert.providers import get_embeddings

app = FastAPI(title="Storage Expert")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    # Check if already ingested by original filename
    from langchain_chroma import Chroma
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())
    all_meta = vectorstore._collection.get()
    existing_names = {Path(m["source"]).name for m in all_meta.get("metadatas", []) if m and "source" in m}
    if file.filename in existing_names:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"status": "skipped", "filename": file.filename, "chunks_stored": 0}

    try:
        before = vectorstore._collection.count()
        ingest_file(tmp_path)
        after = vectorstore._collection.count()
        chunks_stored = after - before
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {"status": "ok", "filename": file.filename, "chunks_stored": chunks_stored}
