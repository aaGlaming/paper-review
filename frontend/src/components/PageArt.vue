<script setup lang="ts">
/**
 * 每页背景画：大插画 + 小插画的双图组合，纯装饰不进无障碍树。
 *
 * - 大图放内容区一侧空白（桌面端可见），小图放另一处留白；
 * - 全部 `aria-hidden + pointer-events: none`，不挡交互；
 * - 颜色走墨色变量 + 透明度令牌，跟双主题；
 * - 900px 以下只留小图（大图隐藏），390px 以下全藏，不挤内容。
 */
defineProps<{ art: string; spot: string; layout?: 'right' | 'left' }>()
</script>

<template>
  <div class="page-art" :data-layout="layout ?? 'right'" aria-hidden="true">
    <img class="page-art__main" :src="art" alt="" aria-hidden="true" />
    <img class="page-art__spot" :src="spot" alt="" aria-hidden="true" />
  </div>
</template>

<style scoped>
.page-art {
  pointer-events: none;
  position: relative;
  color: var(--pr-ink);
}

.page-art__main,
.page-art__spot {
  position: fixed;
  z-index: 0;
  pointer-events: none;
  opacity: var(--pr-bg-draft-opacity);
}

/* 默认布局：大图贴右下空白，小图贴左上空白（错开页缘线稿） */
.page-art[data-layout='right'] .page-art__main {
  right: 2vw;
  bottom: 6vh;
  width: min(300px, 24vw);
}

.page-art[data-layout='right'] .page-art__spot {
  left: 3vw;
  top: 22vh;
  width: min(150px, 13vw);
  opacity: var(--pr-bg-corner-opacity);
}

.page-art[data-layout='left'] .page-art__main {
  left: 2vw;
  bottom: 6vh;
  width: min(300px, 24vw);
}

.page-art[data-layout='left'] .page-art__spot {
  right: 3vw;
  top: 22vh;
  width: min(150px, 13vw);
  opacity: var(--pr-bg-corner-opacity);
}

@media (max-width: 1100px) {
  .page-art__main {
    display: none;
  }
}

@media (max-width: 900px) {
  .page-art {
    display: none;
  }
}
</style>
