<script setup lang="ts">
import type { DebugEvent } from '~/composables/useDebugRunner'
import type { LogFilter } from '~/types/log-filter'
import { highlightSegments, type HighlightPattern } from '~/utils/log-highlight'

type SeverityFilter = 'all' | 'error' | 'warning' | 'network'

const props = defineProps<{
  platformName: string
  runDotClass: string
  runLabel: string
  busy: boolean
  elapsed: number
  events: DebugEvent[]
  filteredEvents: DebugEvent[]
  severity: SeverityFilter
  severityOptions: Array<{ key: SeverityFilter, label: string }>
  errorCount: number
  warningCount: number
  selectedFilter: LogFilter
  keywordQuery: string
  activeDeviceAvailable: boolean
  copiedTarget: string
  highlightPatterns: HighlightPattern[]
}>()

const emit = defineEmits<{
  'update:severity': [value: SeverityFilter]
  'update:selectedFilter': [value: LogFilter]
  'update:keywordQuery': [value: string]
  run: [action: string]
  copy: [target: string, text: string]
}>()

const eventConsole = ref<HTMLElement | null>(null)

const selectedFilter = computed({
  get: () => props.selectedFilter,
  set: value => emit('update:selectedFilter', value)
})
const keywordQuery = computed({
  get: () => props.keywordQuery,
  set: value => emit('update:keywordQuery', value)
})

function eventClass(event: DebugEvent) {
  return `event-row event-${event.kind}`
}

function iconFor(event: DebugEvent) {
  if (event.kind === 'error') return 'i-heroicons-x-circle'
  if (event.kind === 'warning') return 'i-heroicons-exclamation-triangle'
  if (event.kind === 'success') return 'i-heroicons-check-circle'
  if (event.kind === 'command') return 'i-heroicons-chevron-right'
  return 'i-heroicons-minus'
}

watch(() => props.events.length, async () => {
  await nextTick()
  if (eventConsole.value) eventConsole.value.scrollTop = eventConsole.value.scrollHeight
})
</script>

<template>
  <section class="pane">
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
          color="gray"
          variant="ghost"
          size="xs"
          :class="{ 'filter-chip-active': severity === item.key }"
          @click="emit('update:severity', item.key)"
        >
          {{ item.label }}
          <span v-if="item.key === 'error' && errorCount" class="filter-count">{{ errorCount }}</span>
          <span v-else-if="item.key === 'warning' && warningCount" class="filter-count">{{ warningCount }}</span>
        </UButton>
      </div>
      <span class="event-summary">{{ filteredEvents.length }} / {{ events.length }} 条</span>
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
        placeholder="搜索日志"
        class="keyword-filter"
      />
      <UButton
        color="gray"
        variant="ghost"
        icon="i-heroicons-arrow-path"
        :loading="busy"
        :disabled="busy || !activeDeviceAvailable"
        @click="emit('run', 'log')"
      >
        启动并跟随
        <kbd class="shortcut-key">⌘D</kbd>
      </UButton>
    </div>

    <AppEmptyState
      v-if="!events.length"
      class="pane-body"
      icon="i-heroicons-command-line"
      label="运行输出"
      meta="stdout"
      title="等待运行输出"
      :description="activeDeviceAvailable
        ? `点击「构建并启动」，${platformName} 日志会实时写入这里。`
        : `连接并授权 ${platformName} 设备后，构建、安装与日志会显示在这里。`"
    />
    <AppEmptyState
      v-else-if="!filteredEvents.length"
      class="pane-body"
      icon="i-heroicons-funnel"
      label="运行输出"
      meta="filtered"
      title="没有匹配记录"
      description="调整关键字或筛选条件后重试。"
    />
    <div v-else ref="eventConsole" class="event-console">
      <div
        v-for="event in filteredEvents"
        :key="event.id"
        :class="eventClass(event)"
      >
        <span class="event-time">{{ event.time }}</span>
        <UIcon :name="iconFor(event)" class="event-icon" />
        <span class="event-text">
          <template
            v-for="(segment, index) in highlightSegments(event.text, highlightPatterns)"
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
            @click="emit('copy', `event-${event.id}`, event.text)"
          />
        </UTooltip>
      </div>
    </div>
  </section>
</template>

