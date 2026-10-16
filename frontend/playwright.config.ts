import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const CONFIG_DIR = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = path.resolve(CONFIG_DIR, '..')

// 后端解释器来自提示词指定的 agent-task 环境；允许用环境变量换掉，便于换机器。
const PYTHON =
  process.env.PAPER_REVIEW_PYTHON ??
  path.join('D:', 'LEARN', 'AI', 'programs', 'AgentTask', 'env', 'agent-task', 'Scripts', 'python.exe')

export default defineConfig({
  testDir: './tests/e2e',
  // 本阶段的冒烟用例只有一个，串行跑，避免两个 webServer 被并发重启。
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: [['list']],
  use: {
    // E2E 必须走 Vite 的 5173，才能吃到 /api 代理；直连 8077 等于把代理这条链路跳过去。
    baseURL: 'http://127.0.0.1:5173',
    trace: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8077`,
      cwd: PROJECT_ROOT,
      url: 'http://127.0.0.1:8077/api/contests',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --port 5173',
      cwd: CONFIG_DIR,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
})
