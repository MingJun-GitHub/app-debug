<script setup lang="ts">
import QRCode from 'qrcode'
import {
  PAGE_SHORTCUT_GROUPS,
  PAGE_SITES,
  PAGE_URL_DOC,
  buildPageShortcutUrl,
  type PageShortcut,
  type PageSiteKey
} from '~/composables/page-shortcuts'

type Platform = 'ios' | 'android'
type LinkKind = 'h5' | 'universal' | 'deeplink'

interface LinkTarget {
  kind: LinkKind
  label: string
  description: string
  value: string
}

interface LinkResolution {
  input: string
  normalized: string
  platform: Platform
  siteHost: string
  deepLinkHost: string
  recognizedUniversal: boolean
  warning: string
  targets: LinkTarget[]
}

const props = defineProps<{
  platform: Platform
  deviceName?: string
  deviceAvailable?: boolean
}>()

const inputs = reactive<Record<Platform, string>>({ ios: '', android: '' })
const selectedKinds = reactive<Record<Platform, LinkKind>>({
  ios: 'universal',
  android: 'universal'
})
const selectedSites = reactive<Record<Platform, PageSiteKey>>({
  ios: 'us',
  android: 'us'
})
const selectedShortcutIds = reactive<Record<Platform, string>>({
  ios: '',
  android: ''
})
const resolution = ref<LinkResolution | null>(null)
const resolving = ref(false)
const opening = ref(false)
const error = ref('')
const status = ref('')
const qrDataUrl = ref('')
const copiedTarget = ref('')
const pendingShortcutOpen = ref(false)
let resolveTimer: ReturnType<typeof setTimeout> | undefined
let resolveSerial = 0
let copiedTimer: ReturnType<typeof setTimeout> | undefined

const input = computed({
  get: () => inputs[props.platform],
  set: (value: string) => { inputs[props.platform] = value }
})

const selectedKind = computed({
  get: () => selectedKinds[props.platform],
  set: (value: LinkKind) => { selectedKinds[props.platform] = value }
})

const selectedSite = computed({
  get: () => selectedSites[props.platform],
  set: (value: PageSiteKey) => { selectedSites[props.platform] = value }
})

const selectedShortcutId = computed({
  get: () => selectedShortcutIds[props.platform],
  set: (value: string) => { selectedShortcutIds[props.platform] = value }
})

const shortcuts = PAGE_SHORTCUT_GROUPS.flatMap(group => group.items)

const selectedTarget = computed(() =>
  resolution.value?.targets.find(target => target.kind === selectedKind.value)
  || resolution.value?.targets[0]
  || null
)

const h5Target = computed(() =>
  resolution.value?.targets.find(target => target.kind === 'h5')
  || resolution.value?.targets.find(target => target.kind === 'universal')
  || null
)

function storageKey(platform: Platform) {
  return `app-debug:page-link:${platform}`
}

function loadSavedInput() {
  if (typeof window === 'undefined') return
  for (const platform of ['ios', 'android'] as Platform[]) {
    try {
      inputs[platform] = window.localStorage.getItem(storageKey(platform)) || ''
    } catch {
      // Local storage can be unavailable in restricted browser contexts.
    }
  }
}

function selectShortcut(shortcut: PageShortcut) {
  selectedShortcutId.value = shortcut.id
  selectedKind.value = 'deeplink'
  pendingShortcutOpen.value = Boolean(props.deviceAvailable)
  input.value = buildPageShortcutUrl(selectedSite.value, shortcut)
  status.value = props.deviceAvailable
    ? `正在打开${shortcut.label}`
    : `已选择${shortcut.label}，连接设备后即可打开`
}

function scheduleResolve() {
  if (resolveTimer) clearTimeout(resolveTimer)
  resolveSerial += 1
  resolving.value = false
  error.value = ''
  status.value = ''
  const value = input.value.trim()
  if (!value) {
    resolution.value = null
    resolveTimer = undefined
    return
  }
  resolveTimer = setTimeout(resolveLink, 280)
}

