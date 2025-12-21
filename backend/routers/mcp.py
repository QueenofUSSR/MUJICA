import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.mcp_stdio import MCPStdioRunner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])

CONFIG_PATH = Path("backend") / "static" / "mcp_config.json"


class MCPConfigIn(BaseModel):
    config: Dict[str, Any]


class CallToolIn(BaseModel):
    server: str
    tool: str
    args: Dict[str, Any] = {}
    # 可选：允许 override（过关版可以不做）
    override: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_servers(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # 兼容两种 key：mcpServers / servers
    if "mcpServers" in cfg and isinstance(cfg["mcpServers"], dict):
        return cfg["mcpServers"]
    if "servers" in cfg and isinstance(cfg["servers"], dict):
        return cfg["servers"]
    return {}


@router.get("/config")
def get_config():
    return {"config": _load_config()}


@router.post("/config")
def set_config(payload: MCPConfigIn):
    cfg = payload.config
    servers = _get_servers(cfg)
    if not servers:
        raise HTTPException(status_code=400, detail="Config must include 'mcpServers' or 'servers' with at least one server.")
    _save_config(cfg)
    logger.info("MCP config saved. servers=%s", list(servers.keys()))
    return {"ok": True, "servers": list(servers.keys())}


@router.get("/tools/{server_name}")
async def list_tools(server_name: str):
    cfg = _load_config()
    servers = _get_servers(cfg)
    if server_name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found in config.")

    s = servers[server_name]
    command = s.get("command")
    args = s.get("args", [])
    env = s.get("env")

    if not command or not isinstance(args, list):
        raise HTTPException(status_code=400, detail="Server config must include 'command' and list 'args' (stdio mode).")

    runner = MCPStdioRunner()
    tools = await runner.list_tools(command=command, args=args, env=env)
    # 返回更前端友好的结构
    return {
        "server": server_name,
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in tools
        ],
    }


@router.post("/call")
async def call_tool(payload: CallToolIn):
    cfg = _load_config()
    servers = _get_servers(cfg)

    if payload.server not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{payload.server}' not found in config.")
    s = dict(servers[payload.server])
    if payload.override:
        s.update(payload.override)

    command = s.get("command")
    args = s.get("args", [])
    env = s.get("env")

    if not command or not isinstance(args, list):
        raise HTTPException(status_code=400, detail="Server config must include 'command' and list 'args' (stdio mode).")

    logger.info("MCP call_tool server=%s tool=%s args=%s", payload.server, payload.tool, payload.args)

    runner = MCPStdioRunner()
    content = await runner.call_tool(
        command=command,
        args=args,
        tool_name=payload.tool,
        tool_args=payload.args,
        env=env,
    )
    return {"server": payload.server, "tool": payload.tool, "result": content}
