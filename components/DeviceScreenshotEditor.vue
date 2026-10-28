<script setup lang="ts">
type Platform = 'ios' | 'android'
type Point = { x: number, y: number }
type Stroke = {
  color: string
  size: number
  points: Point[]
}

const props = defineProps<{
  modelValue: boolean
  platform: Platform
  deviceName?: string
  imageUrl: string
  loading: boolean
  error: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'refresh': []
}>()

const colors = ['#ff5263', '#ffd84d', '#4ade80', '#60a5fa', '#ffffff']
const brushSizes = [4, 8, 14]
const selectedColor = ref(colors[0])
const selectedSize = ref(brushSizes[1])
const strokes = ref<Stroke[]>([])
const currentStroke = ref<Stroke | null>(null)
const imageElement = ref<HTMLImageElement | null>(null)
const canvasElement = ref<HTMLCanvasElement | null>(null)
const stageElement = ref<HTMLElement | null>(null)
const imageReady = ref(false)
const screenLooksBlank = ref(false)
const drawing = ref(false)
const deviceWidth = ref(300)
const copyStatus = ref('')
const copyError = ref('')
const copying = ref(false)
let statusTimer: ReturnType<typeof setTimeout> | undefined
let resizeObserver: ResizeObserver | undefined

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const platformLabel = computed(() => props.platform === 'ios' ? 'iOS' : 'ANDROID')
const canAnnotate = computed(() => imageReady.value && !props.loading)
const editorBadge = computed(() => {
  if (props.error) return { color: 'red' as const, label: '截屏失败' }
  if (props.loading) return { color: 'gray' as const, label: '读取中' }
  if (screenLooksBlank.value) return { color: 'amber' as const, label: '请点亮设备' }
  if (imageReady.value) return { color: 'green' as const, label: '可编辑' }
  return { color: 'gray' as const, label: '等待截图' }
})

function setStatus(message: string, isError = false) {
  copyStatus.value = isError ? '' : message
  copyError.value = isError ? message : ''
  if (statusTimer) clearTimeout(statusTimer)
  if (message) {
    statusTimer = setTimeout(() => {
      copyStatus.value = ''
      copyError.value = ''
    }, 3200)
  }
}

function context2d(canvas: HTMLCanvasElement) {
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器不支持 Canvas')
  return context
}

function drawStroke(
  context: CanvasRenderingContext2D,
  stroke: Stroke,
  transform?: (point: Point) => Point,
  scale = 1
) {
  if (!stroke.points.length) return
  const points = transform ? stroke.points.map(transform) : stroke.points
  context.beginPath()
  context.strokeStyle = stroke.color
  context.lineWidth = stroke.size * scale
  context.lineCap = 'round'
  context.lineJoin = 'round'
  context.moveTo(points[0].x, points[0].y)
  if (points.length === 1) {
    context.lineTo(points[0].x + 0.1, points[0].y + 0.1)
  } else {
    for (const point of points.slice(1)) context.lineTo(point.x, point.y)
  }
  context.stroke()
}

function redraw() {
  const canvas = canvasElement.value
  if (!canvas) return
  const context = context2d(canvas)
  context.clearRect(0, 0, canvas.width, canvas.height)
  for (const stroke of strokes.value) drawStroke(context, stroke)
  if (currentStroke.value) drawStroke(context, currentStroke.value)
}

function syncCanvas() {
  const image = imageElement.value
  const canvas = canvasElement.value
  if (!image || !canvas || !image.complete || !image.naturalWidth) return
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  imageReady.value = true
  screenLooksBlank.value = detectBlankImage(image)
  redraw()
  fitDevice()
}

function detectBlankImage(image: HTMLImageElement) {
  try {
    const sample = document.createElement('canvas')
    sample.width = 32
    sample.height = 64
    const context = context2d(sample)
    context.drawImage(image, 0, 0, sample.width, sample.height)
    const pixels = context.getImageData(0, 0, sample.width, sample.height).data
    let luminance = 0
    let brightPixels = 0
    const count = pixels.length / 4
    for (let index = 0; index < pixels.length; index += 4) {
      const value = pixels[index] * 0.2126 + pixels[index + 1] * 0.7152 + pixels[index + 2] * 0.0722
      luminance += value
      if (value > 24) brightPixels += 1
    }
    return luminance / count < 5 && brightPixels / count < 0.01
  } catch {
    return false
  }
}

