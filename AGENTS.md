# AGENTS.md

## 项目定位

App Debug 是本地 iOS / Android 调试工作台，使用 Nuxt 3 + Python 标准库。它负责设备发现、构建/安装/启动、实时任务输出、日志检索，以及读取已安装 App 的环境、设备身份和 Sensors AB 实验分组。

iOS 与 Android 必须保持隔离：切换平台时，另一平台的设备选择、任务、日志和设备上下文不能被覆盖或清空。

## 架构

| 路径 | 职责 |
|---|---|
| `app.vue` | 页面结构、平台切换、四个 Tab、任务操作 |
| `composables/useDebugRunner.ts` | 设备、任务、日志、设备上下文的 API 状态 |
| `server.py` | 本地 HTTP API、静态页面托管、任务进程管理 |
| `device_context.py` | iOS plist / NSKeyedArchiver 和 Android `run-as` / MMKV / SharedPreferences 读取 |
| `project_settings.py` | 本机项目目录持久化、项目结构校验和 Git 元数据读取 |
| `run163.sh`、`runandroid.sh` | 两端的构建、安装、启动、日志和环境检查 |
| `tests/test_device_context.py` | 设备上下文解析测试 |
| `tests/test_project_settings.py` | 项目关联、校验和分支读取测试 |
| `App Debug.app`、`Stop App Debug.app` | macOS 一键启动/停止本地服务并打开浏览器 |
| `Start App Debug.command` | 在终端前台启动服务，首次缺少依赖或构建产物时自动准备 |

本地 API 仅监听 `127.0.0.1:8787`。Nuxt 开发服务运行在 `3000`，并将 `/api` 代理到 `8787`。

## 功能说明

- `运行`：展示构建、安装、启动和实时日志，支持分类筛选、关键词过滤、复制和停止任务。
- `问题`：汇总当前运行错误，提取源码文件行号，并保留最近上下文。
- `日志`：搜索 `log/decoded.log`，支持普通字符串和正则。
- `设备`：展示 UDID、型号、系统、Debug/Release、测试/线上环境、站点、国家、`device_id`、`distinctId`，以及 AB 进组/出组结果。
- 每个平台同时最多运行一个任务。停止任务需要二次确认；页面离开时会通知后端终止活动任务。
- 设备上下文读取失败时返回部分数据，不能阻塞设备选择或影响其他调试功能。
- 顶部项目名称打开“项目设置”，可关联 iOS/Android 目录并查看分支、提交和工作区状态。

## 设备上下文来源

设备上下文只读，不修改 iOS 或 Android 工程。

### iOS

- 使用 `xcrun devicectl device copy from` 读取 `com.bloomchic.shopify` 的 App 数据容器。
- UserDefaults：`Library/Preferences/com.bloomchic.shopify.plist`。
- AB 缓存：`Library/sensorsanalytics-abtest-SensorsABTestExperimentResultsResponseData.plist`。
- `isDebugUrlEnabled` 为 true 时表示测试环境，否则表示线上环境。

### Android

- 使用 `adb -s <serial> exec-out run-as com.bloomchic.app`。
- AB 缓存：`shared_prefs/spUtils.xml`。
- Sensors 身份：`shared_prefs/com.sensorsdata.analytics.android.sdk.SensorsDataAPI.xml`。
- 环境、App 设备 ID 和站点：`files/mmkv/mmkv.default`。
- MMKV 的 key/value 长度使用 varint 编码；修改读取逻辑时必须保持与真实格式一致并更新测试。

Android 完整上下文仅适用于 Debug 包。Release 包通常无法使用 `run-as`，此时返回设备信息并标记 App 上下文不可用。

AB 结果是本地缓存快照。实验状态变化后，应先在 App 内触发 AB 请求，再点击“设备”页的刷新按钮。

## 项目目录设置

- 设置默认保存在 `~/Library/Application Support/App Debug/settings.json`。
- `APP_DEBUG_SETTINGS` 可覆盖设置文件位置。
- 保存前校验 iOS 的 workspace/project 或 Android 的 `gradlew` 和 Gradle settings 文件。
- 修改关联目录时，对应平台不能有活动任务。
- 项目路径属于用户本机配置，禁止写入仓库或作为默认示例提交。

