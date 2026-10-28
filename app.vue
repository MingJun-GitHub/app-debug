<script setup lang="ts">
import { redactSensitive } from '~/composables/redaction'
import { ALL_LOG_FILTER, type LogFilter } from '~/types/log-filter'
import type { HighlightPattern } from '~/utils/log-highlight'

type PlatformKey = 'ios' | 'android'
type TabKey = 'run' | 'issues' | 'logs' | 'device' | 'links' | 'sessions'
type SeverityFilter = 'all' | 'error' | 'warning' | 'network'

const runners = {
  ios: useDebugRunner('ios'),
  android: useDebugRunner('android')
}
const projectSettings = useProjectSettings()

const platform = ref<PlatformKey>('ios')
const activeTabIndexes = reactive<Record<PlatformKey, number>>({ ios: 0, android: 0 })
const selectedDevices = reactive<Record<PlatformKey, any>>({ ios: '', android: '' })
const buildConfigurations = reactive<Record<PlatformKey, string>>({ ios: 'Debug', android: 'Debug' })
const severities = reactive<Record<PlatformKey, SeverityFilter>>({ ios: 'all', android: 'all' })
const keywordQueries = reactive<Record<PlatformKey, string>>({ ios: '', android: '' })
const selectedFilters = reactive<Record<PlatformKey, LogFilter>>({
  ios: ALL_LOG_FILTER,
  android: ALL_LOG_FILTER
})
const refreshingDevices = reactive<Record<PlatformKey, boolean>>({ ios: false, android: false })
const copiedTarget = ref('')
const stopConfirmOpen = ref(false)
const stopping = ref(false)
const settingsOpen = ref(false)
const screenshotPreviewOpen = ref(false)
const sourceViewerOpen = ref(false)
const sourceViewerPath = ref('')
const sourceViewerLine = ref(1)
let statusTimer: ReturnType<typeof setInterval> | undefined
let deviceTimer: ReturnType<typeof setInterval> | undefined
let copyTimer: ReturnType<typeof setTimeout> | undefined

const runner = computed(() => runners[platform.value])
const status = computed(() => runner.value.status.value)
const physicalDevices = computed(() => runner.value.physicalDevices.value)
const connectedDevice = computed(() => runner.value.connectedDevice.value)
const deviceContext = computed(() => runner.value.deviceContext.value)
const deviceContextLoading = computed(() => runner.value.deviceContextLoading.value)
const deviceContextError = computed(() => runner.value.deviceContextError.value)
const screenshotUrl = computed(() => runner.value.screenshotUrl.value)
const screenshotLoading = computed(() => runner.value.screenshotLoading.value)
const screenshotError = computed(() => runner.value.screenshotError.value)
const activeDeviceAvailable = computed(() =>
  Boolean(
    connectedDevice.value?.available
    || deviceContext.value?.device.connected
    || physicalDevices.value.some(device => device.available)
  )
)
const screenshotDeviceName = computed(() =>
  connectedDevice.value?.name
  || deviceContext.value?.device.name
  || physicalDevices.value.find(device => device.available)?.name
)
const sdk = computed(() => runner.value.sdk.value)
const events = computed(() => runner.value.events.value)
const errors = computed(() => runner.value.errors.value)
const warnings = computed(() => runner.value.warnings.value)
const callStack = computed(() => runner.value.callStack.value)
const logs = computed(() => runner.value.logs.value)
const logMeta = computed(() => runner.value.logMeta.value)
const activeJob = computed(() => runner.value.activeJob.value)
const currentSessionId = computed(() => runner.value.currentSessionId.value)
const jobDone = computed(() => runner.value.jobDone.value)
const jobResult = computed(() => runner.value.jobResult.value)
const elapsed = computed(() => runner.value.elapsed.value)
const busy = computed(() => runner.value.busy.value)
const projectConnection = computed(() =>
  projectSettings.settings.value?.projects[platform.value] || null
)
const projectBranch = computed(() => projectConnection.value?.git.branch || '')

const selectedDevice = computed({
  get: () => selectedDevices[platform.value],
  set: (value) => { selectedDevices[platform.value] = value }
})

const buildConfiguration = computed({
  get: () => buildConfigurations[platform.value],
  set: (value) => { buildConfigurations[platform.value] = value }
})

const severity = computed({
  get: () => severities[platform.value],
  set: (value) => { severities[platform.value] = value }
})

const selectedFilter = computed({
  get: () => selectedFilters[platform.value],
  set: (value) => { selectedFilters[platform.value] = value }
})

const keywordQuery = computed({
  get: () => keywordQueries[platform.value],
  set: (value) => { keywordQueries[platform.value] = value }
})

