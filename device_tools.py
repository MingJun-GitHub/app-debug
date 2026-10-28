"""Device screenshot helpers shared by iOS and Android."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class DeviceToolError(RuntimeError):
    """A device command failed in a way that should be shown to the user."""


def _command_error(command: list[str], result: subprocess.CompletedProcess) -> str:
    output = " ".join(
        ((result.stdout or "") + "\n" + (result.stderr or "")).split()
    )
    if output:
        return output[-800:]
    return f"{Path(command[0]).name} 退出码 {result.returncode}"


def _run_text(command: list[str], timeout: int = 45) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeviceToolError(f"设备命令执行失败: {exc}") from exc
    if result.returncode != 0:
        raise DeviceToolError(_command_error(command, result))
    return result.stdout


def _run_bytes(command: list[str], timeout: int = 45) -> bytes:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeviceToolError(f"设备命令执行失败: {exc}") from exc
    if result.returncode != 0:
        result_text = subprocess.CompletedProcess(
            command,
            result.returncode,
            result.stdout.decode("utf-8", errors="replace"),
            result.stderr.decode("utf-8", errors="replace"),
        )
        raise DeviceToolError(_command_error(command, result_text))
    return result.stdout


def capture_screenshot(platform: str, device: dict) -> bytes:
    """Capture the current screen and return PNG bytes."""
    udid = device["udid"]
    with tempfile.TemporaryDirectory(prefix="app-debug-shot-") as temp_dir:
        destination = Path(temp_dir) / "screenshot.png"
        if platform == "android":
            image = _run_bytes(
                ["adb", "-s", udid, "exec-out", "screencap", "-p"],
                timeout=30,
            )
        elif platform == "ios":
            if device.get("simulator"):
                command = [
                    "xcrun", "simctl", "io", udid,
                    "screenshot", str(destination),
                ]
            else:
                command = [
                    "xcrun", "devicectl", "device", "capture", "screenshot",
                    "--device", udid,
                    "--destination", str(destination),
                ]
            _run_text(command, timeout=45)
            if not destination.exists():
                raise DeviceToolError("设备没有返回截图文件")
            image = destination.read_bytes()
        else:
            raise DeviceToolError(f"不支持的平台: {platform}")

    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise DeviceToolError("设备返回的截图格式不是 PNG")
    return image
