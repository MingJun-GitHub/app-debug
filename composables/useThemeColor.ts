const THEME_STORAGE_KEY = 'app-debug:theme-color'
const THEME_STATE_KEY = 'app-debug:theme-color'

const themeColorOptions = [
  {
    key: 'green',
    label: '绿色',
    accent: '#4ade80',
    shades: {
      50: '#f0fdf4',
      100: '#dcfce7',
      200: '#bbf7d0',
      300: '#86efac',
      400: '#4ade80',
      500: '#22c55e',
      600: '#16a34a',
      700: '#15803d',
      800: '#166534',
      900: '#14532d',
      950: '#052e16'
    }
  },
  {
    key: 'teal',
    label: '青绿',
    accent: '#2dd4bf',
    shades: {
      50: '#f0fdfa',
      100: '#ccfbf1',
      200: '#99f6e4',
      300: '#5eead4',
      400: '#2dd4bf',
      500: '#14b8a6',
      600: '#0d9488',
      700: '#0f766e',
      800: '#115e59',
      900: '#134e4a',
      950: '#042f2e'
    }
  },
  {
    key: 'cyan',
    label: '青色',
    accent: '#22d3ee',
    shades: {
      50: '#ecfeff',
      100: '#cffafe',
      200: '#a5f3fc',
      300: '#67e8f9',
      400: '#22d3ee',
      500: '#06b6d4',
      600: '#0891b2',
      700: '#0e7490',
      800: '#155e75',
      900: '#164e63',
      950: '#083344'
    }
  },
  {
    key: 'blue',
    label: '蓝色',
    accent: '#60a5fa',
    shades: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
      950: '#172554'
    }
  },
  {
    key: 'indigo',
    label: '靛蓝',
    accent: '#818cf8',
    shades: {
      50: '#eef2ff',
      100: '#e0e7ff',
      200: '#c7d2fe',
      300: '#a5b4fc',
      400: '#818cf8',
      500: '#6366f1',
      600: '#4f46e5',
      700: '#4338ca',
      800: '#3730a3',
      900: '#312e81',
      950: '#1e1b4b'
    }
  },
  {
    key: 'violet',
    label: '紫色',
    accent: '#a78bfa',
    shades: {
      50: '#f5f3ff',
      100: '#ede9fe',
      200: '#ddd6fe',
      300: '#c4b5fd',
      400: '#a78bfa',
      500: '#8b5cf6',
      600: '#7c3aed',
      700: '#6d28d9',
      800: '#5b21b6',
      900: '#4c1d95',
      950: '#2e1065'
    }
  },
  {
    key: 'fuchsia',
    label: '洋红',
    accent: '#e879f9',
    shades: {
      50: '#fdf4ff',
      100: '#fae8ff',
      200: '#f5d0fe',
      300: '#f0abfc',
      400: '#e879f9',
      500: '#d946ef',
      600: '#c026d3',
      700: '#a21caf',
      800: '#86198f',
      900: '#701a75',
      950: '#4a044e'
    }
  },
  {
    key: 'rose',
    label: '玫红',
    accent: '#fb7185',
    shades: {
      50: '#fff1f2',
      100: '#ffe4e6',
      200: '#fecdd3',
      300: '#fda4af',
      400: '#fb7185',
      500: '#f43f5e',
      600: '#e11d48',
      700: '#be123c',
      800: '#9f1239',
      900: '#881337',
      950: '#4c0519'
    }
  },
  {
    key: 'orange',
    label: '橙色',
    accent: '#fb923c',
    shades: {
      50: '#fff7ed',
      100: '#ffedd5',
      200: '#fed7aa',
      300: '#fdba74',
      400: '#fb923c',
      500: '#f97316',
      600: '#ea580c',
      700: '#c2410c',
      800: '#9a3412',
      900: '#7c2d12',
      950: '#431407'
    }
  }
] as const

export type ThemeColorKey = typeof themeColorOptions[number]['key']
type ThemeColorOption = typeof themeColorOptions[number]

const themeColors = Object.fromEntries(
  themeColorOptions.map(option => [option.key, option])
) as Record<ThemeColorKey, ThemeColorOption>

function isThemeColorKey(value: string | null): value is ThemeColorKey {
  return Boolean(value && value in themeColors)
}

function readStoredThemeColor(): ThemeColorKey {
  if (!import.meta.client) return 'green'
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeColorKey(stored) ? stored : 'green'
  } catch {
    return 'green'
  }
}

function hexToRgbChannels(hex: string) {
  const value = hex.replace('#', '')
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16)
  ].join(' ')
}

function applyThemeColor(option: ThemeColorOption) {
  if (!import.meta.client) return
  const root = document.documentElement
  root.dataset.themeColor = option.key
  root.style.setProperty('--app-theme-color', option.accent)
  root.style.setProperty('--app-primary-rgb', hexToRgbChannels(option.accent))
  root.style.setProperty('--color-primary-DEFAULT', hexToRgbChannels(option.accent))
  for (const [shade, value] of Object.entries(option.shades)) {
    root.style.setProperty(`--color-primary-${shade}`, hexToRgbChannels(value))
  }
}

export function useThemeColor() {
  const themeColor = useState<ThemeColorKey>(THEME_STATE_KEY, readStoredThemeColor)
  const currentThemeColor = computed(() => themeColors[themeColor.value])

  function setThemeColor(next: ThemeColorKey) {
    const option = themeColors[next]
    if (!option) return
    themeColor.value = next
    applyThemeColor(option)
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Theme switching still works when browser storage is unavailable.
    }
  }

  function initializeThemeColor() {
    applyThemeColor(currentThemeColor.value)
  }

  return {
    themeColor,
    themeColorOptions,
    currentThemeColor,
    setThemeColor,
    initializeThemeColor
  }
}
