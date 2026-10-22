<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { ApiError, authRegister } from '../api'
import { useAuth } from '../composables/useAuth'
import PostLoginIntro from '../components/PostLoginIntro.vue'

/**
 * 注册页。成功 201 后自动登录一次再跳 `/parse`（少一次输密码）。
 *
 * 前端只做两条即时校验：两次密码一致、密码长度 8~64。其余（用户名格式、
 * 邮箱格式、重复）全交给后端，避免两套规则不一致。409 统一显示
 * 「该注册信息不可用」，不猜是用户名还是邮箱（防枚举）。
 */

const router = useRouter()
const { login } = useAuth()

const username = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const displayName = ref('')
const busy = ref(false)
const error = ref('')
const showIntro = ref(false)

async function enterSystem(): Promise<void> {
  if (!showIntro.value) return
  showIntro.value = false
  await router.replace('/parse')
  await nextTick()
  document.querySelector<HTMLElement>('.shell__body')?.focus({ preventScroll: true })
}

const mismatch = computed(() => confirm.value !== '' && password.value !== confirm.value)
const badLength = computed(
  () => password.value !== '' && (password.value.length < 8 || password.value.length > 64),
)
const canSubmit = computed(
  () =>
    !busy.value &&
    username.value.trim() !== '' &&
    email.value.trim() !== '' &&
    password.value !== '' &&
    !mismatch.value &&
    !badLength.value,
)

async function submit(): Promise<void> {
  if (!canSubmit.value) {
    if (mismatch.value) {
      error.value = '两次输入的密码不一致'
    } else if (badLength.value) {
      error.value = '密码长度需为 8~64 位'
    }
    return
  }
  busy.value = true
  error.value = ''
  try {
    await authRegister({
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
      display_name: displayName.value.trim(),
    })
    await login(username.value.trim(), password.value)
    showIntro.value = true
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 409) {
      error.value = '该注册信息不可用'
    } else {
      error.value = reason instanceof ApiError ? reason.message : '注册失败，请稍后重试'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="register-scene">
    <form class="register" @submit.prevent="submit">
      <h1 class="register__title">注册</h1>
      <label class="register__field">
        用户名
        <input v-model="username" name="username" autocomplete="username" required />
      </label>
      <label class="register__field">
        邮箱
        <input v-model="email" name="email" type="email" autocomplete="email" required />
      </label>
      <label class="register__field">
        密码
        <input
          v-model="password"
          name="password"
          type="password"
          autocomplete="new-password"
          required
        />
      </label>
      <label class="register__field">
        确认密码
        <input
          v-model="confirm"
          name="confirm"
          type="password"
          autocomplete="new-password"
          required
        />
      </label>
      <label class="register__field">
        显示名（可选）
        <input v-model="displayName" name="display_name" autocomplete="nickname" />
      </label>
      <p v-if="error" class="register__error" role="alert">{{ error }}</p>
      <button class="register__submit" type="submit" :disabled="!canSubmit">
        {{ busy ? '注册中…' : '注册并登录' }}
      </button>
      <p class="register__hint">
        已有账号？
        <RouterLink to="/login">去登录</RouterLink>
      </p>
    </form>
    <PostLoginIntro v-if="showIntro" @continue="enterSystem" />
  </div>
</template>

<style scoped>
.register {
  display: flex;
  flex-direction: column;
  gap: var(--pr-space-4);
  max-width: 24rem;
  margin: 0 auto;
  padding: var(--pr-space-6);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  box-shadow: var(--pr-shadow-sheet);
}

.register-scene {
  display: grid;
  place-items: center;
  width: 100%;
  min-height: 100vh;
  padding: var(--pr-space-4);
}

.register__title {
  margin: 0;
  font-size: var(--pr-text-xl);
}

.register__field {
  display: flex;
  flex-direction: column;
  gap: var(--pr-space-2);
}

.register__error {
  color: var(--pr-danger);
}

.register__hint {
  margin: 0;
}
</style>
