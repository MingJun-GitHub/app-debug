#!/bin/zsh
#
# runandroid - Android 本地构建、安装、启动和日志工具
#
# 用法:
#   ./runandroid.sh          构建 + 安装 + 启动
#   ./runandroid.sh build    只构建
#   ./runandroid.sh install  只安装
#   ./runandroid.sh launch   只启动
#   ./runandroid.sh log      启动并跟随 logcat
#   ./runandroid.sh logs     拉取并解码 xlog
#   ./runandroid.sh doctor   环境检查
#
set -u

PROJECT_DIR="${PROJECT_DIR:-/Users/mingjun/Desktop/app/android}"
CONFIGURATION="${CONFIGURATION:-Debug}"
BUNDLE_ID="${BUNDLE_ID:-com.bloomchic.app}"
DEVICE_SERIAL="${DEVICE_SERIAL:-}"
GRADLEW="$PROJECT_DIR/gradlew"
PACKAGE_DIR="$PROJECT_DIR/app/build/outputs/apk"
LOG_FILE="$PROJECT_DIR/log/decoded.log"

if [[ "$CONFIGURATION" == "Release" ]]; then
  VARIANT="release"
  TASK=":app:assembleRelease"
  BUILD_TYPE="Release"
else
  VARIANT="debug"
  TASK=":app:assembleDebug"
  BUILD_TYPE="Debug"
fi

log()   { print -r -- "==> $*"; }
ok()    { print -r -- "  ✓ $*"; }
warn()  { print -r -- "  ! $*"; }
fail()  { print -r -- "  ✗ $*"; }
dim()   { print -r -- "    $*"; }

die() {
  fail "$*"
  exit 1
}

find_device() {
  if [[ -n "$DEVICE_SERIAL" ]]; then
    return 0
  fi

  DEVICE_SERIAL=$(adb devices | /usr/bin/awk '$2 == "device" { print $1; exit }')
  [[ -n "$DEVICE_SERIAL" ]] || die "未检测到可用的 Android 设备"
}

adb_device() {
  find_device
  adb -s "$DEVICE_SERIAL" "$@"
}

latest_apk() {
  local dir="$PACKAGE_DIR/$VARIANT"
  [[ -d "$dir" ]] || return 1
  /usr/bin/find "$dir" -maxdepth 1 -type f -name '*.apk' -print0 \
    | /usr/bin/xargs -0 /usr/bin/stat -f '%m %N' 2>/dev/null \
    | /usr/bin/sort -nr \
    | /usr/bin/head -1 \
    | /usr/bin/cut -d' ' -f2-
}

cmd_build() {
  log "构建 Android $BUILD_TYPE"
  dim "项目    : $PROJECT_DIR"
  dim "任务    : $TASK"
  hr="────────────────────────────────────────────────────────"
  print -r -- "$hr"

  cd "$PROJECT_DIR" || die "进入项目目录失败: $PROJECT_DIR"
  [[ -x "$GRADLEW" ]] || die "找不到 Gradle Wrapper: $GRADLEW"

  local -a env_args
  env_args=()
  if [[ "$CONFIGURATION" == "Release" ]]; then
    env_args=(
      "IsRelease=release"
      "AppVersion=${AppVersion:-4.2.1}"
    )
  fi

  env "${env_args[@]}" "$GRADLEW" "$TASK" --console=plain 2>&1 | /usr/bin/awk '
    /^WARNING: D8: Unexpected error during rewriting/ { d8++; skip = 1; next }
    /^WARNING: D8: An error occurred when parsing kotlin metadata/ { metadata++; skip = 1; next }
    skip && /^(com\.android\.tools\.r8\.|[[:space:]]*at )/ { next }
    {
      skip = 0
      print
      fflush()
    }
    END {
      if (d8 || metadata) {
        printf "  ! 已折叠 D8 Kotlin metadata 警告：%d 条类警告，%d 条汇总警告\n", d8, metadata
        fflush()
      }
    }
  '
  local rc=${pipestatus[1]}
  if [[ $rc -ne 0 ]]; then
    fail "Android 构建失败"
    return $rc
  fi
  ok "Android 构建成功"
  local apk
  apk=$(latest_apk) && dim "APK: $apk"
}

cmd_install() {
  local apk
  apk=$(latest_apk) || die "找不到 $BUILD_TYPE APK，请先执行 build"
  find_device
  log "安装到 Android 设备 $DEVICE_SERIAL"
  dim "APK: $apk"
  adb -s "$DEVICE_SERIAL" install -r "$apk"
  local rc=$?
  [[ $rc -eq 0 ]] || return $rc
  ok "安装完成"
}

