# Storage Expert

AI agent that reads enterprise storage vendor PDFs (NetApp, Pure Storage, Dell EMC, HPE, etc.) and answers natural language questions about specs, features, and compatibility.

Built with LangChain, ChromaDB, FastAPI, and your choice of LLM provider.

## Features

- **Web chatbot** — browser-based chat UI with conversation memory and markdown rendering
- **Ingest** vendor PDFs via web upload or CLI (single file or folder)
- **Ask** single-shot questions from the command line
- **Persistent** vector store — ingest once, query forever
- **Multi-provider** — Claude, OpenAI, Groq, Ollama, or any OpenAI-compatible router
- **Docker-ready** — single image, volume-mounted knowledge base
- **VM-ready** — systemd + nginx deployment included

---

## Quick Start (Local)

```bash
# 1. Clone and install
git clone https://github.com/ap369/storage-expert.git
cd storage-expert
make install

# 2. Configure
cp .env.example .env
# Edit .env and add your API key(s)

# 3. Start the web UI
make serve
# Open http://localhost:8000
# Upload PDFs from the sidebar and start chatting
```

---

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env and add your API key(s)

make docker-build
make docker-up
# Open http://localhost:8000

make docker-down   # stop
```

The `chroma_db/` knowledge base is mounted as a volume — it persists across container restarts.

---

## VM Deployment (systemd + nginx)

On a fresh Ubuntu 22.04 VM:

```bash
# 1. Install system dependencies
apt install -y python3 python3-venv nginx git

# 2. Clone the repo
git clone https://github.com/ap369/storage-expert.git /data/storage-expert
cd /data/storage-expert

# 3. Configure
cp .env.example .env && nano .env

# 4. Deploy (as root)
make deploy
# App is now running at http://<server-ip>
```

To update after a code change:
```bash
make deploy-update   # git pull + pip install + restart
```

---

## CLI Usage

```bash
# Ingest
make ingest ARGS="--file vendor_pdfs/netapp_aff_a800.pdf"
make ingest ARGS="--folder vendor_pdfs/"

# Single-shot question
make ask ARGS="'What is the max IOPS of the NetApp AFF A800?'"

# Interactive chat
make chat

# Or use the CLI directly
source .venv/bin/activate
storage-expert ask --provider groq "What protocols does Pure Storage support?"
storage-expert chat --provider openai
```

---

## Makefile Reference

Run `make` or `make help` to see all commands.

**Local development**

| Command | Description |
|---|---|
| `make install` | Create venv and install all dependencies |
| `make serve` | Start the web server at http://localhost:8000 |
| `make ingest ARGS="..."` | Ingest PDFs (--file or --folder) |
| `make ask ARGS="'question'"` | Ask a single question |
| `make chat` | Start interactive CLI chat |

**Knowledge base**

| Command | Description |
|---|---|
| `make reset` | Wipe ChromaDB (clean slate) |
| `make reingest` | Re-ingest all PDFs under `vendor_pdfs/` |

**Docker**

| Command | Description |
|---|---|
| `make docker-build` | Build the Docker image |
| `make docker-up` | Start the app with docker compose |
| `make docker-down` | Stop the app |

**VM deployment** (run as root on the server)

| Command | Description |
|---|---|
| `make deploy` | Full first-time setup (venv + systemd + nginx) |
| `make deploy-update` | Pull latest code and restart service |
| `make deploy-start/stop/restart` | Control the systemd service |
| `make deploy-status` | Show service status |
| `make deploy-logs` | Tail live service logs |

---

## Providers

| Provider | Env var required |
|---|---|
| `claude` (default) | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `groq` | `GROQ_API_KEY` |
| `ollama` | none (Ollama must be running) |
| `custom` | `CUSTOM_API_URL` + `CUSTOM_API_KEY` |

Set default provider in `.env`:
```env
STORAGE_EXPERT_PROVIDER=groq
```

Override at runtime: `storage-expert chat --provider openai`

---

## Embeddings

Default: `all-MiniLM-L6-v2` via `sentence-transformers` — runs locally, no API key needed (~80MB download on first use).

Override via `STORAGE_EXPERT_EMBEDDINGS` in `.env`:

| Value | Backend | Requirement |
|---|---|---|
| `huggingface` (default) | Local sentence-transformers | none |
| `openai` | OpenAI text-embedding-3-small | `OPENAI_API_KEY` |
| `ollama` | Ollama nomic-embed-text | Ollama running |

---

## Project Structure

```
storage_expert/
├── storage_expert/       # Core RAG pipeline (CLI)
│   ├── cli.py            # Click CLI — ingest / ask / chat
│   ├── providers.py      # LLM + embeddings config
│   ├── ingest.py         # PDF → chunks → ChromaDB
│   ├── qa.py             # Single-shot Q&A
│   └── chat.py           # Interactive chat with memory
├── web/
│   ├── server.py         # FastAPI app (REST API)
│   └── static/
│       └── index.html    # Single-page chat UI
├── deploy/
│   ├── storage-expert.service   # systemd unit file
│   └── nginx.conf               # nginx reverse proxy config
├── vendor_pdfs/          # Drop PDFs here (gitignored)
├── chroma_db/            # Persistent vector store (gitignored)
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Requirements

- Python 3.9+
- An API key for your chosen LLM provider
- Docker (optional, for containerized deployment)
- nginx + systemd (optional, for VM deployment)
