<script setup lang="ts">
import type { DebugEvent, Device } from '~/composables/useDebugRunner'

type TabKey = 'run' | 'issues' | 'logs'
type SeverityFilter = 'all' | 'error' | 'warning' | 'network'

const {
  status,
  physicalDevices,
  connectedDevice,
  sdk,
  events,
  errors,
  warnings,
  callStack,
  logs,
  logMeta,
  activeJob,
  jobDone,
  jobResult,
  elapsed,
  busy,
  clearEvents,
  refreshStatus,
  loadDevices,
  selectDevice,
  runAction,
  stopJob,
  searchLogs
} = useDebugRunner()

const platform = ref<'ios' | 'android'>('ios')
const activeTabIndex = ref(0)
const selectedDevice = ref<any>(null)
const buildConfiguration = ref('Debug')
const eventQuery = ref('')
const severity = ref<SeverityFilter>('all')
const logQuery = ref('')
const logRegex = ref(false)
const copied = ref(false)
const eventPane = ref<HTMLElement | null>(null)
let statusTimer: ReturnType<typeof setInterval> | undefined
let deviceTimer: ReturnType<typeof setInterval> | undefined

const tabs = [
  { key: 'run', label: '运行', icon: 'i-heroicons-play' },
  { key: 'issues', label: '问题', icon: 'i-heroicons-exclamation-triangle' },
  { key: 'logs', label: '日志', icon: 'i-heroicons-document-text' }
]

const activeTab = computed<TabKey>(() => (tabs[activeTabIndex.value]?.key as TabKey) || 'run')

const deviceOptions = computed(() => physicalDevices.value.map(device => ({
  label: `${device.name} · iOS ${device.os || '?'}`,
  icon: 'i-heroicons-device-phone-mobile',
  udid: device.udid,
  name: device.name,
  disabled: !device.available
})))

const configurationOptions = ['Debug', 'Release']

const severityOptions: Array<{ key: SeverityFilter, label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'error', label: '错误' },
  { key: 'warning', label: '警告' },
  { key: 'network', label: '网络' }
]

const issueCount = computed(() => errors.value.length)
const warningCount = computed(() => warnings.value.length)

const filteredEvents = computed(() => {
  const query = eventQuery.value.trim().toLowerCase()
  return events.value.filter((event) => {
    const matchesQuery = !query || event.text.toLowerCase().includes(query)
    if (!matchesQuery) return false
    if (severity.value === 'all') return true
    if (severity.value === 'error') return event.kind === 'error'
    if (severity.value === 'warning') return event.kind === 'warning'
    return /network|request|response|http|url|socket|tls|connection|api/i.test(event.text)
  })
})

const runLabel = computed(() => {
  if (busy.value && activeJob.value) return `运行中 · ${activeJob.value.action}`
  if (jobResult.value === 'cancelled') return '已停止'
  if (jobResult.value === 'error') return '运行失败'
  if (jobResult.value === 'success') return `运行完成 · ${elapsed.value}s`
  return '等待运行'
})

const runDotClass = computed(() => {
  if (busy.value) return 'run-dot busy'
  if (jobResult.value === 'error') return 'run-dot error'
  if (jobResult.value === 'success') return 'run-dot success'
  return 'run-dot'
})

const firstError = computed(() => errors.value.at(-1)?.text || '')
const latestEvents = computed(() => events.value.slice(-80))

async function initialize() {
  await refreshStatus()
  await loadDevices()
  const preferred = connectedDevice.value
    || physicalDevices.value.find(device => device.available)
    || physicalDevices.value[0]
  if (preferred) {
    selectedDevice.value = deviceOptions.value.find(option => option.udid === preferred.udid) || null
    await selectDevice(preferred).catch(() => {})
  }
  statusTimer = setInterval(refreshStatus, 5000)
  deviceTimer = setInterval(loadDevices, 30000)
}

async function handleDeviceChange(value: any) {
  if (!value?.udid) return
  const device = physicalDevices.value.find(item => item.udid === value.udid)
  if (device?.available) await selectDevice(device).catch(() => {})
}

async function handleRun(action: string) {
  showTab('run')
  await runAction(action, buildConfiguration.value)
  await nextTick()
  if (eventPane.value) eventPane.value.scrollTop = eventPane.value.scrollHeight
}

async function copyError() {
  if (!firstError.value) return
  await navigator.clipboard.writeText(
    [firstError.value, ...callStack.value].join('\n')
  )
  copied.value = true
  setTimeout(() => { copied.value = false }, 1600)
}

