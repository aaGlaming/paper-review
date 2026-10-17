<script setup lang="ts">
/**
 * 空态插画基座：统一尺寸、统一线条语言、统一无障碍处理。
 *
 * - 装饰性（默认）：`aria-hidden="true"`，不进无障碍树；
 * - 叙事性：传 `title` 即转为 `role="img"` + `<title>`，读屏只读一句。
 * - 颜色：线条 `currentColor`（跟墨色走双主题），强调色只用 `--pr-accent-soft`
 *   类语义变量，不写裸色值。
 */
defineProps<{ title?: string }>()
</script>

<template>
  <svg
    class="empty-illo"
    viewBox="0 0 240 150"
    fill="none"
    :role="title ? 'img' : undefined"
    :aria-hidden="title ? undefined : 'true'"
  >
    <title v-if="title">{{ title }}</title>
    <slot />
  </svg>
</template>

<style scoped>
.empty-illo {
  display: block;
  width: min(240px, 100%);
  height: auto;
  color: var(--pr-ink-faint);
}
</style>
