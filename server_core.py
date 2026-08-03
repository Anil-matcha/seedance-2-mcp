"""Shared catalog and MuAPI client for the Seedance 2 MCP servers.

The reference MuAPI MCP server exposes a broad, hand-maintained model catalog.
This project keeps the same useful ideas—MuAPI API-key forwarding, allowlisted
model routes, and explicit async prediction polling—but narrows the catalog to
Seedance 2 so clients get a small, predictable tool surface.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests


API_BASE = os.getenv("MUAPI_BASE_URL", "https://api.muapi.ai/api/v1").rstrip("/")
HTTP_TIMEOUT = float(os.getenv("MUAPI_HTTP_TIMEOUT", "120"))
POLL_INTERVAL = float(os.getenv("MUAPI_POLL_INTERVAL", "2"))
POLL_TIMEOUT = float(os.getenv("MUAPI_POLL_TIMEOUT", "300"))

ASPECT_RATIOS = ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
FIRST_LAST_ASPECT_RATIOS = ["adaptive", *ASPECT_RATIOS]
QUALITY_VALUES = ["standard", "fast"]


def _string_schema(description: str, *, uri: bool = False) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": description}
    if uri:
        schema["format"] = "uri"
    return schema


def _url_list_schema(description: str, maximum: int) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": {"type": "string", "format": "uri"},
        "maxItems": maximum,
    }


def _integer_schema(description: str, default: int = 5) -> dict[str, Any]:
    return {
        "type": "integer",
        "description": description,
        "default": default,
        "minimum": 4,
        "maximum": 15,
    }


def _output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "request_id": {"type": "string"},
            "status": {"type": "string"},
            "output": {"type": "object"},
        },
    }


def _generation_tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "outputSchema": _output_schema(),
    }


COMMON_QUALITY = {
    "type": "string",
    "description": "Use the standard route or the faster lower-cost route.",
    "enum": QUALITY_VALUES,
    "default": "standard",
}

TOOLS: list[dict[str, Any]] = [
    _generation_tool(
        "seedance_2_text_to_video",
        "Generate a Seedance 2 video from a text prompt. Use quality=fast for the fast route.",
        {
            "prompt": _string_schema("Detailed scene, subject, camera, lighting, and motion description."),
            "quality": COMMON_QUALITY,
            "aspect_ratio": {
                "type": "string",
                "description": "Output video aspect ratio.",
                "enum": ASPECT_RATIOS,
                "default": "16:9",
            },
            "duration": _integer_schema("Video duration in seconds."),
        },
        ["prompt"],
    ),
    _generation_tool(
        "seedance_2_image_to_video",
        "Animate one or more reference images with Seedance 2. One image anchors the start frame; multiple images enable reference-driven generation.",
        {
            "prompt": _string_schema("Motion and scene description. Reference inputs as @image1, @image2, and so on."),
            "images_list": _url_list_schema("Reference image URLs. Up to 9 images.", 9),
            "quality": COMMON_QUALITY,
            "aspect_ratio": {
                "type": "string",
                "description": "Output video aspect ratio.",
                "enum": ASPECT_RATIOS,
                "default": "16:9",
            },
            "duration": _integer_schema("Video duration in seconds."),
        },
        ["prompt", "images_list"],
    ),
    _generation_tool(
        "seedance_2_first_last_frame",
        "Generate a Seedance 2 transition from a first frame, optionally to a last frame.",
        {
            "prompt": _string_schema("Describe the transition and camera motion."),
            "images_list": _url_list_schema("One or two frame image URLs: [first_frame] or [first_frame, last_frame].", 2),
            "quality": COMMON_QUALITY,
            "aspect_ratio": {
                "type": "string",
                "description": "Use adaptive to preserve the reference geometry.",
                "enum": FIRST_LAST_ASPECT_RATIOS,
                "default": "adaptive",
            },
            "duration": _integer_schema("Video duration in seconds."),
        },
        ["prompt", "images_list"],
    ),
    _generation_tool(
        "seedance_2_omni_reference",
        "Generate a Seedance 2 video guided by image, video, and audio references.",
        {
            "prompt": _string_schema("Describe how the references should combine. Use @imageN, @videoN, and @audioN references."),
            "images_list": _url_list_schema("Reference image URLs. Up to 9 images.", 9),
            "video_files": _url_list_schema("Reference video URLs. Up to 3 clips.", 3),
            "audio_files": _url_list_schema("Reference audio URLs. Up to 3 clips.", 3),
            "quality": COMMON_QUALITY,
            "aspect_ratio": {
                "type": "string",
                "description": "Output video aspect ratio.",
                "enum": ASPECT_RATIOS,
                "default": "16:9",
            },
            "duration": _integer_schema("Video duration in seconds."),
        },
        ["prompt"],
    ),
    {
        "name": "muapi_predict_result",
        "description": "Poll a MuAPI prediction until it completes or fails.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": _string_schema("The request_id returned by a Seedance 2 generation call."),
            },
            "required": ["request_id"],
            "additionalProperties": False,
        },
        "outputSchema": _output_schema(),
    },
    {
        "name": "muapi_account_balance",
        "description": "Read the current MuAPI credit balance.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


@dataclass(frozen=True)
class Route:
    endpoint: str
    quality: bool = True


ROUTES: dict[str, Route] = {
    "seedance_2_text_to_video": Route("seedance-2-text-to-video"),
    "seedance_2_image_to_video": Route("seedance-2-image-to-video"),
    "seedance_2_first_last_frame": Route("seedance-2-first-last-frame"),
    "seedance_2_omni_reference": Route("seedance-2-omni-reference"),
}

FAST_ENDPOINTS = {
    "seedance_2_text_to_video": "seedance-2-text-to-video-fast",
    "seedance_2_image_to_video": "seedance-2-image-to-video-fast",
    "seedance_2_first_last_frame": "seedance-2-first-last-frame-fast",
    "seedance_2_omni_reference": "seedance-2-omni-reference-fast",
}

TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}


class MuApiError(RuntimeError):
    """A safe, user-facing MuAPI error without provider-specific details."""

    def __init__(self, status_code: int, code: str = "MUAPI_REQUEST_FAILED") -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(f"MuAPI request failed ({code}, HTTP {status_code})")

    def as_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "type": "muapi_error",
                "code": self.code,
                "status_code": self.status_code,
            }
        }


def api_key_from_env() -> str:
    return os.getenv("MUAPI_API_KEY") or os.getenv("MUAPIAPP_API_KEY") or ""


def _require_tool(tool_name: str) -> None:
    if tool_name not in TOOL_BY_NAME:
        raise ValueError(f"Unknown tool: {tool_name}")


def _require_url_list(arguments: dict[str, Any], key: str, *, minimum: int = 1, maximum: int) -> None:
    values = arguments.get(key)
    if not isinstance(values, list) or not (minimum <= len(values) <= maximum):
        raise ValueError(f"{key} must contain between {minimum} and {maximum} URL(s)")
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(f"{key} must contain non-empty URL strings")


def build_request(tool_name: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate MCP arguments and map them to an allowlisted MuAPI endpoint."""
    _require_tool(tool_name)
    if tool_name not in ROUTES:
        raise ValueError(f"{tool_name} is not a generation tool")

    allowed = set(TOOL_BY_NAME[tool_name]["inputSchema"]["properties"])
    unknown = set(arguments) - allowed
    if unknown:
        raise ValueError(f"Unsupported argument(s): {', '.join(sorted(unknown))}")

    payload = dict(arguments)
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt is required")

    if tool_name == "seedance_2_image_to_video":
        _require_url_list(payload, "images_list", maximum=9)
    elif tool_name == "seedance_2_first_last_frame":
        _require_url_list(payload, "images_list", maximum=2)
    else:
        for key, maximum in (("images_list", 9), ("video_files", 3), ("audio_files", 3)):
            if key in payload and payload[key] is not None:
                _require_url_list(payload, key, maximum=maximum)

    quality = payload.pop("quality", "standard")
    if quality not in QUALITY_VALUES:
        raise ValueError(f"quality must be one of: {', '.join(QUALITY_VALUES)}")
    endpoint = FAST_ENDPOINTS[tool_name] if quality == "fast" else ROUTES[tool_name].endpoint

    return endpoint, payload


class MuApiClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("MUAPI_API_KEY is not configured")
        self.api_key = api_key

    @property
    def headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = requests.request(
                method,
                f"{API_BASE}/{path.lstrip('/')}",
                headers=self.headers,
                timeout=HTTP_TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise MuApiError(503, "MUAPI_UNAVAILABLE") from exc

        try:
            body = response.json()
        except ValueError:
            body = None
        if not response.ok:
            code = "MUAPI_REQUEST_FAILED"
            if isinstance(body, dict):
                nested = body.get("error")
                if isinstance(nested, dict) and isinstance(nested.get("code"), str):
                    code = nested["code"]
                elif isinstance(body.get("code"), str):
                    code = body["code"]
            raise MuApiError(response.status_code, code)
        return body if body is not None else {}

    def submit(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", endpoint, json=payload)
        if not isinstance(result, dict):
            raise MuApiError(502, "MUAPI_INVALID_RESPONSE")
        request_id = result.get("request_id") or result.get("id")
        if not request_id:
            raise MuApiError(502, "MUAPI_MISSING_REQUEST_ID")
        return {**result, "request_id": request_id}

    def prediction(self, request_id: str) -> dict[str, Any]:
        result = self._request("GET", f"predictions/{request_id}/result")
        if not isinstance(result, dict):
            raise MuApiError(502, "MUAPI_INVALID_RESPONSE")
        return result

    def wait_for_prediction(self, request_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + POLL_TIMEOUT
        terminal = {"completed", "succeeded", "done", "failed", "error", "canceled", "cancelled"}
        while time.monotonic() < deadline:
            result = self.prediction(request_id)
            status = str(result.get("status", "")).lower()
            if status in terminal:
                return result
            time.sleep(POLL_INTERVAL)
        raise MuApiError(504, "MUAPI_POLL_TIMEOUT")

    def balance(self) -> dict[str, Any]:
        result = self._request("GET", "account/balance")
        return result if isinstance(result, dict) else {"balance": result}


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any] | None,
    api_key: str,
    *,
    wait: bool = True,
) -> dict[str, Any]:
    """Execute a catalog tool, optionally waiting for generation completion."""
    arguments = dict(arguments or {})
    client = MuApiClient(api_key)

    if tool_name == "muapi_account_balance":
        return client.balance()
    if tool_name == "muapi_predict_result":
        request_id = arguments.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("request_id is required")
        return client.wait_for_prediction(request_id) if wait else client.prediction(request_id)

    endpoint, payload = build_request(tool_name, arguments)
    submitted = client.submit(endpoint, payload)
    if not wait:
        return {"request_id": submitted["request_id"], "status": submitted.get("status", "queued")}
    return client.wait_for_prediction(submitted["request_id"])


def as_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)
