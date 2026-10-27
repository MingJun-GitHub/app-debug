# App Debug

前端开发者使用的本地 iOS / Android 调试工作台。当前已经接通 iOS 构建、安装、启动、设备管理和日志能力，Android 保留了平台入口与扩展位置。

## 技术栈

- Nuxt 3
- Nuxt UI 2
- Vue 3
- Python 标准库本地 API
- Xcode 26.3 / `xcrun`

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

## Android 扩展

页面已经保留 Android 平台入口。后续可以在 `composables/useDebugRunner.ts` 外增加平台适配器，把同一套事件结构映射到：

- `./gradlew assembleDebug`
- `adb install -r`
- `adb shell am start`
- `adb logcat`

## 服务安全

Python 服务只监听 `127.0.0.1`，默认不对外网开放。
