#!/bin/zsh
#
# run163 - 用 Xcode 26.3 命令行构建、安装、启动 iOS App
#
# 用法:
#   ./run163.sh              构建 + 安装 + 启动
#   ./run163.sh build        只构建
#   ./run163.sh install      只安装（用上次产物）
#   ./run163.sh launch       只启动
#   ./run163.sh log          启动并挂控制台日志
#   ./run163.sh doctor       检查环境
#   ./run163.sh logs         拉取 xlog 并解码
#
set -u

# ---------- 可配置项 ----------
PROJECT_DIR="${PROJECT_DIR:-/Users/mingjun/Desktop/app/ios}"
XCODE_APP="${XCODE_APP:-/Applications/Xcode-26.3.app}"
WORKSPACE="${WORKSPACE:-BloomchicStore.xcworkspace}"
SCHEME="${SCHEME:-BloomchicStore-Debug}"
CONFIGURATION="${CONFIGURATION:-Debug}"
DERIVED_DATA="${DERIVED_DATA:-./.derivedData}"
BUNDLE_ID="${BUNDLE_ID:-com.bloomchic.shopify}"
DEVICE_UDID="${DEVICE_UDID:-}"
DEVICE_NAME="${DEVICE_NAME:-}"

# ---------- 输出 ----------
if [[ -t 1 ]]; then
  C_RESET=$'\e[0m'; C_BOLD=$'\e[1m'
  C_RED=$'\e[31m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'; C_BLUE=$'\e[34m'; C_GRAY=$'\e[90m'
else
  C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_GRAY=""
fi

log()   { print -r -- "${C_BLUE}==>${C_RESET} $*"; }
ok()    { print -r -- "${C_GREEN}  ✓${C_RESET} $*"; }
warn()  { print -r -- "${C_YELLOW}  !${C_RESET} $*"; }
fail()  { print -r -- "${C_RED}  ✗${C_RESET} $*"; }
dim()   { print -r -- "${C_GRAY}    $*${C_RESET}"; }
hr()    { print -r -- "${C_GRAY}────────────────────────────────────────────────────────${C_RESET}"; }

die() {
  fail "$*"
  exit 1
}

# ---------- 环境 ----------
export DEVELOPER_DIR="$XCODE_APP/Contents/Developer"

