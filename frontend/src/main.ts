import ElementPlus from 'element-plus'
import { createApp } from 'vue'

// 先引 Element Plus 的样式，再引设计令牌：令牌里的主题变量要覆盖它。
import 'element-plus/dist/index.css'
import './styles/tokens.css'

import App from './App.vue'
import { THEME_STORAGE_KEY, getPreferredTheme, type Theme } from './composables/useTheme'
import router from './router'

// 先定主题再挂载，避免首屏闪白：存档优先，其次跟系统偏好。
try {
  const raw = localStorage.getItem(THEME_STORAGE_KEY)
  const stored: Theme | null = raw === 'light' || raw === 'dark' ? raw : null
  document.documentElement.setAttribute('data-theme', stored ?? getPreferredTheme())
} catch {
  document.documentElement.setAttribute('data-theme', 'light')
}

createApp(App).use(router).use(ElementPlus).mount('#app')
