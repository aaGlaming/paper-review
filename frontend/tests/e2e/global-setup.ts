/**
 * E2E 全局准备：注册（或登录）固定学生与教师账号，把 token 写进 storageState。
 *
 * 走 5173 的 Vite 代理（与页面同源），打的同样是后端 /api/auth/*。
 * 账号已存在（409）则改用 login。产物进 tests/e2e/.auth/（已进 .gitignore，不提交）。
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { request, type APIRequestContext } from '@playwright/test'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const AUTH_DIR = path.join(HERE, '.auth')
const STATE_FILE = path.join(AUTH_DIR, 'user.json')
const TEACHER_STATE_FILE = path.join(AUTH_DIR, 'teacher.json')

const BASE_URL = 'http://127.0.0.1:5173'
const USERNAME = 'e2e_student'
const PASSWORD = 'e2e-password-123'
const TEACHER_USERNAME = 'e2e_teacher'
const TEACHER_PASSWORD = 'e2e-teacher-password-123'

async function registerOrLogin(
  context: APIRequestContext,
  username: string,
  email: string,
  password: string,
  displayName: string,
): Promise<string> {
  const registered = await context.post('/api/auth/register', {
    data: { username, email, password, display_name: displayName },
  })

  if (registered.status() !== 201 && registered.status() !== 409) {
    throw new Error(`globalSetup register failed: ${registered.status()}`)
  }
  const logged = await context.post('/api/auth/login', {
    data: { username, password },
  })
  if (!logged.ok()) {
    throw new Error(`globalSetup login failed: ${logged.status()}`)
  }
  const token = (await logged.json()).token as string | undefined
  if (!token) throw new Error('globalSetup: no token in login response')
  return token
}

function writeState(file: string, token: string): void {
  fs.writeFileSync(
    file,
    JSON.stringify(
      {
        cookies: [],
        origins: [
          {
            origin: BASE_URL,
            localStorage: [{ name: 'pr.auth.token', value: token }],
          },
        ],
      },
      null,
      2,
    ),
  )
}

async function globalSetup(): Promise<void> {
  const context = await request.newContext({ baseURL: BASE_URL })
  try {
    const token = await registerOrLogin(
      context, USERNAME, 'e2e-student@example.com', PASSWORD, 'E2E 学生',
    )
    const teacherToken = await registerOrLogin(
      context,
      TEACHER_USERNAME,
      'e2e-teacher@example.com',
      TEACHER_PASSWORD,
      'E2E 教师',
    )
    const me = await context.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${teacherToken}` },
    })
    if (!me.ok()) {
      throw new Error(`globalSetup teacher identity check failed: ${me.status()}`)
    }
    const teacher = (await me.json()) as { permissions?: string[] }
    if (!teacher.permissions?.includes('review:read:all')) {
      throw new Error('e2e_teacher 缺少 review:read:all；先运行 python scripts/promote_e2e_teacher.py 再跑 E2E')
    }

    fs.mkdirSync(AUTH_DIR, { recursive: true })
    writeState(STATE_FILE, token)
    writeState(TEACHER_STATE_FILE, teacherToken)
  } finally {
    await context.dispose()
  }
}

export default globalSetup
