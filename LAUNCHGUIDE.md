# Seedance 2 MCP Server

## Overview

- **Name:** Seedance 2 MCP Server
- **Tagline:** Generate Seedance 2 videos from any MCP-compatible assistant
- **Homepage:** https://muapi.ai
- **Repository:** https://github.com/Anil-matcha/seedance-2-mcp
- **License:** MIT
- **Category:** Video Generation, AI, MCP

## Description

This focused server exposes Seedance 2 text-to-video, image-to-video, first/last-frame, and omni-reference generation through MuAPI. It supports a standards-based local stdio transport plus an HTTP bridge with discovery, async prediction polling, and SSE status streaming.

## Setup

```bash
export MUAPI_API_KEY=your_muapi_key_here
python -m pip install -r requirements.txt
python mcp_stdio.py
```

## Transport

- **stdio:** `python mcp_stdio.py`
- **HTTP bridge:** `python mcp_server.py`, default port `8000`

## Authentication

The stdio process reads `MUAPI_API_KEY` (or legacy `MUAPIAPP_API_KEY`) from its environment. The HTTP bridge accepts the same environment variable or an `Authorization: Bearer ...` / `x-api-key` header.

## Tool count

Six tools: four Seedance 2 generation tools, `muapi_predict_result`, and `muapi_account_balance`.
