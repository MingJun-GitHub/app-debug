<script setup lang="ts">
interface RouteItem {
  pattern: string
  kind: string
  source: string
  line: number | null
}

interface RouteInventory {
  platform: 'ios' | 'android'
  project: string
  count: number
  routes: RouteItem[]
  warnings: string[]
}

const props = defineProps<{
  modelValue: boolean
  platform: 'ios' | 'android'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
const inventory = ref<RouteInventory | null>(null)
const query = ref('')
const loading = ref(false)
const error = ref('')
const copied = ref('')

const filteredRoutes = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return inventory.value?.routes || []
  return (inventory.value?.routes || []).filter(route =>
    route.pattern.toLowerCase().includes(needle)
    || route.source.toLowerCase().includes(needle)
  )
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(`/api/${props.platform}/routes`)
    const data = await response.json()
    if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
    inventory.value = data
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取路由清单失败'
  } finally {
    loading.value = false
  }
}

function sourceName(path: string) {
  return path.split('/').pop() || path
}

async function copyRoute(route: RouteItem) {
  try {
    await navigator.clipboard.writeText(route.pattern)
    copied.value = route.pattern
    setTimeout(() => {
      if (copied.value === route.pattern) copied.value = ''
    }, 1400)
  } catch {
    error.value = '复制路由失败'
  }
}

watch(
  () => [props.modelValue, props.platform],
  ([visible]) => {
    if (visible) load()
  },
  { immediate: true }
)
</script>

<template>
  <Teleport to="body">
    <UModal v-model="open" :ui="{ width: 'sm:max-w-5xl' }">
      <UCard class="route-inventory-card">
      <template #header>
        <div class="route-modal-head">
          <div>
            <h2>路由清单</h2>
            <p>只读解析 {{ platform === 'ios' ? 'iOS' : 'Android' }} 仓库现有路由与 Deep Link。</p>
          </div>
          <UBadge color="gray" variant="subtle">
            {{ inventory?.count || 0 }} 条
          </UBadge>
        </div>
      </template>

      <div class="route-modal-toolbar">
        <UInput
          v-model="query"
          icon="i-heroicons-magnifying-glass"
          placeholder="筛选路由、文件名或路径"
          class="flex-1"
        />
        <UButton
          color="gray"
          variant="ghost"
          icon="i-heroicons-arrow-path"
          :loading="loading"
          @click="load"
        >
          刷新
        </UButton>
      </div>

      <UAlert
        v-if="error"
        color="red"
        variant="soft"
        icon="i-heroicons-exclamation-circle"
        :description="error"
      />
      <UAlert
        v-for="warning in inventory?.warnings || []"
        :key="warning"
        color="amber"
        variant="soft"
        icon="i-heroicons-exclamation-triangle"
        :description="warning"
      />

      <div v-if="filteredRoutes.length" class="route-modal-list">
        <div
          v-for="route in filteredRoutes"
          :key="`${route.pattern}-${route.source}-${route.line}`"
          class="route-modal-row"
        >
          <code>{{ route.pattern }}</code>
          <span>{{ sourceName(route.source) }}<template v-if="route.line">:{{ route.line }}</template></span>
          <UButton
            color="gray"
            variant="ghost"
            size="xs"
            square
            :icon="copied === route.pattern ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
            aria-label="复制路由"
            @click="copyRoute(route)"
          />
        </div>
      </div>
      <AppEmptyState
        v-else
        class="route-modal-empty"
        icon="i-heroicons-code-bracket-square"
        :title="loading ? '正在读取路由' : '没有匹配路由'"
        :description="loading ? '正在解析关联项目的路由文件。' : '调整筛选关键词后重试。'"
      />

      <template #footer>
        <div class="route-modal-footer">
          <span>{{ filteredRoutes.length }} / {{ inventory?.count || 0 }} 条</span>
          <div class="toolbar-spacer" />
          <UButton color="gray" variant="ghost" @click="open = false">
            关闭
          </UButton>
        </div>
      </template>
      </UCard>
    </UModal>
  </Teleport>
</template>

