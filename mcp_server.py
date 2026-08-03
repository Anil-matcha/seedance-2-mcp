"""Small HTTP bridge for running the Seedance 2 MCP catalog locally.

The standards-based stdio transport lives in :mod:`mcp_stdio`. This HTTP
surface follows the practical endpoints used by the MuAPI reference server,
which makes it useful for local dashboards, Cursor integrations, and simple
health checks without exposing arbitrary upstream endpoints.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server_core import (
    API_BASE,
    TOOLS,
    TOOL_BY_NAME,
    MuApiError,
    api_key_from_env,
    as_text,
    execute_tool,
)


app = FastAPI(
    title="Seedance 2 MCP Server",
    version="1.0.0",
    description="Focused MCP-compatible HTTP bridge for Seedance 2 via MuAPI.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ToolCallRequest(BaseModel):
    name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    tool: str | None = None
    model: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)


TASKS: dict[str, dict[str, Any]] = {}


def _api_key(authorization: str | None, x_api_key: str | None) -> str:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return api_key_from_env()


def _require_api_key(authorization: str | None, x_api_key: str | None) -> str:
    key = _api_key(authorization, x_api_key)
    if not key:
        raise HTTPException(
            status_code=401,
            detail="MuAPI API key required. Set MUAPI_API_KEY or send x-api-key/Authorization.",
        )
    return key


def _tool_name(tool: str | None, model: str | None) -> str:
    selected = tool or model
    if not selected:
        raise HTTPException(status_code=400, detail="tool is required")
    # Accept the MCP tool name as the canonical form. Model aliases are kept
    # intentionally narrow so this bridge cannot proxy arbitrary URLs.
    aliases = {
        "seedance-2-text-to-video": "seedance_2_text_to_video",
        "seedance-2-image-to-video": "seedance_2_image_to_video",
        "seedance-2-first-last-frame": "seedance_2_first_last_frame",
        "seedance-2-omni-reference": "seedance_2_omni_reference",
    }
    selected = aliases.get(selected, selected)
    if selected not in TOOL_BY_NAME:
        raise HTTPException(status_code=404, detail="Tool not found")
    return selected


async def _run_task(request_id: str, tool_name: str, arguments: dict[str, Any], api_key: str) -> None:
    TASKS[request_id]["status"] = "processing"
    try:
        result = await asyncio.to_thread(execute_tool, tool_name, arguments, api_key, wait=True)
        TASKS[request_id].update(
            {
                "status": "completed",
                "result": result,
                "completed_at": time.time(),
            }
        )
    except MuApiError as exc:
        TASKS[request_id].update(
            {
                "status": "failed",
                **exc.as_dict(),
                "failed_at": time.time(),
            }
        )
    except Exception as exc:  # pragma: no cover - final safety net for a worker task
        TASKS[request_id].update(
            {
                "status": "failed",
                "error": {"type": "validation_error", "message": str(exc)},
                "failed_at": time.time(),
            }
        )


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "Seedance 2 MCP Server",
        "version": "1.0.0",
        "transport": "HTTP bridge; use mcp_stdio.py for MCP stdio",
        "muapi_base_url": API_BASE,
        "endpoints": {
            "health": "/health",
            "tools": "/mcp/tools",
            "resources": "/mcp/resources",
            "call_tool": "/mcp/tools/{tool_name}/call",
            "run": "/mcp/run",
            "predictions": "/mcp/predictions/{request_id}",
            "stream": "/mcp/predictions/{request_id}/stream",
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "tools": len(TOOLS)}


@app.get("/mcp/tools")
async def list_tools() -> dict[str, Any]:
    return {"tools": TOOLS}


@app.get("/mcp/resources")
async def list_resources() -> dict[str, Any]:
    return {
        "resources": [
            {
                "uri": f"muapi://{tool['name']}",
                "name": tool["name"],
                "description": tool["description"],
                "mimeType": "application/json",
            }
            for tool in TOOLS
        ]
    }


@app.get("/mcp/resources/{tool_name}")
async def get_resource(tool_name: str) -> dict[str, Any]:
    tool = TOOL_BY_NAME.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {
        "uri": f"muapi://{tool_name}",
        "contents": [
            {
                "uri": f"muapi://{tool_name}",
                "mimeType": "application/json",
                "text": as_text(tool),
            }
        ],
    }


@app.get("/cursor/capabilities")
async def cursor_capabilities() -> dict[str, Any]:
    return {
        "name": "Seedance 2 Generator",
        "description": "Focused Seedance 2 video generation via MuAPI.",
        "capabilities": {
            "canGenerate": ["video"],
            "supportsAsync": True,
            "supportsStreaming": True,
            "requiresApiKey": True,
        },
        "tools": TOOLS,
    }


async def _enqueue(
    tool_name: str,
    arguments: dict[str, Any],
    api_key: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    TASKS[request_id] = {
        "request_id": request_id,
        "tool": tool_name,
        "status": "queued",
        "created_at": time.time(),
    }
    background_tasks.add_task(_run_task, request_id, tool_name, arguments, api_key)
    return {"request_id": request_id, "status": "queued", "tool": tool_name}


@app.post("/mcp/tools/{tool_name}/call")
async def call_tool(
    tool_name: str,
    request: ToolCallRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    tool_name = _tool_name(tool_name, request.name)
    api_key = _require_api_key(authorization, x_api_key)
    return await _enqueue(tool_name, request.arguments, api_key, background_tasks)


@app.post("/mcp/run")
async def run_model(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    tool_name = _tool_name(request.tool, request.model)
    api_key = _require_api_key(authorization, x_api_key)
    return await _enqueue(tool_name, request.input, api_key, background_tasks)


@app.get("/mcp/predictions/{request_id}")
async def get_prediction(request_id: str) -> dict[str, Any]:
    task = TASKS.get(request_id)
    if not task:
        raise HTTPException(status_code=404, detail="Request ID not found")
    return task


@app.get("/mcp/predictions/{request_id}/stream")
async def stream_prediction(request_id: str) -> StreamingResponse:
    if request_id not in TASKS:
        raise HTTPException(status_code=404, detail="Request ID not found")

    async def events():
        last_status = None
        while True:
            task = TASKS.get(request_id)
            if not task:
                yield f"data: {as_text({'error': 'Request ID not found'})}\n\n"
                return
            if task["status"] != last_status:
                yield f"data: {as_text(task)}\n\n"
                last_status = task["status"]
            if task["status"] in {"completed", "failed"}:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=int(__import__("os").getenv("PORT", "8000")))
