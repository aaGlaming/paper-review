<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { ApiError, getReview } from '../../api'
import type {
  ChangeEvidence,
  ChangeListItem,
  DimensionResult,
  ReviewArchive,
} from '../../api/types'
import { concatSections, locateEvidence } from '../../composables/useOffsetLocator'
import ConflictItem from '../ConflictItem.vue'
import DimensionCard from '../DimensionCard.vue'
import SuggestionItem from '../SuggestionItem.vue'

const props = defineProps<{ reviewId: string | null }>()
const emit = defineEmits<{ close: [] }>()

const drawerOpen = computed({
  get: () => Boolean(props.reviewId),
  set: (open: boolean) => {
    if (!open && props.reviewId) closeDrawer()
  },
})
const review = ref<ReviewArchive | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const activeDimension = ref<string | null>(null)
const focusedChange = ref<{ key: string; evidence: ChangeEvidence } | null>(null)
const quoteSection = ref<HTMLElement | null>(null)
let requestSequence = 0

const archived = computed(() => review.value && 'dimensions' in review.value ? review.value : null)
const dimensions = computed(() => archived.value?.dimensions ?? [])
const sections = computed(() => review.value?.sections ?? [])
const body = computed(() => concatSections(sections.value))
const changes = computed(() => archived.value?.change_list ?? [])

function groupByKind(items: ChangeListItem[]): Array<{ kind: string; items: ChangeListItem[] }> {
  const groups = new Map<string, ChangeListItem[]>()
  for (const item of items) {
    const group = groups.get(item.kind) ?? []
    group.push(item)
    groups.set(item.kind, group)
  }
  return [...groups].map(([kind, groupedItems]) => ({ kind, items: groupedItems }))
}

const suggestionGroups = computed(() => groupByKind(changes.value.filter((item) => !item.finding_kind)))
const findingGroups = computed(() => groupByKind(changes.value.filter((item) => Boolean(item.finding_kind))))
const suggestionCount = computed(() => suggestionGroups.value.reduce((sum, group) => sum + group.items.length, 0))
const findingCount = computed(() => findingGroups.value.reduce((sum, group) => sum + group.items.length, 0))

function excerpt(evidence: ChangeEvidence): {
  quote: string
  before: string
  match: string
  after: string
  approximateNote: string
  noSnapshot: boolean
} {
  const quote = evidence.text ?? ''
  if (!sections.value.length) {
    return { quote, before: '', match: '', after: '', approximateNote: '', noSnapshot: true }
  }
  const location = locateEvidence(body.value, evidence)
  if (!location) {
    return { quote, before: '', match: '', after: '', approximateNote: '', noSnapshot: false }
  }
  const excerptStart = Math.max(0, location.start - 60)
  const matchEnd = location.start + location.text.length
  const excerptEnd = Math.min(body.value.length, matchEnd + 60)
  return {
    quote,
    before: body.value.slice(excerptStart, location.start),
    match: location.text,
    after: body.value.slice(matchEnd, excerptEnd),
    approximateNote: location.exact ? '' : location.approximateNote ?? '按偏移定位，未精确匹配',
    noSnapshot: false,
  }
}

const quoteRows = computed(() => dimensions.value.map((dimension) => ({
  dimension,
  result: dimension.quote ? excerpt({ text: dimension.quote }) : null,
})))
const focusedExcerpt = computed(() => focusedChange.value ? excerpt(focusedChange.value.evidence) : null)

function clearInternalState(): void {
  requestSequence += 1
  review.value = null
  loading.value = false
  errorMessage.value = ''
  activeDimension.value = null
  focusedChange.value = null
}

function closeDrawer(): void {
  clearInternalState()
  emit('close')
}

function messageFrom(reason: unknown): string {
  if (reason instanceof ApiError) return reason.message
  if (reason instanceof Error) return reason.message
  return String(reason)
}

watch(
  () => props.reviewId,
  async (reviewId) => {
    clearInternalState()
    if (!reviewId) return
    const sequence = requestSequence
    loading.value = true
    try {
      const result = await getReview(reviewId)
      if (sequence === requestSequence) review.value = result
    } catch (reason) {
      if (sequence === requestSequence) errorMessage.value = messageFrom(reason)
    } finally {
      if (sequence === requestSequence) loading.value = false
    }
  },
  { immediate: true },
)

