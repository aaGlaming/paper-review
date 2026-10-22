<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, shallowRef } from 'vue'

import { ApiError, getDashboardSummary, getDashboardTrend } from '../api'
import type { DashboardSummary, DashboardTrend } from '../api/types'
import { echarts } from '../lib/echarts'
import MotionNumber from '../components/MotionNumber.vue'
import RequestActivity from '../components/RequestActivity.vue'

type ChartName = 'trend' | 'contests' | 'bands' | 'gaps' | 'conflicts' | 'hotspots' | 'citation'
const summary = shallowRef<DashboardSummary | null>(null)
const trend = shallowRef<DashboardTrend | null>(null)
const loadError = shallowRef('')
const loading = shallowRef(true)
const elements: Partial<Record<ChartName, HTMLElement>> = {}
const instances: Array<ReturnType<typeof echarts.init>> = []
function cssToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
const palette = ['--pr-chart-1', '--pr-chart-2', '--pr-chart-3', '--pr-conflict'].map(cssToken)
const ink = cssToken('--pr-ink')
const rule = cssToken('--pr-rule')
const surface = cssToken('--pr-surface')
const alertColor = cssToken('--pr-conflict')
const textStyle = { color: ink, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)' }
const axisLine = { lineStyle: { color: rule } }

function errorText(reason: unknown): string {
  return reason instanceof ApiError
    ? reason.message
    : reason instanceof Error ? reason.message : String(reason)
}

function setChartElement(name: ChartName, value: Element | null): void {
  if (value instanceof HTMLElement) elements[name] = value
  else delete elements[name]
}

function createChart(name: ChartName, option: Record<string, unknown>): void {
  const element = elements[name]
  if (!element) return
  const chart = echarts.init(element)
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  chart.setOption({
    animation: !reduceMotion,
    animationDuration: reduceMotion ? 0 : 420,
    animationDurationUpdate: reduceMotion ? 0 : 240,
    animationEasing: 'cubicOut',
    ...option,
  })
  instances.push(chart)
}

function renderCharts(): void {
  if (trend.value?.series.length) {
    createChart('trend', {
      color: palette,
      textStyle,
      tooltip: { trigger: 'axis' },
      legend: { textStyle },
      grid: { left: 42, right: 18, top: 34, bottom: 28 },
      xAxis: { type: 'category', data: trend.value.series.map((item) => item.date), axisLine },
      yAxis: { type: 'value', axisLine, splitLine: { lineStyle: { color: rule } } },
      series: [
        { name: '总提交', type: 'line', data: trend.value.series.map((item) => item.total), smooth: false },
        { name: '无主', type: 'line', data: trend.value.series.map((item) => item.ownerless), smooth: false },
      ],
    })
  }
  if (summary.value?.contests.length) {
    createChart('contests', {
      color: palette,
      textStyle,
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle },
      series: [{
        type: 'pie', radius: ['42%', '72%'],
        data: summary.value.contests.map((item) => ({ name: item.contest_id || '未绑定赛题', value: item.review_count })),
        label: { color: ink, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)' },
      }],
    })
  }
  if (summary.value?.bands.length) {
    const dimensions = summary.value.bands
    createChart('bands', {
      color: palette,
      textStyle,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { textStyle },
      grid: { left: 54, right: 16, top: 38, bottom: 28 },
      xAxis: { type: 'category', data: dimensions.map((item) => item.dimension_code), axisLine },
      yAxis: { type: 'value', axisLine, splitLine: { lineStyle: { color: rule } } },
      series: ['充分', '基本', '不足', '证据不足'].map((band) => ({
        name: band, type: 'bar', stack: 'total',
        data: dimensions.map((item) => item.counts[band as keyof typeof item.counts]),
        label: { show: true, position: 'inside', color: surface, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)' },
      })),
    })
  }
  if (summary.value?.insufficient_top.length) {
    const rows = summary.value.insufficient_top.filter((item) => item.insufficient_total > 0)
    if (rows.length) createChart('gaps', {
      color: [alertColor], textStyle,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 88, right: 18, top: 16, bottom: 26 },
      xAxis: { type: 'value', axisLine, splitLine: { lineStyle: { color: rule } } },
      yAxis: { type: 'category', data: rows.map((item) => item.dimension_code).reverse(), axisLine },
      series: [{ type: 'bar', data: rows.map((item) => item.insufficient_total).reverse(), label: { show: true, position: 'right', color: ink, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)' } }],
    })
  }
  if (summary.value?.conflicts.length) {
    createChart('conflicts', {
      color: palette,
      textStyle,
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle },
      series: [{
        type: 'pie', radius: '68%',
        data: summary.value.conflicts.map((item) => ({ name: item.kind, value: item.count })),
        label: { color: ink, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)' },
      }],
    })
  }
  if (summary.value?.hotspots.length) {
    const rows = summary.value.hotspots
    createChart('hotspots', {
      color: [palette[1]], textStyle,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 118, right: 24, top: 12, bottom: 26 },
      xAxis: { type: 'value', axisLine, splitLine: { lineStyle: { color: rule } } },
      yAxis: { type: 'category', data: rows.map((item) => item.target).reverse(), axisLine },
      series: [{ type: 'bar', data: rows.map((item) => item.count).reverse(), label: { show: true, position: 'right', color: ink, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)' } }],
    })
  }
  if (summary.value && summary.value.citation.total_dimensions > 0) {
    createChart('citation', {
      color: [alertColor], textStyle,
      series: [{
        type: 'gauge', min: 0, max: 100,
        progress: { show: true, width: 12, itemStyle: { color: alertColor } },
        axisLine: { lineStyle: { width: 12, color: [[1, rule]] } },
        pointer: { show: false },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        detail: { valueAnimation: false, formatter: '{value}%', color: ink, fontFamily: 'var(--pr-font-data, ui-monospace, monospace)', fontSize: 26, offsetCenter: [0, '5%'] },
        data: [{ value: Number((summary.value.citation.citation_rate * 100).toFixed(1)), name: '引用失败率' }],
      }],
    })
  }
}

