import json
from pathlib import Path
from typing import List

MCP_CONFIG_PATH = Path("mcp_servers.json")


def load_server_configs() -> List[dict]:
    if not MCP_CONFIG_PATH.exists():
        return []
    return json.loads(MCP_CONFIG_PATH.read_text())


def _to_adapter_config(servers: List[dict]) -> dict:
    config = {}
    for s in servers:
        if s["transport"] == "streamable_http":
            config[s["name"]] = {"url": s["url"], "transport": "streamable_http"}
        else:
            parts = s["command"].split()
            config[s["name"]] = {"command": parts[0], "args": parts[1:], "transport": "stdio"}
    return config


def _import_client():
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        return MultiServerMCPClient
    except ImportError:
        raise RuntimeError("MCP packages not installed. Run: pip install -e '.[mcp]'")


async def get_mcp_tools() -> list:
    servers = load_server_configs()
    if not servers:
        return []
    try:
        MultiServerMCPClient = _import_client()
    except RuntimeError:
        return []
    async with MultiServerMCPClient(_to_adapter_config(servers)) as client:
        return client.get_tools()


async def probe_servers() -> List[dict]:
    servers = load_server_configs()
    if not servers:
        return []
    try:
        MultiServerMCPClient = _import_client()
    except RuntimeError as e:
        return [{**s, "online": False, "tool_count": 0, "error": str(e)} for s in servers]
    results = []
    for s in servers:
        try:
            async with MultiServerMCPClient(_to_adapter_config([s])) as client:
                tools = client.get_tools()
            results.append({**s, "online": True, "tool_count": len(tools)})
        except Exception:
            results.append({**s, "online": False, "tool_count": 0})
    return results
