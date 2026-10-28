export type PageSiteKey = 'us' | 'uk' | 'au' | 'eu' | 'de' | 'fr'

export interface PageSite {
  key: PageSiteKey
  label: string
  deepHost: string
  webHost: string
}

export interface PageShortcut {
  id: string
  label: string
  description: string
  path: string
  icon: string
}

export interface PageShortcutGroup {
  key: string
  label: string
  items: PageShortcut[]
}

export const PAGE_URL_DOC =
  'https://bloomchic.feishu.cn/wiki/PjUgwVqCYimx4XkkLhwckceKnAf'

export const PAGE_SITES: PageSite[] = [
  { key: 'us', label: '美国站', deepHost: 'app', webHost: 'bloomchic.com' },
  { key: 'uk', label: '英国站', deepHost: 'app.uk', webHost: 'bloomchic.co.uk' },
  { key: 'au', label: '澳洲站', deepHost: 'app.au', webHost: 'bloomchic.au' },
  { key: 'eu', label: '欧洲站', deepHost: 'app.eu', webHost: 'bloomchic.eu' },
  { key: 'de', label: '德国站', deepHost: 'app.de', webHost: 'bloomchic.de' },
  { key: 'fr', label: '法国站', deepHost: 'app.fr', webHost: 'bloomchic.fr' }
]

export const PAGE_SHORTCUT_GROUPS: PageShortcutGroup[] = [
  {
    key: 'common',
    label: '常用页面',
    items: [
      { id: 'home', label: '首页', description: 'Home Tab', path: '?tab=home', icon: 'i-heroicons-home' },
      { id: 'category', label: '分类', description: 'Category Tab', path: '?tab=category', icon: 'i-heroicons-squares-2x2' },
      { id: 'cart', label: '购物车', description: 'Cart', path: '/cart', icon: 'i-heroicons-shopping-bag' },
      { id: 'me', label: '我的', description: 'Me Tab', path: '?tab=me', icon: 'i-heroicons-user' },
      { id: 'search', label: '搜索', description: 'Search Page', path: '/search-page?q=', icon: 'i-heroicons-magnifying-glass' },
      { id: 'wishlist', label: '心愿单', description: 'Wishlist', path: '/wishlist', icon: 'i-heroicons-heart' }
    ]
  },
  {
    key: 'account',
    label: '账户页面',
    items: [
      { id: 'login', label: '登录', description: 'Sign In', path: '/account/login', icon: 'i-heroicons-arrow-right-on-rectangle' },
      { id: 'orders', label: '我的订单', description: 'My Orders', path: '/orders', icon: 'i-heroicons-clipboard-document-list' },
      { id: 'address', label: '地址管理', description: 'Address', path: '/address', icon: 'i-heroicons-map-pin' },
      { id: 'reviews', label: '我的评论', description: 'My Reviews', path: '/reviews', icon: 'i-heroicons-chat-bubble-left-right' },
      { id: 'member', label: '会员权益', description: 'Member Benefits', path: '/member_benefits', icon: 'i-heroicons-sparkles' }
    ]
  },
  {
    key: 'service',
    label: '设置与服务',
    items: [
      { id: 'settings', label: '设置', description: 'Settings', path: '/settings', icon: 'i-heroicons-cog-6-tooth' },
      { id: 'notifications', label: '通知设置', description: 'Notifications', path: '/settings/notification', icon: 'i-heroicons-bell' },
      { id: 'privacy', label: '隐私设置', description: 'Privacy', path: '/settings/privacy', icon: 'i-heroicons-shield-check' },
      { id: 'feedback', label: '用户反馈', description: 'Feedback', path: '/feedback', icon: 'i-heroicons-chat-bubble-oval-left' },
      { id: 'supports', label: '客服', description: 'Support', path: '/supports', icon: 'i-heroicons-lifebuoy' }
    ]
  }
]

export function pageSite(key: PageSiteKey) {
  return PAGE_SITES.find(site => site.key === key) || PAGE_SITES[0]
}

export function buildPageShortcutUrl(siteKey: PageSiteKey, shortcut: PageShortcut) {
  return `bloomchic://${pageSite(siteKey).deepHost}${shortcut.path}`
}
