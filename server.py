#!/usr/bin/env python3
"""
App Debug 本地服务

统一托管 Nuxt 前端，并为 iOS / Android 提供彼此隔离的构建、设备和日志 API。
仅监听本机回环地址，不对外网开放。
"""

import json
import mimetypes
import os
import re
import signal
import subprocess
import threading
import time
import uuid
import webbrowser
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from device_context import now_iso, read_app_context
from project_settings import (
    apply_settings,
    load_settings,
    project_info,
    settings_payload,
    update_project_path,
)

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / ".output" / "public"
INDEX = DIST_DIR / "index.html"

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8787"))

ALLOWED_ACTIONS = {"all", "build", "install", "launch", "log", "logs", "doctor"}
PLATFORMS = {
    "ios": {
        "runner": BASE_DIR / "run163.sh",
        "project": Path("/Users/mingjun/Desktop/app/ios"),
        "log": Path("/Users/mingjun/Desktop/app/ios/log/decoded.log"),
        "name": "BloomchicStore",
    },
    "android": {
        "runner": BASE_DIR / "runandroid.sh",
        "project": Path("/Users/mingjun/Desktop/app/android"),
        "log": Path("/Users/mingjun/Desktop/app/android/log/decoded.log"),
        "name": "Bloomchic Android",
    },
}

_settings_lock = threading.Lock()
_settings, _settings_error = load_settings()
apply_settings(PLATFORMS, _settings)

_jobs = {}
_jobs_lock = threading.Lock()
_device_context_lock = threading.Lock()
_device_context_cache = {}

# iOS 与 Android 分别保存设备选择，避免切换平台时互相覆盖。
_device_lock = threading.Lock()
_selected_devices = {
    "ios": {"udid": "", "name": ""},
    "android": {"udid": "", "name": ""},
}


class Job:
    def __init__(self, platform, action, configuration=""):
        self.id = uuid.uuid4().hex[:12]
        self.platform = platform
        self.action = action
        self.configuration = configuration
        self.lines = []
        self.line_base = 0
        self.line_lock = threading.Lock()
        self.done = False
        self.exit_code = None
        self.started = time.time()
        self.finished = None
        self.proc = None
        self.cancel_requested = threading.Event()
        self.completed = threading.Event()

    def append(self, text):
        with self.line_lock:
            for line in text.splitlines():
                self.lines.append(line.rstrip("\r"))
            if len(self.lines) > 5000:
                removed = len(self.lines) - 3000
                self.lines = self.lines[-3000:]
                self.line_base += removed

    def snapshot(self, offset=0):
        with self.line_lock:
            truncated = offset < self.line_base
            local_offset = max(0, offset - self.line_base)
            lines = self.lines[local_offset:]
            total = self.line_base + len(self.lines)
        return {
            "id": self.id,
            "platform": self.platform,
            "action": self.action,
            "done": self.done,
            "cancelled": self.cancel_requested.is_set(),
            "exitCode": self.exit_code,
            "running": self.proc is not None and self.proc.poll() is None,
            "elapsed": round((self.finished or time.time()) - self.started, 1),
            "total": total,
            "offset": offset,
            "truncated": truncated,
            "lines": lines,
        }


def _run_job(job):
    runtime = PLATFORMS[job.platform]
    cmd = ["/bin/zsh", str(runtime["runner"]), job.action]
    env = dict(os.environ)
    env["TERM"] = "dumb"
    if job.configuration:
        env["CONFIGURATION"] = job.configuration
    with _device_lock:
        selected = dict(_selected_devices[job.platform])
    if selected["udid"]:
        if job.platform == "ios":
            env["DEVICE_UDID"] = selected["udid"]
            env["DEVICE_NAME"] = selected["name"]
        else:
            env["DEVICE_SERIAL"] = selected["udid"]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            start_new_session=True,
        )
        job.proc = proc
        if job.cancel_requested.is_set():
            _signal_job(job, signal.SIGTERM)
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            job.append(line.rstrip("\n"))
        proc.wait()
        job.exit_code = proc.returncode
    except Exception as exc:  # noqa: BLE001
        job.append(f"[runner] 启动失败: {exc}")
        job.exit_code = -1
    finally:
        if job.proc is not None and job.proc.poll() is None:
            _signal_job(job, signal.SIGTERM)
            try:
                job.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _signal_job(job, signal.SIGKILL)
        job.done = True
        job.finished = time.time()
        job.completed.set()


