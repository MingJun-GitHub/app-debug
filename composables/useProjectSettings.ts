export interface ProjectGitInfo {
  repoRoot: string
  repoName: string
  branch: string
  commit: string
  dirty: boolean
  changedFiles: number
  detached: boolean
  remote: string
}

export interface ProjectConnection {
  platform: 'ios' | 'android'
  path: string
  defaultPath: string
  exists: boolean
  valid: boolean
  errors: string[]
  warnings: string[]
  git: ProjectGitInfo
}

export interface ProjectSettings {
  version: number
  configPath: string
  loadError: string | null
  projects: Record<'ios' | 'android', ProjectConnection>
}

interface PickDirectoryResult {
  cancelled: boolean
  path?: string
  project?: ProjectConnection
}

async function requestJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
  return data as T
}

export function useProjectSettings() {
  const settings = ref<ProjectSettings | null>(null)
  const loading = ref(false)
  const saving = ref<'ios' | 'android' | null>(null)
  const picking = ref<'ios' | 'android' | null>(null)
  const error = ref('')

  async function refresh() {
    loading.value = true
    try {
      settings.value = await requestJSON<ProjectSettings>('/api/settings')
      error.value = ''
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '读取项目设置失败'
    } finally {
      loading.value = false
    }
  }

  async function save(platform: 'ios' | 'android', path: string) {
    saving.value = platform
    error.value = ''
    try {
      const result = await requestJSON<{ settings: ProjectSettings }>(
        '/api/settings/project',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ platform, path })
        }
      )
      settings.value = result.settings
      return result.settings.projects[platform]
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '保存项目目录失败'
      throw cause
    } finally {
      saving.value = null
    }
  }

  async function pickDirectory(platform: 'ios' | 'android') {
    picking.value = platform
    error.value = ''
    try {
      return await requestJSON<PickDirectoryResult>(
        '/api/settings/pick-directory',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ platform })
        }
      )
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '选择项目目录失败'
      throw cause
    } finally {
      picking.value = null
    }
  }

  return {
    settings,
    loading,
    saving,
    picking,
    error,
    refresh,
    save,
    pickDirectory
  }
}
