"""
Mindbase MCP Server

Exposes tools for AI models to read and write user context:
- mindbase_remember: store a thought/note
- mindbase_search: semantic search over context
- mindbase_recent: get recent context
- mindbase_summary: get compact markdown summary for system prompt injection
"""

import asyncio
import json
import logging

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mindbase_shared.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mindbase-mcp")
settings = Settings()

server = Server("mindbase")


def api_headers() -> dict:
    return {"X-API-Key": settings.mindbase_api_key, "Content-Type": "application/json"}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="mindbase_remember",
            description="Save a thought, note, or observation to the user's persistent context memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Text to remember"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                    "source": {"type": "string", "default": "mcp"},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="mindbase_search",
            description="Search the user's context memory by keyword/topic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="mindbase_recent",
            description="Get the user's most recent context entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="mindbase_summary",
            description="Get a compact markdown summary of recent context — ideal for system prompt injection.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    base = settings.mindbase_api_url.rstrip("/")

    async with httpx.AsyncClient(timeout=30) as client:
        if name == "mindbase_remember":
            payload = {
                "content": arguments["content"],
                "source": arguments.get("source", "mcp"),
                "metadata": {"tags": arguments.get("tags", []), "via": "mcp"},
            }
            resp = await client.post(f"{base}/v1/ingest", headers=api_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            return [TextContent(type="text", text=f"Saved to Mindbase (fragment {data['fragment_id']})")]

        if name == "mindbase_search":
            payload = {"query": arguments["query"], "limit": arguments.get("limit", 10)}
            resp = await client.post(f"{base}/v1/search", headers=api_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2, default=str))]

        if name == "mindbase_recent":
            limit = arguments.get("limit", 20)
            resp = await client.get(f"{base}/v1/context/recent", headers=api_headers(), params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
            return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2, default=str))]

        if name == "mindbase_summary":
            resp = await client.get(f"{base}/v1/context/summary", headers=api_headers())
            resp.raise_for_status()
            data = resp.json()
            return [TextContent(type="text", text=data["content"])]

    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
