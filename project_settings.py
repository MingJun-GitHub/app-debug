"""Persistent local project associations for the App Debug workspace."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


PLATFORMS = ("ios", "android")
DEFAULT_PROJECTS = {
    "ios": Path.home() / "Desktop" / "app" / "ios",
    "android": Path.home() / "Desktop" / "app" / "android",
}


def default_settings() -> dict[str, Any]:
    return {
        "version": 1,
        "projects": {
            platform: {"path": str(path)}
            for platform, path in DEFAULT_PROJECTS.items()
        },
    }


def settings_path(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("APP_DEBUG_SETTINGS")
    if configured:
        return Path(configured).expanduser().resolve()
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "App Debug"
        / "settings.json"
    )


def _normalize_settings(raw: Any) -> tuple[dict[str, Any], str | None]:
    settings = default_settings()
    if not isinstance(raw, dict):
        return settings, "设置文件格式无效，已使用默认项目路径。"

    projects = raw.get("projects")
    if not isinstance(projects, dict):
        return settings, "设置文件缺少 projects，已使用默认项目路径。"

    for platform in PLATFORMS:
        item = projects.get(platform)
        if isinstance(item, dict):
            path = str(item.get("path") or "").strip()
            if path:
                settings["projects"][platform]["path"] = path
    version = raw.get("version")
    if isinstance(version, int) and version > 0:
        settings["version"] = version
    return settings, None


def load_settings(path: str | Path | None = None) -> tuple[dict[str, Any], str | None]:
    target = settings_path(path)
    if not target.exists():
        return default_settings(), None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return default_settings(), f"读取设置失败，已使用默认路径: {exc}"
    return _normalize_settings(raw)


def save_settings(settings: dict[str, Any], path: str | Path | None = None) -> Path:
    target = settings_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = _normalize_settings(settings)[0]
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target


def _git(path: Path) -> dict[str, Any]:
    empty = {
        "repoRoot": "",
        "repoName": "",
        "branch": "",
        "commit": "",
        "dirty": False,
        "changedFiles": 0,
        "detached": False,
        "remote": "",
    }
    if not path.is_dir():
        return empty
    try:
        root = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if root.returncode != 0:
            return empty
        repo_root = Path(root.stdout.strip())

        branch = subprocess.run(
            ["git", "-C", str(repo_root), "symbolic-ref", "--short", "-q", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        remote = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        changed_lines = [line for line in status.stdout.splitlines() if line.strip()]
        branch_name = branch.stdout.strip()
        return {
            "repoRoot": str(repo_root),
            "repoName": repo_root.name,
            "branch": branch_name or (commit.stdout.strip() or "detached"),
            "commit": commit.stdout.strip(),
            "dirty": bool(changed_lines),
            "changedFiles": len(changed_lines),
            "detached": not bool(branch_name),
            "remote": remote.stdout.strip() if remote.returncode == 0 else "",
        }
    except Exception:  # noqa: BLE001
        return empty


def _display_name(platform: str, path: Path, git: dict[str, Any]) -> str:
    if path.is_dir():
        if platform == "ios":
            workspaces = sorted(path.glob("*.xcworkspace"))
            projects = sorted(path.glob("*.xcodeproj"))
            if workspaces:
                return workspaces[0].stem
            if projects:
                return projects[0].stem
        else:
            settings_file = path / "settings.gradle"
            if not settings_file.exists():
                settings_file = path / "settings.gradle.kts"
            if settings_file.exists():
                try:
                    match = re.search(
                        r"rootProject\.name\s*=\s*['\"]([^'\"]+)['\"]",
                        settings_file.read_text(encoding="utf-8", errors="replace"),
                    )
                    if match:
                        return match.group(1)
                except Exception:  # noqa: BLE001
                    pass
    return git.get("repoName") or path.name or platform


def project_info(platform: str, configured_path: str) -> dict[str, Any]:
    if platform not in PLATFORMS:
        raise ValueError("platform not allowed")

    path = Path(configured_path).expanduser().resolve()
    exists = path.is_dir()
    errors: list[str] = []
    warnings: list[str] = []

    if not exists:
        errors.append("目录不存在或不是文件夹")
    elif platform == "ios":
        has_project = any(path.glob("*.xcworkspace")) or any(path.glob("*.xcodeproj"))
        if not has_project:
            errors.append("未找到 .xcworkspace 或 .xcodeproj")
    else:
        has_gradle = (path / "gradlew").exists()
        has_settings = (path / "settings.gradle").exists() or (path / "settings.gradle.kts").exists()
        if not has_gradle:
            errors.append("未找到 gradlew")
        if not has_settings:
            errors.append("未找到 settings.gradle 或 settings.gradle.kts")

    git = _git(path)
    if exists and not git["repoRoot"]:
        warnings.append("目录不是 Git 仓库，无法显示分支")

    return {
        "platform": platform,
        "path": str(path),
        "displayName": _display_name(platform, path, git),
        "defaultPath": str(DEFAULT_PROJECTS[platform]),
        "exists": exists,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "git": git,
    }


def settings_payload(
    settings: dict[str, Any],
    *,
    config_path: str | Path | None = None,
    load_error: str | None = None,
) -> dict[str, Any]:
    return {
        "version": int(settings.get("version") or 1),
        "configPath": str(settings_path(config_path)),
        "loadError": load_error,
        "projects": {
            platform: project_info(
                platform,
                str(settings["projects"][platform]["path"]),
            )
            for platform in PLATFORMS
        },
    }


def update_project_path(
    settings: dict[str, Any],
    platform: str,
    path: str,
    *,
    config_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    info = project_info(platform, path)
    if not info["valid"]:
        raise ValueError("；".join(info["errors"]))

    updated = {
        "version": int(settings.get("version") or 1),
        "projects": {
            key: {"path": str(value["path"])}
            for key, value in settings["projects"].items()
        },
    }
    updated["projects"][platform]["path"] = info["path"]
    save_settings(updated, config_path)
    return updated, info


def apply_settings(runtimes: dict[str, dict[str, Any]], settings: dict[str, Any]) -> None:
    for platform in PLATFORMS:
        project = Path(settings["projects"][platform]["path"]).expanduser().resolve()
        runtimes[platform]["project"] = project
        runtimes[platform]["log"] = project / "log" / "decoded.log"
        info = project_info(platform, str(project))
        if info["exists"]:
            runtimes[platform]["name"] = info["displayName"]
