<script setup lang="ts">
import type { DeviceContext } from '~/composables/useDebugRunner'
import { redactSensitive } from '~/composables/redaction'

const props = defineProps<{
  platform: 'ios' | 'android'
  context: DeviceContext | null
  loading: boolean
  error: string
  deviceAvailable: boolean
}>()

const emit = defineEmits<{
  refresh: []
  screenshot: []
}>()

const query = ref('')
const copiedTarget = ref('')
let copyTimer: ReturnType<typeof setTimeout> | undefined

const platformName = computed(() => props.platform === 'ios' ? 'iOS' : 'Android')
const experiments = computed(() => {
  const context = props.context
  if (!context) return []
  return [...context.app.experiments, ...context.app.outExperiments]
})
const filteredExperiments = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return experiments.value
  return experiments.value.filter(experiment =>
    experiment.key.toLowerCase().includes(needle)
    || experiment.group.toLowerCase().includes(needle)
    || experiment.experimentId.toLowerCase().includes(needle)
  )
})
const state = computed(() => {
  if (props.loading) return { label: '读取中', color: 'blue' as const }
  if (props.error) return { label: '读取失败', color: 'red' as const }
  if (!props.context?.app.available) return { label: '仅设备信息', color: 'amber' as const }
  if (props.context.cached) return { label: '缓存', color: 'gray' as const }
  return { label: '已读取', color: 'green' as const }
})
const environmentBadge = computed(() => {
  const name = props.context?.app.environment.name
  if (name === 'test') return { label: '测试环境', color: 'amber' as const }
  if (name === 'production') return { label: '线上环境', color: 'green' as const }
  return { label: '环境未知', color: 'gray' as const }
})
const contextCopyText = computed(() => {
  const context = props.context
  if (!context) return ''
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
    ...experiments.value.map(experiment =>
      `${experiment.state === 'out' ? '[出组] ' : '[进组] '}${experiment.key} -> ${experiment.group}`
    )
  ].join('\n')
})

async function copyText(target: string, text: string) {
  if (!text.trim()) return
  try {
    await navigator.clipboard.writeText(redactSensitive(text))
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = redactSensitive(text)
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

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<template>
  <section class="pane device-context-pane">
    <div class="pane-toolbar">
      <div class="run-status">
        <UIcon name="i-heroicons-device-phone-mobile" />
        <span>设备上下文</span>
        <UBadge :color="state.color" variant="subtle">
          {{ state.label }}
        </UBadge>
      </div>
      <div class="toolbar-spacer" />
      <UInput
        v-model="query"
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
          :loading="loading"
          aria-label="重新读取设备上下文"
          @click="emit('refresh')"
        />
      </UTooltip>
      <UTooltip text="复制脱敏后的设备与 AB 上下文">
        <UButton
          color="gray"
          variant="ghost"
          square
          :icon="copiedTarget === 'device-context' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
          :disabled="!context"
          aria-label="复制设备与 AB 上下文"
          @click="copyText('device-context', contextCopyText)"
        />
      </UTooltip>
      <UButton
        color="gray"
        variant="soft"
        icon="i-heroicons-camera"
        :disabled="!deviceAvailable"
        @click="emit('screenshot')"
      >
        截图预览
        <kbd class="shortcut-key">⇧⌘S</kbd>
      </UButton>
    </div>

    <AppEmptyState
      v-if="loading && !context"
      class="pane-body"
      icon="i-heroicons-arrow-path"
      title="正在读取设备上下文"
      description="正在读取 App 已保存的环境、身份和设备缓存。"
    />
    <AppEmptyState
      v-else-if="error && !context"
      class="pane-body"
      icon="i-heroicons-exclamation-triangle"
      title="设备上下文读取失败"
      :description="error"
    >
      <UButton
        color="gray"
        variant="soft"
        icon="i-heroicons-arrow-path"
        @click="emit('refresh')"
      >
        重试
      </UButton>
    </AppEmptyState>
    <AppEmptyState
      v-else-if="!context"
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
              <UBadge :color="context.device.connected ? 'green' : 'red'" variant="subtle">
                {{ context.device.connected ? '已连接' : '未连接' }}
              </UBadge>
            </div>
          </template>
          <div class="context-fields">
            <div class="context-field">
              <span>设备</span>
              <code>{{ context.device.name || '-' }}</code>
            </div>
            <div class="context-field">
              <span>UDID</span>
              <code>{{ context.device.udid || '-' }}</code>
              <UButton
                v-if="context.device.udid"
                color="gray"
                variant="ghost"
                size="xs"
                square
                :icon="copiedTarget === 'device-udid' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                aria-label="复制设备 UDID"
                @click="copyText('device-udid', context.device.udid)"
              />
            </div>
            <div class="context-field">
              <span>型号 / 系统</span>
              <code>{{ context.device.model || '-' }} · {{ platformName }} {{ context.device.os || '?' }}</code>
            </div>
            <div class="context-field">
              <span>构建配置</span>
              <code>{{ context.device.buildConfiguration }}</code>
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
              <code>{{ context.app.environment.site || '-' }}</code>
            </div>
            <div class="context-field">
              <span>地区</span>
              <code>{{ context.app.environment.country || '-' }}</code>
            </div>
            <div class="context-field">
              <span>App device_id</span>
              <code>{{ context.app.ids.deviceId || '-' }}</code>
              <UButton
                v-if="context.app.ids.deviceId"
                color="gray"
                variant="ghost"
                size="xs"
                square
                :icon="copiedTarget === 'app-device-id' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                aria-label="复制 App device_id"
                @click="copyText('app-device-id', context.app.ids.deviceId)"
              />
            </div>
            <div class="context-field">
              <span>Distinct ID</span>
              <code>{{ context.app.ids.distinctId || '-' }}</code>
              <UButton
                v-if="context.app.ids.distinctId"
                color="gray"
                variant="ghost"
                size="xs"
                square
                :icon="copiedTarget === 'distinct-id' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                aria-label="复制 Distinct ID"
                @click="copyText('distinct-id', context.app.ids.distinctId)"
              />
            </div>
          </div>
        </UCard>
      </div>

      <UAlert
        v-if="!context.app.available || context.app.warnings.length"
        color="amber"
        variant="soft"
        icon="i-heroicons-information-circle"
        :title="context.app.available ? '部分缓存未读取' : 'App 调试缓存不可用'"
        :description="context.app.warnings.join('；') || '打开 App 后再刷新。'"
      />

      <UCard class="experiment-card">
        <template #header>
          <div class="context-card-heading">
            <div>
              <span>AB 实验分组</span>
              <p>
                {{ filteredExperiments.length }} / {{ experiments.length }} 条
                <template v-if="context.app.snapshotAt"> · 快照 {{ context.app.snapshotAt }}</template>
              </p>
            </div>
            <UBadge color="primary" variant="subtle">
              {{ experiments.filter(item => item.state === 'in').length }} 进组
            </UBadge>
          </div>
        </template>

        <div v-if="filteredExperiments.length" class="experiment-list">
          <div
            v-for="experiment in filteredExperiments"
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
            <strong>{{ experiments.length ? '没有匹配实验' : '暂未读取到 AB 分组' }}</strong>
            <p>{{ experiments.length ? '调整关键词后重试。' : '打开 App 实验室或触发 AB 请求，然后点击刷新。' }}</p>
          </div>
        </div>
      </UCard>
    </div>
  </section>
</template>

