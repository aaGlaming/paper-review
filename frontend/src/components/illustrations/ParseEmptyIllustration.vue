<script setup lang="ts">
import EmptyIllustration from './EmptyIllustration.vue'

/**
 * 解析空态插画：稿源未定——一张空白稿纸 + 虚线稿源框 + 手绘箭头指向它。
 * 叙事：先把稿子放进来，章节树才会长出来。
 */
</script>

<template>
  <EmptyIllustration title="空稿纸等待稿源">
    <!-- 空稿纸：微弯轮廓 + 两道待写横线 -->
    <path d="M70 22 C110 19 150 20 186 22 C187 60 187 100 186 130 C150 132 110 131 70 130 C69 100 69 60 70 22 Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <path d="M74 26 C110 23.5 148 24.5 182 26" stroke="currentColor" stroke-width="1" stroke-linecap="round" opacity="0.5" />
    <path d="M86 52 C112 50 140 51 166 52" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-dasharray="5 5" opacity="0.7" />
    <path d="M86 68 C112 66 140 67 166 68" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-dasharray="5 5" opacity="0.7" />
    <!-- 稿源框：左下虚线框 + 圈注 -->
    <rect x="30" y="96" width="52" height="30" rx="2" stroke="currentColor" stroke-width="1.2" stroke-dasharray="5 4" />
    <path d="M56 88 C70 80 84 74 96 66" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    <path d="M90 62 L97 65 L92 71" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
    <!-- 纸角测量标 -->
    <path d="M196 22 L206 22 M201 22 L201 32" stroke="currentColor" stroke-width="1" stroke-linecap="round" opacity="0.6" />
  </EmptyIllustration>
</template>
