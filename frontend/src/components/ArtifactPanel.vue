<script setup lang="ts">
import { computed, reactive } from 'vue'

import type { PaperSection, ReviewArtifact } from '../api/types'

const props = withDefaults(defineProps<{
  artifacts: ReviewArtifact[]
  sections?: PaperSection[]
  canExtract?: boolean
  extracting?: boolean
  errorMessage?: string
}>(), {
  canExtract: false,
  extracting: false,
  errorMessage: '',
  sections: () => [],
})

const emit = defineEmits<{
  locate: [artifact: ReviewArtifact]
  extract: []
}>()

const expanded = reactive(new Set<number>())
const groups = computed(() => ({
  claim: props.artifacts.filter((item) => item.artifact_type === 'claim'),
  table: props.artifacts.filter((item) => item.artifact_type === 'table'),
  citation: props.artifacts.filter((item) => item.artifact_type === 'citation'),
}))
const groupMeta = [
  { type: 'claim' as const, title: '主张' },
  { type: 'table' as const, title: '表格' },
  { type: 'citation' as const, title: '引用' },
]

function claimText(item: ReviewArtifact): string {
  const text = item.claim_text ?? ''
  return !expanded.has(item.artifact_id) && text.length > 80 ? `${text.slice(0, 80)}…` : text
}

function tableRows(markdown: string | null): { headers: string[]; rows: string[][] } {
  const lines = (markdown ?? '').split(/\r?\n/).filter((line) => line.trim().startsWith('|'))
  const cells = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim())
  if (!lines.length) return { headers: [], rows: [] }
  const headers = cells(lines[0])
  const rows = lines.slice(2).map(cells)
  return { headers, rows }
}

function toggleClaim(id: number): void {
  if (expanded.has(id)) expanded.delete(id)
  else expanded.add(id)
}

function citationSection(item: ReviewArtifact): string {
  const section = props.sections.find((candidate) =>
    typeof candidate.char_start === 'number' && typeof candidate.char_end === 'number' &&
    candidate.char_start <= item.char_start && item.char_start < candidate.char_end,
  )
  return section?.title || item.section_type || '未分类'
}
</script>

<template>
  <section class="artifact-panel" data-testid="artifact-panel" aria-label="抽取产物">
    <template v-if="artifacts.length">
      <section v-for="group in groupMeta" :key="group.type" class="artifact-group" :data-testid="`artifact-group-${group.type}`">
        <h3 class="artifact-group__title">{{ group.title }} <span>({{ groups[group.type].length }})</span></h3>
        <p v-if="!groups[group.type].length" class="artifact-group__none">无</p>
        <ul v-else class="artifact-group__list">
          <li v-for="item in groups[group.type]" :key="item.artifact_id" class="artifact-item">
            <button type="button" class="artifact-item__locate" @click="emit('locate', item)">
              <template v-if="group.type === 'claim'">
                {{ claimText(item) }}
                <span v-if="(item.claim_text?.length ?? 0) > 80" class="artifact-item__expand" @click.stop="toggleClaim(item.artifact_id)">
                  {{ expanded.has(item.artifact_id) ? '收起' : '展开' }}
                </span>
              </template>
              <template v-else-if="group.type === 'citation'">
                {{ item.citation_text }} <span class="artifact-item__section">{{ citationSection(item) }}</span>
              </template>
              <template v-else>
                <table class="artifact-table">
                  <thead><tr><th v-for="(head, index) in tableRows(item.table_markdown).headers" :key="index">{{ head }}</th></tr></thead>
                  <tbody><tr v-for="(row, rowIndex) in tableRows(item.table_markdown).rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody>
                </table>
              </template>
            </button>
          </li>
        </ul>
      </section>
    </template>
    <div v-else class="artifact-panel__empty" data-testid="artifact-empty">
      <span>本篇未抽取到产物</span>
      <button v-if="canExtract" type="button" :disabled="extracting" @click="emit('extract')">
        {{ extracting ? '抽取中…' : '抽取' }}
      </button>
    </div>
    <p v-if="extracting && artifacts.length" class="artifact-panel__status" role="status">正在抽取产物…</p>
    <p v-if="errorMessage" class="artifact-panel__error" role="alert">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.artifact-panel { display: grid; gap: var(--pr-space-2); width: 100%; }
.artifact-group { min-width: 0; }
.artifact-group__title { margin: 0 0 var(--pr-space-1); font-size: var(--pr-text-sm); font-weight: 600; }
.artifact-group__title span, .artifact-group__none, .artifact-item__section { color: var(--pr-ink-muted); }
.artifact-group__none { margin: 0; font-size: var(--pr-text-sm); }
.artifact-group__list { display: grid; gap: var(--pr-space-1); margin: 0; padding: 0; list-style: none; }
.artifact-item__locate { width: 100%; border: 0; padding: var(--pr-space-2); background: var(--pr-surface); color: var(--pr-ink); text-align: left; cursor: pointer; }
.artifact-item__locate:hover { background: var(--pr-slot-bg); }
.artifact-item__expand { margin-left: var(--pr-space-1); color: var(--pr-primary-strong); text-decoration: underline; }
.artifact-item__section { display: block; margin-top: var(--pr-space-1); font-size: var(--pr-text-xs); }
.artifact-table { border-collapse: collapse; font-size: var(--pr-text-xs); }
.artifact-table th, .artifact-table td { padding: 2px var(--pr-space-2); border: 1px solid var(--pr-rule); }
.artifact-panel__empty { display: flex; align-items: center; gap: var(--pr-space-3); }
.artifact-panel__status, .artifact-panel__error { margin: 0; }
.artifact-panel__error { color: var(--pr-range); }
</style>
