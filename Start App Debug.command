#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8787}"
URL="http://127.0.0.1:${PORT}"

find_python() {
  local candidate
  candidate="$(command -v python3 2>/dev/null || true)"
  if [[ -z "$candidate" && -x /opt/homebrew/bin/python3 ]]; then
    candidate=/opt/homebrew/bin/python3
  fi
  if [[ -z "$candidate" && -x /usr/bin/python3 ]]; then
    candidate=/usr/bin/python3
  fi
  print -r -- "$candidate"
}

find_npm() {
  local candidate
  candidate="$(command -v npm 2>/dev/null || true)"
  if [[ -z "$candidate" ]]; then
    candidate="$(/bin/ls -1 "$HOME"/.nvm/versions/node/*/bin/npm 2>/dev/null | /usr/bin/tail -1)"
  fi
  if [[ -z "$candidate" && -x /opt/homebrew/bin/npm ]]; then
    candidate=/opt/homebrew/bin/npm
  fi
  print -r -- "$candidate"
}

wait_until_ready() {
  local attempt
  for attempt in {1..40}; do
    if /usr/bin/curl -fsS --max-time 1 "$URL/" >/dev/null 2>&1; then
      return 0
    fi
    /bin/sleep 0.25
  done
  return 1
}

if /usr/bin/curl -fsS --max-time 1 "$URL/" >/dev/null 2>&1; then
  echo "App Debug 已在运行：$URL"
  /usr/bin/open "$URL"
  exit 0
fi

if /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "端口 $PORT 已被其他进程占用，请先关闭占用进程。"
  exit 1
fi

PYTHON_BIN="$(find_python)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "找不到 python3，请先安装 Python。"
  exit 1
fi

if [[ ! -d "$ROOT/node_modules" ]]; then
  NPM_BIN="$(find_npm)"
  if [[ -z "$NPM_BIN" ]]; then
    echo "找不到 npm，请先安装 Node.js。"
    exit 1
  fi
  (cd "$ROOT" && "$NPM_BIN" install) || exit 1
fi

if [[ ! -f "$ROOT/.output/public/index.html" ]]; then
  NPM_BIN="$(find_npm)"
  if [[ -z "$NPM_BIN" ]]; then
    echo "找不到 npm，请先安装 Node.js。"
    exit 1
  fi
  (cd "$ROOT" && "$NPM_BIN" run build) || exit 1
fi

cd "$ROOT" || exit 1
echo "正在启动 App Debug：$URL"
"$PYTHON_BIN" server.py --no-browser &
server_pid=$!

cleanup() {
  /bin/kill -INT "$server_pid" 2>/dev/null || true
}
trap cleanup INT TERM HUP

if ! wait_until_ready; then
  echo "启动失败，请检查上方日志。"
  cleanup
  exit 1
fi

/usr/bin/open "$URL"
echo "服务运行中。按 Ctrl+C 停止，或双击 Stop App Debug。"
wait "$server_pid"
exit $?
