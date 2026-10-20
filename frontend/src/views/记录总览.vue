<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue'

import { ApiError, listContests, listReviews } from '../api'
import type { ContestSummary, ReviewListResponse } from '../api/types'
import RecordsFilterBar from '../components/records/RecordsFilterBar.vue'
import RecordDrawer from '../components/records/RecordDrawer.vue'
import RecordsTable from '../components/records/RecordsTable.vue'

const contests = shallowRef<ContestSummary[]>([])
const response = shallowRef<ReviewListResponse | null>(null)
const contestId = shallowRef('')
const ownedOnly = shallowRef(false)
const page = shallowRef(1)
const pageSize = 20
const loading = shallowRef(false)
const loadError = shallowRef('')
const selectedId = ref<string | null>(null)

function errorMessage(reason: unknown): string {
  return reason instanceof ApiError
    ? reason.message
    : reason instanceof Error ? reason.message : String(reason)
}

async function loadContests(): Promise<void> {
  try {
    contests.value = (await listContests()).contests
  } catch (reason) {
    loadError.value = errorMessage(reason)
  }
}

async function loadReviews(): Promise<void> {
  loading.value = true
  loadError.value = ''
  response.value = null
  try {
    const params: Parameters<typeof listReviews>[0] = { page: page.value, pageSize }
    if (contestId.value) params.contestId = contestId.value
    if (ownedOnly.value) params.owner = 'owned'
    response.value = await listReviews(params)
  } catch (reason) {
    loadError.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

function selectContest(value: string): void {
  contestId.value = value
  page.value = 1
  void loadReviews()
}

function toggleOwner(value: boolean): void {
  ownedOnly.value = value
  page.value = 1
  void loadReviews()
}

function refresh(): void {
  void loadReviews()
}

function changePage(value: number): void {
  page.value = value
  void loadReviews()
}

function contestLabel(id: string): string {
  const contest = contests.value.find((item) => item.contest_id === id)
  return contest ? `${contest.year} · ${contest.problem_code}` : id
}

onMounted(() => {
  void loadContests()
  void loadReviews()
})
</script>

<template>
  <main class="records">
    <header class="records__header">
      <h1>记录总览</h1>
      <p v-if="response" class="records__scope">
        当前范围：{{ response.scope === 'all' ? '全部学生' : '我的记录' }}
      </p>
    </header>

    <p v-if="loadError" class="records__error" role="alert">
      {{ loadError }}
    </p>

    <RecordsFilterBar
      :contests="contests"
      :contest-id="contestId"
      :owned-only="ownedOnly"
      :loading="loading"
      @select-contest="selectContest"
      @toggle-owner="toggleOwner"
      @refresh="refresh"
    />

    <RecordsTable
      v-if="response"
      :reviews="response.reviews"
      :scope="response.scope"
      :total="response.total"
      :page="page"
      :page-size="pageSize"
      @page-change="changePage"
      @row-click="selectedId = $event"
    >
      <template #contest="{ row }">
        {{ contestLabel(row.contest_id) }}
      </template>
    </RecordsTable>
    <p v-else-if="loading && !loadError" class="records__loading" aria-live="polite">
      正在读取评审记录…
    </p>
    <RecordDrawer :review-id="selectedId" @close="selectedId = null" />
  </main>
</template>

<style scoped>
.records {
  max-width: var(--pr-measure-wide, 1200px);
  margin: 0 auto;
  padding: var(--pr-space-6) var(--pr-space-4);
}

.records__header h1 {
  margin: 0;
  font-size: var(--pr-text-2xl);
}

.records__header p,
.records__error,
.records__loading {
  margin: var(--pr-space-2) 0 0;
  color: var(--pr-ink-muted);
}

.records__error {
  color: var(--pr-range);
}
</style>