## 开发与验证

```sh
npm install
npm run dev
```

提交前至少执行：

```sh
python3 -m unittest discover -s tests -v
npm run build
```

Nuxt 页面支持 HMR。修改 `server.py` 或 `device_context.py` 后必须重启 Python 服务；`scripts/dev.mjs` 不会自动重载 Python：

```sh
lsof -nP -iTCP:8787 -sTCP:LISTEN
```

如果 `8787` 已被其他进程占用，使用隔离端口测试：

```sh
npm run build
python3 server.py --no-browser --port 8791
```

## 使用 ego-browser 调试

需要浏览器验证时，使用 `ego-browser`。开始前先读取并遵循当前 Skill：

```sh
cat ~/.agents/skills/ego-browser/SKILL.md
ego-browser skill
```

整个目标只创建一个 TaskSpace，并复用已有页面 `p1`。Android 标准验证流程：

```sh
ego-browser nodejs <<'EOF'
const task = await taskSpace("app-debug android e2e");
const page = task.page("p1");

await page.goto("http://127.0.0.1:8791");
await page.waitForLoadState();

await page.click("loc=role:tab[name='Android']", { label: "切换 Android" });
await page.waitForFunction(
  () => document.body.innerText.includes("Android 调试台"),
  undefined,
  { timeout: 10000 },
);

await page.click("loc=role:tab[name='设备']", { label: "打开设备页" });
await page.waitForFunction(
  () => {
    const text = document.body.innerText;
    return text.includes("AB 实验分组") || text.includes("读取失败");
  },
  undefined,
  { timeout: 30000 },
);

const api = await page.fetch(
  "/api/android/device/context?configuration=Debug&refresh=1",
  { timeout: 30000 },
);
const text = await page.evaluate(() => document.body.innerText);
const screenshot = await page.screenshot({
  path: "/private/tmp/app-debug-android-e2e.png",
});

console.log({
  apiStatus: api.status,
  hasReadError: text.includes("读取失败"),
  hasEnvironment: text.includes("测试环境") || text.includes("线上环境"),
  hasDeviceId: !text.includes("App device_id\n-"),
  hasExperimentSection: text.includes("AB 实验分组"),
  screenshot,
});
EOF
```

iOS 验证复用相同步骤，只替换平台 Tab 和 `/api/ios/...`。断言中使用字段是否存在，不硬编码个人设备 ID、Distinct ID、Experiment ID 或实验分组。

通过条件：

- 设备上下文 API 返回 HTTP `200`。
- 页面不出现“读取失败”。
- 设备、构建配置、环境、身份和 AB 区域可见。
- 有缓存时至少展示一条实验 key 和分组。
- 截图布局清晰，无控件重叠。
- 成功后执行 `await task.finish({ keep: [] })`。

## 常见问题

| 现象 | 检查 | 处理 |
|---|---|---|
| 设备页显示 `not found` | `lsof -nP -iTCP:8787 -sTCP:LISTEN` | 旧 Python 进程未重启，启动最新服务 |
| Android 环境未知、`device_id` 为空 | 检查 MMKV 文件和解析结果 | 校验 varint 长度、key 及站点字段 |
| Distinct ID 重复或异常 | 检查 `SensorsDataAPI.xml` | 优先使用 `events_distinct_id` |
| Android App 上下文不可用 | `adb devices -l`、`adb shell run-as com.bloomchic.app ls` | 安装 Debug 包并至少启动一次 App |
| iOS App 上下文不可用 | 设备锁定、信任和安装状态 | 解锁并授权，打开 App 后重试刷新 |
| AB 数据不更新 | App 内实验请求 | 在 App 内触发 AB 拉取，再刷新设备页 |
| 页面仍是旧版本 | 当前 URL 和服务进程 | 强制刷新或访问最新构建端口 |

## 修改边界

- 设备上下文保持只读、Debug 导向；不修改 iOS/Android 业务仓库。
- 响应和页面中不得出现 token、Cookie、Authorization、APNs/FCM token 或用户凭据。
- 保留工作区中与当前任务无关的用户修改。
- 缓存格式属于兼容边界；修改 `device_context.py` 时同步更新解析测试。
