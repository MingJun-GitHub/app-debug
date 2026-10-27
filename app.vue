<script setup lang="ts">
import type { DebugEvent } from '~/composables/useDebugRunner'

type PlatformKey = 'ios' | 'android'
type TabKey = 'run' | 'issues' | 'logs'
type SeverityFilter = 'all' | 'error' | 'warning' | 'network'

const runners = {
  ios: useDebugRunner('ios'),
  android: useDebugRunner('android')
}

const platform = ref<PlatformKey>('ios')
const activeTabIndexes = reactive<Record<PlatformKey, number>>({ ios: 0, android: 0 })
const selectedDevices = reactive<Record<PlatformKey, any>>({ ios: '', android: '' })
const buildConfigurations = reactive<Record<PlatformKey, string>>({ ios: 'Debug', android: 'Debug' })
const eventQueries = reactive<Record<PlatformKey, string>>({ ios: '', android: '' })
const severities = reactive<Record<PlatformKey, SeverityFilter>>({ ios: 'all', android: 'all' })
const logQueries = reactive<Record<PlatformKey, string>>({ ios: '', android: '' })
const logRegex = reactive<Record<PlatformKey, boolean>>({ ios: false, android: false })
const refreshingDevices = reactive<Record<PlatformKey, boolean>>({ ios: false, android: false })
const copied = ref(false)
const eventPane = ref<HTMLElement | null>(null)
let statusTimer: ReturnType<typeof setInterval> | undefined
let deviceTimer: ReturnType<typeof setInterval> | undefined

const runner = computed(() => runners[platform.value])
const status = computed(() => runner.value.status.value)
const physicalDevices = computed(() => runner.value.physicalDevices.value)
const connectedDevice = computed(() => runner.value.connectedDevice.value)
const sdk = computed(() => runner.value.sdk.value)
const events = computed(() => runner.value.events.value)
const errors = computed(() => runner.value.errors.value)
const warnings = computed(() => runner.value.warnings.value)
const callStack = computed(() => runner.value.callStack.value)
const logs = computed(() => runner.value.logs.value)
const logMeta = computed(() => runner.value.logMeta.value)
const activeJob = computed(() => runner.value.activeJob.value)
const jobDone = computed(() => runner.value.jobDone.value)
const jobResult = computed(() => runner.value.jobResult.value)
const elapsed = computed(() => runner.value.elapsed.value)
const busy = computed(() => runner.value.busy.value)

const selectedDevice = computed({
  get: () => selectedDevices[platform.value],
  set: (value) => { selectedDevices[platform.value] = value }
})

const buildConfiguration = computed({
  get: () => buildConfigurations[platform.value],
  set: (value) => { buildConfigurations[platform.value] = value }
})

const eventQuery = computed({
  get: () => eventQueries[platform.value],
  set: (value) => { eventQueries[platform.value] = value }
})

const severity = computed({
  get: () => severities[platform.value],
  set: (value) => { severities[platform.value] = value }
})

const logQuery = computed({
  get: () => logQueries[platform.value],
  set: (value) => { logQueries[platform.value] = value }
})

const currentLogRegex = computed({
  get: () => logRegex[platform.value],
  set: (value) => { logRegex[platform.value] = value }
})

const tabs = [
  { key: 'run', label: '运行', icon: 'i-heroicons-play' },
  { key: 'issues', label: '问题', icon: 'i-heroicons-exclamation-triangle' },
  { key: 'logs', label: '日志', icon: 'i-heroicons-document-text' }
]

const platformTabs = [
  { key: 'ios', label: 'iOS' },
  { key: 'android', label: 'Android' }
]

const platformTabsUi = {
  wrapper: 'space-y-0',
  list: {
    base: 'relative',
    rounded: 'rounded-[10px]',
    padding: 'p-[3px]',
    height: 'h-[38px]',
    width: 'w-[235px]',
    marker: {
      wrapper: 'absolute top-[3px] left-[3px] duration-200 ease-out',
      base: 'rounded-[7px] shadow-[0_2px_8px_rgba(0,0,0,0.35)]',
      background: 'bg-primary-500 dark:bg-primary-500'
    },
    tab: {
      base: 'relative z-10 font-semibold',
      height: 'h-[30px]',
      active: 'text-white',
      inactive: 'text-slate-400 hover:text-slate-200'
    }
  }
}

