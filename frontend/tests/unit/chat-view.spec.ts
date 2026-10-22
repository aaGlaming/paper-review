import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import type { ChatMessageItem, ChatSessionItem, ContestSummary } from '../../src/api/types'
import ChatView from '../../src/views/AI问询.vue'

vi.mock('../../src/api', async (original) => {
  const actual = await original<typeof import('../../src/api')>()
  return {
    ...actual, askQuestion: vi.fn(), createChatSession: vi.fn(), deleteChatSession: vi.fn(),
    generateSummary: vi.fn(), listChatMessages: vi.fn(), listChatSessions: vi.fn(),
    listContests: vi.fn(), listReviews: vi.fn(), runAnalytics: vi.fn(),
  }
})
const session: ChatSessionItem = { session_id:'s1', title:'会话一', created_at:'now', updated_at:'now', message_count:0 }
const contest: ContestSummary = { contest_id:'contest-test', year:2026, problem_code:'X', title:'练习', statement:'', status:'published', rubric:null, constraints:[], pitfall_count:0, exemplar_count:0 }
function message(role:'user'|'assistant', content:string, id='m1'): ChatMessageItem {
  return { message_id:id, role, content, refs:[], model_name:'model', seq:1, created_at:'now' }
}
async function mountChat(history: ChatMessageItem[] = []) {
  vi.mocked(api.listContests).mockResolvedValue({ contests:[contest] })
  vi.mocked(api.listReviews).mockResolvedValue({ reviews:[], total:7, page:1, page_size:1, scope:'all' })
  vi.mocked(api.listChatSessions).mockResolvedValue({ sessions:[session] })
  vi.mocked(api.listChatMessages).mockResolvedValue({ session_id:'s1', messages:history })
  vi.mocked(api.runAnalytics).mockResolvedValue({ kind:'conflicts', result:{ contest_id:'contest-test', reviews_with_changes:0, kinds:{}, hotspots:[], finding_total:0, unparsable:0 } })
  vi.mocked(api.generateSummary).mockResolvedValue({ content:'摘要文本', refs:[], model_name:'m', notes:{ rejected:0, evidence_short:2 } })
  const router = createRouter({ history:createMemoryHistory(), routes:[{ path:'/chat', component:ChatView },{ path:'/records', component:{ template:'<div>records</div>' } }] })
  await router.push('/chat'); await router.isReady()
  const wrapper = mount(ChatView, { global:{ plugins:[ElementPlus,router] } })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => { vi.clearAllMocks() })

describe('AI 问询页', () => {
  it('显示三条例问，点击只填入输入框', async () => {
    const { wrapper } = await mountChat()
    const example = '某条记录的假设维为什么判证据不足？'
    const exampleButton = wrapper.findAll('button').find((button) => button.text() === example)!
    await exampleButton.trigger('click')
    expect(wrapper.text()).toContain(example)
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe(example)
    expect(api.askQuestion).not.toHaveBeenCalled()
  })
  it('先显示用户消息，返回后显示助手消息', async () => {
    let resolve!: (value: Awaited<ReturnType<typeof api.askQuestion>>) => void
    vi.mocked(api.askQuestion).mockImplementation(() => new Promise((done) => { resolve = done }))
    const { wrapper } = await mountChat()
    await wrapper.get('textarea').setValue('请解释记录')
    await wrapper.get('.composer button').trigger('click')
    expect(wrapper.text()).toContain('请解释记录')
    expect(wrapper.get('[data-testid="request-activity"]').text()).toContain('正在整理回答')
    resolve({ message_id:'m2', content:'助手回答', refs:[], model_name:'m', notifications:{ rejected:0, unused:0 } })
    await flushPromises()
    expect(wrapper.text()).toContain('助手回答')
    expect(wrapper.find('[data-testid="request-activity"]').exists()).toBe(false)
  })
  it('将两个引用渲染为可点 chip 并带 review 查询参数跳转', async () => {
    const { wrapper, router } = await mountChat([message('assistant','详情 [review_id=r1 dim=assumption] 和 [review_id=r2 dim=evidence]')])
    const chips = wrapper.findAll('[data-ref-chip]')
    expect(chips).toHaveLength(2)
    await chips[1]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/records')
    expect(router.currentRoute.value.query.review).toBe('r2')
  })
  it('显示被移除的引用数量', async () => {
    vi.mocked(api.askQuestion).mockResolvedValue({ message_id:'m2', content:'答案', refs:[], model_name:'m', notifications:{ rejected:2, unused:0 } })
    const { wrapper } = await mountChat()
    await wrapper.get('textarea').setValue('问题')
    await wrapper.get('.composer button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('已移除 2 条')
  })
  it('失败显示错误并保留输入内容', async () => {
    vi.mocked(api.askQuestion).mockRejectedValue(new api.ApiError(502,'服务暂不可用'))
    const { wrapper } = await mountChat()
    await wrapper.get('textarea').setValue('方便重试的问题')
    await wrapper.get('.composer button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('服务暂不可用')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('方便重试的问题')
  })
})
