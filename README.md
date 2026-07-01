# Storage Expert

AI agent that reads enterprise storage vendor PDFs (NetApp, Pure Storage, Dell EMC, HPE, etc.) and answers natural language questions about specs, features, and compatibility.

Built with LangChain, ChromaDB, and your choice of LLM provider.

## Features

- **Ingest** vendor PDFs — single file or entire folder
- **Ask** single-shot questions from the command line
- **Chat** interactively with conversation memory across turns
- **Persistent** vector store — ingest once, query forever
- **Multi-provider** — Claude, OpenAI, Groq, Ollama, or any OpenAI-compatible router

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/ap369/storage-expert.git
cd storage-expert
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env and add your API key(s)

# 3. Ingest vendor PDFs
storage-expert ingest --folder vendor_pdfs/
# or a single file:
storage-expert ingest --file netapp_aff_a800.pdf

# 4. Ask questions
storage-expert ask "What is the max IOPS of the NetApp AFF A800?"

# 5. Or chat interactively
storage-expert chat
```

## Providers

| Provider | Flag | Required env var |
|---|---|---|
| Claude (default) | `--provider claude` | `ANTHROPIC_API_KEY` |
| OpenAI | `--provider openai` | `OPENAI_API_KEY` |
| Groq | `--provider groq` | `GROQ_API_KEY` |
| Ollama (local) | `--provider ollama` | none |
| Custom / router | `--provider custom` | `CUSTOM_API_URL` + `CUSTOM_API_KEY` |

Switch provider at runtime:

```bash
storage-expert ask --provider groq "What protocols does Pure Storage support?"
storage-expert chat --provider openai
storage-expert chat --provider ollama --model llama3
```

Set a default in `.env`:

```env
STORAGE_EXPERT_PROVIDER=groq
```

## Embeddings

Embeddings default to `all-MiniLM-L6-v2` running locally via `sentence-transformers` — no API key needed, ~80MB download on first use.

Override via `STORAGE_EXPERT_EMBEDDINGS` in `.env`:

| Value | Backend | Requirement |
|---|---|---|
| `huggingface` (default) | Local sentence-transformers | none |
| `openai` | OpenAI text-embedding-3-small | `OPENAI_API_KEY` |
| `ollama` | Ollama nomic-embed-text | Ollama running locally |

## Project Structure

```
storage_expert/
├── storage_expert/
│   ├── cli.py          # Click CLI — ingest / ask / chat commands
│   ├── providers.py    # LLM + embeddings configuration
│   ├── ingest.py       # PDF loading, chunking, ChromaDB storage
│   ├── qa.py           # Single-shot Q&A
│   └── chat.py         # Interactive chat with conversation memory
├── vendor_pdfs/        # Drop your PDFs here (gitignored)
├── chroma_db/          # Persistent vector store (gitignored)
├── .env.example        # Environment variable reference
└── pyproject.toml
```

## Requirements

- Python 3.9+
- An API key for your chosen LLM provider
