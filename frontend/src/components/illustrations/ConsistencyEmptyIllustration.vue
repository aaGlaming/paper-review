<script setup lang="ts">
import EmptyIllustration from './EmptyIllustration.vue'

/**
 * 审查空态插画：硬伤待核对——两处数值被手绘圈注起，中间一道对勾引线。
 * 叙事：数字打架、引用失联都在这里逐条定位核对。
 */
</script>

<template>
  <EmptyIllustration title="两处数值等待核对">
    <!-- 对比两行：微弯基线 + 数值短线 -->
    <path d="M50 52 C90 50 130 51 175 52" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    <path d="M50 88 C90 86 130 87 175 88" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    <path d="M120 46 L150 46" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    <path d="M118 82 L142 82" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    <!-- 手绘圈：绕两处数值各一圈 -->
    <ellipse cx="135" cy="50" rx="26" ry="14" stroke="currentColor" stroke-width="1.5" />
    <ellipse cx="136.5" cy="51.5" rx="23" ry="12" stroke="currentColor" stroke-width="0.9" opacity="0.5" />
    <ellipse cx="130" cy="86" rx="24" ry="13" stroke="currentColor" stroke-width="1.5" />
    <!-- 对勾引线 -->
    <path d="M185 60 C190 70 196 82 202 96" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="4 4" opacity="0.6" />
    <path d="M196 108 L203 115 L213 102" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
  </EmptyIllustration>
</template>
