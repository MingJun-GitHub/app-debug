"""Task snapshots shared by the local HTTP and MCP layers."""

from __future__ import annotations

import threading
import time
import uuid


class Job:
    def __init__(self, platform, action, configuration="", session_id=""):
        self.id = uuid.uuid4().hex[:12]
        self.platform = platform
        self.action = action
        self.configuration = configuration
        self.session_id = session_id
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
            "sessionId": self.session_id,
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

