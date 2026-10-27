#!/usr/bin/env python3
"""
Xcode 26.3 本地控制台

只用标准库。启动后在浏览器打开 http://127.0.0.1:8787
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
RUNNER = BASE_DIR / "run163.sh"
DIST_DIR = BASE_DIR / ".output" / "public"
INDEX = DIST_DIR / "index.html"

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8787"))

ALLOWED_ACTIONS = {"all", "build", "install", "launch", "log", "logs", "doctor"}

_jobs = {}
_jobs_lock = threading.Lock()

# 当前选中的设备（网页切换后写入，构建时注入环境变量）
_device_lock = threading.Lock()
_selected_device = {"udid": "", "name": ""}

LOG_FILE = Path("/Users/mingjun/Desktop/app/ios/log/decoded.log")


class Job:
    def __init__(self, action, configuration=""):
        self.id = uuid.uuid4().hex[:12]
        self.action = action
        self.configuration = configuration
        self.lines = []
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
            self.lines = self.lines[-3000:]

    def snapshot(self, offset=0):
        return {
            "id": self.id,
            "action": self.action,
            "done": self.done,
            "cancelled": self.cancel_requested.is_set(),
            "exitCode": self.exit_code,
            "running": self.proc is not None and self.proc.poll() is None,
            "elapsed": round((self.finished or time.time()) - self.started, 1),
            "total": len(self.lines),
            "offset": offset,
            "lines": self.lines[offset:],
        }


def _run_job(job):
    cmd = ["/bin/zsh", str(RUNNER), job.action]
    env = dict(os.environ)
    env["TERM"] = "dumb"
    if job.configuration:
        env["CONFIGURATION"] = job.configuration
    with _device_lock:
        if _selected_device["udid"]:
            env["DEVICE_UDID"] = _selected_device["udid"]
            env["DEVICE_NAME"] = _selected_device["name"]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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


def start_job(action, configuration=""):
    job = Job(action, configuration)
    with _jobs_lock:
        _jobs[job.id] = job
        if len(_jobs) > 20:
            for key in sorted(_jobs, key=lambda k: _jobs[k].started)[:-20]:
                _jobs.pop(key, None)
    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return job


def latest_sdk():
    """读取最近产物里的 SDK 名，用于页面展示。"""
    app = (
        Path("/Users/mingjun/Desktop/app/ios")
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


def device_info():
    try:
        out = subprocess.run(
            ["xcrun", "xcdevice", "list"],
            capture_output=True, text=True, timeout=20,
        )
        items = json.loads(out.stdout)
        fallback = None
        for item in items:
            if item.get("simulator"):
                continue
            if item.get("platform") != "com.apple.platform.iphoneos":
                continue
            state = "connected" if item.get("available") else "unavailable"
            info = {
                "name": item.get("name", ""),
                "udid": item.get("identifier", ""),
                "state": state,
                "interface": item.get("interface", ""),
                "os": item.get("operatingSystemVersion", ""),
            }
            if item.get("available"):
                return info
            fallback = fallback or info
        if fallback:
            return fallback
    except Exception:  # noqa: BLE001
        pass
    return None


def list_devices():
    """通过 run163.sh devices 取结构化设备列表（含模拟器）。"""
    try:
        out = subprocess.run(
            ["/bin/zsh", str(RUNNER), "devices"],
            capture_output=True, text=True, timeout=90, cwd=str(BASE_DIR),
        )
        raw = out.stdout.strip()
        if not raw:
            return []
        return json.loads(raw.split("\n")[-1])
    except Exception:  # noqa: BLE001
        return []


def search_log(keyword, limit=200, use_regex=False):
    """在已解码日志中检索，返回匹配行。"""
    if not LOG_FILE.exists():
        return {
            "ok": False,
            "error": "log/decoded.log 不存在，请先点「拉取 App 日志」",
            "lines": [],
            "total": 0,
        }
    try:
        if use_regex:
            pattern = re.compile(keyword)
        else:
            pattern = None
        hits = []
        with LOG_FILE.open("r", encoding="utf-8", errors="replace") as fh:
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
            "file": str(LOG_FILE),
            "size": LOG_FILE.stat().st_size,
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

        if path == "/api/status":
            with _device_lock:
                selected = dict(_selected_device)
            return self._send(200, json.dumps({
                "device": device_info(),
                "sdk": latest_sdk(),
                "selected": selected,
            }, ensure_ascii=False))

        if path == "/api/devices":
            return self._send(200, json.dumps({
                "devices": list_devices(),
            }, ensure_ascii=False))

        if path == "/api/log/search":
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
                search_log(keyword, limit, use_regex), ensure_ascii=False
            ))

        if path == "/api/log/meta":
            exists = LOG_FILE.exists()
            return self._send(200, json.dumps({
                "exists": exists,
                "file": str(LOG_FILE),
                "size": LOG_FILE.stat().st_size if exists else 0,
                "mtime": LOG_FILE.stat().st_mtime if exists else None,
            }, ensure_ascii=False))

        if path.startswith("/api/job/"):
            job_id = path.rsplit("/", 1)[-1]
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            offset = 0
            for part in query.split("&"):
                if part.startswith("offset="):
                    try:
                        offset = int(part.split("=", 1)[1])
                    except ValueError:
                        offset = 0
            job = _jobs.get(job_id)
            if not job:
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

        if path == "/api/run":
            action = str(payload.get("action", "all"))
            configuration = str(payload.get("configuration", "")).strip()
            if action not in ALLOWED_ACTIONS:
                return self._send(400, json.dumps({"error": "action not allowed"}))
            if configuration and configuration not in ("Debug", "Release"):
                return self._send(400, json.dumps({"error": "configuration not allowed"}))
            with _jobs_lock:
                for job in _jobs.values():
                    if not job.done and job.action in ("all", "build"):
                        return self._send(409, json.dumps({
                            "error": "已有构建在进行中",
                            "jobId": job.id,
                        }))
            job = start_job(action, configuration)
            return self._send(200, json.dumps({"jobId": job.id}))

        if path == "/api/stop":
            job_id = str(payload.get("jobId", ""))
            job = _jobs.get(job_id)
            if job and stop_job(job):
                return self._send(200, json.dumps({"stopped": True}))
            return self._send(200, json.dumps({"stopped": False}))

        if path == "/api/device/select":
            udid = str(payload.get("udid", "")).strip()
            name = str(payload.get("name", "")).strip()
            with _device_lock:
                _selected_device["udid"] = udid
                _selected_device["name"] = name
            return self._send(200, json.dumps({
                "selected": {"udid": udid, "name": name},
            }, ensure_ascii=False))

        return self._send(404, json.dumps({"error": "not found"}))


def main():
    parser = ArgumentParser(description="App Debug local server")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not RUNNER.exists():
        raise SystemExit(f"找不到 {RUNNER}")
    if not os.access(RUNNER, os.X_OK):
        os.chmod(RUNNER, 0o755)

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
