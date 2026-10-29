<script setup lang="ts">
import type {
  ValidationKind,
  ValidationState,
  ValidationStatus
} from '~/composables/useValidationRunner'

const props = defineProps<{
  platform: 'ios' | 'android'
  configuration: string
  states: Record<ValidationKind, ValidationState>
  activeKind: ValidationKind
  runBusy: boolean
  deviceAvailable: boolean
  copiedTarget: string
}>()

const emit = defineEmits<{
  'update:activeKind': [value: ValidationKind]
  run: [kind: ValidationKind]
  stop: []
  clear: [kind: ValidationKind]
  copy: [target: string, text: string]
  'view-source': [location: string]
}>()

const activeState = computed(() => props.states[props.activeKind])
const anyValidationRunning = computed(() =>
  props.states.test.status === 'running' || props.states.lint.status === 'running'
)
const sourceLocations = computed(() => {
  const pattern = /((?:[A-Za-z0-9_.@+-]+\/)*[A-Za-z0-9_.@+-]+\.(?:swift|m|mm|kt|kts|java|c|cc|cpp|h|hpp):\d+)/g
  const values = new Set<string>()
  for (const line of activeState.value.lines) {
    for (const match of line.text.matchAll(pattern)) values.add(match[1])
  }
  return [...values]
})

const actions: Array<{
  kind: ValidationKind
  label: string
  title: string
  icon: string
  description: string
}> = [
  {
    kind: 'test',
    label: '单元测试',
    title: '运行单元测试',
    icon: 'i-heroicons-beaker',
    description: '执行仓库现有的单元测试入口，并保留完整输出和会话。'
  },
  {
    kind: 'lint',
    label: '静态检查',
    title: '运行静态检查',
    icon: 'i-heroicons-shield-check',
    description: '执行现有 lint / analyze，不修改业务工程配置。'
  }
]

function statusMeta(status: ValidationStatus) {
  if (status === 'running') return { label: '运行中', color: 'blue' as const }
  if (status === 'success') return { label: '通过', color: 'green' as const }
  if (status === 'error') return { label: '失败', color: 'red' as const }
  if (status === 'cancelled') return { label: '已停止', color: 'amber' as const }
  return { label: '未运行', color: 'gray' as const }
}

function canRun(kind: ValidationKind) {
  if (props.runBusy || anyValidationRunning.value) return false
  if (kind === 'test' && props.platform === 'ios' && !props.deviceAvailable) return false
  return true
}

function run(kind: ValidationKind) {
  emit('update:activeKind', kind)
  emit('run', kind)
}

function iconFor(lineKind: ValidationState['lines'][number]['kind']) {
  if (lineKind === 'error') return 'i-heroicons-x-circle'
  if (lineKind === 'warning') return 'i-heroicons-exclamation-triangle'
  if (lineKind === 'success') return 'i-heroicons-check-circle'
  if (lineKind === 'command') return 'i-heroicons-chevron-right'
  return 'i-heroicons-minus'
}

function sourceParts(location: string) {
  const match = location.match(/^(.*):(\d+)$/)
  return { path: match?.[1] || location, line: Number(match?.[2] || 1) }
}
</script>