# DERIVED_DATA 可能是相对路径（相对项目目录），统一解析成绝对路径
if [[ "$DERIVED_DATA" == /* ]]; then
  DERIVED_DATA_ABS="$DERIVED_DATA"
else
  DERIVED_DATA_ABS="$PROJECT_DIR/${DERIVED_DATA#./}"
fi
APP_PATH="$DERIVED_DATA_ABS/Build/Products/${CONFIGURATION}-iphoneos/BloomchicStore.app"

require_xcode() {
  [[ -d "$XCODE_APP" ]] || die "找不到 Xcode: $XCODE_APP"
  [[ -x "$XCODE_APP/Contents/Developer/usr/bin/xcodebuild" ]] || die "Xcode 目录不完整: $XCODE_APP"
}

detect_device() {
  if [[ -n "$DEVICE_UDID" ]]; then
    return 0
  fi

  local json
  json=$(xcrun xcdevice list 2>/dev/null)
  [[ -n "$json" ]] || die "无法枚举设备（xcdevice list 无输出）"

  local parsed
  parsed=$(print -r -- "$json" | /usr/bin/python3 -c '
import json, sys
try:
    items = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for d in items:
    if d.get("plugin") or d.get("platform") != "com.apple.platform.iphoneos":
        continue
    if d.get("ignored"):
        continue
    kind = "模拟器" if d.get("simulator") else "真机"
    print(f"{d.get(\"identifier\",\"\")}\t{d.get(\"name\",\"\")}\t{kind}\t{d.get(\"operatingSystemVersion\",\"\")}")
')

  [[ -n "$parsed" ]] || die "没有可用的 iOS 设备"

  # 优先真机，否则取第一个可用设备
  local chosen
  chosen=$(print -r -- "$parsed" | /usr/bin/awk -F'\t' '$3=="真机"{print; exit}')
  [[ -n "$chosen" ]] || chosen=$(print -r -- "$parsed" | head -1)

  DEVICE_UDID=$(print -r -- "$chosen" | /usr/bin/cut -f1)
  DEVICE_NAME=$(print -r -- "$chosen" | /usr/bin/cut -f2)
  [[ -n "$DEVICE_UDID" ]] || die "无法解析设备 UDID"
}

# ---------- 命令 ----------
cmd_sdk_info() {
  if [[ -f "$APP_PATH/Info.plist" ]]; then
    local sdk; sdk=$(/usr/libexec/PlistBuddy -c 'Print :DTSDKName' "$APP_PATH/Info.plist" 2>/dev/null)
    local xcode; xcode=$(/usr/libexec/PlistBuddy -c 'Print :DTXcode' "$APP_PATH/Info.plist" 2>/dev/null)
    ok "产物 SDK: ${sdk:-未知}  (DTXcode ${xcode:-未知})"
  fi
}

cmd_build() {
  log "构建 ${SCHEME} (${CONFIGURATION})"
  dim "Xcode   : $XCODE_APP"
  dim "工作区  : $PROJECT_DIR/$WORKSPACE"
  dim "缓存    : $DERIVED_DATA"
  hr

  cd "$PROJECT_DIR" || die "进入项目目录失败: $PROJECT_DIR"

  local logfile="/tmp/run163-build.log"
  local start=$SECONDS

  xcodebuild \
    -workspace "$WORKSPACE" \
    -scheme "$SCHEME" \
    -configuration "$CONFIGURATION" \
    -derivedDataPath "$DERIVED_DATA" \
    -destination "id=$DEVICE_UDID" \
    build > "$logfile" 2>&1
  local rc=$?

  if [[ $rc -ne 0 ]]; then
    fail "构建失败（耗时 $((SECONDS - start))s）"
    print -r -- ""
    print -r -- "${C_RED}--- 关键错误 ---${C_RESET}"
    /usr/bin/grep -nE '(^|: )(error|fatal error):' "$logfile" | head -30
    print -r -- ""
    print -r -- "${C_GRAY}完整日志: $logfile${C_RESET}"
    return 1
  fi

  ok "构建成功（耗时 $((SECONDS - start))s）"
  cmd_sdk_info
  return 0
}

cmd_install() {
  [[ -d "$APP_PATH" ]] || die "找不到产物: $APP_PATH（先执行 build）"
  log "安装到设备 $DEVICE_UDID"
  xcrun devicectl device install app --device "$DEVICE_UDID" "$APP_PATH" 2>&1 | /usr/bin/grep -E 'installationURL|bundleID|ERROR|error' | /usr/bin/sed 's/^/    /'
  local rc=${pipestatus[1]}
  [[ $rc -eq 0 ]] || return 1
  ok "安装完成"
}

cmd_launch() {
  log "启动 $BUNDLE_ID"
  xcrun devicectl device process launch \
    --device "$DEVICE_UDID" \
    --terminate-existing \
    --activate \
    "$BUNDLE_ID" 2>&1 | /usr/bin/sed 's/^/    /'
  local rc=${pipestatus[1]}
  [[ $rc -eq 0 ]] || return 1
  ok "已启动"
}

cmd_log() {
  log "启动并挂控制台（Ctrl+C 退出日志，App 继续运行）"
  hr
  xcrun devicectl device process launch \
    --console \
    --terminate-existing \
    --device "$DEVICE_UDID" \
    "$BUNDLE_ID" 2>&1 \
    | /usr/bin/sed -u 's/^/[device] /'
  local rc=${pipestatus[1]}
  return "$rc"
}

cmd_doctor() {
  log "环境检查"
  hr

  if [[ -x "$XCODE_APP/Contents/Developer/usr/bin/xcodebuild" ]]; then
    local v; v=$("$XCODE_APP/Contents/Developer/usr/bin/xcodebuild" -version 2>/dev/null | head -1)
    ok "Xcode: $v"
  else
    fail "Xcode 不可用: $XCODE_APP"
  fi

  local sel; sel=$(xcode-select -p 2>/dev/null)
  if [[ "$sel" == "$XCODE_APP/Contents/Developer" ]]; then
    ok "xcode-select 指向 26.3"
  else
    warn "xcode-select 指向 $sel"
    dim "本脚本用 DEVELOPER_DIR 覆盖，不受影响"
  fi

  ok "macOS: $(sw_vers -productVersion)"

  local saved_udid="$DEVICE_UDID"
  DEVICE_UDID=""
  if detect_device 2>/dev/null; then
    ok "设备: ${DEVICE_NAME:-$DEVICE_UDID} ($DEVICE_UDID)"
  else
    fail "未检测到可用 iOS 设备"
  fi
  DEVICE_UDID="$saved_udid"

  if [[ -f "$PROJECT_DIR/$WORKSPACE/contents.xcworkspacedata" ]]; then
    ok "工作区存在"
  else
    fail "工作区缺失: $PROJECT_DIR/$WORKSPACE"
  fi

  local xcconfig="$PROJECT_DIR/Pods/Target Support Files/Pods-BloomchicStore/Pods-BloomchicStore.debug.xcconfig"
  if [[ -f "$xcconfig" ]]; then
    local root; root=$(/usr/bin/grep -m1 '^PODS_ROOT' "$xcconfig" | /usr/bin/sed 's/^PODS_ROOT = //')
    if [[ "$root" == '${SRCROOT}/Pods' ]]; then
      ok "PODS_ROOT 正常"
    else
      fail "PODS_ROOT 异常: $root"
      dim "在项目目录执行 pod install 修复"
    fi
  else
    warn "未找到 Pods 配置，可能需要 pod install"
  fi

  if [[ -d "$APP_PATH" ]]; then
    cmd_sdk_info
  else
    dim "尚无构建产物"
  fi
}

cmd_logs() {
  log "拉取并解码 xlog"
  cd "$PROJECT_DIR" || die "进入项目目录失败"
  [[ -x ./Script/pull_log.sh ]] || die "找不到 Script/pull_log.sh"
  ./Script/pull_log.sh "$DEVICE_UDID"
  ok "输出: $PROJECT_DIR/log/decoded.log"
}

cmd_grep() {
  local keyword="${1:-}"
  [[ -n "$keyword" ]] || die "用法: ./run163.sh grep <关键字>"
  local file="$PROJECT_DIR/log/decoded.log"
  [[ -f "$file" ]] || die "找不到 $file（先执行 ./run163.sh logs）"
  log "搜索 $file: $keyword"
  hr
  /usr/bin/grep -n --color=never -F -- "$keyword" "$file" | tail -200
}

cmd_devices() {
  # 输出 JSON，供网页选择设备
  local json
  json=$(xcrun xcdevice list 2>/dev/null) || json="[]"
  print -r -- "$json" | /usr/bin/python3 -c '
import json, sys
try:
    items = json.load(sys.stdin)
except Exception:
    items = []
out = []
for d in items:
    if d.get("platform") not in ("com.apple.platform.iphoneos", "com.apple.platform.iphonesimulator"):
        continue
    if d.get("ignored"):
        continue
    out.append({
        "udid": d.get("identifier", ""),
        "name": d.get("name", ""),
        "model": d.get("modelName", ""),
        "os": d.get("operatingSystemVersion", ""),
        "simulator": bool(d.get("simulator")),
        "available": bool(d.get("available")),
        "error": d.get("error"),
    })
out.sort(key=lambda x: (x["simulator"], not x["available"], x["name"]))
print(json.dumps(out, ensure_ascii=False))
'
}

# ---------- 入口 ----------
usage() {
  print -r -- "${C_BOLD}run163${C_RESET} - Xcode 26.3 命令行构建工具"
  print -r -- ""
  print -r -- "用法: ./run163.sh [命令]"
  print -r -- ""
  print -r -- "  （无参数） 构建 + 安装 + 启动"
  print -r -- "  build      只构建"
  print -r -- "  install    只安装"
  print -r -- "  launch     只启动"
  print -r -- "  log        启动并挂控制台日志"
  print -r -- "  logs       拉取并解码 App 日志"
  print -r -- "  doctor     环境检查"
  print -r -- "  devices    列出可用设备（JSON）"
  print -r -- "  grep <kw>  在已解码日志里搜索关键字"
  print -r -- ""
  print -r -- "环境变量覆盖: PROJECT_DIR XCODE_APP SCHEME CONFIGURATION DEVICE_UDID"
}

require_xcode

case "${1:-all}" in
  all)
    detect_device
    log "设备: ${DEVICE_NAME:-$DEVICE_UDID}"
    cmd_build && cmd_install && cmd_launch
    ;;
  build)
    detect_device
    cmd_build
    ;;
  install)
    detect_device
    cmd_install
    ;;
  launch)
    detect_device
    cmd_launch
    ;;
  log)
    detect_device
    cmd_log
    ;;
  logs)
    detect_device
    cmd_logs
    ;;
  devices)
    cmd_devices
    ;;
  grep)
    shift
    cmd_grep "$@"
    ;;
  doctor)
    cmd_doctor
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