function fitDevice() {
  const image = imageElement.value
  const stage = stageElement.value
  if (!image?.naturalWidth || !image.naturalHeight || !stage) return
  const stageStyle = getComputedStyle(stage)
  const horizontalPadding = parseFloat(stageStyle.paddingLeft) + parseFloat(stageStyle.paddingRight)
  const verticalPadding = parseFloat(stageStyle.paddingTop) + parseFloat(stageStyle.paddingBottom)
  const availableWidth = Math.max(180, stage.clientWidth - horizontalPadding - 24)
  const availableHeight = Math.max(240, stage.clientHeight - verticalPadding - 24)
  const aspect = image.naturalWidth / image.naturalHeight
  const frameInset = 22
  const widthByHeight = (availableHeight - frameInset) * aspect + frameInset
  const fitted = Math.min(360, availableWidth + frameInset, widthByHeight)
  deviceWidth.value = Math.round(Math.max(200, fitted))
}

function pointFromEvent(event: PointerEvent): Point {
  const canvas = canvasElement.value
  if (!canvas) return { x: 0, y: 0 }
  const rect = canvas.getBoundingClientRect()
  return {
    x: (event.clientX - rect.left) * canvas.width / rect.width,
    y: (event.clientY - rect.top) * canvas.height / rect.height
  }
}

function beginStroke(event: PointerEvent) {
  if (!canAnnotate.value || event.button !== 0) return
  event.preventDefault()
  canvasElement.value?.setPointerCapture(event.pointerId)
  currentStroke.value = {
    color: selectedColor.value,
    size: selectedSize.value * (canvasElement.value?.width || 1) / 300,
    points: [pointFromEvent(event)]
  }
  drawing.value = true
  redraw()
}

function moveStroke(event: PointerEvent) {
  if (!drawing.value || !currentStroke.value) return
  event.preventDefault()
  currentStroke.value.points.push(pointFromEvent(event))
  redraw()
}

function endStroke(event: PointerEvent) {
  if (!drawing.value || !currentStroke.value) return
  event.preventDefault()
  canvasElement.value?.releasePointerCapture(event.pointerId)
  strokes.value.push(currentStroke.value)
  currentStroke.value = null
  drawing.value = false
  redraw()
}

function undoStroke() {
  strokes.value.pop()
  redraw()
}

function clearStrokes() {
  strokes.value = []
  currentStroke.value = null
  drawing.value = false
  redraw()
}

function roundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  const r = Math.min(radius, width / 2, height / 2)
  context.beginPath()
  context.moveTo(x + r, y)
  context.arcTo(x + width, y, x + width, y + height, r)
  context.arcTo(x + width, y + height, x, y + height, r)
  context.arcTo(x, y + height, x, y, r)
  context.arcTo(x, y, x + width, y, r)
  context.closePath()
}

