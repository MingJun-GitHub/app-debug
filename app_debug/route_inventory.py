"""Read-only route inventory extracted from the linked mobile repositories."""

from __future__ import annotations

import re
import threading
from html import escape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


_cache: dict[tuple[str, str, str, int], dict[str, Any]] = {}
_cache_lock = threading.Lock()
_IOS_ROUTE_PATTERN = re.compile(
    r"(?:routePattern|pattern|path)\s*[:=]\s*[\"']([^\"']+)[\"']"
)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _android_routes(project: Path) -> tuple[list[dict[str, Any]], list[str]]:
    routes: list[dict[str, Any]] = []
    warnings: list[str] = []
    root = project / "app" / "src" / "main" / "res" / "navigation"
    if not root.is_dir():
        return routes, ["未找到 Android navigation XML 目录"]
    for path in sorted(root.glob("*.xml")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            document = ElementTree.fromstring(text)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{path.name}: {exc}")
            continue
        for node in document.iter():
            if not node.tag.endswith("deepLink"):
                continue
            uris = [
                value
                for key, value in node.attrib.items()
                if key.endswith("uri") and value.strip()
            ]
            for uri in uris:
                offset = text.find(uri)
                if offset < 0:
                    offset = text.find(escape(uri, quote=False))
                routes.append({
                    "pattern": uri,
                    "kind": "deeplink",
                    "source": str(path),
                    "line": _line_number(text, offset) if offset >= 0 else None,
                })
    return routes, warnings


def _ios_routes(project: Path) -> tuple[list[dict[str, Any]], list[str]]:
    routes: list[dict[str, Any]] = []
    warnings: list[str] = []
    source_root = project / "BloomchicStore"
    if not source_root.is_dir():
        return routes, ["未找到 iOS BloomchicStore 源码目录"]
    candidates = [
        path
        for path in source_root.rglob("*.swift")
        if "Router" in path.name or "Route" in path.name
    ]
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{path.name}: {exc}")
            continue
        for match in _IOS_ROUTE_PATTERN.finditer(text):
            pattern = match.group(1).strip()
            if not pattern.startswith(("/", "(")):
                continue
            routes.append({
                "pattern": pattern,
                "kind": "route",
                "source": str(path),
                "line": _line_number(text, match.start()),
            })
    return routes, warnings


def route_inventory(platform: str, project_path: str) -> dict[str, Any]:
    project = Path(project_path).expanduser().resolve()
    try:
        stamp = project.stat().st_mtime_ns
    except OSError:
        stamp = 0
    cache_key = (platform, str(project), "v1", stamp)
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    if platform == "ios":
        routes, warnings = _ios_routes(project)
    elif platform == "android":
        routes, warnings = _android_routes(project)
    else:
        raise ValueError("platform not allowed")

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for route in routes:
        unique[(str(route["pattern"]), str(route["source"]))] = route
    result = {
        "platform": platform,
        "project": str(project),
        "count": len(unique),
        "routes": sorted(
            unique.values(),
            key=lambda item: (str(item["pattern"]), str(item["source"])),
        ),
        "warnings": warnings,
    }
    with _cache_lock:
        _cache.clear()
        _cache[cache_key] = result
    return result

