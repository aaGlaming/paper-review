<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ApiError } from '../api'
import { useAuth } from '../composables/useAuth'
import { resolveRedirect } from '../router'

/**
 * 登录页。居中卡片 + 背景图（见 P4 压图脚本）。
 *
 * 三条纪律：
 * 1. 错误提示直接用 `ApiError.message`（后端已统一成「用户名或密码错误」），前端不翻译。
 * 2. 跳转只接受以 `/` 开头且不以 `//` 开头的相对路径（防开放重定向，见 resolveRedirect）。
 * 3. token 只进 localStorage 与 Authorization 头，不拼 URL、不打日志。
 */

const LOGIN_BACKGROUND_URL = new URL('../../pictures/login_background.webp', import.meta.url).href

const route = useRoute()
const router = useRouter()
const { login } = useAuth()

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

async function submit(): Promise<void> {
  if (busy.value) {
    return
  }
  busy.value = true
  error.value = ''
  try {
    await login(username.value.trim(), password.value)
    await router.replace(resolveRedirect(route.query.redirect))
  } catch (reason) {
    error.value = reason instanceof ApiError ? reason.message : '登录失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login" :style="{ backgroundImage: `url(${LOGIN_BACKGROUND_URL})` }">
    <form class="login__card" @submit.prevent="submit">
      <h1 class="login__title">登录</h1>
      <label class="login__field">
        用户名
        <input v-model="username" name="username" autocomplete="username" required />
      </label>
      <label class="login__field">
        密码
        <input
          v-model="password"
          name="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <p v-if="error" class="login__error" role="alert">{{ error }}</p>
      <button class="login__submit" type="submit" :disabled="busy">
        {{ busy ? '登录中…' : '登录' }}
      </button>
      <p class="login__hint">
        还没有账号？
        <RouterLink to="/register">去注册</RouterLink>
      </p>
    </form>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  background-size: cover;
  background-position: center;
}

.login__card {
  display: flex;
  flex-direction: column;
  gap: var(--pr-space-4);
  min-width: 20rem;
  padding: var(--pr-space-6);
  background: var(--pr-surface);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius-card, 8px);
}

.login__title {
  margin: 0;
  font-size: var(--pr-text-xl);
}

.login__field {
  display: flex;
  flex-direction: column;
  gap: var(--pr-space-2);
}

.login__error {
  color: var(--pr-danger);
}

.login__hint {
  margin: 0;
}
</style>
