<script setup lang="ts">
import type { DebugEvent } from '~/composables/useDebugRunner'

const props = defineProps<{
  errors: DebugEvent[]
  callStack: string[]
  firstError: string
  latestEvents: DebugEvent[]
  jobDone: boolean
  copiedTarget: string
}>()

const emit = defineEmits<{
  copy: [target: string, text: string]
  'view-source': [location: string]
}>()

function sourceParts(location: string) {
  const match = location.match(/^(.*):(\d+)$/)
  return {
    path: match?.[1] || location,
    line: Number(match?.[2] || 1)
  }
}
</script>

<template>
  <section class="pane">
    <div class="pane-toolbar">
      <div class="run-status">
        <UIcon name="i-heroicons-exclamation-triangle" />
        <span>当前问题</span>
      </div>
      <div class="toolbar-spacer" />
      <UTooltip text="复制全部错误、调用栈和最近上下文">
        <UButton
          color="gray"
          variant="ghost"
          size="xs"
          square
          :icon="copiedTarget === 'all-errors' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
          aria-label="复制全部错误信息"
          :disabled="!errors.length"
          @click="emit('copy', 'all-errors', [
            'Errors:',
            ...errors.map(event => `[${event.time}] ${event.text}`),
            '',
            'Source locations:',
            ...callStack,
            '',
            'Recent context:',
            ...latestEvents.map(event => `[${event.time}] ${event.text}`)
          ].join('\n'))"
        />
      </UTooltip>
      <span class="event-summary">{{ errors.length }} 个错误 · {{ callStack.length }} 个源码位置</span>
    </div>

    <div v-if="errors.length" class="issues-layout pane-body">
      <UAlert
        color="red"
        variant="soft"
        icon="i-heroicons-exclamation-circle"
        title="本次运行发现错误"
        :description="firstError"
      />

      <div class="issue-grid">
        <UCard>
          <template #header>
            <div class="card-heading">
              <span>错误事件</span>
              <UBadge color="red" variant="subtle">{{ errors.length }}</UBadge>
            </div>
          </template>
          <div class="issue-lines">
            <div v-for="event in errors" :key="event.id" class="issue-line">
              <span class="issue-time">{{ event.time }}</span>
              <pre>{{ event.text }}</pre>
              <UTooltip text="复制这条错误">
                <UButton
                  color="gray"
                  variant="ghost"
                  size="xs"
                  square
                  :icon="copiedTarget === `error-${event.id}` ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                  aria-label="复制这条错误"
                  @click="emit('copy', `error-${event.id}`, event.text)"
                />
              </UTooltip>
            </div>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <div class="card-heading">
              <span>源码位置</span>
              <UBadge color="gray" variant="subtle">{{ callStack.length }}</UBadge>
            </div>
          </template>
          <div v-if="callStack.length" class="stack-list">
            <div
              v-for="(frame, index) in callStack"
              :key="frame"
              class="stack-row source-stack-row"
            >
              <span>{{ index + 1 }}</span>
              <button
                type="button"
                class="source-location-button"
                :title="sourceParts(frame).path"
                @click="emit('view-source', frame)"
              >
                <code>{{ frame }}</code>
              </button>
              <UTooltip text="查看源码">
                <UButton
                  color="gray"
                  variant="ghost"
                  size="xs"
                  square
                  icon="i-heroicons-document-magnifying-glass"
                  aria-label="查看源码"
                  @click="emit('view-source', frame)"
                />
              </UTooltip>
            </div>
          </div>
          <div v-else class="small-empty">
            本次错误没有解析到文件行号，可切换到日志 Tab 查看完整上下文。
          </div>
        </UCard>
      </div>

      <UCard>
        <template #header>
          <div class="card-heading">
            <span>最近上下文</span>
            <span class="muted">最后 80 条</span>
          </div>
        </template>
        <div class="context-log">
          <div v-for="event in latestEvents" :key="event.id">
            <span>{{ event.time }}</span>
            <code>{{ event.text }}</code>
          </div>
        </div>
      </UCard>
    </div>
    <AppEmptyState
      v-else
      class="pane-body"
      icon="i-heroicons-shield-check"
      title="当前运行没有错误"
      :description="jobDone ? '构建和启动日志中尚未发现错误。' : '运行结束后这里会显示错误与源码位置。'"
    />
  </section>
</template>

