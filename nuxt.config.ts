export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: process.env.NODE_ENV === 'development' },
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  ssr: false,
  colorMode: {
    preference: 'dark',
    fallback: 'dark'
  },
  icon: {
    // The production app is a static SPA. Bundle icons locally so a blocked
    // or unavailable Iconify API never leaves empty icon slots in the UI.
    provider: 'none',
    clientBundle: {
      scan: true,
      icons: [
        'heroicons:adjustments-horizontal',
        'heroicons:arrow-down-tray',
        'heroicons:arrow-path',
        'heroicons:arrow-right-on-rectangle',
        'heroicons:arrow-top-right-on-square',
        'heroicons:arrow-uturn-left',
        'heroicons:beaker',
        'heroicons:bell',
        'heroicons:camera',
        'heroicons:chat-bubble-left-right',
        'heroicons:chat-bubble-oval-left',
        'heroicons:check',
        'heroicons:check-circle',
        'heroicons:check-circle-solid',
        'heroicons:chevron-right',
        'heroicons:clipboard',
        'heroicons:clipboard-document',
        'heroicons:clipboard-document-check',
        'heroicons:clipboard-document-list',
        'heroicons:clock',
        'heroicons:code-bracket',
        'heroicons:code-bracket-square',
        'heroicons:cog-6-tooth',
        'heroicons:command-line',
        'heroicons:cube',
        'heroicons:device-phone-mobile',
        'heroicons:device-tablet',
        'heroicons:document-arrow-down',
        'heroicons:document-magnifying-glass',
        'heroicons:document-text',
        'heroicons:exclamation-circle',
        'heroicons:exclamation-triangle',
        'heroicons:folder',
        'heroicons:folder-open',
        'heroicons:funnel',
        'heroicons:heart',
        'heroicons:home',
        'heroicons:inbox',
        'heroicons:information-circle',
        'heroicons:lifebuoy',
        'heroicons:light-bulb',
        'heroicons:link',
        'heroicons:magnifying-glass',
        'heroicons:map-pin',
        'heroicons:minus',
        'heroicons:minus-circle',
        'heroicons:play',
        'heroicons:play-solid',
        'heroicons:plus',
        'heroicons:plus-circle',
        'heroicons:qr-code',
        'heroicons:rocket-launch',
        'heroicons:shield-check',
        'heroicons:shopping-bag',
        'heroicons:sparkles',
        'heroicons:squares-2x2',
        'heroicons:stop',
        'heroicons:trash',
        'heroicons:user',
        'heroicons:wrench-screwdriver',
        'heroicons:x-circle',
        'heroicons:x-mark'
      ],
      sizeLimitKb: 512
    }
  },
  app: {
    head: {
      title: 'App Debug',
      meta: [
        { name: 'description', content: 'Local iOS and Android debug workspace' },
        { name: 'theme-color', content: '#090b10' }
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }]
    }
  },
  nitro: {
    devProxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true
      }
    }
  }
})
