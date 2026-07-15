# Project Cleanup — Design

Date: 2026-07-15
Status: approved

## Goal

Remove dead weight left behind by the provider refactor (single OpenAI-compatible
endpoint), deduplicate code, fix per-request waste, and make deploy configs
consistent with the current architecture.

## 1. Dead files & artifacts

- Delete `models/` (~80MB HuggingFace cache; embeddings are API-based now) and `.DS_Store`.
- Keep `mcp_servers.json_` (user's saved MCP config, disabled by rename); ignore it in git.
- `.gitignore`: add `.vscode/`, `.pytest_cache/`, `.claude/`, `.playwright-mcp/`,
  `mcp_servers.json_`; drop stale `models/` and contradictory `docs/` entries
  (a spec file under `docs/` is already tracked).

## 2. Code quality

- `ingest.py`: make `get_vectorstore()` and `already_ingested()` public.
  Use them in `web/server.py` (`/documents`, `/ingest`, `/chat`), `qa.py`, and
  `chat.py`, which each construct the same Chroma object inline today.
- `/ingest` dedup reuses `already_ingested()` instead of an inline collection query.
- Makefile: delete the no-op `download-models` target, its help line, and `.PHONY` entry.
- Typing: `Optional[str]` → `str | None` (requires-python is >=3.11).

## 3. Performance

- `functools.lru_cache` on `get_llm(model)`, `get_embeddings()`, and
  `get_vectorstore()`. Config is env-driven and read once per process; a `.env`
  change already requires a restart, so cached singletons change no behavior.
- `/ingest` runs the blocking `ingest_file()` via `asyncio.to_thread` so large
  uploads no longer freeze the event loop (login/chat during ingestion).

## 4. Deploy & config coherence

- Dockerfile: `COPY system_prompt.md .` — the container currently falls back to
  the generic prompt because the file is missing from the image.
- docker-compose: mount `./vendor_pdfs` so uploaded PDFs survive rebuilds.
- deploy/ (systemd, nginx) and CI: verified, no stale references.

## Verification

1. `make check` — all smoke tests pass.
2. Grep confirms no references to removed symbols/targets remain.
3. Live end-to-end chat round against the running server.
