# Storage Expert

AI agent that reads enterprise storage vendor PDFs (NetApp, Pure Storage, Dell EMC, HPE, etc.) and answers natural language questions about specs, features, and compatibility.

Built with LangChain, ChromaDB, FastAPI, and any OpenAI-compatible LLM endpoint.

## Features

- **Web chatbot** — browser-based chat UI with conversation memory and markdown rendering
- **Authentication** — login page, session cookies, CLI user management
- **Ingest** vendor PDFs via web upload or CLI (single file or folder)
- **Ask** single-shot questions from the command line
- **Persistent** vector store — ingest once, query forever
- **Provider-agnostic** — works with any OpenAI-compatible endpoint (OpenAI, Groq, Ollama, vLLM, LiteLLM, ...)
- **MCP support** — connect any MCP server for live tool calling alongside RAG
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

# 3. Create your first user
make adduser ARGS="yourname"

# 4. Start the web UI
make serve
# Open http://localhost:8000 and log in
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

# 4. Create a user
make adduser ARGS="admin"

# 5. Deploy (as root)
make deploy
# App is now running at http://<server-ip>
```

To update after a code change:
```bash
make deploy-update   # git pull + pip install + restart
```

---

## Authentication

Access to the web UI requires a login. Users are managed via CLI — there is no self-registration.

```bash
# Create a user
make adduser ARGS="alice"
# Prompts for password (hidden input, confirmed twice)

# Or directly
storage-expert adduser alice
```

Users are stored in `users.db` (SQLite, gitignored). Passwords are hashed with bcrypt + SHA-256.

---

## MCP Integration

Connect any MCP server to give the LLM access to live tools (e.g. NetApp APIs) alongside the PDF knowledge base.

```bash
# 1. Install MCP extras (requires Python 3.10+)
pip install -e '.[mcp]'

# 2. Create mcp_servers.json (gitignored)
cp mcp_servers.example.json mcp_servers.json
# Edit with your actual server details
```

`mcp_servers.json` format:
```json
[
  { "name": "NetApp", "transport": "streamable_http", "url": "http://localhost:3000/mcp" },
  { "name": "Pure Storage", "transport": "stdio", "command": "npx @purestorage/mcp-server" }
]
```

The sidebar shows each server's online/offline status and tool count, refreshing every 30 seconds.

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
storage-expert ask "What protocols does Pure Storage support?"
storage-expert chat --model llama-3.3-70b-versatile   # optional per-run model override
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

**User management**

| Command | Description |
|---|---|
| `make adduser ARGS="username"` | Create a web UI user (prompts for password) |

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

## LLM & Embeddings Configuration

Any OpenAI-compatible endpoint works. Configure in `.env`:

```env
# LLM (required)
API_URL=https://api.groq.com/openai/v1
API_KEY=your-api-key            # any placeholder value for keyless endpoints
LLM_MODEL=llama-3.3-70b-versatile

# Embeddings (defaults to the LLM endpoint; only used when RAG is enabled)
EMBED_API_URL=http://localhost:11434/v1   # e.g. local Ollama
EMBED_API_KEY=                            # leave empty for keyless endpoints
EMBED_MODEL=all-minilm
```

Example endpoints: OpenAI (`https://api.openai.com/v1`), Groq (`https://api.groq.com/openai/v1`), local Ollama (`http://localhost:11434/v1`), or any vLLM/LiteLLM router.

> **Note:** if you change `EMBED_MODEL` after ingesting documents, wipe and re-ingest —
> embedding dimensions differ between models: `make reset && make reingest`

---

## Project Structure

```
storage_expert/
├── storage_expert/          # Core RAG pipeline (CLI)
│   ├── cli.py               # Click CLI — ingest / ask / chat / adduser
│   ├── providers.py         # LLM + embeddings config
│   ├── ingest.py            # PDF → chunks → ChromaDB
│   ├── qa.py                # Single-shot Q&A
│   ├── chat.py              # Interactive chat with memory
│   ├── auth.py              # User management (SQLite + bcrypt)
│   └── mcp_client.py        # MCP server connection + tool loader
├── web/
│   ├── server.py            # FastAPI app (REST API + auth)
│   └── static/
│       ├── index.html       # Single-page chat UI
│       └── login.html       # Login page
├── deploy/
│   ├── storage-expert.service   # systemd unit file
│   └── nginx.conf               # nginx reverse proxy config
├── vendor_pdfs/             # Drop PDFs here (gitignored)
├── chroma_db/               # Persistent vector store (gitignored)
├── mcp_servers.json         # MCP server config (gitignored)
├── mcp_servers.example.json # MCP config template
├── users.db                 # User database (gitignored)
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Requirements

- Python 3.11+
- An OpenAI-compatible LLM endpoint (URL + API key)
- Docker (optional, for containerized deployment)
- nginx + systemd (optional, for VM deployment)
