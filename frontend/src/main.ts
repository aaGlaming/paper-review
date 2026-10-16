import ElementPlus from 'element-plus'
import { createApp } from 'vue'

// 先引 Element Plus 的样式，再引设计令牌：令牌里的主题变量要覆盖它。
import 'element-plus/dist/index.css'
import './styles/tokens.css'

import App from './App.vue'
import router from './router'

createApp(App).use(router).use(ElementPlus).mount('#app')
