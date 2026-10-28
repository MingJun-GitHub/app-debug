<script setup lang="ts">
import type { DebugEvent } from '~/composables/useDebugRunner'
import { ALL_LOG_FILTER, type LogFilter } from '~/types/log-filter'

type PlatformKey = 'ios' | 'android'
type TabKey = 'run' | 'issues' | 'logs' | 'device' | 'links'
type SeverityFilter = 'all' | 'error' | 'warning' | 'network'
type HighlightPattern = { value: string, regex: boolean }
type HighlightSegment = { text: string, highlighted: boolean }

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
const experimentQueries = reactive<Record<PlatformKey, string>>({ ios: '', android: '' })
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
const eventPane = ref<HTMLElement | null>(null)
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

const experimentQuery = computed({
  get: () => experimentQueries[platform.value],
  set: (value) => { experimentQueries[platform.value] = value }
})

const tabs = [
  { key: 'run', label: '运行', icon: 'i-heroicons-play' },
  { key: 'issues', label: '问题', icon: 'i-heroicons-exclamation-triangle' },
  { key: 'logs', label: '日志', icon: 'i-heroicons-document-text' },
  { key: 'device', label: '设备', icon: 'i-heroicons-device-phone-mobile' },
  { key: 'links', label: '页面', icon: 'i-heroicons-arrow-top-right-on-square' }
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

const deviceExperimentRows = computed(() => {
  const context = deviceContext.value
  if (!context) return []
  return [
    ...context.app.experiments,
    ...context.app.outExperiments
  ]
})

const filteredDeviceExperiments = computed(() => {
  const query = experimentQuery.value.trim().toLowerCase()
  if (!query) return deviceExperimentRows.value
  return deviceExperimentRows.value.filter((experiment) =>
    experiment.key.toLowerCase().includes(query)
    || experiment.group.toLowerCase().includes(query)
    || experiment.experimentId.toLowerCase().includes(query)
  )
})

const deviceContextState = computed(() => {
  if (deviceContextLoading.value) return { label: '读取中', color: 'blue' as const }
  if (deviceContextError.value) return { label: '读取失败', color: 'red' as const }
  if (!deviceContext.value?.app.available) return { label: '仅设备信息', color: 'amber' as const }
  if (deviceContext.value.cached) return { label: '缓存', color: 'gray' as const }
  return { label: '已读取', color: 'green' as const }
})

const environmentBadge = computed(() => {
  const name = deviceContext.value?.app.environment.name
  if (name === 'test') return { label: '测试环境', color: 'amber' as const }
  if (name === 'production') return { label: '线上环境', color: 'green' as const }
  return { label: '环境未知', color: 'gray' as const }
})

const deviceContextCopyText = computed(() => {
  const context = deviceContext.value
  if (!context) return ''
  const experiments = deviceExperimentRows.value.map((experiment) =>
    `${experiment.state === 'out' ? '[出组] ' : '[进组] '}${experiment.key} -> ${experiment.group}`
  )
  return [
    `Platform: ${context.platform}`,
    `Project: ${context.projectName || '-'}`,
    `Device: ${context.device.name || '-'} (${context.device.udid || '-'})`,
    `Model: ${context.device.model || '-'}`,
    `OS: ${context.device.os || '-'}`,
    `Build: ${context.device.buildConfiguration}`,
    `Environment: ${context.app.environment.name}`,
    `Site: ${context.app.environment.site || '-'}`,
    `Country: ${context.app.environment.country || '-'}`,
    `App device_id: ${context.app.ids.deviceId || '-'}`,
    `Distinct ID: ${context.app.ids.distinctId || '-'}`,
    `Snapshot: ${context.app.snapshotAt || '-'}`,
    '',
    ...experiments
  ].join('\n')
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

function highlightSegments(text: string, patterns: HighlightPattern[]): HighlightSegment[] {
  if (!text || !patterns.length) return [{ text, highlighted: false }]

  const ranges: Array<[number, number]> = []
  for (const pattern of patterns) {
    if (!pattern.value) continue
    if (pattern.regex) {
      try {
        const matcher = new RegExp(pattern.value, 'gi')
        let match: RegExpExecArray | null
        let matched = 0
        while ((match = matcher.exec(text)) && matched < 1000) {
          if (!match[0].length) {
            matcher.lastIndex += 1
            continue
          }
          ranges.push([match.index, match.index + match[0].length])
          matched += 1
        }
      } catch {
        // Invalid regexes are still searchable server-side; skip only their highlight.
      }
      continue
    }

    const needle = pattern.value.toLowerCase()
    const haystack = text.toLowerCase()
    let searchFrom = 0
    while (searchFrom < haystack.length) {
      const index = haystack.indexOf(needle, searchFrom)
      if (index < 0) break
      ranges.push([index, index + needle.length])
      searchFrom = index + Math.max(needle.length, 1)
    }
  }

  if (!ranges.length) return [{ text, highlighted: false }]
  ranges.sort((left, right) => left[0] - right[0])
  const merged: Array<[number, number]> = []
  for (const range of ranges) {
    const previous = merged.at(-1)
    if (previous && range[0] <= previous[1]) {
      previous[1] = Math.max(previous[1], range[1])
    } else {
      merged.push([...range])
    }
  }

  const segments: HighlightSegment[] = []
  let cursor = 0
  for (const [start, end] of merged) {
    if (start > cursor) segments.push({ text: text.slice(cursor, start), highlighted: false })
    segments.push({ text: text.slice(start, end), highlighted: true })
    cursor = end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), highlighted: false })
  return segments
}

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
const errorCopyText = computed(() => [
  `Platform: ${platformName.value}`,
  `Project: ${projectName.value}`,
  `SDK: ${sdk.value || '-'}`,
  `Device: ${connectedDevice.value?.name || '-'}`,
  '',
  'Errors:',
  ...errors.value.map(event => `[${event.time}] ${event.text}`),
  '',
  'Source locations:',
  ...callStack.value,
  '',
  'Recent context:',
  ...latestEvents.value.map(event => `[${event.time}] ${event.text}`)
].join('\n'))
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
  await nextTick()
  if (eventPane.value) eventPane.value.scrollTop = eventPane.value.scrollHeight
}

