<script setup lang="ts">
import EmptyIllustration from './EmptyIllustration.vue'

/**
 * 评测单篇缺口插画：汇总有数、单篇待接——三张小卡 + 一张虚线空卡，箭头指向空卡。
 * 叙事：汇总三项指标可看，单篇差异等后端单篇接口。
 */
</script>

<template>
  <EmptyIllustration title="单篇明细等待后端接口">
    <!-- 三张实卡 -->
    <rect x="36" y="48" width="44" height="52" rx="2" stroke="currentColor" stroke-width="1.4" />
    <path d="M44 64 C56 62 68 63 72 64" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    <rect x="88" y="42" width="44" height="52" rx="2" stroke="currentColor" stroke-width="1.2" opacity="0.75" />
    <path d="M96 58 C108 56 120 57 124 58" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" opacity="0.75" />
    <rect x="140" y="48" width="28" height="52" rx="2" stroke="currentColor" stroke-width="1.2" opacity="0.75" />
    <!-- 一张虚线空卡 + 箭头 -->
    <rect x="176" y="56" width="28" height="44" rx="2" stroke="currentColor" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.8" />
    <path d="M150 110 C160 116 168 120 174 122" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    <path d="M168 118 L175 123 L169 127" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
  </EmptyIllustration>
</template>
