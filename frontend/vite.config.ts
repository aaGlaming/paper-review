import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'

const REPOSITORY_ROOT = fileURLToPath(new URL('..', import.meta.url))

// 后端没有 CORS 中间件，而 P8 不许改后端：页面一律用相对路径 /api/...，
// 开发与 E2E 都靠这里的代理转到 8077。不走代理，五个页面一个都连不上后端。
const BACKEND_ORIGIN = 'http://127.0.0.1:8077'

export default defineConfig({
  plugins: [vue()],
  server: {
    fs: { allow: [REPOSITORY_ROOT] },
    // 固定 IPv4 回环：不写死 host 时 Vite 可能只监听 [::1]，而 baseURL 与
    // Playwright 的就绪探测用的是 127.0.0.1，两边会对不上。
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
      },
    },
  },
})
