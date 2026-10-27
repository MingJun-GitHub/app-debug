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

_jobs = {}
_jobs_lock = threading.Lock()

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
        self.done = False
        self.exit_code = None
        self.started = time.time()
        self.finished = None
        self.proc = None
        self.cancel_requested = threading.Event()
        self.completed = threading.Event()

    def append(self, text):
        for line in text.splitlines():
            self.lines.append(line)
        if len(self.lines) > 5000:
            removed = len(self.lines) - 3000
            self.lines = self.lines[-3000:]
            self.line_base += removed

    def snapshot(self, offset=0):
        truncated = offset < self.line_base
        local_offset = max(0, offset - self.line_base)
        return {
            "id": self.id,
            "platform": self.platform,
            "action": self.action,
            "done": self.done,
            "cancelled": self.cancel_requested.is_set(),
            "exitCode": self.exit_code,
            "running": self.proc is not None and self.proc.poll() is None,
            "elapsed": round((self.finished or time.time()) - self.started, 1),
            "total": self.line_base + len(self.lines),
            "offset": offset,
            "truncated": truncated,
            "lines": self.lines[local_offset:],
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
        # 即使 shell 已退出，仍清理可能忽略 TERM 的后代进程。
        time.sleep(3)
        _signal_job(job, signal.SIGKILL)

    threading.Thread(target=finish_stop, daemon=True).start()
    return True


def start_job(platform, action, configuration=""):
    job = Job(platform, action, configuration)
    with _jobs_lock:
        _jobs[job.id] = job
        if len(_jobs) > 20:
            for key in sorted(_jobs, key=lambda k: _jobs[k].started)[:-20]:
                _jobs.pop(key, None)
    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return job


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

        if route == ["log", "search"]:
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            keyword = (params.get("q") or [""])[0]
            if not keyword:
                return self._send(400, json.dumps({"error": "缺少 q 参数"}))
            try:
                limit = min(int((params.get("limit") or ["200"])[0]), 1000)
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
            with _jobs_lock:
                for job in _jobs.values():
                    if (
                        job.platform == platform
                        and not job.done
                        and job.action in ("all", "build")
                    ):
                        return self._send(409, json.dumps({
                            "error": "已有构建在进行中",
                            "jobId": job.id,
                        }))
            job = start_job(platform, action, configuration)
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
        server.server_close()


if __name__ == "__main__":
    main()
