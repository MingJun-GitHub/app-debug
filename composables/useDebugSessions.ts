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

async function requestJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
  return data as T
}

export function useDebugSessions(platform: 'ios' | 'android') {
  const sessions = ref<SessionSummary[]>([])
  const selected = ref<DebugSession | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)
  const savingSnapshot = ref(false)
  const exporting = ref(false)
  const deleting = ref(false)
  const clearing = ref(false)
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

  async function deleteSession(sessionId: string) {
    if (!sessionId) return false
    deleting.value = true
    error.value = ''
    try {
      await requestJSON(
        `/api/${platform}/sessions/${encodeURIComponent(sessionId)}/delete`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ confirm: true })
        }
      )
      if (selected.value?.id === sessionId) selected.value = null
      await refresh()
      return true
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '删除会话失败'
      return false
    } finally {
      deleting.value = false
    }
  }

  async function clearSessions() {
    clearing.value = true
    error.value = ''
    try {
      await requestJSON(`/api/${platform}/sessions/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true })
      })
      selected.value = null
      sessions.value = []
      return true
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '清空会话失败'
      return false
    } finally {
      clearing.value = false
    }
  }

  return {
    sessions,
    selected,
    loading,
    loadingDetail,
    savingSnapshot,
    exporting,
    deleting,
    clearing,
    error,
    root,
    refresh,
    load,
    saveSnapshot,
    exportSession,
    deleteSession,
    clearSessions
  }
}

