# Web Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI web server + single-page chat UI on top of the existing CLI RAG pipeline, with PDF upload support and persistent ChromaDB knowledge base.

**Architecture:** FastAPI serves both the API endpoints and the static `index.html`. Session memory is an in-memory dict keyed by UUID (generated client-side). The existing `storage_expert/` modules are reused as-is — no changes to CLI code.

**Tech Stack:** FastAPI, Uvicorn, python-multipart, vanilla JS (no build step), Docker + docker-compose

## Global Constraints

- Python 3.9+
- Do not modify any existing files in `storage_expert/` (cli.py, providers.py, ingest.py, qa.py, chat.py)
- Provider fixed by `.env` (`STORAGE_EXPERT_PROVIDER`, default `claude`)
- Responses are non-streaming (full answer returned at once)
- `chroma_db/` must persist across container restarts via Docker volume

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Add fastapi, uvicorn, python-multipart |
| `web/__init__.py` | Create | Package marker |
| `web/server.py` | Create | FastAPI app — all endpoints + session memory |
| `web/static/index.html` | Create | Single-page chat UI (vanilla JS) |
| `Dockerfile` | Create | Build image, run uvicorn |
| `docker-compose.yml` | Create | Service + chroma_db volume + .env |

---

### Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add web dependencies to pyproject.toml**

In the `dependencies` list, add:
```toml
"fastapi>=0.111",
"uvicorn>=0.30",
"python-multipart>=0.0.9",
```

- [ ] **Step 2: Install**

```bash
source .venv/bin/activate
pip install -e . --quiet
```

