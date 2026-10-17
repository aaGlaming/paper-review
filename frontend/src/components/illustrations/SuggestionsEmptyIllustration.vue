<script setup lang="ts">
import EmptyIllustration from './EmptyIllustration.vue'

/**
 * 建议空态插画：三段修改清单待生成——三个清单项纵向排，首项被铅笔圈起。
 * 叙事：先改硬伤、再补证据、最后改表述，三段按序来。
 */
</script>

<template>
  <EmptyIllustration title="三段修改清单等待生成">
    <!-- 三个清单项：勾选框 + 横线 -->
    <rect x="60" y="36" width="12" height="12" rx="1" stroke="currentColor" stroke-width="1.4" />
    <path d="M82 42 C110 40 140 41 168 42" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
    <rect x="60" y="62" width="12" height="12" rx="1" stroke="currentColor" stroke-width="1.2" opacity="0.7" />
    <path d="M82 68 C110 66 140 67 168 68" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.7" />
    <rect x="60" y="88" width="12" height="12" rx="1" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 3" opacity="0.7" />
    <path d="M82 94 C110 92 140 93 168 94" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.7" />
    <!-- 铅笔圈起首项 -->
    <ellipse cx="115" cy="43" rx="58" ry="17" stroke="currentColor" stroke-width="1.4" />
    <ellipse cx="116" cy="44.5" rx="55" ry="15" stroke="currentColor" stroke-width="0.9" opacity="0.5" />
    <!-- 铅笔：一杆 + 笔尖 -->
    <path d="M170 108 C182 100 194 92 204 84" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <path d="M204 84 L210 78 L205 76 Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" />
  </EmptyIllustration>
</template>
