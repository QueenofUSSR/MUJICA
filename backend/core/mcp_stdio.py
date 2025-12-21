import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, Optional, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPStdioRunner:
    """
    Minimal MCP stdio runner:
    - spawn server process
    - initialize session
    - list_tools / call_tool
    - close cleanly
    """

    async def _open_session(
        self, command: str, args: list[str], env: Optional[Dict[str, str]] = None
    ) -> Tuple[AsyncExitStack, ClientSession]:
        exit_stack = AsyncExitStack()
        params = StdioServerParameters(command=command, args=args, env=env)
        stdio_transport = await exit_stack.enter_async_context(stdio_client(params))
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        return exit_stack, session

    async def list_tools(self, command: str, args: list[str], env: Optional[Dict[str, str]] = None) -> Any:
        exit_stack, session = await self._open_session(command, args, env)
        try:
            resp = await session.list_tools()
            return resp.tools
        finally:
            await exit_stack.aclose()

    async def call_tool(
        self,
        command: str,
        args: list[str],
        tool_name: str,
        tool_args: Dict[str, Any],
        env: Optional[Dict[str, str]] = None,
    ) -> Any:
        exit_stack, session = await self._open_session(command, args, env)
        try:
            result = await session.call_tool(tool_name, tool_args)
            return result.content
        finally:
            await exit_stack.aclose()
