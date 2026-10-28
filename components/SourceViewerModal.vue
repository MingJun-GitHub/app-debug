<script setup lang="ts">
import { redactSensitive } from '~/composables/redaction'

interface SourceLine {
  n: number
  text: string
}

interface SourceResult {
  path: string
  relativePath: string
  requestedPath: string
  language: string
  line: number
  startLine: number
  endLine: number
  totalLines: number
  lines: SourceLine[]
}

const props = defineProps<{
  modelValue: boolean
  platform: 'ios' | 'android'
  path: string
  line: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
const result = ref<SourceResult | null>(null)
const loading = ref(false)
const error = ref('')
const copied = ref('')
let copyTimer: ReturnType<typeof setTimeout> | undefined

async function load() {
  if (!props.path) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const params = new URLSearchParams({
      path: props.path,
      line: String(props.line || 1),
      context: '18'
    })
    const response = await fetch(`/api/${props.platform}/source?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
    result.value = data
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取源码失败'
  } finally {
    loading.value = false
  }
}

async function copyText(kind: string, value: string) {
  const text = redactSensitive(value)
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copied.value = kind
  if (copyTimer) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copied.value = '' }, 1600)
}

const codeText = computed(() =>
  result.value?.lines.map(line => line.text).join('\n') || ''
)

watch(
  () => [props.modelValue, props.platform, props.path, props.line],
  ([visible]) => {
    if (visible) load()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<template>
  <UModal v-model="open" :ui="{ width: 'sm:max-w-6xl' }">
    <UCard>
      <template #header>
        <div class="source-viewer-head">
          <div class="source-viewer-title">
            <UIcon name="i-heroicons-code-bracket-square" />
            <div>
              <strong>源码位置</strong>
              <span>{{ result?.relativePath || path }}</span>
            </div>
          </div>
          <div class="source-viewer-actions">
            <UBadge v-if="result" color="gray" variant="subtle">
              {{ result.language }} · {{ result.totalLines }} 行
            </UBadge>
            <UTooltip text="复制源码窗口">
              <UButton
                color="gray"
                variant="soft"
                size="xs"
                :icon="copied === 'code' ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                :disabled="!result"
                @click="copyText('code', codeText)"
              >
                复制代码
              </UButton>
            </UTooltip>
            <UButton
              color="gray"
              variant="ghost"
              square
              icon="i-heroicons-x-mark"
              aria-label="关闭源码查看器"
              @click="open = false"
            />
          </div>
        </div>
      </template>

      <div v-if="loading" class="source-viewer-state">
        <UIcon name="i-heroicons-arrow-path" class="spinning" />
        <span>正在读取项目源码</span>
      </div>
      <div v-else-if="error" class="source-viewer-state error">
        <UIcon name="i-heroicons-exclamation-triangle" />
        <span>{{ error }}</span>
        <UButton color="gray" variant="soft" icon="i-heroicons-arrow-path" @click="load">
          重试
        </UButton>
      </div>
      <div v-else-if="result" class="source-viewer-code">
        <div
          v-for="row in result.lines"
          :key="row.n"
          class="source-code-row"
          :class="{ current: row.n === result.line }"
        >
          <span class="source-line-number">{{ row.n }}</span>
          <code>{{ row.text || ' ' }}</code>
        </div>
      </div>

      <template #footer>
        <div class="source-viewer-footer">
          <code>{{ result?.path || path }}</code>
          <div class="toolbar-spacer" />
          <UButton
            color="gray"
            variant="ghost"
            icon="i-heroicons-clipboard"
            :disabled="!result"
            @click="copyText('path', result?.path || path)"
          >
            {{ copied === 'path' ? '已复制路径' : '复制路径' }}
          </UButton>
        </div>
      </template>
    </UCard>
  </UModal>
</template>

