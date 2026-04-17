"""
mcp_client.py  —  MCP Client wrapper
======================================
Wraps the real MCP ClientSession so the agent can call tools
through the proper MCP protocol.

The MCP server runs as a subprocess; communication is over stdio.
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server.py")


class MCPClient:
    """
    Async context manager that starts the MCP server subprocess and
    maintains a live ClientSession for the agent to use.

    Usage:
        async with MCPClient() as client:
            tools   = await client.list_tools()
            result  = await client.call_tool("add_transaction", {...})
    """

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._exit_stack = None
        self._stdio_cm = None
        self._session_cm = None

    async def __aenter__(self) -> "MCPClient":
        params = StdioServerParameters(
            command=sys.executable,
            args=[SERVER_SCRIPT],
        )
        self._stdio_cm = stdio_client(params)
        read_stream, write_stream = await self._stdio_cm.__aenter__()

        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()

        await self._session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session_cm:
            await self._session_cm.__aexit__(*exc)
        if self._stdio_cm:
            await self._stdio_cm.__aexit__(*exc)

    async def list_tools(self) -> list[dict]:
        """Return list of tool dicts with name, description, inputSchema."""
        response = await self._session.list_tools()
        return [
            {
                "name":        t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
            }
            for t in response.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """
        Call a tool on the MCP server.
        Returns the raw text content of the first result block.
        """
        result = await self._session.call_tool(name, arguments)
        if result.content:
            return result.content[0].text
        return json.dumps({"error": "empty result"})


# ── Convenience: run a single tool call without keeping session open ──────────

async def quick_call(tool_name: str, arguments: dict) -> str:
    async with MCPClient() as client:
        return await client.call_tool(tool_name, arguments)


async def quick_summary() -> dict:
    async with MCPClient() as client:
        raw = await client.call_tool("get_summary", {})
        return json.loads(raw)


async def quick_transactions() -> list:
    async with MCPClient() as client:
        raw = await client.call_tool("get_transactions", {})
        return json.loads(raw)
