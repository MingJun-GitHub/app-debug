<script setup lang="ts">
import type { DeviceContext } from '~/composables/useDebugRunner'
import { redactSensitive } from '~/composables/redaction'
import type { SessionSummary } from '~/composables/useDebugSessions'

const props = defineProps<{
  platform: 'ios' | 'android'
  currentSessionId: string
  deviceContext: DeviceContext | null
  deviceAvailable: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  run: [action: string]
  'view-source': [location: string]
}>()

const store = useDebugSessions(props.platform)
const selectedId = ref('')
const copied = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | undefined

const selected = computed(() => store.selected.value)
const platformName = computed(() => props.platform === 'ios' ? 'iOS' : 'Android')
const testDisabled = computed(() =>
  props.busy || (props.platform === 'ios' && !props.deviceAvailable)
)
const snapshotDiff = computed(() => {
  const snapshots = selected.value?.snapshots || []
  if (snapshots.length < 2) return null
  const before = snapshots.at(-2)?.context
  const after = snapshots.at(-1)?.context
  if (!before || !after) return null
  const changes: Array<{ field: string, before: string, after: string }> = []
  const compare = (field: string, left: unknown, right: unknown) => {
    const beforeValue = String(left ?? '-')
    const afterValue = String(right ?? '-')
    if (beforeValue !== afterValue) changes.push({ field, before: beforeValue, after: afterValue })
  }
  compare('App 环境', before.app.environment.name, after.app.environment.name)
  compare('站点', before.app.environment.site, after.app.environment.site)
  compare('国家/地区', before.app.environment.country, after.app.environment.country)
  compare('设备', before.device.name, after.device.name)
  compare('系统', before.device.os, after.device.os)
  compare('构建配置', before.device.buildConfiguration, after.device.buildConfiguration)
  const experimentMap = (context: typeof before) => new Map(
    [...context.app.experiments, ...context.app.outExperiments]
      .map(item => [`${item.state}:${item.key}`, item.group || ''])
  )
  const beforeExperiments = experimentMap(before)
  const afterExperiments = experimentMap(after)
  const experimentChanges: Array<{ key: string, before: string, after: string, kind: string }> = []
  for (const key of new Set([...beforeExperiments.keys(), ...afterExperiments.keys()])) {
    const left = beforeExperiments.get(key)
    const right = afterExperiments.get(key)
    if (left === right) continue
    experimentChanges.push({
      key: key.replace(/^[^:]+:/, ''),
      before: left || '-',
      after: right || '-',
      kind: left == null ? '新增' : right == null ? '移除' : '变化'
    })
  }
  return { changes, experimentChanges }
})

function statusBadge(status?: SessionSummary['status']) {
  if (status === 'success') return { color: 'green' as const, label: '通过' }
  if (status === 'error') return { color: 'red' as const, label: '失败' }
  if (status === 'cancelled') return { color: 'amber' as const, label: '已停止' }
  return { color: 'blue' as const, label: '运行中' }
}

function actionLabel(action?: string) {
  return ({
    all: '构建并启动',
    build: '构建',
    install: '安装',
    launch: '启动',
    log: '跟随日志',
    logs: '拉取日志',
    doctor: '环境检查',
    test: '单元测试',
    lint: '静态检查'
  } as Record<string, string>)[action || ''] || action || '-'
}

function formatTime(value?: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

async function selectSession(sessionId: string) {
  selectedId.value = sessionId
  await store.load(sessionId)
}

async function refreshAll(selectCurrent = true) {
  await store.refresh()
  const target = props.currentSessionId
    || selectedId.value
    || store.sessions.value[0]?.id
  if (target && selectCurrent) {
    selectedId.value = target
    await store.load(target)
  }
  await store.loadRoutes()
}

async function saveSnapshot() {
  if (!props.deviceContext || !selectedId.value) return
  await store.saveSnapshot(selectedId.value, props.deviceContext)
}

async function copyDiagnostic() {
  const target = selectedId.value
  if (!target) return
  const result = await store.exportSession(target, 'markdown')
  if (!result) return
  try {
    await navigator.clipboard.writeText(result.content)
    copied.value = 'diagnostic'
    if (copiedTimer) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => { copied.value = '' }, 1600)
  } catch {
    store.error.value = '浏览器拒绝写入剪贴板，请使用下载按钮'
  }
}

