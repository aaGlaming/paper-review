<script setup lang="ts">
import type { ChatMessageItem as Message } from '../../api/types'

const props = defineProps<{ message: Message; rejected?: number }>()
const emit = defineEmits<{ reference: [reviewId: string] }>()
const marker = /\[review_id=([^\s\]]+)\s+dim=([^\s\]]+)\]/g
function parts(content: string): Array<{ text?: string; reviewId?: string; dimension?: string }> {
  const result: Array<{ text?: string; reviewId?: string; dimension?: string }> = []
  let offset = 0
  for (const match of content.matchAll(marker)) {
    const index = match.index ?? 0
    if (index > offset) result.push({ text: content.slice(offset, index) })
    result.push({ reviewId: match[1], dimension: match[2] })
    offset = index + match[0].length
  }
  if (offset < content.length) result.push({ text: content.slice(offset) })
  return result
}
</script>
<template>
  <article class="message" :class="`message--${props.message.role}`" :data-message-id="props.message.message_id">
    <div class="message__bubble">
      <template v-for="(part, index) in parts(props.message.content)" :key="index">
        <span v-if="part.text !== undefined">{{ part.text }}</span>
        <el-button v-else link type="primary" data-ref-chip @click="emit('reference', part.reviewId!)">{{ part.reviewId }} · {{ part.dimension }}</el-button>
      </template>
    </div>
    <small v-if="rejected" class="message__note">已移除 {{ rejected }} 条无法溯源的引用</small>
  </article>
</template>
<style scoped>
.message { display:flex; flex-direction:column; max-width:min(82%, 760px); margin:.8rem 0 }
.message--user { margin-left:auto; align-items:flex-end }
.message--assistant { margin-right:auto }
.message__bubble { padding:.85rem 1rem; background:var(--pr-surface); border:1px solid var(--pr-rule); white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.65 }
.message--user .message__bubble { background:var(--pr-primary-soft) }
.message__note { margin-top:.25rem; color:var(--pr-ink-muted) }
</style>
