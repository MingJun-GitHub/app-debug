<template>
  <svg
    viewBox="0 0 64 64"
    role="img"
    aria-label="App Debug"
  >
    <defs>
      <linearGradient id="app-debug-bg" x1="10" y1="8" x2="54" y2="57" gradientUnits="userSpaceOnUse">
        <stop stop-color="#15372b" />
        <stop offset="1" stop-color="#09130f" />
      </linearGradient>
      <linearGradient id="app-debug-bracket" x1="12" y1="18" x2="52" y2="46" gradientUnits="userSpaceOnUse">
        <stop stop-color="#86efac" />
        <stop offset="1" stop-color="#22c55e" />
      </linearGradient>
    </defs>
    <rect x="3" y="3" width="58" height="58" rx="16" fill="url(#app-debug-bg)" stroke="#2f7556" stroke-width="1.5" />
    <path d="M22 20 12 32l10 12" fill="none" stroke="url(#app-debug-bracket)" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round" />
    <path d="m42 20 10 12-10 12" fill="none" stroke="url(#app-debug-bracket)" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M23 32h4l2.2-5.5 4.3 11 2.2-5.5H40" fill="none" stroke="#e8fff2" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="32.2" cy="15.3" r="2.2" fill="#facc15" />
  </svg>
</template>
