<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuth } from '../composables/useAuth'
import ThemeToggle from './ThemeToggle.vue'

// 五个页面入口。顺序即评审流程的顺序：先解析、再评分、再审查、再改、最后对照评测。
const items = [
  { label: '论文解析', to: '/parse' },
  { label: '分项评分', to: '/scoring' },
  { label: '一致性审查', to: '/consistency' },
  { label: '修改建议', to: '/suggestions' },
  { label: '评测对照', to: '/eval' },
  { label: '记录总览', to: '/records', permission: 'review:read:all' },
  { label: 'AI 问询', to: '/chat', permission: 'chat:use' },
  { label: '数据大屏', to: '/dashboard', permission: 'dashboard:view' },
] as const

// 权限项通过 hasPermission 才加入可点导航。
const { token, user, restoreError, hasPermission, logout, restore } = useAuth()
const router = useRouter()
const recoveryBusy = ref(false)
const visibleItems = computed(() =>
  items.filter((item) => !('permission' in item) || hasPermission(item.permission)),
)

function roleLabel(role: string | undefined): string {
  if (role === 'teacher') {
    return '教师'
  }
  return '学生'
}

async function signOut(): Promise<void> {
  await logout()
  await router.replace('/login')
}

async function retrySession(): Promise<void> {
  if (recoveryBusy.value) return
  recoveryBusy.value = true
  try {
    await restore()
  } catch {
    // useAuth.restoreError 提供可见原因；401 会清除 token，下面转到登录页。
  } finally {
    recoveryBusy.value = false
  }
  if (!token.value) await router.replace('/login')
}
</script>

<template>
  <header class="nav">
    <div class="nav__brand">
      <span class="nav__flow" aria-hidden="true">01–05</span>
      <span class="nav__name">竞赛论文预审工作台</span>
    </div>
    <nav class="nav__links">
      <RouterLink
        v-for="item in visibleItems"
        :key="item.to"
        :to="item.to"
        class="nav__link"
        data-nav-item
      >
        {{ item.label }}
      </RouterLink>
    </nav>
    <div v-if="token && !user" class="nav__recovery" data-testid="session-recovery" role="status">
      <span>{{ restoreError || '正在验证登录状态，权限页面暂不可见。' }}</span>
      <button data-testid="session-retry" type="button" :disabled="recoveryBusy" @click="retrySession">
        {{ recoveryBusy ? '正在验证…' : '重新验证' }}
      </button>
      <button data-testid="session-clear" type="button" @click="signOut">退出并重新登录</button>
    </div>
    <div class="nav__spacer" aria-hidden="true"></div>
    <div v-if="user" class="nav__user" data-nav-user>
      <span class="nav__username">{{ user.username }}</span>
      <span class="nav__role" data-nav-role>{{ roleLabel(user.role) }}</span>
      <button class="nav__logout" data-nav-logout type="button" @click="signOut">退出</button>
    </div>
    <ThemeToggle />
  </header>
</template>

<style scoped>
.nav {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--pr-space-6);
  padding: var(--pr-space-3) var(--pr-space-4);
  border-bottom: 1px solid var(--pr-rule);
  background: var(--pr-surface);
  box-shadow: var(--pr-shadow-paper);
}

.nav__brand {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
  flex: none;
}

.nav__flow {
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-lg);
  color: var(--pr-ink-faint);
  letter-spacing: 0.02em;
}

.nav__name {
  font-size: var(--pr-text-lg);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.nav__links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-4);
}

.nav__spacer {
  flex: 1;
}

.nav__recovery {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--pr-space-2) var(--pr-space-3);
  flex-basis: 100%;
  padding: var(--pr-space-2) var(--pr-space-3);
  border-inline-start: 3px solid var(--pr-warning);
  background: var(--pr-surface-raised, var(--pr-surface));
  color: var(--pr-ink-muted);
}

.nav__recovery button {
  border: 0;
  background: transparent;
  color: var(--pr-ink);
  text-decoration: underline;
  cursor: pointer;
}

.nav__recovery button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.nav__link {
  position: relative;
  padding-bottom: var(--pr-space-1);
  color: var(--pr-ink-muted);
  text-decoration: none;
}

.nav__link:hover {
  color: var(--pr-ink);
}

.nav__link.router-link-active {
  color: var(--pr-ink);
}

/* 激活态：手绘下划线（sketch-underline.svg），替代 CSS 下划线 */
.nav__link.router-link-active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 10px;
  background-image: url('../../../docs/design/sketch-svg/sketch-underline.svg');
  background-size: 100% 100%;
  background-repeat: no-repeat;
  pointer-events: none;
}

.nav__user {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--pr-space-3);
  flex: none;
  min-width: 0;
}

.nav__role {
  color: var(--pr-ink-muted);
}

.nav__logout {
  padding: 0;
  border: none;
  background: none;
  color: var(--pr-ink-muted);
  cursor: pointer;
}

.nav__logout:hover {
  color: var(--pr-ink);
}
</style>