<template>
  <section class="validation-pane">
    <div class="validation-head">
      <div>
        <h2>验证工作区</h2>
        <p>单元测试和静态检查使用独立日志、独立会话，不占用运行面板。</p>
      </div>
      <div class="validation-head-meta">
        <UBadge color="gray" variant="subtle">{{ configuration }}</UBadge>
        <UBadge
          v-if="anyValidationRunning"
          color="blue"
          variant="subtle"
        >
          验证运行中
        </UBadge>
      </div>
    </div>

    <div class="validation-action-grid">
      <UCard
        v-for="action in actions"
        :key="action.kind"
        class="validation-action-card"
        :class="{ selected: activeKind === action.kind }"
      >
        <div class="validation-action-main">
          <div class="validation-action-icon">
            <UIcon :name="action.icon" />
          </div>
          <div class="validation-action-copy">
            <div>
              <strong>{{ action.label }}</strong>
              <UBadge
                :color="statusMeta(states[action.kind].status).color"
                variant="subtle"
              >
                {{ statusMeta(states[action.kind].status).label }}
              </UBadge>
            </div>
            <p>{{ action.description }}</p>
            <span v-if="states[action.kind].sessionId">
              Session {{ states[action.kind].sessionId.slice(0, 12) }}
              · {{ states[action.kind].elapsed }}s
            </span>
          </div>
        </div>
        <div class="validation-action-footer">
          <UButton
            :color="activeKind === action.kind ? 'primary' : 'gray'"
            :variant="activeKind === action.kind ? 'soft' : 'ghost'"
            icon="i-heroicons-play"
            :disabled="!canRun(action.kind)"
            :loading="states[action.kind].status === 'running'"
            @click="run(action.kind)"
          >
            {{ action.title }}
          </UButton>
          <UButton
            color="gray"
            variant="ghost"
            icon="i-heroicons-document-text"
            @click="emit('update:activeKind', action.kind)"
          >
            查看日志
          </UButton>
        </div>
      </UCard>
    </div>

    <UCard class="validation-console-card" :ui="{ body: { padding: 'p-0 sm:p-0' } }">
      <template #header>
        <div class="validation-console-head">
          <div class="validation-console-tabs">
            <button
              v-for="action in actions"
              :key="action.kind"
              type="button"
              :class="{ active: activeKind === action.kind }"
              @click="emit('update:activeKind', action.kind)"
            >
              {{ action.label }}
              <UBadge
                :color="statusMeta(states[action.kind].status).color"
                variant="subtle"
              >
                {{ statusMeta(states[action.kind].status).label }}
              </UBadge>
            </button>
          </div>
          <div class="toolbar-spacer" />
          <span class="event-summary">
            {{ activeState.lines.length }} 条日志
            <template v-if="activeState.status === 'running'"> · {{ activeState.elapsed }}s</template>
          </span>
          <UButton
            color="gray"
            variant="ghost"
            size="xs"
            square
            icon="i-heroicons-clipboard"
            :disabled="!activeState.lines.length"
            aria-label="复制验证日志"
            @click="emit('copy', `validation-${activeKind}`, activeState.lines.map(line => line.text).join('\n'))"
          />
          <UButton
            color="gray"
            variant="ghost"
            size="xs"
            square
            icon="i-heroicons-trash"
            :disabled="!activeState.lines.length || activeState.status === 'running'"
            aria-label="清空验证日志"
            @click="emit('clear', activeKind)"
          />
          <UButton
            v-if="activeState.status === 'running'"
            color="red"
            variant="soft"
            size="xs"
            icon="i-heroicons-stop"
            @click="emit('stop')"
          >
            停止
          </UButton>
        </div>
      </template>

      <div v-if="sourceLocations.length" class="validation-sources">
        <span>源码位置</span>
        <button
          v-for="location in sourceLocations"
          :key="location"
          type="button"
          :title="sourceParts(location).path"
          @click="emit('view-source', location)"
        >
          {{ location }}
        </button>
      </div>

      <div v-if="activeState.error" class="validation-error">
        <UIcon name="i-heroicons-exclamation-circle" />
        <span>{{ activeState.error }}</span>
      </div>
      <AppEmptyState
        v-if="!activeState.lines.length"
        class="validation-empty"
        icon="i-heroicons-command-line"
        :title="activeState.status === 'running' ? '正在等待验证输出' : `尚未运行${activeKind === 'test' ? '单元测试' : '静态检查'}`"
        description="运行后完整日志会保留在当前验证面板和调试会话中。"
      />
      <div v-else class="event-console validation-console">
        <div
          v-for="line in activeState.lines"
          :key="line.id"
          class="event-row"
          :class="`event-${line.kind}`"
        >
          <span class="event-time">{{ line.time }}</span>
          <UIcon :name="iconFor(line.kind)" class="event-icon" />
          <span class="event-text">{{ line.text }}</span>
          <UButton
            color="gray"
            variant="ghost"
            size="xs"
            square
            icon="i-heroicons-clipboard"
            aria-label="复制这条验证日志"
            @click="emit('copy', `validation-line-${line.id}`, line.text)"
          />
        </div>
      </div>
    </UCard>
  </section>
</template>