async function copyText(target: string, text: string) {
  if (!text.trim()) return
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
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
              <UIcon name="i-heroicons-git-branch" />
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
                <LogFilterSelect
                  v-model="selectedFilter"
                  class="event-filter"
                  placeholder="筛选实时日志 · ⌘F"
                />
                <UInput
                  id="event-keyword-filter"
                  v-model="keywordQuery"
                  icon="i-heroicons-magnifying-glass"
                  placeholder="二次搜索关键词"
                  class="keyword-filter"
                />
                <UButton
                  color="gray"
                  variant="ghost"
                  icon="i-heroicons-arrow-path"
                  :loading="busy"
                  :disabled="busy || !activeDeviceAvailable"
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
                  <span class="event-text">
                    <template
                      v-for="(segment, index) in highlightSegments(event.text, logHighlightPatterns)"
                      :key="index"
                    >
                      <mark v-if="segment.highlighted" class="log-highlight">{{ segment.text }}</mark>
                      <template v-else>{{ segment.text }}</template>
                    </template>
                  </span>
                  <UTooltip text="复制这条日志">
                    <UButton
                      color="gray"
                      variant="ghost"
                      size="xs"
                      square
                      :icon="copiedTarget === `event-${event.id}` ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                      aria-label="复制这条运行日志"
                      @click="copyText(`event-${event.id}`, event.text)"
                    />
                  </UTooltip>
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
                <UTooltip text="复制全部错误、调用栈和最近上下文">
                  <UButton
                    color="gray"
                    variant="ghost"
                    size="xs"
                    square
                    :icon="copiedTarget === 'all-errors' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                    aria-label="复制全部错误信息"
                    :disabled="!errors.length"
                    @click="copyText('all-errors', errorCopyText)"
                  />
                </UTooltip>
                <span class="event-summary">{{ errors.length }} 个错误 · {{ callStack.length }} 个源码位置</span>
              </div>
              <div v-if="errors.length" class="issues-layout pane-body">
                <UAlert
                  color="red"
                  variant="soft"
                  icon="i-heroicons-exclamation-circle"
                  title="本次运行发现错误"
                  :description="firstError"
                />

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
                        <span class="issue-time">{{ event.time }}</span>
                        <pre>{{ event.text }}</pre>
                        <UTooltip text="复制这条错误">
                          <UButton
                            color="gray"
                            variant="ghost"
                            size="xs"
                            square
                            :icon="copiedTarget === `error-${event.id}` ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                            aria-label="复制这条错误"
                            @click="copyText(`error-${event.id}`, event.text)"
                          />
                        </UTooltip>
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
                        <UTooltip text="复制源码位置">
                          <UButton
                            color="gray"
                            variant="ghost"
                            size="xs"
                            square
                            :icon="copiedTarget === `frame-${index}` ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                            aria-label="复制源码位置"
                            @click="copyText(`frame-${index}`, frame)"
                          />
                        </UTooltip>
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

            <section v-else-if="activeTab === 'logs'" class="pane">
              <div class="pane-toolbar log-search">
                <LogFilterSelect
                  v-model="selectedFilter"
                  :placeholder="`搜索 ${platformName} decoded.log，例如 HttpLogging / error / request-id`"
                  class="flex-1"
                />
                <UInput
                  v-model="keywordQuery"
                  icon="i-heroicons-magnifying-glass"
                  placeholder="二次搜索关键词"
                  class="keyword-filter"
                  @keydown.enter="searchCurrentLogs"
                />
                <UButton
                  icon="i-heroicons-magnifying-glass"
                  :disabled="!selectedFilter.query && !keywordQuery.trim()"
                  @click="searchCurrentLogs"
                >
                  搜索
                </UButton>
                <UTooltip text="复制全部搜索结果">
                  <UButton
                    color="gray"
                    variant="ghost"
                    square
                    :icon="copiedTarget === 'all-logs' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                    aria-label="复制全部日志"
                    :disabled="!logs.length"
                    @click="copyText('all-logs', logs.map(line => line.text).join('\n'))"
                  />
                </UTooltip>
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
                  <span class="log-no">{{ line.n }}</span>
                  <code>
                    <template
                      v-for="(segment, index) in highlightSegments(line.text, logHighlightPatterns)"
                      :key="index"
                    >
                      <mark v-if="segment.highlighted" class="log-highlight">{{ segment.text }}</mark>
                      <template v-else>{{ segment.text }}</template>
                    </template>
                  </code>
                  <UTooltip text="复制这条日志">
                    <UButton
                      color="gray"
                      variant="ghost"
                      size="xs"
                      square
                      :icon="copiedTarget === `log-${line.n}` ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                      aria-label="复制这条日志"
                      @click="copyText(`log-${line.n}`, line.text)"
                    />
                  </UTooltip>
                </div>
              </div>
              <div v-if="logs.length" class="log-meta">{{ logMeta }}</div>
            </section>

            <PageLinkPanel
              v-else-if="activeTab === 'links'"
              :platform="platform"
              :device-name="connectedDevice?.name"
              :device-available="Boolean(connectedDevice?.available)"
            />

            <section v-else class="pane device-context-pane">
              <div class="pane-toolbar">
                <div class="run-status">
                  <UIcon name="i-heroicons-device-phone-mobile" />
                  <span>设备上下文</span>
                  <UBadge :color="deviceContextState.color" variant="subtle">
                    {{ deviceContextState.label }}
                  </UBadge>
                </div>
                <div class="toolbar-spacer" />
                <UInput
                  v-model="experimentQuery"
                  icon="i-heroicons-magnifying-glass"
                  placeholder="搜索实验 key、分组或 ID"
                  class="experiment-filter"
                />
                <UTooltip text="重新读取 App 缓存">
                  <UButton
                    color="gray"
                    variant="ghost"
                    icon="i-heroicons-arrow-path"
                    square
                    :loading="deviceContextLoading"
                    aria-label="重新读取设备上下文"
                    @click="loadCurrentDeviceContext(true)"
                  />
                </UTooltip>
                <UTooltip text="复制设备与 AB 上下文">
                  <UButton
                    color="gray"
                    variant="ghost"
                    square
                    :icon="copiedTarget === 'device-context' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                    :disabled="!deviceContext"
                    aria-label="复制设备与 AB 上下文"
                    @click="copyText('device-context', deviceContextCopyText)"
                  />
                </UTooltip>
                <UButton
                  color="gray"
                  variant="soft"
                  icon="i-heroicons-camera"
                  :disabled="!activeDeviceAvailable"
                  @click="openScreenshotPreview"
                >
                  截图预览
                  <kbd class="shortcut-key">⇧⌘S</kbd>
                </UButton>
              </div>

              <AppEmptyState
                v-if="deviceContextLoading && !deviceContext"
                class="pane-body"
                icon="i-heroicons-arrow-path"
                title="正在读取设备上下文"
                description="正在读取 App 已保存的环境、身份和设备缓存。"
              />
              <AppEmptyState
                v-else-if="deviceContextError && !deviceContext"
                class="pane-body"
                icon="i-heroicons-exclamation-triangle"
                title="设备上下文读取失败"
                :description="deviceContextError"
              >
                <UButton
                  color="gray"
                  variant="soft"
                  icon="i-heroicons-arrow-path"
                  @click="loadCurrentDeviceContext(true)"
                >
                  重试
                </UButton>
              </AppEmptyState>
              <AppEmptyState
                v-else-if="!deviceContext"
                class="pane-body"
                icon="i-heroicons-device-phone-mobile"
                title="尚未读取设备"
                description="连接并选择设备后，这里会显示 App 环境、设备 ID 和 AB 分组。"
              />

              <div v-else class="device-context-body pane-body">
                <div class="context-summary-grid">
                  <UCard>
                    <template #header>
                      <div class="context-card-heading">
                        <span>设备</span>
                        <UBadge :color="deviceContext.device.connected ? 'green' : 'red'" variant="subtle">
                          {{ deviceContext.device.connected ? '已连接' : '未连接' }}
                        </UBadge>
                      </div>
                    </template>
                    <div class="context-fields">
                      <div class="context-field">
                        <span>设备</span>
                        <code>{{ deviceContext.device.name || '-' }}</code>
                      </div>
                      <div class="context-field">
                        <span>UDID</span>
                        <code>{{ deviceContext.device.udid || '-' }}</code>
                        <UButton
                          v-if="deviceContext.device.udid"
                          color="gray"
                          variant="ghost"
                          size="xs"
                          square
                          :icon="copiedTarget === 'device-udid' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                          aria-label="复制设备 UDID"
                          @click="copyText('device-udid', deviceContext.device.udid)"
                        />
                      </div>
                      <div class="context-field">
                        <span>型号 / 系统</span>
                        <code>{{ deviceContext.device.model || '-' }} · {{ platformName }} {{ deviceContext.device.os || '?' }}</code>
                      </div>
                      <div class="context-field">
                        <span>构建配置</span>
                        <code>{{ deviceContext.device.buildConfiguration }}</code>
                      </div>
                    </div>
                  </UCard>

                  <UCard>
                    <template #header>
                      <div class="context-card-heading">
                        <span>运行环境</span>
                        <UBadge :color="environmentBadge.color" variant="subtle">
                          {{ environmentBadge.label }}
                        </UBadge>
                      </div>
                    </template>
                    <div class="context-fields">
                      <div class="context-field">
                        <span>站点</span>
                        <code>{{ deviceContext.app.environment.site || '-' }}</code>
                      </div>
                      <div class="context-field">
                        <span>地区</span>
                        <code>{{ deviceContext.app.environment.country || '-' }}</code>
                      </div>
                      <div class="context-field">
                        <span>App device_id</span>
                        <code>{{ deviceContext.app.ids.deviceId || '-' }}</code>
                        <UButton
                          v-if="deviceContext.app.ids.deviceId"
                          color="gray"
                          variant="ghost"
                          size="xs"
                          square
                          :icon="copiedTarget === 'app-device-id' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                          aria-label="复制 App device_id"
                          @click="copyText('app-device-id', deviceContext.app.ids.deviceId)"
                        />
                      </div>
                      <div class="context-field">
                        <span>Distinct ID</span>
                        <code>{{ deviceContext.app.ids.distinctId || '-' }}</code>
                        <UButton
                          v-if="deviceContext.app.ids.distinctId"
                          color="gray"
                          variant="ghost"
                          size="xs"
                          square
                          :icon="copiedTarget === 'distinct-id' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                          aria-label="复制 Distinct ID"
                          @click="copyText('distinct-id', deviceContext.app.ids.distinctId)"
                        />
                      </div>
                    </div>
                  </UCard>
                </div>

                <UAlert
                  v-if="!deviceContext.app.available || deviceContext.app.warnings.length"
                  color="amber"
                  variant="soft"
                  icon="i-heroicons-information-circle"
                  :title="deviceContext.app.available ? '部分缓存未读取' : 'App 调试缓存不可用'"
                  :description="deviceContext.app.warnings.join('；') || '打开 App 后再刷新。'"
                />

                <UCard class="experiment-card">
                  <template #header>
                    <div class="context-card-heading">
                      <div>
                        <span>AB 实验分组</span>
                        <p>
                          {{ filteredDeviceExperiments.length }} / {{ deviceExperimentRows.length }} 条
                          <template v-if="deviceContext.app.snapshotAt"> · 快照 {{ deviceContext.app.snapshotAt }}</template>
                        </p>
                      </div>
                      <UBadge color="primary" variant="subtle">
                        {{ deviceExperimentRows.filter(item => item.state === 'in').length }} 进组
                      </UBadge>
                    </div>
                  </template>

                  <div v-if="filteredDeviceExperiments.length" class="experiment-list">
                    <div
                      v-for="experiment in filteredDeviceExperiments"
                      :key="`${experiment.state}-${experiment.key}-${experiment.experimentId}`"
                      class="experiment-row"
                    >
                      <div class="experiment-name">
                        <code>{{ experiment.key }}</code>
                        <span>
                          {{ experiment.experimentId ? `Experiment ${experiment.experimentId}` : 'Sensors ABTest' }}
                          <template v-if="experiment.controlGroup"> · 对照组</template>
                        </span>
                      </div>
                      <UBadge :color="experiment.state === 'out' ? 'gray' : 'primary'" variant="subtle">
                        {{ experiment.state === 'out' ? '出组' : '进组' }}
                      </UBadge>
                      <code class="experiment-group">{{ experiment.group || '-' }}</code>
                      <UTooltip text="复制实验分组">
                        <UButton
                          color="gray"
                          variant="ghost"
                          size="xs"
                          square
                          :icon="copiedTarget === `experiment-${experiment.key}` ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                          aria-label="复制实验分组"
                          @click="copyText(`experiment-${experiment.key}`, `${experiment.key} -> ${experiment.group}`)"
                        />
                      </UTooltip>
                    </div>
                  </div>
                  <div v-else class="experiment-empty">
                    <UIcon name="i-heroicons-beaker" />
                    <div>
                      <strong>{{ deviceExperimentRows.length ? '没有匹配实验' : '暂未读取到 AB 分组' }}</strong>
                      <p>
                        {{ deviceExperimentRows.length
                          ? '调整关键词后重试。'
                          : '打开 App 实验室或触发 AB 请求，然后点击刷新。' }}
                      </p>
                    </div>
                  </div>
                </UCard>
              </div>
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
    </div>
  </UApp>
</template>