function resizeCharts(): void {
  for (const chart of instances) chart.resize()
}

onMounted(async () => {
  loading.value = true
  const [summaryResult, trendResult] = await Promise.allSettled([
    getDashboardSummary(),
    getDashboardTrend(30),
  ])
  if (summaryResult.status === 'fulfilled') summary.value = summaryResult.value
  else loadError.value = errorText(summaryResult.reason)
  if (trendResult.status === 'fulfilled') trend.value = trendResult.value
  else if (!loadError.value) loadError.value = errorText(trendResult.reason)
  loading.value = false
  await nextTick()
  renderCharts()
  window.addEventListener('resize', resizeCharts)
})

// ECharts 实例随路由组件创建；销毁时逐个 dispose，避免路由切换后 canvas 与监听器泄漏。
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  for (const chart of instances) chart.dispose()
  instances.length = 0
})
</script>

<template>
  <main class="dashboard">
    <header class="dashboard__header">
      <div><h1>数据大屏</h1><p>评审记录汇总 · 最近 30 天趋势</p></div>
      <span v-if="summary?.cached || trend?.cached" class="dashboard__cache">缓存数据</span>
    </header>
    <p v-if="loadError" class="dashboard__error" role="alert">{{ loadError }}</p>
    <RequestActivity v-else-if="loading" :active="loading" label="正在读取大屏数据" />
    <div v-else class="dashboard__grid">
      <section class="dashboard__module dashboard__module--wide" data-dashboard-module>
        <h2>提交总量趋势</h2>
        <div v-if="trend?.series.length" :ref="(el) => setChartElement('trend', el as Element | null)" class="dashboard__chart" data-chart="trend" />
        <p v-if="!summary" class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module" data-dashboard-module>
        <h2>赛题分布</h2>
        <div v-if="summary?.contests.length" :ref="(el) => setChartElement('contests', el as Element | null)" class="dashboard__chart" data-chart="contests" />
        <p v-else class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module dashboard__module--wide" data-dashboard-module>
        <h2>五维档位分布</h2>
        <div v-if="summary?.bands.length" :ref="(el) => setChartElement('bands', el as Element | null)" class="dashboard__chart" data-chart="bands" />
        <p v-else class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module" data-dashboard-module>
        <h2>证据不足 Top 维度</h2>
        <div v-if="summary?.insufficient_top.some((item) => item.insufficient_total > 0)" :ref="(el) => setChartElement('gaps', el as Element | null)" class="dashboard__chart" data-chart="gaps" />
        <p v-else class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module" data-dashboard-module>
        <h2>冲突类型分布</h2>
        <div v-if="summary?.conflicts.length" :ref="(el) => setChartElement('conflicts', el as Element | null)" class="dashboard__chart" data-chart="conflicts" />
        <p v-else class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module" data-dashboard-module>
        <h2>高频冲突对象 Top 10</h2>
        <div v-if="summary?.hotspots.length" :ref="(el) => setChartElement('hotspots', el as Element | null)" class="dashboard__chart" data-chart="hotspots" />
        <p v-else class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module" data-dashboard-module>
        <h2>引用失败率</h2>
        <div v-if="summary && summary.citation.total_dimensions > 0" :ref="(el) => setChartElement('citation', el as Element | null)" class="dashboard__chart dashboard__chart--gauge" data-chart="citation" />
        <p v-else class="dashboard__empty">暂无数据</p>
      </section>
      <section class="dashboard__module dashboard__module--metrics" data-dashboard-module>
        <h2>关键指标</h2>
        <div v-if="summary" class="dashboard__metrics">
          <article><span>总提交</span><strong><MotionNumber :value="summary.cards.total_submissions" /></strong></article>
          <article><span>本周新增</span><strong><MotionNumber :value="summary.cards.weekly_new" /></strong></article>
          <article><span>待处理冲突</span><strong><MotionNumber :value="summary.cards.pending_conflicts" /></strong></article>
          <article><span>gold 一致率</span><strong><MotionNumber v-if="summary.gold" :value="summary.gold.agreement * 100" :decimals="1" suffix="%" /><template v-else>暂无 gold 数据</template></strong></article>
        </div>
        <p v-if="summary && summary.cards.parse_only > 0" class="dashboard__parse-only" data-testid="parse-only-count">
          另有 {{ summary.cards.parse_only }} 篇仅解析未评分
        </p>
        <p v-if="!summary" class="dashboard__empty">暂无数据</p>
      </section>
    </div>
  </main>