const debugTabsUi = {
  wrapper: 'space-y-0',
  list: {
    base: 'relative',
    rounded: 'rounded-lg',
    padding: 'p-[3px]',
    height: 'h-[40px]',
    marker: {
      wrapper: 'absolute top-[3px] left-[3px] duration-200 ease-out',
      base: 'rounded-md shadow-sm',
      background: 'bg-primary-500 dark:bg-primary-500'
    },
    tab: {
      base: 'relative z-10',
      height: 'h-[34px]',
      active: 'text-white',
      inactive: 'text-slate-400 hover:text-slate-200'
    }
  }
}

const platformIndex = computed({
  get: () => platformTabs.findIndex(tab => tab.key === platform.value),
  set: (index) => {
    const next = platformTabs[index]?.key as PlatformKey | undefined
    if (next) platform.value = next
  }
})

const activeTabIndex = computed({
  get: () => activeTabIndexes[platform.value],
  set: (value) => { activeTabIndexes[platform.value] = value }
})

const activeTab = computed<TabKey>(() => (tabs[activeTabIndex.value]?.key as TabKey) || 'run')

function deviceOptionsFor(key: PlatformKey) {
  return runners[key].physicalDevices.value.map(device => ({
    label: `${device.name} · ${key === 'ios' ? 'iOS' : 'Android'} ${device.os || '?'}`,
    icon: key === 'ios' ? 'i-heroicons-device-phone-mobile' : 'i-heroicons-device-tablet',
    udid: device.udid,
    name: device.name,
    disabled: !device.available
  }))
}