cmd_launch() {
  find_device
  log "启动 $BUNDLE_ID"
  adb_device shell am force-stop "$BUNDLE_ID" >/dev/null 2>&1 || true
  adb_device shell monkey \
    -p "$BUNDLE_ID" \
    -c android.intent.category.LAUNCHER \
    1
  local rc=$?
  [[ $rc -eq 0 ]] || return $rc
  ok "已发送启动命令"
}

cmd_log() {
  find_device
  log "启动并跟随 logcat（Ctrl+C 退出日志）"
  print -r -- "────────────────────────────────────────────────────────"
  adb_device shell am force-stop "$BUNDLE_ID" >/dev/null 2>&1 || true
  local launch_output
  launch_output=$(adb_device shell monkey \
    -p "$BUNDLE_ID" \
    -c android.intent.category.LAUNCHER \
    1 2>&1)
  print -r -- "$launch_output"
  if ! print -r -- "$launch_output" | /usr/bin/grep -q 'Events injected:'; then
    fail "Android App 启动失败，未进入 logcat"
    return 1
  fi

  local pids=""
  local attempt
  for attempt in {1..12}; do
    pids=$(adb_device shell pidof "$BUNDLE_ID" 2>/dev/null | /usr/bin/xargs)
    [[ -n "$pids" ]] && break
    sleep 0.5
  done
  if [[ -n "$pids" ]]; then
    local pid_filter="${pids// /,}"
    dim "应用 PID: $pids"
    adb_device logcat -v threadtime --pid="$pid_filter"
    return $?
  fi

  local uid
  uid=$(adb_device shell dumpsys package "$BUNDLE_ID" 2>/dev/null \
    | /usr/bin/awk -F= '/userId=/ { gsub(/[^0-9]/, "", $2); print $2; exit }')
  if [[ -n "$uid" ]]; then
    warn "未获取到 PID，按应用 UID $uid 过滤日志"
    adb_device logcat -v threadtime --uid="$uid"
    return $?
  fi
  fail "应用进程未启动，无法建立实时日志流"
  return 1
}

cmd_logs() {
  find_device
  log "拉取并解码 Android xlog"
  cd "$PROJECT_DIR" || die "进入项目目录失败: $PROJECT_DIR"
  [[ -x ./scripts/pull_log.sh ]] || die "找不到 scripts/pull_log.sh"
  ./scripts/pull_log.sh "$DEVICE_SERIAL"
  [[ -f "$LOG_FILE" ]] && ok "输出: $LOG_FILE"
}

cmd_doctor() {
  local failures=0
  log "Android 环境检查"
  print -r -- "────────────────────────────────────────────────────────"

  if command -v java >/dev/null 2>&1; then
    ok "Java: $(java -version 2>&1 | head -1)"
  else
    fail "未找到 Java"
    failures=$((failures + 1))
  fi

  if command -v adb >/dev/null 2>&1; then
    ok "ADB: $(adb version | head -1)"
  else
    fail "未找到 adb"
    failures=$((failures + 1))
  fi

  if [[ -x "$GRADLEW" ]]; then
    ok "Gradle Wrapper 可执行"
  else
    fail "Gradle Wrapper 不可用"
    failures=$((failures + 1))
  fi
  if [[ -f "$PROJECT_DIR/settings.gradle" ]]; then
    ok "Android 项目存在"
  else
    fail "Android 项目缺失"
    failures=$((failures + 1))
  fi

  local devices
  devices=$(adb devices | /usr/bin/awk 'NR > 1 && $2 == "device" { print $1 }')
  if [[ -n "$devices" ]]; then
    ok "设备: ${devices//$'\n'/, }"
  else
    warn "没有已授权的 Android 设备"
  fi

  local apk
  if apk=$(latest_apk); then
    ok "最近 APK: $(basename "$apk")"
  else
    dim "尚无 $BUILD_TYPE APK"
  fi
  (( failures == 0 ))
}

case "${1:-all}" in
  all)
    cmd_build && cmd_install && cmd_launch
    ;;
  build)
    cmd_build
    ;;
  install)
    cmd_install
    ;;
  launch)
    cmd_launch
    ;;
  log)
    cmd_log
    ;;
  logs)
    cmd_logs
    ;;
  doctor)
    cmd_doctor
    ;;
  *)
    die "未知操作: $1"
    ;;
esac
