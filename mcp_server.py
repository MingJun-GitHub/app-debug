#!/usr/bin/env python3
"""Minimal local MCP bridge for App Debug.

The server speaks newline-delimited JSON-RPC over stdio and delegates to the
local App Debug HTTP API. Diagnostic reads are redacted before being returned.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app_debug.redaction import redact_data


BASE_URL = os.environ.get("APP_DEBUG_URL", "http://127.0.0.1:8787").rstrip("/")
PROTOCOL_VERSION = "2024-11-05"
PLATFORM_SCHEMA = {
    "type": "string",
    "enum": ["ios", "android"],
    "description": "Target mobile platform.",
}


def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = 60,
) -> tuple[int, bytes, str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return (
                response.status,
                response.read(),
                response.headers.get_content_type(),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get_content_type()


def _json_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    status, body, _content_type = _request(method, path, payload, timeout=timeout)
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"App Debug returned invalid JSON: {exc}") from exc
    if status >= 400:
        raise RuntimeError(data.get("error") or f"HTTP {status}")
    return redact_data(data)


def _text_result(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": False,
    }


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool(
        "app_debug_status",
        "Read devices, installed artifact, SDK and selected device for one platform.",
        {"platform": PLATFORM_SCHEMA},
        ["platform"],
    ),
    _tool(
        "list_sessions",
        "List persistent App Debug sessions for one platform.",
        {
            "platform": PLATFORM_SCHEMA,
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        ["platform"],
    ),
    _tool(
        "get_session",
        "Read a redacted diagnostic JSON export for a session.",
        {
            "platform": PLATFORM_SCHEMA,
            "session_id": {"type": "string"},
        },
        ["platform", "session_id"],
    ),
    _tool(
        "device_context",
        "Read the installed app environment, identity and AB snapshot. Values are redacted.",
        {
            "platform": PLATFORM_SCHEMA,
            "configuration": {
                "type": "string",
                "enum": ["Debug", "Release"],
                "default": "Debug",
            },
            "refresh": {"type": "boolean", "default": False},
        },
        ["platform"],
    ),
    _tool(
        "route_inventory",
        "Read routes and deep links from the linked repository without modifying it.",
        {"platform": PLATFORM_SCHEMA},
        ["platform"],
    ),
    _tool(
        "start_action",
        "Start an existing App Debug action. Build/install/launch/log actions require confirm=true.",
        {
            "platform": PLATFORM_SCHEMA,
            "action": {
                "type": "string",
                "enum": [
                    "all",
                    "build",
                    "install",
                    "launch",
                    "log",
                    "logs",
                    "doctor",
                    "test",
                    "lint",
                ],
            },
            "configuration": {
                "type": "string",
                "enum": ["Debug", "Release"],
                "default": "Debug",
            },
            "confirm": {
                "type": "boolean",
                "description": "Required for actions that build, install or launch the app.",
            },
        },
        ["platform", "action"],
    ),
    _tool(
        "job_status",
        "Read incremental output from a running or completed App Debug job.",
        {
            "platform": PLATFORM_SCHEMA,
            "job_id": {"type": "string"},
            "offset": {"type": "integer", "minimum": 0},
        },
        ["platform", "job_id"],
    ),
    _tool(
        "open_link",
        "Open an existing deep link or universal link on the selected device.",
        {
            "platform": PLATFORM_SCHEMA,
            "url": {"type": "string"},
        },
        ["platform", "url"],
    ),
    _tool(
        "capture_screenshot",
        "Capture the selected device screen to the local App Debug support directory.",
        {"platform": PLATFORM_SCHEMA},
        ["platform"],
    ),
]


def _status(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    return _json_request("GET", f"/api/{platform}/status", timeout=30)


def _sessions(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    limit = max(1, min(int(arguments.get("limit", 20)), 100))
    return _json_request("GET", f"/api/{platform}/sessions?limit={limit}")


def _session(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    session_id = urllib.parse.quote(str(arguments["session_id"]), safe="")
    result = _json_request(
        "GET",
        f"/api/{platform}/sessions/{session_id}/export?format=json",
    )
    return result.get("content", "{}")


def _context(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    configuration = arguments.get("configuration", "Debug")
    refresh = "1" if arguments.get("refresh") else "0"
    return _json_request(
        "GET",
        f"/api/{platform}/device/context"
        f"?configuration={urllib.parse.quote(configuration)}&refresh={refresh}",
        timeout=90,
    )


def _routes(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    return _json_request("GET", f"/api/{platform}/routes", timeout=60)


def _start_action(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    action = arguments["action"]
    guarded = {"all", "build", "install", "launch", "log", "logs"}
    if action in guarded and arguments.get("confirm") is not True:
        raise RuntimeError(f"{action} requires confirm=true")
    return _json_request(
        "POST",
        f"/api/{platform}/run",
        {
            "action": action,
            "configuration": arguments.get("configuration", "Debug"),
        },
        timeout=45,
    )


def _job(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    job_id = urllib.parse.quote(str(arguments["job_id"]), safe="")
    offset = max(0, int(arguments.get("offset", 0)))
    return _json_request("GET", f"/api/{platform}/job/{job_id}?offset={offset}")


def _open_link(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    return _json_request(
        "POST",
        f"/api/{platform}/link/open",
        {"url": str(arguments["url"])},
        timeout=60,
    )


def _screenshot(arguments: dict[str, Any]) -> Any:
    platform = arguments["platform"]
    status, image, content_type = _request(
        "GET",
        f"/api/{platform}/device/screenshot",
        timeout=60,
    )
    if status >= 400:
        try:
            error = json.loads(image.decode("utf-8")).get("error")
        except Exception:  # noqa: BLE001
            error = f"HTTP {status}"
        raise RuntimeError(error)
    if content_type != "image/png":
        raise RuntimeError("App Debug did not return PNG data")
    directory = (
        Path.home()
        / "Library"
        / "Application Support"
        / "App Debug"
        / "screenshots"
    )
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{platform}-{int(time.time())}.png"
    destination.write_bytes(image)
    return {"path": str(destination), "bytes": len(image)}


HANDLERS = {
    "app_debug_status": _status,
    "list_sessions": _sessions,
    "get_session": _session,
    "device_context": _context,
    "route_inventory": _routes,
    "start_action": _start_action,
    "job_status": _job,
    "open_link": _open_link,
    "capture_screenshot": _screenshot,
}


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "app-debug", "version": "0.4.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"unknown tool: {name}"},
            }
        try:
            result = _text_result(handler(arguments))
        except Exception as exc:  # noqa: BLE001
            result = {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"unknown method: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = _handle(request)
        except Exception as exc:  # noqa: BLE001
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