const deviceOptions = computed(() => physicalDevices.value.map(device => ({
  label: `${device.name} · ${platform.value === 'ios' ? 'iOS' : 'Android'} ${device.os || '?'}`,
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
const platformName = computed(() => platform.value === 'ios' ? 'iOS' : 'Android')
const projectName = computed(() => status.value?.projectName || (platform.value === 'ios' ? 'BloomchicStore' : 'Bloomchic Android'))

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
const logEmptyTitle = computed(() => {
  if (logMeta.value === '尚未搜索') return '尚未搜索日志'
  if (/不存在|失败|错误|not found/i.test(logMeta.value)) return '日志暂不可用'
  return '没有匹配的日志'
})
const logEmptyDescription = computed(() => {
  if (logMeta.value === '尚未搜索') {
    return `输入关键字后搜索 ${platformName.value} decoded.log。`
  }
  if (/不存在|失败|错误|not found/i.test(logMeta.value)) return logMeta.value
  return '调整关键字或正则条件后重试。'
})

async function initializePlatform(key: PlatformKey) {
  const current = runners[key]
  await current.refreshStatus()
  await current.loadDevices()
  const preferred = current.connectedDevice.value
    || current.physicalDevices.value.find(device => device.available)
    || current.physicalDevices.value[0]
  if (preferred) {
    selectedDevices[key] = deviceOptionsFor(key).find(option => option.udid === preferred.udid) || null
    await current.selectDevice(preferred).catch(() => {})
  }
}

async function refreshAllStatus() {
  await Promise.all(Object.values(runners).map(current => current.refreshStatus()))
}

async function loadAllDevices() {
  await Promise.all(Object.values(runners).map(current => current.loadDevices()))
}

async function initialize() {
  await Promise.all([initializePlatform('ios'), initializePlatform('android')])
  statusTimer = setInterval(refreshAllStatus, 5000)
  deviceTimer = setInterval(loadAllDevices, 30000)
}

async function handleDeviceChange(value: any) {
  if (!value?.udid) return
  const device = physicalDevices.value.find(item => item.udid === value.udid)
  if (device?.available) await runner.value.selectDevice(device).catch(() => {})
}

async function refreshCurrentDevices() {
  if (refreshingDevices[platform.value]) return
  refreshingDevices[platform.value] = true
  try {
    await Promise.all([
      runner.value.refreshStatus(),
      runner.value.loadDevices()
    ])
    const devices = runner.value.physicalDevices.value
    const currentUdid = selectedDevices[platform.value]?.udid
    const preferred = devices.find(device => device.udid === currentUdid)
      || devices.find(device => device.available)
    if (preferred?.available) {
      selectedDevices[platform.value] = deviceOptionsFor(platform.value)
        .find(option => option.udid === preferred.udid) || null
      await runner.value.selectDevice(preferred).catch(() => {})
    } else {
      selectedDevices[platform.value] = ''
    }
  } finally {
    refreshingDevices[platform.value] = false
  }
}

async function handleRun(action: string) {
  showTab('run')
  await runner.value.runAction(action, buildConfiguration.value)
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
  activeTabIndexes[platform.value] = index >= 0 ? index : 0
}

function clearCurrentEvents() {
  runner.value.clearEvents()
}

function stopCurrentJob() {
  runner.value.stopJob()
}

function searchCurrentLogs() {
  runner.value.searchLogs(logQueries[platform.value], logRegex[platform.value])
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
  } else if (key === 'i') {
    event.preventDefault()
    handleRun('install')
  } else if (key === 'l' && event.shiftKey) {
    event.preventDefault()
    handleRun('logs')
  } else if (key === 'l') {
    event.preventDefault()
    handleRun('launch')
  } else if (key === 'd' && event.shiftKey) {
    event.preventDefault()
    handleRun('doctor')
  } else if (key === 'd') {
    event.preventDefault()
    handleRun('log')
  } else if (key === 'f') {
    event.preventDefault()
    showTab('run')
    nextTick(() => document.querySelector<HTMLInputElement>('#event-filter')?.focus())
  } else if (key === 'k') {
    event.preventDefault()
    clearCurrentEvents()
  } else if (key === '.') {
    event.preventDefault()
    stopCurrentJob()
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

        <UTabs
          v-model="platformIndex"
          :items="platformTabs"
          :content="false"
          :ui="platformTabsUi"
          class="platform-tabs"
          aria-label="调试平台"
        >
          <template #icon="{ item }">
            <IosMark v-if="item.key === 'ios'" class="platform-icon" />
            <AndroidMark v-else class="platform-icon" />
          </template>
        </UTabs>

        <div class="context-bar">
          <UButton color="gray" variant="ghost" icon="i-heroicons-cube">
            {{ projectName }}
          </UButton>
        </div>

        <div class="top-spacer" />
        <UButton
          color="gray"
          variant="ghost"
          icon="i-heroicons-wrench-screwdriver"
          class="shortcut-top"
          :disabled="busy"
          @click="handleRun('doctor')"
        >
          环境检查
          <kbd class="shortcut-key">⌘⇧D</kbd>
        </UButton>
        <UButton
          color="gray"
          variant="ghost"
          icon="i-heroicons-trash"
          class="shortcut-top"
          @click="clearCurrentEvents"
        >
          清空
          <kbd class="shortcut-key">⌘K</kbd>
        </UButton>
      </header>

      <div class="workspace">
        <aside class="sidebar">
          <div class="sidebar-label">运行配置</div>

          <div class="field-group">
            <label class="field-label">目标设备</label>
            <div class="device-row">
              <USelectMenu
                v-model="selectedDevice"
                :options="deviceOptions"
                option-attribute="label"
                placeholder="选择已连接设备"
                :icon="platform === 'ios' ? 'i-heroicons-device-phone-mobile' : 'i-heroicons-device-tablet'"
                searchable
                searchable-placeholder="搜索设备"
                class="w-full"
                @update:model-value="handleDeviceChange"
              >
                <template #empty>
                  未检测到设备，请连接后重新检测
                </template>
                <template #option-empty="{ query }">
                  未找到“{{ query }}”
                </template>
              </USelectMenu>
            </div>
            <UButton
              color="primary"
              variant="ghost"
              icon="i-heroicons-arrow-path"
              block
              size="sm"
              :loading="refreshingDevices[platform]"
              @click="refreshCurrentDevices"
            >
              重新检测设备
            </UButton>
            <div class="field-hint">
              <span class="mini-dot" :class="{ online: connectedDevice?.available }" />
              {{ connectedDevice?.name || `未检测到 ${platformName} 设备` }}
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
              class="run-primary"
              :loading="busy"
              @click="handleRun('all')"
            >
              <span>构建并启动</span>
              <kbd class="shortcut-key">⌘↵</kbd>
            </UButton>

            <div class="action-grid">
              <UButton
                color="gray"
                variant="ghost"
                icon="i-heroicons-wrench-screwdriver"
                class="shortcut-button"
                :disabled="busy"
                @click="handleRun('build')"
              >
                <span>构建</span>
                <kbd class="shortcut-key">⌘B</kbd>
              </UButton>
              <UButton
                color="gray"
                variant="ghost"
                icon="i-heroicons-arrow-down-tray"
                class="shortcut-button"
                :disabled="busy"
                @click="handleRun('install')"
              >
                <span>安装</span>
                <kbd class="shortcut-key">⌘I</kbd>
              </UButton>
              <UButton
                color="gray"
                variant="ghost"
                icon="i-heroicons-rocket-launch"
                class="shortcut-button"
                :disabled="busy"
                @click="handleRun('launch')"
              >
                <span>启动</span>
                <kbd class="shortcut-key">⌘L</kbd>
              </UButton>
              <UButton
                color="gray"
                variant="ghost"
                icon="i-heroicons-document-magnifying-glass"
                class="shortcut-button"
                :disabled="busy"
                @click="handleRun('logs')"
              >
                <span>拉日志</span>
                <kbd class="shortcut-key">⇧⌘L</kbd>
              </UButton>
            </div>
          </UCard>

          <UButton
            color="red"
            variant="ghost"
            icon="i-heroicons-stop"
            class="stop-button"
            block
            :disabled="!busy"
            @click="stopCurrentJob"
          >
            停止任务
            <kbd class="shortcut-key">⌘.</kbd>
          </UButton>

          <div class="sidebar-tip">
            <UIcon name="i-heroicons-command-line" />
            <span><kbd>⌘F</kbd> 过滤 · <kbd>⌘.</kbd> 停止</span>
          </div>
        </aside>

        <main class="main-panel">
          <div class="main-head">
            <div>
              <h1>{{ platformName }} 调试台</h1>
              <p>构建、安装、启动、日志和错误定位在一个独立工作流里完成。</p>
            </div>
            <div class="top-spacer" />
            <UBadge :color="sdk ? 'green' : 'gray'" variant="subtle">
              {{ sdk || 'SDK 未发现' }}
            </UBadge>
            <UBadge :color="connectedDevice?.available ? 'green' : 'red'" variant="subtle">
              {{ connectedDevice?.name || '设备未连接' }}
            </UBadge>
          </div>

          <div class="main-content">
            <UTabs
              v-model="activeTabIndex"
              :items="tabs"
              :content="false"
              :ui="debugTabsUi"
              class="debug-tabs"
            />

            <section v-if="activeTab === 'run'" class="pane">
              <div class="pane-toolbar">
                <div class="run-status">
                  <span :class="runDotClass" />
                  <span>{{ runLabel }}</span>
                  <span v-if="busy" class="elapsed">{{ elapsed }}s</span>
                </div>
                <div class="severity-filter">
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
                </div>
                <span class="event-summary">
                  {{ filteredEvents.length }} / {{ events.length }} 条
                </span>
                <div class="toolbar-spacer" />
                <UInput
                  id="event-filter"
                  v-model="eventQuery"
                  icon="i-heroicons-magnifying-glass"
                  placeholder="实时过滤日志 · ⌘F"
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
                  <kbd class="shortcut-key">⌘D</kbd>
                </UButton>
              </div>

              <AppEmptyState
                v-if="!events.length"
                class="pane-body"
                icon="i-heroicons-command-line"
                title="还没有运行记录"
                :description="`点击「构建并启动」，${platformName} 日志会实时出现在这里。`"
              />
              <AppEmptyState
                v-else-if="!filteredEvents.length"
                class="pane-body"
                icon="i-heroicons-funnel"
                title="没有匹配记录"
                description="调整关键字或筛选条件后重试。"
              />
              <div v-else ref="eventPane" class="event-console">
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
              <div class="pane-toolbar">
                <div class="run-status">
                  <UIcon name="i-heroicons-exclamation-triangle" />
                  <span>当前问题</span>
                </div>
                <div class="toolbar-spacer" />
                <span class="event-summary">{{ errors.length }} 个错误 · {{ callStack.length }} 个源码位置</span>
              </div>
              <div v-if="errors.length" class="issues-layout pane-body">
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
              <AppEmptyState
                v-else
                class="pane-body"
                icon="i-heroicons-shield-check"
                title="当前运行没有错误"
                :description="jobDone ? '构建和启动日志中尚未发现错误。' : '运行结束后这里会显示错误与源码位置。'"
              />
            </section>

            <section v-else class="pane">
              <div class="pane-toolbar log-search">
                <UInput
                  v-model="logQuery"
                  icon="i-heroicons-magnifying-glass"
                  :placeholder="`搜索 ${platformName} decoded.log，例如 HttpLogging / error / request-id`"
                  class="flex-1"
                  @keydown.enter="searchCurrentLogs"
                />
                <UCheckbox v-model="currentLogRegex" label="正则" />
                <UButton
                  icon="i-heroicons-magnifying-glass"
                  @click="searchCurrentLogs"
                >
                  搜索
                </UButton>
              </div>
              <AppEmptyState
                v-if="!logs.length"
                class="pane-body"
                :icon="logEmptyTitle === '日志暂不可用' ? 'i-heroicons-exclamation-triangle' : 'i-heroicons-document-magnifying-glass'"
                :title="logEmptyTitle"
                :description="logEmptyDescription"
              />
              <div v-else class="log-result pane-body">
                <div v-for="line in logs" :key="line.n" class="log-line">
                  <span>{{ line.n }}</span>
                  <code>{{ line.text }}</code>
                </div>
              </div>
              <div v-if="logs.length" class="log-meta">{{ logMeta }}</div>
            </section>
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
