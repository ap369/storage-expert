"""Import-level and unit smoke tests — no API keys, no network, no ChromaDB."""
import importlib
import pytest


# ── Third-party package sanity check ─────────────────────────────────────────
# Each entry is a package whose top-level import crashing = app won't start.
# Explicit list makes regressions visible immediately (vs. buried tracebacks).

_THIRD_PARTY = [
    # LangChain ecosystem
    "langchain_chroma",
    "langchain_core",
    "langchain_community",
    "langchain_huggingface",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_groq",
    "langchain_ollama",
    "langchain_text_splitters",
    # ML / embedding stack (version skew between transformers/torch causes crashes)
    "chromadb",
    "fitz",                 # pymupdf — public API is under 'fitz'
    "sentence_transformers",
    "transformers",
    # Web layer
    "fastapi",
    "uvicorn",
    "starlette",
    "pydantic",
    # CLI / auth
    "click",
    "dotenv",
    "bcrypt",
]


@pytest.mark.parametrize("package", _THIRD_PARTY)
def test_third_party_importable(package):
    importlib.import_module(package)


# ── Core module imports ───────────────────────────────────────────────────────

def test_import_ingest():
    import storage_expert.ingest

def test_import_qa():
    import storage_expert.qa

def test_import_chat():
    import storage_expert.chat

def test_import_providers():
    import storage_expert.providers

def test_import_auth():
    import storage_expert.auth

def test_import_mcp_client():
    import storage_expert.mcp_client

def test_import_cli():
    import storage_expert.cli

def test_import_web_server():
    import web.server
    assert web.server.app is not None


# ── mcp_client: load_server_configs ──────────────────────────────────────────

def test_load_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from storage_expert import mcp_client
    importlib.reload(mcp_client)
    assert mcp_client.load_server_configs() == []

def test_load_array_with_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mcp_servers.json").write_text(
        '[{"name": "A", "transport": "streamable_http", "url": "http://localhost/mcp"}]'
    )
    from storage_expert import mcp_client
    importlib.reload(mcp_client)
    assert mcp_client.load_server_configs()[0]["name"] == "A"

def test_load_array_missing_name_gets_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mcp_servers.json").write_text(
        '[{"transport": "streamable_http", "url": "http://localhost/mcp"}]'
    )
    from storage_expert import mcp_client
    importlib.reload(mcp_client)
    servers = mcp_client.load_server_configs()
    assert "name" in servers[0]

def test_load_claude_desktop_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mcp_servers.json").write_text(
        '{"mcpServers": {"MyServer": {"command": "npx foo", "transport": "stdio"}}}'
    )
    from storage_expert import mcp_client
    importlib.reload(mcp_client)
    assert mcp_client.load_server_configs()[0]["name"] == "MyServer"


# ── mcp_client: _to_adapter_config ───────────────────────────────────────────

def test_adapter_http():
    from storage_expert.mcp_client import _to_adapter_config
    cfg = _to_adapter_config([{"name": "X", "transport": "streamable_http", "url": "http://x/mcp"}])
    assert cfg["X"]["transport"] == "streamable_http"
    assert cfg["X"]["url"] == "http://x/mcp"

def test_adapter_stdio_split_string():
    from storage_expert.mcp_client import _to_adapter_config
    cfg = _to_adapter_config([{"name": "X", "command": "npx foo-server"}])
    assert cfg["X"]["command"] == "npx"
    assert cfg["X"]["args"] == ["foo-server"]

def test_adapter_stdio_explicit_args():
    from storage_expert.mcp_client import _to_adapter_config
    cfg = _to_adapter_config([{"name": "X", "command": "npx", "args": ["foo-server"]}])
    assert cfg["X"]["command"] == "npx"
    assert cfg["X"]["args"] == ["foo-server"]

def test_adapter_infers_transport_from_url():
    from storage_expert.mcp_client import _to_adapter_config
    cfg = _to_adapter_config([{"name": "X", "url": "http://x/mcp"}])
    assert cfg["X"]["transport"] == "streamable_http"


# ── auth: init_db / add_user / verify_user ───────────────────────────────────

def test_auth_roundtrip(tmp_path, monkeypatch):
    import storage_expert.auth as auth_mod
    monkeypatch.setattr(auth_mod, "DB_PATH", tmp_path / "users.db")
    auth_mod.init_db()
    auth_mod.add_user("alice", "s3cr3t!")
    assert auth_mod.verify_user("alice", "s3cr3t!") is True
    assert auth_mod.verify_user("alice", "wrong") is False
    assert auth_mod.verify_user("nobody", "s3cr3t!") is False

def test_duplicate_user_raises(tmp_path, monkeypatch):
    import sqlite3
    import storage_expert.auth as auth_mod
    monkeypatch.setattr(auth_mod, "DB_PATH", tmp_path / "users.db")
    auth_mod.init_db()
    auth_mod.add_user("bob", "pass1")
    with pytest.raises(sqlite3.IntegrityError):
        auth_mod.add_user("bob", "pass2")
