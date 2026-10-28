"""Read-only route inventory extracted from the linked mobile repositories."""

from __future__ import annotations

import re
import threading
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from xml.etree import ElementTree

from app_debug.links import normalize_link_url


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


def _route_parts(pattern: str) -> tuple[str, str, str, str]:
    value = pattern.strip()
    if "://" in value:
        parsed = urlsplit(value)
        return (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower(),
            parsed.path or "/",
            parsed.query,
        )
    if value.startswith(("http:", "https:")):
        parsed = urlsplit(value)
        return (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower(),
            parsed.path or "/",
            parsed.query,
        )
    if re.match(r"^(?:www\.)?(?:bloomchic\.|bloom-chic-|lavisheus\.)", value):
        parsed = urlsplit(f"https://{value}")
        return (
            "https",
            (parsed.hostname or "").lower(),
            parsed.path or "/",
            parsed.query,
        )
    parsed = urlsplit(value)
    return "", "", parsed.path or "/", parsed.query


_PATH_TOKEN = re.compile(r"\(/:lang\)|:[A-Za-z_][A-Za-z0-9_]*|\{[^}]+\}|\.\*")


def _path_expression(path: str) -> tuple[re.Pattern[str], bool]:
    parts: list[str] = []
    cursor = 0
    dynamic = False
    for match in _PATH_TOKEN.finditer(path):
        parts.append(re.escape(path[cursor:match.start()]))
        token = match.group(0)
        if token == "(/:lang)":
            parts.append(r"(?:/[^/]+)?")
        elif token == ".*":
            parts.append(".*")
        else:
            parts.append(r"[^/?#]+")
        dynamic = True
        cursor = match.end()
    parts.append(re.escape(path[cursor:]))
    expression = "".join(parts)
    if expression != "/":
        expression = expression.rstrip("/")
    return re.compile(f"^{expression}$", re.IGNORECASE), dynamic


def _normalize_host(value: str) -> str:
    return value.lower().removeprefix("www.")


def match_route(
    platform: str,
    value: str,
    project_path: str,
) -> dict[str, Any]:
    normalized = normalize_link_url(value)
    parsed = urlsplit(normalized)
    target_scheme = parsed.scheme.lower()
    target_host = _normalize_host(parsed.hostname or "")
    target_path = parsed.path or "/"
    target_query_keys = {key for key, _item in parse_qsl(parsed.query, keep_blank_values=True)}
    inventory = route_inventory(platform, project_path)
    matches: list[dict[str, Any]] = []

    for route in inventory["routes"]:
        pattern = str(route["pattern"])
        pattern_scheme, pattern_host, pattern_path, pattern_query = _route_parts(pattern)
        if pattern_host and _normalize_host(pattern_host) != target_host:
            continue
        expression, dynamic = _path_expression(pattern_path.rstrip("/") or "/")
        if not expression.fullmatch(target_path.rstrip("/") or "/"):
            continue
        required_query_keys = {
            key for key, _item in parse_qsl(pattern_query, keep_blank_values=True)
        }
        missing_query_keys = sorted(required_query_keys - target_query_keys)
        score = 60 if dynamic else 90
        if pattern_host:
            score += 20
        if pattern_scheme and pattern_scheme == target_scheme:
            score += 10
        if required_query_keys and not missing_query_keys:
            score += 10
        matches.append({
            **route,
            "score": score,
            "dynamic": dynamic,
            "missingQueryKeys": missing_query_keys,
        })

    matches.sort(
        key=lambda item: (
            -int(item["score"]),
            len(str(item["pattern"])),
            str(item["pattern"]),
            str(item["source"]),
        )
    )
    best = matches[0] if matches else None
    warnings = list(inventory.get("warnings") or [])
    if best and best["missingQueryKeys"]:
        warnings.append(
            "命中路由的参数不完整: " + ", ".join(best["missingQueryKeys"])
        )
    if not matches:
        warnings.append("当前 Deep Link / Universal Link 未匹配到仓库现有路由")
    return {
        "platform": platform,
        "input": str(value or "").strip(),
        "normalized": normalized,
        "matched": bool(matches),
        "matchedCount": len(matches),
        "best": best,
        "matches": matches[:20],
        "warnings": warnings,
    }

