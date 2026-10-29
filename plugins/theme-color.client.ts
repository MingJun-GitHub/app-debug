import { useThemeColor } from '~/composables/useThemeColor'

export default defineNuxtPlugin(() => {
  useThemeColor().initializeThemeColor()
})