</template>

<style scoped>
.dashboard { max-width: 1440px; margin: 0 auto; padding: var(--pr-space-6) var(--pr-space-4); color: var(--pr-ink); }
.dashboard__header { display:flex; align-items:center; justify-content:space-between; margin-bottom:var(--pr-space-5); }
.dashboard__header h1 { margin:0; font-size:var(--pr-text-2xl); }
.dashboard__header p { margin:var(--pr-space-1) 0 0; color:var(--pr-ink-muted); }
.dashboard__cache,.dashboard__empty { color:var(--pr-ink-muted); font-family:var(--pr-font-data, ui-monospace, monospace); }
.dashboard__error { color:var(--pr-range); }
.dashboard__grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:var(--pr-space-4); }
.dashboard__module { animation:dashboard-arrive var(--pr-motion-content) var(--pr-motion-ease) both; }
.dashboard__module:nth-child(1) { animation-delay:0ms; }
.dashboard__module:nth-child(2) { animation-delay:45ms; }
.dashboard__module:nth-child(3) { animation-delay:90ms; }
.dashboard__module:nth-child(4) { animation-delay:135ms; }
.dashboard__module:nth-child(n+5) { animation-delay:0ms; }
@keyframes dashboard-arrive { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:translateY(0); } }
.dashboard__module { min-width:0; padding:var(--pr-space-4); border:1px solid var(--pr-rule); background:var(--pr-surface); }
.dashboard__module h2 { margin:0 0 var(--pr-space-3); font-size:var(--pr-text-lg); font-weight:600; }
.dashboard__module--wide { grid-column:span 2; }
.dashboard__module--metrics { grid-column:span 2; }
.dashboard__chart { width:100%; height:260px; }
.dashboard__chart--gauge { height:220px; }
.dashboard__empty { min-height:36px; display:flex; align-items:center; margin:0; }
.dashboard__metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:var(--pr-space-3); }
.dashboard__metrics article { min-height:84px; display:flex; flex-direction:column; justify-content:space-between; padding:var(--pr-space-3); border-left:2px solid var(--pr-rule); }
.dashboard__metrics span { color:var(--pr-ink-muted); }
.dashboard__metrics strong { font:600 1.4rem var(--pr-font-data, ui-monospace, monospace); color:var(--pr-ink); }
.dashboard__parse-only { margin:var(--pr-space-3) 0 0; color:var(--pr-ink-muted); font-size:var(--pr-text-sm); }
@media (max-width:900px) { .dashboard__grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:620px) { .dashboard__grid { grid-template-columns:1fr; } .dashboard__module--wide,.dashboard__module--metrics { grid-column:auto; } .dashboard__metrics { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (prefers-reduced-motion:reduce) { .dashboard__module { animation:none; } }
</style>
