<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, listContests, listReviews } from '../api'
import type { ContestSummary, ReviewListResponse } from '../api/types'
import RecordsFilterBar from '../components/records/RecordsFilterBar.vue'
import RecordDrawer from '../components/records/RecordDrawer.vue'
import RequestActivity from '../components/RequestActivity.vue'
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
const route = useRoute()
const router = useRouter()

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

function closeDrawer(): void {
  selectedId.value = null
  if (route?.query.review !== undefined) {
    void router?.replace({ query: { ...route.query, review: undefined } })
  }
}

function contestLabel(id: string): string {
  const contest = contests.value.find((item) => item.contest_id === id)
  return contest ? `${contest.year} · ${contest.problem_code}` : id
}

onMounted(() => {
  const preset = route?.query.review
  if (typeof preset === 'string' && preset) selectedId.value = preset
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
    <RequestActivity :active="loading && Boolean(response)" label="正在更新评审记录" />

    <Transition name="content" mode="out-in">
      <RecordsTable
        v-if="response"
        :key="`${page}-${contestId}-${ownedOnly}`"
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
    </Transition>
    <RequestActivity v-if="!response && loading && !loadError" label="正在读取评审记录" :active="loading" />
    <RecordDrawer :review-id="selectedId" @close="closeDrawer" />
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
.content-enter-active,.content-leave-active { transition: opacity var(--pr-motion-content) var(--pr-motion-ease), transform var(--pr-motion-content) var(--pr-motion-ease); }
.content-enter-from,.content-leave-to { opacity: 0; transform: translateY(3px); }
@media (prefers-reduced-motion: reduce) { .content-enter-active,.content-leave-active { transition: none; } }
</style>
