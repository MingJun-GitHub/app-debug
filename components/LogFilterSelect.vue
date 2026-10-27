<script setup lang="ts">
import { DEFAULT_LOG_FILTERS, type LogFilter } from '~/types/log-filter'

const props = withDefaults(defineProps<{
  modelValue: LogFilter
  placeholder?: string
}>(), {
  placeholder: '选择或输入日志筛选'
})

const emit = defineEmits<{
  'update:modelValue': [filter: LogFilter]
}>()

const STORAGE_KEY = 'app-debug:log-filters'
const customFilters = ref<LogFilter[]>([])
const managerOpen = ref(false)
const draftFilters = ref<LogFilter[]>([])

const options = computed(() => {
  const [all, ...builtIns] = DEFAULT_LOG_FILTERS
  return [all, ...customFilters.value, ...builtIns]
})

function loadCustomFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    if (Array.isArray(saved)) {
      customFilters.value = saved
        .filter(item => item && typeof item.label === 'string' && typeof item.query === 'string')
        .map(item => ({
          id: String(item.id || crypto.randomUUID()),
          label: item.label,
          query: item.query,
          regex: Boolean(item.regex),
          icon: 'i-heroicons-funnel',
          builtIn: false
        }))
    }
  } catch {
    customFilters.value = []
  }
}

function saveCustomFilters() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(customFilters.value))
}

function selectFilter(value: any) {
  if (!value) return
  if (value.id) {
    emit('update:modelValue', value as LogFilter)
    return
  }

  const label = String(value.label || '').trim()
  if (!label) return
  const existing = customFilters.value.find(item => item.label === label)
  if (existing) {
    emit('update:modelValue', existing)
    return
  }

  const filter: LogFilter = {
    id: crypto.randomUUID(),
    label,
    query: label,
    regex: false,
    icon: 'i-heroicons-funnel',
    builtIn: false
  }
  customFilters.value.push(filter)
  saveCustomFilters()
  emit('update:modelValue', filter)
}

function openManager() {
  draftFilters.value = customFilters.value.map(item => ({ ...item }))
  managerOpen.value = true
}

function addDraft() {
  draftFilters.value.push({
    id: crypto.randomUUID(),
    label: '',
    query: '',
    regex: false,
    icon: 'i-heroicons-funnel',
    builtIn: false
  })
}

function removeDraft(id: string) {
  draftFilters.value = draftFilters.value.filter(item => item.id !== id)
}

function saveManager() {
  customFilters.value = draftFilters.value
    .map(item => ({
      ...item,
      label: item.label.trim(),
      query: item.query.trim(),
      builtIn: false
    }))
    .filter(item => item.label && item.query)
  saveCustomFilters()

  const selected = customFilters.value.find(item => item.id === props.modelValue.id)
  if (selected) emit('update:modelValue', selected)
  managerOpen.value = false
}

onMounted(loadCustomFilters)
</script>

<template>
  <div class="log-filter-select">
    <USelectMenu
      :model-value="modelValue"
      :options="options"
      option-attribute="label"
      :placeholder="placeholder"
      icon="i-heroicons-funnel"
      searchable
      searchable-placeholder="搜索筛选，输入后可直接新增"
      creatable
      show-create-option-when="always"
      :ui-menu="{ width: 'w-[360px]', height: 'max-h-[420px]' }"
      class="min-w-0 flex-1"
      @update:model-value="selectFilter"
    >
      <template #option="{ option }">
        <UIcon :name="option.icon || 'i-heroicons-funnel'" class="log-filter-option-icon" />
        <span class="log-filter-option-label">{{ option.label }}</span>
        <span class="log-filter-option-query">{{ option.query || '显示全部' }}</span>
      </template>
      <template #option-create="{ option }">
        <UIcon name="i-heroicons-plus-circle" class="log-filter-option-icon" />
        <span>新增筛选“{{ option.label }}”</span>
      </template>
      <template #empty>
        没有匹配的筛选，输入关键字后可直接新增
      </template>
    </USelectMenu>

    <UTooltip text="管理自定义日志筛选">
      <UButton
        color="gray"
        variant="ghost"
        icon="i-heroicons-adjustments-horizontal"
        square
        aria-label="管理日志筛选"
        @click="openManager"
      />
    </UTooltip>

    <UModal v-model="managerOpen" :ui="{ width: 'sm:max-w-3xl' }">
      <UCard>
        <template #header>
          <div class="filter-manager-header">
            <div>
              <h2>日志筛选管理</h2>
              <p>新增或编辑自定义关键字；正则筛选会按正则表达式匹配。</p>
            </div>
            <UButton color="gray" variant="ghost" icon="i-heroicons-x-mark" square @click="managerOpen = false" />
          </div>
        </template>

        <div class="filter-manager-list">
          <div v-if="!draftFilters.length" class="filter-manager-empty">
            暂无自定义筛选，可点击下方“新增筛选”。
          </div>
          <div v-for="item in draftFilters" :key="item.id" class="filter-manager-row">
            <UInput v-model="item.label" placeholder="名称，例如 结算接口" />
            <UInput v-model="item.query" placeholder="关键字或正则，例如 /api/checkout" />
            <UCheckbox v-model="item.regex" label="正则" />
            <UButton color="red" variant="ghost" icon="i-heroicons-trash" square @click="removeDraft(item.id)" />
          </div>
        </div>

        <template #footer>
          <div class="filter-manager-footer">
            <UButton color="gray" variant="ghost" icon="i-heroicons-plus" @click="addDraft">
              新增筛选
            </UButton>
            <div class="filter-manager-actions">
              <UButton color="gray" variant="ghost" @click="managerOpen = false">取消</UButton>
              <UButton icon="i-heroicons-check" @click="saveManager">保存</UButton>
            </div>
          </div>
        </template>
      </UCard>
    </UModal>
  </div>
</template>

<style scoped>
.log-filter-select {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
}

.log-filter-option-icon {
  width: 15px;
  height: 15px;
  flex: 0 0 15px;
}

.log-filter-option-label {
  white-space: nowrap;
}

.log-filter-option-query {
  min-width: 0;
  margin-left: auto;
  overflow: hidden;
  color: rgb(var(--color-gray-500));
  font: 10px/1.4 var(--app-mono);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-manager-header,
.filter-manager-footer,
.filter-manager-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.filter-manager-header h2 {
  margin: 0;
  font-size: 15px;
}

.filter-manager-header p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 11px;
}

.filter-manager-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-manager-row {
  display: grid;
  grid-template-columns: minmax(140px, 0.7fr) minmax(220px, 1.3fr) auto auto;
  align-items: center;
  gap: 8px;
}

.filter-manager-empty {
  padding: 28px 0;
  color: var(--app-muted);
  font-size: 12px;
  text-align: center;
}

.filter-manager-actions {
  justify-content: flex-end;
}

@media (max-width: 700px) {
  .filter-manager-row {
    grid-template-columns: 1fr auto;
  }

  .filter-manager-row > :nth-child(2) {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>