async function resolveLink() {
  const value = input.value.trim()
  if (!value) {
    resolution.value = null
    return
  }

  const serial = ++resolveSerial
  resolving.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ url: value })
    const response = await fetch(`/api/${props.platform}/link/resolve?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
    if (serial !== resolveSerial) return
    resolution.value = data
    const preferred = data.targets.some((target: LinkTarget) => target.kind === selectedKind.value)
      ? selectedKind.value
      : data.targets.some((target: LinkTarget) => target.kind === 'universal')
        ? 'universal'
        : data.targets[0]?.kind
    if (preferred) selectedKind.value = preferred
    if (pendingShortcutOpen.value && props.deviceAvailable) {
      pendingShortcutOpen.value = false
      await openOnDevice()
    }
  } catch (cause) {
    if (serial !== resolveSerial) return
    pendingShortcutOpen.value = false
    resolution.value = null
    error.value = cause instanceof Error ? cause.message : '链接解析失败'
  } finally {
    if (serial === resolveSerial) resolving.value = false
  }
}

async function renderQr() {
  if (!selectedTarget.value?.value) {
    qrDataUrl.value = ''
    return
  }
  try {
    qrDataUrl.value = await QRCode.toDataURL(selectedTarget.value.value, {
      width: 260,
      margin: 2,
      errorCorrectionLevel: 'M',
      color: {
        dark: '#0b0f14',
        light: '#ffffff'
      }
    })
  } catch {
    qrDataUrl.value = ''
  }
}

function openInBrowser() {
  const target = h5Target.value
  if (!target?.value) return
  window.open(target.value, '_blank', 'noopener,noreferrer')
  status.value = '已在浏览器打开 H5 页面'
}

async function openOnDevice() {
  const target = selectedTarget.value
  if (!target?.value || opening.value) return
  opening.value = true
  error.value = ''
  status.value = ''
  try {
    const response = await fetch(`/api/${props.platform}/link/open`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: target.value,
        kind: target.kind
      })
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
    status.value = `已发送到 ${props.deviceName || '当前设备'}`
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '设备打开失败'
  } finally {
    opening.value = false
  }
}

async function copyTarget(target: LinkTarget) {
  try {
    await navigator.clipboard.writeText(target.value)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = target.value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copiedTarget.value = target.kind
  status.value = `${target.label} 已复制`
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    if (copiedTarget.value === target.kind) copiedTarget.value = ''
  }, 1600)
}

function clearInput() {
  input.value = ''
  pendingShortcutOpen.value = false
  resolution.value = null
  error.value = ''
  status.value = ''
  if (resolveTimer) clearTimeout(resolveTimer)
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.removeItem(storageKey(props.platform))
    } catch {
      // Ignore storage failures.
    }
  }
}

watch(input, (value) => {
  const selected = shortcuts.find(shortcut => shortcut.id === selectedShortcutId.value)
  if (selected && value !== buildPageShortcutUrl(selectedSite.value, selected)) {
    selectedShortcutId.value = ''
    pendingShortcutOpen.value = false
  }
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(storageKey(props.platform), value)
    } catch {
      // Ignore storage failures.
    }
  }
  scheduleResolve()
})

watch(() => props.platform, () => {
  pendingShortcutOpen.value = false
  error.value = ''
  status.value = ''
  resolution.value = null
  scheduleResolve()
})

watch(selectedSite, () => {
  pendingShortcutOpen.value = false
  const selected = shortcuts.find(shortcut => shortcut.id === selectedShortcutId.value)
  if (selected) {
    input.value = buildPageShortcutUrl(selectedSite.value, selected)
    status.value = `已切换到${PAGE_SITES.find(site => site.key === selectedSite.value)?.label || '当前站点'}`
  }
})

watch(selectedTarget, () => {
  renderQr()
}, { immediate: true })

onMounted(() => {
  loadSavedInput()
  scheduleResolve()
})

onBeforeUnmount(() => {
  if (resolveTimer) clearTimeout(resolveTimer)
  if (copiedTimer) clearTimeout(copiedTimer)
})
</script>

<template>
  <section class="page-link-panel">
    <div class="page-link-heading">
      <div>
        <h2>页面直达</h2>
        <p>粘贴 H5 链接，或从通用页面列表中快速选择。自动生成 Deep Link 和二维码。</p>
      </div>
      <div class="page-link-heading-actions">
        <a :href="PAGE_URL_DOC" target="_blank" rel="noopener noreferrer" class="page-doc-link">
          <UIcon name="i-heroicons-document-text" />
          URL 文档
        </a>
        <UBadge :color="deviceAvailable ? 'green' : 'gray'" variant="subtle">
          {{ deviceAvailable ? deviceName || '设备已连接' : '设备未连接' }}
        </UBadge>
      </div>
    </div>

    <div class="shortcut-panel">
      <div class="shortcut-head">
        <div>
          <strong>快捷跳转</strong>
          <span>有设备时点击页面直接跳转；链接仍可复制或扫码</span>
        </div>
        <USelectMenu
          v-model="selectedSite"
          :options="PAGE_SITES"
          option-attribute="label"
          value-attribute="key"
          class="shortcut-site"
        />
      </div>

      <div v-for="group in PAGE_SHORTCUT_GROUPS" :key="group.key" class="shortcut-group">
        <span class="shortcut-group-label">{{ group.label }}</span>
        <div class="shortcut-grid">
          <button
            v-for="shortcut in group.items"
            :key="shortcut.id"
            type="button"
            class="shortcut-item"
            :class="{ selected: selectedShortcutId === shortcut.id }"
            @click="selectShortcut(shortcut)"
          >
            <UIcon :name="shortcut.icon" />
            <span>
              <strong>{{ shortcut.label }}</strong>
              <small>{{ shortcut.description }}</small>
            </span>
          </button>
        </div>
      </div>
    </div>

    <div class="link-input-shell">
      <UInput
        v-model="input"
        size="lg"
        icon="i-heroicons-link"
        placeholder="粘贴 H5 链接，例如 https://www.bloomchic.com/products/..."
        class="link-input"
        :loading="resolving"
        @keydown.enter="resolveLink"
      />
      <UButton
        v-if="input"
        color="gray"
        variant="ghost"
        square
        icon="i-heroicons-x-mark"
        aria-label="清空链接"
        @click="clearInput"
      />
    </div>

    <UAlert
      v-if="error"
      color="red"
      variant="soft"
      icon="i-heroicons-exclamation-circle"
      title="链接不可用"
      :description="error"
    />

    <div v-else-if="!input.trim()" class="link-empty">
      <div class="link-empty-icon">
        <UIcon name="i-heroicons-arrow-top-right-on-square" />
      </div>
      <div>
        <strong>从一条 H5 链接开始</strong>
        <p>首页、LP、商品页都可以。粘贴后无需手动替换 scheme。</p>
      </div>
    </div>

    <template v-else-if="resolution">
      <UAlert
        v-if="resolution.warning"
        color="amber"
        variant="soft"
        icon="i-heroicons-information-circle"
        title="注意"
        :description="resolution.warning"
      />

      <div class="link-workbench">
        <div class="link-targets">
          <div
            v-for="target in resolution.targets"
            :key="target.kind"
            class="link-target"
            :class="{ selected: selectedTarget?.kind === target.kind }"
            role="button"
            tabindex="0"
            @click="selectedKind = target.kind"
            @keydown.enter="selectedKind = target.kind"
            @keydown.space.prevent="selectedKind = target.kind"
          >
            <div class="link-target-head">
              <div>
                <strong>{{ target.label }}</strong>
                <span>{{ target.description }}</span>
              </div>
              <UIcon
                :name="selectedTarget?.kind === target.kind ? 'i-heroicons-check-circle-solid' : 'i-heroicons-minus-circle'"
                class="link-target-check"
              />
            </div>
            <code>{{ target.value }}</code>
            <div class="link-target-actions">
              <UButton
                color="gray"
                variant="ghost"
                size="xs"
                :icon="copiedTarget === target.kind ? 'i-heroicons-check' : 'i-heroicons-clipboard'"
                @click.stop="copyTarget(target)"
              >
                {{ copiedTarget === target.kind ? '已复制' : '复制' }}
              </UButton>
              <UButton
                color="gray"
                variant="ghost"
                size="xs"
                icon="i-heroicons-device-phone-mobile"
                :disabled="!deviceAvailable"
                :loading="opening && selectedTarget?.kind === target.kind"
                @click.stop="selectedKind = target.kind; openOnDevice()"
              >
                设备打开
              </UButton>
            </div>
          </div>
        </div>

        <div class="link-qr-card">
          <div class="link-qr-head">
            <div>
              <strong>扫码访问</strong>
              <span>{{ selectedTarget?.label }}</span>
            </div>
            <UIcon name="i-heroicons-qr-code" />
          </div>
          <div class="link-qr-code">
            <img v-if="qrDataUrl" :src="qrDataUrl" alt="页面链接二维码">
            <UIcon v-else name="i-heroicons-qr-code" />
          </div>
          <p>点击左侧不同链接，可生成对应二维码。</p>
        </div>
      </div>

      <div class="link-footer-actions">
        <UButton
          color="gray"
          variant="soft"
          icon="i-heroicons-arrow-top-right-on-square"
          :disabled="!h5Target"
          @click="openInBrowser"
        >
          浏览器打开 H5
        </UButton>
        <UButton
          icon="i-heroicons-device-phone-mobile"
          :disabled="!deviceAvailable || !selectedTarget"
          :loading="opening"
          @click="openOnDevice"
        >
          在 {{ platform === 'ios' ? 'iOS' : 'Android' }} 设备打开
        </UButton>
        <span class="link-site">
          {{ resolution.siteHost || '未知站点' }}
          <template v-if="resolution.deepLinkHost"> · {{ resolution.deepLinkHost }}</template>
        </span>
      </div>

      <UAlert
        v-if="status"
        color="green"
        variant="soft"
        icon="i-heroicons-check-circle"
        :description="status"
      />
    </template>
  </section>
</template>

<style scoped>
.page-link-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding: 14px 2px 24px;
}

.page-link-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-link-heading h2 {
  margin: 0;
  font-size: 16px;
}

.page-link-heading p {
  margin: 5px 0 0;
  color: var(--app-muted);
  font-size: 11px;
}

.page-link-heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-doc-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--app-muted);
  font-size: 10px;
  text-decoration: none;
}

.page-doc-link:hover {
  color: var(--app-text);
}

.page-doc-link svg {
  width: 14px;
  height: 14px;
}

.shortcut-panel {
  display: flex;
  flex-direction: column;
  gap: 11px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: rgba(16, 19, 26, 0.64);
  padding: 13px;
}

.shortcut-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.shortcut-head > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.shortcut-head strong {
  font-size: 12px;
}

.shortcut-head span,
.shortcut-group-label {
  color: var(--app-faint);
  font-size: 9.5px;
}

.shortcut-site {
  width: 118px;
}

.shortcut-group {
  display: grid;
  grid-template-columns: 66px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
}

.shortcut-group-label {
  padding-top: 9px;
}

.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
}

.shortcut-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  padding: 7px 8px;
  color: var(--app-muted);
  text-align: left;
  cursor: pointer;
  transition: border-color 140ms ease, background 140ms ease, color 140ms ease;
}

.shortcut-item:hover,
.shortcut-item:focus-visible {
  outline: none;
  border-color: var(--app-border-strong);
  background: var(--app-surface-soft);
  color: var(--app-text);
}

.shortcut-item.selected {
  border-color: rgba(74, 222, 128, 0.46);
  background: rgba(74, 222, 128, 0.08);
  color: var(--app-text);
}

.shortcut-item > svg {
  width: 15px;
  height: 15px;
  flex: 0 0 15px;
  color: var(--app-primary);
}

.shortcut-item > span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 1px;
}

.shortcut-item strong {
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shortcut-item small {
  overflow: hidden;
  color: var(--app-faint);
  font-size: 8.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-input-shell {
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 1060px;
}

.link-input {
  min-width: 0;
  flex: 1;
}

.link-empty {
  display: flex;
  max-width: 720px;
  align-items: center;
  gap: 13px;
  margin-top: 8px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 12px;
  background: rgba(16, 19, 26, 0.58);
  padding: 20px;
}

.link-empty-icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border: 1px solid rgba(74, 222, 128, 0.24);
  border-radius: 10px;
  background: rgba(74, 222, 128, 0.08);
  color: var(--app-primary);
}

.link-empty strong {
  font-size: 12px;
}

.link-empty p {
  margin: 5px 0 0;
  color: var(--app-muted);
  font-size: 10.5px;
  line-height: 1.6;
}

.link-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
}

.link-targets {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
}

.link-target {
  min-width: 0;
  outline: none;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: rgba(16, 19, 26, 0.78);
  padding: 12px 13px;
  cursor: pointer;
  transition: border-color 140ms ease, background 140ms ease;
}

.link-target:hover,
.link-target:focus-visible {
  border-color: var(--app-border-strong);
  background: var(--app-surface-raised);
}

.link-target.selected {
  border-color: rgba(74, 222, 128, 0.46);
  background: rgba(74, 222, 128, 0.06);
  box-shadow: inset 3px 0 0 var(--app-primary);
}

.link-target-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.link-target-head > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.link-target-head strong {
  font-size: 11.5px;
}

.link-target-head span {
  color: var(--app-faint);
  font-size: 9.5px;
}

.link-target-check {
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  color: var(--app-faint);
}

.link-target.selected .link-target-check {
  color: var(--app-primary);
}

.link-target code {
  display: block;
  margin-top: 9px;
  overflow-wrap: anywhere;
  color: var(--app-text);
  font: 10.5px/1.6 var(--app-mono);
}

.link-target-actions {
  display: flex;
  gap: 4px;
  margin-top: 7px;
}

.link-qr-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  align-self: start;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-surface-raised);
  padding: 14px;
}

.link-qr-head {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
}

.link-qr-head > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.link-qr-head strong {
  font-size: 11.5px;
}

.link-qr-head span,
.link-qr-card p {
  color: var(--app-faint);
  font-size: 9.5px;
}

.link-qr-head svg {
  width: 18px;
  height: 18px;
  color: var(--app-primary);
}

.link-qr-code {
  display: grid;
  width: 232px;
  height: 232px;
  place-items: center;
  margin: 14px 0 10px;
  border-radius: 10px;
  background: #fff;
}

.link-qr-code img {
  width: 216px;
  height: 216px;
}

.link-qr-code svg {
  width: 52px;
  height: 52px;
  color: #a4acb9;
}

.link-qr-card p {
  margin: 0;
  text-align: center;
}

.link-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.link-site {
  margin-left: auto;
  color: var(--app-faint);
  font: 9.5px var(--app-mono);
}

@media (max-width: 900px) {
  .link-workbench {
    grid-template-columns: minmax(0, 1fr);
  }

  .link-qr-card {
    width: 100%;
  }

  .link-site {
    width: 100%;
    margin-left: 0;
  }

  .shortcut-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .page-link-heading,
  .shortcut-head {
    align-items: flex-start;
  }

  .page-link-heading-actions {
    flex-direction: column;
    align-items: flex-end;
  }

  .shortcut-group {
    grid-template-columns: minmax(0, 1fr);
  }

  .shortcut-group-label {
    padding-top: 0;
  }
}
</style>