async function downloadDiagnostic(format: 'markdown' | 'json') {
  const target = selectedId.value
  if (!target) return
  const result = await store.exportSession(target, format)
  if (!result) return
  const blob = new Blob([result.content], { type: result.contentType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = result.filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

watch(() => props.currentSessionId, async (value) => {
  await store.refresh()
  if (value) {
    selectedId.value = value
    await store.load(value)
  }
})

watch(() => store.sessions.value.length, async (length) => {
  if (!length || selectedId.value) return
  const first = store.sessions.value[0]
  if (first) {
    selectedId.value = first.id
    await store.load(first.id)
  }
})

onMounted(() => refreshAll())
onBeforeUnmount(() => {
  if (copiedTimer) clearTimeout(copiedTimer)
})
</script>

<template>
  <section class="session-panel">
    <div class="session-toolbar">
      <div class="session-heading">
        <div>
          <h2>调试会话</h2>
          <p>保留构建、验证、设备快照和错误证据，生成可交给 AI 的脱敏上下文。</p>
        </div>
        <UBadge color="gray" variant="subtle">{{ platformName }}</UBadge>
      </div>
      <div class="session-actions">
        <UButton
          color="gray"
          variant="soft"
          icon="i-heroicons-beaker"
          :loading="busy"
          :disabled="testDisabled"
          @click="emit('run', 'test')"
        >
          单元测试
        </UButton>
        <UButton
          color="gray"
          variant="soft"
          icon="i-heroicons-shield-check"
          :loading="busy"
          :disabled="busy"
          @click="emit('run', 'lint')"
        >
          静态检查
        </UButton>
        <UButton
          color="gray"
          variant="ghost"
          square
          icon="i-heroicons-arrow-path"
          :loading="store.loading.value || store.loadingDetail.value"
          aria-label="刷新调试会话"
          @click="refreshAll()"
        />
      </div>
    </div>

    <UAlert
      v-if="store.error.value"
      color="red"
      variant="soft"
      icon="i-heroicons-exclamation-circle"
      title="会话数据不可用"
      :description="store.error.value"
    />

    <div class="session-layout">
      <aside class="session-history">
        <div class="session-section-head">
          <span>最近会话</span>
          <UBadge color="gray" variant="subtle">{{ store.sessions.value.length }}</UBadge>
        </div>
        <AppEmptyState
          v-if="!store.sessions.value.length && !store.loading.value"
          class="session-history-empty"
          icon="i-heroicons-clock"
          title="还没有调试会话"
          description="运行构建、单元测试或静态检查后，记录会保存在本机。"
        />
        <button
          v-for="session in store.sessions.value"
          :key="session.id"
          type="button"
          class="session-history-item"
          :class="{ selected: selectedId === session.id }"
          @click="selectSession(session.id)"
        >
          <span class="session-history-line">
            <strong>{{ actionLabel(session.action) }}</strong>
            <UBadge :color="statusBadge(session.status).color" variant="subtle">
              {{ statusBadge(session.status).label }}
            </UBadge>
          </span>
          <span class="session-history-meta">
            {{ formatTime(session.createdAt) }}
            <template v-if="session.analysis.errorCount"> · {{ session.analysis.errorCount }} errors</template>
          </span>
          <code>{{ session.project.commit || session.id }}</code>
        </button>
        <p v-if="store.root.value" class="session-root">{{ store.root.value }}</p>
      </aside>

      <div class="session-detail">
        <AppEmptyState
          v-if="!selected && !store.loadingDetail.value"
          icon="i-heroicons-clipboard-document-check"
          title="选择一条会话"
          description="查看构建来源、测试结果、设备快照和诊断导出。"
        />
        <div v-else-if="selected" class="session-detail-body">
          <UCard>
            <template #header>
              <div class="session-detail-head">
                <div>
                  <div class="card-heading">
                    <span>{{ actionLabel(selected.action) }}</span>
                    <UBadge :color="statusBadge(selected.status).color" variant="subtle">
                      {{ statusBadge(selected.status).label }}
                    </UBadge>
                  </div>
                  <p>
                    {{ formatTime(selected.createdAt) }}
                    · {{ selected.configuration }}
                    · {{ selected.result.elapsed || 0 }}s
                  </p>
                </div>
                <div class="session-export-actions">
                  <UButton
                    color="gray"
                    variant="soft"
                    size="xs"
                    icon="i-heroicons-document-arrow-down"
                    :loading="store.exporting.value"
                    @click="downloadDiagnostic('markdown')"
                  >
                    Markdown
                  </UButton>
                  <UButton
                    color="gray"
                    variant="ghost"
                    size="xs"
                    icon="i-heroicons-code-bracket"
                    :disabled="store.exporting.value"
                    @click="downloadDiagnostic('json')"
                  >
                    JSON
                  </UButton>
                </div>
              </div>
            </template>

            <div class="session-metrics">
              <div>
                <span>错误</span>
                <strong :class="{ danger: selected.analysis.errorCount }">{{ selected.analysis.errorCount }}</strong>
              </div>
              <div>
                <span>警告</span>
                <strong>{{ selected.analysis.warningCount }}</strong>
              </div>
              <div>
                <span>日志行</span>
                <strong>{{ selected.analysis.lineCount }}</strong>
              </div>
              <div>
                <span>设备快照</span>
                <strong>{{ selected.snapshots.length }}</strong>
              </div>
            </div>

            <div class="session-project-grid">
              <div class="context-field">
                <span>项目</span>
                <code>{{ selected.project.displayName || selected.project.repoName || '-' }}</code>
              </div>
              <div class="context-field">
                <span>分支</span>
                <code>{{ selected.project.branch || '-' }}</code>
              </div>
              <div class="context-field">
                <span>提交</span>
                <code>{{ selected.project.commit || '-' }}</code>
              </div>
              <div class="context-field">
                <span>工作区</span>
                <code :class="{ warning: selected.project.dirty }">
                  {{ selected.project.dirty ? `${selected.project.changedFiles || 0} 个已修改文件` : '干净' }}
                </code>
              </div>
              <div class="context-field">
                <span>产物</span>
                <code>{{ selected.artifact.name || '-' }}</code>
              </div>
              <div class="context-field">
                <span>设备</span>
                <code>{{ selected.device.name || '-' }}</code>
              </div>
            </div>

            <div v-if="selected.project.submodules?.length" class="session-submodules">
              <div class="session-section-head">
                <span>子模块</span>
                <UBadge color="gray" variant="subtle">{{ selected.project.submodules.length }}</UBadge>
              </div>
              <div
                v-for="submodule in selected.project.submodules"
                :key="submodule.path"
                class="session-submodule-row"
              >
                <code>{{ submodule.path }}</code>
                <span>{{ submodule.branch || 'detached' }}</span>
                <code>{{ submodule.commit.slice(0, 12) }}</code>
                <UBadge
                  :color="submodule.conflicted ? 'red' : submodule.modified || submodule.dirty ? 'amber' : 'green'"
                  variant="subtle"
                >
                  {{ submodule.conflicted ? '冲突' : submodule.modified || submodule.dirty ? '有变化' : '正常' }}
                </UBadge>
              </div>
            </div>

            <div class="session-evidence-actions">
              <UButton
                color="gray"
                variant="soft"
                icon="i-heroicons-camera"
                :loading="store.savingSnapshot.value"
                :disabled="!deviceContext || selected.status === 'running'"
                @click="saveSnapshot"
              >
                保存当前设备快照
              </UButton>
              <UButton
                icon="i-heroicons-clipboard-document-check"
                :loading="store.exporting.value"
                @click="copyDiagnostic"
              >
                {{ copied === 'diagnostic' ? '已复制脱敏上下文' : '复制 AI 上下文' }}
              </UButton>
            </div>
          </UCard>

          <div class="session-evidence-grid">
            <UCard>
              <template #header>
                <div class="card-heading">
                  <span>源码位置</span>
                  <UBadge color="gray" variant="subtle">
                    {{ selected.analysis.sourceLocations?.length || 0 }}
                  </UBadge>
                </div>
              </template>
              <div v-if="selected.analysis.sourceLocations?.length" class="stack-list">
                <div
                  v-for="(location, index) in selected.analysis.sourceLocations"
                  :key="location"
                  class="stack-row source-stack-row"
                >
                  <span>{{ index + 1 }}</span>
                  <button
                    type="button"
                    class="source-location-button"
                    :title="location"
                    @click="emit('view-source', location)"
                  >
                    <code>{{ location }}</code>
                  </button>
                  <UButton
                    color="gray"
                    variant="ghost"
                    size="xs"
                    square
                    icon="i-heroicons-document-magnifying-glass"
                    @click="emit('view-source', location)"
                  />
                </div>
              </div>
              <div v-else class="small-empty">这条会话没有解析到源码文件行号。</div>
            </UCard>

            <UCard>
              <template #header>
                <div class="card-heading">
                  <span>错误聚合</span>
                  <UBadge color="gray" variant="subtle">
                    {{ selected.analysis.errorGroups?.length || 0 }}
                  </UBadge>
                </div>
              </template>
              <div v-if="selected.analysis.errorGroups?.length" class="session-error-groups">
                <div
                  v-for="group in selected.analysis.errorGroups"
                  :key="group.fingerprint"
                  class="session-error-group"
                >
                  <UBadge color="red" variant="subtle">x{{ group.count }}</UBadge>
                  <code>{{ redactSensitive(group.sample) }}</code>
                </div>
              </div>
              <div v-else class="small-empty">没有发现错误。</div>
            </UCard>
          </div>

          <UCard v-if="selected.analysis.summaries?.length">
            <template #header>
              <div class="card-heading">
                <span>验证摘要</span>
                <UBadge color="gray" variant="subtle">
                  {{ selected.analysis.summaries.length }}
                </UBadge>
              </div>
            </template>
            <div class="session-validation-summaries">
              <code
                v-for="summary in selected.analysis.summaries"
                :key="summary"
              >
                {{ redactSensitive(summary) }}
              </code>
            </div>
          </UCard>

          <UCard v-if="selected.snapshots.length">
            <template #header>
              <div class="card-heading">
                <span>设备快照</span>
                <span class="muted">最近 {{ selected.snapshots.length }} 次</span>
              </div>
            </template>
            <div class="session-snapshot-row">
              <div>
                <strong>{{ selected.snapshots.at(-1)?.context.app.environment.site || '-' }}</strong>
                <span>{{ selected.snapshots.at(-1)?.context.app.environment.country || '-' }}</span>
              </div>
              <div>
                <strong>{{ selected.snapshots.at(-1)?.context.app.environment.name || 'unknown' }}</strong>
                <span>App 环境</span>
              </div>
              <div>
                <strong>{{ selected.snapshots.at(-1)?.context.app.experiments.length || 0 }}</strong>
                <span>进组实验</span>
              </div>
              <div>
                <strong>{{ formatTime(selected.snapshots.at(-1)?.capturedAt) }}</strong>
                <span>采集时间</span>
              </div>
            </div>
            <div v-if="snapshotDiff" class="session-diff">
              <div class="session-section-head">
                <span>最近两次快照变化</span>
                <UBadge
                  :color="snapshotDiff.changes.length || snapshotDiff.experimentChanges.length ? 'amber' : 'green'"
                  variant="subtle"
                >
                  {{ snapshotDiff.changes.length + snapshotDiff.experimentChanges.length }}
                </UBadge>
              </div>
              <div
                v-for="change in snapshotDiff.changes"
                :key="change.field"
                class="session-diff-row"
              >
                <strong>{{ change.field }}</strong>
                <code>{{ change.before }}</code>
                <span>→</span>
                <code>{{ change.after }}</code>
              </div>
              <div
                v-for="change in snapshotDiff.experimentChanges"
                :key="change.key"
                class="session-diff-row"
              >
                <strong>{{ change.kind }} {{ change.key }}</strong>
                <code>{{ change.before }}</code>
                <span>→</span>
                <code>{{ change.after }}</code>
              </div>
              <div
                v-if="!snapshotDiff.changes.length && !snapshotDiff.experimentChanges.length"
                class="small-empty"
              >
                最近两次设备快照没有变化。
              </div>
            </div>
          </UCard>
        </div>
      </div>

      <aside class="session-routes">
        <div class="session-section-head">
          <span>路由清单</span>
          <UBadge color="gray" variant="subtle">{{ store.routes.value?.count || 0 }}</UBadge>
        </div>
        <p>只读解析 {{ platformName }} 仓库现有路由，用于检查 Deep Link 是否仍然存在。</p>
        <div v-if="store.routes.value?.routes.length" class="session-route-list">
          <code
            v-for="route in store.routes.value.routes.slice(0, 40)"
            :key="`${route.pattern}-${route.source}`"
            :title="route.source"
          >
            {{ route.pattern }}
          </code>
        </div>
        <div v-else class="small-empty">暂未读取到路由。</div>
        <UAlert
          v-if="store.routes.value?.warnings.length"
          color="amber"
          variant="soft"
          icon="i-heroicons-exclamation-triangle"
          :description="store.routes.value.warnings.join('；')"
        />
      </aside>
    </div>
  </section>
</template>

