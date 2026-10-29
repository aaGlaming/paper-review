<script setup lang="ts">
import EmptyIllustration from './EmptyIllustration.vue'

/**
 * 评分空态插画：五维待取证——五个空档位框排成不规则两行，中间一枚放大镜。
 * 叙事：确认章节树之后，五维才会逐个取证选档。
 */
</script>

<template>
  <EmptyIllustration title="五个维度等待取证">
    <!-- 五个档位框：大小不一、轻微错位 -->
    <rect x="52" y="36" width="40" height="26" rx="2" stroke="currentColor" stroke-width="1.4" />
    <rect x="100" y="32" width="40" height="26" rx="2" stroke="currentColor" stroke-width="1.2" opacity="0.7" />
    <rect x="148" y="38" width="40" height="26" rx="2" stroke="currentColor" stroke-width="1.2" opacity="0.7" />
    <rect x="72" y="72" width="40" height="26" rx="2" stroke="currentColor" stroke-width="1.2" opacity="0.7" />
    <rect x="122" y="76" width="40" height="26" rx="2" stroke="currentColor" stroke-width="1.2" stroke-dasharray="5 4" />
    <!-- 放大镜：圆 + 柄 + 复线 -->
    <circle cx="168" cy="100" r="16" stroke="currentColor" stroke-width="1.5" />
    <circle cx="168" cy="100" r="19.5" stroke="currentColor" stroke-width="0.9" opacity="0.45" />
    <path d="M180 112 C184 116 188 120 192 124" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <!-- 引线：从镜片连到待查框 -->
    <path d="M156 90 C140 84 130 78 124 72" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-dasharray="4 4" opacity="0.6" />
  </EmptyIllustration>
</template>
