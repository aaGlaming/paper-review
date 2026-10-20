<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import type { ReviewListItem, ReviewListResponse } from '../../api/types'

const props = defineProps<{
  reviews: ReviewListItem[]
  scope: ReviewListResponse['scope'] | null
  total: number
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  pageChange: [page: number]
  rowClick: [reviewId: string]
}>()
const tableRef = ref<{ $el?: HTMLElement } | null>(null)

function syncRowIds(): void {
  const rows = tableRef.value?.$el?.querySelectorAll('tbody .el-table__row')
  rows?.forEach((element, index) => {
    const item = props.reviews[index]
    if (item) {
      element.setAttribute('data-row-id', item.review_id)
      element.setAttribute('title', '查看详情')
    }
  })
}

watch(() => props.reviews, () => void nextTick(syncRowIds), { flush: 'post', immediate: true })
onMounted(() => void nextTick(syncRowIds))

function formatTime(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
  const date = new Date(hasTimezone ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function dimensions(row: ReviewListItem): Array<[string, string | null]> {
  return Object.entries(row.bands).slice(0, 5)
}
</script>

<template>
  <section class="records-table">
    <p v-if="total === 0" class="records-table__empty">
      还没有评审记录
    </p>
    <template v-else>
      <el-table
        ref="tableRef"
        :data="reviews"
        row-key="review_id"
        class="records-table__grid"
        @row-click="(row: ReviewListItem) => emit('rowClick', row.review_id)"
      >
        <el-table-column label="提交时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="scope === 'all'" label="学生" min-width="120">
          <template #default="{ row }">{{ row.owner_username ?? '无主' }}</template>
        </el-table-column>
        <el-table-column label="赛题" min-width="120">
          <template #default="{ row }"><slot name="contest" :row="row">{{ row.contest_id }}</slot></template>
        </el-table-column>
        <el-table-column label="量规版本" min-width="140">
          <template #default="{ row }">{{ row.rubric_id }} v{{ row.rubric_version }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="140" />
        <el-table-column label="档位概览" min-width="220">
          <template #default="{ row }">
            <div class="records-table__bands">
              <el-tag v-for="[code, band] in dimensions(row)" :key="code" size="small" effect="plain">
                {{ code }} {{ band ?? '—' }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="finding_total" label="冲突数" min-width="90" />
      </el-table>
      <el-pagination
        class="records-table__pagination"
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="emit('pageChange', $event)"
      />
    </template>
  </section>
</template>

<style scoped>
.records-table__empty {
  margin: var(--pr-space-6) 0;
  padding: var(--pr-space-6);
  border: 1px dashed var(--pr-rule-strong);
  border-radius: var(--pr-radius);
  color: var(--pr-ink-muted);
  text-align: center;
}

.records-table__bands {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-1);
}

.records-table__grid :deep(.el-table__row) {
  cursor: pointer;
}

.records-table__pagination {
  justify-content: end;
  margin-top: var(--pr-space-4);
}
</style>
