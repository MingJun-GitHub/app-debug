export type EventKind = 'info' | 'success' | 'warning' | 'error' | 'command' | 'dim'

export interface DebugEvent {
  id: string
  time: string
  text: string
  kind: EventKind
}

export interface Device {
  udid: string
  name: string
  model?: string
  os?: string
  simulator: boolean
  available: boolean
  error?: string | null
}

export interface DebugStatus {
  device?: Device | null
  sdk?: string | null
  selected?: {
    udid: string
    name: string
  }
}

interface JobSnapshot {
  id: string
  done: boolean
  cancelled: boolean
  exitCode: number | null
  elapsed: number
  total: number
  lines: string[]
}

interface LogResult {
  ok: boolean
  error?: string
  total: number
  lines: Array<{ n: number, text: string }>
}

function classify(line: string): EventKind {
  if (/^\s*✗/.test(line) || /\berror:|\*\* BUILD FAILED \*\*|fatal error|exception|failed/i.test(line)) return 'error'
  if (/^\s*✓/.test(line) || /\*\* BUILD SUCCEEDED \*\*|success|完成/i.test(line)) return 'success'
  if (/^\s*!/.test(line) || /\bwarning:|warn/i.test(line)) return 'warning'
  if (/^==>/.test(line)) return 'command'
  if (/^\s{4}/.test(line)) return 'dim'
  return 'info'
}

function clock() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

async function requestJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
  return data as T
}

export function useDebugRunner() {
  const status = ref<DebugStatus | null>(null)
  const devices = ref<Device[]>([])
  const events = ref<DebugEvent[]>([])
  const logs = ref<Array<{ n: number, text: string }>>([])
  const logMeta = ref('尚未搜索')
  const activeJob = ref<{ id: string, action: string } | null>(null)
  const jobDone = ref(true)
  const jobResult = ref<'success' | 'error' | 'cancelled' | null>(null)
  const elapsed = ref(0)
  const busy = ref(false)
  let eventSerial = 0
  let jobOffset = 0

  const physicalDevices = computed(() => devices.value.filter(device => !device.simulator))
  const connectedDevice = computed(() => status.value?.device || null)
  const sdk = computed(() => status.value?.sdk || null)
  const errors = computed(() => events.value.filter(event => event.kind === 'error'))
  const warnings = computed(() => events.value.filter(event => event.kind === 'warning'))
  const callStack = computed(() => {
    const seen = new Set<string>()
    for (const event of errors.value) {
      const matches = event.text.match(/(?:[A-Za-z0-9_\-./]+)\.(?:swift|m|mm|kt|java):\d+/g) || []
      for (const match of matches) seen.add(match)
    }
    return [...seen]
  })

  function appendLines(lines: string[]) {
    if (!lines.length) return
    const next = lines.map((line) => ({
      id: `event-${++eventSerial}`,
      time: clock(),
      text: line || ' ',
      kind: classify(line)
    }))
    events.value.push(...next)
    if (events.value.length > 5000) events.value = events.value.slice(-3000)
  }

  function clearEvents() {
    events.value = []
    elapsed.value = 0
    jobResult.value = null
    jobOffset = 0
  }

  async function refreshStatus() {
    try {
      status.value = await requestJSON<DebugStatus>('/api/status')
    } catch {
      status.value = null
    }
  }

  async function loadDevices() {
    try {
      const data = await requestJSON<{ devices: Device[] }>('/api/devices')
      devices.value = data.devices.filter(device => !device.simulator)
    } catch {
      devices.value = []
    }
  }

  async function selectDevice(device: Device) {
    await requestJSON('/api/device/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ udid: device.udid, name: device.name })
    })
  }

  async function pollJob() {
    if (!activeJob.value) return
    try {
      const job = await requestJSON<JobSnapshot>(
        `/api/job/${activeJob.value.id}?offset=${jobOffset}`
      )
      appendLines(job.lines || [])
      jobOffset = job.total
      elapsed.value = job.elapsed
      if (job.done) {
        busy.value = false
        jobDone.value = true
        jobResult.value = job.cancelled ? 'cancelled' : job.exitCode === 0 ? 'success' : 'error'
        activeJob.value = null
        await refreshStatus()
        return
      }
      setTimeout(pollJob, 500)
    } catch {
      busy.value = false
      jobDone.value = true
      jobResult.value = 'error'
      activeJob.value = null
    }
  }

  async function runAction(action: string, configuration = 'Debug') {
    if (busy.value) return
    clearEvents()
    jobOffset = 0
    busy.value = true
    jobDone.value = false
    try {
      const data = await requestJSON<{ jobId: string }>('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, configuration })
      })
      activeJob.value = { id: data.jobId, action }
      pollJob()
    } catch (error) {
      appendLines([`[runner] ${error instanceof Error ? error.message : String(error)}`])
      busy.value = false
      jobDone.value = true
      jobResult.value = 'error'
    }
  }

  async function stopJob() {
    if (!activeJob.value) return
    try {
      await requestJSON('/api/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobId: activeJob.value.id })
      })
    } catch {
      appendLines(['[runner] 停止请求失败'])
    }
  }

  async function searchLogs(query: string, regex: boolean) {
    if (!query.trim()) return
    logMeta.value = '搜索中…'
    const params = new URLSearchParams({ q: query, limit: '300' })
    if (regex) params.set('regex', '1')
    try {
      const result = await requestJSON<LogResult>(`/api/log/search?${params}`)
      logs.value = result.lines || []
      logMeta.value = result.ok
        ? `${result.total} 条匹配 · 显示最近 ${result.lines.length} 条`
        : result.error || '搜索失败'
    } catch (error) {
      logs.value = []
      logMeta.value = error instanceof Error ? error.message : '搜索失败'
    }
  }

  return {
    status,
    devices,
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
    appendLines,
    clearEvents,
    refreshStatus,
    loadDevices,
    selectDevice,
    runAction,
    stopJob,
    searchLogs
  }
}
