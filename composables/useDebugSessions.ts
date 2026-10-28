import type { DeviceContext } from '~/composables/useDebugRunner'

export interface SessionSummary {
  id: string
  platform: 'ios' | 'android'
  action: string
  kind: 'run' | 'validation'
  configuration: string
  createdAt: string
  updatedAt: string
  status: 'running' | 'success' | 'error' | 'cancelled'
  project: {
    displayName?: string
    branch?: string
    commit?: string
  }
  result: {
    exitCode?: number | null
    elapsed?: number
    lineCount?: number
  }
  analysis: {
    errorCount: number
    warningCount: number
    lineCount: number
  }
  snapshotCount: number
}

export interface SessionSnapshot {
  capturedAt: string
  label: string
  context: DeviceContext
}

export interface DebugSession extends Omit<SessionSummary, 'snapshotCount'> {
  schemaVersion: number
  project: SessionSummary['project'] & {
    path?: string
    repoName?: string
    dirty?: boolean
    changedFiles?: number
    detached?: boolean
    remote?: string
    submodules?: Array<{
      path: string
      commit: string
      branch: string
      initialized: boolean
      dirty: boolean
      modified: boolean
      conflicted: boolean
    }>
  }
  device: {
    name?: string
    udid?: string
    model?: string
    os?: string
    available?: boolean
  }
  artifact: {
    name?: string
    path?: string
    version?: string
    size?: number | null
    mtime?: number
  }
  analysis: SessionSummary['analysis'] & {
    sourceLocations?: string[]
    errorGroups?: Array<{
      fingerprint: string
      count: number
      sample: string
    }>
    summaries?: string[]
    outcomes?: Array<{ name: string, count: number }>
  }
  snapshots: SessionSnapshot[]
  logFile: string
}

export interface DiagnosticExport {
  content: string
  contentType: string
  filename: string
}

export interface RouteInventory {
  platform: 'ios' | 'android'
  project: string
  count: number
  routes: Array<{
    pattern: string
    kind: string
    source: string
    line: number | null
  }>
  warnings: string[]
}

async function requestJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
  return data as T
}

export function useDebugSessions(platform: 'ios' | 'android') {
  const sessions = ref<SessionSummary[]>([])
  const selected = ref<DebugSession | null>(null)
  const routes = ref<RouteInventory | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)
  const savingSnapshot = ref(false)
  const exporting = ref(false)
  const error = ref('')
  const root = ref('')

  async function refresh(limit = 30) {
    loading.value = true
    error.value = ''
    const selectedId = selected.value?.id
    try {
      const data = await requestJSON<{ sessions: SessionSummary[], root: string }>(
        `/api/${platform}/sessions?limit=${limit}`
      )
      sessions.value = data.sessions
      root.value = data.root
      if (selectedId) await load(selectedId)
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '读取调试会话失败'
    } finally {
      loading.value = false
    }
  }

  async function load(sessionId: string) {
    if (!sessionId) return null
    loadingDetail.value = true
    error.value = ''
    try {
      selected.value = await requestJSON<DebugSession>(
        `/api/${platform}/sessions/${encodeURIComponent(sessionId)}`
      )
      return selected.value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '读取会话详情失败'
      return null
    } finally {
      loadingDetail.value = false
    }
  }

  async function saveSnapshot(sessionId: string, context: DeviceContext, label = 'device-context') {
    if (!sessionId || !context) return null
    savingSnapshot.value = true
    error.value = ''
    try {
      const data = await requestJSON<{ session: DebugSession }>(
        `/api/${platform}/sessions/${encodeURIComponent(sessionId)}/snapshot`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ context, label })
        }
      )
      selected.value = data.session
      await refresh()
      return data.session
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '保存设备快照失败'
      return null
    } finally {
      savingSnapshot.value = false
    }
  }

  async function exportSession(sessionId: string, format: 'markdown' | 'json' = 'markdown') {
    if (!sessionId) return null
    exporting.value = true
    error.value = ''
    try {
      return await requestJSON<DiagnosticExport>(
        `/api/${platform}/sessions/${encodeURIComponent(sessionId)}/export?format=${format}`
      )
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '导出诊断包失败'
      return null
    } finally {
      exporting.value = false
    }
  }

  async function loadRoutes() {
    try {
      routes.value = await requestJSON<RouteInventory>(`/api/${platform}/routes`)
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '读取路由清单失败'
    }
  }

  return {
    sessions,
    selected,
    routes,
    loading,
    loadingDetail,
    savingSnapshot,
    exporting,
    error,
    root,
    refresh,
    load,
    saveSnapshot,
    exportSession,
    loadRoutes
  }
}

