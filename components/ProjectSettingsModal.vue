<script setup lang="ts">
import type { ProjectConnection } from '~/composables/useProjectSettings'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  updated: []
}>()

const api = useProjectSettings()
const platforms = ['ios', 'android'] as const
const draft = reactive<Record<'ios' | 'android', string>>({ ios: '', android: '' })
const localError = ref('')

const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

const settings = computed(() => api.settings.value)
const projects = computed(() => settings.value?.projects)

function syncDrafts() {
  if (!settings.value) return
  draft.ios = settings.value.projects.ios.path
  draft.android = settings.value.projects.android.path
}

async function load() {
  localError.value = ''
  await api.refresh()
  if (api.error.value) localError.value = api.error.value
  syncDrafts()
}

async function save(platform: 'ios' | 'android') {
  localError.value = ''
  try {
    await api.save(platform, draft[platform])
    syncDrafts()
    emit('updated')
  } catch (cause) {
    localError.value = cause instanceof Error ? cause.message : '保存失败'
  }
}

async function choose(platform: 'ios' | 'android') {
  localError.value = ''
  try {
    const result = await api.pickDirectory(platform)
    if (!result.cancelled && result.path) draft[platform] = result.path
  } catch (cause) {
    localError.value = cause instanceof Error ? cause.message : '选择目录失败'
  }
}

function useDefault(platform: 'ios' | 'android') {
  const project = projects.value?.[platform]
  if (project) draft[platform] = project.defaultPath
}

function status(project: ProjectConnection) {
  if (!project.exists) return { label: '目录不存在', color: 'red' as const }
  if (!project.valid) return { label: '项目结构不匹配', color: 'amber' as const }
  return { label: '已关联', color: 'green' as const }
}

watch(() => props.modelValue, (value) => {
  if (value) load()
})
</script>

<template>
  <UModal v-model="open" :ui="{ width: 'sm:max-w-3xl' }">
    <UCard>
      <template #header>
        <div class="settings-modal-head">
          <div>
            <h2>项目设置</h2>
            <p>关联当前机器上的 iOS / Android 项目，运行和日志会使用这里的目录。</p>
          </div>
          <UBadge color="gray" variant="subtle">
            {{ settings?.configPath || '本地用户配置' }}
          </UBadge>
        </div>
      </template>

      <div class="settings-body">
        <UAlert
          v-if="localError || settings?.loadError"
          color="red"
          variant="soft"
          icon="i-heroicons-exclamation-triangle"
          title="项目设置需要处理"
          :description="localError || settings?.loadError || ''"
        />

        <div class="settings-project-grid">
          <section
            v-for="platform in platforms"
            :key="platform"
            class="settings-project"
          >
            <div class="settings-project-head">
              <div class="settings-project-title">
                <div :class="['settings-platform-icon', platform]">
                  <IosMark v-if="platform === 'ios'" />
                  <AndroidMark v-else />
                </div>
                <div>
                  <strong>{{ platform === 'ios' ? 'iOS 项目' : 'Android 项目' }}</strong>
                  <span>
                    {{ platform === 'ios' ? 'Xcode workspace / project' : 'Gradle root project' }}
                  </span>
                </div>
              </div>
              <UBadge
                v-if="projects?.[platform]"
                :color="status(projects[platform]).color"
                variant="subtle"
              >
                {{ status(projects[platform]).label }}
              </UBadge>
            </div>

            <label class="settings-path-label">本地目录</label>
            <UInput
              v-model="draft[platform]"
              icon="i-heroicons-folder"
              placeholder="选择或输入项目绝对路径"
              class="settings-path-input"
            />

            <div class="settings-path-actions">
              <UButton
                color="gray"
                variant="soft"
                icon="i-heroicons-folder-open"
                :loading="api.picking.value === platform"
                @click="choose(platform)"
              >
                选择目录
              </UButton>
              <UButton
                color="gray"
                variant="ghost"
                @click="useDefault(platform)"
              >
                使用默认路径
              </UButton>
              <div class="toolbar-spacer" />
              <UButton
                color="primary"
                icon="i-heroicons-check"
                :loading="api.saving.value === platform"
                :disabled="!draft[platform].trim()"
                @click="save(platform)"
              >
                保存关联
              </UButton>
            </div>

            <template v-if="projects?.[platform]">
              <div class="settings-meta">
                <div>
                  <span>仓库</span>
                  <code>{{ projects[platform].git.repoName || '-' }}</code>
                </div>
                <div>
                  <span>分支</span>
                  <code>{{ projects[platform].git.branch || '-' }}</code>
                </div>
                <div>
                  <span>提交</span>
                  <code>{{ projects[platform].git.commit || '-' }}</code>
                </div>
                <div>
                  <span>工作区</span>
                  <code :class="{ warning: projects[platform].git.dirty }">
                    {{ projects[platform].git.dirty
                      ? `${projects[platform].git.changedFiles} 个已修改文件`
                      : projects[platform].git.repoRoot ? '干净' : '-' }}
                  </code>
                </div>
              </div>

              <div
                v-for="message in projects[platform].errors"
                :key="message"
                class="settings-message error"
              >
                <UIcon name="i-heroicons-x-circle" />
                <span>{{ message }}</span>
              </div>
              <div
                v-for="message in projects[platform].warnings"
                :key="message"
                class="settings-message warning"
              >
                <UIcon name="i-heroicons-exclamation-triangle" />
                <span>{{ message }}</span>
              </div>
            </template>
          </section>
        </div>

        <p class="settings-note">
          设置保存在当前用户目录，不会写入仓库。其他人拉取项目后，可以在各自机器上关联不同目录。
        </p>
      </div>

      <template #footer>
        <div class="settings-footer">
          <span v-if="api.loading.value">正在读取项目信息…</span>
          <div class="toolbar-spacer" />
          <UButton color="gray" variant="ghost" @click="open = false">
            关闭
          </UButton>
        </div>
      </template>
    </UCard>
  </UModal>
</template>