function timestamp() {
  return new Date().toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

async function composeImage() {
  const image = imageElement.value
  if (!image?.complete || !image.naturalWidth) throw new Error('截图尚未加载完成')

  const screenWidth = Math.min(image.naturalWidth, 900)
  const scale = screenWidth / image.naturalWidth
  const screenHeight = Math.round(image.naturalHeight * scale)
  const margin = Math.max(54, Math.round(screenWidth * 0.075))
  const top = 86
  const footer = 62
  const bezel = Math.max(12, Math.round(screenWidth * 0.018))
  const radius = Math.round(screenWidth * 0.045)
  const output = document.createElement('canvas')
  output.width = screenWidth + margin * 2
  output.height = top + screenHeight + bezel * 2 + footer
  const context = context2d(output)

  context.fillStyle = '#070a10'
  context.fillRect(0, 0, output.width, output.height)
  const glow = context.createRadialGradient(
    output.width / 2,
    0,
    0,
    output.width / 2,
    0,
    output.width * 0.72
  )
  glow.addColorStop(0, 'rgba(74, 222, 128, 0.16)')
  glow.addColorStop(1, 'rgba(74, 222, 128, 0)')
  context.fillStyle = glow
  context.fillRect(0, 0, output.width, output.height)

  context.fillStyle = '#f0f3f8'
  context.font = '600 22px -apple-system, BlinkMacSystemFont, sans-serif'
  context.fillText(platformLabel.value, margin, 38)
  context.fillStyle = '#8c97aa'
  context.font = '15px -apple-system, BlinkMacSystemFont, sans-serif'
  context.fillText(props.deviceName || '当前设备', margin + 112, 38)
  context.fillStyle = '#4ade80'
  context.beginPath()
  context.arc(output.width - margin - 106, 31, 4, 0, Math.PI * 2)
  context.fill()
  context.fillStyle = '#8c97aa'
  context.font = '13px -apple-system, BlinkMacSystemFont, sans-serif'
  context.fillText(`App Debug · ${timestamp()}`, output.width - margin - 94, 36)

  const phoneX = margin - bezel
  const phoneY = top - bezel
  const phoneWidth = screenWidth + bezel * 2
  const phoneHeight = screenHeight + bezel * 2
  context.shadowColor = 'rgba(0, 0, 0, 0.55)'
  context.shadowBlur = 36
  context.shadowOffsetY = 18
  context.fillStyle = '#151a23'
  roundedRect(context, phoneX, phoneY, phoneWidth, phoneHeight, radius + bezel)
  context.fill()
  context.shadowColor = 'transparent'

  context.save()
  roundedRect(context, margin, top, screenWidth, screenHeight, radius)
  context.clip()
  context.drawImage(image, margin, top, screenWidth, screenHeight)
  for (const stroke of strokes.value) {
    drawStroke(
      context,
      stroke,
      point => ({
        x: margin + point.x * scale,
        y: top + point.y * scale
      }),
      scale
    )
  }
  if (props.platform === 'android') {
    context.fillStyle = '#050608'
    context.beginPath()
    context.arc(output.width / 2, top + 18, 6, 0, Math.PI * 2)
    context.fill()
  } else {
    context.fillStyle = '#050608'
    roundedRect(
      context,
      output.width / 2 - 36,
      top + 10,
      72,
      20,
      10
    )
    context.fill()
  }
  context.restore()

  context.strokeStyle = 'rgba(148, 163, 184, 0.25)'
  context.lineWidth = 1
  roundedRect(context, phoneX, phoneY, phoneWidth, phoneHeight, radius + bezel)
  context.stroke()

  context.fillStyle = '#5c6779'
  context.font = '13px -apple-system, BlinkMacSystemFont, sans-serif'
  context.fillText(
    '设备截图 · 涂鸦内容会一起复制',
    margin,
    output.height - 23
  )
  return output
}

function canvasBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      blob => blob ? resolve(blob) : reject(new Error('截图合成失败')),
      'image/png'
    )
  })
}

async function copyImage() {
  if (copying.value || !imageReady.value) return
  copying.value = true
  setStatus('正在合成截图…')
  try {
    const canvas = await composeImage()
    const blob = await canvasBlob(canvas)
    if (!navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
      throw new Error('当前浏览器不支持复制图片，请使用“保存 PNG”')
    }
    await navigator.clipboard.write([
      new ClipboardItem({ 'image/png': blob })
    ])
    setStatus('已复制到剪贴板，可直接粘贴发送')
  } catch (cause) {
    setStatus(
      cause instanceof Error ? cause.message : '复制图片失败',
      true
    )
  } finally {
    copying.value = false
  }
}

async function saveImage() {
  if (!imageReady.value) return
  try {
    const canvas = await composeImage()
    const blob = await canvasBlob(canvas)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `app-debug-${props.platform}-${Date.now()}.png`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    setStatus('截图已保存')
  } catch (cause) {
    setStatus(cause instanceof Error ? cause.message : '保存截图失败', true)
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.modelValue) {
    open.value = false
  }
}

watch(() => props.imageUrl, () => {
  imageReady.value = false
  screenLooksBlank.value = false
  strokes.value = []
  currentStroke.value = null
  copyStatus.value = ''
  copyError.value = ''
  nextTick(syncCanvas)
})

watch(() => props.modelValue, (visible) => {
  if (visible) {
    nextTick(() => {
      if (stageElement.value) resizeObserver?.observe(stageElement.value)
      syncCanvas()
      fitDevice()
    })
  }
})

onMounted(() => {
  resizeObserver = new ResizeObserver(fitDevice)
  window.addEventListener('keydown', handleKeydown)
  if (props.modelValue) {
    nextTick(() => {
      if (stageElement.value) resizeObserver?.observe(stageElement.value)
      fitDevice()
    })
  }
})

