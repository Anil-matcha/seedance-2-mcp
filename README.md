# Seedance 2 MCP Server

[![Powered by MuAPI](https://img.shields.io/badge/Powered%20by-MuAPI-6366f1?style=flat-square)](https://muapi.ai)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-green?style=flat-square)](https://modelcontextprotocol.io)

A focused [Model Context Protocol](https://modelcontextprotocol.io) server for generating Seedance 2 videos through [MuAPI](https://muapi.ai). It exposes only the Seedance 2 workflows, so an assistant gets useful model-specific schemas instead of a large general-purpose catalog.

The implementation is informed by [SamurAIGPT/muapi-mcp-server](https://github.com/SamurAIGPT/muapi-mcp-server): it forwards a MuAPI key, keeps generation asynchronous, and provides both an MCP stdio transport and a small HTTP bridge.

## 📺 Video Tutorial

[![How to Access Seedance 2.5 API (Step-by-Step Guide)](https://img.youtube.com/vi/Uszlw7H4VP4/maxresdefault.jpg)](https://www.youtube.com/watch?v=Uszlw7H4VP4)

**[How to Access Seedance 2.5 API (Step-by-Step Guide)](https://www.youtube.com/watch?v=Uszlw7H4VP4)** — a full walkthrough of getting an API key and making your first Seedance 2.5 call via [MuAPI](https://muapi.ai/seedance-2.5?utm_source=github&utm_medium=readme&utm_campaign=seedance-2-mcp).

## Related Projects

- [MuAPI Seedance 2](https://muapi.ai/seedance-2) — Model landing page and browser playground links for the Seedance 2 family.
- [MuAPI MCP documentation](https://muapi.ai/docs/mcp) — Hosted MCP setup and tool-use guidance.
- [MuAPI access keys](https://muapi.ai/access-keys) — Create the API key required by this server.
- [Seedance-2-API](https://github.com/Anil-matcha/Seedance-2-API) — Python wrapper for Seedance 2.0 and Seedance 2 Mini.
- [seedance-2-generator](https://github.com/SamurAIGPT/seedance-2-generator) — Ready-made Next.js SaaS built on Seedance 2.
- [seedance2-comfyui](https://github.com/Anil-matcha/seedance2-comfyui) — Seedance 2 custom nodes and workflows for ComfyUI.
- [n8n-nodes-seedance2](https://github.com/Anil-matcha/n8n-nodes-seedance2) — Automate Seedance 2 generation in n8n.
- [awesome-seedance-2.5-api-prompts](https://github.com/Anil-matcha/awesome-seedance-2.5-api-prompts) — Prompt and camera-control references for the Seedance family.
- [muapi-mcp-server](https://github.com/SamurAIGPT/muapi-mcp-server) — Broad MuAPI MCP server reference for Claude, Cursor, and other clients.
- [Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI) — Open-source media studio that uses MuAPI for image and video workflows.

## Included tools

| Tool | Purpose |
| --- | --- |
| `seedance_2_text_to_video` | Text-to-video generation; `standard` or `fast` quality route |
| `seedance_2_image_to_video` | Animate one or more image references |
| `seedance_2_first_last_frame` | Generate a transition from one or two frame images |
| `seedance_2_omni_reference` | Combine image, video, and audio references |
| `muapi_predict_result` | Poll a MuAPI prediction by `request_id` |
| `muapi_account_balance` | Read the MuAPI credit balance |

Generation tools return the completed prediction when used over stdio. The HTTP bridge returns a local request ID immediately and exposes the result at `/mcp/predictions/{request_id}` or as server-sent events.

## Quick start

```bash
git clone https://github.com/Anil-matcha/seedance-2-mcp.git
cd seedance-2-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MUAPI_API_KEY=your_muapi_key_here
```

Run the standards-based stdio server for an MCP client:

```bash
python mcp_stdio.py
```

Run the local HTTP bridge instead:

```bash
python mcp_server.py
# http://localhost:8000/docs
```

`MUAPIAPP_API_KEY` is accepted as a backwards-compatible alternative. `MUAPI_BASE_URL`, `MUAPI_HTTP_TIMEOUT`, `MUAPI_POLL_INTERVAL`, and `MUAPI_POLL_TIMEOUT` can be used for local testing or a compatible MuAPI deployment.

## Claude Code

With `MUAPI_API_KEY` exported in the shell used by Claude Code:

```bash
claude mcp add seedance-2 -- python /absolute/path/to/seedance-2-mcp/mcp_stdio.py
```

## Cursor, Windsurf, and Claude Desktop

Copy the `mcp.json` entry and replace the placeholder path. Keep the API key in the client environment; do not commit it.

```json
{
  "mcpServers": {
    "seedance-2": {
      "command": "python",
      "args": ["/absolute/path/to/seedance-2-mcp/mcp_stdio.py"],
      "env": {
        "MUAPI_API_KEY": "${MUAPI_API_KEY}"
      }
    }
  }
}
```

## HTTP bridge

The HTTP process is useful for local integrations that need a simple request/poll surface:

```bash
curl http://localhost:8000/mcp/tools

curl -X POST http://localhost:8000/mcp/tools/seedance_2_text_to_video/call \
  -H "Authorization: Bearer $MUAPI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "prompt": "A red paper boat drifting through a sunlit forest stream, cinematic camera movement",
      "duration": 5,
      "aspect_ratio": "16:9",
      "quality": "standard"
    }
  }'
```

Poll the returned local ID:

```bash
curl http://localhost:8000/mcp/predictions/REQUEST_ID
curl -N http://localhost:8000/mcp/predictions/REQUEST_ID/stream
```

The bridge allowlists all upstream paths and never accepts an arbitrary endpoint URL. Generation and polling consume MuAPI credits according to the selected route.

## Model notes

The server uses MuAPI's Seedance 2 API routes. A single image is a start frame; multiple images can be referenced in the prompt as `@image1`, `@image2`, and so on. Omni reference inputs use `@imageN`, `@videoN`, and `@audioN`. For reproducible prompts, keep the full scene, camera, lighting, and motion direction in the prompt.

## Docker

```bash
docker build -t seedance-2-mcp .
docker run --rm -p 8000:8000 -e MUAPI_API_KEY="$MUAPI_API_KEY" seedance-2-mcp
```

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q server_core.py mcp_server.py mcp_stdio.py
```

## License

MIT. See [LICENSE](LICENSE).
