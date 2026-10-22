<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

import {
  ApiError, askQuestion, createChatSession, deleteChatSession, generateSummary,
  listChatMessages, listChatSessions, listContests, listReviews, runAnalytics,
} from '../api'
import type {
  AnalyticsResponse, ChatMessageItem, ChatSessionItem, ContestSummary, SummaryResponse,
} from '../api/types'
import ChatAnalyticsBar from '../components/chat/ChatAnalyticsBar.vue'
import ChatComposer from '../components/chat/ChatComposer.vue'
import ChatMessageItemView from '../components/chat/ChatMessageItem.vue'
import ChatSessionList from '../components/chat/ChatSessionList.vue'
import RequestActivity from '../components/RequestActivity.vue'

const examples = [
  '某条记录的假设维为什么判证据不足？',
  '这道题有多少学生的建模维是证据不足？',
  '把本周提交整理成一段教研会摘要',
]
const router = useRouter()
const sessions = ref<ChatSessionItem[]>([])
const messages = ref<ChatMessageItem[]>([])
const contests = ref<ContestSummary[]>([])
const activeId = ref<string | null>(null)
const contestId = ref('')
const question = ref('')
const total = ref<number | null>(null)
const totalFailed = ref(false)
const pageError = ref('')
const busy = ref(false)
const sessionsLoading = ref(false)
const analyticsLoading = ref(false)
const analyticsError = ref('')
const analyticsResult = ref<AnalyticsResponse | SummaryResponse | null>(null)
const rejectedByMessage = ref<Record<string, number>>({})
const hasContest = computed(() => Boolean(contestId.value))

function errorText(reason: unknown): string {
  return reason instanceof ApiError ? reason.message : reason instanceof Error ? reason.message : String(reason)
}
function localMessage(role: 'user' | 'assistant', content: string): ChatMessageItem {
  return { message_id: `local-${Date.now()}-${Math.random()}`, role, content, refs: null, model_name: null, seq: messages.value.length + 1, created_at: new Date().toISOString() }
}
async function selectSession(id: string): Promise<void> {
  activeId.value = id
  analyticsResult.value = null
  try { messages.value = (await listChatMessages(id)).messages }
  catch (reason) { pageError.value = errorText(reason); messages.value = [] }
}
async function createSession(): Promise<void> {
  try {
    const item = await createChatSession()
    sessions.value = [item, ...sessions.value]
    activeId.value = item.session_id
    messages.value = []
    question.value = ''
    analyticsResult.value = null
  } catch (reason) { pageError.value = errorText(reason) }
}
async function removeSession(id: string): Promise<void> {
  try { await ElMessageBox.confirm('删除后会话历史将无法恢复，确定删除吗？', '删除会话', { type: 'warning' }) }
  catch { return }
  try {
    await deleteChatSession(id)
    sessions.value = sessions.value.filter((item) => item.session_id !== id)
    if (activeId.value === id) {
      activeId.value = null
      messages.value = []
      const next = sessions.value[0]
      if (next) await selectSession(next.session_id)
    }
  } catch (reason) { pageError.value = errorText(reason) }
}
async function send(text: string): Promise<void> {
  if (!activeId.value || !contestId.value || !text.trim() || busy.value) return
  const trimmed = text.trim()
  question.value = ''
  messages.value.push(localMessage('user', trimmed))
  busy.value = true
  pageError.value = ''
  try {
    const answer = await askQuestion(activeId.value, { question: trimmed, contestId: contestId.value })
    messages.value.push({
      message_id: answer.message_id, role: 'assistant', content: answer.content,
      refs: answer.refs, model_name: answer.model_name, seq: messages.value.length + 1,
      created_at: new Date().toISOString(),
    })
    if (answer.notifications.rejected) rejectedByMessage.value[answer.message_id] = answer.notifications.rejected
  } catch (reason) {
    question.value = trimmed
    pageError.value = errorText(reason)
  } finally { busy.value = false }
}
async function run(kind: 'bands' | 'conflicts' | 'summary'): Promise<void> {
  if (!contestId.value) return
  analyticsLoading.value = true
  analyticsError.value = ''
  analyticsResult.value = null
  try {
    if (kind === 'summary') {
      analyticsResult.value = await generateSummary({ contestId: contestId.value, top: 5 })
    } else {
      analyticsResult.value = await runAnalytics({ contestId: contestId.value, kind })
    }
  } catch (reason) { analyticsError.value = errorText(reason) }
  finally { analyticsLoading.value = false }
}
function openRecord(reviewId: string): void {
  void router.push({ path: '/records', query: { review: reviewId } })
}

