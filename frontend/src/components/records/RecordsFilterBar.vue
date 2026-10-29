<script setup lang="ts">
import type { ContestSummary } from '../../api/types'

defineProps<{
  contests: ContestSummary[]
  contestId: string
  ownedOnly: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  selectContest: [contestId: string]
  toggleOwner: [enabled: boolean]
  refresh: []
}>()
</script>

<template>
  <section class="records-filters" aria-label="筛选记录">
    <label class="records-filters__contest">
      <span>赛题</span>
      <el-select
        :model-value="contestId"
        aria-label="赛题筛选"
        @change="emit('selectContest', $event)"
      >
        <el-option label="全部" value="" />
        <el-option
          v-for="contest in contests"
          :key="contest.contest_id"
          :label="`${contest.year} · ${contest.problem_code}`"
          :value="contest.contest_id"
        />
      </el-select>
    </label>
    <label class="records-filters__owned">
      <el-switch
        :model-value="ownedOnly"
        aria-label="只显示有主记录"
        @change="emit('toggleOwner', Boolean($event))"
      />
      <span>只显示有主记录</span>
    </label>
    <el-button :loading="loading" @click="emit('refresh')">刷新</el-button>
  </section>
</template>

<style scoped>
.records-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: var(--pr-space-4);
  margin: var(--pr-space-5) 0 var(--pr-space-4);
}

.records-filters__contest,
.records-filters__owned {
  display: inline-flex;
  align-items: center;
  gap: var(--pr-space-2);
}

.records-filters__contest {
  flex-direction: column;
  align-items: start;
}
</style>