onBeforeUnmount(() => {
  if (statusTimer) clearTimeout(statusTimer)
  resizeObserver?.disconnect()
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="screenshot-modal">
      <div
        v-if="open"
        class="screenshot-modal-layer"
        role="dialog"
        aria-modal="true"
        aria-label="设备截图编辑器"
        @click.self="open = false"
      >
        <UCard class="screenshot-editor-card">
      <template #header>
        <div class="screenshot-editor-heading">
          <div>
            <span>设备截图</span>
            <p>{{ platform === 'ios' ? 'iOS' : 'Android' }} · {{ deviceName || '当前设备' }}</p>
          </div>
          <div class="screenshot-editor-head-actions">
            <UBadge :color="editorBadge.color" variant="subtle">
              {{ editorBadge.label }}
            </UBadge>
            <UButton
              color="gray"
              variant="soft"
              size="xs"
              icon="i-heroicons-arrow-path"
              :loading="loading"
              @click="emit('refresh')"
            >
              重新截屏
            </UButton>
          </div>
        </div>
      </template>

      <div class="screenshot-editor-layout">
        <div ref="stageElement" class="screenshot-stage">
          <div
            v-if="imageUrl"
            class="device-mockup"
            :class="platform"
            :style="{ width: `${deviceWidth}px` }"
          >
            <div class="device-side-button volume-up" />
            <div class="device-side-button volume-down" />
            <div class="device-side-button power" />
            <div class="device-screen">
              <img
                ref="imageElement"
                :src="imageUrl"
                :alt="`${platform} 当前设备截图`"
                @load="syncCanvas"
              >
              <canvas
                ref="canvasElement"
                class="screenshot-drawing-canvas"
                :class="{ drawing }"
                @pointerdown="beginStroke"
                @pointermove="moveStroke"
                @pointerup="endStroke"
                @pointercancel="endStroke"
                @pointerleave="drawing && endStroke($event)"
              />
              <span class="device-camera" />
            </div>
          </div>
          <div v-else class="screenshot-editor-placeholder">
            <UIcon
              :name="loading ? 'i-heroicons-arrow-path' : 'i-heroicons-exclamation-triangle'"
              :class="{ spinning: loading }"
            />
            <strong>{{ loading ? '正在截取设备画面' : '暂时无法截屏' }}</strong>
            <p>{{ error || '请确认设备已解锁并保持连接。' }}</p>
            <UButton
              v-if="!loading"
              color="gray"
              variant="soft"
              icon="i-heroicons-arrow-path"
              @click="emit('refresh')"
            >
              重试
            </UButton>
          </div>
        </div>

        <aside class="screenshot-tools">
          <div class="screenshot-tool-section">
            <div class="screenshot-tool-title">
              <span>涂鸦颜色</span>
              <code>{{ selectedColor }}</code>
            </div>
            <div class="screenshot-color-list">
              <button
                v-for="color in colors"
                :key="color"
                type="button"
                class="screenshot-color"
                :class="{ selected: selectedColor === color }"
                :style="{ '--swatch': color }"
                :aria-label="`选择颜色 ${color}`"
                @click="selectedColor = color"
              />
            </div>
          </div>

          <div class="screenshot-tool-section">
            <div class="screenshot-tool-title">
              <span>画笔粗细</span>
              <code>{{ selectedSize }} px</code>
            </div>
            <div class="screenshot-size-list">
              <button
                v-for="size in brushSizes"
                :key="size"
                type="button"
                class="screenshot-size"
                :class="{ selected: selectedSize === size }"
                :aria-label="`画笔粗细 ${size}`"
                @click="selectedSize = size"
              >
                <span :style="{ width: `${size}px`, height: `${size}px` }" />
              </button>
            </div>
          </div>

          <div class="screenshot-tool-actions">
            <UButton
              color="gray"
              variant="soft"
              icon="i-heroicons-arrow-uturn-left"
              :disabled="!strokes.length"
              @click="undoStroke"
            >
              撤销
            </UButton>
            <UButton
              color="gray"
              variant="ghost"
              icon="i-heroicons-trash"
              :disabled="!strokes.length"
              @click="clearStrokes"
            >
              清空
            </UButton>
          </div>

          <div class="screenshot-share-card">
            <UIcon name="i-heroicons-clipboard-document" />
            <div>
              <strong>复制后直接发送</strong>
              <p>会带上设备外框、截图时间和当前涂鸦。</p>
            </div>
          </div>

          <UButton
            block
            size="lg"
            icon="i-heroicons-clipboard-document-check"
            :loading="copying"
            :disabled="!imageReady"
            @click="copyImage"
          >
            复制图片
          </UButton>
          <UButton
            block
            color="gray"
            variant="ghost"
            icon="i-heroicons-arrow-down-tray"
            :disabled="!imageReady"
            @click="saveImage"
          >
            保存 PNG
          </UButton>

          <UAlert
            v-if="copyError"
            color="red"
            variant="soft"
            icon="i-heroicons-exclamation-circle"
            :description="copyError"
          />
          <UAlert
            v-else-if="copyStatus"
            color="green"
            variant="soft"
            icon="i-heroicons-check-circle"
            :description="copyStatus"
          />
          <UAlert
            v-if="screenLooksBlank"
            color="amber"
            variant="soft"
            icon="i-heroicons-light-bulb"
            title="当前画面接近全黑"
            :description="platform === 'ios'
              ? 'iPhone 熄屏或锁屏时会返回黑图，请点亮并解锁设备后重新截屏。'
              : '设备可能已熄屏，请点亮屏幕后重新截屏。'"
          />
          <p class="screenshot-editor-tip">
            在设备画面上按住并拖动即可涂鸦。截图只在当前页面处理，不上传到服务器。
          </p>
        </aside>
      </div>

      <template #footer>
        <div class="screenshot-editor-footer">
          <span>本地生成 · 不写入业务工程</span>
          <UButton color="gray" variant="ghost" @click="open = false">
            关闭
          </UButton>
        </div>
      </template>
        </UCard>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.screenshot-modal-layer {
  position: fixed;
  z-index: 100;
  inset: 0;
  display: grid;
  place-items: center;
  overflow: auto;
  background: rgba(3, 6, 11, 0.8);
  padding: clamp(12px, 2.5vw, 40px);
  backdrop-filter: blur(7px);
}

.screenshot-editor-card {
  width: min(1152px, calc(100vw - 24px));
  overflow: hidden;
  border: 1px solid var(--app-border-strong);
  background: var(--app-surface-raised);
  box-shadow:
    0 32px 90px rgba(0, 0, 0, 0.62),
    0 0 0 1px rgba(255, 255, 255, 0.025) inset;
}

.screenshot-modal-enter-active,
.screenshot-modal-leave-active {
  transition: opacity 160ms ease;
}

.screenshot-modal-enter-active .screenshot-editor-card,
.screenshot-modal-leave-active .screenshot-editor-card {
  transition: transform 180ms ease, opacity 160ms ease;
}

.screenshot-modal-enter-from,
.screenshot-modal-leave-to {
  opacity: 0;
}

.screenshot-modal-enter-from .screenshot-editor-card,
.screenshot-modal-leave-to .screenshot-editor-card {
  opacity: 0;
  transform: translateY(8px) scale(0.985);
}

.screenshot-editor-heading,
.screenshot-editor-head-actions,
.screenshot-editor-footer,
.screenshot-tool-title,
.screenshot-tool-actions,
.screenshot-share-card {
  display: flex;
  align-items: center;
}

.screenshot-editor-heading {
  justify-content: space-between;
  gap: 16px;
}

.screenshot-editor-heading > div:first-child {
  min-width: 0;
}

.screenshot-editor-heading span {
  font-size: 14px;
  font-weight: 650;
}

.screenshot-editor-heading p {
  margin: 3px 0 0;
  color: var(--app-muted);
  font-size: 10px;
}

.screenshot-editor-head-actions {
  gap: 8px;
}

.screenshot-editor-layout {
  display: grid;
  min-height: 0;
  height: min(760px, calc(100vh - 235px));
  grid-template-columns: minmax(360px, 1fr) 286px;
  gap: 18px;
}

.screenshot-stage {
  display: grid;
  min-height: 0;
  place-items: center;
  overflow: auto;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background:
    radial-gradient(circle at 50% 0%, rgba(74, 222, 128, 0.13), transparent 52%),
    linear-gradient(145deg, #0c1119, #070a0f);
  padding: 20px;
}

.device-mockup {
  position: relative;
  max-width: calc(100% - 8px);
  flex: 0 0 auto;
  border: 2px solid #3a4351;
  border-radius: 35px;
  background: linear-gradient(145deg, #2e3541, #11151d 22%, #080a0f 75%, #242b36);
  box-shadow:
    0 26px 65px rgba(0, 0, 0, 0.62),
    inset 0 0 0 2px rgba(255, 255, 255, 0.08);
  padding: 9px;
}

.device-screen {
  position: relative;
  overflow: hidden;
  border-radius: 27px;
  background: #000;
}

.device-screen img {
  display: block;
  width: 100%;
  height: auto;
}

.screenshot-drawing-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
  touch-action: none;
}

.screenshot-drawing-canvas.drawing {
  cursor: grabbing;
}

.device-camera {
  position: absolute;
  top: 10px;
  left: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #050608;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.04);
  pointer-events: none;
  transform: translateX(-50%);
}

.device-mockup.ios .device-camera {
  width: 62px;
  height: 18px;
  border-radius: 999px;
}

.device-side-button {
  position: absolute;
  width: 3px;
  border-radius: 999px;
  background: #3b4350;
}

.device-side-button.volume-up {
  top: 74px;
  left: -5px;
  height: 38px;
}

.device-side-button.volume-down {
  top: 120px;
  left: -5px;
  height: 54px;
}

.device-side-button.power {
  top: 96px;
  right: -5px;
  height: 62px;
}

.device-mockup.android .device-side-button {
  left: auto;
  right: -5px;
}

.device-mockup.android .device-side-button.volume-up {
  top: 82px;
}

.device-mockup.android .device-side-button.volume-down {
  top: 128px;
}

.device-mockup.android .device-side-button.power {
  top: 208px;
  height: 54px;
}

.screenshot-tools {
  display: flex;
  min-height: 0;
  flex-direction: column;
  gap: 15px;
  overflow: auto;
  padding: 2px;
}

.screenshot-tool-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.screenshot-tool-title {
  justify-content: space-between;
  color: var(--app-muted);
  font-size: 10px;
}

.screenshot-tool-title code {
  color: var(--app-faint);
  font: 9px var(--app-mono);
}

.screenshot-color-list,
.screenshot-size-list {
  display: flex;
  gap: 9px;
}

.screenshot-color {
  width: 28px;
  height: 28px;
  border: 2px solid transparent;
  border-radius: 50%;
  background: var(--swatch);
  box-shadow: inset 0 0 0 2px rgba(0, 0, 0, 0.16);
}

.screenshot-color.selected {
  border-color: #fff;
  box-shadow:
    0 0 0 3px rgba(255, 255, 255, 0.12),
    inset 0 0 0 2px rgba(0, 0, 0, 0.16);
}

.screenshot-size {
  display: grid;
  width: 42px;
  height: 30px;
  place-items: center;
  border: 1px solid var(--app-border);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.025);
}

.screenshot-size span {
  border-radius: 50%;
  background: var(--app-text);
}

.screenshot-size.selected {
  border-color: var(--app-primary);
  background: rgba(74, 222, 128, 0.09);
}

.screenshot-tool-actions {
  gap: 7px;
}

.screenshot-tool-actions button {
  flex: 1;
  justify-content: center;
}

.screenshot-share-card {
  align-items: flex-start;
  gap: 9px;
  margin-top: 2px;
  border: 1px solid rgba(74, 222, 128, 0.16);
  border-radius: 9px;
  background: rgba(74, 222, 128, 0.045);
  padding: 10px;
}

.screenshot-share-card > svg {
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  color: var(--app-primary);
}

.screenshot-share-card strong {
  display: block;
  font-size: 10.5px;
}

.screenshot-share-card p {
  margin: 3px 0 0;
  color: var(--app-faint);
  font-size: 9.5px;
  line-height: 1.55;
}

.screenshot-editor-tip {
  margin: 1px 0 0;
  color: var(--app-faint);
  font-size: 9.5px;
  line-height: 1.6;
}

.screenshot-editor-placeholder {
  display: flex;
  max-width: 360px;
  align-items: center;
  flex-direction: column;
  gap: 9px;
  color: var(--app-faint);
  text-align: center;
}

.screenshot-editor-placeholder > svg {
  width: 38px;
  height: 38px;
  color: var(--app-primary);
}

.screenshot-editor-placeholder > svg.spinning {
  animation: screenshot-spin 0.9s linear infinite;
}

.screenshot-editor-placeholder strong {
  color: var(--app-text);
  font-size: 13px;
}

.screenshot-editor-placeholder p {
  margin: 0 0 4px;
  font-size: 10.5px;
  line-height: 1.6;
}

.screenshot-editor-footer {
  min-height: 28px;
  justify-content: space-between;
  gap: 14px;
  color: var(--app-faint);
  font-size: 10px;
}

@keyframes screenshot-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .screenshot-editor-layout {
    grid-template-columns: minmax(320px, 1fr) 250px;
    gap: 14px;
  }
}

@media (max-width: 760px) {
  .screenshot-editor-layout {
    grid-template-columns: 1fr;
  }

  .screenshot-tools {
    overflow: visible;
  }
}
</style>
