import json
from pathlib import Path
from typing import List

MCP_CONFIG_PATH = Path("mcp_servers.json")


def load_server_configs() -> List[dict]:
    if not MCP_CONFIG_PATH.exists():
        return []
    data = json.loads(MCP_CONFIG_PATH.read_text())
    # Support Claude Desktop dict format: {"mcpServers": {"Name": {...}}}
    if isinstance(data, dict):
        servers = data.get("mcpServers", data)
        return [{"name": name, **cfg} for name, cfg in servers.items()]
    # Ensure every entry has a name
    for i, s in enumerate(data):
        if "name" not in s:
            s["name"] = s.get("url") or s.get("command", f"server-{i}")
    return data


def _to_adapter_config(servers: List[dict]) -> dict:
    config = {}
    for s in servers:
        name = s["name"]
        transport = s.get("transport", "streamable_http" if "url" in s else "stdio")
        if transport == "streamable_http":
            entry = {"url": s["url"], "transport": "streamable_http"}
            if s.get("headers"):
                entry["headers"] = s["headers"]
            config[name] = entry
        else:
            if s.get("args") is not None:
                # Claude Desktop format: command is binary, args is a list
                config[name] = {"command": s["command"], "args": s["args"], "transport": "stdio"}
            else:
                # Our format: command is the full string to split
                parts = s["command"].split()
                config[name] = {"command": parts[0], "args": parts[1:], "transport": "stdio"}
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
    client = MultiServerMCPClient(_to_adapter_config(servers))
    return await client.get_tools()


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
            client = MultiServerMCPClient(_to_adapter_config([s]))
            tools = await client.get_tools()
            results.append({**s, "online": True, "tool_count": len(tools)})
        except Exception:
            results.append({**s, "online": False, "tool_count": 0})
    return results
