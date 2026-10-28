<script setup lang="ts">
import type { LogFilter } from '~/types/log-filter'
import { highlightSegments, type HighlightPattern } from '~/utils/log-highlight'

const props = defineProps<{
  platformName: string
  selectedFilter: LogFilter
  keywordQuery: string
  logs: Array<{ n: number, text: string }>
  logMeta: string
  copiedTarget: string
  highlightPatterns: HighlightPattern[]
}>()

const emit = defineEmits<{
  'update:selectedFilter': [value: LogFilter]
  'update:keywordQuery': [value: string]
  search: []
  copy: [target: string, text: string]
}>()

const selectedFilter = computed({
  get: () => props.selectedFilter,
  set: value => emit('update:selectedFilter', value)
})
const keywordQuery = computed({
  get: () => props.keywordQuery,
  set: value => emit('update:keywordQuery', value)
})
const emptyTitle = computed(() => {
  if (props.logMeta === '尚未搜索') return '尚未搜索日志'
  if (/不存在|失败|错误|not found/i.test(props.logMeta)) return '日志暂不可用'
  return '没有匹配的日志'
})
const emptyDescription = computed(() => {
  if (props.logMeta === '尚未搜索') {
    return `输入关键字后搜索 ${props.platformName} decoded.log。`
  }
  if (/不存在|失败|错误|not found/i.test(props.logMeta)) return props.logMeta
  return '调整关键字或正则条件后重试。'
})
</script>

<template>
  <section class="pane">
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
        @keydown.enter="emit('search')"
      />
      <UButton
        icon="i-heroicons-magnifying-glass"
        :disabled="!selectedFilter.query && !keywordQuery.trim()"
        @click="emit('search')"
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
          @click="emit('copy', 'all-logs', logs.map(line => line.text).join('\n'))"
        />
      </UTooltip>
    </div>
    <AppEmptyState
      v-if="!logs.length"
      class="pane-body"
      :icon="emptyTitle === '日志暂不可用' ? 'i-heroicons-exclamation-triangle' : 'i-heroicons-document-magnifying-glass'"
      :title="emptyTitle"
      :description="emptyDescription"
    />
    <div v-else class="log-result pane-body">
      <div v-for="line in logs" :key="line.n" class="log-line">
        <span class="log-no">{{ line.n }}</span>
        <code>
          <template
            v-for="(segment, index) in highlightSegments(line.text, highlightPatterns)"
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
            @click="emit('copy', `log-${line.n}`, line.text)"
          />
        </UTooltip>
      </div>
    </div>
    <div v-if="logs.length" class="log-meta">{{ logMeta }}</div>
  </section>
</template>

