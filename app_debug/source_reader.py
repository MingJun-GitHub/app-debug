"""Read-only, project-scoped source windows for error locations."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_SUFFIXES = {
    ".swift",
    ".m",
    ".mm",
    ".kt",
    ".kts",
    ".java",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".xml",
    ".gradle",
}
SKIP_DIRS = {
    ".git",
    ".gradle",
    ".derivedData",
    "build",
    "Pods",
    "node_modules",
}


def _language(path: Path) -> str:
    return {
        ".swift": "swift",
        ".m": "objective-c",
        ".mm": "objective-c++",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".java": "java",
        ".c": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".xml": "xml",
        ".gradle": "groovy",
    }.get(path.suffix.lower(), "text")


def _candidate_paths(root: Path, requested: str) -> list[Path]:
    raw = Path(requested).expanduser()
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(root / raw)
    if not any(path.is_file() for path in candidates):
        filename = raw.name
        if filename:
            for path in root.rglob(filename):
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                if path.is_file():
                    candidates.append(path)
                if len(candidates) >= 24:
                    break
    return candidates


def read_source_window(
    project_path: str,
    requested_path: str,
    *,
    line: int = 1,
    context: int = 14,
) -> dict[str, Any]:
    """Return a line-numbered source window without escaping the project root."""
    root = Path(project_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError("项目目录不存在")
    requested = str(requested_path or "").strip()
    if not requested:
        raise ValueError("源码路径不能为空")

    chosen: Path | None = None
    normalized_request = requested.replace("\\", "/").lstrip("/")
    for candidate in _candidate_paths(root, requested):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.is_relative_to(root) or not resolved.is_file():
            continue
        if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        resolved_posix = resolved.as_posix()
        if chosen is None:
            chosen = resolved
        if resolved_posix.endswith(normalized_request):
            chosen = resolved
            break
    if chosen is None:
        raise FileNotFoundError("源码文件不存在，或位于项目目录之外")
    if chosen.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("源码文件超过 2 MB，无法直接预览")

    context = max(1, min(int(context), 80))
    requested_line = max(1, int(line))
    try:
        all_lines = chosen.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise RuntimeError(f"读取源码失败: {exc}") from exc

    start = max(1, requested_line - context)
    end = min(len(all_lines), requested_line + context)
    rows = [
        {"n": number, "text": all_lines[number - 1]}
        for number in range(start, end + 1)
    ]
    return {
        "path": str(chosen),
        "relativePath": chosen.relative_to(root).as_posix(),
        "requestedPath": requested,
        "language": _language(chosen),
        "line": requested_line,
        "startLine": start,
        "endLine": end,
        "totalLines": len(all_lines),
        "lines": rows,
    }