async function scrollToQuotes(): Promise<void> {
  await nextTick()
  quoteSection.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

async function locateDimension(dimension: DimensionResult): Promise<void> {
  activeDimension.value = dimension.dimension_code
  focusedChange.value = null
  await scrollToQuotes()
  const target = Array.from(quoteSection.value?.querySelectorAll<HTMLElement>('[data-quote-code]') ?? [])
    .find((element) => element.dataset.quoteCode === dimension.dimension_code)
  target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}

async function locateChange(payload: { key: string; evidence: ChangeEvidence }): Promise<void> {
  focusedChange.value = payload
  activeDimension.value = null
  await scrollToQuotes()
}
</script>

<template>
  <el-drawer
    v-model="drawerOpen"
    title="评审记录详情"
    size="60%"
    direction="rtl"
    :destroy-on-close="true"
  >
    <p v-if="loading" class="record-drawer__status" role="status">正在读取…</p>
    <p v-else-if="errorMessage" class="record-drawer__error" role="alert">{{ errorMessage }}</p>
    <template v-else-if="review">
      <section class="record-drawer__section" aria-labelledby="record-drawer-dimensions">
        <h2 id="record-drawer-dimensions">五维档位</h2>
        <div v-if="dimensions.length" class="record-drawer__dimensions">
          <DimensionCard
            v-for="dimension in dimensions"
            :key="dimension.dimension_code"
            :dimension="dimension"
            @locate="locateDimension"
          />
        </div>
        <p v-else class="record-drawer__empty">该记录没有维度档位</p>
      </section>

      <section
        ref="quoteSection"
        class="record-drawer__section"
        aria-labelledby="record-drawer-quotes"
      >
        <h2 id="record-drawer-quotes">原句与定位</h2>
        <p v-if="!sections.length" class="record-drawer__snapshot-note">
          该记录没有正文快照，无法在正文中定位
        </p>
        <article
          v-for="row in quoteRows"
          :key="row.dimension.dimension_code"
          class="record-drawer__quote"
          :class="{ 'record-drawer__quote--active': activeDimension === row.dimension.dimension_code }"
          :data-quote-code="row.dimension.dimension_code"
        >
          <h3>{{ row.dimension.dimension_code }}</h3>
          <p v-if="!row.dimension.quote" class="record-drawer__no-quote">未给原句</p>
          <template v-else>
            <p class="record-drawer__original">{{ row.dimension.quote }}</p>
            <p v-if="row.result?.match" class="record-drawer__context">
              <span>{{ row.result.before }}</span><mark>{{ row.result.match }}</mark><span>{{ row.result.after }}</span>
            </p>
            <p v-if="row.result?.approximateNote" class="record-drawer__note">
              {{ row.result.approximateNote }}
            </p>
          </template>
        </article>
        <article v-if="focusedChange" class="record-drawer__focused-evidence">
          <h3>选中证据</h3>
          <p v-if="focusedExcerpt?.quote" class="record-drawer__original">{{ focusedExcerpt.quote }}</p>
          <p v-if="focusedExcerpt?.noSnapshot" class="record-drawer__snapshot-note">
            该记录没有正文快照，无法在正文中定位
          </p>
          <p v-if="focusedExcerpt?.match" class="record-drawer__context">
            <span>{{ focusedExcerpt.before }}</span><mark>{{ focusedExcerpt.match }}</mark><span>{{ focusedExcerpt.after }}</span>
          </p>
          <p v-if="focusedExcerpt?.approximateNote" class="record-drawer__note">
            {{ focusedExcerpt.approximateNote }}
          </p>
        </article>
      </section>

      <section class="record-drawer__section" aria-labelledby="record-drawer-changes">
        <h2 id="record-drawer-changes">修改建议</h2>
        <template v-if="suggestionCount || findingCount">
          <h3>维度建议（{{ suggestionCount }}）</h3>
          <template v-for="group in suggestionGroups" :key="`suggestion-${group.kind}`">
            <h4>{{ group.kind }}（{{ group.items.length }}）</h4>
            <SuggestionItem
              v-for="(item, index) in group.items"
              :key="`${item.upstream_id}-${index}`"
              :item="item"
              :located-key="null"
              @locate="locateChange"
            />
          </template>
          <h3>审查 findings（{{ findingCount }}）</h3>
          <template v-for="group in findingGroups" :key="`finding-${group.kind}`">
            <h4>{{ group.kind }}（{{ group.items.length }}）</h4>
            <ConflictItem
              v-for="(item, index) in group.items"
              :key="`${item.upstream_id}-${index}`"
              :item="item"
              :located-key="null"
              @locate="locateChange"
            />
          </template>
        </template>
        <p v-else class="record-drawer__empty">该记录没有修改建议</p>
      </section>
    </template>
  </el-drawer>
</template>

<style scoped>
.record-drawer__section {
  margin-bottom: var(--pr-space-7);
}

.record-drawer__section h2 {
  margin: 0 0 var(--pr-space-4);
  font-size: var(--pr-text-xl);
}

.record-drawer__section h3,
.record-drawer__section h4 {
  margin: var(--pr-space-4) 0 var(--pr-space-2);
}

.record-drawer__dimensions {
  display: grid;
  gap: var(--pr-space-4);
}

.record-drawer__quote,
.record-drawer__focused-evidence {
  margin-top: var(--pr-space-3);
  padding: var(--pr-space-3);
  border-left: 3px solid var(--pr-rule-strong);
  background: var(--pr-surface);
  scroll-margin-top: var(--pr-space-5);
}

.record-drawer__quote--active {
  border-left-color: var(--pr-primary-strong);
  background: var(--pr-primary-soft);
}

.record-drawer__quote h3,
.record-drawer__focused-evidence h3 {
  margin: 0 0 var(--pr-space-2);
}

.record-drawer__original,
.record-drawer__context,
.record-drawer__note,
.record-drawer__empty,
.record-drawer__snapshot-note,
.record-drawer__no-quote,
.record-drawer__status,
.record-drawer__error {
  margin: var(--pr-space-2) 0 0;
}

.record-drawer__original {
  white-space: pre-wrap;
  font-family: var(--pr-font-quote);
}

.record-drawer__context {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: var(--pr-leading-quote);
}

.record-drawer__context mark {
  background: var(--pr-insufficient-soft);
  color: var(--pr-ink);
  outline: 2px solid var(--pr-primary-strong);
}

.record-drawer__note,
.record-drawer__snapshot-note,
.record-drawer__empty {
  color: var(--pr-ink-muted);
}

.record-drawer__error {
  color: var(--pr-range);
}
</style>