onMounted(async () => {
  const tasks = await Promise.allSettled([
    listContests(), listReviews({ pageSize: 1 }), listChatSessions(),
  ])
  if (tasks[0].status === 'fulfilled') {
    contests.value = tasks[0].value.contests
    contestId.value = contests.value[0]?.contest_id ?? ''
  } else pageError.value = errorText(tasks[0].reason)
  if (tasks[1].status === 'fulfilled') total.value = tasks[1].value.total
  else totalFailed.value = true
  if (tasks[2].status === 'fulfilled') {
    sessions.value = tasks[2].value.sessions
    const first = sessions.value[0]
    if (first) await selectSession(first.session_id)
  } else pageError.value = errorText(tasks[2].reason)
})
</script>

<template>
  <main class="chat-page">
    <header class="chat-page__header">
      <div><h1>AI 问询</h1><p>{{ totalFailed || total === null ? '记录数量读取失败' : `你正在问询全部 ${total} 条提交记录` }}</p></div>
    </header>
    <p v-if="pageError" role="alert" class="chat-page__error">{{ pageError }}</p>
    <div class="chat-layout">
      <ChatSessionList :sessions="sessions" :active-id="activeId" :loading="sessionsLoading" @create="createSession" @select="selectSession" @remove="removeSession" />
      <section class="chat-main" aria-label="问询消息">
        <TransitionGroup name="message" tag="div" class="chat-main__messages" aria-live="polite">
          <div v-if="activeId && !messages.length" key="chat-empty" class="chat-empty">
            <p>选择一个问题开始：</p>
            <el-button v-for="example in examples" :key="example" text @click="question = example">{{ example }}</el-button>
          </div>
          <ChatMessageItemView v-for="message in messages" :key="message.message_id" :message="message" :rejected="rejectedByMessage[message.message_id]" @reference="openRecord" />
          <p v-if="!activeId" key="no-session" class="muted">新建会话后开始问询</p>
          <RequestActivity key="assistant-pending" :active="busy" label="正在整理回答" />
        </TransitionGroup>
        <ChatAnalyticsBar :result="analyticsResult" :loading="analyticsLoading" :error="analyticsError" @run="run" @clear="analyticsResult = null" />
        <ChatComposer v-model:question="question" :contests="contests" :contest-id="contestId" :busy="busy" @update:contest-id="contestId = $event" @send="send" />
        <p v-if="!hasContest" class="muted">请先选择赛题范围</p>
      </section>
    </div>
  </main>
</template>

<style scoped>
.chat-page { max-width:var(--pr-measure-wide, 1200px); margin:0 auto; padding:var(--pr-space-6) var(--pr-space-4) }
.chat-page__header { display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem }
.chat-page__header h1 { margin:0 }.chat-page__header p,.muted { color:var(--pr-ink-muted) }
.chat-layout { display:grid; grid-template-columns:280px minmax(0,1fr); gap:1.2rem; min-height:65vh }
.chat-main { display:flex; flex-direction:column; min-width:0; border-left:1px solid var(--pr-rule); padding-left:1.2rem }
.chat-main__messages { flex:1; min-height:240px; max-height:50vh; overflow:auto; padding:.5rem }
.message-enter-active,.message-leave-active { transition: opacity var(--pr-motion-list) var(--pr-motion-ease), transform var(--pr-motion-list) var(--pr-motion-ease) }
.message-enter-from,.message-leave-to { opacity:0; transform:translateY(5px) }
.message-move { transition:transform var(--pr-motion-list) var(--pr-motion-ease) }
.chat-empty { display:flex; flex-direction:column; align-items:flex-start; gap:.2rem; margin:2rem auto; max-width:36rem }
.chat-page__error { color:var(--pr-range) }
@media(max-width:900px) { .chat-layout { grid-template-columns:1fr; min-height:0 }.chat-main { border-left:0; border-top:1px solid var(--pr-rule); padding:1rem 0 0 }.chat-main__messages { max-height:40vh } }
@media(prefers-reduced-motion:reduce) { .message-enter-active,.message-leave-active,.message-move { transition:none } }
</style>