function eventClass(event: DebugEvent) {
  return `event-row event-${event.kind}`
}

function showTab(key: TabKey) {
  const index = tabs.findIndex(tab => tab.key === key)
  activeTabIndex.value = index >= 0 ? index : 0
}

function handleShortcut(event: KeyboardEvent) {
  if (!(event.metaKey || event.ctrlKey)) return
  const key = event.key.toLowerCase()
  if (key === 'enter') {
    event.preventDefault()
    handleRun('all')
  } else if (key === 'b') {
    event.preventDefault()
    handleRun('build')
  } else if (key === 'f') {
    event.preventDefault()
    showTab('run')
    nextTick(() => document.querySelector<HTMLInputElement>('#event-filter')?.focus())
  } else if (key === 'k') {
    event.preventDefault()
    clearEvents()
  } else if (key === '.') {
    event.preventDefault()
    stopJob()
  }
}

onMounted(() => {
  initialize()
  window.addEventListener('keydown', handleShortcut)
})

onBeforeUnmount(() => {
  if (statusTimer) clearInterval(statusTimer)
  if (deviceTimer) clearInterval(deviceTimer)
  window.removeEventListener('keydown', handleShortcut)
})
</script>

<template>
  <UApp>
    <div class="debug-shell">
      <header class="topbar">
        <div class="brand">
          <div class="brand-mark">
            <AppLogo />
          </div>
          <div>
            <div class="brand-title">App Debug</div>
            <div class="brand-subtitle">LOCAL DEBUG WORKSPACE</div>
          </div>
        </div>

        <div class="platform-switch" aria-label="调试平台">
          <UButton
            :color="platform === 'ios' ? 'primary' : 'gray'"
            :variant="platform === 'ios' ? 'solid' : 'ghost'"
            @click="platform = 'ios'"
          >
            <IosMark class="platform-icon" />
            iOS
          </UButton>
          <UButton
            :color="platform === 'android' ? 'primary' : 'gray'"
            :variant="platform === 'android' ? 'solid' : 'ghost'"
            @click="platform = 'android'"
          >
            <AndroidMark class="platform-icon" />
            Android
            <UBadge color="gray" variant="subtle" size="xs">Soon</UBadge>
          </UButton>
        </div>

        <div class="context-bar">
          <UButton color="gray" variant="soft" icon="i-heroicons-cube">
            BloomchicStore
          </UButton>
          <UBadge :color="buildConfiguration === 'Debug' ? 'amber' : 'green'" variant="subtle">
            {{ buildConfiguration }}
          </UBadge>
        </div>

        <div class="top-spacer" />
        <UButton
          color="gray"
          variant="ghost"
          icon="i-heroicons-wrench-screwdriver"
          :disabled="busy"
          @click="handleRun('doctor')"
        >
          环境检查
        </UButton>
        <UButton
          color="gray"
          variant="ghost"
          icon="i-heroicons-trash"
          @click="clearEvents"
        >
          清空
        </UButton>
      </header>

      <div class="workspace">
        <aside class="sidebar">
          <div class="sidebar-label">运行配置</div>

          <div class="field-group">
            <label class="field-label">目标设备</label>
            <USelectMenu
              v-model="selectedDevice"
              :options="deviceOptions"
              option-attribute="label"
              placeholder="选择已连接设备"
              icon="i-heroicons-device-phone-mobile"
              searchable
              searchable-placeholder="搜索设备"
              class="w-full"
              @update:model-value="handleDeviceChange"
            />
            <div class="field-hint">
              <span class="mini-dot" :class="{ online: connectedDevice?.available }" />
              {{ connectedDevice?.name || '未检测到 iOS 真机' }}
            </div>
          </div>

          <div class="field-group">
            <label class="field-label">构建配置</label>
            <USelectMenu
              v-model="buildConfiguration"
              :options="configurationOptions"
              icon="i-heroicons-adjustments-horizontal"
              class="w-full"
            />
          </div>

          <UCard
            class="run-card"
            :ui="{ body: { padding: 'p-0 sm:p-0' } }"
          >
            <div class="run-card-head">
              <div>
                <div class="run-card-title">当前任务</div>
                <div class="run-card-meta">{{ runLabel }}</div>
              </div>
              <span :class="runDotClass" />
            </div>

            <UButton
              block
              size="md"
              icon="i-heroicons-play-solid"
              :loading="busy"
              @click="handleRun('all')"
            >
              构建并启动
            </UButton>

            <div class="action-grid">
              <UButton
                color="gray"
                variant="soft"
                icon="i-heroicons-hammer"
                :disabled="busy"
                @click="handleRun('build')"
              >
                构建
              </UButton>
              <UButton
                color="gray"
                variant="soft"
                icon="i-heroicons-arrow-down-tray"
                :disabled="busy"
                @click="handleRun('install')"
              >
                安装
              </UButton>
              <UButton
                color="gray"
                variant="soft"
                icon="i-heroicons-rocket-launch"
                :disabled="busy"
                @click="handleRun('launch')"
              >
                启动
              </UButton>
              <UButton
                color="gray"
                variant="soft"
                icon="i-heroicons-document-magnifying-glass"
                :disabled="busy"
                @click="handleRun('logs')"
              >
                拉日志
              </UButton>
            </div>
          </UCard>

          <UButton
            color="red"
            variant="ghost"
            icon="i-heroicons-stop"
            block
            :disabled="!busy"
            @click="stopJob"
          >
            停止任务
          </UButton>

          <div class="sidebar-tip">
            <UIcon name="i-heroicons-command-line" />
            <span><kbd>⌘ ↵</kbd> 构建并启动</span>
          </div>
        </aside>

        <main class="main-panel">
          <div class="main-head">
            <div>
              <h1>{{ platform === 'ios' ? 'iOS 调试台' : 'Android 调试台' }}</h1>
              <p>{{ platform === 'ios' ? '构建、安装、启动和错误定位在一个工作流里完成。' : 'Android 适配入口已预留，后续接入 adb、Gradle 和 logcat。' }}</p>
            </div>
            <div class="top-spacer" />
            <UBadge :color="sdk?.includes('26.') ? 'green' : 'gray'" variant="subtle">
              {{ sdk || 'SDK 未发现' }}
            </UBadge>
            <UBadge :color="connectedDevice?.available ? 'green' : 'red'" variant="subtle">
              {{ connectedDevice?.name || '设备未连接' }}
            </UBadge>
          </div>

          <div v-if="platform === 'ios'" class="main-content">
            <UTabs
              v-model="activeTabIndex"
              :items="tabs"
              :content="false"
              class="debug-tabs"
            />

            <section v-if="activeTab === 'run'" class="pane">
              <div class="pane-toolbar">
                <div class="run-status">
                  <span :class="runDotClass" />
                  <span>{{ runLabel }}</span>
                  <span v-if="busy" class="elapsed">{{ elapsed }}s</span>
                </div>
                <div class="toolbar-spacer" />
                <UInput
                  id="event-filter"
                  v-model="eventQuery"
                  icon="i-heroicons-magnifying-glass"
                  placeholder="实时过滤日志"
                  class="event-filter"
                />
                <UButton
                  color="gray"
                  variant="ghost"
                  icon="i-heroicons-arrow-path"
                  :loading="busy"
                  @click="handleRun('log')"
                >
                  启动并跟随
                </UButton>
              </div>

              <div class="filter-row">
                <UButton
                  v-for="item in severityOptions"
                  :key="item.key"
                  :color="severity === item.key ? 'primary' : 'gray'"
                  :variant="severity === item.key ? 'soft' : 'ghost'"
                  size="xs"
                  @click="severity = item.key"
                >
                  {{ item.label }}
                  <span v-if="item.key === 'error' && errors.length" class="filter-count">{{ errors.length }}</span>
                  <span v-else-if="item.key === 'warning' && warnings.length" class="filter-count">{{ warnings.length }}</span>
                </UButton>
                <div class="toolbar-spacer" />
                <span class="event-summary">
                  {{ filteredEvents.length }} / {{ events.length }} 条
                </span>
              </div>

              <div ref="eventPane" class="event-console">
                <div v-if="!events.length" class="empty-state">
                  <UIcon name="i-heroicons-command-line" class="empty-icon" />
                  <div>还没有运行记录</div>
                  <p>点击「构建并启动」，日志会实时出现在这里。</p>
                </div>
                <div v-else-if="!filteredEvents.length" class="empty-state compact">
                  没有符合当前过滤条件的事件
                </div>
                <div
                  v-for="event in filteredEvents"
                  :key="event.id"
                  :class="eventClass(event)"
                >
                  <span class="event-time">{{ event.time }}</span>
                  <UIcon
                    :name="event.kind === 'error'
                      ? 'i-heroicons-x-circle'
                      : event.kind === 'warning'
                        ? 'i-heroicons-exclamation-triangle'
                        : event.kind === 'success'
                          ? 'i-heroicons-check-circle'
                          : event.kind === 'command'
                            ? 'i-heroicons-chevron-right'
                            : 'i-heroicons-minus'"
                    class="event-icon"
                  />
                  <span class="event-text">{{ event.text }}</span>
                </div>
              </div>
            </section>

            <section v-else-if="activeTab === 'issues'" class="pane">
              <div v-if="errors.length" class="issues-layout">
                <UAlert
                  color="red"
                  variant="soft"
                  icon="i-heroicons-exclamation-circle"
                  title="本次运行发现错误"
                  :description="firstError"
                >
                  <template #trailing>
                    <UButton
                      size="xs"
                      color="red"
                      variant="soft"
                      :icon="copied ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                      @click="copyError"
                    >
                      {{ copied ? '已复制' : '复制' }}
                    </UButton>
                  </template>
                </UAlert>

                <div class="issue-grid">
                  <UCard>
                    <template #header>
                      <div class="card-heading">
                        <span>错误事件</span>
                        <UBadge color="red" variant="subtle">{{ errors.length }}</UBadge>
                      </div>
                    </template>
                    <div class="issue-lines">
                      <div v-for="event in errors" :key="event.id" class="issue-line">
                        <span>{{ event.time }}</span>
                        <pre>{{ event.text }}</pre>
                      </div>
                    </div>
                  </UCard>

                  <UCard>
                    <template #header>
                      <div class="card-heading">
                        <span>源码位置</span>
                        <UBadge color="gray" variant="subtle">{{ callStack.length }}</UBadge>
                      </div>
                    </template>
                    <div v-if="callStack.length" class="stack-list">
                      <div
                        v-for="(frame, index) in callStack"
                        :key="frame"
                        class="stack-row"
                      >
                        <span>{{ index + 1 }}</span>
                        <code>{{ frame }}</code>
                      </div>
                    </div>
                    <div v-else class="small-empty">
                      本次错误没有解析到文件行号，可切换到日志 Tab 查看完整上下文。
                    </div>
                  </UCard>
                </div>

                <UCard>
                  <template #header>
                    <div class="card-heading">
                      <span>最近上下文</span>
                      <span class="muted">最后 80 条</span>
                    </div>
                  </template>
                  <div class="context-log">
                    <div v-for="event in latestEvents" :key="event.id">
                      <span>{{ event.time }}</span>
                      <code>{{ event.text }}</code>
                    </div>
                  </div>
                </UCard>
              </div>
              <div v-else class="empty-state panel-empty">
                <UIcon name="i-heroicons-shield-check" class="empty-icon success" />
                <div>当前运行没有错误</div>
                <p>{{ jobDone ? '构建和启动日志中尚未发现错误。' : '运行结束后这里会显示错误与源码位置。' }}</p>
              </div>
            </section>

            <section v-else class="pane">
              <div class="log-search">
                <UInput
                  v-model="logQuery"
                  icon="i-heroicons-magnifying-glass"
                  placeholder="搜索 decoded.log，例如 HttpLogging / error / request-id"
                  class="flex-1"
                  @keydown.enter="searchLogs(logQuery, logRegex)"
                />
                <UCheckbox v-model="logRegex" label="正则" />
                <UButton
                  icon="i-heroicons-magnifying-glass"
                  @click="searchLogs(logQuery, logRegex)"
                >
                  搜索
                </UButton>
              </div>
              <div class="log-result">
                <div v-if="!logs.length" class="empty-state compact">
                  {{ logMeta }}
                </div>
                <div v-for="line in logs" :key="line.n" class="log-line">
                  <span>{{ line.n }}</span>
                  <code>{{ line.text }}</code>
                </div>
              </div>
              <div class="log-meta">{{ logMeta }}</div>
            </section>
          </div>

          <div v-else class="platform-empty">
            <AndroidMark class="platform-empty-icon" />
            <h2>Android 适配入口</h2>
            <p>当前工作台保留了平台切换和统一事件流。后续接入 Gradle、adb、logcat 后即可复用运行、错误和日志视图。</p>
            <UButton
              color="gray"
              variant="soft"
              icon="i-heroicons-arrow-left"
              @click="platform = 'ios'"
            >
              返回 iOS
            </UButton>
          </div>
        </main>
      </div>

      <footer class="statusbar">
        <span>{{ activeJob?.id || 'No active job' }}</span>
        <span>{{ events.length }} events</span>
        <span>Local only · 127.0.0.1</span>
        <span class="toolbar-spacer" />
        <span>App Debug 0.3</span>
      </footer>
    </div>
  </UApp>
</template>
