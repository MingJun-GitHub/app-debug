"""Persistent, local-only debug sessions and AI diagnostic exports."""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app_debug.analysis import analyze_lines
from app_debug.redaction import redact_data, redact_text


SCHEMA_VERSION = 1
_store_lock = threading.RLock()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def default_session_root() -> Path:
    configured = os.environ.get("APP_DEBUG_SESSIONS")
    if configured:
        return Path(configured).expanduser().resolve()
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "App Debug"
        / "sessions"
    )


def _safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{6,64}", value or ""):
        raise ValueError("session id not allowed")
    return value


class SessionStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser().resolve() if root else default_session_root()

    def _platform_dir(self, platform: str) -> Path:
        if platform not in ("ios", "android"):
            raise ValueError("platform not allowed")
        return self.root / platform

    def _dir(self, platform: str, session_id: str) -> Path:
        return self._platform_dir(platform) / _safe_id(session_id)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def create(
        self,
        *,
        platform: str,
        session_id: str,
        action: str,
        configuration: str,
        project: dict[str, Any] | None,
        device: dict[str, Any] | None,
        artifact: dict[str, Any] | None,
    ) -> dict[str, Any]:
        directory = self._dir(platform, session_id)
        timestamp = _now()
        session = {
            "schemaVersion": SCHEMA_VERSION,
            "id": session_id,
            "platform": platform,
            "action": action,
            "kind": "validation" if action in ("test", "lint") else "run",
            "configuration": configuration,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "status": "running",
            "project": project or {},
            "device": device or {},
            "artifact": artifact or {},
            "result": {},
            "analysis": {},
            "snapshots": [],
            "logFile": "job.log",
        }
        with _store_lock:
            directory.mkdir(parents=True, exist_ok=True)
            self._write_json(directory / "session.json", session)
            (directory / "job.log").write_text("", encoding="utf-8")
        return session

    def append_log(self, platform: str, session_id: str, text: str) -> None:
        directory = self._dir(platform, session_id)
        with _store_lock:
            with (directory / "job.log").open("a", encoding="utf-8") as handle:
                handle.write(text)
                if text and not text.endswith("\n"):
                    handle.write("\n")

    def complete(
        self,
        *,
        platform: str,
        session_id: str,
        status: str,
        exit_code: int | None,
        elapsed: float,
        lines: list[str],
        artifact: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        directory = self._dir(platform, session_id)
        metadata_path = directory / "session.json"
        with _store_lock:
            session = self._read_json(metadata_path)
            session.update({
                "updatedAt": _now(),
                "status": status,
                "result": {
                    "exitCode": exit_code,
                    "elapsed": elapsed,
                    "lineCount": len(lines),
                },
                "analysis": analyze_lines(lines),
            })
            if artifact:
                session["artifact"] = artifact
            self._write_json(metadata_path, session)
            log_path = directory / "job.log"
            if not log_path.exists() or log_path.stat().st_size == 0:
                log_path.write_text(
                    "\n".join(lines) + ("\n" if lines else ""),
                    encoding="utf-8",
                )
        return session

    def attach_snapshot(
        self,
        platform: str,
        session_id: str,
        context: dict[str, Any],
        *,
        label: str = "device-context",
    ) -> dict[str, Any]:
        directory = self._dir(platform, session_id)
        metadata_path = directory / "session.json"
        timestamp = _now()
        with _store_lock:
            session = self._read_json(metadata_path)
            snapshots = list(session.get("snapshots") or [])
            snapshot = {
                "capturedAt": timestamp,
                "label": label,
                "context": context,
            }
            snapshots.append(snapshot)
            session["snapshots"] = snapshots[-20:]
            session["updatedAt"] = timestamp
            self._write_json(metadata_path, session)
            self._write_json(
                directory / f"snapshot-{len(snapshots):02d}.json",
                snapshot,
            )
        return session

    def list(self, platform: str, limit: int = 30) -> list[dict[str, Any]]:
        root = self._platform_dir(platform)
        if not root.is_dir():
            return []
        sessions: list[dict[str, Any]] = []
        with _store_lock:
            for path in root.glob("*/session.json"):
                try:
                    sessions.append(self._read_json(path))
                except Exception:  # noqa: BLE001
                    continue
        sessions.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
        summaries = []
        for session in sessions[: max(1, min(limit, 200))]:
            analysis = session.get("analysis") or {}
            summaries.append({
                "id": session.get("id"),
                "platform": session.get("platform"),
                "action": session.get("action"),
                "kind": session.get("kind"),
                "configuration": session.get("configuration"),
                "createdAt": session.get("createdAt"),
                "updatedAt": session.get("updatedAt"),
                "status": session.get("status"),
                "project": {
                    "displayName": (session.get("project") or {}).get("displayName"),
                    "branch": (session.get("project") or {}).get("branch"),
                    "commit": (session.get("project") or {}).get("commit"),
                },
                "result": session.get("result") or {},
                "analysis": {
                    "errorCount": analysis.get("errorCount", 0),
                    "warningCount": analysis.get("warningCount", 0),
                    "lineCount": analysis.get("lineCount", 0),
                },
                "snapshotCount": len(session.get("snapshots") or []),
            })
        return summaries

    def get(self, platform: str, session_id: str) -> dict[str, Any] | None:
        path = self._dir(platform, session_id) / "session.json"
        if not path.is_file():
            return None
        with _store_lock:
            return self._read_json(path)

    def log_text(self, platform: str, session_id: str, max_chars: int = 250_000) -> str:
        path = self._dir(platform, session_id) / "job.log"
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]

    def export(self, platform: str, session_id: str, format_name: str = "markdown") -> dict[str, Any]:
        session = self.get(platform, session_id)
        if not session:
            raise KeyError("session not found")
        log = self.log_text(platform, session_id)
        payload = {
            **session,
            "log": log,
        }
        payload = redact_data(payload)
        if format_name in ("json", "application/json"):
            content = json.dumps(payload, ensure_ascii=False, indent=2)
            extension = "json"
            content_type = "application/json; charset=utf-8"
        else:
            content = self._markdown(payload)
            extension = "md"
            content_type = "text/markdown; charset=utf-8"
        return {
            "content": content,
            "contentType": content_type,
            "filename": f"app-debug-{platform}-{session_id}.{extension}",
        }

    def delete(self, platform: str, session_id: str) -> bool:
        directory = self._dir(platform, session_id)
        if not directory.is_dir():
            return False
        with _store_lock:
            shutil.rmtree(directory)
        return True

    def clear(self, platform: str) -> int:
        root = self._platform_dir(platform)
        if not root.is_dir():
            return 0
        removed = 0
        with _store_lock:
            for directory in root.iterdir():
                if not directory.is_dir() or not _safe_id(directory.name):
                    continue
                shutil.rmtree(directory)
                removed += 1
        return removed

    def _markdown(self, session: dict[str, Any]) -> str:
        project = session.get("project") or {}
        device = session.get("device") or {}
        analysis = session.get("analysis") or {}
        artifact = session.get("artifact") or {}
        snapshots = session.get("snapshots") or []
        latest_context = snapshots[-1].get("context", {}) if snapshots else {}
        app = latest_context.get("app") or {}
        environment = app.get("environment") or {}
        lines = [
            "# App Debug Diagnostic",
            "",
            f"- Session: `{session.get('id', '-')}`",
            f"- Platform: `{session.get('platform', '-')}`",
            f"- Action: `{session.get('action', '-')}`",
            f"- Configuration: `{session.get('configuration', '-')}`",
            f"- Status: `{session.get('status', '-')}`",
            f"- Created: `{session.get('createdAt', '-')}`",
            "",
            "## Project",
            "",
            f"- Name: `{project.get('displayName') or project.get('repoName') or '-'}`",
            f"- Branch: `{project.get('branch') or '-'}`",
            f"- Commit: `{project.get('commit') or '-'}`",
            f"- Dirty: `{project.get('dirty', '-')}`",
            f"- Artifact: `{artifact.get('name') or '-'}`",
            "",
            "## Device",
            "",
            f"- Device: `{device.get('name') or '-'}`",
            f"- Model: `{device.get('model') or '-'}`",
            f"- OS: `{device.get('os') or '-'}`",
            f"- Environment: `{environment.get('name') or '-'}`",
            f"- Site: `{environment.get('site') or '-'}`",
            f"- Country: `{environment.get('country') or '-'}`",
            "",
            "## Analysis",
            "",
            f"- Errors: `{analysis.get('errorCount', 0)}`",
            f"- Warnings: `{analysis.get('warningCount', 0)}`",
            f"- Log lines: `{analysis.get('lineCount', 0)}`",
            f"- Snapshots: `{len(snapshots)}`",
            "",
            "### Source locations",
            "",
        ]
        locations = analysis.get("sourceLocations") or []
        lines.extend(f"- `{item}`" for item in locations[:80])
        if not locations:
            lines.append("- none")

        lines.extend(["", "### Error groups", ""])
        groups = analysis.get("errorGroups") or []
        for group in groups[:50]:
            lines.append(
                f"- x{group.get('count', 1)} `{redact_text(group.get('sample', ''))}`"
            )
        if not groups:
            lines.append("- none")

        lines.extend(["", "## Reproduce", "", "1. Open the linked project on the same commit.", "2. Connect the same platform device and choose the recorded build configuration.", "3. Run the same App Debug action and compare the session analysis and snapshots.", "", "## Log", "", "```text"])
        lines.append(str(session.get("log") or "").strip())
        lines.extend(["```", ""])
        return "\n".join(lines)