Expected: no errors. Verify:
```bash
python -c "import fastapi, uvicorn; print('ok')"
```
Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add fastapi/uvicorn/multipart dependencies"
```

---

### Task 2: FastAPI server — documents and ingest endpoints

**Files:**
- Create: `web/__init__.py`
- Create: `web/server.py`

**Produces:**
- `GET /` → serves `web/static/index.html`
- `GET /documents` → `{"documents": ["filename.pdf", ...]}`
- `POST /ingest` → multipart `file` field → `{"status": "ok", "chunks_stored": N, "filename": "..."}`

- [ ] **Step 1: Create `web/__init__.py`**

Empty file:
```python
```

- [ ] **Step 2: Create `web/server.py` with documents + ingest endpoints**

```python
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
```

- [ ] **Step 3: Smoke-test the server starts**

```bash
source .venv/bin/activate
uvicorn web.server:app --port 8000 &
sleep 2
curl -s http://localhost:8000/documents
kill %1
```

Expected output: `{"documents":[]}`  (or list of already-ingested filenames)

- [ ] **Step 4: Commit**

```bash
git add web/__init__.py web/server.py
git commit -m "feat: add FastAPI server with /documents and /ingest endpoints"
```

---

### Task 3: Chat endpoint with session memory

**Files:**
- Modify: `web/server.py` — add `/chat` endpoint

**Consumes:**
- `_sessions` dict from Task 2
- `get_llm(provider, model)` from `storage_expert/providers.py`
- `get_embeddings()` from `storage_expert/providers.py`
- `CHROMA_PATH` from `storage_expert/ingest.py`

**Produces:**
- `POST /chat` body `{"message": str, "session_id": str}` → `{"answer": str, "sources": [str]}`

- [ ] **Step 1: Add chat request model and endpoint to `web/server.py`**

After the existing imports, add:
```python
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from storage_expert.providers import get_llm
```

Add the request model and endpoint:
```python
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

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
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
```

- [ ] **Step 2: Test chat endpoint (requires a real API key in .env)**

```bash
source .venv/bin/activate
uvicorn web.server:app --port 8000 &
sleep 2
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the max IOPS of the NetApp AFF A800?", "session_id": "test-123"}'
kill %1
```

Expected: `{"answer": "...", "sources": ["test_netapp_a800.pdf (page 1)"]}`

- [ ] **Step 3: Commit**

```bash
git add web/server.py
git commit -m "feat: add /chat endpoint with session memory"
```

---

### Task 4: Frontend — single-page chat UI

**Files:**
- Create: `web/static/index.html`

**Consumes:**
- `GET /documents` → populates sidebar
- `POST /ingest` → called on file upload
- `POST /chat` → called on message send

- [ ] **Step 1: Create `web/static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Storage Expert</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; display: flex; height: 100vh; background: #f5f5f5; }

    /* Sidebar */
    #sidebar {
      width: 260px; background: #1e1e2e; color: #cdd6f4;
      display: flex; flex-direction: column; padding: 16px; gap: 12px; flex-shrink: 0;
    }
    #sidebar h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.1em; color: #89b4fa; }
    #add-btn {
      background: #89b4fa; color: #1e1e2e; border: none; border-radius: 6px;
      padding: 8px 12px; cursor: pointer; font-size: 13px; font-weight: 600; text-align: left;
    }
    #add-btn:hover { background: #74c7ec; }
    #file-input { display: none; }
    #doc-list { list-style: none; display: flex; flex-direction: column; gap: 4px; overflow-y: auto; flex: 1; }
    #doc-list li {
      font-size: 12px; padding: 6px 8px; border-radius: 4px;
      background: #313244; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    #upload-status { font-size: 11px; color: #a6e3a1; min-height: 16px; }

    /* Main chat area */
    #main { flex: 1; display: flex; flex-direction: column; }
    #header { padding: 16px 20px; background: #fff; border-bottom: 1px solid #e0e0e0; font-weight: 600; font-size: 16px; }
    #messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }

    .msg { max-width: 75%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; font-size: 14px; }
    .msg.user { align-self: flex-end; background: #89b4fa; color: #1e1e2e; border-bottom-right-radius: 4px; }
    .msg.assistant { align-self: flex-start; background: #fff; border: 1px solid #e0e0e0; border-bottom-left-radius: 4px; }
    .sources { font-size: 11px; color: #888; margin-top: 6px; }

    #input-bar { display: flex; gap: 8px; padding: 16px 20px; background: #fff; border-top: 1px solid #e0e0e0; }
    #msg-input {
      flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px;
      font-size: 14px; outline: none;
    }
    #msg-input:focus { border-color: #89b4fa; }
    #send-btn {
      background: #89b4fa; color: #1e1e2e; border: none; border-radius: 8px;
      padding: 10px 18px; cursor: pointer; font-weight: 600; font-size: 14px;
    }
    #send-btn:hover { background: #74c7ec; }
    #send-btn:disabled { background: #ccc; cursor: not-allowed; }
  </style>
</head>
<body>

<div id="sidebar">
  <h2>Knowledge Base</h2>
  <button id="add-btn">+ Add PDF</button>
  <input type="file" id="file-input" accept=".pdf" />
  <div id="upload-status"></div>
  <ul id="doc-list"></ul>
</div>

<div id="main">
  <div id="header">Storage Expert</div>
  <div id="messages"></div>
  <div id="input-bar">
    <input id="msg-input" type="text" placeholder="Ask about your storage systems…" />
    <button id="send-btn">Send</button>
  </div>
</div>

<script>
  const sessionId = sessionStorage.getItem('session_id') || crypto.randomUUID();
  sessionStorage.setItem('session_id', sessionId);

  async function loadDocuments() {
    const res = await fetch('/documents');
    const data = await res.json();
    const list = document.getElementById('doc-list');
    list.innerHTML = '';
    data.documents.forEach(name => {
      const li = document.createElement('li');
      li.textContent = name;
      li.title = name;
      list.appendChild(li);
    });
  }

  document.getElementById('add-btn').addEventListener('click', () => {
    document.getElementById('file-input').click();
  });

  document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const status = document.getElementById('upload-status');
    status.textContent = 'Uploading…';

    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/ingest', { method: 'POST', body: form });
      const data = await res.json();
      if (res.ok) {
        status.textContent = `Stored ${data.chunks_stored} chunks`;
        await loadDocuments();
      } else {
        status.textContent = `Error: ${data.detail}`;
      }
    } catch {
      status.textContent = 'Upload failed';
    }
    e.target.value = '';
  });

  function appendMessage(role, text, sources) {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.textContent = text;
    if (sources && sources.length > 0) {
      const s = document.createElement('div');
      s.className = 'sources';
      s.textContent = 'Sources: ' + sources.join(' | ');
      div.appendChild(s);
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  async function sendMessage() {
    const input = document.getElementById('msg-input');
    const btn = document.getElementById('send-btn');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    btn.disabled = true;
    appendMessage('user', message);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      const data = await res.json();
      appendMessage('assistant', data.answer, data.sources);
    } catch {
      appendMessage('assistant', 'Error: could not reach the server.');
    }
    btn.disabled = false;
    input.focus();
  }

  document.getElementById('send-btn').addEventListener('click', sendMessage);
  document.getElementById('msg-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  loadDocuments();
</script>
</body>
</html>
```

- [ ] **Step 2: Test in browser**

```bash
source .venv/bin/activate
uvicorn web.server:app --port 8000 --reload
```

Open `http://localhost:8000` in a browser. Verify:
- Sidebar shows existing ingested PDFs
- "Add PDF" button opens file picker
- Uploading a PDF shows chunk count and refreshes sidebar
- Typing a question and pressing Enter (or Send) returns an answer with sources

- [ ] **Step 3: Commit**

```bash
git add web/static/index.html
git commit -m "feat: add single-page chat UI"
```

---

### Task 5: Docker setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY storage_expert/ ./storage_expert/
COPY web/ ./web/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  storage-expert:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./chroma_db:/app/chroma_db
    env_file:
      - .env
```

- [ ] **Step 3: Build and run**

```bash
docker compose build
docker compose up -d
curl -s http://localhost:8000/documents
```

Expected: `{"documents": [...]}` — same knowledge base as local (because `chroma_db/` is mounted).

- [ ] **Step 4: Commit and push**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: add Docker setup for cloud deployment"
git push
```
