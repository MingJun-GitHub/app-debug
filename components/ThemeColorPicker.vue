<script setup lang="ts">
import { useThemeColor, type ThemeColorKey } from '~/composables/useThemeColor'

const {
  themeColor,
  themeColorOptions,
  currentThemeColor,
  setThemeColor
} = useThemeColor()
const colorMode = useColorMode()
const appearance = computed(() => colorMode.value === 'light' ? 'light' : 'dark')
const appearanceLabel = computed(() => appearance.value === 'light' ? 'Light' : 'Dark')

function selectTheme(key: ThemeColorKey) {
  setThemeColor(key)
}

function setAppearance(value: 'light' | 'dark') {
  colorMode.preference = value
}
</script>

<template>
  <UPopover
    :popper="{ placement: 'bottom-end', offsetDistance: 10 }"
    :ui="{ width: 'w-auto', container: 'z-[70]' }"
  >
    <UButton
      color="gray"
      variant="ghost"
      size="md"
      square
      class="theme-color-trigger"
      :aria-label="`主题设置：${appearanceLabel}，${currentThemeColor.label}`"
      :title="`主题设置：${appearanceLabel}，${currentThemeColor.label}`"
    >
      <span class="theme-color-trigger-icon">
        <UIcon name="i-heroicons-swatch" />
        <span
          class="theme-color-trigger-dot"
          :style="{ background: currentThemeColor.accent }"
        />
      </span>
    </UButton>

    <template #panel>
      <div class="theme-picker-panel">
        <div class="theme-picker-head">
          <div>
            <strong>主题设置</strong>
            <p>外观和强调色全局生效，并保存在当前浏览器</p>
          </div>
          <span class="theme-picker-current">
            <span :style="{ background: currentThemeColor.accent }" />
            {{ appearanceLabel }} · {{ currentThemeColor.label }}
          </span>
        </div>

        <div class="theme-picker-row">
          <span>外观</span>
          <div class="theme-picker-modes" role="group" aria-label="选择界面外观">
            <button
              type="button"
              :class="{ selected: appearance === 'light' }"
              :aria-pressed="appearance === 'light'"
              @click="setAppearance('light')"
            >
              <UIcon name="i-heroicons-sun" />
              Light
            </button>
            <button
              type="button"
              :class="{ selected: appearance === 'dark' }"
              :aria-pressed="appearance === 'dark'"
              @click="setAppearance('dark')"
            >
              <UIcon name="i-heroicons-moon" />
              Dark
            </button>
          </div>
        </div>

        <div class="theme-picker-section-label">主题色</div>
        <div class="theme-picker-grid" role="group" aria-label="选择界面主题色">
          <button
            v-for="option in themeColorOptions"
            :key="option.key"
            type="button"
            class="theme-picker-option"
            :class="{ selected: themeColor === option.key }"
            :aria-pressed="themeColor === option.key"
            @click="selectTheme(option.key)"
          >
            <span
              class="theme-picker-swatch"
              :style="{ '--theme-swatch': option.accent }"
            />
            <span>{{ option.label }}</span>
            <UIcon
              v-if="themeColor === option.key"
              name="i-heroicons-check"
              class="theme-picker-check"
            />
          </button>
        </div>

        <p class="theme-picker-note">
          错误、警告和成功状态继续使用固定语义色，iOS 与 Android 共用当前主题。
        </p>
      </div>
    </template>
  </UPopover>
</template>
