import os
from typing import Optional


def _build_config() -> Optional[dict]:
    url = os.getenv("MCP_SERVER_URL")
    cmd = os.getenv("MCP_SERVER_COMMAND")
    if url:
        return {"mcp": {"url": url, "transport": "streamable_http"}}
    if cmd:
        parts = cmd.split()
        return {"mcp": {"command": parts[0], "args": parts[1:], "transport": "stdio"}}
    return None


async def get_mcp_tools() -> list:
    config = _build_config()
    if not config:
        return []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        raise RuntimeError(
            "MCP packages not installed. Run: pip install -e '.[mcp]'"
        )
    async with MultiServerMCPClient(config) as client:
        return client.get_tools()