def _signal_job(job, sig):
    """只向该任务独立的进程组发送信号，包含 shell 和子命令。"""
    if job.proc is None:
        return
    try:
        os.killpg(job.proc.pid, sig)
    except ProcessLookupError:
        pass


def stop_job(job):
    if job.done:
        return False
    job.cancel_requested.set()
    _signal_job(job, signal.SIGTERM)

    def finish_stop():
        job.completed.wait(timeout=3)
        if job.proc is not None and job.proc.poll() is None:
            _signal_job(job, signal.SIGKILL)

    threading.Thread(target=finish_stop, daemon=True).start()
    return True


def start_job(platform, action, configuration=""):
    with _jobs_lock:
        active = [
            job for job in _jobs.values()
            if job.platform == platform and not job.done
        ]
        if active:
            return None, active[0]
        job = Job(platform, action, configuration)
        _jobs[job.id] = job
        if len(_jobs) > 20:
            remove_count = len(_jobs) - 20
            finished = sorted(
                (key for key, item in _jobs.items() if item.done),
                key=lambda key: _jobs[key].started,
            )
            for key in finished[:remove_count]:
                _jobs.pop(key, None)
    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return job, None


def stop_all_jobs():
    with _jobs_lock:
        active = [job for job in _jobs.values() if not job.done]
    for job in active:
        stop_job(job)
    for job in active:
        job.completed.wait(timeout=4)


def current_settings_payload(reload=False):
    global _settings, _settings_error
    with _settings_lock:
        if reload:
            _settings, _settings_error = load_settings()
            apply_settings(PLATFORMS, _settings)
        snapshot = settings_payload(_settings, load_error=_settings_error)
    return snapshot


def save_project_setting(platform, path):
    global _settings, _settings_error
    with _jobs_lock:
        active = [
            job for job in _jobs.values()
            if job.platform == platform and not job.done
        ]
    if active:
        raise RuntimeError(f"该平台已有任务在运行: {active[0].action}")

    with _settings_lock:
        _settings, info = update_project_path(_settings, platform, path)
        _settings_error = None
        apply_settings(PLATFORMS, _settings)
        with _device_context_lock:
            for cache_key in list(_device_context_cache):
                if cache_key[0] == platform:
                    _device_context_cache.pop(cache_key, None)
        snapshot = settings_payload(_settings, load_error=None)
    return snapshot, info


def pick_project_directory(platform):
    if os.uname().sysname != "Darwin":
        raise RuntimeError("当前系统不支持原生目录选择，请手动输入路径。")
    path = PLATFORMS[platform]["project"]
    default_path = path if path.exists() else Path.home()
    prompt = f"选择 {platform.upper()} 项目目录"
    script = [
        "on run argv",
        "try",
        "set chosenFolder to choose folder with prompt (item 1 of argv) "
        "default location (POSIX file (item 2 of argv))",
        "return POSIX path of chosenFolder",
        "on error number -128",
        'return ""',
        "end try",
        "end run",
    ]
    command = ["osascript"]
    for line in script:
        command.extend(["-e", line])
    command.extend([prompt, str(default_path)])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "目录选择失败")
    selected = result.stdout.strip()
    return {
        "cancelled": not bool(selected),
        "path": selected,
        "project": project_info(platform, selected) if selected else None,
    }


