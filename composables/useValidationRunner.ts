export type ValidationKind = 'test' | 'lint'
export type ValidationStatus = 'idle' | 'running' | 'success' | 'error' | 'cancelled'

export interface ValidationLine {
  id: number
  time: string
  text: string
  kind: 'info' | 'success' | 'warning' | 'error' | 'command' | 'dim'
}

export interface ValidationState {
  status: ValidationStatus
  jobId: string
  sessionId: string
  configuration: string
  elapsed: number
  exitCode: number | null
  lines: ValidationLine[]
  total: number
  error: string
}

interface JobSnapshot {
  id: string
  sessionId?: string
  done: boolean
  cancelled: boolean
  exitCode: number | null
  elapsed: number
  total: number
  truncated?: boolean
  lines: string[]
}

async function requestJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
  return data as T
}

function classify(line: string): ValidationLine['kind'] {
  if (/^\s*✗/.test(line) || /\berror:|\*\* BUILD FAILED \*\*|fatal error|exception|failed|FAILURE:|What went wrong|Execution failed|Caused by:/i.test(line) || /\s[EF](?:\/|\s{2,})/.test(line)) return 'error'
  if (/^\s*✓/.test(line) || /\*\* BUILD SUCCEEDED \*\*|BUILD SUCCESSFUL|TEST SUCCEEDED|success|完成/i.test(line)) return 'success'
  if (/^\s*!/.test(line) || /^\s*w:|warning:|warn/i.test(line) || /\sW(?:\/|\s{2,})/.test(line)) return 'warning'
  if (/^(==>|> Task)/.test(line)) return 'command'
  if (/^\s{4}/.test(line)) return 'dim'
  return 'info'
}

function clock() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function initialState(): ValidationState {
  return {
    status: 'idle',
    jobId: '',
    sessionId: '',
    configuration: 'Debug',
    elapsed: 0,
    exitCode: null,
    lines: [],
    total: 0,
    error: ''
  }
}

export function useValidationRunner(platform: 'ios' | 'android') {
  const states = reactive<Record<ValidationKind, ValidationState>>({
    test: initialState(),
    lint: initialState()
  })
  const activeKind = ref<ValidationKind>('test')
  const running = computed(() =>
    states.test.status === 'running' || states.lint.status === 'running'
  )
  const activeState = computed(() => states[activeKind.value])
  const activeJobId = computed(() => activeState.value.jobId)
  let serial = 0
  let lineSerial = 0

  function append(kind: ValidationKind, lines: string[]) {
    if (!lines.length) return
    states[kind].lines.push(...lines.map(text => ({
      id: ++lineSerial,
      time: clock(),
      text: text || ' ',
      kind: classify(text)
    })))
    if (states[kind].lines.length > 5000) {
      states[kind].lines = states[kind].lines.slice(-3000)
    }
  }

  async function poll(kind: ValidationKind, offset: number, currentSerial: number) {
    const state = states[kind]
    if (!state.jobId || currentSerial !== serial) return
    try {
      const job = await requestJSON<JobSnapshot>(
        `/api/${platform}/job/${state.jobId}?offset=${offset}`
      )
      if (currentSerial !== serial) return
      if (job.truncated) state.lines = []
      append(kind, job.lines || [])
      state.total = job.total
      state.elapsed = job.elapsed
      if (job.sessionId) state.sessionId = job.sessionId
      if (job.done) {
        state.status = job.cancelled ? 'cancelled' : job.exitCode === 0 ? 'success' : 'error'
        state.exitCode = job.exitCode
        if (state.sessionId) void captureSnapshot(kind)
        return
      }
      setTimeout(() => poll(kind, job.total, currentSerial), 500)
    } catch (cause) {
      if (currentSerial !== serial) return
      state.status = 'error'
      state.error = cause instanceof Error ? cause.message : '读取验证日志失败'
    }
  }

  async function captureSnapshot(kind: ValidationKind) {
    const state = states[kind]
    if (!state.sessionId) return
    try {
      const context = await requestJSON<Record<string, unknown>>(
        `/api/${platform}/device/context?configuration=${encodeURIComponent(state.configuration)}&refresh=1`
      )
      await requestJSON(
        `/api/${platform}/sessions/${encodeURIComponent(state.sessionId)}/snapshot`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ context, label: `validation-${kind}` })
        }
      )
    } catch {
      // The validation result remains useful when device context is unavailable.
    }
  }

  async function run(kind: ValidationKind, configuration = 'Debug') {
    if (running.value) return false
    activeKind.value = kind
    serial += 1
    const currentSerial = serial
    states[kind] = initialState()
    states[kind].status = 'running'
    states[kind].configuration = configuration
    try {
      const data = await requestJSON<{ jobId: string, sessionId: string }>(
        `/api/${platform}/run`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: kind, configuration })
        }
      )
      states[kind].jobId = data.jobId
      states[kind].sessionId = data.sessionId
      void poll(kind, 0, currentSerial)
      return true
    } catch (cause) {
      states[kind].status = 'error'
      states[kind].error = cause instanceof Error ? cause.message : '启动验证失败'
      return false
    }
  }

  async function stop() {
    const state = activeState.value
    if (!state.jobId || state.status !== 'running') return false
    try {
      await requestJSON(`/api/${platform}/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobId: state.jobId })
      })
      return true
    } catch (cause) {
      state.error = cause instanceof Error ? cause.message : '停止验证失败'
      return false
    }
  }

  function clear(kind: ValidationKind = activeKind.value) {
    states[kind] = initialState()
    if (kind === activeKind.value) activeKind.value = kind
  }

  return {
    platform,
    states,
    activeKind,
    activeState,
    activeJobId,
    running,
    run,
    stop,
    clear
  }
}

