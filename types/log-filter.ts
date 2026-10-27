export interface LogFilter {
  id: string
  label: string
  query: string
  regex: boolean
  icon?: string
  builtIn?: boolean
}

export const DEFAULT_LOG_FILTERS: LogFilter[] = [
  {
    id: 'all',
    label: '全部日志',
    query: '',
    regex: false,
    icon: 'i-heroicons-list-bullet',
    builtIn: true
  },
  {
    id: 'network-request',
    label: '网络请求',
    query: 'HttpLogging.*(-->|GET|POST|PUT|PATCH|DELETE)',
    regex: true,
    icon: 'i-heroicons-globe-alt',
    builtIn: true
  },
  {
    id: 'network-response',
    label: '网络响应',
    query: 'HttpLogging.*<--',
    regex: true,
    icon: 'i-heroicons-arrow-down-circle',
    builtIn: true
  },
  {
    id: 'network-error',
    label: '网络错误',
    query: 'HttpLogging.*(ERROR|error|timeout|failed)',
    regex: true,
    icon: 'i-heroicons-signal-slash',
    builtIn: true
  },
  {
    id: 'sensors',
    label: '神策事件',
    query: 'trackEvent|onTrackEvent|SensorsAnalytics|sensorsdata|BCSensors',
    regex: true,
    icon: 'i-heroicons-chart-bar',
    builtIn: true
  },
  {
    id: 'lifecycle',
    label: '页面 / 生命周期',
    query: 'onCreate|onResume|onPause|FrontPageShow|PageShow|BloomJourney',
    regex: true,
    icon: 'i-heroicons-window',
    builtIn: true
  },
  {
    id: 'commerce',
    label: '商品 / 购物车',
    query: 'ProductClick|ProductShow|AddToCartClick|Cart|Checkout|Order',
    regex: true,
    icon: 'i-heroicons-shopping-bag',
    builtIn: true
  },
  {
    id: 'errors',
    label: '错误 / 崩溃',
    query: 'error|exception|FATAL EXCEPTION|AndroidRuntime|SIGABRT|fatal error',
    regex: true,
    icon: 'i-heroicons-bug-ant',
    builtIn: true
  },
  {
    id: 'build',
    label: '构建任务',
    query: 'xcodebuild|BUILD (SUCCEEDED|FAILED)|> Task|gradle',
    regex: true,
    icon: 'i-heroicons-wrench-screwdriver',
    builtIn: true
  }
]

export const ALL_LOG_FILTER = DEFAULT_LOG_FILTERS[0]
