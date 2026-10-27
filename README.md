# App Debug

前端开发者使用的本地 iOS / Android 调试工作台。iOS 与 Android 使用彼此独立的项目、设备、任务和日志状态。

## 技术栈

- Nuxt 3
- Nuxt UI 2
- Vue 3
- Python 标准库本地 API
- Xcode 26.3 / `xcrun`
- Android SDK / Gradle / `adb`

## 开发

安装依赖：

```sh
npm install
```

同时启动 Nuxt UI 和 Python API：

```sh
npm run dev
```

默认地址：

- UI: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8787>

也可以分开启动：

```sh
npm run dev:api
npm run dev:ui
```

## 生产构建

```sh
npm run build
python3 server.py
```

浏览器会打开 <http://127.0.0.1:8787>。Python 服务同时托管 `.output/public` 和 `/api/*`。

## 页面结构

- 运行：实时构建和启动事件、关键字过滤、错误/警告/网络快捷筛选
- 问题：本次运行的真实错误、源码行号和最近上下文
- 日志：搜索设备 `decoded.log`
- 运行配置：设备选择、Debug/Release、构建、安装、启动和拉日志
- 设备支持手动重新检测，插入设备后无需等待自动轮询

## 快捷键

| 快捷键 | 操作 |
|---|---|
| `⌘ ↵` | 构建并启动 |
| `⌘ B` | 构建 |
| `⌘ I` | 安装 |
| `⌘ L` | 启动 |
| `⌘ D` | 启动并跟随日志 |
| `⇧ ⌘ L` | 拉取并解码日志 |
| `⇧ ⌘ D` | 环境检查 |
| `⌘ F` | 聚焦日志过滤 |
| `⌘ .` | 停止当前平台任务 |
| `⌘ K` | 清空当前平台事件流 |

平台状态完全隔离：

- iOS 使用 `~/Desktop/app/ios`、`run163.sh` 和 `xcrun`
- Android 使用 `~/Desktop/app/android`、`runandroid.sh` 和 `adb`
- 切换平台不会清空另一平台的设备、日志或运行状态

## 运行脚本

```sh
./run163.sh            # 构建 + 安装 + 启动
./run163.sh build      # 只构建
./run163.sh install    # 只安装
./run163.sh launch     # 只启动
./run163.sh log        # 启动并挂控制台日志
./run163.sh logs       # 拉取并解码 App 日志
./run163.sh doctor     # 环境检查
```

配置通过环境变量覆盖：

```sh
PROJECT_DIR=/path/to/ios \
SCHEME=OtherScheme \
DEVICE_UDID=00008150-XXXXXXXXXXXX \
./run163.sh
```

支持 `PROJECT_DIR`、`XCODE_APP`、`WORKSPACE`、`SCHEME`、`CONFIGURATION`、`DERIVED_DATA`、`BUNDLE_ID`、`DEVICE_UDID`。

## Android 运行脚本

```sh
./runandroid.sh            # 构建 + 安装 + 启动
./runandroid.sh build      # 只构建
./runandroid.sh install    # 只安装
./runandroid.sh launch     # 只启动
./runandroid.sh log        # 启动并跟随 logcat
./runandroid.sh logs       # 拉取并解码 xlog
./runandroid.sh doctor     # 环境检查
```

默认项目目录为 `~/Desktop/app/android`，包名为 `com.bloomchic.app`。可通过 `PROJECT_DIR`、`CONFIGURATION`、`BUNDLE_ID`、`DEVICE_SERIAL` 覆盖。

iOS 和 Android 各自使用独立 API 前缀：

- `/api/ios/*`
- `/api/android/*`

## 服务安全

Python 服务只监听 `127.0.0.1`，默认不对外网开放。
