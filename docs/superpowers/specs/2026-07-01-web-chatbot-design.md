# Web Chatbot — Design Spec

**Date:** 2026-07-01
**Project:** storage-expert

---

## Context

Add a web-based chat UI on top of the existing CLI RAG pipeline. Users can query the persistent ChromaDB knowledge base through a browser instead of the terminal. PDF ingestion remains available via CLI or via the web UI (both work, same ChromaDB store).

---

## Architecture

A `web/` layer added on top of existing modules — no changes to `storage_expert/` internals.

```
storage_expert/
├── storage_expert/         # existing (untouched)
│   ├── cli.py
│   ├── providers.py
│   ├── ingest.py
│   ├── qa.py
│   └── chat.py
├── web/
│   ├── server.py           # FastAPI app
│   └── static/
│       └── index.html      # Single-page chat UI (vanilla JS)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml          # add: fastapi, uvicorn, python-multipart
```

---

## API Endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| `GET /` | — | — | Serves `index.html` |
| `POST /chat` | `{message, session_id}` | — | `{answer, sources: [...]}` |
| `POST /ingest` | multipart PDF file | — | `{status, chunks_stored}` |
| `GET /documents` | — | — | `{documents: [...filenames]}` |

---

## Session Memory

- Client generates a UUID on page load, stored in `sessionStorage`
- Sent as `session_id` with every `/chat` request
- Server keeps an in-memory dict: `{session_id: [HumanMessage, AIMessage, ...]}`
- History resets on server restart (acceptable for v1)

---

## Frontend (index.html)

Single HTML file, vanilla JS, no build step.

**Layout:**
- **Left sidebar** — "Add PDF" button at the top; below it, list of all PDFs currently in the knowledge base (populated via `GET /documents` on load). Uploading a PDF calls `POST /ingest` and refreshes the list.
- **Main area** — chat window with message bubbles (user right, assistant left). Source citations shown in small text below each assistant reply.
- **Bottom bar** — text input + Send button. Enter key submits.

**Behavior:**
- Chat is ready immediately on load — no upload required if PDFs are already ingested
- Upload is for adding new documents to the persistent KB, not a per-session requirement

---

## Deployment

**Provider:** Fixed via `.env` (`STORAGE_EXPERT_PROVIDER`). Not selectable from the UI.

**Dockerfile:**
- Base: `python:3.11-slim`
- Installs via `pip install -e .`
- Exposes port `8000`
- Starts with `uvicorn web.server:app --host 0.0.0.0 --port 8000`

**docker-compose.yml:**
- One service
- Mounts `./chroma_db` as a volume (knowledge base persists across restarts)
- Reads `.env` for API keys and provider config

```bash
docker compose up -d   # start in background
```

---

## Error Handling

- Upload non-PDF → HTTP 400 with message
- Chat with empty KB → `{answer: "No documents in the knowledge base yet.", sources: []}`
- Missing API key → HTTP 500 with the specific env var name
- Unreadable PDF → HTTP 400, file skipped

---

## Dependencies to Add

```
fastapi>=0.111
uvicorn>=0.30
python-multipart>=0.0.9
```