def latest_ios_sdk():
    """读取最新 iOS 产物里的 SDK 名。"""
    app = (
        PLATFORMS["ios"]["project"]
        / ".derivedData/Build/Products/Debug-iphoneos/BloomchicStore.app/Info.plist"
    )
    if not app.exists():
        return None
    try:
        out = subprocess.run(
            ["/usr/libexec/PlistBuddy", "-c", "Print :DTSDKName", str(app)],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def list_ios_devices():
    try:
        out = subprocess.run(
            ["xcrun", "xcdevice", "list"],
            capture_output=True, text=True, timeout=20,
        )
        items = json.loads(out.stdout)
        devices = []
        for item in items:
            if item.get("platform") != "com.apple.platform.iphoneos":
                continue
            devices.append({
                "name": item.get("name", ""),
                "udid": item.get("identifier", ""),
                "model": item.get("modelName", ""),
                "state": "connected" if item.get("available") else "unavailable",
                "interface": item.get("interface", ""),
                "os": item.get("operatingSystemVersion", ""),
                "simulator": bool(item.get("simulator")),
                "available": bool(item.get("available")),
            })
        devices.sort(key=lambda item: (item["simulator"], not item["available"], item["name"]))
        return devices
    except Exception:  # noqa: BLE001
        return []


def list_android_devices():
    """枚举已连接且已授权的 adb 设备。"""
    try:
        out = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True, timeout=15,
        )
        devices = []
        for line in out.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            attrs = {}
            for part in parts[2:]:
                if ":" in part:
                    key, value = part.split(":", 1)
                    attrs[key] = value.replace("_", " ")
            model = attrs.get("model") or attrs.get("product") or serial
            version = ""
            if state == "device":
                try:
                    version = subprocess.run(
                        ["adb", "-s", serial, "shell", "getprop", "ro.build.version.release"],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.strip()
                except Exception:  # noqa: BLE001
                    pass
            devices.append({
                "name": model,
                "udid": serial,
                "model": model,
                "state": "connected" if state == "device" else state,
                "interface": "emulator" if serial.startswith("emulator-") else "adb",
                "os": version,
                "simulator": serial.startswith("emulator-"),
                "available": state == "device",
            })
        devices.sort(key=lambda item: (item["simulator"], not item["available"], item["name"]))
        return devices
    except Exception:  # noqa: BLE001
        return []


def list_devices(platform):
    return list_ios_devices() if platform == "ios" else list_android_devices()


def select_device(devices, platform):
    with _device_lock:
        selected = dict(_selected_devices[platform])
    if selected["udid"]:
        match = next((item for item in devices if item["udid"] == selected["udid"]), None)
        if match:
            return match
    return next((item for item in devices if item["available"]), None) or (devices[0] if devices else None)


def latest_android_artifact(configuration="Debug"):
    variant = "release" if configuration == "Release" else "debug"
    output_dir = PLATFORMS["android"]["project"] / "app/build/outputs/apk" / variant
    if not output_dir.exists():
        return None
    files = sorted(output_dir.glob("*.apk"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not files:
        return None
    version = ""
    metadata = output_dir / "output-metadata.json"
    if metadata.exists():
        try:
            data = json.loads(metadata.read_text(encoding="utf-8"))
            elements = data.get("elements") or []
            if elements:
                version = str(elements[0].get("versionName") or "")
        except Exception:  # noqa: BLE001
            pass
    return {
        "name": files[0].name,
        "path": str(files[0]),
        "version": version,
    }


def platform_status(platform):
    devices = list_devices(platform)
    device = select_device(devices, platform)
    with _device_lock:
        selected = dict(_selected_devices[platform])
    if platform == "ios":
        sdk = latest_ios_sdk()
        artifact = None
        app = (
            PLATFORMS["ios"]["project"]
            / ".derivedData/Build/Products/Debug-iphoneos/BloomchicStore.app"
        )
        if app.exists():
            artifact = {"name": app.name, "path": str(app)}
    else:
        sdk = None
        artifact = latest_android_artifact()
        if artifact:
            sdk = f"Android {artifact['version']}".strip()
    return {
        "platform": platform,
        "project": str(PLATFORMS[platform]["project"]),
        "projectName": PLATFORMS[platform]["name"],
        "device": device,
        "sdk": sdk,
        "artifact": artifact,
        "selected": selected,
    }


def device_context(platform, configuration="Debug", refresh=False):
    status = platform_status(platform)
    device = status.get("device")
    udid = device.get("udid", "") if device else ""
    cache_key = (platform, udid, configuration)
    now = time.time()

    if not refresh:
        with _device_context_lock:
            cached = _device_context_cache.get(cache_key)
        if cached and now - cached["cachedAt"] < 12:
            payload = dict(cached["payload"])
            payload["cached"] = True
            return payload

    available = bool(device and device.get("available"))
    app = read_app_context(platform, udid if available else "")
    if device and not available:
        app["warnings"] = ["设备当前不可用，请解锁设备并完成授权后重新检测。"]
    payload = {
        "schemaVersion": 1,
        "platform": platform,
        "collectedAt": now_iso(),
        "source": "app_sandbox_cache",
        "cached": False,
        "device": {
            **(device or {}),
            "connected": available,
            "buildConfiguration": configuration,
        },
        "project": status.get("project"),
        "projectName": status.get("projectName"),
        "app": app,
    }
    with _device_context_lock:
        _device_context_cache[cache_key] = {
            "cachedAt": now,
            "payload": payload,
        }
        if len(_device_context_cache) > 20:
            oldest = sorted(
                _device_context_cache,
                key=lambda item: _device_context_cache[item]["cachedAt"],
            )[:len(_device_context_cache) - 20]
            for item in oldest:
                _device_context_cache.pop(item, None)
    return payload


def search_log(platform, keyword, limit=200, use_regex=False):
    """在已解码日志中检索，返回匹配行。"""
    log_file = PLATFORMS[platform]["log"]
    if not log_file.exists():
        return {
            "ok": False,
            "error": f"{platform} log/decoded.log 不存在，请先点「拉取日志」",
            "lines": [],
            "total": 0,
        }
    try:
        if use_regex:
            pattern = re.compile(keyword)
        else:
            pattern = None
        hits = []
        with log_file.open("r", encoding="utf-8", errors="replace") as fh:
            for idx, line in enumerate(fh, 1):
                line = line.rstrip("\n")
                matched = bool(pattern.search(line)) if pattern else (keyword in line)
                if matched:
                    hits.append({"n": idx, "text": line})
                    if len(hits) > 5000:
                        hits = hits[-3000:]
        total = len(hits)
        return {
            "ok": True,
            "lines": hits[-limit:],
            "total": total,
            "file": str(log_file),
            "size": log_file.stat().st_size,
        }
    except re.error as exc:
        return {"ok": False, "error": f"正则错误: {exc}", "lines": [], "total": 0}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "lines": [], "total": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    def _send(
        self,
        code,
        body,
        content_type="application/json; charset=utf-8",
        cache="no-store",
    ):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path):
        if not INDEX.exists():
            return self._send(
                503,
                "Nuxt 页面尚未构建，请先运行 npm install && npm run build",
                "text/plain; charset=utf-8",
            )

        relative = unquote(path).lstrip("/")
        target = (DIST_DIR / relative).resolve()
        dist_root = DIST_DIR.resolve()
        if target != dist_root and not target.is_relative_to(dist_root):
            return self._send(404, "not found", "text/plain; charset=utf-8")

        if not target.is_file() or path in ("/", "/index.html"):
            target = INDEX

        if not target.is_file():
            return self._send(404, "not found", "text/plain; charset=utf-8")

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in (
            "application/javascript",
            "application/json",
            "image/svg+xml",
        ):
            content_type += "; charset=utf-8"
        cache = "public, max-age=31536000, immutable" if path.startswith("/_nuxt/") else "no-store"
        return self._send(200, target.read_bytes(), content_type, cache)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]

        if not path.startswith("/api/"):
            return self._serve_static(path)

        parts = [part for part in path.split("/") if part]
        if parts == ["api", "settings"]:
            return self._send(200, json.dumps(
                current_settings_payload(reload=True),
                ensure_ascii=False,
            ))

        if len(parts) >= 3 and parts[1] in PLATFORMS:
            platform = parts[1]
            route = parts[2:]
        else:
            platform = "ios"
            route = parts[1:]

        if route == ["status"]:
            return self._send(
                200,
                json.dumps(platform_status(platform), ensure_ascii=False),
            )

        if route == ["devices"]:
            return self._send(200, json.dumps({
                "devices": list_devices(platform),
            }, ensure_ascii=False))

        if route == ["device", "context"]:
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            configuration = (params.get("configuration") or ["Debug"])[0]
            if configuration not in ("Debug", "Release"):
                return self._send(400, json.dumps({"error": "configuration not allowed"}))
            refresh = (params.get("refresh") or ["0"])[0] == "1"
            return self._send(200, json.dumps(
                device_context(platform, configuration, refresh),
                ensure_ascii=False,
            ))

        if route == ["log", "search"]:
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            keyword = (params.get("q") or [""])[0]
            if not keyword:
                return self._send(400, json.dumps({"error": "缺少 q 参数"}))
            try:
                limit = max(1, min(int((params.get("limit") or ["200"])[0]), 1000))
            except ValueError:
                limit = 200
            use_regex = (params.get("regex") or ["0"])[0] == "1"
            return self._send(200, json.dumps(
                search_log(platform, keyword, limit, use_regex), ensure_ascii=False
            ))

        if route == ["log", "meta"]:
            log_file = PLATFORMS[platform]["log"]
            exists = log_file.exists()
            return self._send(200, json.dumps({
                "exists": exists,
                "file": str(log_file),
                "size": log_file.stat().st_size if exists else 0,
                "mtime": log_file.stat().st_mtime if exists else None,
            }, ensure_ascii=False))

        if len(route) == 2 and route[0] == "job":
            job_id = route[1]
            params = parse_qs(urlparse(self.path).query)
            try:
                offset = int((params.get("offset") or ["0"])[0])
            except ValueError:
                offset = 0
            job = _jobs.get(job_id)
            if not job or job.platform != platform:
                return self._send(404, json.dumps({"error": "job not found"}))
            return self._send(200, json.dumps(job.snapshot(offset)))

        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._send(400, json.dumps({"error": "invalid json"}))

        parts = [part for part in path.split("/") if part]
        if parts == ["api", "settings", "project"]:
            platform = str(payload.get("platform", "")).strip()
            path_value = str(payload.get("path", "")).strip()
            if platform not in PLATFORMS:
                return self._send(400, json.dumps({"error": "platform not allowed"}))
            if not path_value:
                return self._send(400, json.dumps({"error": "项目目录不能为空"}))
            try:
                settings, info = save_project_setting(platform, path_value)
            except RuntimeError as exc:
                return self._send(409, json.dumps({"error": str(exc)}, ensure_ascii=False))
            except ValueError as exc:
                return self._send(400, json.dumps({"error": str(exc)}, ensure_ascii=False))
            return self._send(200, json.dumps({
                "settings": settings,
                "project": info,
            }, ensure_ascii=False))

        if parts == ["api", "settings", "pick-directory"]:
            platform = str(payload.get("platform", "")).strip()
            if platform not in PLATFORMS:
                return self._send(400, json.dumps({"error": "platform not allowed"}))
            try:
                result = pick_project_directory(platform)
            except RuntimeError as exc:
                return self._send(501, json.dumps({"error": str(exc)}, ensure_ascii=False))
            return self._send(200, json.dumps(result, ensure_ascii=False))

        if len(parts) >= 3 and parts[1] in PLATFORMS:
            platform = parts[1]
            route = parts[2:]
        else:
            platform = "ios"
            route = parts[1:]

        if route == ["run"]:
            action = str(payload.get("action", "all"))
            configuration = str(payload.get("configuration", "")).strip()
            if action not in ALLOWED_ACTIONS:
                return self._send(400, json.dumps({"error": "action not allowed"}))
            if configuration and configuration not in ("Debug", "Release"):
                return self._send(400, json.dumps({"error": "configuration not allowed"}))
            job, conflict = start_job(platform, action, configuration)
            if conflict:
                return self._send(409, json.dumps({
                    "error": f"该平台已有任务在运行: {conflict.action}",
                    "jobId": conflict.id,
                }))
            return self._send(200, json.dumps({"jobId": job.id}))

        if route == ["stop"]:
            job_id = str(payload.get("jobId", ""))
            job = _jobs.get(job_id)
            if job and job.platform == platform and stop_job(job):
                return self._send(200, json.dumps({"stopped": True}))
            return self._send(200, json.dumps({"stopped": False}))

        if route == ["device", "select"]:
            udid = str(payload.get("udid", "")).strip()
            name = str(payload.get("name", "")).strip()
            with _device_lock:
                _selected_devices[platform]["udid"] = udid
                _selected_devices[platform]["name"] = name
            return self._send(200, json.dumps({
                "selected": {"udid": udid, "name": name},
            }, ensure_ascii=False))

        return self._send(404, json.dumps({"error": "not found"}))


def main():
    parser = ArgumentParser(description="App Debug local server")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    for runtime in PLATFORMS.values():
        runner = runtime["runner"]
        if not runner.exists():
            raise SystemExit(f"找不到 {runner}")
        if not os.access(runner, os.X_OK):
            os.chmod(runner, 0o755)

    server = ThreadingHTTPServer((HOST, args.port), Handler)
    url = f"http://{HOST}:{args.port}"
    print(f"App Debug 已启动: {url}")
    print("按 Ctrl+C 停止")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        stop_all_jobs()
        server.server_close()


if __name__ == "__main__":
    main()
