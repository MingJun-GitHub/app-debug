export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  ssr: false,
  colorMode: {
    preference: 'dark',
    fallback: 'dark'
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
