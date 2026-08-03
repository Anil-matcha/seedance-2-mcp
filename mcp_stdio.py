"""Standards-based MCP stdio transport for Seedance 2."""

from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from server_core import TOOLS, MuApiError, api_key_from_env, as_text, execute_tool


app = Server("seedance-2")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"],
            outputSchema=tool.get("outputSchema"),
        )
        for tool in TOOLS
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        api_key = api_key_from_env()
        result = await asyncio.to_thread(execute_tool, name, arguments, api_key, wait=True)
        return [TextContent(type="text", text=as_text(result))]
    except MuApiError as exc:
        return [TextContent(type="text", text=as_text(exc.as_dict()))]
    except Exception as exc:
        return [TextContent(type="text", text=as_text({"error": {"type": "validation_error", "message": str(exc)}}))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