const tabs = [
  { key: 'run', label: '运行', icon: 'i-heroicons-play' },
  { key: 'issues', label: '问题', icon: 'i-heroicons-exclamation-triangle' },
  { key: 'logs', label: '日志', icon: 'i-heroicons-document-text' },
  { key: 'device', label: '设备', icon: 'i-heroicons-device-phone-mobile' },
  { key: 'links', label: '页面', icon: 'i-heroicons-arrow-top-right-on-square' },
  { key: 'sessions', label: '会话', icon: 'i-heroicons-clipboard-document-check' }
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
const deviceAlert = computed(() => {
  const device = connectedDevice.value
  if (!device) {
    return {
      color: 'amber' as const,
      icon: 'i-heroicons-device-phone-mobile',
      title: `未检测到 ${platformName.value} 设备`,
      description: '连接设备并完成授权后，点击“重新检测设备”。'
    }
  }
  if (!device.available) {
    return {
      color: 'red' as const,
      icon: 'i-heroicons-exclamation-triangle',
      title: `${device.name || platformName.value + ' 设备'} 当前不可用`,
      description: device.error || '检查连接、解锁和设备授权状态后重新检测。'
    }
  }
  return null
})

const logHighlightPatterns = computed<HighlightPattern[]>(() => {
  const patterns: HighlightPattern[] = []
  const filterQuery = selectedFilter.value.query.trim()
  const keyword = keywordQuery.value.trim()
  if (filterQuery) {
    patterns.push({ value: filterQuery, regex: selectedFilter.value.regex })
  }
  if (keyword) {
    patterns.push({ value: keyword, regex: false })
  }
  return patterns
})

const filteredEvents = computed(() => {
  const filter = selectedFilter.value
  let queryPattern: RegExp | null = null
  if (filter.query) {
    if (filter.regex) {
      try {
        queryPattern = new RegExp(filter.query, 'i')
      } catch {
        queryPattern = null
      }
    }
  }
  return events.value.filter((event) => {
    const matchesQuery = !filter.query
      || (queryPattern
        ? queryPattern.test(event.text)
        : event.text.toLowerCase().includes(filter.query.toLowerCase()))
    if (!matchesQuery) return false
    const keyword = keywordQuery.value.trim()
    if (keyword && !event.text.toLowerCase().includes(keyword.toLowerCase())) return false
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

const hasActiveJobs = computed(() =>
  Object.values(runners).some(current => current.busy.value)
)

const firstError = computed(() => errors.value.at(-1)?.text || '')
const latestEvents = computed(() => events.value.slice(-80))
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

async function loadCurrentDeviceContext(refresh = false) {
  await runner.value.loadDeviceContext(buildConfiguration.value, refresh)
}

async function openScreenshotPreview() {
  if (!activeDeviceAvailable.value) return
  screenshotPreviewOpen.value = true
  if (!screenshotUrl.value) await runner.value.captureScreenshot()
}

async function refreshScreenshot() {
  if (!activeDeviceAvailable.value) return
  await runner.value.captureScreenshot()
}

async function refreshAllStatus() {
  await Promise.all(Object.values(runners).map(current => current.refreshStatus()))
}

async function loadAllDevices() {
  await Promise.all(Object.values(runners).map(current => current.loadDevices()))
}

async function handleSettingsUpdated() {
  await projectSettings.refresh()
  for (const current of Object.values(runners)) {
    current.deviceContext.value = null
  }
  await Promise.all(Object.values(runners).flatMap(current => [
    current.refreshStatus(),
    current.loadDevices()
  ]))
}

async function initialize() {
  await Promise.all([
    initializePlatform('ios'),
    initializePlatform('android'),
    projectSettings.refresh()
  ])
  statusTimer = setInterval(refreshAllStatus, 5000)
  deviceTimer = setInterval(loadAllDevices, 30000)
}

async function handleDeviceChange(value: any) {
  if (!value?.udid) return
  const device = physicalDevices.value.find(item => item.udid === value.udid)
  if (device?.available) {
    await runner.value.selectDevice(device).catch(() => {})
    if (activeTab.value === 'device') await loadCurrentDeviceContext(true)
  }
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
      if (activeTab.value === 'device') await loadCurrentDeviceContext(true)
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
}

async function copyText(target: string, text: string) {
  if (!text.trim()) return
  const safeText = redactSensitive(text)
  try {
    await navigator.clipboard.writeText(safeText)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = safeText
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copiedTarget.value = target
  if (copyTimer) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => {
    if (copiedTarget.value === target) copiedTarget.value = ''
  }, 1600)
}

function showTab(key: TabKey) {
  const index = tabs.findIndex(tab => tab.key === key)
  activeTabIndexes[platform.value] = index >= 0 ? index : 0
}

function openSourceLocation(location: string) {
  const match = location.match(/^(.*):(\d+)$/)
  sourceViewerPath.value = match?.[1] || location
  sourceViewerLine.value = Number(match?.[2] || 1)
  sourceViewerOpen.value = true
}

function clearCurrentEvents() {
  runner.value.clearEvents()
}

function requestStop() {
  if (!busy.value) return
  stopConfirmOpen.value = true
}

async function confirmStop() {
  if (!busy.value || stopping.value) return
  stopping.value = true
  try {
    await runner.value.stopJob()
    stopConfirmOpen.value = false
  } finally {
    stopping.value = false
  }
}

function stopActiveJobsOnUnload() {
  for (const key of ['ios', 'android'] as PlatformKey[]) {
    const job = runners[key].activeJob.value
    if (!job) continue
    const payload = JSON.stringify({ jobId: job.id })
    const sent = navigator.sendBeacon(
      `/api/${key}/stop`,
      new Blob([payload], { type: 'application/json' })
    )
    if (!sent) {
      fetch(`/api/${key}/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true
      }).catch(() => {})
    }
  }
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasActiveJobs.value) return
  event.preventDefault()
  event.returnValue = ''
}

function handlePageHide(event: PageTransitionEvent) {
  if (event.persisted || !hasActiveJobs.value) return
  stopActiveJobsOnUnload()
}

function searchCurrentLogs() {
  const primary = selectedFilter.value.query.trim()
  const keyword = keywordQuery.value.trim()
  if (!primary && !keyword) return
  if (!keyword) {
    runner.value.searchLogs(primary, selectedFilter.value.regex)
    return
  }

  const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const primaryPattern = primary
    ? `(?=.*${selectedFilter.value.regex ? `(?:${primary})` : escapeRegex(primary)})`
    : ''
  runner.value.searchLogs(
    `${primaryPattern}(?=.*${escapeRegex(keyword)})`,
    true
  )
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
    nextTick(() => document.querySelector<HTMLInputElement>('#event-keyword-filter')?.focus())
  } else if (key === 's' && event.shiftKey) {
    event.preventDefault()
    openScreenshotPreview()
  } else if (key === 'k') {
    event.preventDefault()
    clearCurrentEvents()
  } else if (key === '.') {
    event.preventDefault()
    requestStop()
  }
}

watch(activeTab, (tab) => {
  if (tab === 'device') loadCurrentDeviceContext()
})

watch(platform, () => {
  screenshotPreviewOpen.value = false
  if (activeTab.value === 'device') loadCurrentDeviceContext()
})

watch(buildConfiguration, () => {
  if (activeTab.value === 'device') loadCurrentDeviceContext(true)
})

onMounted(() => {
  initialize()
  window.addEventListener('keydown', handleShortcut)
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('pagehide', handlePageHide)
})

onBeforeUnmount(() => {
  if (statusTimer) clearInterval(statusTimer)
  if (deviceTimer) clearInterval(deviceTimer)
  if (copyTimer) clearTimeout(copyTimer)
  Object.values(runners).forEach(current => current.clearScreenshot())
  window.removeEventListener('keydown', handleShortcut)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('pagehide', handlePageHide)
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
          <UButton
            color="gray"
            variant="ghost"
            icon="i-heroicons-cube"
            title="关联本地项目"
            @click="settingsOpen = true"
          >
            <span>{{ projectName }}</span>
            <span v-if="projectBranch" class="project-branch">
              <UIcon name="i-heroicons-code-bracket-square" />
              {{ projectBranch }}
            </span>
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
              variant="link"
              icon="i-heroicons-arrow-path"
              size="sm"
              class="device-refresh-link"
              :loading="refreshingDevices[platform]"
              @click="refreshCurrentDevices"
            >
              重新检测设备
            </UButton>
            <UAlert
              v-if="deviceAlert"
              :color="deviceAlert.color"
              variant="soft"
              :icon="deviceAlert.icon"
              :title="deviceAlert.title"
              :description="deviceAlert.description"
              class="device-alert"
            />
            <div v-else class="field-hint">
              <span class="mini-dot online" />
              {{ connectedDevice?.name }}
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
              :disabled="busy || !activeDeviceAvailable"
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
                :disabled="busy || !activeDeviceAvailable"
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
                :disabled="busy || !activeDeviceAvailable"
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
                :disabled="busy || !activeDeviceAvailable"
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
                :disabled="busy || !activeDeviceAvailable"
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
            @click="requestStop"
          >
            停止任务
            <kbd class="shortcut-key">⌘.</kbd>
          </UButton>

          <div class="sidebar-tip">
            <UIcon name="i-heroicons-command-line" />
            <span>
              <kbd>⌘F</kbd> 过滤 · <kbd>⌘.</kbd> 停止<br>
              <span class="sidebar-tip-note">刷新或关闭页面会自动停止任务</span>
            </span>
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

            <DebugRunPane
              v-if="activeTab === 'run'"
              :platform-name="platformName"
              :run-dot-class="runDotClass"
              :run-label="runLabel"
              :busy="busy"
              :elapsed="elapsed"
              :events="events"
              :filtered-events="filteredEvents"
              :severity="severity"
              :severity-options="severityOptions"
              :error-count="errors.length"
              :warning-count="warnings.length"
              :selected-filter="selectedFilter"
              :keyword-query="keywordQuery"
              :active-device-available="activeDeviceAvailable"
              :copied-target="copiedTarget"
              :highlight-patterns="logHighlightPatterns"
              @update:severity="severity = $event"
              @update:selected-filter="selectedFilter = $event"
              @update:keyword-query="keywordQuery = $event"
              @run="handleRun"
              @copy="copyText"
            />

            <DebugIssuesPane
              v-else-if="activeTab === 'issues'"
              :errors="errors"
              :call-stack="callStack"
              :first-error="firstError"
              :latest-events="latestEvents"
              :job-done="jobDone"
              :copied-target="copiedTarget"
              @copy="copyText"
              @view-source="openSourceLocation"
            />

            <DebugLogsPane
              v-else-if="activeTab === 'logs'"
              :platform-name="platformName"
              :selected-filter="selectedFilter"
              :keyword-query="keywordQuery"
              :logs="logs"
              :log-meta="logMeta"
              :copied-target="copiedTarget"
              :highlight-patterns="logHighlightPatterns"
              @update:selected-filter="selectedFilter = $event"
              @update:keyword-query="keywordQuery = $event"
              @search="searchCurrentLogs"
              @copy="copyText"
            />

            <PageLinkPanel
              v-else-if="activeTab === 'links'"
              :platform="platform"
              :device-name="connectedDevice?.name"
              :device-available="Boolean(connectedDevice?.available)"
            />

            <DebugSessionPanel
              v-else-if="activeTab === 'sessions'"
              :key="platform"
              :platform="platform"
              :current-session-id="currentSessionId"
              :device-context="deviceContext"
              :device-available="activeDeviceAvailable"
              :busy="busy"
              @run="handleRun"
              @view-source="openSourceLocation"
            />

            <DeviceContextPanel
              v-else
              :platform="platform"
              :context="deviceContext"
              :loading="deviceContextLoading"
              :error="deviceContextError"
              :device-available="activeDeviceAvailable"
              @refresh="loadCurrentDeviceContext(true)"
              @screenshot="openScreenshotPreview"
            />
          </div>
        </main>
      </div>

      <footer class="statusbar">
        <span>{{ activeJob?.id || 'No active job' }}</span>
        <span>{{ events.length }} events</span>
        <span>Local only · 127.0.0.1</span>
        <span class="toolbar-spacer" />
        <span>App Debug 0.4</span>
      </footer>

      <UModal v-model="stopConfirmOpen">
        <UCard>
          <template #header>
            <div class="confirm-dialog-header">
              <div class="confirm-dialog-icon bg-amber-50 text-amber-500 dark:bg-amber-950 dark:text-amber-400">
                <UIcon name="i-heroicons-exclamation-triangle" />
              </div>
              <div>
                <h2>确认停止当前任务？</h2>
                <p>{{ platformName }} · {{ activeJob?.action || '正在运行' }}</p>
              </div>
            </div>
          </template>
          <p class="confirm-dialog-copy">
            停止后会终止构建、安装或日志相关进程。未完成的输出会保留在当前页面。
          </p>
          <template #footer>
            <div class="confirm-dialog-footer">
              <UButton color="gray" variant="ghost" @click="stopConfirmOpen = false">
                继续运行
              </UButton>
              <UButton
                color="red"
                icon="i-heroicons-stop"
                :loading="stopping"
                @click="confirmStop"
              >
                停止任务
              </UButton>
            </div>
          </template>
        </UCard>
      </UModal>

      <DeviceScreenshotEditor
        v-model="screenshotPreviewOpen"
        :platform="platform"
        :device-name="screenshotDeviceName"
        :image-url="screenshotUrl"
        :loading="screenshotLoading"
        :error="screenshotError"
        @refresh="refreshScreenshot"
      />

      <ProjectSettingsModal
        v-model="settingsOpen"
        @updated="handleSettingsUpdated"
      />

      <SourceViewerModal
        v-model="sourceViewerOpen"
        :platform="platform"
        :path="sourceViewerPath"
        :line="sourceViewerLine"
      />
    </div>
  </UApp>
</template>
