<script setup lang="ts">
import type { AnalyticsResponse, SummaryResponse } from '../../api/types'

defineProps<{ result: AnalyticsResponse | SummaryResponse | null; loading: boolean; error: string }>()
const emit = defineEmits<{ run: [kind: 'bands' | 'conflicts' | 'summary']; clear: [] }>()
</script>
<template>
  <section class="analytics" aria-label="统计结果">
    <div class="analytics__actions">
      <el-button :loading="loading" @click="emit('run','bands')">档位汇总</el-button>
      <el-button :loading="loading" @click="emit('run','conflicts')">冲突汇总</el-button>
      <el-button :loading="loading" @click="emit('run','summary')">生成摘要</el-button>
      <el-button v-if="result" text @click="emit('clear')">清空结果</el-button>
    </div>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <div v-if="result" class="analytics__result" data-analytics-result>
      <template v-if="'content' in result">
        <p class="summary">{{ result.content }}</p>
        <p v-if="result.notes.evidence_short" class="muted">可用证据少于 3 条（{{ result.notes.evidence_short }} 条）</p>
      </template>
      <el-table v-else-if="'bands' in result.result" :data="result.result.bands" stripe>
        <el-table-column prop="dimension_code" label="维度" />
        <el-table-column label="档位计数"><template #default="scope">{{ Object.entries(scope.row.counts).map(([band,count]) => `${band}：${count}`).join('；') }}</template></el-table-column>
      </el-table>
      <ol v-else-if="'hotspots' in result.result" class="hotspots"><li v-for="item in result.result.hotspots.slice(0,5)" :key="item.target">{{ item.target }}（{{ item.count }}）</li><li v-if="!result.result.hotspots.length" class="muted">暂无汇总项</li></ol>
    </div>
  </section>
</template>
<style scoped>
.analytics { border-top:1px solid var(--pr-rule); padding-top:.8rem }
.analytics__actions { display:flex; flex-wrap:wrap; gap:.4rem }
.analytics__result { margin-top:.8rem; max-height:220px; overflow:auto; padding:.7rem; background:var(--pr-surface) }
.summary { white-space:pre-wrap; line-height:1.6 }
.muted { color:var(--pr-ink-muted) }.error { color:var(--pr-range) }
</style>
